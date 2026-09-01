from datetime import time
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils.translation import gettext as _

from hover.actions_pipeline_library import user_can_create_pipelines
from hover.models import Connector, Pipeline
from hover.telemetry import (
    HoverTelemetryEvent,
    HoverTelemetryOutcome,
    emit_hover_telemetry_on_commit,
)
from zerver.lib.exceptions import ErrorCode, InvalidJSONError, JsonableError
from zerver.lib.streams import access_stream_by_name, access_stream_for_send_message
from zerver.lib.topic import get_topic_history_for_stream
from zerver.models.users import UserProfile


class PipelineUpdatePermissionError(JsonableError):
    code = ErrorCode.PERMISSION_DENIED
    http_status_code = 403


def access_pipeline_for_update(acting_user: UserProfile, pipeline_id: int) -> Pipeline:
    try:
        pipeline = Pipeline.objects.select_related(
            "input_destination", "output_destination", "created_by"
        ).get(id=pipeline_id, realm=acting_user.realm)
    except Pipeline.DoesNotExist:
        raise JsonableError(_("Invalid Pipeline ID."))
    if not acting_user.is_realm_admin and pipeline.created_by_id != acting_user.id:
        raise PipelineUpdatePermissionError(
            _("You do not have permission to update this Pipeline.")
        )
    return pipeline


def _validate_schedule(
    *, cadence: str, weekday: int | None, local_time: time, timezone: str
) -> None:
    if cadence not in Pipeline.Cadence.values:
        raise JsonableError(_("Invalid Pipeline schedule."))
    if cadence == Pipeline.Cadence.WEEKLY:
        if weekday not in Pipeline.Weekday.values:
            raise JsonableError(_("Choose a weekday for a weekly Pipeline."))
    elif weekday is not None:
        raise JsonableError(_("A weekday is only valid for a weekly Pipeline."))
    if local_time.utcoffset() is not None or local_time.second != 0 or local_time.microsecond != 0:
        raise JsonableError(_("Pipeline schedules must use whole minutes."))
    try:
        ZoneInfo(timezone)
    except (ZoneInfoNotFoundError, ValueError):
        raise JsonableError(_("Invalid IANA timezone."))


def _validate_input_topic_access(
    *, acting_user: UserProfile, input_destination: Any, input_topic: str
) -> None:
    assert input_destination.recipient_id is not None
    history = get_topic_history_for_stream(
        user_profile=acting_user,
        recipient_id=input_destination.recipient_id,
        public_history=input_destination.is_history_public_to_subscribers(),
        allow_empty_topic_name=False,
    )
    if any(item["name"].casefold() == input_topic.casefold() for item in history):
        return
    if Connector.objects.filter(destination=input_destination, topic__iexact=input_topic).exists():
        return
    raise JsonableError(_("Choose an accessible input Topic."))


def _validate_execution_identity_access(
    *,
    pipeline: Pipeline,
    input_destination: Any,
    input_topic: str,
    output_destination: Any,
) -> None:
    execution_identity = pipeline.created_by
    if execution_identity is None or not execution_identity.is_active:
        raise JsonableError(_("The Pipeline creator must be active before activation."))
    # The update actor authorizes the mutation; the creator remains the durable
    # execution identity and must independently retain both read and send access.
    execution_input, _input_subscription = access_stream_by_name(
        execution_identity, input_destination.name
    )
    _validate_input_topic_access(
        acting_user=execution_identity,
        input_destination=execution_input,
        input_topic=input_topic,
    )
    access_stream_for_send_message(execution_identity, output_destination, None)


def _validate_create_lifecycle_state(lifecycle_state: str) -> None:
    if lifecycle_state not in {Pipeline.State.ACTIVE, Pipeline.State.DRAFT}:
        raise JsonableError(_("New Pipelines must be active or draft."))


def _transition_outcome(previous_state: str, lifecycle_state: str) -> HoverTelemetryOutcome:
    if previous_state == Pipeline.State.DRAFT:
        return HoverTelemetryOutcome.ACTIVATED
    if lifecycle_state == Pipeline.State.PAUSED:
        return HoverTelemetryOutcome.PAUSED
    return HoverTelemetryOutcome.RESUMED


