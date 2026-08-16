from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from typing import Any

from django.db import IntegrityError, transaction
from django.db.models import Prefetch, Q, QuerySet
from django.utils.timezone import now as timezone_now
from django.utils.translation import gettext as _

from hover.models import (
    MAX_PIPELINE_RUNTIME_SECONDS,
    ModuleDefinition,
    ModuleDefinitionArchive,
    ModuleDraft,
    ModuleDraftCollaborator,
    ModuleSourceRequirement,
    ModuleSupportedTrigger,
    ModuleVersion,
    ModuleVersionArchive,
    PipelineCreatorAssignment,
)
from zerver.lib.exceptions import JsonableError
from zerver.models.realm_audit_logs import AuditLogEventType, RealmAuditLog
from zerver.models.realms import Realm
from zerver.models.users import UserProfile

MAX_PIPELINE_LOOKBACK_SECONDS = 366 * 24 * 60 * 60
_SAFE_KEY_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_SAFE_IDENTITY_RE = re.compile(r"^[a-z][a-z0-9_.-]{0,99}$")
_SEMVER_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")
_PRIVATE_CONTRACT_KEYS = {
    "api_key",
    "authorization",
    "bearer",
    "clawer_endpoint",
    "credential",
    "credentials",
    "endpoint",
    "password",
    "provider_id",
    "provider_identifier",
    "secret",
    "token",
}
_PRIVATE_CONTRACT_KEY_PARTS = {
    "auth",
    "bearer",
    "credential",
    "endpoint",
    "jid",
    "password",
    "phone",
    "provider",
    "secret",
    "token",
    "url",
}


class ModuleDraftConflictError(JsonableError):
    http_status_code = 409


@dataclass(frozen=True)
class ModuleRequirementSpec:
    key: str
    capability: str
    minimum_count: int
    maximum_count: int


@dataclass(frozen=True)
class ModuleDraftSpec:
    stable_key: str
    version: str
    name: str
    description: str
    output_type: str
    runtime_key: str
    prompt_key: str
    destination_topic: str
    navigation_icon: str
    navigation_order: int
    input_contract: dict[str, Any]
    lookback_seconds: int
    integration_keys: list[str]
    output_template: dict[str, Any]
    maximum_runtime_seconds: int
    requirements: list[ModuleRequirementSpec]
    supported_triggers: list[str]


def _audit(
    *,
    realm: Realm,
    acting_user: UserProfile,
    event_type: AuditLogEventType,
    extra_data: dict[str, object],
    modified_user: UserProfile | None = None,
) -> None:
    # Library audit records intentionally contain only Hover database IDs,
    # lifecycle states, counts, and revisions. Authoring contracts can contain
    # sensitive business instructions and never belong in an audit log.
    RealmAuditLog.objects.create(
        realm=realm,
        acting_user=acting_user,
        modified_user=modified_user,
        event_type=event_type,
        event_time=timezone_now(),
        extra_data=extra_data,
    )


def _active_creator_assignments(realm: Realm) -> QuerySet[PipelineCreatorAssignment]:
    return PipelineCreatorAssignment.objects.filter(
        realm=realm,
        revoked_at__isnull=True,
        user__is_active=True,
        user__is_bot=False,
        user__role__in=[
            UserProfile.ROLE_MEMBER,
            UserProfile.ROLE_REALM_ADMINISTRATOR,
            UserProfile.ROLE_REALM_OWNER,
            UserProfile.ROLE_MODERATOR,
        ],
    )


def user_is_pipeline_creator(user: UserProfile) -> bool:
    return user.is_active and _active_creator_assignments(user.realm).filter(user=user).exists()


def user_can_create_pipelines(user: UserProfile) -> bool:
    return user.is_realm_admin or user_is_pipeline_creator(user)


def _assert_hover_enabled(user: UserProfile) -> None:
    if not user.realm.hover_enabled:
        raise JsonableError(_("Hover is not enabled for this organization."))


def _assert_creator(user: UserProfile) -> None:
    _assert_hover_enabled(user)
    if not user_can_create_pipelines(user):
        raise JsonableError(_("You do not have permission to create Pipelines."))


def _assert_realm_admin(user: UserProfile) -> None:
    _assert_hover_enabled(user)
    if not user.is_realm_admin:
        raise JsonableError(_("Must be an organization administrator"))


