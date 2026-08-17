"""Incremental, replay-safe materialization of Clawer publications into Hover."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import timedelta
from datetime import timezone as datetime_timezone
from uuid import UUID, uuid4

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone

from hover.actions_review_requests import (
    ReviewRequestMaterializationError,
    materialize_disputed_details,
)
from hover.actions_suggested_actions import (
    create_suggested_action_for_generated_item,
    send_suggested_action_projection_event,
)
from hover.clawer_sync import ClawerSync, ClawerSyncError
from hover.models import (
    ConnectedAccount,
    EvidenceLink,
    GeneratedItem,
    PublicationSyncAttempt,
    SpaceAttachment,
)
from hover.publication_contracts import (
    AnalysisPayload,
    ClawerPublication,
    DecisionPayload,
    DigestPayload,
    FeedUpdatePayload,
    ProgressUpdatePayload,
    SuggestedActionPayload,
    publication_envelope_hash,
)
from hover.telemetry import (
    HoverTelemetryEvent,
    HoverTelemetryOutcome,
    count_bucket,
    emit_hover_telemetry_on_commit,
    lag_bucket,
)
from zerver.actions.message_send import internal_send_stream_message
from zerver.actions.streams import bulk_add_subscriptions
from zerver.lib.message import truncate_topic
from zerver.models.groups import UserGroupMembership
from zerver.models.messages import Message
from zerver.models.users import UserProfile

MAX_PUBLICATION_SYNC_BATCH = 20
PUBLICATION_SYNC_LEASE_DURATION = timedelta(minutes=5)
PUBLICATION_SYNC_POLL_INTERVAL = timedelta(minutes=1)
PUBLICATION_SYNC_MAX_BACKOFF_SECONDS = 3600


class PublicationSyncError(Exception):
    """Content-free operational failure suitable for retry diagnostics."""

    def __init__(self, error_code: str, *, retryable: bool) -> None:
        super().__init__(error_code)
        self.error_code = error_code
        self.retryable = retryable


@dataclass(frozen=True)
class PublicationSyncResult:
    attachment_id: int
    created: int
    replayed: int
    next_cursor: str
    has_more: bool


def _bullets(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items)


def render_publication(publication: ClawerPublication) -> tuple[str, str]:
    """Render the six contracts without product-, Source-, or demo-name checks."""
    payload = publication.payload
    if isinstance(payload, DigestPayload):
        content = (
            f"## {payload.title}\n\n"
            f"### Operations\n\n{payload.operation}\n\n"
            f"### Marketing\n\n{payload.marketing}"
        )
    elif isinstance(payload, FeedUpdatePayload):
        content = f"## {payload.title}\n\n{_bullets(payload.developments)}"
    elif isinstance(payload, ProgressUpdatePayload):
        sections = [
            f"## {payload.title}",
            f"**Status:** {payload.status.replace('_', ' ').title()}",
            f"### Updates\n\n{_bullets(payload.updates)}",
        ]
        if payload.resolved_items:
            sections.append(f"### Completed\n\n{_bullets(payload.resolved_items)}")
        if payload.blockers:
            sections.append(f"### Blockers\n\n{_bullets(payload.blockers)}")
        content = "\n\n".join(sections)
    elif isinstance(payload, DecisionPayload):
        content = (
            f"## {payload.title}\n\n"
            f"**Decision:** {payload.decision}\n\n"
            f"**Rationale:** {payload.rationale}\n\n"
            f"**Lifecycle:** {payload.lifecycle.title()}"
        )
    elif isinstance(payload, SuggestedActionPayload):
        sections = [
            "## Suggested action",
            payload.wording,
        ]
        if payload.proposed_assignee is not None:
            sections.append(f"**Proposed assignee:** {payload.proposed_assignee.display_name}")
        if payload.proposed_due_date is not None:
            sections.append(f"**Proposed due date:** {payload.proposed_due_date.isoformat()}")
        content = "\n\n".join(sections)
    elif isinstance(payload, AnalysisPayload):
        findings = "\n".join(
            f"- **{finding.title}:** {finding.detail}" for finding in payload.findings
        )
        content = f"## {payload.title}\n\n{payload.summary}\n\n### Findings\n\n{findings}"
        if payload.sentiment is not None:
            content += (
                f"\n\n### Sentiment\n\n"
                f"**{payload.sentiment.label.title()}:** {payload.sentiment.summary}"
            )
    else:  # pragma: no cover - the discriminated transport union is exhaustive.
        raise PublicationSyncError("unsupported_publication_contract", retryable=False)

    if len(content) > settings.MAX_MESSAGE_LENGTH:
        raise PublicationSyncError("publication_content_too_long", retryable=False)
    topic = truncate_topic(publication.producer_name)
    return topic, content


def _opaque_hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _assistant_is_valid(assistant: UserProfile, attachment: SpaceAttachment) -> bool:
    configured_email = str(settings.HOVER_ASSISTANT_EMAIL).strip().casefold()
    return (
        bool(configured_email)
        and assistant.realm_id == attachment.realm_id
        and assistant.is_active
        and assistant.is_bot
        and assistant.delivery_email.strip().casefold() == configured_email
    )


def _validate_syncable_attachment(
    attachment: SpaceAttachment,
    assistant: UserProfile,
) -> None:
    if (
        attachment.state != SpaceAttachment.State.ACTIVE
        or attachment.space.state != attachment.space.State.LAUNCHED
        or attachment.space.stream is None
        or attachment.source.account.approval_state != ConnectedAccount.ApprovalState.APPROVED
    ):
        raise PublicationSyncError("attachment_not_syncable", retryable=False)
    if not _assistant_is_valid(assistant, attachment):
        raise PublicationSyncError("invalid_hover_assistant", retryable=False)


def _claim_attachment(
    *, attachment_id: int, assistant: UserProfile
) -> tuple[SpaceAttachment, UUID, str]:
    with transaction.atomic(durable=True):
        attachment = (
            SpaceAttachment.objects.select_for_update(no_key=True, of=("self",))
            .select_related("realm", "space", "space__stream", "source", "source__account")
            .get(id=attachment_id)
        )
        _validate_syncable_attachment(attachment, assistant)
        now = timezone.now()
        if (
            attachment.publication_sync_state == SpaceAttachment.PublicationSyncState.LEASED
            and attachment.publication_sync_lease_expires_at is not None
            and attachment.publication_sync_lease_expires_at > now
        ):
            raise PublicationSyncError("publication_sync_already_leased", retryable=True)

        lease_token = uuid4()
        attachment.publication_sync_state = SpaceAttachment.PublicationSyncState.LEASED
        attachment.publication_sync_lease_token = lease_token
        attachment.publication_sync_lease_expires_at = now + PUBLICATION_SYNC_LEASE_DURATION
        attachment.save(
            update_fields=[
                "publication_sync_state",
                "publication_sync_lease_token",
                "publication_sync_lease_expires_at",
                "date_updated",
            ]
        )
        return attachment, lease_token, attachment.publication_cursor


def _record_failure(
    *,
    attachment_id: int,
    lease_token: UUID,
    error_code: str,
    retryable: bool,
    requested_cursor: str,
    returned_cursor: str = "",
    publication_count: int = 0,
) -> None:
    realm_id: int | None = None
    with transaction.atomic(durable=True):
        attachment = SpaceAttachment.objects.select_for_update(no_key=True).get(id=attachment_id)
        # A worker whose lease expired must not overwrite the newer worker's state.
        if attachment.publication_sync_lease_token != lease_token:
            return
        realm_id = attachment.realm_id
        attachment.last_publication_sync_error = error_code[:64]
        attachment.publication_sync_failures += 1
        attachment.publication_sync_lease_token = None
        attachment.publication_sync_lease_expires_at = None
        if retryable:
            attachment.publication_sync_state = SpaceAttachment.PublicationSyncState.BACKOFF
            backoff_seconds = min(
                60 * (2 ** min(attachment.publication_sync_failures - 1, 6)),
                PUBLICATION_SYNC_MAX_BACKOFF_SECONDS,
            )
            attachment.next_publication_sync_at = timezone.now() + timedelta(
                seconds=backoff_seconds
            )
        else:
            attachment.publication_sync_state = SpaceAttachment.PublicationSyncState.BLOCKED
            attachment.next_publication_sync_at = None
        attachment.save(
            update_fields=[
                "last_publication_sync_error",
                "publication_sync_failures",
                "publication_sync_state",
                "publication_sync_lease_token",
                "publication_sync_lease_expires_at",
                "next_publication_sync_at",
                "date_updated",
            ]
        )
        PublicationSyncAttempt.objects.create(
            realm=attachment.realm,
            attachment=attachment,
            outcome=PublicationSyncAttempt.Outcome.ERROR,
            error_code=error_code[:64],
            retryable=retryable,
            publication_count=publication_count,
            requested_cursor_hash=_opaque_hash(requested_cursor),
            returned_cursor_hash=_opaque_hash(returned_cursor) if returned_cursor else "",
        )
    assert realm_id is not None
    if error_code in {
        "invalid_upstream_contract",
        "publication_content_too_long",
        "unsupported_publication_contract",
    }:
        outcome = HoverTelemetryOutcome.CONTRACT_REJECTED
    elif error_code == "publication_identity_conflict":
        outcome = HoverTelemetryOutcome.DUPLICATE_REJECTED
    elif retryable:
        outcome = HoverTelemetryOutcome.RETRYABLE_FAILURE
    else:
        outcome = HoverTelemetryOutcome.PERMANENT_FAILURE
    emit_hover_telemetry_on_commit(
        HoverTelemetryEvent.PUBLICATION_SYNC,
        outcome,
        dimensions={
            "realm_id": realm_id,
            "attachment_id": attachment_id,
            "lag_bucket": lag_bucket(None),
            "publication_count_bucket": count_bucket(publication_count),
            "created_count_bucket": count_bucket(0),
            "replayed_count_bucket": count_bucket(0),
            "retryable": retryable,
        },
    )


def _create_generated_item(
    *,
    attachment: SpaceAttachment,
    assistant: UserProfile,
    publication: ClawerPublication,
    envelope_hash: str,
) -> GeneratedItem:
    assert attachment.space.stream is not None
    topic, content = render_publication(publication)
    message_id = internal_send_stream_message(
        sender=assistant,
        stream=attachment.space.stream,
        topic_name=topic,
        content=content,
        acting_user=assistant,
    )
    if message_id is None:
        raise PublicationSyncError("native_message_not_created", retryable=True)
    message = Message.objects.filter(
        id=message_id,
        realm=attachment.realm,
        recipient=attachment.space.stream.recipient,
        sender=assistant,
    ).first()
    if message is None:
        raise PublicationSyncError("native_message_not_created", retryable=True)
    generated_item = GeneratedItem.objects.create(
        realm=attachment.realm,
        message=message,
        attachment=attachment,
        publication_id=publication.publication_id,
        idempotency_key=publication.idempotency_key,
        publication_envelope_hash=envelope_hash,
        business_identity=publication.business_identity,
        output_type=publication.contract,
        module_key=publication.producer_key,
        module_name=publication.producer_name,
        module_version=publication.producing_version,
        source_summary=f"From {attachment.source.display_name}",
        payload=publication.payload.model_dump(mode="json"),
        reviewed_payload=publication.payload.model_dump(mode="json"),
        importance=publication.importance,
        run_reference=publication.run_reference,
        covered_start_at=publication.covered_period.start,
        covered_end_at=publication.covered_period.end,
        occurred_at=publication.occurred_at,
        generated_at=publication.generated_at,
        published_at=publication.published_at,
        lineage_key=publication.lineage_key,
        parent_publication_id=publication.parent_publication_id,
        material_change=publication.material_change,
    )
    evidence_links = [
        EvidenceLink(
            generated_item=generated_item,
            realm=attachment.realm,
            source=attachment.source,
            evidence_ref=evidence_ref,
            position=position,
            provider_key=attachment.source.provider_key,
            provider_name=attachment.source.account.provider_name,
            display_name=attachment.source.display_name,
        )
        for position, evidence_ref in enumerate(publication.evidence_refs)
    ]
    EvidenceLink.objects.bulk_create(evidence_links)
    materialize_disputed_details(
        generated_item=generated_item,
        details=publication.disputed_details,
        evidence_by_ref={link.evidence_ref: link for link in evidence_links},
    )
    if isinstance(publication.payload, SuggestedActionPayload):
        action = create_suggested_action_for_generated_item(generated_item, publication.payload)
        send_suggested_action_projection_event(action)
    return generated_item


def _matches_legacy_publication(
    existing: GeneratedItem,
    attachment: SpaceAttachment,
    publication: ClawerPublication,
) -> bool:
    """Verify every persisted envelope field before adopting a legacy replay hash."""
    evidence_links = list(existing.evidence_links.all())
    return (
        existing.attachment_id == attachment.id
        and attachment.source.external_ref == publication.source_ref
        and existing.business_identity == publication.business_identity
        and existing.output_type == publication.contract
        and existing.module_key == publication.producer_key
        and existing.module_name == publication.producer_name
        and existing.module_version == publication.producing_version
        and existing.payload == publication.payload.model_dump(mode="json")
        and existing.importance == publication.importance
        and existing.run_reference == publication.run_reference
        and existing.covered_start_at == publication.covered_period.start
        and existing.covered_end_at == publication.covered_period.end
        and existing.occurred_at == publication.occurred_at
        and existing.generated_at == publication.generated_at
        and existing.published_at == publication.published_at
        and existing.lineage_key == publication.lineage_key
        and existing.parent_publication_id == publication.parent_publication_id
        and existing.material_change == publication.material_change
        and [link.evidence_ref for link in evidence_links] == publication.evidence_refs
        and all(link.source_id == attachment.source_id for link in evidence_links)
        and not publication.disputed_details
    )


def sync_space_attachment(
    *,
    attachment_id: int,
    assistant: UserProfile,
    clawer_sync: ClawerSync,
    limit: int = MAX_PUBLICATION_SYNC_BATCH,
) -> PublicationSyncResult:
    """Fetch and atomically accept one bounded publication page."""
    if limit < 1 or limit > MAX_PUBLICATION_SYNC_BATCH:
        raise PublicationSyncError("invalid_publication_batch_limit", retryable=False)
    attachment, lease_token, stored_cursor = _claim_attachment(
        attachment_id=attachment_id,
        assistant=assistant,
    )
    requested_cursor = stored_cursor or None
    try:
        page = clawer_sync.sync_publications(
            realm_uuid=attachment.realm.uuid,
            account_external_id=attachment.source.account.external_account_id,
            source_ref=attachment.source.external_ref,
            cursor=requested_cursor,
            limit=limit,
            start_at=attachment.history_start_at.astimezone(datetime_timezone.utc).isoformat(),
        )
    except ClawerSyncError as exc:
        _record_failure(
            attachment_id=attachment_id,
            lease_token=lease_token,
            error_code=exc.error_code,
            retryable=exc.retryable,
            requested_cursor=stored_cursor,
        )
        raise PublicationSyncError(exc.error_code, retryable=exc.retryable)
    except ValueError:
        _record_failure(
            attachment_id=attachment_id,
            lease_token=lease_token,
            error_code="invalid_upstream_contract",
            retryable=False,
            requested_cursor=stored_cursor,
        )
        raise PublicationSyncError("invalid_upstream_contract", retryable=False)

    created = 0
    replayed = 0
    try:
        with transaction.atomic(durable=True):
            locked = (
                SpaceAttachment.objects.select_for_update(no_key=True, of=("self",))
                .select_related("realm", "space", "space__stream", "source", "source__account")
                .get(id=attachment_id)
            )
            _validate_syncable_attachment(locked, assistant)
            if locked.publication_sync_lease_token != lease_token:
                raise PublicationSyncError("publication_sync_lease_lost", retryable=True)
            if locked.publication_cursor != stored_cursor:
                raise PublicationSyncError("publication_cursor_conflict", retryable=True)
            if (
                len(page.publications) > limit
                or any(
                    publication.source_ref != locked.source.external_ref
                    for publication in page.publications
                )
                or (page.has_more and not page.publications)
                or (page.has_more and page.next_cursor == stored_cursor)
            ):
                raise PublicationSyncError("invalid_upstream_contract", retryable=False)
            assert locked.space.stream is not None
            UserGroupMembership.objects.get_or_create(
                user_group_id=locked.space.stream.can_send_message_group_id,
                user_profile=assistant,
            )
            bulk_add_subscriptions(
                locked.realm,
                [locked.space.stream],
                [assistant],
                acting_user=None,
            )
            for publication in page.publications:
                envelope_hash = publication_envelope_hash(publication)
                existing = (
                    GeneratedItem.objects.filter(attachment=locked)
                    .filter(
                        Q(publication_id=publication.publication_id)
                        | Q(idempotency_key=publication.idempotency_key)
                    )
                    .prefetch_related("evidence_links")
                    .first()
                )
                if existing is not None:
                    if (
                        existing.publication_id != publication.publication_id
                        or existing.idempotency_key != publication.idempotency_key
                    ):
                        raise PublicationSyncError("publication_identity_conflict", retryable=False)
                    if not existing.publication_envelope_hash:
                        if not _matches_legacy_publication(existing, locked, publication):
                            raise PublicationSyncError(
                                "publication_identity_conflict", retryable=False
                            )
                        existing.publication_envelope_hash = envelope_hash
                        existing.save(update_fields=["publication_envelope_hash"])
                    elif existing.publication_envelope_hash != envelope_hash:
                        raise PublicationSyncError("publication_identity_conflict", retryable=False)
                    replayed += 1
                    continue
                _create_generated_item(
                    attachment=locked,
                    assistant=assistant,
                    publication=publication,
                    envelope_hash=envelope_hash,
                )
                created += 1
            locked.publication_cursor = page.next_cursor
            locked.last_publication_sync_at = timezone.now()
            locked.last_publication_sync_error = ""
            locked.publication_sync_failures = 0
            locked.publication_sync_state = SpaceAttachment.PublicationSyncState.IDLE
            locked.publication_sync_lease_token = None
            locked.publication_sync_lease_expires_at = None
            locked.next_publication_sync_at = timezone.now() + (
                timedelta(0) if page.has_more else PUBLICATION_SYNC_POLL_INTERVAL
            )
            locked.save(
                update_fields=[
                    "publication_cursor",
                    "last_publication_sync_at",
                    "last_publication_sync_error",
                    "publication_sync_failures",
                    "publication_sync_state",
                    "publication_sync_lease_token",
                    "publication_sync_lease_expires_at",
                    "next_publication_sync_at",
                    "date_updated",
                ]
            )
            PublicationSyncAttempt.objects.create(
                realm=locked.realm,
                attachment=locked,
                outcome=PublicationSyncAttempt.Outcome.SUCCESS,
                publication_count=len(page.publications),
                created_count=created,
                replayed_count=replayed,
                requested_cursor_hash=_opaque_hash(stored_cursor),
                returned_cursor_hash=_opaque_hash(page.next_cursor),
            )
    except PublicationSyncError as exc:
        _record_failure(
            attachment_id=attachment_id,
            lease_token=lease_token,
            error_code=exc.error_code,
            retryable=exc.retryable,
            requested_cursor=stored_cursor,
            returned_cursor=page.next_cursor,
            publication_count=len(page.publications),
        )
        raise
    except ReviewRequestMaterializationError as exc:
        error = PublicationSyncError(exc.error_code, retryable=exc.retryable)
        _record_failure(
            attachment_id=attachment_id,
            lease_token=lease_token,
            error_code=error.error_code,
            retryable=error.retryable,
            requested_cursor=stored_cursor,
            returned_cursor=page.next_cursor,
            publication_count=len(page.publications),
        )
        raise error
    except IntegrityError:
        error = PublicationSyncError("publication_identity_conflict", retryable=False)
        _record_failure(
            attachment_id=attachment_id,
            lease_token=lease_token,
            error_code=error.error_code,
            retryable=error.retryable,
            requested_cursor=stored_cursor,
            returned_cursor=page.next_cursor,
            publication_count=len(page.publications),
        )
        raise error

    published_at = max(
        (publication.published_at for publication in page.publications),
        default=None,
    )
    lag_seconds = (
        (timezone.now() - published_at).total_seconds() if published_at is not None else None
    )
    dimensions = {
        "realm_id": attachment.realm_id,
        "attachment_id": attachment_id,
        "lag_bucket": lag_bucket(lag_seconds),
        "publication_count_bucket": count_bucket(len(page.publications)),
        "created_count_bucket": count_bucket(created),
        "replayed_count_bucket": count_bucket(replayed),
        "retryable": False,
    }
    emit_hover_telemetry_on_commit(
        HoverTelemetryEvent.PUBLICATION_SYNC,
        HoverTelemetryOutcome.SUCCESS,
        dimensions=dimensions,
    )
    if replayed:
        emit_hover_telemetry_on_commit(
            HoverTelemetryEvent.PUBLICATION_SYNC,
            HoverTelemetryOutcome.DUPLICATE_REPLAYED,
            dimensions=dimensions,
        )

    return PublicationSyncResult(
        attachment_id=attachment_id,
        created=created,
        replayed=replayed,
        next_cursor=page.next_cursor,
        has_more=page.has_more,
    )
