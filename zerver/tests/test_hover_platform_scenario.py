import hashlib
from datetime import datetime, timezone
from typing import Any
from unittest import TestCase
from uuid import uuid4

import orjson
from typing_extensions import override

from hover.actions_spaces import do_create_space, do_launch_space
from hover.clawer_sync import InMemoryClawerSync
from hover.lib_awareness import get_awareness_projection
from hover.models import (
    ConnectedAccount,
    GeneratedItem,
    Source,
    SourceParticipantBinding,
    SpaceAttachment,
    SpaceMembership,
    SuggestedAction,
    Todo,
)
from hover.personal_editions import get_personal_editions_for_user, sync_personal_editions
from hover.publication_contracts import ClawerPublication, ClawerPublicationPage
from hover.publication_sync import sync_space_attachment
from zerver.actions.channel_folders import check_add_channel_folder
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.user_groups import get_system_user_group_by_name
from zerver.models.groups import SystemGroups
from zerver.tests.hover_platform_scenario import (
    SCENARIO_FIXTURE,
    HoverPlatformScenario,
    load_hover_platform_scenario,
)


class HoverPlatformScenarioTest(TestCase):
    def fixture_data(self) -> dict[str, Any]:
        return orjson.loads(SCENARIO_FIXTURE.read_bytes())

    def test_fixture_covers_cross_provider_platform_workflow(self) -> None:
        fixture_bytes = SCENARIO_FIXTURE.read_bytes()
        expected_checksum = SCENARIO_FIXTURE.with_suffix(".json.sha256").read_text().strip()
        self.assertEqual(hashlib.sha256(fixture_bytes).hexdigest(), expected_checksum)
        scenario = load_hover_platform_scenario()

        self.assertEqual(
            {provider.provider_key for provider in scenario.providers},
            {"whatsapp", "instagram", "github"},
        )
        self.assertEqual(
            {step.kind for step in scenario.steps},
            {
                "generated_update",
                "conflict_detected",
                "suggested_action",
                "todo_created",
                "todo_completed",
                "review_submitted",
                "conflict_resolved",
            },
        )
        self.assertEqual(scenario.publication("generated-update").contract, "feed_update")
        self.assertEqual(
            scenario.publication("conflict-detected").disputed_details[0].field_path,
            "status",
        )
        self.assertEqual(scenario.publication("suggested-action").contract, "suggested_action")

    def test_fixture_is_sanitized_and_not_tied_to_product_demo_logic(self) -> None:
        fixture = SCENARIO_FIXTURE.read_text()
        for forbidden in [
            "aimto",
            "@g.us",
            "hvr_srv_",
            "private.invalid",
            "+60",
            "10.240.",
        ]:
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, fixture.casefold())

    def test_step_shape_validation(self) -> None:
        data = self.fixture_data()
        data["steps"][0]["publication"] = None
        with self.assertRaisesRegex(ValueError, "must carry exactly one publication"):
            HoverPlatformScenario.model_validate(data)

        data = self.fixture_data()
        data["steps"][0]["provider_key"] = None
        with self.assertRaisesRegex(ValueError, "must identify one provider"):
            HoverPlatformScenario.model_validate(data)

        data = self.fixture_data()
        data["steps"][3]["references_step_id"] = None
        with self.assertRaisesRegex(ValueError, "must reference their predecessor"):
            HoverPlatformScenario.model_validate(data)

    def test_scenario_workflow_validation(self) -> None:
        data = self.fixture_data()
        data["providers"].pop()
        with self.assertRaisesRegex(ValueError, "all supported fixture providers"):
            HoverPlatformScenario.model_validate(data)

        data = self.fixture_data()
        data["providers"].append(data["providers"][0].copy())
        with self.assertRaisesRegex(ValueError, "providers must be unique"):
            HoverPlatformScenario.model_validate(data)

        data = self.fixture_data()
        data["steps"][1]["step_id"] = data["steps"][0]["step_id"]
        with self.assertRaisesRegex(ValueError, "step IDs must be unique"):
            HoverPlatformScenario.model_validate(data)

        data = self.fixture_data()
        data["steps"][3]["references_step_id"] = "later-step"
        with self.assertRaisesRegex(ValueError, "must point to an earlier step"):
            HoverPlatformScenario.model_validate(data)

        data = self.fixture_data()
        data["steps"][0]["provider_key"] = "whatsapp"
        with self.assertRaisesRegex(ValueError, "must use its provider source"):
            HoverPlatformScenario.model_validate(data)

        data = self.fixture_data()
        data["steps"].pop()
        with self.assertRaisesRegex(ValueError, "complete platform workflow"):
            HoverPlatformScenario.model_validate(data)

    def test_publication_requires_a_publication_step(self) -> None:
        scenario = load_hover_platform_scenario()
        with self.assertRaises(KeyError):
            scenario.publication("missing-step")


