from datetime import time
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils.translation import gettext as _

from hover.actions_connectors import access_connector
from hover.actions_pipeline_library import user_can_create_pipelines
from hover.models import Connector, Pipeline
from zerver.lib.exceptions import InvalidJSONError, JsonableError
from zerver.lib.streams import access_stream_by_name, access_stream_for_send_message
from zerver.models.users import UserProfile


@transaction.atomic(durable=True)
def do_create_pipeline(
    *,
    acting_user: UserProfile,
    connector_id: int,
    name: str,
    instruction: str,
    cadence: str,
    weekday: int | None,
    local_time: time,
    timezone: str,
    output_destination_name: str,
    output_topic: str,
) -> Pipeline:
    if not user_can_create_pipelines(acting_user):
        raise JsonableError(_("You do not have permission to create Pipelines."))
    connector = access_connector(acting_user, connector_id)
    if connector.state != Connector.State.ACTIVE or connector.destination_id is None:
        raise JsonableError(_("Choose an active connector for this Pipeline."))
    if Pipeline.objects.filter(connector=connector).exists():
        raise JsonableError(_("That data source already belongs to a Pipeline."))
    normalized_name = name.strip()
    normalized_instruction = instruction.strip()
    normalized_topic = output_topic.strip()
    if not normalized_name or len(normalized_name) > Pipeline.MAX_NAME_LENGTH:
        raise JsonableError(_("Pipeline names must contain 1 to 80 characters."))
    if not normalized_instruction or len(normalized_instruction) > Pipeline.MAX_INSTRUCTION_LENGTH:
        raise JsonableError(_("Tell Hover what this Pipeline should summarize."))
    if not normalized_topic or len(normalized_topic) > Pipeline.MAX_TOPIC_LENGTH:
        raise JsonableError(_("Output topics must contain 1 to 60 characters."))
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
    output_destination, _subscription = access_stream_by_name(acting_user, output_destination_name)
    access_stream_for_send_message(acting_user, output_destination, None)
    if (
        connector.destination_id == output_destination.id
        and connector.topic.casefold() == normalized_topic.casefold()
    ):
        raise JsonableError(_("A Pipeline cannot post summaries to the topic it reads from."))
    pipeline = Pipeline(
        realm=acting_user.realm,
        connector=connector,
        name=normalized_name,
        instruction=normalized_instruction,
        cadence=cadence,
        weekday=weekday,
        local_time=local_time,
        timezone=timezone,
        output_destination=output_destination,
        output_topic=normalized_topic,
        created_by=acting_user,
    )
    try:
        pipeline.full_clean()
        pipeline.save()
    except ValidationError as exc:
        raise InvalidJSONError(str(exc))
    except IntegrityError:
        raise JsonableError(_("That data source already belongs to a Pipeline."))
    return pipeline