def _assert_safe_contract_value(value: object) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if not isinstance(key, str):
                raise JsonableError(_("Input contract keys must be strings."))
            normalized_key = re.sub(r"[^a-z0-9]", "", key.casefold())
            if key.casefold() in _PRIVATE_CONTRACT_KEYS or any(
                part in normalized_key for part in _PRIVATE_CONTRACT_KEY_PARTS
            ):
                raise JsonableError(_("Input contracts cannot contain credentials or endpoints."))
            _assert_safe_contract_value(child)
    elif isinstance(value, list):
        for child in value:
            _assert_safe_contract_value(child)
    elif value is not None and not isinstance(value, (str, int, float, bool)):
        raise JsonableError(_("Input contract contains an unsupported value."))


def _validate_input_contract(contract: dict[str, Any]) -> None:
    _assert_safe_contract_value(contract)
    if contract != {"kind": "attached_sources", "record_type": "message"}:
        raise JsonableError(_("Invalid Pipeline input contract."))


def _validate_output_template(template: dict[str, Any], *, pipeline_name: str) -> None:
    _assert_safe_contract_value(template)
    if set(template) - {"format", "title", "sections"}:
        raise JsonableError(_("Invalid Pipeline output template."))
    if template.get("format") != "hover_generated_update":
        raise JsonableError(_("Invalid Pipeline output template."))
    title = template.get("title")
    if title is not None and title != pipeline_name:
        raise JsonableError(_("Pipeline output titles must match the Pipeline name."))
    sections = template.get("sections")
    if sections is not None and (
        not isinstance(sections, list)
        or not 1 <= len(sections) <= 20
        or any(
            not isinstance(section, str) or not _SAFE_KEY_RE.fullmatch(section)
            for section in sections
        )
    ):
        raise JsonableError(_("Invalid Pipeline output template."))
    if title is None and sections is None:
        raise JsonableError(_("Invalid Pipeline output template."))


def validate_draft_spec(spec: ModuleDraftSpec) -> ModuleDraftSpec:
    stable_key = spec.stable_key.strip()
    version = spec.version.strip()
    name = spec.name.strip()
    description = spec.description.strip()
    output_type = spec.output_type.strip()
    runtime_key = spec.runtime_key.strip()
    prompt_key = spec.prompt_key.strip()
    destination_topic = spec.destination_topic.strip()
    navigation_icon = spec.navigation_icon.strip()
    integration_keys = sorted({item.strip() for item in spec.integration_keys})
    supported_triggers = sorted(set(spec.supported_triggers))
    requirements = sorted(spec.requirements, key=lambda item: item.key)

    if not _SAFE_KEY_RE.fullmatch(stable_key):
        raise JsonableError(_("Invalid Pipeline key."))
    if _SEMVER_RE.fullmatch(version) is None:
        raise JsonableError(_("Pipeline versions must use semantic versioning."))
    if not name or len(name) > 100 or len(description) > 1024:
        raise JsonableError(_("Invalid Pipeline name or description."))
    if not _SAFE_KEY_RE.fullmatch(output_type):
        raise JsonableError(_("Invalid Pipeline output type."))
    if not _SAFE_IDENTITY_RE.fullmatch(runtime_key) or not _SAFE_IDENTITY_RE.fullmatch(prompt_key):
        raise JsonableError(_("Invalid runtime or prompt identity."))
    if not destination_topic or len(destination_topic) > 60:
        raise JsonableError(_("Invalid destination topic."))
    if not navigation_icon or len(navigation_icon) > 64 or not 0 <= spec.navigation_order <= 32767:
        raise JsonableError(_("Invalid Pipeline navigation metadata."))
    if not spec.input_contract:
        raise JsonableError(_("A Pipeline input contract is required."))
    _validate_input_contract(spec.input_contract)
    if not 1 <= spec.lookback_seconds <= MAX_PIPELINE_LOOKBACK_SECONDS:
        raise JsonableError(_("Pipeline lookback is outside the supported range."))
    if any(not _SAFE_KEY_RE.fullmatch(item) for item in integration_keys):
        raise JsonableError(_("Integration references must be registered integration keys."))
    # T09 stores only opaque, non-secret integration references. T10 resolves
    # them against the acting creator's Studio-mediated integration registry
    # before any real-data test or external operation.
    if not spec.output_template:
        raise JsonableError(_("A bounded output template is required."))
    _validate_output_template(spec.output_template, pipeline_name=name)
    if not 1 <= spec.maximum_runtime_seconds <= MAX_PIPELINE_RUNTIME_SECONDS:
        raise JsonableError(
            _("Maximum runtime must be between 1 and %(cap)s seconds.")
            % {"cap": MAX_PIPELINE_RUNTIME_SECONDS}
        )
    if not requirements:
        raise JsonableError(_("At least one Source requirement is required."))
    if len({item.key for item in requirements}) != len(requirements):
        raise JsonableError(_("Source requirement keys must be unique."))
    for requirement in requirements:
        if (
            not _SAFE_KEY_RE.fullmatch(requirement.key)
            or not _SAFE_KEY_RE.fullmatch(requirement.capability)
            or requirement.minimum_count < 1
            or requirement.maximum_count < requirement.minimum_count
            or requirement.maximum_count > 100
        ):
            raise JsonableError(_("Invalid Source requirement contract."))
    # The accepted installation contract reserves per-Source automatic runs for
    # a later product decision; new published versions support only explicit or
    # scheduled execution.
    valid_triggers = {
        ModuleSupportedTrigger.Kind.MANUAL,
        ModuleSupportedTrigger.Kind.SCHEDULE,
    }
    if not supported_triggers or not set(supported_triggers) <= valid_triggers:
        raise JsonableError(_("Invalid supported trigger contract."))

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
        navigation_order=spec.navigation_order,
        input_contract=spec.input_contract,
        lookback_seconds=spec.lookback_seconds,
        integration_keys=integration_keys,
        output_template=spec.output_template,
        maximum_runtime_seconds=spec.maximum_runtime_seconds,
        requirements=requirements,
        supported_triggers=supported_triggers,
    )


