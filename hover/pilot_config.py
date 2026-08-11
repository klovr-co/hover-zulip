"""Strict, versioned configuration for controlled Hover pilot rollouts."""

from __future__ import annotations

import json
from datetime import datetime, time
from pathlib import Path
from typing import Any, Literal
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import orjson
from django.conf import settings
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from hover.actions_integrations import do_associate_integration_route
from hover.actions_modules import do_install_module, ensure_prebuilt_module_catalog
from hover.actions_spaces import do_launch_space
from hover.models import (
    ConnectedAccount,
    ConnectedAccountGrant,
    ConnectedAccountGrantSelector,
    IntegrationRouteAssociation,
    ModuleInstallation,
    ModuleVersion,
    Source,
    SourceCapability,
    SourceParticipantBinding,
    Space,
    SpaceAdministrator,
    SpaceAttachment,
    SpaceMembership,
)
from zerver.lib.channel_folders import render_channel_folder_description
from zerver.lib.exceptions import JsonableError
from zerver.models.channel_folders import ChannelFolder
from zerver.models.realms import Realm
from zerver.models.streams import Subscription
from zerver.models.users import UserProfile

REQUIRED_MODULE_KEYS = frozenset(
    {
        "conversation_digest",
        "progress_tracker",
        "suggested_actions",
        "decisions",
        "marketing_digest",
        "topic_analysis",
    }
)
FORBIDDEN_MODULE_KEYS = frozenset({"email", "weekly_roundup", "ai_slides", "topics_you_follow"})
ACCEPTANCE_GATE_KEYS = (
    "access",
    "duplication",
    "evidence",
    "audit_history",
    "notifications",
    "voluntary_use",
)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PilotMetadata(StrictModel):
    schema_version: Literal["hover-pilot/v1"]
    pilot_key: str = Field(pattern=r"^[a-z][a-z0-9_-]{2,63}$")
    realm: str = Field(min_length=1, max_length=40)
    operator_email: str = Field(min_length=3, max_length=254)
    private_config: bool


class CategorySpec(StrictModel):
    name: str = Field(min_length=1, max_length=60)
    description: str = Field(max_length=1024)


class SpaceSpec(StrictModel):
    name: str = Field(min_length=1, max_length=60)
    description: str = Field(max_length=1024)
    launch: bool = False


class AccountSpec(StrictModel):
    key: str = Field(pattern=r"^[a-z][a-z0-9_]{1,31}$")
    provider_key: str = Field(pattern=r"^[a-z][a-z0-9_]{0,31}$")
    provider_name: str = Field(min_length=1, max_length=60)
    external_account_id: UUID
    display_name: str = Field(min_length=1, max_length=100)
    connection_kind: Literal["remote_studio", "native_integration"]
    incoming_webhook_bot_email: str | None = None
    approval_reviewed: Literal[True]

    @model_validator(mode="after")
    def validate_bot_boundary(self) -> AccountSpec:
        if (self.connection_kind == "native_integration") != (
            self.incoming_webhook_bot_email is not None
        ):
            raise ValueError("Only native integration accounts require an incoming webhook bot")
        return self


class HistorySpec(StrictModel):
    timezone: str = Field(min_length=1, max_length=64)
    start_at: datetime

    @field_validator("start_at")
    @classmethod
    def require_offset(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("History start_at must include a UTC offset")
        return value

    @field_validator("timezone")
    @classmethod
    def require_iana_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError):
            raise ValueError("History timezone must be a valid IANA timezone")
        return value


class SourceSpec(StrictModel):
    key: str = Field(pattern=r"^[a-z][a-z0-9_]{1,63}$")
    account_key: str
    source_ref: str = Field(pattern=r"^src_[0-9a-f]{32}$")
    adapter_key: str = Field(pattern=r"^[a-z][a-z0-9_]{0,31}$")
    provider_key: str = Field(pattern=r"^[a-z][a-z0-9_]{0,31}$")
    provider_name: str = Field(min_length=1, max_length=60)
    source_type: str = Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")
    display_name: str = Field(min_length=1, max_length=100)
    external_url: str = ""
    supports_live_capture: bool = False
    capabilities: list[Literal["message_history"]]
    history: HistorySpec

    @field_validator("external_url")
    @classmethod
    def validate_external_url(cls, value: str) -> str:
        if value and not value.startswith("https://"):
            raise ValueError("Source URLs must use HTTPS")
        return value

    @field_validator("capabilities")
    @classmethod
    def unique_capabilities(cls, value: list[str]) -> list[str]:
        if not value or len(value) != len(set(value)):
            raise ValueError("Sources require unique explicit capabilities")
        return value


