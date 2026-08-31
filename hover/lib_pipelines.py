from typing import Any

from django.db.models import Prefetch, Q, QuerySet

from hover.lib_connectors import get_connector_provider_metadata
from hover.models import Connector, Pipeline
from zerver.lib.streams import get_streams_for_user
from zerver.lib.topic import get_topic_history_for_stream
from zerver.models.users import UserProfile


def pipeline_projection_queryset() -> QuerySet[Pipeline]:
    return Pipeline.objects.select_related(
        "input_destination", "output_destination", "created_by"
    ).prefetch_related(
        Prefetch(
            "input_destination__hover_connectors",
            queryset=Connector.objects.select_related("destination").order_by("id"),
        )
    )


def _visible_streams(user: UserProfile) -> list[Any]:
    return get_streams_for_user(user, include_can_access_content=True)


def visible_pipelines(user: UserProfile) -> QuerySet[Pipeline]:
    visible_stream_ids = [stream.id for stream in _visible_streams(user)]
    normal_visibility = Q(
        input_destination_id__in=visible_stream_ids,
        output_destination_id__in=visible_stream_ids,
        created_by=user,
    )
    repair_visibility = Q(
        input_availability=Pipeline.InputAvailability.TOPIC_UNAVAILABLE,
        created_by=user,
    )
    if user.is_realm_admin:
        normal_visibility = Q(
            input_destination_id__in=visible_stream_ids,
            output_destination_id__in=visible_stream_ids,
            realm=user.realm,
        )
        repair_visibility = Q(
            input_availability=Pipeline.InputAvailability.TOPIC_UNAVAILABLE,
            realm=user.realm,
        )
    return pipeline_projection_queryset().filter(normal_visibility | repair_visibility).distinct()


def _topic_connectors(stream: Any, topic: str) -> list[Connector]:
    connectors = stream.hover_connectors.all()
    return [connector for connector in connectors if connector.topic.casefold() == topic.casefold()]


def _data_source_data(connector: Connector) -> dict[str, Any]:
    logo_url = None
    if connector.provider_key != "legacy":
        logo_url = get_connector_provider_metadata(connector.provider_key)["logo_url"]
    return {
        "id": connector.id,
        "name": connector.name or connector.provider_name,
        "provider_key": connector.provider_key,
        "provider_name": connector.provider_name,
        "provider_logo_url": logo_url,
        "state": connector.state,
        "health_status": connector.health_status,
    }


def _source_warning(connector: Connector) -> dict[str, Any] | None:
    if (
        connector.state == Connector.State.ACTIVE
        and connector.health_status != Connector.HealthStatus.DEGRADED
    ):
        return None
    return {
        "data_source_id": connector.id,
        "data_source_name": connector.name or connector.provider_name,
        "state": connector.state,
        "health_status": connector.health_status,
    }


def pipeline_data(pipeline: Pipeline, user: UserProfile) -> dict[str, Any]:
    input_destination = pipeline.input_destination
    connectors = (
        []
        if input_destination is None
        else _topic_connectors(input_destination, pipeline.input_topic)
    )
    warnings = [warning for connector in connectors if (warning := _source_warning(connector))]
    status = pipeline.state
    if (
        pipeline.state != Pipeline.State.DRAFT
        and pipeline.input_availability == Pipeline.InputAvailability.TOPIC_UNAVAILABLE
    ):
        status = "needs_attention"
    can_update = user.is_realm_admin or pipeline.created_by_id == user.id
    available_transitions: list[str] = []
    if can_update:
        available_transitions.append("edit")
        if pipeline.state == Pipeline.State.ACTIVE:
            available_transitions.append("pause")
        elif (
            pipeline.state == Pipeline.State.DRAFT
            and pipeline.input_availability == Pipeline.InputAvailability.AVAILABLE
        ):
            available_transitions.append("activate")
        elif (
            pipeline.state == Pipeline.State.PAUSED
            and pipeline.input_availability == Pipeline.InputAvailability.AVAILABLE
        ):
            available_transitions.append("resume")
    return {
        "id": pipeline.id,
        "name": pipeline.name,
        "instruction": pipeline.instruction,
        "input_destination": input_destination.name if input_destination is not None else None,
        "input_topic": pipeline.input_topic,
        "data_sources": [_data_source_data(connector) for connector in connectors],
        "source_warnings": warnings,
        "cadence": pipeline.cadence,
        "weekday": pipeline.weekday,
        "local_time": pipeline.local_time.strftime("%H:%M"),
        "timezone": pipeline.timezone,
        "output_destination": pipeline.output_destination.name,
        "output_topic": pipeline.output_topic,
        "input_availability": pipeline.input_availability,
        "run_health": pipeline.run_health,
        "lifecycle_state": pipeline.state,
        "status": status,
        "available_transitions": available_transitions,
        "last_run_at": pipeline.last_run_at.isoformat() if pipeline.last_run_at else None,
        "date_created": pipeline.date_created.isoformat(),
    }