def _spec_from_draft(draft: ModuleDraft) -> ModuleDraftSpec:
    return ModuleDraftSpec(
        stable_key=draft.stable_key,
        version=draft.version,
        name=draft.name,
        description=draft.description,
        output_type=draft.output_type,
        runtime_key=draft.runtime_key,
        prompt_key=draft.prompt_key,
        destination_topic=draft.destination_topic,
        navigation_icon=draft.navigation_icon,
        navigation_order=draft.navigation_order,
        input_contract=draft.input_contract,
        lookback_seconds=draft.lookback_seconds,
        integration_keys=draft.integration_keys,
        output_template=draft.output_template,
        maximum_runtime_seconds=draft.maximum_runtime_seconds,
        requirements=[ModuleRequirementSpec(**item) for item in draft.requirements],
        supported_triggers=draft.supported_triggers,
    )


def _draft_values(spec: ModuleDraftSpec) -> dict[str, object]:
    values = asdict(spec)
    values["requirements"] = [asdict(item) for item in spec.requirements]
    return values


def _canonical_version_contract(
    *, definition: ModuleDefinition, spec: ModuleDraftSpec
) -> dict[str, object]:
    return {
        "definition_key": definition.stable_key,
        "version": spec.version,
        "input_contract": spec.input_contract,
        "lookback_seconds": spec.lookback_seconds,
        "runtime_key": spec.runtime_key,
        "prompt_key": spec.prompt_key,
        "integration_keys": spec.integration_keys,
        "output_type": spec.output_type,
        "output_template": spec.output_template,
        "maximum_runtime_seconds": spec.maximum_runtime_seconds,
        "destination_topic": spec.destination_topic,
        "navigation_icon": spec.navigation_icon,
        "navigation_order": spec.navigation_order,
        "requirements": [asdict(item) for item in spec.requirements],
        "supported_triggers": spec.supported_triggers,
    }


