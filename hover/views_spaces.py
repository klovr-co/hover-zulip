from typing import Annotated, Literal

from django.http import HttpRequest, HttpResponse
from django.utils.translation import gettext as _
from pydantic import Json, StringConstraints

from hover.actions_memberships import do_confirm_space_member, do_remove_space_member
from hover.actions_spaces import (
    do_add_space_administrator,
    do_create_space,
    do_launch_space,
    do_remove_space_administrator,
)
from hover.lib_spaces import (
    access_space_by_id,
    access_space_for_administration,
    get_accessible_spaces,
    get_space_data,
    space_projection_queryset,
)
from hover.models import Space
from zerver.decorator import require_non_guest_user
from zerver.lib.exceptions import JsonableError
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import PathOnly, typed_endpoint, typed_endpoint_without_parameters
from zerver.models.channel_folders import ChannelFolder
from zerver.models.users import UserProfile, get_user_profile_by_id_in_realm


@require_non_guest_user
@typed_endpoint
def create_space(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    category_id: Json[int] | None = None,
    description: Annotated[str, StringConstraints(max_length=Space.MAX_DESCRIPTION_LENGTH)] = "",
    name: Annotated[str, StringConstraints(max_length=Space.MAX_NAME_LENGTH)],
) -> HttpResponse:
    category: ChannelFolder | None = None
    if category_id is not None:
        try:
            category = ChannelFolder.objects.get(id=category_id, realm=user_profile.realm)
        except ChannelFolder.DoesNotExist:
            raise JsonableError(_("Invalid Space category."))

    space = do_create_space(user_profile, name=name, description=description, category=category)
    return json_success(request, data={"space": get_space_data(space, viewer=user_profile)})


@require_non_guest_user
@typed_endpoint_without_parameters
def list_spaces(request: HttpRequest, user_profile: UserProfile) -> HttpResponse:
    return json_success(
        request,
        data={
            "spaces": [
                get_space_data(space, viewer=user_profile)
                for space in get_accessible_spaces(user_profile)
            ]
        },
    )


@require_non_guest_user
@typed_endpoint
def get_space(
    request: HttpRequest, user_profile: UserProfile, *, space_id: PathOnly[int]
) -> HttpResponse:
    space = access_space_by_id(user_profile, space_id)
    return json_success(request, data={"space": get_space_data(space, viewer=user_profile)})


@require_non_guest_user
@typed_endpoint
def add_space_administrator(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    space_id: PathOnly[int],
    user_id: Json[int],
) -> HttpResponse:
    space = access_space_for_administration(user_profile, space_id)
    try:
        target = get_user_profile_by_id_in_realm(user_id, user_profile.realm)
    except UserProfile.DoesNotExist:
        raise JsonableError(_("Invalid user ID"))
    do_add_space_administrator(space, target, acting_user=user_profile)
    return json_success(request)


@require_non_guest_user
@typed_endpoint
def remove_space_administrator(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    space_id: PathOnly[int],
    user_id: PathOnly[int],
) -> HttpResponse:
    space = access_space_for_administration(user_profile, space_id)
    try:
        target = get_user_profile_by_id_in_realm(user_id, user_profile.realm)
    except UserProfile.DoesNotExist:
        raise JsonableError(_("Invalid user ID"))
    do_remove_space_administrator(space, target, acting_user=user_profile)
    return json_success(request)


@require_non_guest_user
@typed_endpoint
def confirm_space_member(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    space_id: PathOnly[int],
    user_id: Json[int],
    role: Json[Literal["contributor", "subscriber"]],
) -> HttpResponse:
    space = access_space_for_administration(user_profile, space_id)
    try:
        target = get_user_profile_by_id_in_realm(user_id, user_profile.realm)
    except UserProfile.DoesNotExist:
        raise JsonableError(_("Invalid user ID"))
    do_confirm_space_member(space, target, role=role, acting_user=user_profile)
    updated_space = space_projection_queryset().get(id=space.id)
    return json_success(request, data={"space": get_space_data(updated_space, viewer=user_profile)})


@require_non_guest_user
@typed_endpoint
def remove_space_member(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    space_id: PathOnly[int],
    user_id: PathOnly[int],
) -> HttpResponse:
    space = access_space_for_administration(user_profile, space_id)
    try:
        target = get_user_profile_by_id_in_realm(user_id, user_profile.realm)
    except UserProfile.DoesNotExist:
        raise JsonableError(_("Invalid user ID"))
    do_remove_space_member(space, target, acting_user=user_profile)
    updated_space = space_projection_queryset().get(id=space.id)
    return json_success(request, data={"space": get_space_data(updated_space, viewer=user_profile)})


@require_non_guest_user
@typed_endpoint
def launch_space(
    request: HttpRequest, user_profile: UserProfile, *, space_id: PathOnly[int]
) -> HttpResponse:
    space = access_space_for_administration(user_profile, space_id)
    launched_space, created = do_launch_space(space, acting_user=user_profile)
    return json_success(
        request,
        data={
            "space": get_space_data(launched_space, viewer=user_profile),
            "created": created,
        },
    )
