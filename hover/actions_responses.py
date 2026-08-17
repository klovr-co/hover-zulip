from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Literal

import orjson
from django.utils.translation import gettext as _

from hover.actions_review_requests import resolve_matching_dispute
from hover.actions_suggested_actions import sync_suggested_action_from_reviewed_payload
from hover.models import GeneratedItem, Response, Revision, SpaceMembership
from hover.telemetry import (
    HoverTelemetryEvent,
    HoverTelemetryOutcome,
    count_bucket,
    emit_hover_telemetry_on_commit,
)
from zerver.lib.exceptions import JsonableError
from zerver.models import Message, UserProfile

ResponseType = Literal["reply", "review"]


@dataclass
class PreparedResponse:
    generated_item: GeneratedItem
    response_type: ResponseType
    field_path: str | None
    new_value: Any
    has_explicit_patch: bool


def prepare_response(
    actor: UserProfile,
    *,
    generated_item_id: int,
    response_type: ResponseType,
    review_field: str | None,
    review_value: str | None,
) -> PreparedResponse:
    if actor.is_guest:
        raise JsonableError(_("You do not have permission to review this update."))
    try:
        generated_item = (
            GeneratedItem.objects.select_for_update(no_key=True, of=("self",))
            .select_related("attachment__space__stream", "message")
            .get(id=generated_item_id, realm=actor.realm, attachment__isnull=False)
        )
    except GeneratedItem.DoesNotExist:
        raise JsonableError(_("Invalid generated item ID"))

    assert generated_item.attachment is not None
    space = generated_item.attachment.space
    if (
        space.state != space.State.LAUNCHED
        or space.stream_id is None
        or space.stream is None
        or space.stream.deactivated
        or not SpaceMembership.objects.filter(
            space=space,
            user=actor,
            user__is_active=True,
        ).exists()
    ):
        raise JsonableError(_("Invalid generated item ID"))

    field_path = review_field.strip() if review_field is not None else ""
    has_explicit_patch = False
    new_value: Any = None
    current_payload = generated_item.reviewed_payload or generated_item.payload
    if response_type == "review" and field_path and review_value is not None:
        try:
            new_value = orjson.loads(review_value)
        except orjson.JSONDecodeError:
            pass
        else:
            # The first release deliberately accepts one existing top-level field.
            # That makes a Review deterministic and prevents typo-created state.
            has_explicit_patch = field_path in current_payload and "." not in field_path

    return PreparedResponse(
        generated_item=generated_item,
        response_type=response_type,
        field_path=field_path or None,
        new_value=new_value,
        has_explicit_patch=has_explicit_patch,
    )


def validate_response_destination(
    prepared: PreparedResponse,
    *,
    recipient_type_name: str,
    message_to: Sequence[int] | Sequence[str],
    topic_name: str | None,
) -> None:
    generated_item = prepared.generated_item
    assert generated_item.attachment is not None
    stream = generated_item.attachment.space.stream
    assert stream is not None
    if recipient_type_name != "stream" or len(message_to) != 1:
        raise JsonableError(_("Hover responses must be sent beneath their generated update."))
    stream_indicator = message_to[0]
    matches_stream = (
        stream_indicator == stream.id
        if isinstance(stream_indicator, int)
        else stream_indicator.casefold() == stream.name.casefold()
    )
    if not matches_stream or topic_name != generated_item.message.topic_name():
        raise JsonableError(_("Hover responses must be sent beneath their generated update."))


def create_response(
    prepared: PreparedResponse,
    *,
    message: Message,
    actor: UserProfile,
) -> Response:
    generated_item = prepared.generated_item
    if (
        message.sender_id != actor.id
        or message.realm_id != generated_item.realm_id
        or message.recipient_id != generated_item.message.recipient_id
        or message.topic_name() != generated_item.message.topic_name()
    ):
        raise JsonableError(_("Hover responses must be sent beneath their generated update."))

    clarification_required = prepared.response_type == "review" and not prepared.has_explicit_patch
    response = Response.objects.create(
        realm=actor.realm,
        generated_item=generated_item,
        message=message,
        response_type=prepared.response_type,
        clarification_required=clarification_required,
    )

    resolved_detail = None
    if prepared.has_explicit_patch:
        assert prepared.field_path is not None
        current_payload = dict(generated_item.reviewed_payload or generated_item.payload)
        previous_value = current_payload[prepared.field_path]
        current_payload[prepared.field_path] = prepared.new_value
        generated_item.reviewed_payload = current_payload
        generated_item.save(update_fields=["reviewed_payload"])
        revision = Revision.objects.create(
            realm=actor.realm,
            generated_item=generated_item,
            response=response,
            actor=actor,
            field_path=prepared.field_path,
            previous_value=previous_value,
            new_value=prepared.new_value,
            reason=message.content,
        )
        resolved_detail = resolve_matching_dispute(revision)
        sync_suggested_action_from_reviewed_payload(generated_item)

    if prepared.response_type == "review":
        assert generated_item.attachment is not None
        target_count = (
            resolved_detail.review_request.targets.count() if resolved_detail is not None else 0
        )
        emit_hover_telemetry_on_commit(
            HoverTelemetryEvent.REVIEW,
            (
                HoverTelemetryOutcome.SUCCESS
                if prepared.has_explicit_patch
                else HoverTelemetryOutcome.CLARIFICATION_REQUIRED
            ),
            dimensions={
                "realm_id": actor.realm_id,
                "space_id": generated_item.attachment.space_id,
                "material": resolved_detail is not None,
                "target_count_bucket": count_bucket(target_count),
            },
        )

    return response
