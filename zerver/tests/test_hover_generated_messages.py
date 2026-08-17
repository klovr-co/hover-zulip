from django.core.exceptions import ValidationError
from typing_extensions import override

from hover.models import EvidenceLink, GeneratedItem
from zerver.models import Message
from zerver.tests.test_events import BaseAction


class HoverGeneratedMessageTest(BaseAction):
    @override
    def setUp(self) -> None:
        super().setUp()
        self.user_profile.realm.hover_enabled = True
        self.user_profile.realm.save(update_fields=["hover_enabled"])

    def test_generated_item_rejects_message_from_another_realm(self) -> None:
        hamlet = self.example_user("hamlet")
        message_id = self.send_stream_message(
            hamlet,
            "Verona",
            "An organization-scoped generated item",
            "Project status",
        )

        generated_item = GeneratedItem(
            realm=self.mit_user("sipbtest").realm,
            message=Message.objects.get(id=message_id),
            output_type=GeneratedItem.OutputType.PROGRESS_UPDATE,
            module_key="project_status",
            module_name="Project Status",
            module_version="v3",
            source_summary="Across 2 sources",
        )

        with self.assertRaisesRegex(
            ValidationError, "Generated items and messages must share an organization"
        ):
            generated_item.full_clean()

    def test_evidence_link_rejects_generated_item_from_another_realm(self) -> None:
        hamlet = self.example_user("hamlet")
        message_id = self.send_stream_message(
            hamlet,
            "Verona",
            "An organization-scoped evidence link",
            "Project status",
        )
        generated_item = GeneratedItem.objects.create(
            realm=hamlet.realm,
            message=Message.objects.get(id=message_id),
            output_type=GeneratedItem.OutputType.PROGRESS_UPDATE,
            module_key="project_status",
            module_name="Project Status",
            module_version="v3",
            source_summary="Across 2 sources",
        )
        evidence_link = EvidenceLink(
            generated_item=generated_item,
            realm=self.mit_user("sipbtest").realm,
            position=0,
            provider_key="github",
            provider_name="GitHub",
            display_name="Project repository",
            url="https://github.com/example/project",
        )

        with self.assertRaisesRegex(
            ValidationError, "Evidence links and generated items must share an organization"
        ):
            evidence_link.full_clean()

    def test_initial_fetch_and_realtime_event_share_structured_metadata(self) -> None:
        hamlet = self.example_user("hamlet")
        hamlet.realm.hover_enabled = True
        hamlet.realm.save(update_fields=["hover_enabled"])
        self.login_user(hamlet)

        with self.verify_action(client_gravatar=False) as events:
            message_id = self.send_stream_message(
                hamlet,
                "Verona",
                "A source-backed native message",
                "Project status",
                skip_capture_on_commit_callbacks=True,
            )
            message = Message.objects.get(id=message_id)
            generated_item = GeneratedItem.objects.create(
                realm=hamlet.realm,
                message=message,
                output_type=GeneratedItem.OutputType.PROGRESS_UPDATE,
                module_key="project_status",
                module_name="Project Status",
                module_version="v3",
                source_summary="Across 2 sources",
            )
            EvidenceLink.objects.bulk_create(
                [
                    EvidenceLink(
                        generated_item=generated_item,
                        realm=hamlet.realm,
                        position=0,
                        provider_key="whatsapp",
                        provider_name="WhatsApp",
                        display_name="Operations",
                    ),
                    EvidenceLink(
                        generated_item=generated_item,
                        realm=hamlet.realm,
                        position=1,
                        provider_key="github",
                        provider_name="GitHub",
                        display_name="Project repository",
                        url="https://github.com/example/project",
                    ),
                ]
            )

        event_metadata = events[0]["message"]["hover_generated_item"]
        fetched_messages = self.get_messages(
            anchor=message_id,
            num_before=0,
            num_after=0,
        )
        self.assert_length(fetched_messages, 1)
        self.assertEqual(fetched_messages[0]["hover_generated_item"], event_metadata)
        self.assertEqual(event_metadata["output_type"], "progress_update")
        self.assertEqual(event_metadata["module"]["version"], "v3")
        self.assertEqual(event_metadata["presentation"]["label"], "Progress update")
        self.assertEqual(event_metadata["presentation"]["importance"], "normal")
        self.assertTrue(event_metadata["lineage"]["is_latest"])
        self.assertEqual(
            [source["key"] for source in event_metadata["sources"]], ["whatsapp", "github"]
        )

    def test_message_edit_event_refreshes_generated_metadata(self) -> None:
        hamlet = self.example_user("hamlet")
        hamlet.realm.hover_enabled = True
        hamlet.realm.save(update_fields=["hover_enabled"])
        self.login_user(hamlet)
        message_id = self.send_stream_message(
            hamlet,
            "Verona",
            "A generated message before editing",
            "Project status",
        )
        generated_item = GeneratedItem.objects.create(
            realm=hamlet.realm,
            message=Message.objects.get(id=message_id),
            output_type=GeneratedItem.OutputType.PROGRESS_UPDATE,
            module_key="project_status",
            module_name="Project Status",
            module_version="v3",
            source_summary="Across 2 sources",
        )

        with self.verify_action(state_change_expected=False) as events:
            result = self.client_patch(
                f"/json/messages/{message_id}",
                {"content": "A generated message after editing"},
            )
        self.assert_json_success(result)
        self.assert_length(events, 1)
        event = events[0]
        self.assertEqual(event["type"], "update_message")
        self.assertNotIn("message_realm_id", event)
        self.assertEqual(event["hover_generated_item"]["id"], generated_item.id)
        self.assertEqual(event["hover_generated_item"]["module"]["key"], "project_status")

    def test_lineage_projects_latest_state_and_authorized_history(self) -> None:
        hamlet = self.example_user("hamlet")
        hamlet.realm.hover_enabled = True
        hamlet.realm.save(update_fields=["hover_enabled"])
        self.login_user(hamlet)
        first_id = self.send_stream_message(hamlet, "Verona", "First state", "Decisions")
        latest_id = self.send_stream_message(hamlet, "Verona", "Latest state", "Decisions")
        for message_id, lifecycle in [(first_id, "active"), (latest_id, "reversed")]:
            GeneratedItem.objects.create(
                realm=hamlet.realm,
                message=Message.objects.get(id=message_id),
                output_type=GeneratedItem.OutputType.DECISION,
                module_key="decisions",
                module_name="Decisions",
                module_version="v1",
                source_summary="From Operations",
                lineage_key="decision-13",
                payload={"title": f"State {lifecycle}", "lifecycle": lifecycle},
            )

        fetched = self.get_messages(anchor=latest_id, num_before=1, num_after=0)
        by_id = {message["id"]: message["hover_generated_item"] for message in fetched}
        self.assertFalse(by_id[first_id]["lineage"]["is_latest"])
        self.assertTrue(by_id[latest_id]["lineage"]["is_latest"])
        self.assertEqual(by_id[latest_id]["presentation"]["state"], "reversed")
        self.assertEqual(
            [entry["message_id"] for entry in by_id[latest_id]["lineage"]["history"]],
            [latest_id, first_id],
        )

    def test_ordinary_message_has_no_hover_metadata(self) -> None:
        hamlet = self.example_user("hamlet")
        self.login_user(hamlet)
        message_id = self.send_stream_message(
            hamlet,
            "Verona",
            "https://github.com/example/project from an ordinary assistant",
            "Project Status",
        )

        fetched_messages = self.get_messages(anchor=message_id, num_before=0, num_after=0)
        self.assert_length(fetched_messages, 1)
        self.assertNotIn("hover_generated_item", fetched_messages[0])
