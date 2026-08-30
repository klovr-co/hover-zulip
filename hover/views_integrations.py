from typing import Annotated, Literal

from django.http import HttpRequest, HttpResponse
from pydantic import Json, StringConstraints

from hover.actions_integrations import (
    do_associate_integration_route,
    do_detach_integration_route,
    do_provision_native_source,
    do_rotate_native_source_webhook,
    get_integration_route_data,
)
from hover.lib_spaces import access_space_by_id, get_space_data, space_projection_queryset
from zerver.decorator import require_non_guest_user
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import PathOnly, typed_endpoint
from zerver.models.users import UserProfile


@require_non_guest_user
@typed_endpoint
def provision_native_source(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    space_id: PathOnly[int],
    provider_key: Json[Literal["github", "posthog"]],
    display_name: Json[
        Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
    ],
) -> HttpResponse:
    space = access_space_by_id(user_profile, space_id)
    provisioned = do_provision_native_source(
        acting_user=user_profile,
        space=space,
        provider_key=provider_key,
        display_name=display_name,
    )
    projected_space = space_projection_queryset().get(id=space.id)
    return json_success(
        request,
        data={
            "space": get_space_data(projected_space, viewer=user_profile),
            "attachment_id": provisioned.attachment.id,
            "provider_key": provider_key,
            "webhook_url": provisioned.webhook_url,
        },
    )


@require_non_guest_user
@typed_endpoint
def rotate_native_source_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    space_id: PathOnly[int],
    attachment_id: PathOnly[int],
) -> HttpResponse:
    space = access_space_by_id(user_profile, space_id)
    webhook_url = do_rotate_native_source_webhook(
        acting_user=user_profile,
        space=space,
        attachment_id=attachment_id,
    )
    return json_success(request, data={"webhook_url": webhook_url})


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
            "space": get_space_data(projected_space, viewer=user_profile),
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
            "space": get_space_data(projected_space, viewer=user_profile),
        },
    )
