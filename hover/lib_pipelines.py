from typing import Any

from django.db.models import QuerySet

from hover.lib_connectors import get_connector_provider_metadata, visible_connectors
from hover.models import Pipeline
from zerver.lib.streams import get_streams_for_user
from zerver.models.users import UserProfile


def pipeline_projection_queryset() -> QuerySet[Pipeline]:
    return Pipeline.objects.select_related(
        "connector__bot", "connector__destination", "output_destination", "created_by"
    )


def visible_pipelines(user: UserProfile) -> QuerySet[Pipeline]:
    visible_output_ids = [stream.id for stream in get_streams_for_user(user)]
    return pipeline_projection_queryset().filter(
        connector__in=visible_connectors(user), output_destination_id__in=visible_output_ids
    )


def pipeline_data(pipeline: Pipeline) -> dict[str, Any]:
    connector = pipeline.connector
    status: str
    if connector.state != connector.State.ACTIVE:
        status = Pipeline.State.NEEDS_ATTENTION
    elif pipeline.state == Pipeline.State.ACTIVE and connector.health_status == connector.HealthStatus.DEGRADED:
        status = Pipeline.State.NEEDS_ATTENTION
    else:
        status = pipeline.state
    provider_logo_url = None
    if connector.provider_key != "legacy":
        provider_logo_url = get_connector_provider_metadata(connector.provider_key)["logo_url"]
    return {
        "id": pipeline.id,
        "name": pipeline.name,
        "instruction": pipeline.instruction,
        "connector_id": connector.id,
        "provider_key": connector.provider_key,
        "provider_name": connector.provider_name,
        "provider_logo_url": provider_logo_url,
        "source_destination": connector.destination.name if connector.destination else None,
        "source_topic": connector.topic,
        "event_options": connector.event_options,
        "cadence": pipeline.cadence,
        "weekday": pipeline.weekday,
        "local_time": pipeline.local_time.strftime("%H:%M"),
        "timezone": pipeline.timezone,
        "output_destination": pipeline.output_destination.name,
        "output_topic": pipeline.output_topic,
        "status": status,
        "last_run_at": pipeline.last_run_at.isoformat() if pipeline.last_run_at else None,
        "date_created": pipeline.date_created.isoformat(),
    }
