from datetime import timedelta
from uuid import uuid4

import orjson
from django.core.exceptions import ValidationError
from django.utils.timezone import now as timezone_now
from typing_extensions import override

from hover.actions_modules import ensure_prebuilt_module_catalog
from hover.actions_spaces import do_create_space
from hover.models import (
    ConnectedAccount,
    ConnectedAccountGrant,
    ModuleDefinition,
    ModuleInstallation,
    ModuleSourceRequirement,
    ModuleSupportedTrigger,
    ModuleVersion,
    Source,
    SourceCapability,
    Space,
    SpaceAttachment,
)
from zerver.actions.channel_folders import check_add_channel_folder
from zerver.lib.events import apply_events, fetch_initial_state_data
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.user_groups import get_system_user_group_by_name
from zerver.models.groups import SystemGroups
from zerver.models.realm_audit_logs import AuditLogEventType, RealmAuditLog


class HoverModulesTest(ZulipTestCase):
    @override
    def setUp(self) -> None:
        super().setUp()
        self.creator = self.example_user("hamlet")
        self.realm = self.creator.realm
        self.realm.hover_enabled = True
        self.realm.can_create_spaces_group = get_system_user_group_by_name(
            SystemGroups.MEMBERS, self.realm.id
        )
        self.realm.save(update_fields=["hover_enabled", "can_create_spaces_group"])
        self.category = check_add_channel_folder(
            self.realm, "Programs", "", acting_user=self.example_user("iago")
        )
        self.space = do_create_space(
            self.creator,
            name="Module acceptance",
            description="",
            category=self.category,
        )
        self.account = ConnectedAccount.objects.create(
            realm=self.realm,
            provider_key="whatsapp",
            provider_name="WhatsApp",
            external_account_id=uuid4(),
            display_name="Program account",
            created_by=self.creator,
            owner=self.creator,
            approval_state=ConnectedAccount.ApprovalState.APPROVED,
        )
        ConnectedAccountGrant.objects.create(
            realm=self.realm,
            account=self.account,
            user=self.creator,
            created_by=self.creator,
            state=ConnectedAccountGrant.State.ACTIVE,
            all_selectors=True,
        )
        self.attachment = self.create_attachment("a")
        ensure_prebuilt_module_catalog(self.realm)
        self.version = ModuleVersion.objects.get(
            definition__realm=self.realm, definition__stable_key="conversation_digest"
        )
        self.login_user(self.creator)

    def create_attachment(self, suffix: str) -> SpaceAttachment:
        source = Source.objects.create(
            realm=self.realm,
            account=self.account,
            adapter_key="clawer_sync",
            provider_key="whatsapp",
            source_type="group",
            external_ref=f"src_{suffix * 32}",
            display_name=f"Source {suffix}",
        )
        SourceCapability.objects.create(source=source, capability="message_history")
        return SpaceAttachment.objects.create(
            realm=self.realm,
            space=self.space,
            source=source,
            state=SpaceAttachment.State.ACTIVE,
            history_window=SpaceAttachment.HistoryWindow.LAST_30_DAYS,
            history_timezone="UTC",
            history_start_at=timezone_now() - timedelta(days=30),
            attached_by=self.creator,
        )

    def install_data(self, **overrides: object) -> dict[str, str]:
        data: dict[str, object] = {
            "version_id": orjson.dumps(self.version.id).decode(),
            "attachment_ids": orjson.dumps([self.attachment.id]).decode(),
            "trigger_kind": orjson.dumps("manual").decode(),
            "activation_timezone": "UTC",
        }
        data.update(overrides)
        return {key: value if isinstance(value, str) else str(value) for key, value in data.items()}

    def test_catalog_is_realm_scoped_structured_and_immutable(self) -> None:
        result = self.client_get("/json/hover/modules")
        self.assert_json_success(result)
        modules = orjson.loads(result.content)["modules"]
        self.assert_length(modules, 7)
        marketing = next(item for item in modules if item["definition_key"] == "marketing_digest")
        self.assertEqual(marketing["supported_triggers"], ["manual", "schedule"])
        self.assertEqual(marketing["requirements"][0]["maximum_count"], 1)
        self.assertNotIn("runtime_key", marketing)
        self.assertNotIn("prompt_key", marketing)
        signal_monitor = next(
            item for item in modules if item["definition_key"] == "signal_monitor"
        )
        self.assertEqual(signal_monitor["supported_triggers"], ["manual", "new_source", "schedule"])

        self.version.destination_topic = "Changed"
        with self.assertRaisesRegex(ValidationError, "immutable"):
            self.version.save()
        with self.assertRaisesRegex(ValidationError, "cannot be deleted"):
            self.version.delete()
        definition = self.version.definition
        definition.name = "Changed"
        with self.assertRaisesRegex(ValidationError, "immutable"):
            definition.save()

        other_realm = self.lear_user("cordelia").realm
        wrong_installation = ModuleInstallation(
            realm=other_realm,
            space=self.space,
            version=self.version,
            state=ModuleInstallation.State.CONFIGURED,
            activation_timezone="UTC",
            policy_hash="0" * 64,
        )
        with self.assertRaises(ValidationError):
            wrong_installation.full_clean()

    def test_install_is_pinned_idempotent_and_conflicting_replay_is_409(self) -> None:
        with self.capture_send_event_calls(expected_num_events=1) as events:
            result = self.client_post(
                f"/json/hover/spaces/{self.space.id}/modules", self.install_data()
            )
        self.assert_json_success(result)
        payload = orjson.loads(result.content)
        self.assertTrue(payload["created"])
        installation = ModuleInstallation.objects.get(id=payload["installation"]["id"])
        self.assertEqual(installation.version, self.version)
        self.assertEqual(installation.state, ModuleInstallation.State.CONFIGURED)
        self.assertIsNone(installation.processing_start_at)
        self.assertEqual(events[0]["users"], [self.creator.id])

        replay = self.client_post(
            f"/json/hover/spaces/{self.space.id}/modules", self.install_data()
        )
        self.assert_json_success(replay)
        self.assertFalse(orjson.loads(replay.content)["created"])
        conflict = self.client_post(
            f"/json/hover/spaces/{self.space.id}/modules",
            self.install_data(
                trigger_kind=orjson.dumps("schedule").decode(),
                cadence=orjson.dumps("daily").decode(),
                local_time=orjson.dumps("09:00").decode(),
            ),
        )
        self.assertEqual(conflict.status_code, 409)

        disabled = self.assert_json_success(
            self.client_post(f"/json/hover/module-installations/{installation.id}/disable")
        )
        self.assertTrue(disabled["changed"])
        self.assertEqual(disabled["installation"]["state"], ModuleInstallation.State.DISABLED)
        replayed_disable = self.assert_json_success(
            self.client_post(f"/json/hover/module-installations/{installation.id}/disable")
        )
        self.assertFalse(replayed_disable["changed"])

    def test_initial_state_and_module_installation_event_converge(self) -> None:
        state = fetch_initial_state_data(
            self.creator, realm=self.realm, event_types={"hover_space"}
        )
        with self.capture_send_event_calls(expected_num_events=1) as events:
            result = self.client_post(
                f"/json/hover/spaces/{self.space.id}/modules", self.install_data()
            )
        self.assert_json_success(result)
        event = events[0]["event"]
        self.assertEqual(event["space"]["module_installations"][0]["version_id"], self.version.id)
        self.assertNotIn("runtime_key", event["space"]["module_installations"][0])

        apply_events(
            self.creator,
            state=state,
            events=[event],
            fetch_event_types={"hover_space"},
            client_gravatar=False,
            slim_presence=False,
            include_subscribers=False,
            linkifier_url_template=False,
            user_list_incomplete=False,
            include_deactivated_groups=False,
        )
        fresh_state = fetch_initial_state_data(
            self.creator, realm=self.realm, event_types={"hover_space"}
        )
        self.assertEqual(state["hover_spaces"], fresh_state["hover_spaces"])

    def test_trigger_cardinality_capability_and_backfill_validation(self) -> None:
        marketing = ModuleVersion.objects.get(
            definition__realm=self.realm, definition__stable_key="marketing_digest"
        )
        invalid_trigger = self.client_post(
            f"/json/hover/spaces/{self.space.id}/modules",
            self.install_data(
                version_id=orjson.dumps(marketing.id).decode(),
                trigger_kind=orjson.dumps("new_source").decode(),
                debounce_seconds=orjson.dumps(300).decode(),
            ),
        )
        self.assert_json_error(
            invalid_trigger, "This Module version does not support that trigger."
        )

        second = self.create_attachment("b")
        too_many = self.client_post(
            f"/json/hover/spaces/{self.space.id}/modules",
            self.install_data(
                version_id=orjson.dumps(marketing.id).decode(),
                attachment_ids=orjson.dumps([self.attachment.id, second.id]).decode(),
            ),
        )
        self.assert_json_error(too_many, "The Source binding does not satisfy Module cardinality.")

        SourceCapability.objects.filter(source=self.attachment.source).delete()
        missing_capability = self.client_post(
            f"/json/hover/spaces/{self.space.id}/modules", self.install_data()
        )
        self.assert_json_error(
            missing_capability, "An attached Source lacks a required Module capability."
        )
        SourceCapability.objects.create(source=self.attachment.source, capability="message_history")

        earlier_than_source = timezone_now() - timedelta(days=60)
        invalid_backfill = self.client_post(
            f"/json/hover/spaces/{self.space.id}/modules",
            self.install_data(
                backfill_start_at=orjson.dumps(earlier_than_source.isoformat()).decode(),
                backfill_confirmed=orjson.dumps(True).decode(),
            ),
        )
        self.assert_json_error(
            invalid_backfill, "Backfill starts before an attached Source is available."
        )

        valid_start = timezone_now() - timedelta(days=2)
        missing_confirmation = self.client_post(
            f"/json/hover/spaces/{self.space.id}/modules",
            self.install_data(
                backfill_start_at=orjson.dumps(valid_start.isoformat()).decode(),
                backfill_confirmed=orjson.dumps(False).decode(),
            ),
        )
        self.assert_json_error(
            missing_confirmation, "Earlier backfill requires an explicit bounded confirmation."
        )

    def test_launch_activates_detach_pauses_and_rebind_resumes(self) -> None:
        second = self.create_attachment("b")
        install = self.client_post(
            f"/json/hover/spaces/{self.space.id}/modules", self.install_data()
        )
        installation_id = orjson.loads(install.content)["installation"]["id"]
        launch = self.client_post(f"/json/hover/spaces/{self.space.id}/launch")
        self.assert_json_success(launch)
        installation = ModuleInstallation.objects.get(id=installation_id)
        self.assertEqual(installation.state, ModuleInstallation.State.ENABLED)
        self.assertIsNotNone(installation.activated_at)
        self.assertEqual(installation.processing_start_at, installation.activated_at)

        self.login_user(self.example_user("iago"))
        archived = self.client_post(
            f"/json/hover/pipeline-library/versions/{self.version.id}/archive"
        )
        self.assert_json_success(archived)
        self.login_user(self.creator)
        self.assertNotIn(
            self.version.id,
            {
                item["id"]
                for item in orjson.loads(self.client_get("/json/hover/modules").content)["modules"]
            },
        )

        detached = self.client_delete(
            f"/json/hover/spaces/{self.space.id}/sources/{self.attachment.id}"
        )
        self.assert_json_success(detached)
        detached_space = orjson.loads(detached.content)["space"]
        self.assertEqual(
            [item["id"] for item in detached_space["attachments"]],
            [self.attachment.id, second.id],
        )
        self.assertEqual(detached_space["attachments"][0]["state"], "detached")
        self.assertTrue(detached_space["attachments"][0]["can_browse_records"])
        self.assertEqual(detached_space["module_installations"][0]["state"], "paused_detached")
        installation.refresh_from_db()
        self.attachment.refresh_from_db()
        self.assertEqual(installation.state, ModuleInstallation.State.PAUSED_DETACHED)
        self.assertEqual(
            self.attachment.publication_sync_state,
            SpaceAttachment.PublicationSyncState.IDLE,
        )
        self.assertIsNone(self.attachment.publication_sync_lease_token)
        self.assertIsNone(self.attachment.publication_sync_lease_expires_at)
        self.assertIsNone(self.attachment.next_publication_sync_at)
        self.assertTrue(installation.bindings.filter(attachment=self.attachment).exists())
        self.assertTrue(
            RealmAuditLog.objects.filter(
                event_type=AuditLogEventType.HOVER_SOURCE_DETACHED,
                extra_data__attachment_id=self.attachment.id,
            ).exists()
        )

        rebound = self.client_post(
            f"/json/hover/module-installations/{installation.id}/rebind-resume",
            {"attachment_ids": orjson.dumps([second.id]).decode()},
        )
        self.assert_json_success(rebound)
        successor = ModuleInstallation.objects.get(
            id=orjson.loads(rebound.content)["installation"]["id"]
        )
        installation.refresh_from_db()
        self.assertEqual(installation.state, ModuleInstallation.State.DISABLED)
        self.assertEqual(successor.state, ModuleInstallation.State.ENABLED)
        self.assertEqual(successor.predecessor, installation)
        self.assertEqual(
            list(successor.bindings.values_list("attachment_id", flat=True)), [second.id]
        )

    def test_launch_rolls_back_when_configured_binding_loses_capability(self) -> None:
        installed = self.client_post(
            f"/json/hover/spaces/{self.space.id}/modules", self.install_data()
        )
        self.assert_json_success(installed)
        SourceCapability.objects.filter(source=self.attachment.source).delete()

        launch = self.client_post(f"/json/hover/spaces/{self.space.id}/launch")
        self.assert_json_error(launch, "A configured Module Source lost a required capability.")
        self.space.refresh_from_db()
        self.assertEqual(self.space.state, Space.State.SETUP)
        self.assertIsNone(self.space.stream_id)
        self.assertEqual(
            ModuleInstallation.objects.get(space=self.space).state,
            ModuleInstallation.State.CONFIGURED,
        )

    def test_upgrade_creates_successor_and_preserves_pinned_predecessor(self) -> None:
        installed = self.client_post(
            f"/json/hover/spaces/{self.space.id}/modules", self.install_data()
        )
        predecessor_id = orjson.loads(installed.content)["installation"]["id"]
        definition = self.version.definition
        version2 = ModuleVersion.objects.create(
            definition=definition,
            version="2.0.0",
            output_type=self.version.output_type,
            runtime_key="hover.conversation_digest.v2",
            prompt_key="hover.conversation_digest.v2",
            destination_topic=self.version.destination_topic,
            navigation_icon=self.version.navigation_icon,
            navigation_order=self.version.navigation_order,
            content_hash="2" * 64,
            published_by=self.creator,
            is_sealed=False,
        )
        requirement = self.version.requirements.get()
        ModuleSourceRequirement.objects.create(
            version=version2,
            key=requirement.key,
            capability=requirement.capability,
            minimum_count=1,
            maximum_count=10,
        )
        ModuleSupportedTrigger.objects.create(
            version=version2, kind=ModuleSupportedTrigger.Kind.MANUAL
        )
        ModuleVersion.objects.filter(id=version2.id).update(is_sealed=True)
        result = self.client_post(
            f"/json/hover/module-installations/{predecessor_id}/upgrade",
            self.install_data(version_id=orjson.dumps(version2.id).decode()),
        )
        self.assert_json_success(result)
        successor = ModuleInstallation.objects.get(
            id=orjson.loads(result.content)["installation"]["id"]
        )
        predecessor = ModuleInstallation.objects.get(id=predecessor_id)
        self.assertEqual(predecessor.version, self.version)
        self.assertEqual(predecessor.state, ModuleInstallation.State.DISABLED)
        self.assertEqual(successor.predecessor, predecessor)
        self.assertEqual(successor.version, version2)

    def test_non_admin_cannot_install_and_catalog_does_not_cross_realms(self) -> None:
        self.login("othello")
        denied = self.client_post(
            f"/json/hover/spaces/{self.space.id}/modules", self.install_data()
        )
        self.assert_json_error(denied, "Invalid Space ID")

        other_realm = self.lear_user("cordelia").realm
        other_definition = ModuleDefinition.objects.create(
            realm=other_realm, stable_key="private_module", name="Private", description=""
        )
        ModuleVersion.objects.create(
            definition=other_definition,
            version="1.0.0",
            output_type="analysis",
            runtime_key="private.runtime",
            prompt_key="private.prompt",
            destination_topic="Private",
            navigation_order=1,
            content_hash="f" * 64,
        )
        self.login_user(self.creator)
        modules = orjson.loads(self.client_get("/json/hover/modules").content)["modules"]
        self.assertNotIn("private_module", {module["definition_key"] for module in modules})
