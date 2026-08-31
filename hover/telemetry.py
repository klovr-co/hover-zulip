"""Content-free structured telemetry for Hover.

Callers may only select fixed events, outcomes, and buckets, plus non-negative
integer and boolean dimensions from an event-specific allowlist.  In
particular, arbitrary strings and mappings never cross this boundary.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from enum import Enum

from django.db import transaction

logger = logging.getLogger("zulip.hover.telemetry")


class HoverTelemetryEvent(str, Enum):
    PUBLICATION_SYNC = "publication_sync"
    EVIDENCE_RESOLUTION = "evidence_resolution"
    REVIEW = "review"
    SUGGESTED_ACTION = "suggested_action"
    TODO = "todo"
    NOTIFICATION = "notification"
    EDITION = "edition"
    SOURCE_RECORDS = "source_records"
    SUMMARY_EXECUTION = "summary_execution"
    SUMMARY_SCHEDULER = "summary_scheduler"
    PIPELINE_EXECUTION = "pipeline_execution"
    PIPELINE_LIFECYCLE = "pipeline_lifecycle"
    NATIVE_INGESTION = "native_ingestion"


class HoverTelemetryOutcome(str, Enum):
    SUCCESS = "success"
    DENIED = "denied"
    RETRYABLE_FAILURE = "retryable_failure"
    PERMANENT_FAILURE = "permanent_failure"
    CONTRACT_REJECTED = "contract_rejected"
    DUPLICATE_REJECTED = "duplicate_rejected"
    DUPLICATE_REPLAYED = "duplicate_replayed"
    REQUESTED = "requested"
    RESOLVED = "resolved"
    CLARIFICATION_REQUIRED = "clarification_required"
    APPROVED = "approved"
    NOT_ACTION = "not_action"
    RESTORED = "restored"
    ASSIGNED = "assigned"
    REASSIGNED = "reassigned"
    COMPLETED = "completed"
    REOPENED = "reopened"
    EMITTED = "emitted"
    SUPPRESSED = "suppressed"
    CURRENT = "current"
    DEGRADED = "degraded"
    EMPTY = "empty"
    DRAFT_SAVED = "draft_saved"
    ACTIVATED = "activated"
    PAUSED = "paused"
    RESUMED = "resumed"


class HoverTelemetryBucket(str, Enum):
    ZERO = "zero"
    ONE = "one"
    TWO_TO_FIVE = "two_to_five"
    SIX_TO_TWENTY = "six_to_twenty"
    OVER_TWENTY = "over_twenty"
    UNDER_100MS = "under_100ms"
    UNDER_500MS = "under_500ms"
    UNDER_2S = "under_2s"
    OVER_2S = "over_2s"
    UNDER_1M = "under_1m"
    UNDER_5M = "under_5m"
    UNDER_1H = "under_1h"
    UNDER_1D = "under_1d"
    OVER_1D = "over_1d"
    UNKNOWN = "unknown"
    APPROVAL = "approval"
    ASSIGNMENT = "assignment"
    REASSIGNMENT = "reassignment"
    COMPLETION = "completion"
    REOPENING = "reopening"
    MORNING = "morning"
    END_OF_DAY = "end_of_day"


_COMMON_DIMENSIONS = frozenset({"realm_id"})
_ALLOWED_DIMENSIONS: Mapping[HoverTelemetryEvent, frozenset[str]] = {
    HoverTelemetryEvent.PUBLICATION_SYNC: _COMMON_DIMENSIONS
    | {
        "attachment_id",
        "lag_bucket",
        "publication_count_bucket",
        "created_count_bucket",
        "replayed_count_bucket",
        "retryable",
    },
    HoverTelemetryEvent.EVIDENCE_RESOLUTION: _COMMON_DIMENSIONS
    | {"space_id", "reference_count_bucket", "retryable"},
    HoverTelemetryEvent.REVIEW: _COMMON_DIMENSIONS
    | {"space_id", "material", "target_count_bucket"},
    HoverTelemetryEvent.SUGGESTED_ACTION: _COMMON_DIMENSIONS | {"space_id", "replay", "version"},
    HoverTelemetryEvent.TODO: _COMMON_DIMENSIONS
    | {"space_id", "replay", "version", "notification_emitted"},
    HoverTelemetryEvent.NOTIFICATION: _COMMON_DIMENSIONS | {"space_id", "notification_kind"},
    HoverTelemetryEvent.EDITION: _COMMON_DIMENSIONS
    | {"edition_kind", "edition_count_bucket", "failure_count_bucket", "cache_used"},
    HoverTelemetryEvent.SOURCE_RECORDS: _COMMON_DIMENSIONS
    | {"attachment_id", "duration_bucket", "result_count_bucket"},
    HoverTelemetryEvent.SUMMARY_EXECUTION: _COMMON_DIMENSIONS
    | {
        "installation_id",
        "scheduled",
        "duration_bucket",
        "eligible_count_bucket",
        "snapshot_count_bucket",
        "callback_retry",
        "citation_rejected",
        "published",
    },
    HoverTelemetryEvent.SUMMARY_SCHEDULER: _COMMON_DIMENSIONS | {"installation_id", "lag_bucket"},
    HoverTelemetryEvent.PIPELINE_EXECUTION: _COMMON_DIMENSIONS
    | {
        "pipeline_id",
        "input_message_count_bucket",
        "skipped_authored_count_bucket",
        "same_topic",
        "permission_failure",
        "published",
    },
    HoverTelemetryEvent.PIPELINE_LIFECYCLE: _COMMON_DIMENSIONS | {"pipeline_id"},
    HoverTelemetryEvent.NATIVE_INGESTION: _COMMON_DIMENSIONS
    | {"space_id", "attachment_id", "message_count_bucket", "posthog", "provisioned"},
}
_ALLOWED_OUTCOMES: Mapping[HoverTelemetryEvent, frozenset[HoverTelemetryOutcome]] = {
    HoverTelemetryEvent.PUBLICATION_SYNC: frozenset(
        {
            HoverTelemetryOutcome.SUCCESS,
            HoverTelemetryOutcome.RETRYABLE_FAILURE,
            HoverTelemetryOutcome.PERMANENT_FAILURE,
            HoverTelemetryOutcome.CONTRACT_REJECTED,
            HoverTelemetryOutcome.DUPLICATE_REJECTED,
            HoverTelemetryOutcome.DUPLICATE_REPLAYED,
        }
    ),
    HoverTelemetryEvent.EVIDENCE_RESOLUTION: frozenset(
        {
            HoverTelemetryOutcome.SUCCESS,
            HoverTelemetryOutcome.RETRYABLE_FAILURE,
            HoverTelemetryOutcome.PERMANENT_FAILURE,
        }
    ),
    HoverTelemetryEvent.REVIEW: frozenset(
        {
            HoverTelemetryOutcome.SUCCESS,
            HoverTelemetryOutcome.REQUESTED,
            HoverTelemetryOutcome.RESOLVED,
            HoverTelemetryOutcome.CLARIFICATION_REQUIRED,
        }
    ),
    HoverTelemetryEvent.SUGGESTED_ACTION: frozenset(
        {
            HoverTelemetryOutcome.APPROVED,
            HoverTelemetryOutcome.NOT_ACTION,
            HoverTelemetryOutcome.RESTORED,
        }
    ),
    HoverTelemetryEvent.TODO: frozenset(
        {
            HoverTelemetryOutcome.APPROVED,
            HoverTelemetryOutcome.ASSIGNED,
            HoverTelemetryOutcome.REASSIGNED,
            HoverTelemetryOutcome.COMPLETED,
            HoverTelemetryOutcome.REOPENED,
        }
    ),
    HoverTelemetryEvent.NOTIFICATION: frozenset(
        {HoverTelemetryOutcome.EMITTED, HoverTelemetryOutcome.SUPPRESSED}
    ),
    HoverTelemetryEvent.EDITION: frozenset(
        {
            HoverTelemetryOutcome.CURRENT,
            HoverTelemetryOutcome.DEGRADED,
            HoverTelemetryOutcome.EMPTY,
        }
    ),
    HoverTelemetryEvent.SOURCE_RECORDS: frozenset(
        {
            HoverTelemetryOutcome.SUCCESS,
            HoverTelemetryOutcome.DENIED,
            HoverTelemetryOutcome.RETRYABLE_FAILURE,
            HoverTelemetryOutcome.PERMANENT_FAILURE,
        }
    ),
    HoverTelemetryEvent.SUMMARY_EXECUTION: frozenset(
        {
            HoverTelemetryOutcome.REQUESTED,
            HoverTelemetryOutcome.SUCCESS,
            HoverTelemetryOutcome.EMPTY,
            HoverTelemetryOutcome.PERMANENT_FAILURE,
            HoverTelemetryOutcome.CONTRACT_REJECTED,
            HoverTelemetryOutcome.DUPLICATE_REPLAYED,
        }
    ),
    HoverTelemetryEvent.SUMMARY_SCHEDULER: frozenset(
        {HoverTelemetryOutcome.REQUESTED, HoverTelemetryOutcome.SUPPRESSED}
    ),
    HoverTelemetryEvent.PIPELINE_EXECUTION: frozenset(
        {
            HoverTelemetryOutcome.SUCCESS,
            HoverTelemetryOutcome.DENIED,
            HoverTelemetryOutcome.RETRYABLE_FAILURE,
            HoverTelemetryOutcome.DUPLICATE_REPLAYED,
            HoverTelemetryOutcome.EMPTY,
        }
    ),
    HoverTelemetryEvent.PIPELINE_LIFECYCLE: frozenset(
        {
            HoverTelemetryOutcome.DRAFT_SAVED,
            HoverTelemetryOutcome.ACTIVATED,
            HoverTelemetryOutcome.PAUSED,
            HoverTelemetryOutcome.RESUMED,
        }
    ),
    HoverTelemetryEvent.NATIVE_INGESTION: frozenset(
        {
            HoverTelemetryOutcome.SUCCESS,
            HoverTelemetryOutcome.DENIED,
            HoverTelemetryOutcome.RETRYABLE_FAILURE,
            HoverTelemetryOutcome.PERMANENT_FAILURE,
        }
    ),
}


def count_bucket(count: int) -> HoverTelemetryBucket:
    if count < 0:
        raise ValueError("Telemetry counts must be non-negative")
    if count == 0:
        return HoverTelemetryBucket.ZERO
    if count == 1:
        return HoverTelemetryBucket.ONE
    if count <= 5:
        return HoverTelemetryBucket.TWO_TO_FIVE
    if count <= 20:
        return HoverTelemetryBucket.SIX_TO_TWENTY
    return HoverTelemetryBucket.OVER_TWENTY


def duration_bucket(duration_ms: float) -> HoverTelemetryBucket:
    if duration_ms < 0:
        raise ValueError("Telemetry durations must be non-negative")
    if duration_ms < 100:
        return HoverTelemetryBucket.UNDER_100MS
    if duration_ms < 500:
        return HoverTelemetryBucket.UNDER_500MS
    if duration_ms < 2_000:
        return HoverTelemetryBucket.UNDER_2S
    return HoverTelemetryBucket.OVER_2S


def lag_bucket(lag_seconds: float | None) -> HoverTelemetryBucket:
    if lag_seconds is None:
        return HoverTelemetryBucket.UNKNOWN
    lag_seconds = max(lag_seconds, 0)
    if lag_seconds < 60:
        return HoverTelemetryBucket.UNDER_1M
    if lag_seconds < 5 * 60:
        return HoverTelemetryBucket.UNDER_5M
    if lag_seconds < 60 * 60:
        return HoverTelemetryBucket.UNDER_1H
    if lag_seconds < 24 * 60 * 60:
        return HoverTelemetryBucket.UNDER_1D
    return HoverTelemetryBucket.OVER_1D


def _serialize_dimensions(
    event: HoverTelemetryEvent, dimensions: Mapping[str, object] | None
) -> str:
    supplied = dict(dimensions or {})
    unknown = supplied.keys() - _ALLOWED_DIMENSIONS[event]
    if unknown:
        raise ValueError(f"Unsupported Hover telemetry dimensions: {sorted(unknown)}")

    serialized: list[str] = []
    for key in sorted(supplied):
        value = supplied[key]
        if isinstance(value, HoverTelemetryBucket):
            rendered = value.value
        elif isinstance(value, bool):
            rendered = "true" if value else "false"
        elif isinstance(value, int) and value >= 0:
            rendered = str(value)
        else:
            raise TypeError(
                "Hover telemetry dimensions must be fixed buckets, booleans, "
                "or non-negative integers"
            )
        serialized.append(f"{key}={rendered}")
    return " ".join(serialized)


def _validate_event_outcome(event: object, outcome: object) -> None:
    if not isinstance(event, HoverTelemetryEvent) or not isinstance(outcome, HoverTelemetryOutcome):
        raise TypeError("Hover telemetry requires fixed event and outcome enums")
    if outcome not in _ALLOWED_OUTCOMES[event]:
        raise ValueError("Hover telemetry outcome is not valid for this event")


def emit_hover_telemetry(
    event: HoverTelemetryEvent,
    outcome: HoverTelemetryOutcome,
    *,
    dimensions: Mapping[str, object] | None = None,
) -> None:
    _validate_event_outcome(event, outcome)
    serialized = _serialize_dimensions(event, dimensions)
    suffix = f" {serialized}" if serialized else ""
    logger.info("Hover telemetry event=%s outcome=%s%s", event.value, outcome.value, suffix)


def emit_hover_telemetry_on_commit(
    event: HoverTelemetryEvent,
    outcome: HoverTelemetryOutcome,
    *,
    dimensions: Mapping[str, object] | None = None,
) -> None:
    frozen_dimensions = dict(dimensions or {})
    # Reject unsafe values at the caller boundary, rather than retaining them in
    # an on-commit callback even temporarily.
    _validate_event_outcome(event, outcome)
    _serialize_dimensions(event, frozen_dimensions)
    transaction.on_commit(
        lambda: emit_hover_telemetry(event, outcome, dimensions=frozen_dimensions)
    )