def _canonical_hash(payload: dict[str, object]) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def public_version_data(version: ModuleVersion) -> dict[str, object]:
    return {
        "id": version.id,
        "definition_id": version.definition_id,
        "definition_key": version.definition.stable_key,
        "name": version.definition.name,
        "description": version.definition.description,
        "version": version.version,
        "published_by_id": version.published_by_id,
        "output_type": version.output_type,
        "destination_topic": version.destination_topic,
        "navigation_icon": version.navigation_icon,
        "navigation_order": version.navigation_order,
        "lookback_days": version.lookback_seconds // (24 * 60 * 60),
        "maximum_runtime_seconds": version.maximum_runtime_seconds,
        "content_hash": version.content_hash,
        "published_at": version.published_at.isoformat(),
        "archived": hasattr(version, "archive_record"),
        "requirements": [
            {
                "key": item.key,
                "capability": item.capability,
                "minimum_count": item.minimum_count,
                "maximum_count": item.maximum_count,
            }
            for item in version.requirements.all()
        ],
        "supported_triggers": [item.kind for item in version.supported_triggers.all()],
    }


def public_definition_data(definition: ModuleDefinition) -> dict[str, object]:
    versions = getattr(definition, "library_versions", definition.versions.all())
    return {
        "id": definition.id,
        "stable_key": definition.stable_key,
        "name": definition.name,
        "description": definition.description,
        "archived": hasattr(definition, "archive_record"),
        "versions": [public_version_data(version) for version in versions],
    }


def draft_data(
    draft: ModuleDraft, *, current_creator_ids: set[int] | None = None
) -> dict[str, object]:
    if current_creator_ids is None:
        current_creator_ids = set(
            _active_creator_assignments(draft.realm).values_list("user_id", flat=True)
        )
    return {
        "id": draft.id,
        "definition_id": draft.definition_id,
        "based_on_version_id": draft.based_on_version_id,
        "revision": draft.revision,
        "state": draft.state,
        "contract": {
            "stable_key": draft.stable_key,
            "version": draft.version,
            "name": draft.name,
            "description": draft.description,
            "output_type": draft.output_type,
            "runtime_key": draft.runtime_key,
            "prompt_key": draft.prompt_key,
            "destination_topic": draft.destination_topic,
            "navigation_icon": draft.navigation_icon,
            "navigation_order": draft.navigation_order,
            "input_contract": draft.input_contract,
            "lookback_days": draft.lookback_seconds // (24 * 60 * 60),
            "integration_keys": draft.integration_keys,
            "output_template": draft.output_template,
            "maximum_runtime_seconds": draft.maximum_runtime_seconds,
            "requirements": draft.requirements,
            "supported_triggers": draft.supported_triggers,
        },
        "author_id": draft.author_id,
        "collaborator_user_ids": sorted(
            collaborator.user_id
            for collaborator in draft.collaborators.all()
            if collaborator.user_id in current_creator_ids
        ),
        "published_version_id": draft.published_version_id,
        "date_updated": draft.date_updated.isoformat(),
    }


def visible_drafts(user: UserProfile) -> QuerySet[ModuleDraft]:
    drafts = (
        ModuleDraft.objects.filter(realm=user.realm)
        .select_related("definition", "based_on_version", "published_version", "author")
        .prefetch_related("collaborators")
    )
    if user.is_realm_admin:
        return drafts
    visibility = Q(author=user)
    if user_is_pipeline_creator(user):
        visibility |= Q(collaborators__user=user)
    return drafts.filter(visibility).distinct()


def get_pipeline_library_data(user: UserProfile) -> dict[str, object]:
    _assert_hover_enabled(user)
    from hover.actions_modules import ensure_prebuilt_module_catalog

    ensure_prebuilt_module_catalog(user.realm)
    definition_filter = Q(realm=user.realm)
    versions = ModuleVersion.objects.all()
    if not user.is_realm_admin:
        definition_filter &= Q(archive_record__isnull=True)
        versions = versions.filter(archive_record__isnull=True)
    definitions = (
        ModuleDefinition.objects.filter(definition_filter)
        .select_related("archive_record")
        .prefetch_related(
            Prefetch(
                "versions",
                queryset=versions.select_related("definition", "archive_record")
                .prefetch_related("requirements", "supported_triggers")
                .order_by("published_at", "id"),
                to_attr="library_versions",
            )
        )
        .order_by("name", "id")
    )
    drafts = visible_drafts(user).order_by("-date_updated", "id")
    creator_user_ids = list(
        _active_creator_assignments(user.realm)
        .order_by("user_id")
        .values_list("user_id", flat=True)
    )
    current_creator_ids = set(creator_user_ids)
    return {
        "definitions": [public_definition_data(item) for item in definitions],
        "drafts": [draft_data(item, current_creator_ids=current_creator_ids) for item in drafts],
        "creator_user_ids": creator_user_ids,
        "permissions": {
            "can_create": user_can_create_pipelines(user),
            "can_manage_creators": user.is_realm_admin,
            "can_archive": user.is_realm_admin,
        },
    }


