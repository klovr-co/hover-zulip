from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from django.db import models, transaction
from django.utils.translation import gettext as _

from hover.models import (
    GeneratedItem,
    Space,
    SpaceMembership,
    SuggestedAction,
    SuggestedActionTransition,
    Todo,
)
from hover.publication_contracts import SuggestedActionPayload
from zerver.lib.exceptions import JsonableError
from zerver.models.users import UserProfile
from zerver.tornado.django_api import send_event_on_commit

Decision = Literal["approve", "not_action", "restore"]


class SuggestedActionConflictError(JsonableError):
    data_fields = ["suggested_action"]
    http_status_code = 409

    def __init__(self, action: SuggestedAction) -> None:
        super().__init__(_("This Suggested Action has changed. Review its current state."))
        self.suggested_action = suggested_action_data(action)


@dataclass(frozen=True)
class SuggestedActionDecisionResult:
    changed: bool
    action: SuggestedAction


def _proposal(payload: object) -> SuggestedActionPayload:
    try:
        return SuggestedActionPayload.model_validate(payload)
    except ValueError:
        raise JsonableError(_("This Suggested Action no longer has a valid proposal."))


def create_suggested_action_for_generated_item(
    generated_item: GeneratedItem, payload: SuggestedActionPayload
) -> SuggestedAction:
    if generated_item.attachment is None:
        raise ValueError("Suggested Action publications require a Space attachment")
    proposed = payload.proposed_assignee
    return SuggestedAction.objects.create(
        realm=generated_item.realm,
        space=generated_item.attachment.space,
        generated_item=generated_item,
        wording=payload.wording,
        proposed_assignee_ref=proposed.ref if proposed is not None else "",
        proposed_assignee_display_name=proposed.display_name if proposed is not None else "",
        due_date=payload.proposed_due_date,
    )


def sync_suggested_action_from_reviewed_payload(generated_item: GeneratedItem) -> None:
    """Keep promoted current values aligned with an applied H14 Review."""
    try:
        action = SuggestedAction.objects.select_for_update(no_key=True).get(
            generated_item=generated_item
        )
    except SuggestedAction.DoesNotExist:
        return
    proposal = _proposal(generated_item.reviewed_payload or generated_item.payload)
    action.wording = proposal.wording
    action.due_date = proposal.proposed_due_date
    action.version += 1
    action.save(update_fields=["wording", "due_date", "version", "date_updated"])


def suggested_action_data(action: SuggestedAction) -> dict[str, object]:
    transitions = list(
        action.transitions.select_related("actor").order_by("-date_created", "-id")[:5]
    )
    try:
        todo = action.todo
    except Todo.DoesNotExist:
        todo_data = None
    else:
        from hover.actions_todos import todo_data as serialize_todo

        todo_data = serialize_todo(todo)
    assignee = action.assignee
    return {
        "id": action.id,
        "state": action.state,
        "version": action.version,
        "wording": action.wording,
        "source_proposal": {
            "assignee_ref": action.proposed_assignee_ref or None,
            "assignee_display_name": action.proposed_assignee_display_name or None,
        },
        "assignee": (
            {"user_id": assignee.id, "full_name": assignee.full_name}
            if assignee is not None
            else None
        ),
        "due_date": action.due_date.isoformat() if action.due_date is not None else None,
        "history_count": action.transitions.count(),
        "recent_transitions": [
            {
                "id": transition.id,
                "kind": transition.kind,
                "from_state": transition.from_state,
                "to_state": transition.to_state,
                "actor_id": transition.actor_id,
                "actor_name": transition.actor.full_name,
                "occurred_at": transition.date_created.isoformat(),
                "reason": transition.reason,
            }
            for transition in transitions
        ],
        "todo": todo_data,
    }


def _active_member_ids(space: Space) -> list[int]:
    return list(
        SpaceMembership.objects.filter(
            space=space,
            user__is_active=True,
            user__is_bot=False,
        )
        .exclude(user__role=UserProfile.ROLE_GUEST)
        .values_list("user_id", flat=True)
    )