class HoverPilotCausalScenarioTest(ZulipTestCase):
    SOURCE_REF = "src_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    TEAMMATE_REF = "person_66666666666666666666666666666666"

    @override
    def setUp(self) -> None:
        super().setUp()
        self.user = self.example_user("hamlet")
        self.assistant = self.example_user("default_bot")
        self.settings_override = self.settings(HOVER_ASSISTANT_EMAIL=self.assistant.delivery_email)
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)
        self.realm = self.user.realm
        self.realm.hover_enabled = True
        self.realm.can_create_spaces_group = get_system_user_group_by_name(
            SystemGroups.MEMBERS, self.realm.id
        )
        self.realm.save(update_fields=["hover_enabled", "can_create_spaces_group"])
        category = check_add_channel_folder(
            self.realm, "Programs", "", acting_user=self.example_user("iago")
        )
        self.space = do_create_space(
            self.user,
            name="Sanitized pilot",
            description="One causal source-backed workflow.",
            category=category,
        )
        SpaceMembership.objects.filter(space=self.space, user=self.user).update(
            personal_editions_enabled=True
        )
        self.account = ConnectedAccount.objects.create(
            realm=self.realm,
            provider_key="whatsapp",
            provider_name="WhatsApp",
            external_account_id=uuid4(),
            display_name="Sanitized operations source",
            created_by=self.user,
            owner=self.user,
            approval_state=ConnectedAccount.ApprovalState.APPROVED,
        )
        source = Source.objects.create(
            realm=self.realm,
            account=self.account,
            adapter_key="clawer_sync",
            provider_key="whatsapp",
            provider_name="WhatsApp",
            source_type="group",
            external_ref=self.SOURCE_REF,
            display_name="Sanitized operations group",
        )
        self.attachment = SpaceAttachment.objects.create(
            realm=self.realm,
            space=self.space,
            source=source,
            state=SpaceAttachment.State.ACTIVE,
            history_window=SpaceAttachment.HistoryWindow.CUSTOM,
            history_timezone="UTC",
            history_start_at=datetime(2026, 8, 1, tzinfo=timezone.utc),
            custom_start_date=datetime(2026, 8, 1, tzinfo=timezone.utc).date(),
            attached_by=self.user,
        )
        SourceParticipantBinding.objects.create(
            realm=self.realm,
            source=source,
            participant_ref=self.TEAMMATE_REF,
            user=self.user,
            match_basis=SourceParticipantBinding.MatchBasis.VERIFIED_EMAIL,
            observation_basis="obs_66666666666666666666666666666666",
        )
        self.space, _ = do_launch_space(self.space, acting_user=self.user)
        self.adapter = InMemoryClawerSync()
        self.login_user(self.user)

    def personal_edition(self, publication_id: str, todo_id: int) -> ClawerPublication:
        item = {
            "title": "The reviewed launch action is ready",
            "detail": "Start with the confirmed action in the pilot Space.",
            "operational_publication_ids": [publication_id],
            "confirmed_todo_refs": [f"todo-{todo_id}"],
        }
        return ClawerPublication.model_validate(
            {
                "publication_id": "scenario-personal-morning",
                "idempotency_key": "scenario-personal-morning-identity",
                "business_identity": "scenario-personal-morning-business",
                "contract": "digest",
                "schema_version": "1.0",
                "producer_key": "personal_morning_brief",
                "producer_name": "Personal Morning Brief",
                "producing_version": "scenario:v1",
                "run_reference": "scenario-personal-run",
                "source_ref": self.SOURCE_REF,
                "covered_period": {
                    "start": "2026-08-11T00:00:00Z",
                    "end": "2026-08-11T13:00:00Z",
                },
                "payload": {
                    "contract": "digest",
                    "schema_version": "1.0",
                    "title": "A good place to start",
                    "timezone": "UTC",
                    "operation": "Private generation context.",
                    "marketing": "Private generation context.",
                    "metrics": {"messages": 1, "text": 1, "media": 0, "voice": 0},
                    "generation_context": "sanitized causal scenario",
                    "personal": {
                        "edition": "morning",
                        "teammate_ref": self.TEAMMATE_REF,
                        "teammate_display_name": "Fixture Teammate",
                        "morning": {
                            "urgency": [item],
                            "unresolved_carryover": [],
                            "guidance": [],
                            "all_clear_context": [],
                        },
                        "end_of_day": None,
                        "operational_publication_ids": [publication_id],
                        "confirmed_todo_refs": [f"todo-{todo_id}"],
                    },
                },
                "evidence_refs": [],
                "disputed_details": [],
                "importance": "normal",
                "occurred_at": "2026-08-11T13:00:00Z",
                "generated_at": "2026-08-11T13:01:00Z",
                "published_at": "2026-08-11T13:02:00Z",
                "lineage_key": None,
                "parent_publication_id": None,
                "material_change": False,
            }
        )

    def test_one_source_publication_traverses_review_todo_home_and_edition(self) -> None:
        scenario = load_hover_platform_scenario()
        publication = scenario.publication("suggested-action").model_copy(
            update={"source_ref": self.SOURCE_REF}, deep=True
        )
        self.adapter.publication_pages[
            (
                str(self.realm.uuid),
                str(self.account.external_account_id),
                self.SOURCE_REF,
                None,
            )
        ] = ClawerPublicationPage(
            publications=[publication], next_cursor="memory:scenario", has_more=False
        )

        with (
            self.assertLogs("zulip.hover.telemetry", level="INFO") as telemetry,
            self.captureOnCommitCallbacks(execute=True),
        ):
            sync_space_attachment(
                attachment_id=self.attachment.id,
                assistant=self.assistant,
                clawer_sync=self.adapter,
            )
        self.assertTrue(
            any("event=publication_sync outcome=success" in line for line in telemetry.output)
        )
        generated_item = GeneratedItem.objects.get(publication_id=publication.publication_id)
        action = SuggestedAction.objects.get(generated_item=generated_item)
        self.assertEqual(action.assignee, self.user)
        self.assertEqual(generated_item.evidence_links.count(), 1)

        assert self.space.stream is not None
        review_response = self.client_post(
            "/json/messages",
            {
                "type": "channel",
                "to": orjson.dumps(self.space.stream_id).decode(),
                "topic": generated_item.message.topic_name(),
                "content": "Confirmed after checking the linked source.",
                "hover_generated_item_id": generated_item.id,
                "hover_response_type": "review",
                "hover_review_field": "wording",
                "hover_review_value": orjson.dumps(
                    "Confirm the final reviewed launch caption."
                ).decode(),
            },
        )
        self.assert_json_success(review_response)
        action.refresh_from_db()
        self.assertEqual(action.wording, "Confirm the final reviewed launch caption.")

        approval = self.client_post(
            f"/json/hover/spaces/{self.space.id}/generated-items/"
            f"{generated_item.id}/suggested-action/decisions",
            {
                "decision": "approve",
                "request_id": str(uuid4()),
                "expected_version": action.version,
            },
        )
        self.assert_json_success(approval)
        todo = Todo.objects.get(suggested_action=action)
        self.assertEqual(todo.wording, "Confirm the final reviewed launch caption.")
        self.assertEqual(todo.assignee, self.user)

        awareness = get_awareness_projection(self.user, surface="for_you")
        projected = next(
            item for item in awareness if item["message_id"] == generated_item.message_id
        )
        self.assertIn("assignment", projected["reasons"])
        self.assertEqual(
            projected["hover_generated_item"]["suggested_action"]["todo"]["id"], todo.id
        )

        self.adapter.personal_edition_pages[
            (
                str(self.realm.uuid),
                str(self.account.external_account_id),
                self.TEAMMATE_REF,
                None,
            )
        ] = ClawerPublicationPage(
            publications=[self.personal_edition(publication.publication_id, todo.id)],
            next_cursor="memory:personal-scenario",
            has_more=False,
        )
        sync_status, errors = sync_personal_editions(
            user_profile=self.user, clawer_sync=self.adapter
        )
        self.assertEqual(sync_status, "current")
        self.assertEqual(errors, [])
        editions = get_personal_editions_for_user(user_profile=self.user)
        morning_item = editions["morning"]["sections"]["urgency"][0]
        self.assertEqual(morning_item["update"]["message_id"], generated_item.message_id)
        self.assertEqual(
            morning_item["update"]["evidence_url"],
            f"/json/hover/spaces/{self.space.id}/generated-items/{generated_item.id}/evidence",
        )
