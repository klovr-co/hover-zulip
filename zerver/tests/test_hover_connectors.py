import importlib
from typing import Any
from unittest.mock import patch
from urllib.parse import parse_qs, urlencode, urlsplit

import orjson
from django.apps import apps
from typing_extensions import override

from hover.actions_connectors import record_connector_delivery
from hover.lib_connectors import get_connector_provider_metadata
from hover.models import Connector
from zerver.lib.event_schema import check_hover_connector
from zerver.lib.integrations import INCOMING_WEBHOOK_INTEGRATIONS
from zerver.lib.test_classes import ZulipTestCase
from zerver.models import BotConfigData, Message, UserProfile


class HoverConnectorsTest(ZulipTestCase):
    CONNECTORS_URL = "/json/hover/connectors"

    @override
    def setUp(self) -> None:
        super().setUp()
        self.actor = self.example_user("hamlet")
        self.other_user = self.example_user("othello")
        self.admin = self.example_user("iago")
        self.stream = self.make_stream("Connector signals", realm=self.actor.realm)
        self.subscribe(self.actor, self.stream.name)
        self.subscribe(self.admin, self.stream.name)

    def connector_data(self, **overrides: Any) -> dict[str, str]:
        data: dict[str, Any] = {
            "provider_key": "github",
            "destination_name": self.stream.name,
            "topic": "Deployments",
            "event_options": ["deployment", "deployment_status"],
        }
        data.update(overrides)
        return {key: orjson.dumps(value).decode() for key, value in data.items()}

    def connector_update_data(self, **overrides: Any) -> dict[str, str]:
        data = self.connector_data(**overrides)
        del data["provider_key"]
        return data

    def create_connector(self, **overrides: Any) -> tuple[Connector, dict[str, Any]]:
        response = self.client_post(
            self.CONNECTORS_URL,
            self.connector_data(**overrides),
        )
        payload = self.assert_json_success(response)["connector"]
        return Connector.objects.select_related("bot", "destination").get(id=payload["id"]), payload

    def test_create_list_detail_and_permissions(self) -> None:
        self.login_user(self.actor)
        connector, created = self.create_connector()

        self.assertEqual(connector.provider_key, "github")
        self.assertEqual(connector.provider_name, "GitHub")
        self.assertEqual(connector.name, "GitHub")
        self.assertEqual(connector.destination, self.stream)
        self.assertEqual(connector.created_by, self.actor)
        self.assertEqual(connector.owner, self.actor)
        self.assertEqual(created["credential_identity_id"], connector.bot_id)
        self.assertEqual(created["event_options"], ["deployment", "deployment_status"])
        self.assertIn("/api/v1/external/github?", created["webhook_url"])
        self.assertIn("api_key=", created["webhook_url"])
        self.assertNotIn(
            "webhook_url",
            self.assert_json_success(self.client_get(self.CONNECTORS_URL))["connectors"][0],
        )

        self.login_user(self.other_user)
        self.assertEqual(
            self.assert_json_success(self.client_get(self.CONNECTORS_URL))["connectors"],
            [],
        )
        self.assert_json_error(
            self.client_get(f"{self.CONNECTORS_URL}/{connector.id}"),
            "You do not have permission to manage this connector.",
        )

        self.login_user(self.admin)
        listed = self.assert_json_success(self.client_get(self.CONNECTORS_URL))["connectors"]
        self.assertEqual([item["id"] for item in listed], [connector.id])

    def test_provider_event_validation_and_registry_metadata(self) -> None:
        self.login_user(self.actor)
        self.assert_json_error(
            self.client_post(
                self.CONNECTORS_URL,
                self.connector_data(
                    provider_key="slack_incoming",
                    event_options=["push"],
                ),
            ),
            "Choose supported events for this connector.",
        )
        self.assert_json_error(
            self.client_post(
                self.CONNECTORS_URL,
                self.connector_data(provider_key="not_a_provider", event_options=[]),
            ),
            "Invalid connector provider.",
        )

        for integration in INCOMING_WEBHOOK_INTEGRATIONS:
            if integration.legacy:
                continue
            metadata = get_connector_provider_metadata(integration.name)
            self.assertEqual(metadata["key"], integration.name)
            self.assertTrue(metadata["name"])
            self.assertTrue(metadata["logo_url"])
            self.assertTrue(metadata["description"])
            self.assertIn("supports_event_filters", metadata)
        self.assertEqual(get_connector_provider_metadata("rest_api")["name"], "REST API")

    def test_update_rotate_disable_and_reconcile(self) -> None:
        self.login_user(self.actor)
        connector, created = self.create_connector()
        original_url = created["webhook_url"]
        original_api_key = connector.bot.api_key

        updated = self.assert_json_success(
            self.client_patch(
                f"{self.CONNECTORS_URL}/{connector.id}",
                self.connector_update_data(
                    name="GitHub deployments",
                    destination_name=self.stream.name,
                    topic="Release readiness",
                    event_options=["deployment"],
                ),
            )
        )["connector"]
        self.assertEqual(updated["topic"], "Release readiness")
        self.assertEqual(updated["name"], "GitHub deployments")
        self.assertEqual(updated["event_options"], ["deployment"])

        rotated = self.assert_json_success(
            self.client_post(f"{self.CONNECTORS_URL}/{connector.id}/rotate", {})
        )["connector"]
        self.assertNotEqual(rotated["webhook_url"], original_url)
        connector.bot.refresh_from_db()
        self.assertNotEqual(connector.bot.api_key, original_api_key)

        connector.reconciliation_state = Connector.ReconciliationState.AMBIGUOUS
        connector.state = Connector.State.NEEDS_ATTENTION
        connector.destination = None
        connector.save(
            update_fields=["reconciliation_state", "state", "destination", "date_updated"]
        )
        preserved_api_key = connector.bot.api_key
        legacy_detail = self.assert_json_success(
            self.client_get(f"{self.CONNECTORS_URL}/{connector.id}")
        )["connector"]
        self.assertNotIn("webhook_url", legacy_detail)
        self.assert_json_error(
            self.client_post(f"{self.CONNECTORS_URL}/{connector.id}/rotate", {}),
            "Reconcile this legacy connector before rotating its URL.",
        )

        reconciled = self.assert_json_success(
            self.client_patch(
                f"{self.CONNECTORS_URL}/{connector.id}/reconcile",
                self.connector_data(topic="Reconciled", event_options=["deployment"]),
            )
        )["connector"]
        connector.refresh_from_db()
        connector.bot.refresh_from_db()
        self.assertEqual(connector.reconciliation_state, Connector.ReconciliationState.CANONICAL)
        self.assertEqual(connector.bot.api_key, preserved_api_key)
        self.assertIn("webhook_url", reconciled)

        disabled = self.assert_json_success(
            self.client_delete(f"{self.CONNECTORS_URL}/{connector.id}")
        )["connector"]
        self.assertEqual(disabled["state"], Connector.State.DISABLED)
        self.assertNotIn("webhook_url", disabled)
        self.assert_json_error(
            self.client_post(f"{self.CONNECTORS_URL}/{connector.id}/rotate", {}),
            "This connector is disabled.",
        )
        self.assert_json_error(
            self.client_patch(
                f"{self.CONNECTORS_URL}/{connector.id}",
                self.connector_update_data(topic="Should not change"),
            ),
            "This connector is disabled.",
        )

    def test_real_webhook_delivery_updates_health(self) -> None:
        self.login_user(self.actor)
        connector, created = self.create_connector(
            provider_key="rest_api",
            topic="Internal tools",
            event_options=[],
        )
        webhook = urlsplit(created["webhook_url"])
        response = self.client.post(
            f"{webhook.path}?{webhook.query}",
            data=orjson.dumps({"status": "ready"}),
            content_type="application/json",
            HTTP_HOST=webhook.netloc,
        )
        self.assert_json_success(response)
        connector.refresh_from_db()
        self.assertEqual(connector.health_status, Connector.HealthStatus.HEALTHY)
        self.assertEqual(
            connector.last_delivery_status,
            Connector.LastDeliveryStatus.SUCCESS,
        )
        self.assertIsNotNone(connector.last_successful_delivery)
        self.assertTrue(Message.objects.filter(sender=connector.bot).exists())

        query = parse_qs(webhook.query)
        query["stream"] = [str(self.INVALID_STREAM_ID)]
        failed_response = self.client.post(
            f"{webhook.path}?{urlencode(query, doseq=True)}",
            data=orjson.dumps({"status": "missing destination"}),
            content_type="application/json",
            HTTP_HOST=webhook.netloc,
        )
        self.assert_json_error(
            failed_response,
            f"Channel with ID '{self.INVALID_STREAM_ID}' does not exist",
        )
        connector.refresh_from_db()
        self.assertEqual(connector.health_status, Connector.HealthStatus.DEGRADED)
        self.assertEqual(
            connector.last_delivery_status,
            Connector.LastDeliveryStatus.FAILURE,
        )
        self.assertIsNotNone(connector.last_successful_delivery)

    def test_delivery_live_event_schema(self) -> None:
        self.login_user(self.actor)
        connector, _created = self.create_connector()
        with patch("hover.actions_connectors.send_event_on_commit") as send_event:
            record_connector_delivery(connector.bot, successful=True)

        send_event.assert_called_once()
        realm, event, recipient_ids = send_event.call_args.args
        self.assertEqual(realm, self.actor.realm)
        self.assertIn(self.actor.id, recipient_ids)
        check_hover_connector("event", {"id": 1, **event})

    def test_migration_provider_inference_uses_registry_identity(self) -> None:
        self.login_user(self.actor)
        connector, _created = self.create_connector()
        BotConfigData.objects.filter(bot_profile=connector.bot, key="integration_id").update(
            value="custom_build_system"
        )
        migration = importlib.import_module("hover.migrations.0023_connectors")
        self.assertEqual(
            migration.infer_provider(connector.bot, BotConfigData),
            ("custom_build_system", "Custom Build System"),
        )

        BotConfigData.objects.filter(bot_profile=connector.bot, key="integration_id").delete()
        connector.bot.full_name = "GitHub webhook"
        connector.bot.save(update_fields=["full_name"])
        self.assertEqual(
            migration.infer_provider(connector.bot, BotConfigData),
            ("github", "GitHub"),
        )

    def test_migration_backfill_requires_exactly_one_destination(self) -> None:
        recognized_bot = self.create_test_bot(
            "legacy-github",
            self.actor,
            full_name="GitHub webhook",
            bot_type=UserProfile.INCOMING_WEBHOOK_BOT,
        )
        self.subscribe(recognized_bot, self.stream.name)

        ambiguous_bot = self.create_test_bot(
            "legacy-unknown",
            self.actor,
            full_name="Private build feed",
            bot_type=UserProfile.INCOMING_WEBHOOK_BOT,
        )
        second_stream = self.make_stream("Second connector destination", realm=self.actor.realm)
        self.subscribe(ambiguous_bot, self.stream.name)
        self.subscribe(ambiguous_bot, second_stream.name)

        inactive_bot = self.create_test_bot(
            "legacy-inactive",
            self.actor,
            full_name="GitHub connector",
            bot_type=UserProfile.INCOMING_WEBHOOK_BOT,
        )
        inactive_bot.is_active = False
        inactive_bot.save(update_fields=["is_active"])

        migration = importlib.import_module("hover.migrations.0023_connectors")
        migration.backfill_connectors(apps, None)

        recognized = Connector.objects.get(bot=recognized_bot)
        self.assertEqual(recognized.provider_key, "github")
        self.assertEqual(recognized.destination, self.stream)
        self.assertEqual(recognized.state, Connector.State.ACTIVE)
        self.assertEqual(
            recognized.reconciliation_state,
            Connector.ReconciliationState.LEGACY,
        )

        ambiguous = Connector.objects.get(bot=ambiguous_bot)
        self.assertEqual(ambiguous.provider_key, "legacy")
        self.assertIsNone(ambiguous.destination)
        self.assertEqual(ambiguous.state, Connector.State.NEEDS_ATTENTION)
        self.assertEqual(
            ambiguous.reconciliation_state,
            Connector.ReconciliationState.AMBIGUOUS,
        )
        self.assertFalse(Connector.objects.filter(bot=inactive_bot).exists())

        migration.backfill_connectors(apps, None)
        self.assertEqual(Connector.objects.filter(bot=recognized_bot).count(), 1)
