from __future__ import annotations

from collections.abc import Callable

from django.db import transaction
from django.db.models import Max, QuerySet
from django.utils.timezone import now as timezone_now

from hover.models import Pipeline, PipelineAuthoredMessage, PipelineRun
from hover.telemetry import (
    HoverTelemetryEvent,
    HoverTelemetryOutcome,
    count_bucket,
    emit_hover_telemetry_on_commit,
)
from zerver.actions.message_send import internal_send_stream_message
from zerver.lib.exceptions import JsonableError
from zerver.lib.message import bulk_access_stream_messages_query
from zerver.lib.streams import access_stream_by_name, access_stream_for_send_message
from zerver.models.messages import Message

PipelineSummarizer = Callable[[Pipeline, list[Message]], str]


def runnable_pipelines() -> QuerySet[Pipeline]:
    """Return only Pipelines that a scheduler may attempt to execute."""
    return Pipeline.objects.filter(
        state=Pipeline.State.ACTIVE,
        input_availability=Pipeline.InputAvailability.AVAILABLE,
        input_destination__isnull=False,
    )


def _telemetry_dimensions(
    pipeline: Pipeline,
    *,
    input_count: int,
    skipped_count: int,
    permission_failure: bool,
    published: bool,
) -> dict[str, object]:
    return {
        "realm_id": pipeline.realm_id,
        "pipeline_id": pipeline.id,
        "input_message_count_bucket": count_bucket(input_count),
        "skipped_authored_count_bucket": count_bucket(skipped_count),
        "same_topic": pipeline.input_destination_id == pipeline.output_destination_id
        and pipeline.input_topic.casefold() == pipeline.output_topic.casefold(),
        "permission_failure": permission_failure,
        "published": published,
    }


