from __future__ import annotations

from django.db.models import QuerySet

from hover.models import Pipeline
from zerver.lib.exceptions import JsonableError
from zerver.lib.streams import access_stream_by_name, access_stream_for_send_message
from zerver.models.streams import Stream


def _pipelines_for_topic(stream: Stream, topic: str) -> QuerySet[Pipeline]:
    return Pipeline.objects.select_related("created_by", "output_destination").filter(
        input_destination=stream, input_topic__iexact=topic
    )


def _execution_identity_has_access(pipeline: Pipeline, input_stream: Stream) -> bool:
    actor = pipeline.created_by
    if actor is None or not actor.is_active:
        return False
    try:
        access_stream_by_name(actor, input_stream.name)
        access_stream_for_send_message(actor, pipeline.output_destination, None)
    except JsonableError:
        return False
    return True


def do_update_pipeline_inputs_for_topic_move(
    *, source_stream: Stream, source_topic: str, target_stream: Stream, target_topic: str
) -> int:
    """Follow a complete Topic rename/move without reacting to partial message edits."""
    updated = 0
    for pipeline in _pipelines_for_topic(source_stream, source_topic).select_for_update(of=("self",)):
        pipeline.input_destination = target_stream
        pipeline.input_topic = target_topic
        if _execution_identity_has_access(pipeline, target_stream):
            pipeline.input_availability = Pipeline.InputAvailability.AVAILABLE
        else:
            pipeline.input_availability = Pipeline.InputAvailability.TOPIC_UNAVAILABLE
        pipeline.save(
            update_fields=[
                "input_destination",
                "input_topic",
                "input_availability",
                "date_updated",
            ]
        )
        updated += 1
    return updated


def do_mark_pipeline_topic_unavailable(*, stream: Stream, topic: str) -> int:
    return _pipelines_for_topic(stream, topic).update(
        input_availability=Pipeline.InputAvailability.TOPIC_UNAVAILABLE,
    )


def do_mark_stream_pipeline_inputs_unavailable(*, stream: Stream) -> int:
    return Pipeline.objects.filter(input_destination=stream).update(
        input_availability=Pipeline.InputAvailability.TOPIC_UNAVAILABLE,
    )


def do_restore_stream_pipeline_inputs(*, stream: Stream) -> int:
    updated = 0
    for pipeline in Pipeline.objects.select_related("created_by", "output_destination").filter(
        input_destination=stream,
        input_availability=Pipeline.InputAvailability.TOPIC_UNAVAILABLE,
    ):
        if not _execution_identity_has_access(pipeline, stream):
            continue
        pipeline.input_availability = Pipeline.InputAvailability.AVAILABLE
        pipeline.save(update_fields=["input_availability", "date_updated"])
        updated += 1
    return updated