def _validate_lifecycle_transition(previous_state: str, lifecycle_state: str) -> None:
    allowed = {
        (Pipeline.State.DRAFT, Pipeline.State.ACTIVE),
        (Pipeline.State.ACTIVE, Pipeline.State.PAUSED),
        (Pipeline.State.PAUSED, Pipeline.State.ACTIVE),
    }
    if previous_state == lifecycle_state:
        return
    if (previous_state, lifecycle_state) not in allowed:
        raise JsonableError(_("Invalid Pipeline lifecycle transition."))


def _emit_lifecycle_telemetry(pipeline: Pipeline, outcome: HoverTelemetryOutcome) -> None:
    emit_hover_telemetry_on_commit(
        HoverTelemetryEvent.PIPELINE_LIFECYCLE,
        outcome,
        dimensions={"realm_id": pipeline.realm_id, "pipeline_id": pipeline.id},
    )


@transaction.atomic(durable=True)
def do_create_pipeline(
    *,
    acting_user: UserProfile,
    input_destination_name: str,
    input_topic: str,
    name: str,
    instruction: str,
    cadence: str,
    weekday: int | None,
    local_time: time,
    timezone: str | None,
    output_destination_name: str,
    output_topic: str,
    lifecycle_state: str,
) -> Pipeline:
    if not user_can_create_pipelines(acting_user):
        raise JsonableError(_("You do not have permission to create Pipelines."))

    _validate_create_lifecycle_state(lifecycle_state)
    normalized_name = name.strip()
    normalized_instruction = instruction.strip()
    normalized_input_topic = input_topic.strip()
    normalized_output_topic = output_topic.strip()
    if not normalized_name or len(normalized_name) > Pipeline.MAX_NAME_LENGTH:
        raise JsonableError(_("Pipeline names must contain 1 to 80 characters."))
    if not normalized_instruction or len(normalized_instruction) > Pipeline.MAX_INSTRUCTION_LENGTH:
        raise JsonableError(_("Tell Hover what this Pipeline should summarize."))
    if not normalized_input_topic or len(normalized_input_topic) > Pipeline.MAX_TOPIC_LENGTH:
        raise JsonableError(_("Input topics must contain 1 to 60 characters."))
    if not normalized_output_topic or len(normalized_output_topic) > Pipeline.MAX_TOPIC_LENGTH:
        raise JsonableError(_("Output topics must contain 1 to 60 characters."))
    resolved_timezone = timezone or acting_user.timezone or "UTC"
    _validate_schedule(
        cadence=cadence, weekday=weekday, local_time=local_time, timezone=resolved_timezone
    )

    # access_stream_by_name(require_content_access=True) is the canonical read check.
    input_destination, _input_subscription = access_stream_by_name(
        acting_user, input_destination_name
    )
    _validate_input_topic_access(
        acting_user=acting_user,
        input_destination=input_destination,
        input_topic=normalized_input_topic,
    )
    output_destination, _output_subscription = access_stream_by_name(
        acting_user, output_destination_name
    )
    access_stream_for_send_message(acting_user, output_destination, None)

    pipeline = Pipeline(
        realm=acting_user.realm,
        input_destination=input_destination,
        input_topic=normalized_input_topic,
        name=normalized_name,
        instruction=normalized_instruction,
        cadence=cadence,
        weekday=weekday,
        local_time=local_time,
        timezone=resolved_timezone,
        output_destination=output_destination,
        output_topic=normalized_output_topic,
        state=lifecycle_state,
        created_by=acting_user,
    )
    try:
        pipeline.full_clean()
        pipeline.save()
    except ValidationError as exc:
        raise InvalidJSONError(str(exc))
    _emit_lifecycle_telemetry(
        pipeline,
        HoverTelemetryOutcome.DRAFT_SAVED
        if lifecycle_state == Pipeline.State.DRAFT
        else HoverTelemetryOutcome.ACTIVATED,
    )
    return pipeline