class GrantSpec(StrictModel):
    account_key: str
    user_email: str
    source_keys: list[str] = Field(min_length=1)
    reviewed: Literal[True]

    @field_validator("source_keys")
    @classmethod
    def unique_sources(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("Grant source_keys must be unique")
        return value


class MembershipSpec(StrictModel):
    user_email: str
    role: Literal["contributor", "subscriber"]
    administrator: bool = False
    pilot_cohort: bool = False
    personal_editions: bool = False
    reviewed: Literal[True]

    @model_validator(mode="after")
    def validate_cohort(self) -> MembershipSpec:
        if self.personal_editions != self.pilot_cohort:
            raise ValueError("Personal editions must match the exact pilot cohort")
        return self


class ParticipantMappingSpec(StrictModel):
    source_key: str
    participant_ref: str = Field(pattern=r"^person_[0-9a-f]{32}$")
    user_email: str
    match_basis: Literal["verified_email", "verified_phone"]
    observation_basis: str = Field(pattern=r"^obs_[0-9a-f]{32}$")
    reviewed: Literal[True]


class ProvenanceRouteSpec(StrictModel):
    source_key: str
    bot_email: str
    allowed_actors: list[str] = Field(min_length=1)
    repository_allowlist: list[str] = Field(default_factory=list)
    event_allowlist: list[str] = Field(min_length=1)
    external_configuration_reviewed: Literal[True]

    @field_validator("allowed_actors", "repository_allowlist", "event_allowlist")
    @classmethod
    def unique_values(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("Provenance allowlists must not contain duplicates")
        return value


class TriggerSpec(StrictModel):
    kind: Literal["manual", "new_source", "schedule"]
    cadence: Literal["daily", "weekly"] | None = None
    local_time: time | None = None
    timezone: str = "UTC"
    debounce_seconds: int | None = Field(default=None, ge=60, le=3600)

    @field_validator("timezone")
    @classmethod
    def require_iana_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError):
            raise ValueError("Trigger timezone must be a valid IANA timezone")
        return value

    @model_validator(mode="after")
    def validate_trigger(self) -> TriggerSpec:
        if self.kind == "manual" and any(
            value is not None for value in (self.cadence, self.local_time, self.debounce_seconds)
        ):
            raise ValueError("Manual triggers do not accept scheduling options")
        if self.kind == "new_source" and (
            self.debounce_seconds is None or self.cadence is not None or self.local_time is not None
        ):
            raise ValueError("New-source triggers require only a bounded debounce")
        if self.kind == "schedule" and (
            self.cadence is None or self.local_time is None or self.debounce_seconds is not None
        ):
            raise ValueError("Scheduled triggers require cadence and local_time")
        return self


class ModuleSpec(StrictModel):
    key: str
    version: Literal["1.0.0"] = "1.0.0"
    enabled: bool
    source_keys: list[str]
    trigger: TriggerSpec


class PersonalEditionSpec(StrictModel):
    morning_daily_brief: Literal[True]
    end_of_day_roundup: Literal[True]


class ShadowModeSpec(StrictModel):
    mode: Literal["shadow"]
    comparison_system: Literal["monday"]
    review_writeback: Literal[False]
    todo_writeback: Literal[False]
    allowed_external_writes: list[Literal["never"]] = Field(max_length=0)


class AcceptanceGate(StrictModel):
    key: Literal[
        "access",
        "duplication",
        "evidence",
        "audit_history",
        "notifications",
        "voluntary_use",
    ]
    status: Literal["pending", "passed"]
    evidence: str = Field(min_length=1, max_length=500)


class SanitizedSmokeSpec(StrictModel):
    source_key: str
    fixture_key: str = Field(pattern=r"^[a-z][a-z0-9_-]{2,63}$")
    contains_real_source_content: Literal[False]
    expected_path: list[
        Literal[
            "generated_update",
            "review",
            "confirmed_todo",
            "home_awareness",
            "personal_edition",
        ]
    ]

    @field_validator("expected_path")
    @classmethod
    def validate_path(cls, value: list[str]) -> list[str]:
        expected = [
            "generated_update",
            "review",
            "confirmed_todo",
            "home_awareness",
            "personal_edition",
        ]
        if value != expected:
            raise ValueError("Smoke path must cover every pilot product boundary in order")
        return value


class HoverPilotConfigV1(StrictModel):
    metadata: PilotMetadata
    category: CategorySpec
    space: SpaceSpec
    accounts: list[AccountSpec]
    sources: list[SourceSpec]
    grants: list[GrantSpec]
    memberships: list[MembershipSpec]
    participant_mappings: list[ParticipantMappingSpec]
    provenance_routes: list[ProvenanceRouteSpec]
    modules: list[ModuleSpec]
    forbidden_modules: list[str]
    personal_editions: PersonalEditionSpec
    shadow_mode: ShadowModeSpec
    acceptance_gates: list[AcceptanceGate]
    development_smoke: SanitizedSmokeSpec

    @model_validator(mode="after")
    def validate_rollout_contract(self) -> HoverPilotConfigV1:
        account_by_key = _unique_by(self.accounts, "key", "account")
        source_by_key = _unique_by(self.sources, "key", "source")
        membership_by_email = _unique_by(self.memberships, "user_email", "membership")
        module_by_key = _unique_by(self.modules, "key", "module")

        if set(self.forbidden_modules) != FORBIDDEN_MODULE_KEYS:
            raise ValueError("forbidden_modules must contain the complete canonical denylist")
        required = {key for key, module in module_by_key.items() if module.enabled}
        if required != REQUIRED_MODULE_KEYS:
            raise ValueError("Exactly the six required pilot Modules must be enabled")
        signal = module_by_key.get("signal_monitor")
        if signal is None or signal.enabled or signal.source_keys:
            raise ValueError("Signal Monitor must be available but uninstalled/off")
        if set(module_by_key) != REQUIRED_MODULE_KEYS | {"signal_monitor"}:
            raise ValueError("Pilot modules must not contain non-approved entries")

        whatsapp_sources = [source for source in self.sources if source.provider_key == "whatsapp"]
        if len(whatsapp_sources) != 3:
            raise ValueError("The pilot requires exactly three permitted WhatsApp Sources")
        native_providers = {
            source.provider_key for source in self.sources if source.supports_live_capture
        }
        if native_providers != {"apify", "github"}:
            raise ValueError("The pilot requires reviewed Apify and GitHub provenance Sources")
        for source in self.sources:
            account = account_by_key.get(source.account_key)
            if account is None or account.provider_key != source.provider_key:
                raise ValueError(f"Source {source.key} references an incompatible account")
            if source.supports_live_capture != (account.connection_kind == "native_integration"):
                raise ValueError(f"Source {source.key} has an invalid live-capture setting")

        referenced_grants: set[tuple[str, str]] = set()
        for grant in self.grants:
            if grant.account_key not in account_by_key:
                raise ValueError(f"Grant references unknown account {grant.account_key}")
            if grant.user_email.casefold() not in membership_by_email:
                raise ValueError("Grants may only target reviewed pilot members")
            if (grant.account_key, grant.user_email.casefold()) in referenced_grants:
                raise ValueError("Each account/user grant must be configured once")
            referenced_grants.add((grant.account_key, grant.user_email.casefold()))
            if any(
                key not in source_by_key or source_by_key[key].account_key != grant.account_key
                for key in grant.source_keys
            ):
                raise ValueError("Grant source_keys must belong to its account")
        operator_grants = {
            grant.account_key: set(grant.source_keys)
            for grant in self.grants
            if grant.user_email.casefold() == self.metadata.operator_email.casefold()
        }
        for account_key in account_by_key:
            expected_sources = {
                source.key for source in self.sources if source.account_key == account_key
            }
            if operator_grants.get(account_key) != expected_sources:
                raise ValueError("The operator requires an explicit grant for every pilot Source")

        mapped_emails: set[str] = set()
        for mapping in self.participant_mappings:
            if mapping.source_key not in source_by_key:
                raise ValueError("Participant mapping references an unknown Source")
            if mapping.user_email.casefold() not in membership_by_email:
                raise ValueError("Participant mapping targets an unreviewed teammate")
            mapped_emails.add(mapping.user_email.casefold())
        for membership in self.memberships:
            if (
                membership.personal_editions
                and membership.user_email.casefold() not in mapped_emails
            ):
                raise ValueError("Personal-edition cohort members require a reviewed mapping")
        edition_emails = {
            membership.user_email.casefold()
            for membership in self.memberships
            if membership.personal_editions
        }
        if mapped_emails != edition_emails:
            raise ValueError(
                "Reviewed participant mappings define the exact personal-edition cohort"
            )
        if not any(member.administrator for member in self.memberships):
            raise ValueError("The pilot needs at least one reviewed Space Administrator")

        routed_sources: set[str] = set()
        for route in self.provenance_routes:
            route_source = source_by_key.get(route.source_key)
            if route_source is None or not route_source.supports_live_capture:
                raise ValueError("Provenance routes require a native live-capture Source")
            account = account_by_key[route_source.account_key]
            if account.incoming_webhook_bot_email != route.bot_email:
                raise ValueError("Route bot must match its Connected Account")
            if route_source.provider_key == "github" and not route.repository_allowlist:
                raise ValueError("GitHub routes require an explicit repository allowlist")
            if route.source_key in routed_sources:
                raise ValueError("Each native Source may have one provenance route")
            routed_sources.add(route.source_key)
        native_sources = {source.key for source in self.sources if source.supports_live_capture}
        if routed_sources != native_sources:
            raise ValueError("Every native Source requires exactly one reviewed route")

        for module in self.modules:
            if module.enabled and (
                not module.source_keys
                or any(key not in source_by_key for key in module.source_keys)
            ):
                raise ValueError(f"Enabled Module {module.key} needs valid Source bindings")
        if self.development_smoke.source_key not in source_by_key:
            raise ValueError("Development smoke fixture references an unknown Source")

        gates = _unique_by(self.acceptance_gates, "key", "acceptance gate")
        if set(gates) != set(ACCEPTANCE_GATE_KEYS):
            raise ValueError("The operational acceptance checklist is incomplete")
        return self


def _unique_by(items: list[Any], attribute: str, label: str) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for item in items:
        key = getattr(item, attribute)
        normalized = key.casefold() if isinstance(key, str) else key
        if normalized in result:
            raise ValueError(f"Duplicate {label} {key}")
        result[normalized] = item
    return result


def load_pilot_config(path: Path, *, require_private: bool = False) -> HoverPilotConfigV1:
    try:
        payload = orjson.loads(path.read_bytes())
        config = HoverPilotConfigV1.model_validate(payload)
    except (OSError, orjson.JSONDecodeError, ValidationError) as error:
        raise ValueError(f"Invalid pilot config: {error}")
    if require_private and (
        not config.metadata.private_config or not path.name.endswith(".private.json")
    ):
        raise ValueError("Apply requires a validated file ending in .private.json")
    return config


class PilotConfigError(Exception):
    pass


class PilotReconciler:
    def __init__(self, *, realm: Realm, config: HoverPilotConfigV1) -> None:
        self.realm = realm
        self.config = config
        self.actions: list[str] = []
        self.users: dict[str, UserProfile] = {}
        self.bots: dict[str, UserProfile] = {}

    def validate_database(self) -> dict[str, Any]:
        if self.config.metadata.realm != self.realm.string_id:
            raise PilotConfigError("Config realm does not match --realm")
        emails = {member.user_email.casefold() for member in self.config.memberships}
        users = list(UserProfile.objects.filter(realm=self.realm, delivery_email__in=emails))
        self.users = {user.delivery_email.casefold(): user for user in users}
        if set(self.users) != emails:
            missing = sorted(emails - set(self.users))
            raise PilotConfigError(f"Unknown teammate(s): {', '.join(missing)}")
        for user in self.users.values():
            if not user.is_active or user.is_bot or user.is_guest:
                raise PilotConfigError("Pilot members must be active internal teammates")
        operator = self.users.get(self.config.metadata.operator_email.casefold())
        if operator is None or not operator.is_realm_admin:
            raise PilotConfigError("The operator must be a reviewed organization administrator")

        bot_emails = {
            account.incoming_webhook_bot_email.casefold()
            for account in self.config.accounts
            if account.incoming_webhook_bot_email is not None
        }
        bots = list(UserProfile.objects.filter(realm=self.realm, delivery_email__in=bot_emails))
        self.bots = {bot.delivery_email.casefold(): bot for bot in bots}
        if set(self.bots) != bot_emails:
            raise PilotConfigError("Every native route must reference an existing bot")
        for bot in self.bots.values():
            if (
                not bot.is_active
                or not bot.is_bot
                or bot.bot_type != UserProfile.INCOMING_WEBHOOK_BOT
            ):
                raise PilotConfigError("Provenance routes require active incoming webhook bots")

        self._validate_account_grant_exactness()
        existing = Space.objects.filter(
            realm=self.realm, name__iexact=self.config.space.name
        ).first()
        if existing is not None:
            self._validate_existing_exactness(existing)
        self.actions = [
            "reconcile Category and Space",
            "reconcile approved Connected Accounts and least-privilege grants",
            "reconcile Sources and explicit history attachments",
            "reconcile reviewed internal memberships, administrators, and mappings",
            "reconcile six required Module installations; keep Signal Monitor off",
            "reconcile reviewed native provenance routes after launch",
        ]
        return self.report()

    def _validate_account_grant_exactness(self) -> None:
        source_specs = {spec.key: spec for spec in self.config.sources}
        accounts = {
            spec.key: ConnectedAccount.objects.filter(
                realm=self.realm,
                provider_key=spec.provider_key,
                external_account_id=spec.external_account_id,
            ).first()
            for spec in self.config.accounts
        }
        desired_grants: dict[str, dict[str, GrantSpec]] = {}
        for grant in self.config.grants:
            desired_grants.setdefault(grant.account_key, {})[grant.user_email.casefold()] = grant
        for account_key, account in accounts.items():
            if account is None:
                continue
            expected_by_user = desired_grants.get(account_key, {})
            active_grants = list(
                account.grants.filter(state=ConnectedAccountGrant.State.ACTIVE)
                .select_related("user")
                .prefetch_related("selectors")
            )
            actual_users = {
                active_grant.user.delivery_email.casefold() for active_grant in active_grants
            }
            if actual_users - set(expected_by_user):
                raise PilotConfigError("Configured account contains an unreviewed active grant")
            for active_grant in active_grants:
                if active_grant.all_selectors:
                    raise PilotConfigError("Configured account grant is broader than the pilot")
                grant_spec = expected_by_user[active_grant.user.delivery_email.casefold()]
                expected_selectors = {
                    (
                        "whatsapp_group"
                        if source_specs[source_key].provider_key == "whatsapp"
                        else source_specs[source_key].source_type,
                        source_specs[source_key].source_ref,
                    )
                    for source_key in grant_spec.source_keys
                }
                actual_selectors = {
                    (selector.selector_type, selector.source_ref)
                    for selector in active_grant.selectors.all()
                }
                if actual_selectors - expected_selectors:
                    raise PilotConfigError(
                        "Configured account grant contains an unreviewed selector"
                    )

    def _validate_existing_exactness(self, space: Space) -> None:
        expected_members = {
            member.user_email.casefold(): member for member in self.config.memberships
        }
        expected_roles = {email: member.role for email, member in expected_members.items()}
        actual_roles = {
            membership.user.delivery_email.casefold(): membership.role
            for membership in space.memberships.select_related("user")
        }
        if set(actual_roles) - set(expected_roles):
            raise PilotConfigError("Space contains an unreviewed membership")
        if space.state == Space.State.LAUNCHED and actual_roles != expected_roles:
            raise PilotConfigError("A launched Space's reviewed membership cohort cannot drift")

        expected_personal_editions = {
            email: member.personal_editions for email, member in expected_members.items()
        }
        actual_personal_editions = {
            membership.user.delivery_email.casefold(): membership.personal_editions_enabled
            for membership in space.memberships.select_related("user")
        }
        if any(
            enabled and not expected_personal_editions.get(email, False)
            for email, enabled in actual_personal_editions.items()
        ):
            raise PilotConfigError("Space contains an unreviewed Personal Edition enrollment")
        if (
            space.state == Space.State.LAUNCHED
            and actual_personal_editions != expected_personal_editions
        ):
            raise PilotConfigError("A launched Space's Personal Edition cohort cannot drift")

        expected_administrators = {
            email for email, member in expected_members.items() if member.administrator
        }
        actual_administrators = {
            assignment.user.delivery_email.casefold()
            for assignment in space.administrator_assignments.select_related("user")
        }
        if actual_administrators - expected_administrators:
            raise PilotConfigError("Space contains an unreviewed administrator")
        if space.state == Space.State.LAUNCHED and actual_administrators != expected_administrators:
            raise PilotConfigError("A launched Space's reviewed administrators cannot drift")

        if space.state == Space.State.LAUNCHED:
            assert space.stream is not None
            subscriptions = list(
                Subscription.objects.filter(recipient=space.stream.recipient, active=True)
                .select_related("user_profile")
                .order_by("user_profile_id")
            )
            native_members = {
                subscription.user_profile.delivery_email.casefold(): subscription.user_profile
                for subscription in subscriptions
                if not subscription.user_profile.is_bot
            }
            if set(native_members) != set(expected_members) or any(
                user.is_guest for user in native_members.values()
            ):
                raise PilotConfigError("Launched Space subscriptions contain an unreviewed user")
            allowed_bot_emails = set(self.bots)
            configured_assistant = str(settings.HOVER_ASSISTANT_EMAIL).strip().casefold()
            if configured_assistant:
                allowed_bot_emails.add(configured_assistant)
            unexpected_bots = [
                subscription.user_profile
                for subscription in subscriptions
                if subscription.user_profile.is_bot
                and subscription.user_profile.delivery_email.casefold() not in allowed_bot_emails
            ]
            if unexpected_bots:
                raise PilotConfigError("Launched Space subscriptions contain an unreviewed bot")

        account_specs = {spec.key: spec for spec in self.config.accounts}
        source_specs = {spec.key: spec for spec in self.config.sources}
        expected_attachment_keys = {
            (account_specs[source.account_key].external_account_id, source.source_ref)
            for source in self.config.sources
        }
        actual_attachments = list(
            space.attachments.filter(state=SpaceAttachment.State.ACTIVE).select_related(
                "source__account"
            )
        )
        actual_attachment_keys = {
            (attachment.source.account.external_account_id, attachment.source.external_ref)
            for attachment in actual_attachments
        }
        if actual_attachment_keys - expected_attachment_keys:
            raise PilotConfigError("Space contains an unreviewed active Source attachment")

        configured_sources = Source.objects.filter(
            realm=self.realm,
            external_ref__in=[source.source_ref for source in self.config.sources],
        ).select_related("account")
        configured_source_by_key = {
            (source.account.external_account_id, source.external_ref): source
            for source in configured_sources
        }
        expected_bindings = {
            (
                account_specs[source_specs[mapping.source_key].account_key].external_account_id,
                source_specs[mapping.source_key].source_ref,
                mapping.participant_ref,
                mapping.user_email.casefold(),
            )
            for mapping in self.config.participant_mappings
        }
        actual_bindings = {
            (
                binding.source.account.external_account_id,
                binding.source.external_ref,
                binding.participant_ref,
                binding.user.delivery_email.casefold(),
            )
            for binding in SourceParticipantBinding.objects.filter(
                source_id__in=[source.id for source in configured_source_by_key.values()],
            ).select_related("source__account", "user")
        }
        if actual_bindings - expected_bindings:
            raise PilotConfigError("Configured Sources contain an unreviewed participant mapping")
        if space.state == Space.State.LAUNCHED and actual_bindings != expected_bindings:
            raise PilotConfigError("A launched Space's reviewed cohort mappings cannot drift")

        current_installations = list(
            ModuleInstallation.objects.filter(
                space=space,
                state__in=[
                    ModuleInstallation.State.CONFIGURED,
                    ModuleInstallation.State.ENABLED,
                    ModuleInstallation.State.PAUSED_DETACHED,
                ],
            ).select_related("version__definition")
        )
        current_module_keys = [
            installation.version.definition.stable_key for installation in current_installations
        ]
        if (
            len(current_module_keys) != len(set(current_module_keys))
            or set(current_module_keys) - REQUIRED_MODULE_KEYS
        ):
            raise PilotConfigError("Space contains an unreviewed current Module installation")
        if any(
            installation.state == ModuleInstallation.State.PAUSED_DETACHED
            for installation in current_installations
        ):
            raise PilotConfigError("Space contains a paused Module requiring explicit review")

        expected_routes = {
            source_specs[route.source_key].source_ref: route.bot_email.casefold()
            for route in self.config.provenance_routes
        }
        active_routes = IntegrationRouteAssociation.objects.filter(
            attachment__space=space,
            state=IntegrationRouteAssociation.State.ACTIVE,
        ).select_related("attachment__source", "bot")
        for route in active_routes:
            expected_bot = expected_routes.get(route.attachment.source.external_ref)
            if expected_bot is None or route.bot.delivery_email.casefold() != expected_bot:
                raise PilotConfigError("Space contains an unreviewed active provenance route")

    def report(self) -> dict[str, Any]:
        expansion_ready = self.config.space.launch and all(
            gate.status == "passed" for gate in self.config.acceptance_gates
        )
        rollout_phase = (
            "setup"
            if not self.config.space.launch
            else "expansion_ready"
            if expansion_ready
            else "shadow"
        )
        return {
            "schema_version": self.config.metadata.schema_version,
            "pilot_key": self.config.metadata.pilot_key,
            "realm": self.realm.string_id,
            "mode": self.config.shadow_mode.mode,
            "rollout_phase": rollout_phase,
            "expansion_ready": expansion_ready,
            "counts": {
                "accounts": len(self.config.accounts),
                "sources": len(self.config.sources),
                "whatsapp_sources": sum(
                    source.provider_key == "whatsapp" for source in self.config.sources
                ),
                "routes": len(self.config.provenance_routes),
                "members": len(self.config.memberships),
                "cohort": sum(member.pilot_cohort for member in self.config.memberships),
                "enabled_modules": sum(module.enabled for module in self.config.modules),
            },
            "external_route_controls": [
                {
                    "source_key": route.source_key,
                    "allowed_actor_count": len(route.allowed_actors),
                    "repository_count": len(route.repository_allowlist),
                    "event_count": len(route.event_allowlist),
                    "reviewed": route.external_configuration_reviewed,
                }
                for route in self.config.provenance_routes
            ],
            "shadow_writeback": {"reviews_to_monday": False, "todos_to_monday": False},
            "acceptance_gates": [gate.model_dump() for gate in self.config.acceptance_gates],
            "planned_actions": self.actions,
        }

    def apply(self) -> dict[str, Any]:
        self.validate_database()
        self.actions = []
        operator = self.users[self.config.metadata.operator_email.casefold()]
        with transaction.atomic(durable=True):
            if not self.realm.hover_enabled:
                self.realm.hover_enabled = True
                self.realm.save(update_fields=["hover_enabled"])
                self.actions.append("enable Hover for realm")
            category = self._reconcile_category(operator)
            space = self._reconcile_space(operator, category)
            accounts = self._reconcile_accounts(operator)
            sources = self._reconcile_sources(accounts)
            attachments = self._reconcile_attachments(operator, space, sources)
            self._reconcile_grants(operator, accounts, sources)
            self._reconcile_memberships(operator, space)
            self._reconcile_participant_mappings(sources)
        self._reconcile_modules(operator, space, attachments)
        if self.config.space.launch:
            space, launched = do_launch_space(space, acting_user=operator)
            if launched:
                self.actions.append("launch Space with reviewed cohort")
            self._reconcile_routes(operator, space, attachments)
        return self.report()

    def _reconcile_category(self, operator: UserProfile) -> ChannelFolder:
        category = ChannelFolder.objects.filter(
            realm=self.realm, name__iexact=self.config.category.name, is_archived=False
        ).first()
        if category is None:
            rendered_description = render_channel_folder_description(
                self.config.category.description, self.realm, acting_user=operator
            )
            category = ChannelFolder.objects.create(
                realm=self.realm,
                name=self.config.category.name,
                description=self.config.category.description,
                rendered_description=rendered_description,
                creator=operator,
            )
            category.order = category.id
            category.save(update_fields=["order"])
            self.actions.append("create Category")
        elif category.description != self.config.category.description:
            rendered_description = render_channel_folder_description(
                self.config.category.description, self.realm, acting_user=operator
            )
            category.description = self.config.category.description
            category.rendered_description = rendered_description
            category.save(update_fields=["description", "rendered_description"])
            self.actions.append("update Category")
        return category

    def _reconcile_space(self, operator: UserProfile, category: ChannelFolder) -> Space:
        space = Space.objects.filter(realm=self.realm, name__iexact=self.config.space.name).first()
        if space is None:
            space = Space.objects.create(
                realm=self.realm,
                name=self.config.space.name,
                description=self.config.space.description,
                category=category,
                created_by=operator,
            )
            self.actions.append("create Space")
        elif space.description != self.config.space.description or space.category_id != category.id:
            space.description = self.config.space.description
            space.category = category
            space.full_clean()
            space.save(update_fields=["description", "category", "date_updated"])
            self.actions.append("update Space")
        return space

    def _reconcile_accounts(self, operator: UserProfile) -> dict[str, ConnectedAccount]:
        result: dict[str, ConnectedAccount] = {}
        for spec in self.config.accounts:
            bot = (
                self.bots[spec.incoming_webhook_bot_email.casefold()]
                if spec.incoming_webhook_bot_email is not None
                else None
            )
            account, created = ConnectedAccount.objects.update_or_create(
                realm=self.realm,
                provider_key=spec.provider_key,
                external_account_id=spec.external_account_id,
                defaults={
                    "provider_name": spec.provider_name,
                    "display_name": spec.display_name,
                    "connection_kind": spec.connection_kind,
                    "incoming_webhook_bot": bot,
                    "created_by": operator,
                    "owner": operator,
                    "approval_state": ConnectedAccount.ApprovalState.APPROVED,
                    "health_status": ConnectedAccount.HealthStatus.UNKNOWN,
                },
            )
            account.full_clean()
            if created:
                self.actions.append(f"create approved Connected Account {spec.key}")
            result[spec.key] = account
        return result

    def _reconcile_sources(self, accounts: dict[str, ConnectedAccount]) -> dict[str, Source]:
        result: dict[str, Source] = {}
        for spec in self.config.sources:
            source, created = Source.objects.update_or_create(
                account=accounts[spec.account_key],
                external_ref=spec.source_ref,
                defaults={
                    "realm": self.realm,
                    "adapter_key": spec.adapter_key,
                    "provider_key": spec.provider_key,
                    "source_type": spec.source_type,
                    "display_name": spec.display_name,
                    "provider_name": spec.provider_name,
                    "external_url": spec.external_url,
                    "supports_live_capture": spec.supports_live_capture,
                },
            )
            source.full_clean()
            SourceCapability.objects.exclude(capability__in=spec.capabilities).filter(
                source=source
            ).delete()
            for capability in spec.capabilities:
                SourceCapability.objects.get_or_create(source=source, capability=capability)
            if created:
                self.actions.append(f"create Source {spec.key}")
            result[spec.key] = source
        return result

    def _reconcile_attachments(
        self,
        operator: UserProfile,
        space: Space,
        sources: dict[str, Source],
    ) -> dict[str, SpaceAttachment]:
        result: dict[str, SpaceAttachment] = {}
        for spec in self.config.sources:
            start_at = spec.history.start_at
            attachment = SpaceAttachment.objects.filter(
                space=space, source=sources[spec.key]
            ).first()
            created = attachment is None
            if attachment is None:
                attachment = SpaceAttachment.objects.create(
                    realm=self.realm,
                    space=space,
                    source=sources[spec.key],
                    state=SpaceAttachment.State.ACTIVE,
                    history_window=SpaceAttachment.HistoryWindow.CUSTOM,
                    history_timezone=spec.history.timezone,
                    history_start_at=start_at,
                    custom_start_date=start_at.date(),
                    attached_by=operator,
                    next_publication_sync_at=start_at,
                )
            elif (
                attachment.history_window != SpaceAttachment.HistoryWindow.CUSTOM
                or attachment.history_timezone != spec.history.timezone
                or attachment.history_start_at != start_at
                or attachment.custom_start_date != start_at.date()
            ):
                raise PilotConfigError(f"Source {spec.key} has a conflicting history boundary")
            elif attachment.state != SpaceAttachment.State.ACTIVE:
                raise PilotConfigError(
                    f"Source {spec.key} is detached and requires explicit review"
                )
            attachment.clean()
            attachment.validate_constraints()
            if created:
                self.actions.append(f"attach Source {spec.key} with explicit history")
            result[spec.key] = attachment
        return result

    def _reconcile_grants(
        self,
        operator: UserProfile,
        accounts: dict[str, ConnectedAccount],
        sources: dict[str, Source],
    ) -> None:
        for spec in self.config.grants:
            grant, created = ConnectedAccountGrant.objects.update_or_create(
                realm=self.realm,
                account=accounts[spec.account_key],
                user=self.users[spec.user_email.casefold()],
                defaults={
                    "created_by": operator,
                    "state": ConnectedAccountGrant.State.ACTIVE,
                    "all_selectors": False,
                },
            )
            grant.selectors.all().delete()
            ConnectedAccountGrantSelector.objects.bulk_create(
                [
                    ConnectedAccountGrantSelector(
                        realm=self.realm,
                        grant=grant,
                        selector_type=(
                            "whatsapp_group"
                            if sources[source_key].provider_key == "whatsapp"
                            else sources[source_key].source_type
                        ),
                        source_ref=sources[source_key].external_ref,
                        display_name=sources[source_key].display_name,
                    )
                    for source_key in spec.source_keys
                ]
            )
            if created:
                self.actions.append(f"create least-privilege grant {spec.account_key}")

    def _reconcile_memberships(self, operator: UserProfile, space: Space) -> None:
        for spec in self.config.memberships:
            user = self.users[spec.user_email.casefold()]
            _membership, created = SpaceMembership.objects.update_or_create(
                realm=self.realm,
                space=space,
                user=user,
                defaults={
                    "role": spec.role,
                    "personal_editions_enabled": spec.personal_editions,
                    "added_by": operator,
                },
            )
            if spec.administrator:
                SpaceAdministrator.objects.get_or_create(
                    realm=self.realm,
                    space=space,
                    user=user,
                    defaults={"added_by": operator},
                )
            if created:
                self.actions.append("add reviewed internal teammate")

    def _reconcile_participant_mappings(self, sources: dict[str, Source]) -> None:
        for spec in self.config.participant_mappings:
            binding, created = SourceParticipantBinding.objects.update_or_create(
                source=sources[spec.source_key],
                participant_ref=spec.participant_ref,
                defaults={
                    "realm": self.realm,
                    "user": self.users[spec.user_email.casefold()],
                    "match_basis": spec.match_basis,
                    "observation_basis": spec.observation_basis,
                },
            )
            try:
                binding.full_clean()
            except DjangoValidationError as error:
                raise PilotConfigError(str(error))
            if created:
                self.actions.append("create reviewed teammate mapping")

    def _reconcile_modules(
        self,
        operator: UserProfile,
        space: Space,
        attachments: dict[str, SpaceAttachment],
    ) -> None:
        ensure_prebuilt_module_catalog(self.realm)
        for spec in self.config.modules:
            if not spec.enabled:
                if ModuleInstallation.objects.filter(
                    space=space,
                    version__definition__stable_key=spec.key,
                    state__in=[
                        ModuleInstallation.State.CONFIGURED,
                        ModuleInstallation.State.ENABLED,
                        ModuleInstallation.State.PAUSED_DETACHED,
                    ],
                ).exists():
                    raise PilotConfigError(f"Module {spec.key} must remain off")
                continue
            version = ModuleVersion.objects.get(
                definition__realm=self.realm,
                definition__stable_key=spec.key,
                version=spec.version,
            )
            try:
                _installation, created = do_install_module(
                    acting_user=operator,
                    space=space,
                    version_id=version.id,
                    attachment_ids=[attachments[key].id for key in spec.source_keys],
                    trigger_kind=spec.trigger.kind,
                    activation_timezone=spec.trigger.timezone,
                    cadence=spec.trigger.cadence,
                    local_time=spec.trigger.local_time,
                    debounce_seconds=spec.trigger.debounce_seconds,
                )
            except JsonableError as error:
                raise PilotConfigError(str(error))
            if created:
                self.actions.append(f"install Module {spec.key}")

    def _reconcile_routes(
        self,
        operator: UserProfile,
        space: Space,
        attachments: dict[str, SpaceAttachment],
    ) -> None:
        for spec in self.config.provenance_routes:
            bot = self.bots[spec.bot_email.casefold()]
            try:
                _route, created = do_associate_integration_route(
                    acting_user=operator,
                    space=space,
                    attachment_id=attachments[spec.source_key].id,
                    bot_user_id=bot.id,
                )
            except JsonableError as error:
                raise PilotConfigError(str(error))
            if created:
                self.actions.append(f"associate provenance route {spec.source_key}")


def render_report(report: dict[str, Any]) -> str:
    return json.dumps(report, indent=2, sort_keys=True)
