from datetime import datetime, timezone
from unittest.mock import patch
from urllib.parse import urlencode
from uuid import uuid4

import orjson
from typing_extensions import override

from hover.actions_connected_accounts import (
    do_create_connected_account,
    do_set_connected_account_approval_state,
    do_upsert_connected_account_grant,
)
from hover.actions_integrations import do_associate_integration_route, do_detach_integration_route
from hover.actions_spaces import do_create_space, do_launch_space
from hover.lib import add_hover_metadata
from hover.models import (
    ConnectedAccount,
    IntegrationMessageProvenance,
    IntegrationRouteAssociation,
    Source,
    SpaceAttachment,
    SpaceMembership,
)
from zerver.actions.channel_folders import check_add_channel_folder
from zerver.lib.create_user import create_user
from zerver.lib.exceptions import JsonableError
from zerver.lib.message_cache import MessageDict
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.user_groups import get_system_user_group_by_name
from zerver.models import Message, UserProfile
from zerver.models.groups import SystemGroups


class HoverIntegrationProvenanceTest(ZulipTestCase):
    SOURCE_REF = "src_0123456789abcdef0123456789abcdef"

    @override
    def setUp(self) -> None:
        super().setUp()
        self.actor = self.example_user("hamlet")
        self.realm = self.actor.realm
        self.realm.hover_enabled = True
        self.realm.can_create_spaces_group = get_system_user_group_by_name(
            SystemGroups.MEMBERS, self.realm.id
        )
        self.realm.save(update_fields=["hover_enabled", "can_create_spaces_group"])
        self.bot = self.create_test_bot(
            "github-route",
            self.actor,
            full_name="GitHub integration",
            bot_type=UserProfile.INCOMING_WEBHOOK_BOT,
        )
        self.category = check_add_channel_folder(
            self.realm, "Programs", "", acting_user=self.example_user("iago")
        )
        self.space = do_create_space(
            self.actor, name="AIMTO Events", description="", category=self.category
        )
        self.account = do_create_connected_account(
            realm=self.realm,
            provider_key="github",
            provider_name="GitHub",
            external_account_id=uuid4(),
            display_name="AIMTO repositories",
            created_by=self.actor,
            owner=self.actor,
            connection_kind=ConnectedAccount.ConnectionKind.NATIVE_INTEGRATION,
            incoming_webhook_bot=self.bot,
        )
        do_set_connected_account_approval_state(
            self.account,
            ConnectedAccount.ApprovalState.APPROVED,
            acting_user=self.example_user("iago"),
        )
        do_upsert_connected_account_grant(
            self.account,
            self.actor,
            all_selectors=True,
            selector_specs=[],
            acting_user=self.example_user("iago"),
        )
        self.source = Source.objects.create(
            realm=self.realm,
            account=self.account,
            adapter_key="zulip_native",
            provider_key="github",
            provider_name="GitHub",
            source_type="repository_events",
            external_ref=self.SOURCE_REF,
            display_name="klovr-co/aimto",
            external_url="https://github.com/klovr-co/aimto",
            supports_live_capture=True,
        )
        self.attachment = SpaceAttachment.objects.create(
            realm=self.realm,
            space=self.space,
            source=self.source,
            state=SpaceAttachment.State.ACTIVE,
            history_window=SpaceAttachment.HistoryWindow.TODAY,
            history_timezone="UTC",
            history_start_at=datetime(2026, 8, 11, tzinfo=timezone.utc),
            attached_by=self.actor,
        )
        self.space, _ = do_launch_space(self.space, acting_user=self.actor)
        assert self.space.stream is not None
        self.stream = self.space.stream
        self.subscribe(self.bot, self.stream.name, invite_only=True)

    def associate(self) -> IntegrationRouteAssociation:
        route, created = do_associate_integration_route(
            acting_user=self.actor,
            space=self.space,
            attachment_id=self.attachment.id,
            bot_user_id=self.bot.id,
        )
        self.assertTrue(created)
        return route

    def integration_url(self, integration_name: str) -> str:
        query = urlencode({"stream": self.stream.name, "api_key": self.bot.api_key})
        return f"/api/v1/external/{integration_name}?{query}"

    def test_api_is_idempotent_projects_safe_route_and_requires_member_admin_grant(self) -> None:
        self.login_user(self.actor)
        data = {
            "attachment_id": orjson.dumps(self.attachment.id).decode(),
            "bot_user_id": orjson.dumps(self.bot.id).decode(),
        }
        result = self.client_post(f"/json/hover/spaces/{self.space.id}/integration-routes", data)
        payload = self.assert_json_success(result)
        route = payload["integration_route"]
        self.assertTrue(payload["created"])
        self.assertEqual(route["stream_id"], self.space.stream_id)
        self.assertEqual(route["bot_user_id"], self.bot.id)
        self.assertNotIn("api_key", orjson.dumps(payload).decode())
        projected_attachment = payload["space"]["attachments"][0]
        self.assertEqual(projected_attachment["source"]["provider_name"], "GitHub")
        self.assertEqual(projected_attachment["integration_routes"][0]["id"], route["id"])

        replay = self.assert_json_success(
            self.client_post(f"/json/hover/spaces/{self.space.id}/integration-routes", data)
        )
        self.assertFalse(replay["created"])

        detached = self.assert_json_success(
            self.client_delete(
                f"/json/hover/spaces/{self.space.id}/integration-routes/{route['id']}"
            )
        )
        self.assertEqual(
            detached["integration_route"]["state"], IntegrationRouteAssociation.State.DETACHED
        )
        self.assertEqual(detached["space"]["attachments"][0]["integration_routes"], [])

        non_admin = self.example_user("othello")
        SpaceMembership.objects.create(
            realm=self.realm,
            space=self.space,
            user=non_admin,
            role=SpaceMembership.Role.SUBSCRIBER,
            added_by=self.actor,
        )
        self.login_user(non_admin)
        self.assert_json_error(
            self.client_post(f"/json/hover/spaces/{self.space.id}/integration-routes", data),
            "Invalid Space ID",
        )

        realm_admin = self.example_user("iago")
        self.login_user(realm_admin)
        self.assert_json_error(
            self.client_post(f"/json/hover/spaces/{self.space.id}/integration-routes", data),
            "Invalid Space ID",
        )

    def test_native_message_preserves_body_and_gets_immutable_convergent_provenance(self) -> None:
        before_id = self.send_stream_message(
            self.bot, self.stream.name, content="native body", topic_name="push"
        )
        self.assertFalse(IntegrationMessageProvenance.objects.filter(message_id=before_id).exists())
        route = self.associate()

        message_id = self.send_stream_message(
            self.bot, self.stream.name, content="native body", topic_name="push"
        )
        message = Message.objects.get(id=message_id)
        self.assertEqual(message.content, "native body")
        self.assertEqual(message.topic_name(), "push")
        provenance = IntegrationMessageProvenance.objects.get(message=message)
        self.assertEqual(provenance.association, route)
        self.assertEqual(provenance.external_url, "https://github.com/klovr-co/aimto")

        event_dict = MessageDict.wide_dict(message, self.realm.id)
        add_hover_metadata([event_dict], realm_id=self.realm.id)
        event_metadata = event_dict["hover_source_provenance"]
        self.assertEqual(event_metadata["source"]["display_name"], "klovr-co/aimto")
        self.assertNotIn(self.SOURCE_REF, orjson.dumps(event_metadata).decode())

        self.source.display_name = "renamed later"
        self.source.external_url = "https://github.com/klovr-co/renamed"
        self.source.save(update_fields=["display_name", "external_url", "date_updated"])
        history_dict = MessageDict.wide_dict(message, self.realm.id)
        add_hover_metadata([history_dict], realm_id=self.realm.id)
        self.assertEqual(history_dict["hover_source_provenance"], event_metadata)

        do_detach_integration_route(acting_user=self.actor, space=self.space, route_id=route.id)
        after_id = self.send_stream_message(
            self.bot, self.stream.name, content="after detach", topic_name="push"
        )
        self.assertFalse(IntegrationMessageProvenance.objects.filter(message_id=after_id).exists())
        self.assertTrue(IntegrationMessageProvenance.objects.filter(message_id=message_id).exists())

    def test_native_github_webhook_keeps_its_message_and_gains_provenance(self) -> None:
        route = self.associate()
        message = self.send_webhook_payload(
            self.bot,
            self.integration_url("github"),
            self.webhook_fixture_data("github", "push__1_commit"),
            HTTP_X_GITHUB_EVENT="push",
            content_type="application/json",
        )

        self.assertEqual(message.topic_name(), "public-repo / changes")
        self.assertIn("baxterthehacker", message.content)
        provenance = IntegrationMessageProvenance.objects.get(message=message)
        self.assertEqual(provenance.association, route)
        self.assertEqual(provenance.provider_name, "GitHub")

    def test_slack_compatible_webhook_uses_configured_provider_metadata(self) -> None:
        self.account.provider_key = "apify"
        self.account.provider_name = "Apify"
        self.account.display_name = "AIMTO Apify"
        self.account.save(
            update_fields=["provider_key", "provider_name", "display_name", "date_updated"]
        )
        self.source.provider_key = "instagram"
        self.source.provider_name = "Instagram"
        self.source.source_type = "profile_events"
        self.source.display_name = "AIMTO Instagram"
        self.source.external_url = "https://www.instagram.com/aimto.my/"
        self.source.save(
            update_fields=[
                "provider_key",
                "provider_name",
                "source_type",
                "display_name",
                "external_url",
                "date_updated",
            ]
        )
        route = self.associate()
        message = self.send_webhook_payload(
            self.bot,
            self.integration_url("slack_incoming"),
            {"text": "New Instagram mention from Apify"},
            content_type="application/json",
        )

        self.assertEqual(message.topic_name(), "")
        self.assertEqual(message.content, "New Instagram mention from Apify")
        provenance = IntegrationMessageProvenance.objects.get(message=message)
        self.assertEqual(provenance.association, route)
        self.assertEqual(provenance.provider_key, "instagram")
        self.assertEqual(provenance.provider_name, "Instagram")

    def test_runtime_stops_on_account_revoke_and_wrong_destination(self) -> None:
        self.associate()
        wrong_stream = self.subscribe(self.bot, "Denmark")
        wrong_id = self.send_stream_message(self.bot, wrong_stream.name)
        self.assertFalse(IntegrationMessageProvenance.objects.filter(message_id=wrong_id).exists())

        self.account.approval_state = ConnectedAccount.ApprovalState.REVOKED
        self.account.save(update_fields=["approval_state", "date_updated"])
        revoked_id = self.send_stream_message(self.bot, self.stream.name)
        self.assertFalse(
            IntegrationMessageProvenance.objects.filter(message_id=revoked_id).exists()
        )

    def test_bot_cannot_ambiguously_serve_two_sources(self) -> None:
        self.associate()
        source = Source.objects.create(
            realm=self.realm,
            account=self.account,
            adapter_key="zulip_native",
            provider_key="github",
            provider_name="GitHub",
            source_type="repository_events",
            external_ref="src_ffffffffffffffffffffffffffffffff",
            display_name="another repository",
            external_url="https://github.com/klovr-co/another",
            supports_live_capture=True,
        )
        attachment = SpaceAttachment.objects.create(
            realm=self.realm,
            space=self.space,
            source=source,
            state=SpaceAttachment.State.ACTIVE,
            history_window=SpaceAttachment.HistoryWindow.TODAY,
            history_timezone="UTC",
            history_start_at=datetime(2026, 8, 11, tzinfo=timezone.utc),
            attached_by=self.actor,
        )
        with self.assertRaisesRegex(JsonableError, "already assigned"):
            do_associate_integration_route(
                acting_user=self.actor,
                space=self.space,
                attachment_id=attachment.id,
                bot_user_id=self.bot.id,
            )

    def test_capture_failure_rolls_back_native_message(self) -> None:
        self.associate()
        before = Message.objects.count()
        with (
            self.artificial_transaction_savepoint(),
            patch(
                "hover.integration_capture.IntegrationMessageProvenance.objects.bulk_create",
                side_effect=RuntimeError("capture failed"),
            ),
            self.assertRaisesRegex(RuntimeError, "capture failed"),
        ):
            self.send_stream_message(self.bot, self.stream.name)
        self.assertEqual(Message.objects.count(), before)

    def test_models_reject_unsafe_links_and_cross_realm_bots(self) -> None:
        self.source.external_url = "http://github.example/repository"
        with self.assertRaisesRegex(Exception, "HTTPS"):
            self.source.full_clean()

        other_owner = self.lear_user("cordelia")
        other_bot = create_user(
            "other-route-bot@lear.testserver",
            None,
            other_owner.realm,
            "Other route",
            bot_type=UserProfile.INCOMING_WEBHOOK_BOT,
            bot_owner=other_owner,
        )
        account = ConnectedAccount(
            realm=self.realm,
            provider_key="github",
            provider_name="GitHub",
            external_account_id=uuid4(),
            display_name="Cross realm",
            created_by=self.actor,
            owner=self.actor,
            connection_kind=ConnectedAccount.ConnectionKind.NATIVE_INTEGRATION,
            incoming_webhook_bot=other_bot,
        )
        with self.assertRaisesRegex(Exception, "share the organization"):
            account.full_clean()
