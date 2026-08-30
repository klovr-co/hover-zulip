from __future__ import annotations

import hashlib
import json
import secrets
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils.timezone import is_aware
from django.utils.timezone import now as timezone_now
from django.utils.translation import gettext as _

from hover.lib_spaces import user_is_space_administrator
from hover.models import (
    EvidenceLink,
    GeneratedInputSnapshot,
    GeneratedItem,
    ModuleInstallation,
    ModuleInstallationTrigger,
    ModuleSupportedTrigger,
    SpaceAttachment,
    SpaceMembership,
    SummaryExecution,
    SummaryExecutionInput,
    SummaryExecutionMessage,
)
from hover.telemetry import (
    HoverTelemetryEvent,
    HoverTelemetryOutcome,
    count_bucket,
    duration_bucket,
    emit_hover_telemetry_on_commit,
    lag_bucket,
)
from zerver.actions.message_send import internal_send_stream_message
from zerver.lib.exceptions import JsonableError
from zerver.lib.streams import access_stream_by_id, subscribed_to_stream
from zerver.models.messages import Message
from zerver.models.users import UserProfile

MAX_SUMMARY_INPUTS = 20
MAX_SNAPSHOT_MESSAGES = 120
MAX_SERIALIZED_EVIDENCE_CHARACTERS = 60_000
MAX_OPERATION_BYTES = 128 * 1024
CALLBACK_TOKEN_PREFIX = "hvr_exec_"
SUMMARY_EXECUTION_SCHEMA_VERSION = "1.0"


class SummaryExecutionConflictError(JsonableError):
    http_status_code = 409


@dataclass(frozen=True)
class SummaryDispatch:
    execution: SummaryExecution
    operation: dict[str, object] | None
    callback_bearer: str | None