@transaction.atomic(durable=True)
def do_grant_pipeline_creator(
    *, acting_user: UserProfile, target: UserProfile
) -> tuple[PipelineCreatorAssignment, bool]:
    _assert_realm_admin(acting_user)
    if (
        target.realm_id != acting_user.realm_id
        or not target.is_active
        or target.is_bot
        or target.is_guest
    ):
        raise JsonableError(_("Invalid user ID"))
    assignment, created = PipelineCreatorAssignment.objects.get_or_create(
        realm=acting_user.realm,
        user=target,
        revoked_at=None,
        defaults={"granted_by": acting_user},
    )
    if not created:
        return assignment, False
    _audit(
        realm=acting_user.realm,
        acting_user=acting_user,
        modified_user=target,
        event_type=AuditLogEventType.HOVER_PIPELINE_CREATOR_GRANTED,
        extra_data={"assignment_id": assignment.id},
    )
    return assignment, True


@transaction.atomic(durable=True)
def do_revoke_pipeline_creator(*, acting_user: UserProfile, target: UserProfile) -> bool:
    _assert_realm_admin(acting_user)
    if target.realm_id != acting_user.realm_id:
        raise JsonableError(_("Invalid user ID"))
    assignment = (
        PipelineCreatorAssignment.objects.select_for_update()
        .filter(realm=acting_user.realm, user=target, revoked_at__isnull=True)
        .first()
    )
    if assignment is None:
        return False
    assignment.revoked_at = timezone_now()
    assignment.revoked_by = acting_user
    assignment.save(update_fields=["revoked_at", "revoked_by"])
    _audit(
        realm=acting_user.realm,
        acting_user=acting_user,
        modified_user=target,
        event_type=AuditLogEventType.HOVER_PIPELINE_CREATOR_REVOKED,
        extra_data={"assignment_id": assignment.id},
    )
    return True


@transaction.atomic(durable=True)
def do_create_module_draft(*, acting_user: UserProfile, spec: ModuleDraftSpec) -> ModuleDraft:
    _assert_creator(acting_user)
    spec = validate_draft_spec(spec)
    if spec.version != "1.0.0":
        raise JsonableError(_("New Pipelines begin at server-owned version 1.0.0."))
    if ModuleDefinition.objects.filter(
        realm=acting_user.realm, stable_key=spec.stable_key
    ).exists():
        raise JsonableError(_("That Pipeline key is already published."))
    if ModuleDraft.objects.filter(
        realm=acting_user.realm,
        stable_key=spec.stable_key,
        definition__isnull=True,
        state=ModuleDraft.State.DRAFT,
    ).exists():
        raise ModuleDraftConflictError(_("That Pipeline key already has an active draft."))
    try:
        draft = ModuleDraft.objects.create(
            realm=acting_user.realm, author=acting_user, **_draft_values(spec)
        )
    except IntegrityError:
        raise ModuleDraftConflictError(_("That Pipeline key already has an active draft."))
    _audit(
        realm=acting_user.realm,
        acting_user=acting_user,
        event_type=AuditLogEventType.HOVER_MODULE_DRAFT_CREATED,
        extra_data={"draft_id": draft.id, "revision": draft.revision},
    )
    return draft


def access_module_draft(user: UserProfile, draft_id: int) -> ModuleDraft:
    try:
        return visible_drafts(user).get(id=draft_id)
    except ModuleDraft.DoesNotExist:
        raise JsonableError(_("Invalid Pipeline draft."))


def _can_mutate_draft(user: UserProfile, draft: ModuleDraft) -> bool:
    if user.realm_id != draft.realm_id or draft.state != ModuleDraft.State.DRAFT:
        return False
    if user.is_realm_admin:
        return True
    if not user_is_pipeline_creator(user):
        return False
    return draft.author_id == user.id or draft.collaborators.filter(user=user).exists()


def _assert_can_mutate_draft(user: UserProfile, draft: ModuleDraft) -> None:
    if not _can_mutate_draft(user, draft):
        raise JsonableError(_("You do not have permission to edit this Pipeline draft."))


