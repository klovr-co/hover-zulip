from typing import Any

import orjson
from typing_extensions import override

from hover.models import Connector, Pipeline, PipelineCreatorAssignment
from zerver.lib.test_classes import ZulipTestCase


class HoverPipelinesTest(ZulipTestCase):
    PIPELINES_URL = "/json/hover/pipelines"
    CONNECTORS_URL = "/json/hover/connectors"

    @override
    def setUp(self) -> None:
        super().setUp()
        self.actor = self.example_user("hamlet")
        self.other_user = self.example_user("othello")
        self.source_stream = self.make_stream("Product & Engineering", realm=self.actor.realm)
        self.output_stream = self.make_stream("Product updates", realm=self.actor.realm)
        self.subscribe(self.actor, self.source_stream.name)
        self.subscribe(self.actor, self.output_stream.name)
        PipelineCreatorAssignment.objects.create(realm=self.actor.realm, user=self.actor)

    def json_data(self, **values: Any) -> dict[str, str]:
        return {key: orjson.dumps(value).decode() for key, value in values.items()}

    def create_connector(self) -> Connector:
        response = self.client_post(
            self.CONNECTORS_URL,
            self.json_data(
                provider_key="github",
                destination_name=self.source_stream.name,
                topic="GitHub activity",
                event_options=[],
            ),
        )
        connector_id = self.assert_json_success(response)["connector"]["id"]
        return Connector.objects.get(id=connector_id)

    def pipeline_data(self, connector: Connector, **overrides: Any) -> dict[str, str]:
        values: dict[str, Any] = {
            "connector_id": connector.id,
            "name": "GitHub release brief",
            "instruction": "Summarize release progress, blockers, and decisions.",
            "cadence": "daily",
            "local_time": "09:00",
            "timezone": "Asia/Kuala_Lumpur",
            "output_destination_name": self.output_stream.name,
            "output_topic": "GitHub release brief",
        }
        values.update(overrides)
        return self.json_data(**values)

    def test_create_and_list_pipeline(self) -> None:
        self.login_user(self.actor)
        connector = self.create_connector()
        created = self.assert_json_success(
            self.client_post(self.PIPELINES_URL, self.pipeline_data(connector))
        )["pipeline"]

        pipeline = Pipeline.objects.get(id=created["id"])
        self.assertEqual(pipeline.connector, connector)
        self.assertEqual(pipeline.output_destination, self.output_stream)
        self.assertEqual(created["provider_name"], "GitHub")
        self.assertEqual(created["source_topic"], "GitHub activity")
        self.assertEqual(created["local_time"], "09:00")
        self.assertIsNone(created["weekday"])
        self.assertEqual(created["status"], Pipeline.State.ACTIVE)

        listed = self.assert_json_success(self.client_get(self.PIPELINES_URL))["pipelines"]
        self.assertEqual([item["id"] for item in listed], [pipeline.id])

        connector.state = Connector.State.NEEDS_ATTENTION
        connector.save(update_fields=["state", "date_updated"])
        listed = self.assert_json_success(self.client_get(self.PIPELINES_URL))["pipelines"]
        self.assertEqual(listed[0]["status"], Pipeline.State.NEEDS_ATTENTION)

        self.login_user(self.other_user)
        response = self.assert_json_success(self.client_get(self.PIPELINES_URL))
        self.assertEqual(response["pipelines"], [])
        self.assertFalse(response["can_create"])

    def test_pipeline_requires_creator_capability(self) -> None:
        self.login_user(self.actor)
        connector = self.create_connector()
        PipelineCreatorAssignment.objects.filter(user=self.actor).delete()
        self.assert_json_error(
            self.client_post(self.PIPELINES_URL, self.pipeline_data(connector)),
            "You do not have permission to create Pipelines.",
        )

    def test_pipeline_enforces_exactly_one_source(self) -> None:
        self.login_user(self.actor)
        connector = self.create_connector()
        self.assert_json_success(self.client_post(self.PIPELINES_URL, self.pipeline_data(connector)))
        self.assert_json_error(
            self.client_post(
                self.PIPELINES_URL,
                self.pipeline_data(connector, name="Second pipeline"),
            ),
            "That data source already belongs to a Pipeline.",
        )

    def test_pipeline_rejects_unmanaged_or_invalid_source(self) -> None:
        self.login_user(self.actor)
        connector = self.create_connector()
        connector.state = Connector.State.DISABLED
        connector.save(update_fields=["state", "date_updated"])
        self.assert_json_error(
            self.client_post(self.PIPELINES_URL, self.pipeline_data(connector)),
            "Choose an active connector for this Pipeline.",
        )

        connector.state = Connector.State.ACTIVE
        connector.save(update_fields=["state", "date_updated"])
        PipelineCreatorAssignment.objects.create(realm=self.other_user.realm, user=self.other_user)
        self.login_user(self.other_user)
        self.assert_json_error(
            self.client_post(self.PIPELINES_URL, self.pipeline_data(connector)),
            "You do not have permission to manage this connector.",
        )

    def test_pipeline_validates_schedule_and_output(self) -> None:
        self.login_user(self.actor)
        connector = self.create_connector()
        self.assert_json_error(
            self.client_post(
                self.PIPELINES_URL,
                self.pipeline_data(connector, cadence="hourly"),
            ),
            "Invalid Pipeline schedule.",
        )
        self.assert_json_error(
            self.client_post(
                self.PIPELINES_URL,
                self.pipeline_data(connector, timezone="Mars/Olympus_Mons"),
            ),
            "Invalid IANA timezone.",
        )
        self.assert_json_error(
            self.client_post(
                self.PIPELINES_URL,
                self.pipeline_data(connector, local_time="09:00:30"),
            ),
            "Pipeline schedules must use whole minutes.",
        )
        self.assert_json_error(
            self.client_post(
                self.PIPELINES_URL,
                self.pipeline_data(connector, local_time="09:00+05:30"),
            ),
            "Pipeline schedules must use whole minutes.",
        )
        self.assert_json_error(
            self.client_post(
                self.PIPELINES_URL,
                self.pipeline_data(connector, cadence="weekly"),
            ),
            "Choose a weekday for a weekly Pipeline.",
        )
        created = self.assert_json_success(
            self.client_post(
                self.PIPELINES_URL,
                self.pipeline_data(connector, cadence="weekly", weekday=4),
            )
        )["pipeline"]
        self.assertEqual(created["weekday"], Pipeline.Weekday.FRIDAY)

    def test_pipeline_list_hides_inaccessible_private_output(self) -> None:
        self.login_user(self.actor)
        connector = self.create_connector()
        administrator = self.example_user("iago")
        private_output = self.make_stream(
            "Private leadership updates", realm=self.actor.realm, invite_only=True
        )
        self.subscribe(administrator, private_output.name)

        self.login_user(administrator)
        self.assert_json_success(
            self.client_post(
                self.PIPELINES_URL,
                self.pipeline_data(
                    connector,
                    output_destination_name=private_output.name,
                    output_topic="Confidential launch",
                ),
            )
        )

        self.login_user(self.actor)
        response = self.assert_json_success(self.client_get(self.PIPELINES_URL))
        self.assertEqual(response["pipelines"], [])
