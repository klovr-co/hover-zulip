"""Incremental, replay-safe materialization of Clawer publications into Hover."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timezone as datetime_timezone

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from hover.clawer_sync import ClawerSync, ClawerSyncError
from hover.models import EvidenceLink, GeneratedItem, SpaceAttachment
from hover.publication_contracts import (
    AnalysisPayload,
    ClawerPublication,
    DecisionPayload,
    DigestPayload,
    FeedUpdatePayload,
    ProgressUpdatePayload,
    SuggestedActionPayload,
)
from zerver.actions.message_send import internal_send_stream_message
from zerver.models.constants import MAX_TOPIC_NAME_LENGTH
from zerver.models.messages import Message
from zerver.models.users import UserProfile


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
            "**Status:** Awaiting confirmation",
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
    topic = publication.producer_name[:MAX_TOPIC_NAME_LENGTH]
    return topic, content


def _record_failure(attachment_id: int, error_code: str) -> None:
    with transaction.atomic():
        attachment = SpaceAttachment.objects.select_for_update().get(id=attachment_id)
        attachment.last_publication_sync_error = error_code[:64]
        attachment.publication_sync_failures += 1
        attachment.save(
            update_fields=[
                "last_publication_sync_error",
                "publication_sync_failures",
                "date_updated",
            ]
        )


def _create_generated_item(
    *,
    attachment: SpaceAttachment,
    assistant: UserProfile,
    publication: ClawerPublication,
) -> GeneratedItem:
    assert attachment.space.stream is not None
    topic, content = render_publication(publication)
    message_id = internal_send_stream_message(
        assistant,
        attachment.space.stream,
        topic,
        content,
        acting_user=assistant,
    )
    if message_id is None:
        raise PublicationSyncError("native_message_not_created", retryable=True)
    message = Message.objects.get(id=message_id)
    generated_item = GeneratedItem.objects.create(
        realm=attachment.realm,
        message=message,
        attachment=attachment,
        publication_id=publication.publication_id,
        idempotency_key=publication.idempotency_key,
        business_identity=publication.business_identity,
        output_type=publication.contract,
        module_key=publication.producer_key,
        module_name=publication.producer_name,
        module_version=publication.producing_version,
        source_summary=f"From {attachment.source.display_name}",
        payload=publication.payload.model_dump(mode="json"),
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
    EvidenceLink.objects.bulk_create(
        [
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
    )
    return generated_item


def sync_space_attachment(
    *,
    attachment_id: int,
    assistant: UserProfile,
    clawer_sync: ClawerSync,
    limit: int = 50,
) -> PublicationSyncResult:
    """Fetch and atomically accept one bounded publication page."""
    attachment = SpaceAttachment.objects.select_related(
        "realm", "space", "space__stream", "source", "source__account"
    ).get(id=attachment_id)
    if (
        attachment.state != SpaceAttachment.State.ACTIVE
        or attachment.space.state != attachment.space.State.LAUNCHED
        or attachment.space.stream is None
    ):
        raise PublicationSyncError("attachment_not_syncable", retryable=False)
    if assistant.realm_id != attachment.realm_id or not assistant.is_bot:
        raise PublicationSyncError("invalid_hover_assistant", retryable=False)

    requested_cursor = attachment.publication_cursor or None
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
        _record_failure(attachment_id, exc.error_code)
        raise PublicationSyncError(exc.error_code, retryable=exc.retryable)
    except ValueError:
        _record_failure(attachment_id, "invalid_upstream_contract")
        raise PublicationSyncError("invalid_upstream_contract", retryable=False)

    created = 0
    replayed = 0
    try:
        with transaction.atomic():
            locked = (
                SpaceAttachment.objects.select_for_update(of=("self",))
                .select_related("realm", "space", "space__stream", "source", "source__account")
                .get(id=attachment_id)
            )
            if locked.publication_cursor != (requested_cursor or ""):
                raise PublicationSyncError("publication_cursor_conflict", retryable=True)
            for publication in page.publications:
                existing = GeneratedItem.objects.filter(
                    publication_id=publication.publication_id
                ).first()
                if existing is not None:
                    if existing.attachment_id != locked.id:
                        raise PublicationSyncError("publication_identity_conflict", retryable=False)
                    replayed += 1
                    continue
                _create_generated_item(
                    attachment=locked,
                    assistant=assistant,
                    publication=publication,
                )
                created += 1
            locked.publication_cursor = page.next_cursor
            locked.last_publication_sync_at = timezone.now()
            locked.last_publication_sync_error = ""
            locked.publication_sync_failures = 0
            locked.save(
                update_fields=[
                    "publication_cursor",
                    "last_publication_sync_at",
                    "last_publication_sync_error",
                    "publication_sync_failures",
                    "date_updated",
                ]
            )
    except PublicationSyncError as exc:
        _record_failure(attachment_id, exc.error_code)
        raise

    return PublicationSyncResult(
        attachment_id=attachment_id,
        created=created,
        replayed=replayed,
        next_cursor=page.next_cursor,
        has_more=page.has_more,
    )
