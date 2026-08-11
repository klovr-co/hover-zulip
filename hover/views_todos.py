from typing import Annotated, Literal
from uuid import UUID

from django.http import HttpRequest, HttpResponse
from pydantic import StringConstraints

from hover.actions_todos import authorized_todos, mutate_todo, todo_data
from zerver.decorator import require_non_guest_user
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import PathOnly, typed_endpoint, typed_endpoint_without_parameters
from zerver.models.users import UserProfile


@require_non_guest_user
@typed_endpoint_without_parameters
def list_todos(request: HttpRequest, user_profile: UserProfile) -> HttpResponse:
    return json_success(
        request,
        data={"todos": [todo_data(todo) for todo in authorized_todos(user_profile)]},
    )


@require_non_guest_user
@typed_endpoint
def mutate_todo_view(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    space_id: PathOnly[int],
    todo_id: PathOnly[int],
    operation: Literal["assign", "complete", "reopen"],
    request_id: Annotated[
        str,
        StringConstraints(
            pattern=r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$"
        ),
    ],
    expected_version: Annotated[str, StringConstraints(pattern=r"^[1-9][0-9]*$")],
    assignee_user_id: Annotated[str, StringConstraints(pattern=r"^[1-9][0-9]*$")] | None = None,
    reason: Annotated[str, StringConstraints(max_length=1000)] | None = None,
) -> HttpResponse:
    result = mutate_todo(
        acting_user=user_profile,
        space_id=space_id,
        todo_id=todo_id,
        operation=operation,
        request_id=UUID(request_id),
        expected_version=int(expected_version),
        assignee_user_id=int(assignee_user_id) if assignee_user_id is not None else None,
        reason=reason,
    )
    return json_success(
        request,
        data={"changed": result.changed, "todo": todo_data(result.todo)},
    )
