from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from django.db import transaction
from django.db.models import QuerySet
from django.utils import timezone
from django.utils.translation import gettext as _

from hover.models import Space, SpaceMembership, SuggestedActionTransition, Todo, TodoEvent
from zerver.actions.message_send import internal_send_stream_message
from zerver.lib.exceptions import JsonableError
from zerver.models import Message, UserProfile
from zerver.tornado.django_api import send_event_on_commit

TodoOperation = Literal["assign", "complete", "reopen"]


class TodoConflictError(JsonableError):
    data_fields = ["todo"]
    http_status_code = 409

    def __init__(self, todo: Todo) -> None:
        super().__init__(_("This Todo has changed. Review its current state."))
        self.todo = todo_data(todo)


@dataclass(frozen=True)
class TodoMutationResult:
    changed: bool
    todo: Todo


def _eligible_members(space: Space) -> QuerySet[UserProfile]:
    return (
        UserProfile.objects.filter(
            hover_space_memberships__space=space,
            realm=space.realm,
            is_active=True,
            is_bot=False,
            is_mirror_dummy=False,
        )
        .exclude(role=UserProfile.ROLE_GUEST)
        .distinct()
        .order_by("full_name", "id")
    )


def _active_member_ids(space: Space) -> list[int]:
    return list(_eligible_members(space).values_list("id", flat=True))


def authorized_todos(user: UserProfile) -> QuerySet[Todo]:
    if not user.is_active or user.is_guest or user.is_bot:
        return Todo.objects.none()
    return (
        Todo.objects.filter(
            realm=user.realm,
            space__state=Space.State.LAUNCHED,
            space__memberships__user=user,
        )
        .select_related(
            "space",
            "suggested_action__generated_item__message",
            "assignee",
            "created_by",
        )
        .distinct()
        .order_by("state", "due_date", "date_created", "id")
    )


def _person_data(user: UserProfile | None) -> dict[str, object] | None:
    if user is None:
        return None
    return {"user_id": user.id, "full_name": user.full_name}


def todo_data(todo: Todo) -> dict[str, object]:
    item = todo.suggested_action.generated_item
    events = list(
        todo.events.select_related(
            "actor", "previous_assignee", "new_assignee", "notification_message", "transition"
        ).order_by("-version")[:10]
    )
    approval_event = (
        todo.events.filter(kind=TodoEvent.Kind.APPROVED)
        .select_related("actor", "transition")
        .first()
    )
    evidence_count = item.evidence_links.count()
    return {
        "id": todo.id,
        "state": todo.state,
        "version": todo.version,
        "wording": todo.wording,
        "due_date": todo.due_date.isoformat() if todo.due_date is not None else None,
        "completed_at": todo.completed_at.isoformat() if todo.completed_at is not None else None,
        "assignee": _person_data(todo.assignee),
        "space": {"id": todo.space_id, "name": todo.space.name},
        "generated_item": {
            "id": item.id,
            "message_id": item.message_id,
            "evidence_count": evidence_count,
            "evidence_url": (
                f"/json/hover/spaces/{todo.space_id}/generated-items/{item.id}/evidence"
                if evidence_count > 0
                else None
            ),
        },
        "approval": (
            {
                "transition_id": approval_event.transition_id,
                "actor": _person_data(approval_event.actor),
                "occurred_at": approval_event.date_created.isoformat(),
            }
            if approval_event is not None
            else None
        ),
        "assignable_users": [_person_data(member) for member in _eligible_members(todo.space)],
        "history_count": todo.events.count(),
        "recent_events": [
            {
                "id": event.id,
                "kind": event.kind,
                "actor": _person_data(event.actor),
                "occurred_at": event.date_created.isoformat(),
                "previous_state": event.previous_state,
                "new_state": event.new_state,
                "previous_assignee": _person_data(event.previous_assignee),
                "new_assignee": _person_data(event.new_assignee),
                "reason": event.reason,
                "notification_message_id": event.notification_message_id,
            }
            for event in events
        ],
    }


def _notification_message(
    *, todo: Todo, recipient: UserProfile, actor: UserProfile, kind: str
) -> Message:
    stream = todo.space.stream
    assert stream is not None
    mention = f"@**{recipient.full_name}|{recipient.id}**"
    if kind in {TodoEvent.Kind.ASSIGNED, TodoEvent.Kind.REASSIGNED, TodoEvent.Kind.APPROVED}:
        content = f"**Todo assigned**\n\n{mention}, you are assigned: {todo.wording}"
    else:
        content = f"**Todo completed**\n\n{mention}, {actor.full_name} completed: {todo.wording}"
    message_id = internal_send_stream_message(
        sender=todo.suggested_action.generated_item.message.sender,
        stream=stream,
        topic_name=todo.suggested_action.generated_item.message.topic_name(),
        content=content,
        acting_user=todo.suggested_action.generated_item.message.sender,
    )
    if message_id is None:
        raise JsonableError(_("The Todo notification could not be sent."))
    return Message.objects.get(id=message_id, realm=todo.realm)