@transaction.atomic(durable=True)
def execute_pipeline(
    *, pipeline_id: int, request_key: str, summarize: PipelineSummarizer
) -> PipelineRun:
    """Execute one closed Topic message window exactly once for ``request_key``.

    The Pipeline row lock serializes schedule and retry workers.  Output provenance,
    run completion, and cursor advancement commit atomically with message publishing.
    """
    if not request_key or len(request_key) > 64:
        raise ValueError("Pipeline request keys must contain 1 to 64 characters.")
    pipeline = (
        Pipeline.objects.select_for_update(of=("self",))
        .select_related("input_destination", "output_destination", "created_by")
        .get(id=pipeline_id)
    )
    existing = PipelineRun.objects.filter(pipeline=pipeline, request_key=request_key).first()
    if existing is not None and existing.status == PipelineRun.Status.SUCCEEDED:
        emit_hover_telemetry_on_commit(
            HoverTelemetryEvent.PIPELINE_EXECUTION,
            HoverTelemetryOutcome.DUPLICATE_REPLAYED,
            dimensions=_telemetry_dimensions(
                pipeline,
                input_count=0,
                skipped_count=0,
                permission_failure=False,
                published=existing.output_message_id is not None,
            ),
        )
        return existing
    retry_run = existing

    if (
        pipeline.state != Pipeline.State.ACTIVE
        or pipeline.input_availability != Pipeline.InputAvailability.AVAILABLE
        or pipeline.input_destination is None
    ):
        raise JsonableError("This Pipeline is not active.")
    actor = pipeline.created_by
    if actor is None or not actor.is_active:
        pipeline.input_availability = Pipeline.InputAvailability.TOPIC_UNAVAILABLE
        pipeline.save(update_fields=["input_availability", "date_updated"])
        emit_hover_telemetry_on_commit(
            HoverTelemetryEvent.PIPELINE_EXECUTION,
            HoverTelemetryOutcome.DENIED,
            dimensions=_telemetry_dimensions(
                pipeline,
                input_count=0,
                skipped_count=0,
                permission_failure=True,
                published=False,
            ),
        )
        raise JsonableError("The Pipeline input Topic is unavailable.")

    try:
        current_input, _ = access_stream_by_name(actor, pipeline.input_destination.name)
    except JsonableError:
        pipeline.input_availability = Pipeline.InputAvailability.TOPIC_UNAVAILABLE
        pipeline.save(update_fields=["input_availability", "date_updated"])
        emit_hover_telemetry_on_commit(
            HoverTelemetryEvent.PIPELINE_EXECUTION,
            HoverTelemetryOutcome.DENIED,
            dimensions=_telemetry_dimensions(
                pipeline,
                input_count=0,
                skipped_count=0,
                permission_failure=True,
                published=False,
            ),
        )
        raise JsonableError("The Pipeline input Topic is unavailable.")

    try:
        access_stream_for_send_message(actor, pipeline.output_destination, None)
    except JsonableError:
        pipeline.run_health = Pipeline.RunHealth.FAILED
        pipeline.save(update_fields=["run_health", "date_updated"])
        emit_hover_telemetry_on_commit(
            HoverTelemetryEvent.PIPELINE_EXECUTION,
            HoverTelemetryOutcome.DENIED,
            dimensions=_telemetry_dimensions(
                pipeline,
                input_count=0,
                skipped_count=0,
                permission_failure=True,
                published=False,
            ),
        )
        raise

    assert current_input.recipient_id is not None
    base_window = Message.objects.filter(
        realm=pipeline.realm,
        is_channel_message=True,
        recipient_id=current_input.recipient_id,
        subject__iexact=pipeline.input_topic,
    )
    base_window = bulk_access_stream_messages_query(actor, base_window, current_input)
    if pipeline.input_cursor_message_id is not None:
        base_window = base_window.filter(id__gt=pipeline.input_cursor_message_id)
    window_end = (
        retry_run.input_last_message_id
        if retry_run is not None
        else base_window.aggregate(last=Max("id"))["last"]
    )
    closed_window = base_window if window_end is None else base_window.filter(id__lte=window_end)
    skipped_count = closed_window.filter(hover_pipeline_authorship__isnull=False).count()
    messages = list(
        closed_window.filter(hover_pipeline_authorship__isnull=True)
        .select_related("sender")
        .order_by("id")
    )
    if retry_run is None:
        run = PipelineRun.objects.create(
            pipeline=pipeline,
            request_key=request_key,
            input_first_message_id=messages[0].id if messages else None,
            input_last_message_id=window_end,
        )
    else:
        run = retry_run
        run.status = PipelineRun.Status.PENDING
        run.failure_code = ""
        run.completed_at = None
        run.save(update_fields=["status", "failure_code", "completed_at"])
        emit_hover_telemetry_on_commit(
            HoverTelemetryEvent.PIPELINE_EXECUTION,
            HoverTelemetryOutcome.DUPLICATE_REPLAYED,
            dimensions=_telemetry_dimensions(
                pipeline,
                input_count=len(messages),
                skipped_count=skipped_count,
                permission_failure=False,
                published=False,
            ),
        )

    if not messages:
        run.status = PipelineRun.Status.SUCCEEDED
        run.completed_at = timezone_now()
        run.save(update_fields=["status", "completed_at"])
        pipeline.input_cursor_message_id = window_end or pipeline.input_cursor_message_id
        pipeline.run_health = Pipeline.RunHealth.HEALTHY
        pipeline.last_run_at = run.completed_at
        pipeline.save(
            update_fields=["input_cursor_message_id", "run_health", "last_run_at", "date_updated"]
        )
        emit_hover_telemetry_on_commit(
            HoverTelemetryEvent.PIPELINE_EXECUTION,
            HoverTelemetryOutcome.EMPTY,
            dimensions=_telemetry_dimensions(
                pipeline,
                input_count=0,
                skipped_count=skipped_count,
                permission_failure=False,
                published=False,
            ),
        )
        return run

    try:
        # The savepoint makes publishing and provenance indivisible.  If the
        # provenance insert fails, the sent Message is rolled back before the
        # outer transaction records the failed run.
        with transaction.atomic():
            content = summarize(pipeline, messages).strip()
            if not content:
                raise ValueError("Pipeline processing returned an empty result.")
            message_id = internal_send_stream_message(
                sender=actor,
                stream=pipeline.output_destination,
                topic_name=pipeline.output_topic,
                content=content,
                acting_user=actor,
            )
            if message_id is None:
                raise ValueError("Pipeline output message could not be created.")
            output_message = Message.objects.get(id=message_id)
            PipelineAuthoredMessage.objects.create(
                message=output_message, pipeline=pipeline, run=run
            )
            run.output_message = output_message
            run.status = PipelineRun.Status.SUCCEEDED
            run.completed_at = timezone_now()
            run.save(update_fields=["output_message", "status", "completed_at"])
            pipeline.input_cursor_message_id = window_end
            pipeline.run_health = Pipeline.RunHealth.HEALTHY
            pipeline.last_run_at = run.completed_at
            pipeline.save(
                update_fields=[
                    "input_cursor_message_id",
                    "run_health",
                    "last_run_at",
                    "date_updated",
                ]
            )
    except Exception as exc:
        run.status = PipelineRun.Status.FAILED
        run.failure_code = type(exc).__name__[:64]
        run.completed_at = timezone_now()
        run.save(update_fields=["status", "failure_code", "completed_at"])
        pipeline.run_health = Pipeline.RunHealth.FAILED
        pipeline.last_run_at = run.completed_at
        pipeline.save(update_fields=["run_health", "last_run_at", "date_updated"])
        emit_hover_telemetry_on_commit(
            HoverTelemetryEvent.PIPELINE_EXECUTION,
            HoverTelemetryOutcome.RETRYABLE_FAILURE,
            dimensions=_telemetry_dimensions(
                pipeline,
                input_count=len(messages),
                skipped_count=skipped_count,
                permission_failure=False,
                published=False,
            ),
        )
        return run

    emit_hover_telemetry_on_commit(
        HoverTelemetryEvent.PIPELINE_EXECUTION,
        HoverTelemetryOutcome.SUCCESS,
        dimensions=_telemetry_dimensions(
            pipeline,
            input_count=len(messages),
            skipped_count=skipped_count,
            permission_failure=False,
            published=True,
        ),
    )
    return run
