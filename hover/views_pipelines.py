from datetime import time
from typing import Annotated

from django.http import HttpRequest, HttpResponse
from pydantic import Json, StringConstraints

from hover.actions_pipelines import do_create_pipeline
from hover.actions_pipeline_library import user_can_create_pipelines
from hover.lib_pipelines import pipeline_data, visible_pipelines
from zerver.decorator import require_non_guest_user
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import typed_endpoint, typed_endpoint_without_parameters
from zerver.models.users import UserProfile

PipelineText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


@require_non_guest_user
@typed_endpoint_without_parameters
def list_pipelines(request: HttpRequest, user_profile: UserProfile) -> HttpResponse:
    pipelines = visible_pipelines(user_profile).order_by("name", "id")
    return json_success(
        request,
        data={
            "pipelines": [pipeline_data(item) for item in pipelines],
            "can_create": user_can_create_pipelines(user_profile),
        },
    )


@require_non_guest_user
@typed_endpoint
def create_pipeline(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    connector_id: Json[int],
    name: Json[PipelineText],
    instruction: Json[PipelineText],
    cadence: Json[str],
    weekday: Json[int | None] = None,
    local_time: Json[time],
    timezone: Json[str],
    output_destination_name: Json[str],
    output_topic: Json[str],
) -> HttpResponse:
    pipeline = do_create_pipeline(
        acting_user=user_profile,
        connector_id=connector_id,
        name=name,
        instruction=instruction,
        cadence=cadence,
        weekday=weekday,
        local_time=local_time,
        timezone=timezone,
        output_destination_name=output_destination_name,
        output_topic=output_topic,
    )
    return json_success(request, data={"pipeline": pipeline_data(pipeline)})
