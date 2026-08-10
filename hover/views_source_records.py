import logging
import time
from typing import Annotated
from uuid import uuid4

from django.http import HttpRequest, HttpResponse
from pydantic import Field, Json, StringConstraints

from hover.clawer_sync import get_clawer_sync
from hover.lib_source_records import browse_attachment_records
from zerver.lib.exceptions import JsonableError
from zerver.lib.response import json_response_from_error, json_success
from zerver.lib.typed_endpoint import PathOnly, typed_endpoint
from zerver.models.users import UserProfile

logger = logging.getLogger("zulip.hover.source_records")


def _duration_bucket(duration_ms: float) -> str:
    if duration_ms < 100:
        return "under_100ms"
    if duration_ms < 500:
        return "under_500ms"
    if duration_ms < 2_000:
        return "under_2s"
    return "over_2s"


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
    telemetry_status = "internal_error"
    result_count = 0
    request_id = str(uuid4())
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
        telemetry_status = "success"
        result_count = len(data["records"])
        response = json_success(request, data=data)
    except JsonableError as error:
        telemetry_status = getattr(error, "error_code", "denied")
        response = json_response_from_error(error)
    finally:
        logger.info(
            "Hover Source records operation=source_records status=%s duration_bucket=%s "
            "realm_id=%s attachment_id=%s result_count=%s request_id=%s",
            telemetry_status,
            _duration_bucket((time.monotonic() - started_at) * 1_000),
            user_profile.realm_id,
            attachment_id,
            result_count,
            request_id,
        )
    response["Cache-Control"] = "no-store"
    return response