@transaction.atomic(durable=True)
def do_update_pipeline(
    *,
    pipeline: Pipeline,
    acting_user: UserProfile,
    input_destination_name: str,
    input_topic: str,
    name: str,
    instruction: str,
    cadence: str,
    weekday: int | None,
    local_time: time,
    timezone: str,
    output_destination_name: str,
    output_topic: str,
    lifecycle_state: str | None,
    configuration_changed: bool,
) -> Pipeline:
    pipeline = Pipeline.objects.select_for_update(no_key=False).get(id=pipeline.id)
    if pipeline.realm_id != acting_user.realm_id or (
        not acting_user.is_realm_admin and pipeline.created_by_id != acting_user.id
    ):
        raise PipelineUpdatePermissionError(
            _("You do not have permission to update this Pipeline.")
        )
    target_state = lifecycle_state or pipeline.state
    if target_state not in Pipeline.State.values:
        raise JsonableError(_("Invalid Pipeline lifecycle state."))
    _validate_lifecycle_transition(pipeline.state, target_state)
    normalized_name = name.strip()
    normalized_instruction = instruction.strip()
    normalized_input_topic = input_topic.strip()
    normalized_output_topic = output_topic.strip()
    if not normalized_name or len(normalized_name) > Pipeline.MAX_NAME_LENGTH:
        raise JsonableError(_("Pipeline names must contain 1 to 80 characters."))
    if not normalized_instruction or len(normalized_instruction) > Pipeline.MAX_INSTRUCTION_LENGTH:
        raise JsonableError(_("Tell Hover what this Pipeline should summarize."))
    if not normalized_input_topic or len(normalized_input_topic) > Pipeline.MAX_TOPIC_LENGTH:
        raise JsonableError(_("Input topics must contain 1 to 60 characters."))
    if not normalized_output_topic or len(normalized_output_topic) > Pipeline.MAX_TOPIC_LENGTH:
        raise JsonableError(_("Output topics must contain 1 to 60 characters."))
    _validate_schedule(cadence=cadence, weekday=weekday, local_time=local_time, timezone=timezone)
    if configuration_changed:
        input_destination, _input_subscription = access_stream_by_name(
            acting_user, input_destination_name
        )
        _validate_input_topic_access(
            acting_user=acting_user,
            input_destination=input_destination,
            input_topic=normalized_input_topic,
        )
        output_destination, _output_subscription = access_stream_by_name(
            acting_user, output_destination_name
        )
        access_stream_for_send_message(acting_user, output_destination, None)
    else:
        assert pipeline.input_destination is not None
        input_destination = pipeline.input_destination
        output_destination = pipeline.output_destination

    input_identity_changed = (
        pipeline.input_destination_id != input_destination.id
        or pipeline.input_topic.casefold() != normalized_input_topic.casefold()
    )
    pipeline.input_destination = input_destination
    pipeline.input_topic = normalized_input_topic
    pipeline.name = normalized_name
    pipeline.instruction = normalized_instruction
    pipeline.cadence = cadence
    pipeline.weekday = weekday
    pipeline.local_time = local_time
    pipeline.timezone = timezone
    pipeline.output_destination = output_destination
    pipeline.output_topic = normalized_output_topic
    if configuration_changed:
        pipeline.input_availability = Pipeline.InputAvailability.AVAILABLE
    if target_state == Pipeline.State.ACTIVE and (
        pipeline.input_availability != Pipeline.InputAvailability.AVAILABLE
        and not configuration_changed
    ):
        raise JsonableError(_("Repair the input Topic before activating this Pipeline."))
    if target_state == Pipeline.State.ACTIVE:
        _validate_execution_identity_access(
            pipeline=pipeline,
            input_destination=input_destination,
            input_topic=normalized_input_topic,
            output_destination=output_destination,
        )
    previous_state = pipeline.state
    pipeline.state = target_state
    if input_identity_changed:
        pipeline.input_cursor_message_id = None
    try:
        pipeline.full_clean()
        pipeline.save()
    except ValidationError as exc:
        raise InvalidJSONError(str(exc))
    if previous_state != target_state:
        _emit_lifecycle_telemetry(pipeline, _transition_outcome(previous_state, target_state))
    elif pipeline.state == Pipeline.State.DRAFT and configuration_changed:
        _emit_lifecycle_telemetry(pipeline, HoverTelemetryOutcome.DRAFT_SAVED)
    return pipeline