def _assert_can_manage_draft_collaborators(user: UserProfile, draft: ModuleDraft) -> None:
    if not _can_mutate_draft(user, draft) or (
        not user.is_realm_admin and draft.author_id != user.id
    ):
        raise JsonableError(
            _("Only the draft author or an organization administrator can manage collaborators.")
        )


@transaction.atomic(durable=True)
def do_update_module_draft(
    *, acting_user: UserProfile, draft_id: int, revision: int, spec: ModuleDraftSpec
) -> ModuleDraft:
    try:
        draft = (
            ModuleDraft.objects.select_for_update(of=("self",))
            .select_related("definition")
            .get(id=draft_id, realm=acting_user.realm)
        )
    except ModuleDraft.DoesNotExist:
        raise JsonableError(_("Invalid Pipeline draft."))
    _assert_can_mutate_draft(acting_user, draft)
    if draft.revision != revision:
        raise ModuleDraftConflictError(_("The Pipeline draft changed; reload before editing."))
    spec = validate_draft_spec(spec)
    if spec.version != draft.version:
        raise JsonableError(_("The server-owned Pipeline version cannot be changed."))
    if draft.definition is not None and (
        spec.stable_key != draft.definition.stable_key
        or spec.name != draft.definition.name
        or spec.description != draft.definition.description
    ):
        raise JsonableError(_("A successor draft cannot change its stable definition metadata."))
    if (
        draft.definition is None
        and ModuleDefinition.objects.filter(realm=draft.realm, stable_key=spec.stable_key).exists()
    ):
        raise JsonableError(_("That Pipeline key is already published."))
    for field, value in _draft_values(spec).items():
        setattr(draft, field, value)
    draft.revision += 1
    draft.save(update_fields=[*_draft_values(spec).keys(), "revision", "date_updated"])
    _audit(
        realm=draft.realm,
        acting_user=acting_user,
        event_type=AuditLogEventType.HOVER_MODULE_DRAFT_UPDATED,
        extra_data={"draft_id": draft.id, "revision": draft.revision},
    )
    return draft


@transaction.atomic(durable=True)
def do_add_module_draft_collaborator(
    *, acting_user: UserProfile, draft_id: int, target: UserProfile
) -> tuple[ModuleDraft, bool]:
    try:
        draft = ModuleDraft.objects.select_for_update().get(id=draft_id, realm=acting_user.realm)
    except ModuleDraft.DoesNotExist:
        raise JsonableError(_("Invalid Pipeline draft."))
    _assert_can_manage_draft_collaborators(acting_user, draft)
    if target.realm_id != draft.realm_id or not user_is_pipeline_creator(target):
        raise JsonableError(_("Collaborators must be current Pipeline Creators."))
    if draft.author_id == target.id:
        raise JsonableError(_("The draft author is already an editor."))
    collaborator, created = ModuleDraftCollaborator.objects.get_or_create(
        draft=draft, user=target, defaults={"added_by": acting_user}
    )
    if created:
        _audit(
            realm=draft.realm,
            acting_user=acting_user,
            modified_user=target,
            event_type=AuditLogEventType.HOVER_MODULE_DRAFT_COLLABORATOR_CHANGED,
            extra_data={"draft_id": draft.id, "collaborator_id": collaborator.id, "active": True},
        )
    return draft, created


@transaction.atomic(durable=True)
def do_remove_module_draft_collaborator(
    *, acting_user: UserProfile, draft_id: int, target: UserProfile
) -> tuple[ModuleDraft, bool]:
    try:
        draft = ModuleDraft.objects.select_for_update().get(id=draft_id, realm=acting_user.realm)
    except ModuleDraft.DoesNotExist:
        raise JsonableError(_("Invalid Pipeline draft."))
    _assert_can_manage_draft_collaborators(acting_user, draft)
    deleted, _deleted_by_model = ModuleDraftCollaborator.objects.filter(
        draft=draft, user=target
    ).delete()
    if deleted:
        _audit(
            realm=draft.realm,
            acting_user=acting_user,
            modified_user=target if target.realm_id == draft.realm_id else None,
            event_type=AuditLogEventType.HOVER_MODULE_DRAFT_COLLABORATOR_CHANGED,
            extra_data={"draft_id": draft.id, "active": False},
        )
    return draft, bool(deleted)


