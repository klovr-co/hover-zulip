from django.http import HttpRequest, HttpResponse

from hover.clawer_sync import get_clawer_sync
from hover.personal_editions import get_personal_editions_for_user, sync_personal_editions
from hover.telemetry import (
    HoverTelemetryBucket,
    HoverTelemetryEvent,
    HoverTelemetryOutcome,
    count_bucket,
    emit_hover_telemetry,
)
from zerver.decorator import require_non_guest_user
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import typed_endpoint_without_parameters
from zerver.models.users import UserProfile


@require_non_guest_user
@typed_endpoint_without_parameters
def personal_editions(request: HttpRequest, user_profile: UserProfile) -> HttpResponse:
    sync_status, _errors = sync_personal_editions(
        user_profile=user_profile,
        clawer_sync=get_clawer_sync(),
    )
    editions = get_personal_editions_for_user(user_profile=user_profile)
    available_editions = [kind for kind, edition in editions.items() if edition is not None]
    edition_count = len(available_editions)
    edition_kinds: list[str | None] = []
    edition_kinds.extend(available_editions)
    if not edition_kinds:
        edition_kinds.append(None)
    for edition_kind in edition_kinds:
        if edition_kind == "morning":
            edition_bucket = HoverTelemetryBucket.MORNING
        elif edition_kind == "end_of_day":
            edition_bucket = HoverTelemetryBucket.END_OF_DAY
        else:
            assert edition_kind is None
            edition_bucket = HoverTelemetryBucket.UNKNOWN
        emit_hover_telemetry(
            HoverTelemetryEvent.EDITION,
            {
                "current": HoverTelemetryOutcome.CURRENT,
                "degraded": HoverTelemetryOutcome.DEGRADED,
                "empty": HoverTelemetryOutcome.EMPTY,
            }[sync_status],
            dimensions={
                "realm_id": user_profile.realm_id,
                "edition_kind": edition_bucket,
                "edition_count_bucket": count_bucket(edition_count),
                "failure_count_bucket": count_bucket(len(_errors)),
                "cache_used": sync_status == "degraded" and edition_count > 0,
            },
        )
    response = json_success(
        request,
        data={
            "sync_status": sync_status,
            "editions": editions,
        },
    )
    response["Cache-Control"] = "no-store"
    return response
