from __future__ import annotations

import hashlib
import json
from datetime import datetime, time
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.db import transaction
from django.utils.timezone import is_naive
from django.utils.timezone import now as timezone_now
from django.utils.translation import gettext as _

from hover.lib_spaces import get_space_data, user_is_space_administrator
from hover.models import (
    ConnectedAccount,
    ConnectedAccountGrant,
    ModuleDefinition,
    ModuleInstallation,
    ModuleInstallationBinding,
    ModuleInstallationTrigger,
    ModuleSourceRequirement,
    ModuleSupportedTrigger,
    ModuleVersion,
    Space,
    SpaceAdministrator,
    SpaceAttachment,
    SpaceMembership,
)
from zerver.lib.exceptions import JsonableError
from zerver.models.realms import Realm
from zerver.models.users import UserProfile
from zerver.tornado.django_api import send_event_on_commit


class ModuleConfigurationConflictError(JsonableError):
    http_status_code = 409


PREBUILT_MODULES: tuple[dict[str, Any], ...] = (
    {
        "key": "conversation_digest",
        "name": "Conversation Digest",
        "description": "Summarize important activity from attached conversations.",
        "output_type": "digest",
        "topic": "Conversation Digest",
        "icon": "zulip-icon-align-left",
        "order": 10,
        "triggers": ("manual", "new_source", "schedule"),
        "maximum_count": 10,
    },
    {
        "key": "progress_tracker",
        "name": "Progress Tracker",
        "description": "Track progress and changes across attached conversations.",
        "output_type": "progress_update",
        "topic": "Progress Tracker",
        "icon": "zulip-icon-trending-up",
        "order": 20,
        "triggers": ("manual", "new_source", "schedule"),
        "maximum_count": 10,
    },
    {
        "key": "suggested_actions",
        "name": "Suggested Actions",
        "description": "Identify concrete follow-up work.",
        "output_type": "suggested_action",
        "topic": "Suggested Actions",
        "icon": "zulip-icon-sparkles",
        "order": 30,
        "triggers": ("manual", "new_source", "schedule"),
        "maximum_count": 10,
    },
    {
        "key": "decisions",
        "name": "Decisions",
        "description": "Capture decisions and their supporting context.",
        "output_type": "decision",
        "topic": "Decisions",
        "icon": "zulip-icon-check-circle",
        "order": 40,
        "triggers": ("manual", "new_source", "schedule"),
        "maximum_count": 10,
    },
    {
        "key": "marketing_digest",
        "name": "Marketing Digest",
        "description": "Prepare a marketing-focused digest from one attached Source.",
        "output_type": "digest",
        "topic": "Marketing Digest",
        "icon": "zulip-icon-megaphone",
        "order": 50,
        "triggers": ("manual", "schedule"),
        "maximum_count": 1,
    },
    {
        "key": "topic_analysis",
        "name": "Topic Analysis",
        "description": "Analyze themes in one attached Source.",
        "output_type": "analysis",
        "topic": "Topic Analysis",
        "icon": "zulip-icon-chart-bar",
        "order": 60,
        "triggers": ("manual", "schedule"),
        "maximum_count": 1,
    },
    {
        "key": "signal_monitor",
        "name": "Signal Monitor",
        "description": "Monitor configured Sources for reviewed high-signal changes.",
        "output_type": "analysis",
        "topic": "Signal Monitor",
        "icon": "zulip-icon-bell",
        "order": 70,
        "triggers": ("manual", "new_source", "schedule"),
        "maximum_count": 10,
    },
)


