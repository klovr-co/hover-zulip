import copy
import io
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import orjson
from django.core.management import call_command
from django.core.management.base import CommandError
from typing_extensions import override

from hover.actions_modules import do_install_module, ensure_prebuilt_module_catalog
from hover.models import (
    ConnectedAccount,
    ConnectedAccountGrant,
    IntegrationRouteAssociation,
    ModuleDefinition,
    ModuleInstallation,
    ModuleVersion,
    PersonalEditionSyncState,
    Response,
    Source,
    SourceCapability,
    SourceParticipantBinding,
    Space,
    SpaceAdministrator,
    SpaceAttachment,
    SpaceMembership,
    Todo,
)
from hover.pilot_config import HoverPilotConfigV1
from zerver.actions.streams import bulk_add_subscriptions, bulk_remove_subscriptions
from zerver.lib.test_classes import ZulipTestCase
from zerver.models import ChannelFolder, UserProfile


class HoverPilotConfigTest(ZulipTestCase):
    @override
    def setUp(self) -> None:
        super().setUp()
        self.operator = self.example_user("iago")
        self.realm = self.operator.realm
        self.github_bot = self.create_test_bot(
            "pilot-github",
            self.operator,
            full_name="Pilot GitHub integration",
            bot_type=UserProfile.INCOMING_WEBHOOK_BOT,
        )
        self.apify_bot = self.create_test_bot(
            "pilot-apify",
            self.operator,
            full_name="Pilot Apify integration",
            bot_type=UserProfile.INCOMING_WEBHOOK_BOT,
        )
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)

    def config(self, *, private: bool = True, launch: bool = True) -> dict[str, Any]:
        operator_email = self.operator.delivery_email
        accounts: list[dict[str, Any]] = [
            {
                "key": "whatsapp",
                "provider_key": "whatsapp",
                "provider_name": "WhatsApp",
                "external_account_id": str(uuid.UUID(int=1)),
                "display_name": "Pilot WhatsApp",
                "connection_kind": "remote_studio",
                "incoming_webhook_bot_email": None,
                "approval_reviewed": True,
            },
            {
                "key": "github",
                "provider_key": "github",
                "provider_name": "GitHub",
                "external_account_id": str(uuid.UUID(int=2)),
                "display_name": "Pilot GitHub",
                "connection_kind": "native_integration",
                "incoming_webhook_bot_email": self.github_bot.delivery_email,
                "approval_reviewed": True,
            },
            {
                "key": "apify",
                "provider_key": "apify",
                "provider_name": "Apify",
                "external_account_id": str(uuid.UUID(int=3)),
                "display_name": "Pilot Apify",
                "connection_kind": "native_integration",
                "incoming_webhook_bot_email": self.apify_bot.delivery_email,
                "approval_reviewed": True,
            },
        ]
        source_data = [
            ("whatsapp_one", "whatsapp", "whatsapp", "group_chat", False, ""),
            ("whatsapp_two", "whatsapp", "whatsapp", "group_chat", False, ""),
            ("whatsapp_three", "whatsapp", "whatsapp", "group_chat", False, ""),
            (
                "github_repo",
                "github",
                "github",
                "repository",
                True,
                "https://github.com/example/pilot",
            ),
            (
                "apify_actor",
                "apify",
                "apify",
                "actor_run",
                True,
                "https://console.apify.com/actors/example",
            ),
        ]
        sources: list[dict[str, Any]] = [
            {
                "key": key,
                "account_key": account_key,
                "source_ref": f"src_{index:032x}",
                "adapter_key": "clawer_sync" if not live else provider_key,
                "provider_key": provider_key,
                "provider_name": provider_key.title(),
                "source_type": source_type,
                "display_name": f"Pilot Source {index}",
                "external_url": url,
                "supports_live_capture": live,
                "capabilities": ["message_history"],
                "history": {"timezone": "UTC", "start_at": "2026-08-01T00:00:00Z"},
            }
            for index, (key, account_key, provider_key, source_type, live, url) in enumerate(
                source_data, start=1
            )
        ]
        enabled_modules = [
            "conversation_digest",
            "progress_tracker",
            "suggested_actions",
            "decisions",
            "marketing_digest",
            "topic_analysis",
        ]
        modules = [
            {
                "key": key,
                "version": "1.0.0",
                "enabled": True,
                "source_keys": (
                    ["whatsapp_one"]
                    if key in {"marketing_digest", "topic_analysis"}
                    else ["whatsapp_one", "whatsapp_two", "whatsapp_three"]
                ),
                "trigger": {"kind": "manual", "timezone": "UTC"},
            }
            for key in enabled_modules
        ]
        modules.append(
            {
                "key": "signal_monitor",
                "version": "1.0.0",
                "enabled": False,
                "source_keys": [],
                "trigger": {"kind": "manual", "timezone": "UTC"},
            }
        )
        gates = [
            {"key": key, "status": "passed", "evidence": "Reviewed in staging."}
            for key in [
                "access",
                "duplication",
                "evidence",
                "audit_history",
                "notifications",
                "voluntary_use",
            ]
        ]
        return {
            "metadata": {
                "schema_version": "hover-pilot/v1",
                "pilot_key": "test-pilot",
                "realm": self.realm.string_id,
                "operator_email": operator_email,
                "private_config": private,
            },
            "category": {"name": "Pilot Programs", "description": "Reviewed pilots."},
            "space": {"name": "Pilot Space", "description": "Pilot work.", "launch": launch},
            "accounts": accounts,
            "sources": sources,
            "grants": [
                {
                    "account_key": account["key"],
                    "user_email": operator_email,
                    "source_keys": [
                        source["key"]
                        for source in sources
                        if source["account_key"] == account["key"]
                    ],
                    "reviewed": True,
                }
                for account in accounts
            ],
            "memberships": [
                {
                    "user_email": operator_email,
                    "role": "contributor",
                    "administrator": True,
                    "pilot_cohort": True,
                    "personal_editions": True,
                    "reviewed": True,
                }
            ],
            "participant_mappings": [
                {
                    "source_key": "whatsapp_one",
                    "participant_ref": f"person_{1:032x}",
                    "user_email": operator_email,
                    "match_basis": "verified_email",
                    "observation_basis": f"obs_{1:032x}",
                    "reviewed": True,
                }
            ],
            "provenance_routes": [
                {
                    "source_key": "github_repo",
                    "bot_email": self.github_bot.delivery_email,
                    "allowed_actors": ["github-app:pilot"],
                    "repository_allowlist": ["example/pilot"],
                    "event_allowlist": ["push", "pull_request"],
                    "external_configuration_reviewed": True,
                },
                {
                    "source_key": "apify_actor",
                    "bot_email": self.apify_bot.delivery_email,
                    "allowed_actors": ["actor:pilot"],
                    "repository_allowlist": [],
                    "event_allowlist": ["actor.run.succeeded"],
                    "external_configuration_reviewed": True,
                },
            ],
            "modules": modules,
            "forbidden_modules": [
                "email",
                "weekly_roundup",
                "ai_slides",
                "topics_you_follow",
            ],
            "personal_editions": {
                "morning_daily_brief": True,
                "end_of_day_roundup": True,
            },
            "shadow_mode": {
                "mode": "shadow",
                "comparison_system": "monday",
                "review_writeback": False,
                "todo_writeback": False,
                "allowed_external_writes": [],
            },
            "acceptance_gates": gates,
            "development_smoke": {
                "source_key": "whatsapp_one",
                "fixture_key": "sanitized-pilot-smoke",
                "contains_real_source_content": False,
                "expected_path": [
                    "generated_update",
                    "review",
                    "confirmed_todo",
                    "home_awareness",
                    "personal_edition",
                ],
            },
        }

    def write_config(self, payload: dict[str, Any], *, private_name: bool = True) -> Path:
        suffix = ".private.json" if private_name else ".json"
        path = Path(self.temp_dir.name) / f"pilot{suffix}"
        path.write_bytes(orjson.dumps(payload))
        return path

    def run_command(self, path: Path, *, apply: bool = False, confirm: str | None = None) -> str:
        stdout = io.StringIO()
        args = ["configure_hover_pilot", f"--realm={self.realm.string_id}", f"--config={path}"]
        if apply:
            args.append("--apply")
        if confirm is not None:
            args.append(f"--confirm={confirm}")
        call_command(*args, stdout=stdout)
        return stdout.getvalue()

    def test_strict_versioned_schema_rejects_unsafe_rollouts(self) -> None:
        payload = self.config()
        payload["unexpected"] = True
        with self.assertRaisesRegex(ValueError, "Extra inputs are not permitted"):
            HoverPilotConfigV1.model_validate(payload)

        payload = self.config()
        payload["modules"][0]["key"] = "email"
        with self.assertRaisesRegex(ValueError, "Exactly the six required pilot Modules"):
            HoverPilotConfigV1.model_validate(payload)

        payload = self.config()
        payload["shadow_mode"]["todo_writeback"] = True
        with self.assertRaisesRegex(ValueError, "Input should be False"):
            HoverPilotConfigV1.model_validate(payload)

        payload = self.config()
        payload["memberships"][0]["personal_editions"] = False
        with self.assertRaisesRegex(ValueError, "exact pilot cohort"):
            HoverPilotConfigV1.model_validate(payload)

        payload = self.config()
        payload["modules"][0]["trigger"]["timezone"] = "Not/A-Timezone"
        with self.assertRaisesRegex(ValueError, "valid IANA timezone"):
            HoverPilotConfigV1.model_validate(payload)

    def test_dry_run_validates_without_mutating_records(self) -> None:
        output = self.run_command(self.write_config(self.config()))

        self.assertIn('"operation": "dry-run"', output)
        self.assertIn('"whatsapp_sources": 3', output)
        self.assertIn('"reviews_to_monday": false', output)
        self.assertFalse(Space.objects.filter(realm=self.realm, name="Pilot Space").exists())
        self.assertFalse(
            ChannelFolder.objects.filter(realm=self.realm, name="Pilot Programs").exists()
        )

    def test_apply_requires_private_config_and_exact_confirmation(self) -> None:
        public_path = self.write_config(self.config(private=False), private_name=False)
        with self.assertRaisesRegex(CommandError, "ending in .private.json"):
            self.run_command(public_path, apply=True, confirm="zulip:test-pilot")

        private_path = self.write_config(self.config())
        with self.assertRaisesRegex(CommandError, "Apply refused"):
            self.run_command(private_path, apply=True, confirm="zulip:wrong")

    def test_apply_is_idempotent_and_creates_only_normal_hover_records(self) -> None:
        path = self.write_config(self.config())
        confirmation = f"{self.realm.string_id}:test-pilot"
        first = self.run_command(path, apply=True, confirm=confirmation)
        attachment = SpaceAttachment.objects.get(source__external_ref=f"src_{1:032x}")
        attachment.publication_cursor = "opaque-runtime-cursor"
        attachment.save(update_fields=["publication_cursor"])
        counts = {
            "accounts": ConnectedAccount.objects.filter(realm=self.realm).count(),
            "sources": Source.objects.filter(realm=self.realm).count(),
            "attachments": SpaceAttachment.objects.filter(realm=self.realm).count(),
            "grants": ConnectedAccountGrant.objects.filter(realm=self.realm).count(),
            "memberships": SpaceMembership.objects.filter(realm=self.realm).count(),
            "routes": IntegrationRouteAssociation.objects.filter(realm=self.realm).count(),
            "installations": ModuleInstallation.objects.filter(realm=self.realm).count(),
            "bindings": SourceParticipantBinding.objects.filter(realm=self.realm).count(),
        }

        second = self.run_command(path, apply=True, confirm=confirmation)
        attachment.refresh_from_db()

        self.assertIn('"operation": "apply"', first)
        self.assertIn('"planned_actions": []', second)
        self.assertEqual(attachment.publication_cursor, "opaque-runtime-cursor")
        self.assertEqual(
            counts,
            {
                "accounts": ConnectedAccount.objects.filter(realm=self.realm).count(),
                "sources": Source.objects.filter(realm=self.realm).count(),
                "attachments": SpaceAttachment.objects.filter(realm=self.realm).count(),
                "grants": ConnectedAccountGrant.objects.filter(realm=self.realm).count(),
                "memberships": SpaceMembership.objects.filter(realm=self.realm).count(),
                "routes": IntegrationRouteAssociation.objects.filter(realm=self.realm).count(),
                "installations": ModuleInstallation.objects.filter(realm=self.realm).count(),
                "bindings": SourceParticipantBinding.objects.filter(realm=self.realm).count(),
            },
        )
        self.assertEqual(counts["accounts"], 3)
        self.assertEqual(counts["sources"], 5)
        self.assertEqual(counts["routes"], 2)
        self.assertEqual(counts["installations"], 6)
        self.assertTrue(
            ModuleDefinition.objects.filter(realm=self.realm, stable_key="signal_monitor").exists()
        )
        self.assertFalse(
            ModuleInstallation.objects.filter(
                realm=self.realm, version__definition__stable_key="signal_monitor"
            ).exists()
        )
        self.assertFalse(
            ModuleDefinition.objects.filter(
                realm=self.realm,
                stable_key__in=["email", "weekly_roundup", "ai_slides", "topics_you_follow"],
            ).exists()
        )
        self.assertEqual(PersonalEditionSyncState.objects.filter(realm=self.realm).count(), 0)
        self.assertEqual(
            Response.objects.filter(
                realm=self.realm, response_type=Response.ResponseType.REVIEW
            ).count(),
            0,
        )
        self.assertEqual(Todo.objects.filter(realm=self.realm).count(), 0)

    def test_rejects_external_guests_before_mutation(self) -> None:
        guest = self.example_user("polonius")
        guest.role = UserProfile.ROLE_GUEST
        guest.save(update_fields=["role"])
        payload = copy.deepcopy(self.config())
        payload["memberships"][0]["user_email"] = guest.delivery_email
        for grant in payload["grants"]:
            grant["user_email"] = guest.delivery_email
        payload["participant_mappings"][0]["user_email"] = guest.delivery_email
        payload["metadata"]["operator_email"] = guest.delivery_email
        path = self.write_config(payload)

        with self.assertRaisesRegex(CommandError, "active internal teammates"):
            self.run_command(path)
        self.assertFalse(Space.objects.filter(realm=self.realm, name="Pilot Space").exists())

    def test_signal_monitor_catalog_is_available_without_installation(self) -> None:
        ensure_prebuilt_module_catalog(self.realm)
        self.assertTrue(
            ModuleDefinition.objects.filter(
                realm=self.realm, stable_key="signal_monitor", name="Signal Monitor"
            ).exists()
        )

    def test_setup_space_rejects_unreviewed_membership_and_administrator_drift(self) -> None:
        path = self.write_config(self.config(launch=False))
        confirmation = f"{self.realm.string_id}:test-pilot"
        self.run_command(path, apply=True, confirm=confirmation)
        space = Space.objects.get(realm=self.realm, name="Pilot Space")
        unreviewed = self.example_user("hamlet")
        membership = SpaceMembership.objects.create(
            realm=self.realm,
            space=space,
            user=unreviewed,
            role=SpaceMembership.Role.SUBSCRIBER,
            added_by=self.operator,
        )

        with self.assertRaisesRegex(CommandError, "unreviewed membership"):
            self.run_command(path)

        membership.delete()
        SpaceAdministrator.objects.create(
            realm=self.realm,
            space=space,
            user=unreviewed,
            added_by=self.operator,
        )
        with self.assertRaisesRegex(CommandError, "unreviewed administrator"):
            self.run_command(path)

    def test_rejects_extra_active_grant_on_configured_account(self) -> None:
        path = self.write_config(self.config(launch=False))
        confirmation = f"{self.realm.string_id}:test-pilot"
        self.run_command(path, apply=True, confirm=confirmation)
        account = ConnectedAccount.objects.get(realm=self.realm, provider_key="whatsapp")
        ConnectedAccountGrant.objects.create(
            realm=self.realm,
            account=account,
            user=self.example_user("hamlet"),
            created_by=self.operator,
            state=ConnectedAccountGrant.State.ACTIVE,
            all_selectors=False,
        )

        with self.assertRaisesRegex(CommandError, "unreviewed active grant"):
            self.run_command(path)

    def test_rejects_extra_active_attachment(self) -> None:
        path = self.write_config(self.config(launch=False))
        confirmation = f"{self.realm.string_id}:test-pilot"
        self.run_command(path, apply=True, confirm=confirmation)
        space = Space.objects.get(realm=self.realm, name="Pilot Space")
        account = ConnectedAccount.objects.get(realm=self.realm, provider_key="whatsapp")
        source = Source.objects.create(
            realm=self.realm,
            account=account,
            adapter_key="clawer_sync",
            provider_key="whatsapp",
            source_type="group_chat",
            external_ref=f"src_{99:032x}",
            display_name="Unreviewed source",
            provider_name="WhatsApp",
        )
        SourceCapability.objects.create(source=source, capability="message_history")
        SpaceAttachment.objects.create(
            realm=self.realm,
            space=space,
            source=source,
            state=SpaceAttachment.State.ACTIVE,
            history_window=SpaceAttachment.HistoryWindow.CUSTOM,
            history_timezone="UTC",
            history_start_at=datetime(2026, 8, 1, tzinfo=timezone.utc),
            custom_start_date=datetime(2026, 8, 1, tzinfo=timezone.utc).date(),
            attached_by=self.operator,
        )

        with self.assertRaisesRegex(CommandError, "unreviewed active Source attachment"):
            self.run_command(path)

    def test_rejects_extra_current_module(self) -> None:
        path = self.write_config(self.config(launch=False))
        confirmation = f"{self.realm.string_id}:test-pilot"
        self.run_command(path, apply=True, confirm=confirmation)
        space = Space.objects.get(realm=self.realm, name="Pilot Space")
        version = ModuleVersion.objects.get(
            definition__realm=self.realm,
            definition__stable_key="signal_monitor",
            version="1.0.0",
        )
        attachment = SpaceAttachment.objects.filter(space=space).first()
        assert attachment is not None
        do_install_module(
            acting_user=self.operator,
            space=space,
            version_id=version.id,
            attachment_ids=[attachment.id],
            trigger_kind="manual",
            activation_timezone="UTC",
        )

        with self.assertRaisesRegex(CommandError, "unreviewed current Module"):
            self.run_command(path)

    def test_rejects_unreviewed_native_subscription(self) -> None:
        path = self.write_config(self.config())
        confirmation = f"{self.realm.string_id}:test-pilot"
        self.run_command(path, apply=True, confirm=confirmation)
        space = Space.objects.get(realm=self.realm, name="Pilot Space")
        assert space.stream is not None
        unreviewed = self.example_user("hamlet")
        bulk_add_subscriptions(self.realm, [space.stream], [unreviewed], acting_user=self.operator)

        with self.assertRaisesRegex(CommandError, "unreviewed user"):
            self.run_command(path)

        bulk_remove_subscriptions(
            self.realm, [unreviewed], [space.stream], acting_user=self.operator
        )

    def test_rejects_active_route_bot_drift(self) -> None:
        path = self.write_config(self.config())
        confirmation = f"{self.realm.string_id}:test-pilot"
        self.run_command(path, apply=True, confirm=confirmation)
        drift_bot = self.create_test_bot(
            "pilot-route-drift",
            self.operator,
            full_name="Unreviewed integration",
            bot_type=UserProfile.INCOMING_WEBHOOK_BOT,
        )
        route = IntegrationRouteAssociation.objects.filter(
            realm=self.realm, state=IntegrationRouteAssociation.State.ACTIVE
        ).first()
        assert route is not None
        route.bot = drift_bot
        route.save(update_fields=["bot"])

        with self.assertRaisesRegex(CommandError, "unreviewed active provenance route"):
            self.run_command(path)
