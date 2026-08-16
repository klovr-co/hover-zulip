from datetime import datetime, time
from typing import Annotated, Any, Literal

from django.http import HttpRequest, HttpResponse
from django.utils.translation import gettext as _
from pydantic import BaseModel, Field, Json, StringConstraints

from hover.actions_modules import (
    do_disable_module,
    do_install_module,
    do_rebind_resume_module,
    do_upgrade_module,
    get_module_catalog,
    installation_data,
)
from hover.actions_pipeline_library import (
    ModuleDraftSpec,
    ModuleRequirementSpec,
    do_add_module_draft_collaborator,
    do_archive_module_definition,
    do_archive_module_version,
    do_create_module_draft,
    do_create_successor_draft,
    do_grant_pipeline_creator,
    do_publish_module_draft,
    do_remove_module_draft_collaborator,
    do_revoke_pipeline_creator,
    do_update_module_draft,
    draft_data,
    get_pipeline_library_data,
    public_definition_data,
    public_version_data,
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
from zerver.models.users import UserProfile, get_user_profile_by_id_in_realm


class ModuleRequirementInput(BaseModel):
    key: str
    capability: str
    minimum_count: int = Field(ge=1, le=100)
    maximum_count: int = Field(ge=1, le=100)


def _draft_spec(
    *,
    stable_key: str,
    version: str,
    name: str,
    description: str,
    output_type: str,
    runtime_key: str,
    prompt_key: str,
    destination_topic: str,
    navigation_icon: str,
    navigation_order: int,
    input_contract: dict[str, Any],
    lookback_days: int,
    integration_keys: list[str],
    output_template: dict[str, Any],
    maximum_runtime_seconds: int,
    requirements: list[ModuleRequirementInput],
    supported_triggers: list[str],
) -> ModuleDraftSpec:
    return ModuleDraftSpec(
        stable_key=stable_key,
        version=version,
        name=name,
        description=description,
        output_type=output_type,
        runtime_key=runtime_key,
        prompt_key=prompt_key,
        destination_topic=destination_topic,
        navigation_icon=navigation_icon,
        navigation_order=navigation_order,
        input_contract=input_contract,
        lookback_seconds=lookback_days * 24 * 60 * 60,
        integration_keys=integration_keys,
        output_template=output_template,
        maximum_runtime_seconds=maximum_runtime_seconds,
        requirements=[
            ModuleRequirementSpec(
                key=item.key,
                capability=item.capability,
                minimum_count=item.minimum_count,
                maximum_count=item.maximum_count,
            )
            for item in requirements
        ],
        supported_triggers=supported_triggers,
    )


def _target_user(user_profile: UserProfile, user_id: int) -> UserProfile:
    try:
        return get_user_profile_by_id_in_realm(user_id, user_profile.realm)
    except UserProfile.DoesNotExist:
        raise JsonableError(_("Invalid user ID"))


def _library_result(user_profile: UserProfile, **metadata: object) -> dict[str, object]:
    return {**get_pipeline_library_data(user_profile), **metadata}


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
def get_pipeline_library(request: HttpRequest, user_profile: UserProfile) -> HttpResponse:
    return json_success(request, data=get_pipeline_library_data(user_profile))


@require_non_guest_user
@typed_endpoint
def grant_pipeline_creator(
    request: HttpRequest, user_profile: UserProfile, *, user_id: Json[int]
) -> HttpResponse:
    _assignment, changed = do_grant_pipeline_creator(
        acting_user=user_profile, target=_target_user(user_profile, user_id)
    )
    return json_success(request, data=_library_result(user_profile, changed=changed))


@require_non_guest_user
@typed_endpoint
def revoke_pipeline_creator(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    user_id: PathOnly[int],
) -> HttpResponse:
    changed = do_revoke_pipeline_creator(
        acting_user=user_profile, target=_target_user(user_profile, user_id)
    )
    return json_success(request, data=_library_result(user_profile, changed=changed))


@require_non_guest_user
@typed_endpoint
def create_module_draft(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    stable_key: Annotated[str, StringConstraints(max_length=64)],
    version: Annotated[str, StringConstraints(max_length=32)],
    name: Annotated[str, StringConstraints(max_length=100)],
    description: Annotated[str, StringConstraints(max_length=1024)],
    output_type: Annotated[str, StringConstraints(max_length=32)],
    runtime_key: Annotated[str, StringConstraints(max_length=100)],
    prompt_key: Annotated[str, StringConstraints(max_length=100)],
    destination_topic: Annotated[str, StringConstraints(max_length=60)],
    navigation_icon: Annotated[str, StringConstraints(max_length=64)],
    navigation_order: Json[int],
    input_contract: Json[dict[str, Any]],
    lookback_days: Json[int],
    integration_keys: Json[list[str]],
    output_template: Json[dict[str, Any]],
    maximum_runtime_seconds: Json[int],
    requirements: Json[list[ModuleRequirementInput]],
    supported_triggers: Json[list[str]],
) -> HttpResponse:
    draft = do_create_module_draft(
        acting_user=user_profile,
        spec=_draft_spec(
            stable_key=stable_key,
            version=version,
            name=name,
            description=description,
            output_type=output_type,
            runtime_key=runtime_key,
            prompt_key=prompt_key,
            destination_topic=destination_topic,
            navigation_icon=navigation_icon,
            navigation_order=navigation_order,
            input_contract=input_contract,
            lookback_days=lookback_days,
            integration_keys=integration_keys,
            output_template=output_template,
            maximum_runtime_seconds=maximum_runtime_seconds,
            requirements=requirements,
            supported_triggers=supported_triggers,
        ),
    )
    return json_success(
        request, data=_library_result(user_profile, draft=draft_data(draft), created=True)
    )


@require_non_guest_user
@typed_endpoint
def update_module_draft(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    draft_id: PathOnly[int],
    revision: Json[int],
    stable_key: Annotated[str, StringConstraints(max_length=64)],
    version: Annotated[str, StringConstraints(max_length=32)],
    name: Annotated[str, StringConstraints(max_length=100)],
    description: Annotated[str, StringConstraints(max_length=1024)],
    output_type: Annotated[str, StringConstraints(max_length=32)],
    runtime_key: Annotated[str, StringConstraints(max_length=100)],
    prompt_key: Annotated[str, StringConstraints(max_length=100)],
    destination_topic: Annotated[str, StringConstraints(max_length=60)],
    navigation_icon: Annotated[str, StringConstraints(max_length=64)],
    navigation_order: Json[int],
    input_contract: Json[dict[str, Any]],
    lookback_days: Json[int],
    integration_keys: Json[list[str]],
    output_template: Json[dict[str, Any]],
    maximum_runtime_seconds: Json[int],
    requirements: Json[list[ModuleRequirementInput]],
    supported_triggers: Json[list[str]],
) -> HttpResponse:
    draft = do_update_module_draft(
        acting_user=user_profile,
        draft_id=draft_id,
        revision=revision,
        spec=_draft_spec(
            stable_key=stable_key,
            version=version,
            name=name,
            description=description,
            output_type=output_type,
            runtime_key=runtime_key,
            prompt_key=prompt_key,
            destination_topic=destination_topic,
            navigation_icon=navigation_icon,
            navigation_order=navigation_order,
            input_contract=input_contract,
            lookback_days=lookback_days,
            integration_keys=integration_keys,
            output_template=output_template,
            maximum_runtime_seconds=maximum_runtime_seconds,
            requirements=requirements,
            supported_triggers=supported_triggers,
        ),
    )
    return json_success(request, data=_library_result(user_profile, draft=draft_data(draft)))


@require_non_guest_user
@typed_endpoint
def add_module_draft_collaborator(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    draft_id: PathOnly[int],
    user_id: Json[int],
) -> HttpResponse:
    draft, changed = do_add_module_draft_collaborator(
        acting_user=user_profile,
        draft_id=draft_id,
        target=_target_user(user_profile, user_id),
    )
    return json_success(
        request,
        data=_library_result(user_profile, draft=draft_data(draft), changed=changed),
    )


@require_non_guest_user
@typed_endpoint
def remove_module_draft_collaborator(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    draft_id: PathOnly[int],
    user_id: PathOnly[int],
) -> HttpResponse:
    draft, changed = do_remove_module_draft_collaborator(
        acting_user=user_profile,
        draft_id=draft_id,
        target=_target_user(user_profile, user_id),
    )
    return json_success(
        request,
        data=_library_result(user_profile, draft=draft_data(draft), changed=changed),
    )


@require_non_guest_user
@typed_endpoint
def publish_module_draft(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    draft_id: PathOnly[int],
    revision: Json[int],
) -> HttpResponse:
    draft, created = do_publish_module_draft(
        acting_user=user_profile, draft_id=draft_id, revision=revision
    )
    assert draft.published_version is not None
    return json_success(
        request,
        data=_library_result(
            user_profile,
            draft=draft_data(draft),
            version=public_version_data(draft.published_version),
            created=created,
        ),
    )


@require_non_guest_user
@typed_endpoint
def create_successor_module_draft(
    request: HttpRequest, user_profile: UserProfile, *, version_id: PathOnly[int]
) -> HttpResponse:
    draft, created = do_create_successor_draft(acting_user=user_profile, version_id=version_id)
    return json_success(
        request, data=_library_result(user_profile, draft=draft_data(draft), created=created)
    )


@require_non_guest_user
@typed_endpoint
def archive_module_definition(
    request: HttpRequest, user_profile: UserProfile, *, definition_id: PathOnly[int]
) -> HttpResponse:
    definition, changed = do_archive_module_definition(
        acting_user=user_profile, definition_id=definition_id
    )
    return json_success(
        request,
        data=_library_result(
            user_profile, definition=public_definition_data(definition), changed=changed
        ),
    )


@require_non_guest_user
@typed_endpoint
def archive_module_version(
    request: HttpRequest, user_profile: UserProfile, *, version_id: PathOnly[int]
) -> HttpResponse:
    version, changed = do_archive_module_version(acting_user=user_profile, version_id=version_id)
    return json_success(
        request,
        data=_library_result(user_profile, version=public_version_data(version), changed=changed),
    )


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
