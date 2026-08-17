import time
from typing import Annotated

from django.http import HttpRequest, HttpResponse
from pydantic import Field, Json, StringConstraints

from hover.clawer_sync import ClawerSyncError, get_clawer_sync
from hover.lib_source_records import browse_attachment_records
from hover.telemetry import (
    HoverTelemetryEvent,
    HoverTelemetryOutcome,
    count_bucket,
    duration_bucket,
    emit_hover_telemetry_on_commit,
)
from zerver.lib.exceptions import JsonableError
from zerver.lib.response import json_response_from_error, json_success
from zerver.lib.typed_endpoint import PathOnly, typed_endpoint
from zerver.models.users import UserProfile


@typed_endpoint
def browse_source_records(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    space_id: PathOnly[int],
    attachment_id: PathOnly[int],
    cursor: Json[Annotated[str, StringConstraints(max_length=20_000)] | None] = None,
    limit: Json[Annotated[int, Field(ge=1, le=50)]] = 30,
    query: Json[Annotated[str, StringConstraints(max_length=100)]] = "",
) -> HttpResponse:
    started_at = time.monotonic()
    telemetry_outcome = HoverTelemetryOutcome.PERMANENT_FAILURE
    result_count = 0
    try:
        data = browse_attachment_records(
            user_profile=user_profile,
            space_id=space_id,
            attachment_id=attachment_id,
            cursor=cursor,
            limit=limit,
            query=query,
            clawer_sync=get_clawer_sync(),
        )
        telemetry_outcome = HoverTelemetryOutcome.SUCCESS
        result_count = len(data["records"])
        response = json_success(request, data=data)
    except ClawerSyncError as error:
        telemetry_outcome = (
            HoverTelemetryOutcome.RETRYABLE_FAILURE
            if error.retryable
            else HoverTelemetryOutcome.PERMANENT_FAILURE
        )
        response = json_response_from_error(error)
    except JsonableError as error:
        telemetry_outcome = HoverTelemetryOutcome.DENIED
        response = json_response_from_error(error)
    finally:
        emit_hover_telemetry_on_commit(
            HoverTelemetryEvent.SOURCE_RECORDS,
            telemetry_outcome,
            dimensions={
                "realm_id": user_profile.realm_id,
                "attachment_id": attachment_id,
                "duration_bucket": duration_bucket((time.monotonic() - started_at) * 1_000),
                "result_count_bucket": count_bucket(result_count),
            },
        )
    response["Cache-Control"] = "no-store"
    return response