def send_suggested_action_projection_event(action: SuggestedAction) -> None:
    from hover.lib import add_hover_metadata

    message = {"id": action.generated_item.message_id}
    add_hover_metadata([message], realm_id=action.realm_id, include_suggested_actions=True)
    generated_item = message.get("hover_generated_item")
    if generated_item is None:
        return
    send_event_on_commit(
        action.realm,
        {
            "type": "hover_suggested_action",
            "message_id": action.generated_item.message_id,
            "generated_item": generated_item,
        },
        _active_member_ids(action.space),
    )


@transaction.atomic(durable=True)
def decide_suggested_action(
    *,
    acting_user: UserProfile,
    space_id: int,
    generated_item_id: int,
    decision: Decision,
    request_id: UUID,
    expected_version: int,
    reason: str | None,
) -> SuggestedActionDecisionResult:
    if (
        not acting_user.is_active
        or acting_user.is_guest
        or acting_user.is_bot
        or not SpaceMembership.objects.filter(
            realm=acting_user.realm,
            space_id=space_id,
            user=acting_user,
            space__state=Space.State.LAUNCHED,
        ).exists()
    ):
        raise JsonableError(_("Invalid generated item ID"))
    try:
        action = (
            SuggestedAction.objects.select_for_update(no_key=True, of=("self",))
            .select_related(
                "realm",
                "space__stream",
                "generated_item__message",
                "generated_item__attachment",
                "assignee",
            )
            .get(
                realm=acting_user.realm,
                space_id=space_id,
                generated_item_id=generated_item_id,
                generated_item__attachment__space_id=space_id,
                generated_item__message__recipient_id=models.F("space__stream__recipient_id"),
            )
        )
    except SuggestedAction.DoesNotExist:
        raise JsonableError(_("Invalid generated item ID"))

    replay = action.transitions.filter(request_id=request_id).first()
    if replay is not None:
        return SuggestedActionDecisionResult(changed=False, action=action)
    if expected_version != action.version:
        raise SuggestedActionConflictError(action)

    legal: dict[tuple[str, str], str] = {
        (SuggestedAction.State.PENDING, "approve"): SuggestedAction.State.APPROVED,
        (SuggestedAction.State.PENDING, "not_action"): SuggestedAction.State.NOT_ACTION,
        (SuggestedAction.State.NOT_ACTION, "restore"): SuggestedAction.State.PENDING,
    }
    to_state = legal.get((action.state, decision))
    if to_state is None:
        raise SuggestedActionConflictError(action)

    normalized_reason = " ".join((reason or "").split())
    if len(normalized_reason) > 1000:
        raise JsonableError(_("The reason must be 1000 characters or fewer."))
    if decision != "not_action" and normalized_reason:
        raise JsonableError(_("A reason is only accepted for Not an action."))

    before_wording = action.wording
    before_assignee_id = action.assignee_id
    before_due_date = action.due_date
    todo = None
    if decision == "approve":
        # Revalidate the reviewed contract under the same action lock. It is the
        # approval source; the immutable publication remains untouched.
        proposal = _proposal(
            action.generated_item.reviewed_payload or action.generated_item.payload
        )
        action.wording = proposal.wording
        action.due_date = proposal.proposed_due_date
        todo = Todo.objects.create(
            realm=action.realm,
            space=action.space,
            suggested_action=action,
            wording=action.wording,
            assignee=action.assignee,
            due_date=action.due_date,
            created_by=acting_user,
        )

    from_state = action.state
    action.state = to_state
    action.version += 1
    action.save(update_fields=["state", "wording", "due_date", "version", "date_updated"])
    transition = SuggestedActionTransition.objects.create(
        realm=action.realm,
        action=action,
        request_id=request_id,
        kind=decision,
        from_state=from_state,
        to_state=to_state,
        actor=acting_user,
        reason=normalized_reason,
        before_wording=before_wording,
        after_wording=action.wording,
        before_assignee_id=before_assignee_id,
        after_assignee_id=action.assignee_id,
        before_due_date=before_due_date,
        after_due_date=action.due_date,
        todo=todo,
    )
    if todo is not None:
        from hover.actions_todos import record_todo_approval

        record_todo_approval(todo=todo, transition=transition, actor=acting_user)
    send_suggested_action_projection_event(action)
    return SuggestedActionDecisionResult(changed=True, action=action)
