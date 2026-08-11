from django.http import HttpRequest, HttpResponse
from pydantic import Json

from hover.actions_integrations import (
    do_associate_integration_route,
    do_detach_integration_route,
    get_integration_route_data,
)
from hover.lib_spaces import access_space_by_id, get_space_data, space_projection_queryset
from zerver.decorator import require_non_guest_user
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import PathOnly, typed_endpoint
from zerver.models.users import UserProfile


@require_non_guest_user
@typed_endpoint
def associate_integration_route(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    space_id: PathOnly[int],
    attachment_id: Json[int],
    bot_user_id: Json[int],
) -> HttpResponse:
    space = access_space_by_id(user_profile, space_id)
    route, created = do_associate_integration_route(
        acting_user=user_profile,
        space=space,
        attachment_id=attachment_id,
        bot_user_id=bot_user_id,
    )
    projected_space = space_projection_queryset().get(id=space.id)
    return json_success(
        request,
        data={
            "integration_route": get_integration_route_data(route),
            "space": get_space_data(projected_space),
            "created": created,
        },
    )


@require_non_guest_user
@typed_endpoint
def detach_integration_route(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    space_id: PathOnly[int],
    route_id: PathOnly[int],
) -> HttpResponse:
    space = access_space_by_id(user_profile, space_id)
    route = do_detach_integration_route(acting_user=user_profile, space=space, route_id=route_id)
    projected_space = space_projection_queryset().get(id=space.id)
    return json_success(
        request,
        data={
            "integration_route": get_integration_route_data(route),
            "space": get_space_data(projected_space),
        },
    )