def send_todo_projection_event(todo: Todo) -> None:
    send_event_on_commit(
        todo.realm,
        {
            "type": "hover_todo",
            "message_id": todo.suggested_action.generated_item.message_id,
            "todo": todo_data(todo),
        },
        _active_member_ids(todo.space),
    )


def record_todo_approval(
    *, todo: Todo, transition: SuggestedActionTransition, actor: UserProfile
) -> TodoEvent:
    notification = None
    if todo.assignee is not None:
        notification = _notification_message(
            todo=todo,
            recipient=todo.assignee,
            actor=actor,
            kind=TodoEvent.Kind.APPROVED,
        )
    event = TodoEvent.objects.create(
        realm=todo.realm,
        todo=todo,
        transition=transition,
        request_id=transition.request_id,
        kind=TodoEvent.Kind.APPROVED,
        actor=actor,
        previous_state="",
        new_state=Todo.State.ACTIVE,
        previous_assignee=None,
        new_assignee=todo.assignee,
        notification_message=notification,
        version=todo.version,
    )
    send_todo_projection_event(todo)
    return event


@transaction.atomic(durable=True)
def mutate_todo(
    *,
    acting_user: UserProfile,
    space_id: int,
    todo_id: int,
    operation: TodoOperation,
    request_id: UUID,
    expected_version: int,
    assignee_user_id: int | None,
    reason: str | None,
) -> TodoMutationResult:
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
        raise JsonableError(_("Invalid Todo ID"))
    try:
        todo = (
            Todo.objects.select_for_update(no_key=True, of=("self",))
            .select_related(
                "realm",
                "space__stream",
                "suggested_action__generated_item__message",
                "assignee",
            )
            .get(id=todo_id, realm=acting_user.realm, space_id=space_id)
        )
    except Todo.DoesNotExist:
        raise JsonableError(_("Invalid Todo ID"))

    if todo.events.filter(request_id=request_id).exists():
        return TodoMutationResult(changed=False, todo=todo)
    if expected_version != todo.version:
        raise TodoConflictError(todo)

    normalized_reason = " ".join((reason or "").split())
    if len(normalized_reason) > 1000:
        raise JsonableError(_("The reason must be 1000 characters or fewer."))

    before_state = todo.state
    before_assignee = todo.assignee
    notification_recipient = None
    now = timezone.now()
    if operation == "assign":
        if todo.state != Todo.State.ACTIVE or assignee_user_id is None:
            raise TodoConflictError(todo)
        assignee = _eligible_members(todo.space).filter(id=assignee_user_id).first()
        if assignee is None:
            raise JsonableError(_("The assignee must be a confirmed Space member."))
        # Reconfirming the current assignee is still an auditable assignment
        # command. Appending it reserves the request UUID, so replaying that UUID
        # after a later correction cannot unexpectedly restore the old assignee.
        kind = TodoEvent.Kind.ASSIGNED if todo.assignee_id is None else TodoEvent.Kind.REASSIGNED
        if todo.assignee_id != assignee.id:
            notification_recipient = assignee
        todo.assignee = assignee
    elif operation == "complete":
        if todo.state != Todo.State.ACTIVE or assignee_user_id is not None:
            raise TodoConflictError(todo)
        kind = TodoEvent.Kind.COMPLETED
        todo.state = Todo.State.COMPLETED
        todo.completed_at = now
        if todo.assignee_id is not None and todo.assignee_id != acting_user.id:
            notification_recipient = todo.assignee
    else:
        if todo.state != Todo.State.COMPLETED or assignee_user_id is not None:
            raise TodoConflictError(todo)
        kind = TodoEvent.Kind.REOPENED
        todo.state = Todo.State.ACTIVE
        todo.completed_at = None

    todo.version += 1
    todo.save(
        update_fields=["assignee", "state", "completed_at", "version", "date_updated"]
    )
    notification = None
    if notification_recipient is not None:
        notification = _notification_message(
            todo=todo,
            recipient=notification_recipient,
            actor=acting_user,
            kind=kind,
        )
    TodoEvent.objects.create(
        realm=todo.realm,
        todo=todo,
        request_id=request_id,
        kind=kind,
        actor=acting_user,
        previous_state=before_state,
        new_state=todo.state,
        previous_assignee=before_assignee,
        new_assignee=todo.assignee,
        reason=normalized_reason,
        notification_message=notification,
        version=todo.version,
    )
    send_todo_projection_event(todo)
    return TodoMutationResult(changed=True, todo=todo)
