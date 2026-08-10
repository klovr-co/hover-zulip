from dataclasses import dataclass
from typing import Any, Literal

import orjson
from django.utils.translation import gettext as _

from hover.models import GeneratedItem, Response, Revision, SpaceMembership
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
            GeneratedItem.objects.select_for_update(no_key=True)
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

    if prepared.has_explicit_patch:
        assert prepared.field_path is not None
        current_payload = dict(generated_item.reviewed_payload or generated_item.payload)
        previous_value = current_payload[prepared.field_path]
        current_payload[prepared.field_path] = prepared.new_value
        generated_item.reviewed_payload = current_payload
        generated_item.save(update_fields=["reviewed_payload"])
        Revision.objects.create(
            realm=actor.realm,
            generated_item=generated_item,
            response=response,
            actor=actor,
            field_path=prepared.field_path,
            previous_value=previous_value,
            new_value=prepared.new_value,
            reason=message.content,
        )

    return response