def _next_version(base_version: str | None, definition: ModuleDefinition) -> str:
    if base_version is None:
        candidate = "1.0.0"
    else:
        match = _SEMVER_RE.fullmatch(base_version)
        if match is None:
            candidate = f"{definition.versions.count() + 1}.0.0"
        else:
            major, minor, patch = (int(item) for item in match.groups())
            candidate = f"{major}.{minor}.{patch + 1}"
    while definition.versions.filter(version=candidate).exists():
        match = _SEMVER_RE.fullmatch(candidate)
        assert match is not None
        major, minor, patch = (int(item) for item in match.groups())
        candidate = f"{major}.{minor}.{patch + 1}"
    return candidate


@transaction.atomic(durable=True)
def do_publish_module_draft(
    *, acting_user: UserProfile, draft_id: int, revision: int
) -> tuple[ModuleDraft, bool]:
    try:
        draft = (
            ModuleDraft.objects.select_for_update(of=("self",))
            .select_related("definition", "based_on_version", "published_version")
            .get(id=draft_id, realm=acting_user.realm)
        )
    except ModuleDraft.DoesNotExist:
        raise JsonableError(_("Invalid Pipeline draft."))
    if draft.published_version is not None:
        if not visible_drafts(acting_user).filter(id=draft.id).exists():
            raise JsonableError(_("Invalid Pipeline draft."))
        return draft, False
    _assert_can_mutate_draft(acting_user, draft)
    if draft.revision != revision:
        raise ModuleDraftConflictError(_("The Pipeline draft changed; reload before publishing."))
    spec = validate_draft_spec(_spec_from_draft(draft))
    if draft.definition is None:
        try:
            definition = ModuleDefinition.objects.create(
                realm=draft.realm,
                stable_key=spec.stable_key,
                name=spec.name,
                description=spec.description,
            )
        except IntegrityError:
            raise ModuleDraftConflictError(_("That Pipeline key was published concurrently."))
    else:
        definition_id = draft.definition_id
        assert definition_id is not None
        definition = ModuleDefinition.objects.select_for_update().get(id=definition_id)
        if hasattr(definition, "archive_record"):
            raise JsonableError(_("Archived Pipeline definitions cannot publish new versions."))
    expected_version = _next_version(
        draft.based_on_version.version if draft.based_on_version is not None else None,
        definition,
    )
    if spec.version != expected_version:
        raise ModuleDraftConflictError(_("The server-owned Pipeline version is no longer current."))
    contract = _canonical_version_contract(definition=definition, spec=spec)
    try:
        version = ModuleVersion.objects.create(
            definition=definition,
            version=spec.version,
            output_type=spec.output_type,
            runtime_key=spec.runtime_key,
            prompt_key=spec.prompt_key,
            input_contract=spec.input_contract,
            lookback_seconds=spec.lookback_seconds,
            integration_keys=spec.integration_keys,
            destination_topic=spec.destination_topic,
            navigation_icon=spec.navigation_icon,
            navigation_order=spec.navigation_order,
            output_template=spec.output_template,
            maximum_runtime_seconds=spec.maximum_runtime_seconds,
            is_sealed=False,
            content_hash=_canonical_hash(contract),
            published_by=acting_user,
        )
    except IntegrityError:
        raise ModuleDraftConflictError(_("This Pipeline version was published concurrently."))
    ModuleSourceRequirement.objects.bulk_create(
        [ModuleSourceRequirement(version=version, **asdict(item)) for item in spec.requirements]
    )
    ModuleSupportedTrigger.objects.bulk_create(
        [ModuleSupportedTrigger(version=version, kind=item) for item in spec.supported_triggers]
    )
    ModuleVersion.objects.filter(id=version.id, is_sealed=False).update(is_sealed=True)
    version.is_sealed = True
    draft.definition = definition
    draft.published_version = version
    draft.state = ModuleDraft.State.PUBLISHED
    draft.revision += 1
    draft.save(
        update_fields=["definition", "published_version", "state", "revision", "date_updated"]
    )
    _audit(
        realm=draft.realm,
        acting_user=acting_user,
        event_type=AuditLogEventType.HOVER_MODULE_VERSION_PUBLISHED,
        extra_data={
            "draft_id": draft.id,
            "definition_id": definition.id,
            "version_id": version.id,
            "revision": draft.revision,
            "requirement_count": len(spec.requirements),
            "integration_count": len(spec.integration_keys),
        },
    )
    return draft, True