def topic_inputs_for_user(user: UserProfile) -> list[dict[str, Any]]:
    streams = _visible_streams(user)
    identities: dict[tuple[int, str], tuple[Any, str]] = {}
    for stream in streams:
        assert stream.recipient_id is not None
        history = get_topic_history_for_stream(
            user_profile=user,
            recipient_id=stream.recipient_id,
            public_history=stream.is_history_public_to_subscribers(),
            allow_empty_topic_name=False,
        )
        for item in history:
            topic = item["name"]
            identities[(stream.id, topic.casefold())] = (stream, topic)

    connectors = list(
        Connector.objects.select_related("destination")
        .filter(
            realm=user.realm,
            destination_id__in=[stream.id for stream in streams],
        )
        .exclude(topic="")
        .order_by("id")
    )
    connectors_by_topic: dict[tuple[int, str], list[Connector]] = {}
    streams_by_id = {stream.id: stream for stream in streams}
    for connector in connectors:
        assert connector.destination_id is not None
        stream = streams_by_id[connector.destination_id]
        identities.setdefault((stream.id, connector.topic.casefold()), (stream, connector.topic))
        connectors_by_topic.setdefault((stream.id, connector.topic.casefold()), []).append(
            connector
        )

    topics = []
    for stream, topic in identities.values():
        topic_connectors = connectors_by_topic.get((stream.id, topic.casefold()), [])
        topics.append(
            {
                "input_destination": stream.name,
                "input_topic": topic,
                "data_sources": [_data_source_data(connector) for connector in topic_connectors],
                "input_availability": Pipeline.InputAvailability.AVAILABLE,
            }
        )

    # Keep a recoverable Topic identity in the catalogue even when its Space is
    # archived or its messages were deleted.  ``visible_pipelines`` limits these
    # rows to the Pipeline creator (or a realm administrator), so this does not
    # disclose unavailable private Topics to unrelated users.
    unavailable_pipelines = visible_pipelines(user).filter(
        input_availability=Pipeline.InputAvailability.TOPIC_UNAVAILABLE,
        input_destination__isnull=False,
    )
    available_keys = set(identities)
    unavailable_keys: set[tuple[int, str]] = set()
    for pipeline in unavailable_pipelines:
        assert pipeline.input_destination is not None
        assert pipeline.input_destination_id is not None
        key = (pipeline.input_destination_id, pipeline.input_topic.casefold())
        if key in available_keys or key in unavailable_keys:
            continue
        unavailable_keys.add(key)
        topic_connectors = _topic_connectors(pipeline.input_destination, pipeline.input_topic)
        topics.append(
            {
                "input_destination": pipeline.input_destination.name,
                "input_topic": pipeline.input_topic,
                "data_sources": [_data_source_data(connector) for connector in topic_connectors],
                "input_availability": Pipeline.InputAvailability.TOPIC_UNAVAILABLE,
            }
        )
    return sorted(
        topics,
        key=lambda item: (item["input_destination"].casefold(), item["input_topic"].casefold()),
    )