@dataclass(frozen=True)
class _Candidate:
    input_position: int
    message: Message


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def _hash(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _content_digest(content: str) -> str:
    return hashlib.sha256(content.encode()).hexdigest()


def _callback_token() -> str:
    return f"{CALLBACK_TOKEN_PREFIX}{secrets.token_urlsafe(32)}"


def _callback_token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _execution_telemetry_dimensions(
    execution: SummaryExecution, **extra: object
) -> dict[str, object]:
    return {
        "realm_id": execution.installation.realm_id,
        "installation_id": execution.installation_id,
        "scheduled": execution.kind == SummaryExecution.Kind.SCHEDULED,
        "eligible_count_bucket": count_bucket(execution.eligible_message_count),
        "snapshot_count_bucket": count_bucket(execution.snapshot_message_count),
        **extra,
    }


def _assert_execution_window(window_start: datetime, window_end: datetime) -> None:
    if not is_aware(window_start) or not is_aware(window_end) or window_start >= window_end:
        raise JsonableError(_("Choose a valid Summary date range."))
    if window_end > timezone_now():
        raise JsonableError(_("A Summary preview cannot end in the future."))


def _assert_manual_access(user: UserProfile, installation: ModuleInstallation) -> None:
    space = installation.space
    if (
        user.realm_id != installation.realm_id
        or installation.state != ModuleInstallation.State.ENABLED
        or installation.summary_stream_id is None
        or not SpaceMembership.objects.filter(space=space, user=user, user__is_active=True).exists()
        or not subscribed_to_stream(user, installation.summary_stream_id)
    ):
        raise JsonableError(_("You do not have permission to generate this Summary."))
    assert space.stream_id is not None
    access_stream_by_id(user, space.stream_id)


def _candidate_character_count(candidate: _Candidate, citation_position: int) -> int:
    # This is the exact serialized evidence object shape used in the request.
    value = {
        "citation_token": f"evidence_{citation_position:04d}",
        "sender_label": "Participant 0000",
        "sent_at": candidate.message.date_sent.isoformat(),
        "text": candidate.message.content,
    }
    return len(_canonical_bytes(value).decode())


def _balanced_selection(candidates: dict[int, list[Message]]) -> list[_Candidate]:
    """Round-robin newest evidence per input, then return native chronological order."""
    queues = {
        input_position: deque(
            _Candidate(input_position=input_position, message=message)
            for message in reversed(messages)
        )
        for input_position, messages in candidates.items()
    }
    selected: list[_Candidate] = []
    serialized_characters = 0
    while queues and len(selected) < MAX_SNAPSHOT_MESSAGES:
        made_progress = False
        for input_position in sorted(list(queues)):
            queue = queues[input_position]
            if not queue:
                del queues[input_position]
                continue
            candidate = queue.popleft()
            made_progress = True
            candidate_characters = _candidate_character_count(candidate, len(selected) + 1)
            if serialized_characters + candidate_characters <= MAX_SERIALIZED_EVIDENCE_CHARACTERS:
                selected.append(candidate)
                serialized_characters += candidate_characters
                if len(selected) >= MAX_SNAPSHOT_MESSAGES:
                    break
            if not queue:
                del queues[input_position]
        if not made_progress:
            break
    return sorted(selected, key=lambda item: (item.message.date_sent, item.message.id))


def _operation_for_execution(execution: SummaryExecution) -> dict[str, object]:
    inputs = list(execution.input_snapshots.all())
    messages = list(execution.message_snapshots.all())
    return {
        "schema_version": SUMMARY_EXECUTION_SCHEMA_VERSION,
        "execution_id": str(execution.id),
        "kind": execution.kind,
        "window": {
            "start": execution.window_start.isoformat(),
            "end": execution.window_end.isoformat(),
        },
        "policy_revision": execution.policy_revision,
        "module_version": execution.installation.version.version,
        "prompt_version": execution.installation.version.prompt_key,
        "snapshot_hash": execution.snapshot_hash,
        "inputs": [
            {
                "input_token": f"input_{item.position + 1:04d}",
                "kind": item.kind,
                "label": item.topic_name,
            }
            for item in inputs
        ],
        "evidence": [
            {
                "input_token": f"input_{item.input.position + 1:04d}",
                "citation_token": item.citation_token,
                "sent_at": item.sent_at.isoformat(),
                "sender_label": item.sender_label,
                "text": item.frozen_content,
            }
            for item in messages
        ],
    }


def _existing_execution(
    *,
    installation: ModuleInstallation,
    kind: str,
    manual_request_id: str | None,
    scheduled_for: datetime | None,
) -> SummaryExecution | None:
    if kind == SummaryExecution.Kind.MANUAL:
        return SummaryExecution.objects.filter(
            installation=installation, kind=kind, manual_request_id=manual_request_id
        ).first()
    return SummaryExecution.objects.filter(
        installation=installation, kind=kind, scheduled_for=scheduled_for
    ).first()


@transaction.atomic(durable=True)
def do_prepare_summary_execution(
    *,
    installation: ModuleInstallation,
    kind: str,
    window_start: datetime,
    window_end: datetime,
    requester: UserProfile | None = None,
    manual_request_id: str | None = None,
    scheduled_for: datetime | None = None,
) -> SummaryDispatch:
    _assert_execution_window(window_start, window_end)
    current = (
        ModuleInstallation.objects.select_for_update(no_key=True, of=("self",))
        .select_related("realm", "space__stream", "summary_stream", "version")
        .prefetch_related("summary_inputs__source_attachment__source__account")
        .get(id=installation.id)
    )
    if current.state != ModuleInstallation.State.ENABLED or current.summary_stream_id is None:
        raise JsonableError(_("This Summary is not active."))
    if kind == SummaryExecution.Kind.MANUAL:
        if requester is None or not manual_request_id or scheduled_for is not None:
            raise JsonableError(_("Manual Summary executions require a request ID."))
        _assert_manual_access(requester, current)
    elif kind == SummaryExecution.Kind.SCHEDULED:
        if requester is not None or manual_request_id is not None or scheduled_for != window_end:
            raise JsonableError(_("Invalid scheduled Summary occurrence."))
    else:
        raise JsonableError(_("Invalid Summary execution kind."))

    existing = _existing_execution(
        installation=current,
        kind=kind,
        manual_request_id=manual_request_id,
        scheduled_for=scheduled_for,
    )
    if existing is not None:
        if (
            existing.window_start != window_start
            or existing.window_end != window_end
            or existing.policy_revision != current.policy_revision
            or existing.policy_hash != current.policy_hash
        ):
            raise SummaryExecutionConflictError(_("That Summary request ID is already in use."))
        operation = (
            _operation_for_execution(existing)
            if existing.status in [
                SummaryExecution.Status.PENDING,
                SummaryExecution.Status.DISPATCHED,
            ]
            and existing.snapshot_message_count
            else None
        )
        if operation is None:
            return SummaryDispatch(existing, None, None)
        token = _callback_token()
        existing.callback_token_hash = _callback_token_hash(token)
        existing.status = SummaryExecution.Status.DISPATCHED
        existing.dispatched_at = timezone_now()
        existing.save(update_fields=["callback_token_hash", "status", "dispatched_at"])
        return SummaryDispatch(existing, operation, token)

    if kind == SummaryExecution.Kind.SCHEDULED and SummaryExecution.objects.filter(
        installation=current,
        kind=SummaryExecution.Kind.SCHEDULED,
        status__in=[SummaryExecution.Status.PENDING, SummaryExecution.Status.DISPATCHED],
    ).exists():
        raise SummaryExecutionConflictError(_("This Summary already has an execution in flight."))

    inputs = list(current.summary_inputs.all())
    if not 1 <= len(inputs) <= MAX_SUMMARY_INPUTS:
        raise JsonableError(_("This Summary has an invalid input policy."))
    execution = SummaryExecution.objects.create(
        installation=current,
        kind=kind,
        window_start=window_start,
        window_end=window_end,
        policy_revision=current.policy_revision,
        policy_hash=current.policy_hash,
        requester=requester,
        manual_request_id=manual_request_id,
        scheduled_for=scheduled_for,
    )
    execution_inputs = SummaryExecutionInput.objects.bulk_create(
        [
            SummaryExecutionInput(
                execution=execution,
                stream=item.stream,
                topic_name=item.topic_name,
                kind=item.kind,
                source_attachment=item.source_attachment,
                provider_name=(
                    item.source_attachment.source.account.provider_name
                    if item.source_attachment is not None
                    else ""
                ),
                position=item.position,
            )
            for item in inputs
        ]
    )
    assert current.space.stream is not None
    topic_filter = Q()
    for item in inputs:
        topic_filter |= Q(subject__iexact=item.topic_name)
    messages = list(
        Message.objects.filter(
            topic_filter,
            realm=current.realm,
            recipient=current.space.stream.recipient,
            is_channel_message=True,
            date_sent__gte=window_start,
            date_sent__lt=window_end,
        )
        .select_related("sender")
        .order_by("date_sent", "id")
    )
    input_position_by_topic = {item.topic_name.casefold(): item.position for item in inputs}
    by_input: dict[int, list[Message]] = defaultdict(list)
    for message in messages:
        position = input_position_by_topic.get(message.topic_name().casefold())
        if position is not None:
            by_input[position].append(message)
    selected = _balanced_selection(by_input)
    sender_labels: dict[int, str] = {}
    snapshots: list[SummaryExecutionMessage] = []
    for position, candidate in enumerate(selected):
        sender_labels.setdefault(
            candidate.message.sender_id, f"Participant {len(sender_labels) + 1}"
        )
        snapshots.append(
            SummaryExecutionMessage(
                execution=execution,
                input=execution_inputs[candidate.input_position],
                message=candidate.message,
                frozen_content=candidate.message.content,
                frozen_rendered_content=candidate.message.rendered_content or "",
                content_digest=_content_digest(candidate.message.content),
                sender_label=sender_labels[candidate.message.sender_id],
                sent_at=candidate.message.date_sent,
                position=position,
                citation_token=f"evidence_{position + 1:04d}",
            )
        )
    SummaryExecutionMessage.objects.bulk_create(snapshots)
    snapshot_payload = {
        "inputs": [
            {
                "input_token": f"input_{item.position + 1:04d}",
                "kind": item.kind,
                "label": item.topic_name,
            }
            for item in execution_inputs
        ],
        "evidence": [
            {
                "input_token": f"input_{item.input.position + 1:04d}",
                "citation_token": item.citation_token,
                "sent_at": item.sent_at.isoformat(),
                "sender_label": item.sender_label,
                "text": item.frozen_content,
            }
            for item in snapshots
        ],
    }
    execution.eligible_message_count = len(messages)
    execution.snapshot_message_count = len(snapshots)
    execution.snapshot_hash = _hash(snapshot_payload)
    if not snapshots:
        no_change: dict[str, object] = {
            "schema_version": SUMMARY_EXECUTION_SCHEMA_VERSION,
            "status": SummaryExecution.Status.NO_CHANGE,
            "snapshot_hash": execution.snapshot_hash,
            "digest": None,
            "evidence_tokens": [],
            "failure_code": "",
        }
        execution.status = SummaryExecution.Status.NO_CHANGE
        execution.result_hash = _hash(no_change)
        execution.completed_at = timezone_now()
        execution.save(
            update_fields=[
                "eligible_message_count",
                "snapshot_message_count",
                "snapshot_hash",
                "status",
                "result_hash",
                "completed_at",
            ]
        )
        emit_hover_telemetry_on_commit(
            HoverTelemetryEvent.SUMMARY_EXECUTION,
            HoverTelemetryOutcome.EMPTY,
            dimensions=_execution_telemetry_dimensions(execution),
        )
        return SummaryDispatch(execution, None, None)

    execution.save(
        update_fields=["eligible_message_count", "snapshot_message_count", "snapshot_hash"]
    )
    operation = _operation_for_execution(execution)
    request_hash = _hash(operation)
    if len(_canonical_bytes(operation)) > MAX_OPERATION_BYTES:
        raise JsonableError(_("The Summary snapshot exceeds the operation limit."))
    token = _callback_token()
    execution.request_hash = request_hash
    execution.callback_token_hash = _callback_token_hash(token)
    execution.status = SummaryExecution.Status.DISPATCHED
    execution.dispatched_at = timezone_now()
    execution.save(
        update_fields=["request_hash", "callback_token_hash", "status", "dispatched_at"]
    )
    emit_hover_telemetry_on_commit(
        HoverTelemetryEvent.SUMMARY_EXECUTION,
        HoverTelemetryOutcome.REQUESTED,
        dimensions=_execution_telemetry_dimensions(execution),
    )
    return SummaryDispatch(execution, operation, token)


def _validate_result_payload(
    execution: SummaryExecution, payload: dict[str, object]
) -> tuple[dict[str, object], str, bool]:
    required = {
        "schema_version",
        "status",
        "snapshot_hash",
        "digest",
        "evidence_tokens",
        "failure_code",
        "result_hash",
    }
    if set(payload) != required or payload.get("schema_version") != SUMMARY_EXECUTION_SCHEMA_VERSION:
        raise JsonableError(_("Invalid Summary result contract."))
    status = payload.get("status")
    if status not in {
        SummaryExecution.Status.SUCCEEDED,
        SummaryExecution.Status.NO_CHANGE,
        SummaryExecution.Status.FAILED,
    } or payload.get("snapshot_hash") != execution.snapshot_hash:
        raise JsonableError(_("Invalid Summary result contract."))
    supplied_hash = payload.get("result_hash")
    canonical_result = {key: value for key, value in payload.items() if key != "result_hash"}
    computed_hash = _hash(canonical_result)
    if not isinstance(supplied_hash, str) or supplied_hash != computed_hash:
        raise JsonableError(_("Invalid Summary result hash."))
    evidence_tokens = payload.get("evidence_tokens")
    if not isinstance(evidence_tokens, list) or any(
        not isinstance(token, str) for token in evidence_tokens
    ):
        raise JsonableError(_("Invalid Summary citations."))
    known_tokens = set(execution.message_snapshots.values_list("citation_token", flat=True))
    citation_violation = len(evidence_tokens) != len(set(evidence_tokens)) or not set(
        evidence_tokens
    ).issubset(known_tokens)
    digest = payload.get("digest")
    failure_code = payload.get("failure_code")
    if not isinstance(failure_code, str) or len(failure_code) > 64:
        raise JsonableError(_("Invalid Summary result contract."))
    if status == SummaryExecution.Status.SUCCEEDED:
        expected_digest_keys = {
            "title",
            "main_thread",
            "what_changed",
            "confirmed_facts",
            "unresolved_points",
            "why_it_matters",
        }
        if (
            not isinstance(digest, dict)
            or set(digest) != expected_digest_keys
            or not evidence_tokens
            or failure_code
        ):
            raise JsonableError(_("Invalid successful Summary result."))
    elif digest is not None or evidence_tokens:
        raise JsonableError(_("No-change and failed Summary results cannot include prose."))
    return canonical_result, computed_hash, citation_violation


@transaction.atomic(durable=True)
def do_accept_summary_result(
    *, execution_id: str, callback_bearer: str, payload: dict[str, object]
) -> SummaryExecution:
    try:
        execution = (
            SummaryExecution.objects.select_for_update()
            .select_related("installation")
            .get(id=execution_id)
        )
    except (SummaryExecution.DoesNotExist, ValueError):
        raise JsonableError(_("Invalid Summary execution."))
    if (
        not callback_bearer.startswith(CALLBACK_TOKEN_PREFIX)
        or not secrets.compare_digest(
            _callback_token_hash(callback_bearer), execution.callback_token_hash
        )
    ):
        raise JsonableError(_("Invalid Summary callback credential."))
    canonical_result, result_hash, citation_violation = _validate_result_payload(
        execution, payload
    )
    if execution.status in {
        SummaryExecution.Status.SUCCEEDED,
        SummaryExecution.Status.NO_CHANGE,
        SummaryExecution.Status.FAILED,
        SummaryExecution.Status.PUBLISHED,
    }:
        if execution.result_hash == result_hash:
            emit_hover_telemetry_on_commit(
                HoverTelemetryEvent.SUMMARY_EXECUTION,
                HoverTelemetryOutcome.DUPLICATE_REPLAYED,
                dimensions=_execution_telemetry_dimensions(
                    execution, callback_retry=True
                ),
            )
            return execution
        raise SummaryExecutionConflictError(_("Conflicting Summary result replay."))
    if execution.status != SummaryExecution.Status.DISPATCHED:
        raise SummaryExecutionConflictError(_("Summary execution is not awaiting a result."))

    execution.completed_at = timezone_now()
    execution.result_hash = result_hash
    if citation_violation:
        execution.status = SummaryExecution.Status.FAILED
        execution.failure_code = "citation_boundary_violation"
        execution.result = {}
    else:
        execution.status = str(canonical_result["status"])
        execution.failure_code = str(canonical_result["failure_code"])
        execution.result = canonical_result
    execution.save(
        update_fields=[
            "status",
            "failure_code",
            "result",
            "result_hash",
            "completed_at",
        ]
    )
    dispatched_at = execution.dispatched_at
    elapsed_ms = (
        (execution.completed_at - dispatched_at).total_seconds() * 1000
        if dispatched_at is not None
        else 0
    )
    outcome = (
        HoverTelemetryOutcome.CONTRACT_REJECTED
        if citation_violation
        else HoverTelemetryOutcome.SUCCESS
        if execution.status == SummaryExecution.Status.SUCCEEDED
        else HoverTelemetryOutcome.EMPTY
        if execution.status == SummaryExecution.Status.NO_CHANGE
        else HoverTelemetryOutcome.PERMANENT_FAILURE
    )
    emit_hover_telemetry_on_commit(
        HoverTelemetryEvent.SUMMARY_EXECUTION,
        outcome,
        dimensions=_execution_telemetry_dimensions(
            execution,
            duration_bucket=duration_bucket(elapsed_ms),
            citation_rejected=citation_violation,
        ),
    )
    ModuleInstallationTrigger.objects.filter(
        installation=execution.installation,
        supported_trigger__kind=ModuleSupportedTrigger.Kind.SCHEDULE,
    ).update(lease_expires_at=None)
    return execution


def _summary_sender(execution: SummaryExecution) -> UserProfile:
    installation = execution.installation
    sender = installation.configured_by
    if (
        sender is not None
        and sender.is_active
        and installation.summary_stream_id is not None
        and subscribed_to_stream(sender, installation.summary_stream_id)
    ):
        return sender
    assert installation.summary_stream is not None
    fallback = (
        UserProfile.objects.filter(
            realm=installation.realm,
            is_active=True,
            is_bot=False,
            subscription__recipient=installation.summary_stream.recipient,
            subscription__active=True,
        )
        .order_by("id")
        .first()
    )
    if fallback is None:
        raise JsonableError(_("This Summary has no active publisher."))
    return fallback


def _render_summary(execution: SummaryExecution) -> str:
    if execution.status == SummaryExecution.Status.NO_CHANGE:
        return "## No meaningful changes\n\nNo meaningful changes were found in this interval."
    digest = execution.result.get("digest")
    if not isinstance(digest, dict):
        raise JsonableError(_("This Summary has no publishable result."))
    sections = [f"## {digest['title']}", str(digest["main_thread"])]
    for heading, key in [
        ("What changed", "what_changed"),
        ("Confirmed facts", "confirmed_facts"),
        ("Still unresolved", "unresolved_points"),
    ]:
        values = digest[key]
        if isinstance(values, list) and values:
            sections.append(f"### {heading}\n" + "\n".join(f"- {value}" for value in values))
    sections.append(f"### Why it matters\n{digest['why_it_matters']}")
    edition = (
        "Manual edition"
        if execution.kind == SummaryExecution.Kind.MANUAL
        else "Scheduled edition"
    )
    sections.append(
        f"_{edition} · {execution.window_start.isoformat()} → {execution.window_end.isoformat()}_"
    )
    return "\n\n".join(sections)


@transaction.atomic(durable=True)
def do_publish_summary_execution(
    *, execution: SummaryExecution, acting_user: UserProfile | None = None
) -> SummaryExecution:
    current = (
        SummaryExecution.objects.select_for_update(of=("self",))
        .select_related(
            "installation__realm",
            "installation__space__stream",
            "installation__summary_stream",
            "installation__version",
            "requester",
            "published_item",
        )
        .prefetch_related("input_snapshots", "message_snapshots")
        .get(id=execution.id)
    )
    if current.status == SummaryExecution.Status.PUBLISHED:
        return current
    if current.kind == SummaryExecution.Kind.MANUAL:
        if acting_user is None or current.requester_id != acting_user.id:
            raise JsonableError(_("You do not have permission to publish this preview."))
        _assert_manual_access(acting_user, current.installation)
        for item in current.input_snapshots.all():
            access_stream_by_id(acting_user, item.stream_id)
            source_attachment = item.source_attachment
            if (
                source_attachment is not None
                and source_attachment.state != SpaceAttachment.State.ACTIVE
            ):
                raise JsonableError(_("A generation-time Summary input is no longer available."))
        if current.status != SummaryExecution.Status.SUCCEEDED:
            raise JsonableError(_("This preview has no publishable result."))
    elif current.status not in {
        SummaryExecution.Status.SUCCEEDED,
        SummaryExecution.Status.NO_CHANGE,
    }:
        raise JsonableError(_("This scheduled Summary has no publishable result."))
    installation = current.installation
    if installation.state != ModuleInstallation.State.ENABLED or installation.summary_stream is None:
        raise JsonableError(_("This Summary is not active."))

    sender = _summary_sender(current)
    message_id = internal_send_stream_message(
        sender=sender,
        stream=installation.summary_stream,
        topic_name=installation.label,
        content=_render_summary(current),
        acting_user=sender,
    )
    if message_id is None:
        raise JsonableError(_("The Summary message could not be created."))
    message = Message.objects.get(id=message_id, realm=installation.realm)
    generated_item = GeneratedItem.objects.create(
        realm=installation.realm,
        message=message,
        installation=installation,
        publication_id=str(current.id),
        idempotency_key=str(current.id),
        publication_envelope_hash=current.result_hash,
        business_identity=f"summary:{installation.id}",
        output_type=GeneratedItem.OutputType.DIGEST,
        module_key=installation.version.definition.stable_key,
        module_name=installation.label,
        module_version=installation.version.version,
        source_summary=f"From {current.input_snapshots.count()} Summary inputs",
        payload=current.result,
        reviewed_payload=current.result,
        run_reference=str(current.id),
        covered_start_at=current.window_start,
        covered_end_at=current.window_end,
        generated_at=current.completed_at,
        published_at=timezone_now(),
        material_change=current.status == SummaryExecution.Status.SUCCEEDED,
    )
    execution_inputs = list(current.input_snapshots.all())
    GeneratedInputSnapshot.objects.bulk_create(
        [
            GeneratedInputSnapshot(
                generated_item=generated_item,
                stream=snapshot.stream,
                topic_name=snapshot.topic_name,
                kind=snapshot.kind,
                source_attachment=snapshot.source_attachment,
                provider_name=snapshot.provider_name,
                position=snapshot.position,
            )
            for snapshot in execution_inputs
        ]
    )
    cited_tokens = set(current.result.get("evidence_tokens", []))
    cited_messages = [
        snapshot
        for snapshot in current.message_snapshots.all()
        if snapshot.citation_token in cited_tokens
    ]
    links = [
        EvidenceLink(
            generated_item=generated_item,
            realm=installation.realm,
            citation_message=snapshot.message,
            position=position,
            provider_key="",
            provider_name="",
            display_name="",
        )
        for position, snapshot in enumerate(cited_messages)
    ]
    for link in links:
        link.full_clean()
    EvidenceLink.objects.bulk_create(links)
    current.published_item = generated_item
    current.status = SummaryExecution.Status.PUBLISHED
    current.published_at = generated_item.published_at
    current.save(update_fields=["published_item", "status", "published_at"])
    emit_hover_telemetry_on_commit(
        HoverTelemetryEvent.SUMMARY_EXECUTION,
        HoverTelemetryOutcome.SUCCESS,
        dimensions=_execution_telemetry_dimensions(current, published=True),
    )
    if current.kind == SummaryExecution.Kind.SCHEDULED:
        ModuleInstallationTrigger.objects.filter(
            installation=installation,
            supported_trigger__kind=ModuleSupportedTrigger.Kind.SCHEDULE,
        ).update(lease_expires_at=None)
    return current


def execution_data(execution: SummaryExecution) -> dict[str, object]:
    published_item = execution.published_item
    return {
        "id": str(execution.id),
        "kind": execution.kind,
        "status": execution.status,
        "window_start": execution.window_start.isoformat(),
        "window_end": execution.window_end.isoformat(),
        "policy_revision": execution.policy_revision,
        "uses_previous_settings": execution.policy_revision != execution.installation.policy_revision,
        "eligible_message_count": execution.eligible_message_count,
        "snapshot_message_count": execution.snapshot_message_count,
        "failure_code": execution.failure_code,
        "result": execution.result if execution.status == SummaryExecution.Status.SUCCEEDED else {},
        "published_message_id": published_item.message_id if published_item is not None else None,
        "can_publish": (
            execution.kind == SummaryExecution.Kind.MANUAL
            and execution.status == SummaryExecution.Status.SUCCEEDED
        ),
    }


def access_summary_execution(
    *, user: UserProfile, installation: ModuleInstallation, execution_id: str
) -> SummaryExecution:
    _assert_manual_access(user, installation)
    try:
        return SummaryExecution.objects.select_related(
            "installation", "published_item"
        ).get(id=execution_id, installation=installation, requester=user)
    except (SummaryExecution.DoesNotExist, ValueError):
        raise JsonableError(_("Invalid Summary execution."))


def prepare_due_summary_executions(
    *, at: datetime | None = None, limit: int = 100
) -> list[SummaryDispatch]:
    """Claim at most one chronological missed occurrence per Summary."""
    now = at or timezone_now()
    due_ids = list(
        ModuleInstallationTrigger.objects.filter(
            supported_trigger__kind=ModuleSupportedTrigger.Kind.SCHEDULE,
            installation__state=ModuleInstallation.State.ENABLED,
            installation__summary_stream__isnull=False,
            interval_seconds__isnull=False,
            next_due_at__lte=now,
        )
        .filter(Q(lease_expires_at__isnull=True) | Q(lease_expires_at__lte=now))
        .order_by("next_due_at", "id")
        .values_list("id", flat=True)[:limit]
    )
    dispatches: list[SummaryDispatch] = []
    for trigger_id in due_ids:
        with transaction.atomic():
            trigger = (
                ModuleInstallationTrigger.objects.select_for_update(skip_locked=True)
                .select_related("installation")
                .filter(id=trigger_id, next_due_at__lte=now)
                .first()
            )
            if (
                trigger is None
                or trigger.interval_seconds is None
                or trigger.next_due_at is None
                or (
                    trigger.lease_expires_at is not None and trigger.lease_expires_at > now
                )
                or SummaryExecution.objects.filter(
                    installation=trigger.installation,
                    kind=SummaryExecution.Kind.SCHEDULED,
                    status__in=[
                        SummaryExecution.Status.PENDING,
                        SummaryExecution.Status.DISPATCHED,
                    ],
                ).exists()
            ):
                continue
            scheduled_for = trigger.next_due_at
            interval = timedelta(seconds=trigger.interval_seconds)
            trigger.lease_expires_at = now + timedelta(minutes=15)
            trigger.next_due_at = scheduled_for + interval
            trigger.save(update_fields=["lease_expires_at", "next_due_at"])
            emit_hover_telemetry_on_commit(
                HoverTelemetryEvent.SUMMARY_SCHEDULER,
                HoverTelemetryOutcome.REQUESTED,
                dimensions={
                    "realm_id": trigger.installation.realm_id,
                    "installation_id": trigger.installation_id,
                    "lag_bucket": lag_bucket((now - scheduled_for).total_seconds()),
                },
            )
        try:
            dispatch = do_prepare_summary_execution(
                installation=trigger.installation,
                kind=SummaryExecution.Kind.SCHEDULED,
                window_start=scheduled_for - interval,
                window_end=scheduled_for,
                scheduled_for=scheduled_for,
            )
        except (IntegrityError, SummaryExecutionConflictError):
            continue
        dispatches.append(dispatch)
    return dispatches


@transaction.atomic(durable=True)
def retry_stale_scheduled_dispatch(execution: SummaryExecution) -> SummaryDispatch:
    current = (
        SummaryExecution.objects.select_for_update()
        .select_related("installation__version")
        .prefetch_related("input_snapshots", "message_snapshots__input")
        .get(id=execution.id)
    )
    if (
        current.kind != SummaryExecution.Kind.SCHEDULED
        or current.status != SummaryExecution.Status.DISPATCHED
    ):
        return SummaryDispatch(current, None, None)
    operation = _operation_for_execution(current)
    token = _callback_token()
    current.callback_token_hash = _callback_token_hash(token)
    current.dispatched_at = timezone_now()
    current.save(update_fields=["callback_token_hash", "dispatched_at"])
    return SummaryDispatch(current, operation, token)


def retry_stale_scheduled_dispatches(
    *, at: datetime | None = None, limit: int = 100
) -> list[SummaryDispatch]:
    now = at or timezone_now()
    stale = SummaryExecution.objects.filter(
        kind=SummaryExecution.Kind.SCHEDULED,
        status=SummaryExecution.Status.DISPATCHED,
        dispatched_at__lte=now - timedelta(minutes=15),
    ).order_by("dispatched_at", "id")[:limit]
    return [retry_stale_scheduled_dispatch(execution) for execution in stale]
