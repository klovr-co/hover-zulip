from datetime import datetime, time
from typing import Annotated, Literal

from django.http import HttpRequest, HttpResponse
from django.utils.translation import gettext as _
from pydantic import Json, StringConstraints

from hover.actions_modules import (
    do_disable_module,
    do_install_module,
    do_rebind_resume_module,
    do_upgrade_module,
    get_module_catalog,
    installation_data,
)
from hover.lib_spaces import (
    access_space_for_administration,
    get_space_data,
    space_projection_queryset,
)
from hover.models import ModuleInstallation
from zerver.decorator import require_non_guest_user
from zerver.lib.exceptions import JsonableError
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import PathOnly, typed_endpoint, typed_endpoint_without_parameters
from zerver.models.users import UserProfile


def _parse_local_time(value: str | None) -> time | None:
    if value is None:
        return None
    try:
        parsed = time.fromisoformat(value)
    except ValueError:
        raise JsonableError(_("Invalid scheduled local time."))
    if parsed.tzinfo is not None:
        raise JsonableError(_("Scheduled local time must not contain an offset."))
    return parsed


def _get_installation(user: UserProfile, installation_id: int) -> ModuleInstallation:
    try:
        installation = ModuleInstallation.objects.select_related("space").get(
            id=installation_id, realm=user.realm
        )
    except ModuleInstallation.DoesNotExist:
        raise JsonableError(_("Invalid Module installation."))
    access_space_for_administration(user, installation.space_id)
    return installation


@require_non_guest_user
@typed_endpoint_without_parameters
def list_module_catalog(request: HttpRequest, user_profile: UserProfile) -> HttpResponse:
    if not user_profile.realm.hover_enabled:
        raise JsonableError(_("Hover is not enabled for this organization."))
    return json_success(request, data={"modules": get_module_catalog(user_profile.realm)})


@require_non_guest_user
@typed_endpoint
def install_module(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    space_id: PathOnly[int],
    version_id: Json[int],
    attachment_ids: Json[list[int]],
    trigger_kind: Json[Literal["manual", "new_source", "schedule"]],
    activation_timezone: Annotated[str, StringConstraints(max_length=64)],
    cadence: Json[Literal["daily", "weekly"] | None] = None,
    local_time: Json[str | None] = None,
    debounce_seconds: Json[int | None] = None,
    backfill_start_at: Json[datetime | None] = None,
    backfill_confirmed: Json[bool] = False,
) -> HttpResponse:
    space = access_space_for_administration(user_profile, space_id)
    installation, created = do_install_module(
        acting_user=user_profile,
        space=space,
        version_id=version_id,
        attachment_ids=attachment_ids,
        trigger_kind=trigger_kind,
        activation_timezone=activation_timezone,
        cadence=cadence,
        local_time=_parse_local_time(local_time),
        debounce_seconds=debounce_seconds,
        backfill_start_at=backfill_start_at,
        backfill_confirmed=backfill_confirmed,
    )
    return json_success(
        request,
        data={
            "installation": installation_data(installation),
            "space": get_space_data(space_projection_queryset().get(id=space.id)),
            "created": created,
        },
    )


@require_non_guest_user
@typed_endpoint
def disable_module(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    installation_id: PathOnly[int],
) -> HttpResponse:
    installation, changed = do_disable_module(
        _get_installation(user_profile, installation_id), acting_user=user_profile
    )
    return json_success(
        request, data={"installation": installation_data(installation), "changed": changed}
    )


@require_non_guest_user
@typed_endpoint
def upgrade_module(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    installation_id: PathOnly[int],
    version_id: Json[int],
    attachment_ids: Json[list[int]],
    trigger_kind: Json[Literal["manual", "new_source", "schedule"]],
    activation_timezone: Annotated[str, StringConstraints(max_length=64)],
    cadence: Json[Literal["daily", "weekly"] | None] = None,
    local_time: Json[str | None] = None,
    debounce_seconds: Json[int | None] = None,
    backfill_start_at: Json[datetime | None] = None,
    backfill_confirmed: Json[bool] = False,
) -> HttpResponse:
    successor, created = do_upgrade_module(
        installation=_get_installation(user_profile, installation_id),
        acting_user=user_profile,
        version_id=version_id,
        attachment_ids=attachment_ids,
        trigger_kind=trigger_kind,
        activation_timezone=activation_timezone,
        cadence=cadence,
        local_time=_parse_local_time(local_time),
        debounce_seconds=debounce_seconds,
        backfill_start_at=backfill_start_at,
        backfill_confirmed=backfill_confirmed,
    )
    return json_success(
        request, data={"installation": installation_data(successor), "created": created}
    )


@require_non_guest_user
@typed_endpoint
def rebind_resume_module(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    installation_id: PathOnly[int],
    attachment_ids: Json[list[int]],
) -> HttpResponse:
    installation = do_rebind_resume_module(
        installation=_get_installation(user_profile, installation_id),
        acting_user=user_profile,
        attachment_ids=attachment_ids,
    )
    return json_success(request, data={"installation": installation_data(installation)})
