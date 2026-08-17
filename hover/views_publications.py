from typing import NoReturn

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
            GeneratedItem.objects.select_related("attachment__source__account", "message")
            .prefetch_related("evidence_links")
            .get(
                id=generated_item_id,
                realm=user_profile.realm,
                attachment__space=space,
                message__recipient=space.stream.recipient,
            )
        )
    except GeneratedItem.DoesNotExist:
        raise JsonableError(_("Invalid generated item ID"))

    assert generated_item.attachment is not None
    source = generated_item.attachment.source
    access_message(user_profile, generated_item.message_id, is_modifying_message=False)
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
