import hashlib
from typing import NoReturn

from django.db.models import Q
from django.http import HttpRequest, HttpResponse
from django.utils.translation import gettext as _

from hover.clawer_sync import ClawerSyncError, get_clawer_sync
from hover.lib_spaces import access_space_by_id
from hover.models import ConnectedAccount, DisputedDetail, GeneratedItem, Source
from hover.publication_contracts import ResolvedEvidence
from hover.telemetry import (
    HoverTelemetryEvent,
    HoverTelemetryOutcome,
    count_bucket,
    emit_hover_telemetry_on_commit,
)
from zerver.decorator import require_non_guest_user
from zerver.lib.exceptions import JsonableError
from zerver.lib.message import access_message
from zerver.lib.response import json_success
from zerver.lib.streams import access_stream_by_id
from zerver.lib.typed_endpoint import PathOnly, typed_endpoint
from zerver.models.users import UserProfile


class EvidenceResolutionError(JsonableError):
    data_fields = ["error_code", "retryable"]
    http_status_code = 404

    def __init__(self) -> None:
        super().__init__(_("The exact source evidence is no longer available."))
        self.error_code = "evidence_not_resolvable"
        self.retryable = False


def _evidence_unavailable(*, realm_id: int, space_id: int, reference_count: int) -> NoReturn:
    emit_hover_telemetry_on_commit(
        HoverTelemetryEvent.EVIDENCE_RESOLUTION,
        HoverTelemetryOutcome.PERMANENT_FAILURE,
        dimensions={
            "realm_id": realm_id,
            "space_id": space_id,
            "reference_count_bucket": count_bucket(reference_count),
            "retryable": False,
        },
    )
    raise EvidenceResolutionError


def _resolve_evidence(
    *, user_profile: UserProfile, space_id: int, source: Source, refs: list[str]
) -> list[ResolvedEvidence]:
    try:
        evidence = get_clawer_sync().resolve_evidence(
            realm_uuid=user_profile.realm.uuid,
            account_external_id=source.account.external_account_id,
            source_ref=source.external_ref,
            refs=refs,
        )
    except ClawerSyncError as error:
        emit_hover_telemetry_on_commit(
            HoverTelemetryEvent.EVIDENCE_RESOLUTION,
            (
                HoverTelemetryOutcome.RETRYABLE_FAILURE
                if error.retryable
                else HoverTelemetryOutcome.PERMANENT_FAILURE
            ),
            dimensions={
                "realm_id": user_profile.realm_id,
                "space_id": space_id,
                "reference_count_bucket": count_bucket(len(refs)),
                "retryable": error.retryable,
            },
        )
        raise
    emit_hover_telemetry_on_commit(
        HoverTelemetryEvent.EVIDENCE_RESOLUTION,
        HoverTelemetryOutcome.SUCCESS,
        dimensions={
            "realm_id": user_profile.realm_id,
            "space_id": space_id,
            "reference_count_bucket": count_bucket(len(refs)),
            "retryable": False,
        },
    )
    return evidence


def _resolve_summary_evidence(
    *, user_profile: UserProfile, generated_item: GeneratedItem
) -> dict[str, object]:
    snapshots = list(generated_item.input_snapshots.all())
    snapshot_by_topic = {
        (snapshot.stream_id, snapshot.topic_name.casefold()): snapshot for snapshot in snapshots
    }

    # Strict history policy: access to an edition is withdrawn if any of the
    # exact inputs used for that edition is no longer available to the reader.
    for snapshot in snapshots:
        access_stream_by_id(user_profile, snapshot.stream_id)

    messages_by_snapshot_id: dict[int, list[dict[str, object]]] = {
        snapshot.id: [] for snapshot in snapshots
    }
    execution = getattr(generated_item, "summary_execution", None)
    execution_messages = (
        {snapshot.message_id: snapshot for snapshot in execution.message_snapshots.all()}
        if execution is not None
        else {}
    )
    forbidden_count = 0
    for link in generated_item.evidence_links.all():
        citation = link.citation_message
        if citation is None:
            forbidden_count += 1
            continue
        matched_snapshot = snapshot_by_topic.get(
            (citation.recipient.type_id, citation.topic_name().casefold())
        )
        if matched_snapshot is None:
            # Never reveal the identity or position of a rogue citation.
            forbidden_count += 1
            continue
        try:
            access_message(user_profile, citation.id, is_modifying_message=False)
        except JsonableError:
            forbidden_count += 1
            continue
        frozen = execution_messages.get(citation.id)
        edited_since_generation = (
            frozen is not None
            and frozen.content_digest != hashlib.sha256(citation.content.encode()).hexdigest()
        )
        messages_by_snapshot_id[matched_snapshot.id].append(
            {
                "message_id": citation.id,
                "sender_name": (
                    frozen.sender_label if frozen is not None else citation.sender.full_name
                ),
                "timestamp": int(
                    (frozen.sent_at if frozen is not None else citation.date_sent).timestamp()
                ),
                "rendered_content": (
                    frozen.frozen_rendered_content
                    if frozen is not None
                    else citation.rendered_content or ""
                ),
                "edited_since_generation": edited_since_generation,
            }
        )

    return {
        "groups": [
            {
                "topic": {
                    "stream_id": snapshot.stream_id,
                    "topic_name": snapshot.topic_name,
                    "kind": snapshot.kind,
                    **(
                        {"provider_name": snapshot.provider_name}
                        if snapshot.kind == "source" and snapshot.provider_name
                        else {}
                    ),
                },
                "messages": messages_by_snapshot_id[snapshot.id],
            }
            for snapshot in snapshots
        ],
        "forbidden_count": forbidden_count,
    }


