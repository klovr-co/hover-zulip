from typing import Annotated, Literal
from uuid import UUID

from django.http import HttpRequest, HttpResponse
from pydantic import StringConstraints

from hover.actions_suggested_actions import decide_suggested_action, suggested_action_data
from zerver.decorator import require_non_guest_user
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import PathOnly, typed_endpoint
from zerver.models.users import UserProfile


@require_non_guest_user
@typed_endpoint
def decide_suggested_action_view(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    space_id: PathOnly[int],
    generated_item_id: PathOnly[int],
    decision: Literal["approve", "not_action", "restore"],
    request_id: Annotated[
        str,
        StringConstraints(
            pattern=r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$"
        ),
    ],
    expected_version: Annotated[str, StringConstraints(pattern=r"^[1-9][0-9]*$")],
    reason: Annotated[str, StringConstraints(max_length=1000)] | None = None,
) -> HttpResponse:
    result = decide_suggested_action(
        acting_user=user_profile,
        space_id=space_id,
        generated_item_id=generated_item_id,
        decision=decision,
        request_id=UUID(request_id),
        expected_version=int(expected_version),
        reason=reason,
    )
    return json_success(
        request,
        data={
            "changed": result.changed,
            "suggested_action": suggested_action_data(result.action),
        },
    )
