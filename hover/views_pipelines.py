from datetime import time
from typing import Annotated

from django.http import HttpRequest, HttpResponse
from django.utils.translation import gettext as _
from pydantic import Json, StringConstraints

from hover.actions_pipeline_library import user_can_create_pipelines
from hover.actions_pipelines import (
    access_pipeline_for_update,
    do_create_pipeline,
    do_update_pipeline,
)
from hover.lib_pipelines import pipeline_data, topic_inputs_for_user, visible_pipelines
from zerver.decorator import require_non_guest_user
from zerver.lib.exceptions import JsonableError
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import PathOnly, typed_endpoint, typed_endpoint_without_parameters
from zerver.models.users import UserProfile

PipelineText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


@require_non_guest_user
@typed_endpoint_without_parameters
def list_pipelines(request: HttpRequest, user_profile: UserProfile) -> HttpResponse:
    pipelines = visible_pipelines(user_profile).order_by("name", "id")
    return json_success(
        request,
        data={
            "pipelines": [pipeline_data(item, user_profile) for item in pipelines],
            "topics": topic_inputs_for_user(user_profile),
            "can_create": user_can_create_pipelines(user_profile),
        },
    )


@require_non_guest_user
@typed_endpoint
def create_pipeline(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    input_destination_name: Json[str],
    input_topic: Json[str],
    name: Json[PipelineText],
    instruction: Json[PipelineText],
    cadence: Json[str],
    weekday: Json[int | None] = None,
    local_time: Json[time],
    timezone: Json[str] | None = None,
    output_destination_name: Json[str],
    output_topic: Json[str],
    lifecycle_state: Json[str] = "active",
) -> HttpResponse:
    pipeline = do_create_pipeline(
        acting_user=user_profile,
        input_destination_name=input_destination_name,
        input_topic=input_topic,
        name=name,
        instruction=instruction,
        cadence=cadence,
        weekday=weekday,
        local_time=local_time,
        timezone=timezone,
        output_destination_name=output_destination_name,
        output_topic=output_topic,
        lifecycle_state=lifecycle_state,
    )
    return json_success(request, data={"pipeline": pipeline_data(pipeline, user_profile)})


@require_non_guest_user
@typed_endpoint
def update_pipeline(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    pipeline_id: PathOnly[int],
    input_destination_name: Json[str] | None = None,
    input_topic: Json[str] | None = None,
    name: Json[PipelineText] | None = None,
    instruction: Json[PipelineText] | None = None,
    cadence: Json[str] | None = None,
    weekday: Json[int | None] = None,
    local_time: Json[time] | None = None,
    timezone: Json[str] | None = None,
    output_destination_name: Json[str] | None = None,
    output_topic: Json[str] | None = None,
    lifecycle_state: Json[str] | None = None,
) -> HttpResponse:
    pipeline = access_pipeline_for_update(user_profile, pipeline_id)
    configuration_changed = any(
        value is not None
        for value in (
            input_destination_name,
            input_topic,
            name,
            instruction,
            cadence,
            weekday,
            local_time,
            timezone,
            output_destination_name,
            output_topic,
        )
    )
    if pipeline.input_destination is None and input_destination_name is None:
        raise JsonableError(_("Choose an input Space to repair this Pipeline."))
    effective_cadence = cadence or pipeline.cadence
    if weekday is not None:
        effective_weekday = weekday
    elif cadence is not None and effective_cadence != pipeline.Cadence.WEEKLY:
        effective_weekday = None
    else:
        effective_weekday = pipeline.weekday
    if input_destination_name is None:
        assert pipeline.input_destination is not None
        input_destination_name = pipeline.input_destination.name
    updated = do_update_pipeline(
        pipeline=pipeline,
        acting_user=user_profile,
        input_destination_name=input_destination_name,
        input_topic=input_topic or pipeline.input_topic,
        name=name or pipeline.name,
        instruction=instruction or pipeline.instruction,
        cadence=effective_cadence,
        weekday=effective_weekday,
        local_time=local_time or pipeline.local_time,
        timezone=timezone or pipeline.timezone,
        output_destination_name=output_destination_name or pipeline.output_destination.name,
        output_topic=output_topic or pipeline.output_topic,
        lifecycle_state=lifecycle_state,
        configuration_changed=configuration_changed,
    )
    projected = visible_pipelines(user_profile).get(id=updated.id)
    return json_success(request, data={"pipeline": pipeline_data(projected, user_profile)})