@transaction.atomic(durable=True)
def do_create_successor_draft(
    *, acting_user: UserProfile, version_id: int
) -> tuple[ModuleDraft, bool]:
    _assert_creator(acting_user)
    try:
        version = (
            ModuleVersion.objects.select_for_update(no_key=True)
            .select_related("definition")
            .prefetch_related("requirements", "supported_triggers")
            .get(id=version_id, definition__realm=acting_user.realm)
        )
    except ModuleVersion.DoesNotExist:
        raise JsonableError(_("Invalid Pipeline version."))
    if hasattr(version.definition, "archive_record") or hasattr(version, "archive_record"):
        raise JsonableError(_("Archived Pipelines cannot create successor drafts."))
    existing = ModuleDraft.objects.filter(
        author=acting_user,
        based_on_version=version,
        state=ModuleDraft.State.DRAFT,
    ).first()
    if existing is not None:
        return existing, False
    draft = ModuleDraft.objects.create(
        realm=acting_user.realm,
        definition=version.definition,
        based_on_version=version,
        author=acting_user,
        stable_key=version.definition.stable_key,
        version=_next_version(version.version, version.definition),
        name=version.definition.name,
        description=version.definition.description,
        output_type=version.output_type,
        runtime_key=version.runtime_key,
        prompt_key=version.prompt_key,
        input_contract=version.input_contract,
        lookback_seconds=version.lookback_seconds,
        integration_keys=version.integration_keys,
        destination_topic=version.destination_topic,
        navigation_icon=version.navigation_icon,
        navigation_order=version.navigation_order,
        output_template=version.output_template,
        maximum_runtime_seconds=version.maximum_runtime_seconds,
        requirements=[
            {
                "key": item.key,
                "capability": item.capability,
                "minimum_count": item.minimum_count,
                "maximum_count": item.maximum_count,
            }
            for item in version.requirements.all()
        ],
        supported_triggers=sorted(item.kind for item in version.supported_triggers.all()),
    )
    _audit(
        realm=draft.realm,
        acting_user=acting_user,
        event_type=AuditLogEventType.HOVER_MODULE_DRAFT_CREATED,
        extra_data={"draft_id": draft.id, "based_on_version_id": version.id, "revision": 1},
    )
    return draft, True


@transaction.atomic(durable=True)
def do_archive_module_definition(
    *, acting_user: UserProfile, definition_id: int
) -> tuple[ModuleDefinition, bool]:
    _assert_realm_admin(acting_user)
    try:
        definition = ModuleDefinition.objects.select_for_update().get(
            id=definition_id, realm=acting_user.realm
        )
    except ModuleDefinition.DoesNotExist:
        raise JsonableError(_("Invalid Pipeline definition."))
    archive, created = ModuleDefinitionArchive.objects.get_or_create(
        definition=definition, defaults={"archived_by": acting_user}
    )
    if created:
        _audit(
            realm=acting_user.realm,
            acting_user=acting_user,
            event_type=AuditLogEventType.HOVER_MODULE_DEFINITION_ARCHIVED,
            extra_data={"definition_id": definition.id, "archive_id": archive.id},
        )
    return definition, created


@transaction.atomic(durable=True)
def do_archive_module_version(
    *, acting_user: UserProfile, version_id: int
) -> tuple[ModuleVersion, bool]:
    _assert_realm_admin(acting_user)
    try:
        version = (
            ModuleVersion.objects.select_for_update()
            .select_related("definition")
            .get(id=version_id, definition__realm=acting_user.realm)
        )
    except ModuleVersion.DoesNotExist:
        raise JsonableError(_("Invalid Pipeline version."))
    archive, created = ModuleVersionArchive.objects.get_or_create(
        version=version, defaults={"archived_by": acting_user}
    )
    if created:
        _audit(
            realm=acting_user.realm,
            acting_user=acting_user,
            event_type=AuditLogEventType.HOVER_MODULE_VERSION_ARCHIVED,
            extra_data={
                "definition_id": version.definition_id,
                "version_id": version.id,
                "archive_id": archive.id,
            },
        )
    return version, created