@require_non_guest_user
@typed_endpoint
def resolve_generated_item_evidence(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    space_id: PathOnly[int],
    generated_item_id: PathOnly[int],
) -> HttpResponse:
    """Resolve server-owned evidence refs without accepting refs from the browser."""
    space = access_space_by_id(user_profile, space_id)
    if space.state != space.State.LAUNCHED or space.stream is None:
        raise JsonableError(_("Invalid generated item ID"))
    try:
        generated_item = (
            GeneratedItem.objects.select_related(
                "attachment__source__account",
                "installation__space__stream",
                "message",
            )
            .prefetch_related(
                "input_snapshots",
                "evidence_links__citation_message__sender",
                "summary_execution__message_snapshots",
            )
            .get(
                Q(attachment__space=space) | Q(installation__space=space),
                id=generated_item_id,
                realm=user_profile.realm,
            )
        )
    except GeneratedItem.DoesNotExist:
        raise JsonableError(_("Invalid generated item ID"))

    access_message(user_profile, generated_item.message_id, is_modifying_message=False)
    if generated_item.installation_id is not None:
        assert generated_item.installation is not None
        summary_stream = generated_item.installation.summary_stream
        if summary_stream is None or generated_item.message.recipient != summary_stream.recipient:
            raise JsonableError(_("Invalid generated item ID"))
        return json_success(
            request,
            data=_resolve_summary_evidence(
                user_profile=user_profile,
                generated_item=generated_item,
            ),
        )

    assert generated_item.attachment is not None
    if generated_item.message.recipient != space.stream.recipient:
        raise JsonableError(_("Invalid generated item ID"))
    source = generated_item.attachment.source
    if source.account.approval_state != ConnectedAccount.ApprovalState.APPROVED:
        _evidence_unavailable(
            realm_id=user_profile.realm_id,
            space_id=space_id,
            reference_count=0,
        )
    links = list(generated_item.evidence_links.all())
    evidence_refs = [
        link.evidence_ref for link in links if link.evidence_ref and link.source_id == source.id
    ]
    if not links or len(evidence_refs) != len(links):
        _evidence_unavailable(
            realm_id=user_profile.realm_id,
            space_id=space_id,
            reference_count=len(evidence_refs),
        )
    evidence = _resolve_evidence(
        user_profile=user_profile,
        space_id=space_id,
        source=source,
        refs=evidence_refs,
    )
    return json_success(
        request,
        data={"evidence": [item.model_dump(mode="json") for item in evidence]},
    )


@require_non_guest_user
@typed_endpoint
def resolve_disputed_detail_evidence(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    space_id: PathOnly[int],
    generated_item_id: PathOnly[int],
    disputed_detail_id: PathOnly[int],
) -> HttpResponse:
    """Resolve only the ordered, server-owned evidence subset for one dispute."""
    space = access_space_by_id(user_profile, space_id)
    if space.state != space.State.LAUNCHED or space.stream is None:
        raise JsonableError(_("Invalid disputed detail ID"))
    try:
        detail = (
            DisputedDetail.objects.select_related(
                "generated_item__attachment__source__account",
                "generated_item__message",
            )
            .prefetch_related("conflicting_evidence__evidence_link")
            .get(
                id=disputed_detail_id,
                realm=user_profile.realm,
                generated_item_id=generated_item_id,
                generated_item__attachment__space=space,
                generated_item__message__recipient=space.stream.recipient,
            )
        )
    except DisputedDetail.DoesNotExist:
        raise JsonableError(_("Invalid disputed detail ID"))

    generated_item = detail.generated_item
    attachment = generated_item.attachment
    assert attachment is not None
    source = attachment.source
    access_message(user_profile, generated_item.message_id, is_modifying_message=False)
    if source.account.approval_state != ConnectedAccount.ApprovalState.APPROVED:
        _evidence_unavailable(
            realm_id=user_profile.realm_id,
            space_id=space_id,
            reference_count=0,
        )
    conflict_links = list(detail.conflicting_evidence.all())
    evidence_refs = [
        conflict.evidence_link.evidence_ref
        for conflict in conflict_links
        if conflict.evidence_link.evidence_ref
        and conflict.evidence_link.source_id == source.id
        and conflict.evidence_link.generated_item_id == generated_item.id
    ]
    if len(evidence_refs) < 2 or len(evidence_refs) != len(conflict_links):
        _evidence_unavailable(
            realm_id=user_profile.realm_id,
            space_id=space_id,
            reference_count=len(evidence_refs),
        )
    evidence = _resolve_evidence(
        user_profile=user_profile,
        space_id=space_id,
        source=source,
        refs=evidence_refs,
    )
    return json_success(
        request,
        data={"evidence": [item.model_dump(mode="json") for item in evidence]},
    )