def _canonical_hash(payload: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


@transaction.atomic(savepoint=False)
def ensure_prebuilt_module_catalog(realm: Realm) -> None:
    for item in PREBUILT_MODULES:
        definition, _ = ModuleDefinition.objects.get_or_create(
            realm=realm,
            stable_key=item["key"],
            defaults={"name": item["name"], "description": item["description"]},
        )
        contract = {
            "stable_key": item["key"],
            "version": "1.0.0",
            "output_type": item["output_type"],
            "runtime_key": f"hover.{item['key']}.v1",
            "prompt_key": f"hover.{item['key']}.v1",
            "destination_topic": item["topic"],
            "navigation_icon": item["icon"],
            "navigation_order": item["order"],
            "requirements": [
                {
                    "key": "conversation_history",
                    "capability": "message_history",
                    "minimum_count": 1,
                    "maximum_count": item["maximum_count"],
                }
            ],
            "triggers": list(item["triggers"]),
        }
        version, created = ModuleVersion.objects.get_or_create(
            definition=definition,
            version="1.0.0",
            defaults={
                "output_type": item["output_type"],
                "runtime_key": contract["runtime_key"],
                "prompt_key": contract["prompt_key"],
                "destination_topic": item["topic"],
                "navigation_icon": item["icon"],
                "navigation_order": item["order"],
                "content_hash": _canonical_hash(contract),
            },
        )
        if created:
            requirement = contract["requirements"][0]
            ModuleSourceRequirement.objects.create(version=version, **requirement)
            ModuleSupportedTrigger.objects.bulk_create(
                [ModuleSupportedTrigger(version=version, kind=kind) for kind in item["triggers"]]
            )


def module_version_data(version: ModuleVersion) -> dict[str, Any]:
    return {
        "id": version.id,
        "definition_key": version.definition.stable_key,
        "name": version.definition.name,
        "description": version.definition.description,
        "version": version.version,
        "output_type": version.output_type,
        "destination_topic": version.destination_topic,
        "navigation_icon": version.navigation_icon,
        "navigation_order": version.navigation_order,
        "content_hash": version.content_hash,
        "published_at": version.published_at.isoformat(),
        "requirements": [
            {
                "id": requirement.id,
                "key": requirement.key,
                "capability": requirement.capability,
                "minimum_count": requirement.minimum_count,
                "maximum_count": requirement.maximum_count,
            }
            for requirement in version.requirements.all()
        ],
        "supported_triggers": [trigger.kind for trigger in version.supported_triggers.all()],
    }


def get_module_catalog(realm: Realm) -> list[dict[str, Any]]:
    ensure_prebuilt_module_catalog(realm)
    versions = (
        ModuleVersion.objects.filter(definition__realm=realm)
        .select_related("definition")
        .prefetch_related("requirements", "supported_triggers")
        .order_by("navigation_order", "id")
    )
    return [module_version_data(version) for version in versions]


def installation_data(installation: ModuleInstallation) -> dict[str, Any]:
    version = installation.version
    return {
        "id": installation.id,
        "state": installation.state,
        "version_id": version.id,
        "definition_key": version.definition.stable_key,
        "name": version.definition.name,
        "version": version.version,
        "output_type": version.output_type,
        "destination_topic": version.destination_topic,
        "navigation_icon": version.navigation_icon,
        "navigation_order": version.navigation_order,
        "content_hash": version.content_hash,
        "activated_at": installation.activated_at.isoformat()
        if installation.activated_at
        else None,
        "processing_start_at": (
            installation.processing_start_at.isoformat()
            if installation.processing_start_at
            else None
        ),
        "activation_timezone": installation.activation_timezone,
        "policy_revision": installation.policy_revision,
        "policy_hash": installation.policy_hash,
        "predecessor_id": installation.predecessor_id,
        "bindings": [
            {
                "requirement_key": binding.requirement.key,
                "attachment_id": binding.attachment_id,
            }
            for binding in installation.bindings.all()
        ],
        "triggers": [
            {
                "kind": trigger.supported_trigger.kind,
                "cadence": trigger.cadence,
                "local_time": trigger.local_time.isoformat() if trigger.local_time else None,
                "timezone": trigger.timezone or None,
                "debounce_seconds": trigger.debounce_seconds,
            }
            for trigger in installation.triggers.all()
        ],
    }


def _assert_module_administrator(user: UserProfile, space: Space) -> None:
    if (
        user.realm_id != space.realm_id
        or not user_is_space_administrator(user, space)
        or not SpaceMembership.objects.filter(space=space, user=user, user__is_active=True).exists()
    ):
        raise JsonableError(_("You do not have permission to configure Modules for this Space."))


def _validate_timezone(value: str) -> None:
    try:
        ZoneInfo(value)
    except (ZoneInfoNotFoundError, ValueError):
        raise JsonableError(_("Invalid IANA timezone."))


def _trigger_policy(
    *,
    version: ModuleVersion,
    trigger_kind: str,
    cadence: str | None,
    local_time: time | None,
    timezone: str,
    debounce_seconds: int | None,
) -> tuple[ModuleSupportedTrigger, dict[str, Any]]:
    try:
        supported = version.supported_triggers.get(kind=trigger_kind)
    except ModuleSupportedTrigger.DoesNotExist:
        raise JsonableError(_("This Module version does not support that trigger."))
    if trigger_kind == ModuleSupportedTrigger.Kind.MANUAL:
        if cadence is not None or local_time is not None or debounce_seconds is not None:
            raise JsonableError(_("Manual triggers do not accept scheduling options."))
        return supported, {"kind": trigger_kind}
    if trigger_kind == ModuleSupportedTrigger.Kind.NEW_SOURCE:
        if cadence is not None or local_time is not None or debounce_seconds is None:
            raise JsonableError(_("New-source triggers require a bounded debounce."))
        if not 60 <= debounce_seconds <= 3600:
            raise JsonableError(_("New-source debounce must be between 60 and 3600 seconds."))
        return supported, {"kind": trigger_kind, "debounce_seconds": debounce_seconds}
    if cadence not in ModuleInstallationTrigger.Cadence.values or local_time is None:
        raise JsonableError(_("Scheduled triggers require a supported cadence and local time."))
    _validate_timezone(timezone)
    if debounce_seconds is not None:
        raise JsonableError(_("Scheduled triggers do not accept a debounce."))
    return supported, {
        "kind": trigger_kind,
        "cadence": cadence,
        "local_time": local_time.isoformat(),
        "timezone": timezone,
    }


def _validate_bindings(
    *, user: UserProfile, space: Space, version: ModuleVersion, attachment_ids: list[int]
) -> tuple[list[ModuleSourceRequirement], list[SpaceAttachment]]:
    requirements = list(version.requirements.all())
    if len(requirements) != 1:
        raise JsonableError(_("This Module version has an unsupported requirement contract."))
    requirement = requirements[0]
    if len(set(attachment_ids)) != len(attachment_ids):
        raise JsonableError(_("Each Source attachment may only be bound once."))
    if not requirement.minimum_count <= len(attachment_ids) <= requirement.maximum_count:
        raise JsonableError(_("The Source binding does not satisfy Module cardinality."))
    attachments = list(
        SpaceAttachment.objects.select_for_update(no_key=True, of=("self",))
        .select_related("source__account")
        .prefetch_related("source__capabilities")
        .filter(id__in=attachment_ids, space=space, state=SpaceAttachment.State.ACTIVE)
    )
    if len(attachments) != len(attachment_ids):
        raise JsonableError(_("Modules may only bind active Sources attached to this Space."))
    account_ids = {attachment.source.account_id for attachment in attachments}
    grants_by_account_id = {
        grant.account_id: grant
        for grant in ConnectedAccountGrant.objects.filter(
            account_id__in=account_ids,
            account__realm=user.realm,
            account__approval_state=ConnectedAccount.ApprovalState.APPROVED,
            user=user,
            state=ConnectedAccountGrant.State.ACTIVE,
        ).prefetch_related("selectors")
    }
    for attachment in attachments:
        grant = grants_by_account_id.get(attachment.source.account_id)
        if grant is None or (
            not grant.all_selectors
            and attachment.source.external_ref
            not in {selector.source_ref for selector in grant.selectors.all()}
        ):
            raise JsonableError(_("You may not administer a bound Source."))
        capabilities = {item.capability for item in attachment.source.capabilities.all()}
        if requirement.capability not in capabilities:
            raise JsonableError(_("An attached Source lacks a required Module capability."))
    return requirements, attachments


def _event_user_ids(space: Space) -> list[int]:
    if space.state == Space.State.SETUP:
        return list(
            SpaceAdministrator.objects.filter(space=space, user__is_active=True).values_list(
                "user_id", flat=True
            )
        )
    return list(
        SpaceMembership.objects.filter(space=space, user__is_active=True).values_list(
            "user_id", flat=True
        )
    )


def _send_space_update(space: Space) -> None:
    send_event_on_commit(
        space.realm,
        {"type": "hover_space", "op": "update", "space": get_space_data(space)},
        _event_user_ids(space),
    )


@transaction.atomic(durable=True)
def do_install_module(
    *,
    acting_user: UserProfile,
    space: Space,
    version_id: int,
    attachment_ids: list[int],
    trigger_kind: str,
    activation_timezone: str,
    cadence: str | None = None,
    local_time: time | None = None,
    debounce_seconds: int | None = None,
    backfill_start_at: datetime | None = None,
    backfill_confirmed: bool = False,
    predecessor: ModuleInstallation | None = None,
) -> tuple[ModuleInstallation, bool]:
    return _do_install_module(
        acting_user=acting_user,
        space=space,
        version_id=version_id,
        attachment_ids=attachment_ids,
        trigger_kind=trigger_kind,
        activation_timezone=activation_timezone,
        cadence=cadence,
        local_time=local_time,
        debounce_seconds=debounce_seconds,
        backfill_start_at=backfill_start_at,
        backfill_confirmed=backfill_confirmed,
        predecessor=predecessor,
    )


def _do_install_module(
    *,
    acting_user: UserProfile,
    space: Space,
    version_id: int,
    attachment_ids: list[int],
    trigger_kind: str,
    activation_timezone: str,
    cadence: str | None = None,
    local_time: time | None = None,
    debounce_seconds: int | None = None,
    backfill_start_at: datetime | None = None,
    backfill_confirmed: bool = False,
    predecessor: ModuleInstallation | None = None,
) -> tuple[ModuleInstallation, bool]:
    locked_space = Space.objects.select_for_update(no_key=True).get(id=space.id)
    _assert_module_administrator(acting_user, locked_space)
    _validate_timezone(activation_timezone)
    try:
        version = (
            ModuleVersion.objects.select_for_update(no_key=True, of=("self",))
            .select_related("definition")
            .prefetch_related("requirements", "supported_triggers")
            .get(id=version_id, definition__realm=locked_space.realm)
        )
    except ModuleVersion.DoesNotExist:
        raise JsonableError(_("Invalid Module version."))
    requirements, attachments = _validate_bindings(
        user=acting_user,
        space=locked_space,
        version=version,
        attachment_ids=attachment_ids,
    )
    supported_trigger, trigger_policy = _trigger_policy(
        version=version,
        trigger_kind=trigger_kind,
        cadence=cadence,
        local_time=local_time,
        timezone=activation_timezone,
        debounce_seconds=debounce_seconds,
    )
    configured_at = timezone_now()
    if backfill_start_at is not None:
        if is_naive(backfill_start_at):
            raise JsonableError(_("Backfill start must include a timezone offset."))
        if not backfill_confirmed or backfill_start_at >= configured_at:
            raise JsonableError(_("Earlier backfill requires an explicit bounded confirmation."))
        if any(backfill_start_at < attachment.history_start_at for attachment in attachments):
            raise JsonableError(_("Backfill starts before an attached Source is available."))
    elif backfill_confirmed:
        raise JsonableError(_("Backfill confirmation requires an earlier start time."))
    policy = {
        "version_id": version.id,
        "attachment_ids": sorted(attachment_ids),
        "trigger": trigger_policy,
        "activation_timezone": activation_timezone,
        "backfill_start_at": backfill_start_at.isoformat() if backfill_start_at else None,
        "backfill_confirmed": backfill_confirmed,
    }
    policy_hash = _canonical_hash(policy)
    current = (
        ModuleInstallation.objects.select_for_update(no_key=True)
        .filter(
            space=locked_space,
            version__definition=version.definition,
            state__in=[
                ModuleInstallation.State.CONFIGURED,
                ModuleInstallation.State.ENABLED,
                ModuleInstallation.State.PAUSED_DETACHED,
            ],
        )
        .first()
    )
    if current is not None:
        if current.version_id == version.id and current.policy_hash == policy_hash:
            return current, False
        raise ModuleConfigurationConflictError(
            _("This Space already has a different current configuration for that Module.")
        )
    activated_at = configured_at if locked_space.state == Space.State.LAUNCHED else None
    installation = ModuleInstallation.objects.create(
        realm=locked_space.realm,
        space=locked_space,
        version=version,
        state=(
            ModuleInstallation.State.ENABLED
            if locked_space.state == Space.State.LAUNCHED
            else ModuleInstallation.State.CONFIGURED
        ),
        activation_timezone=activation_timezone,
        activated_at=activated_at,
        processing_start_at=backfill_start_at or activated_at,
        backfill_confirmed=backfill_confirmed,
        policy_hash=policy_hash,
        configured_by=acting_user,
        predecessor=predecessor,
    )
    ModuleInstallationBinding.objects.bulk_create(
        [
            ModuleInstallationBinding(
                installation=installation,
                requirement=requirements[0],
                attachment=attachment,
            )
            for attachment in attachments
        ]
    )
    ModuleInstallationTrigger.objects.create(
        installation=installation,
        supported_trigger=supported_trigger,
        cadence=cadence,
        local_time=local_time,
        timezone=activation_timezone
        if trigger_kind == ModuleSupportedTrigger.Kind.SCHEDULE
        else "",
        debounce_seconds=debounce_seconds,
    )
    _send_space_update(locked_space)
    return installation, True


@transaction.atomic(durable=True)
def do_disable_module(
    installation: ModuleInstallation, *, acting_user: UserProfile
) -> tuple[ModuleInstallation, bool]:
    locked_space = Space.objects.select_for_update(no_key=True).get(id=installation.space_id)
    _assert_module_administrator(acting_user, locked_space)
    current = ModuleInstallation.objects.select_for_update(no_key=True).get(id=installation.id)
    if current.state == ModuleInstallation.State.DISABLED:
        return current, False
    current.state = ModuleInstallation.State.DISABLED
    current.disabled_by = acting_user
    current.save(update_fields=["state", "disabled_by", "date_updated"])
    _send_space_update(locked_space)
    return current, True


@transaction.atomic(durable=True)
def do_upgrade_module(
    *, installation: ModuleInstallation, acting_user: UserProfile, version_id: int, **kwargs: Any
) -> tuple[ModuleInstallation, bool]:
    locked_space = Space.objects.select_for_update(no_key=True).get(id=installation.space_id)
    _assert_module_administrator(acting_user, locked_space)
    current = (
        ModuleInstallation.objects.select_for_update(no_key=True)
        .select_related("version__definition")
        .get(id=installation.id, space=locked_space)
    )
    try:
        successor = current.successor
    except ModuleInstallation.DoesNotExist:
        successor = None
    if successor is not None:
        if successor.version_id == version_id:
            return successor, False
        raise ModuleConfigurationConflictError(_("This Module installation was already upgraded."))
    try:
        new_version = (
            ModuleVersion.objects.select_for_update(no_key=True, of=("self",))
            .select_related("definition")
            .get(id=version_id, definition__realm=locked_space.realm)
        )
    except ModuleVersion.DoesNotExist:
        raise JsonableError(_("Invalid Module version."))
    if (
        new_version.definition_id != current.version.definition_id
        or new_version.id == current.version_id
        or new_version.published_at <= current.version.published_at
    ):
        raise JsonableError(_("An upgrade must select a newer version of the same Module."))
    current.state = ModuleInstallation.State.DISABLED
    current.disabled_by = acting_user
    current.save(update_fields=["state", "disabled_by", "date_updated"])
    return _do_install_module(
        acting_user=acting_user,
        space=locked_space,
        version_id=version_id,
        predecessor=current,
        **kwargs,
    )


@transaction.atomic(savepoint=False)
def pause_installations_for_attachment(attachment: SpaceAttachment) -> None:
    installations = list(
        ModuleInstallation.objects.select_for_update(no_key=True).filter(
            bindings__attachment=attachment,
            state__in=[ModuleInstallation.State.ENABLED, ModuleInstallation.State.CONFIGURED],
        )
    )
    for installation in installations:
        if installation.state == ModuleInstallation.State.ENABLED:
            installation.state = ModuleInstallation.State.PAUSED_DETACHED
            installation.save(update_fields=["state", "date_updated"])
        else:
            installation.state = ModuleInstallation.State.DISABLED
            installation.save(update_fields=["state", "date_updated"])


@transaction.atomic(durable=True)
def do_rebind_resume_module(
    *,
    installation: ModuleInstallation,
    acting_user: UserProfile,
    attachment_ids: list[int],
) -> ModuleInstallation:
    locked_space = Space.objects.select_for_update(no_key=True).get(id=installation.space_id)
    _assert_module_administrator(acting_user, locked_space)
    current = (
        ModuleInstallation.objects.select_for_update(no_key=True)
        .select_related("version__definition")
        .prefetch_related("version__requirements", "triggers__supported_trigger")
        .get(id=installation.id, space=locked_space)
    )
    try:
        existing_successor = current.successor
    except ModuleInstallation.DoesNotExist:
        existing_successor = None
    if existing_successor is not None:
        existing_attachment_ids = set(
            existing_successor.bindings.values_list("attachment_id", flat=True)
        )
        if existing_attachment_ids == set(attachment_ids):
            return existing_successor
        raise ModuleConfigurationConflictError(
            _("This paused Module was already rebound with a different configuration.")
        )
    if current.state != ModuleInstallation.State.PAUSED_DETACHED:
        raise JsonableError(_("Only a paused Module installation can be rebound."))
    trigger = current.triggers.get()
    current.state = ModuleInstallation.State.DISABLED
    current.disabled_by = acting_user
    current.save(update_fields=["state", "disabled_by", "date_updated"])
    successor, created = _do_install_module(
        acting_user=acting_user,
        space=locked_space,
        version_id=current.version_id,
        attachment_ids=attachment_ids,
        trigger_kind=trigger.supported_trigger.kind,
        activation_timezone=current.activation_timezone,
        cadence=trigger.cadence,
        local_time=trigger.local_time,
        debounce_seconds=trigger.debounce_seconds,
        backfill_start_at=(current.processing_start_at if current.backfill_confirmed else None),
        backfill_confirmed=current.backfill_confirmed,
        predecessor=current,
    )
    assert created
    return successor
