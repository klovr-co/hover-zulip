import importlib
from typing import Any
from unittest.mock import patch

import orjson
from typing_extensions import override

from hover.models import (
    Connector,
    Pipeline,
    PipelineAuthoredMessage,
    PipelineCreatorAssignment,
    PipelineRun,
)
from hover.pipeline_execution import execute_pipeline, runnable_pipelines
from hover.pipeline_lifecycle import (
    do_restore_stream_pipeline_inputs,
    do_update_pipeline_inputs_for_topic_move,
)
from zerver.lib.exceptions import JsonableError
from zerver.lib.test_classes import ZulipTestCase, get_topic_messages
from zerver.models.messages import Message


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

    def create_connector(
        self, *, name: str = "GitHub", topic: str = "Release activity"
    ) -> Connector:
        response = self.client_post(
            self.CONNECTORS_URL,
            self.json_data(
                provider_key="github",
                name=name,
                destination_name=self.source_stream.name,
                topic=topic,
                event_options=[],
            ),
        )
        connector_id = self.assert_json_success(response)["connector"]["id"]
        return Connector.objects.get(id=connector_id)

    def pipeline_payload(self, **overrides: Any) -> dict[str, str]:
        values: dict[str, Any] = {
            "input_destination_name": self.source_stream.name,
            "input_topic": "Release activity",
            "name": "Release brief",
            "instruction": "Summarize progress, blockers, and decisions.",
            "cadence": "daily",
            "local_time": "09:00",
            "timezone": "Asia/Kuala_Lumpur",
            "output_destination_name": self.output_stream.name,
            "output_topic": "Release brief",
        }
        values.update(overrides)
        return self.json_data(**values)

    def create_pipeline(self, **overrides: Any) -> Pipeline:
        input_topic = overrides.get("input_topic", "Release activity")
        existing_messages = get_topic_messages(self.actor, self.source_stream, input_topic)
        if (
            not existing_messages
            and not Connector.objects.filter(
                destination=self.source_stream, topic__iexact=input_topic
            ).exists()
        ):
            self.send_stream_message(self.actor, self.source_stream.name, topic_name=input_topic)
        created = self.assert_json_success(
            self.client_post(self.PIPELINES_URL, self.pipeline_payload(**overrides))
        )["pipeline"]
        return Pipeline.objects.get(id=created["id"])

    def test_migration_backfill_value_contract(self) -> None:
        migration = importlib.import_module("hover.migrations.0027_topic_first_pipelines")
        backfill = migration.topic_input_backfill_values
        self.assertEqual(backfill(9, "  Releases  "), (9, "Releases", "active", "available"))
        self.assertEqual(
            backfill(None, "Releases"), (None, "Releases", "draft", "topic_unavailable")
        )
        self.assertEqual(backfill(9, "   "), (None, "", "draft", "topic_unavailable"))
        self.assertEqual(
            backfill(9, "Releases", same_realm=False),
            (None, "Releases", "draft", "topic_unavailable"),
        )

    def test_lifecycle_migration_classifies_every_legacy_state(self) -> None:
        migration = importlib.import_module("hover.migrations.0029_pipeline_lifecycle_expand")
        classify = migration.lifecycle_backfill_values
        self.assertEqual(classify("active", "available", 1, "Topic"), ("active", "available"))
        self.assertEqual(
            classify("draft", "topic_unavailable", None, ""),
            ("draft", "topic_unavailable"),
        )
        self.assertEqual(
            classify("needs_attention", "available", 1, "Topic"),
            ("active", "topic_unavailable"),
        )
        self.assertEqual(
            classify("needs_attention", "available", None, ""),
            ("draft", "topic_unavailable"),
        )

    def test_create_draft_and_projection_transitions(self) -> None:
        self.login_user(self.actor)
        self.send_stream_message(self.actor, self.source_stream.name, topic_name="Release activity")
        created = self.assert_json_success(
            self.client_post(
                self.PIPELINES_URL,
                self.pipeline_payload(lifecycle_state=Pipeline.State.DRAFT),
            )
        )["pipeline"]
        self.assertEqual(created["lifecycle_state"], Pipeline.State.DRAFT)
        self.assertEqual(created["status"], Pipeline.State.DRAFT)
        self.assertEqual(created["available_transitions"], ["edit", "activate"])
        pipeline = Pipeline.objects.get(id=created["id"])
        self.assertFalse(runnable_pipelines().filter(id=pipeline.id).exists())

        pipeline.input_availability = Pipeline.InputAvailability.TOPIC_UNAVAILABLE
        pipeline.save(update_fields=["input_availability"])
        draft_with_unavailable_input = self.assert_json_success(
            self.client_get(self.PIPELINES_URL)
        )["pipelines"][0]
        self.assertEqual(draft_with_unavailable_input["status"], Pipeline.State.DRAFT)
        pipeline.input_availability = Pipeline.InputAvailability.AVAILABLE
        pipeline.save(update_fields=["input_availability"])

        activated = self.assert_json_success(
            self.client_patch(
                f"{self.PIPELINES_URL}/{pipeline.id}",
                self.json_data(lifecycle_state=Pipeline.State.ACTIVE),
            )
        )["pipeline"]
        self.assertEqual(activated["lifecycle_state"], Pipeline.State.ACTIVE)
        self.assertEqual(activated["available_transitions"], ["edit", "pause"])
        self.assertTrue(runnable_pipelines().filter(id=pipeline.id).exists())

    def test_pause_resume_preserves_cursor_and_runs(self) -> None:
        self.login_user(self.actor)
        pipeline = self.create_pipeline()
        pipeline.input_cursor_message_id = 123
        pipeline.save(update_fields=["input_cursor_message_id"])
        run_count = PipelineRun.objects.filter(pipeline=pipeline).count()

        paused = self.assert_json_success(
            self.client_patch(
                f"{self.PIPELINES_URL}/{pipeline.id}",
                self.json_data(lifecycle_state=Pipeline.State.PAUSED),
            )
        )["pipeline"]
        pipeline.refresh_from_db()
        self.assertEqual(paused["available_transitions"], ["edit", "resume"])
        self.assertEqual(pipeline.input_cursor_message_id, 123)
        self.assertEqual(PipelineRun.objects.filter(pipeline=pipeline).count(), run_count)
        self.assertFalse(runnable_pipelines().filter(id=pipeline.id).exists())

        resumed = self.assert_json_success(
            self.client_patch(
                f"{self.PIPELINES_URL}/{pipeline.id}",
                self.json_data(lifecycle_state=Pipeline.State.ACTIVE),
            )
        )["pipeline"]
        pipeline.refresh_from_db()
        self.assertEqual(resumed["available_transitions"], ["edit", "pause"])
        self.assertEqual(pipeline.input_cursor_message_id, 123)
        self.assertEqual(PipelineRun.objects.filter(pipeline=pipeline).count(), run_count)

    def test_invalid_lifecycle_transitions_are_rejected(self) -> None:
        self.login_user(self.actor)
        draft = self.create_pipeline(lifecycle_state=Pipeline.State.DRAFT)
        self.assert_json_error(
            self.client_patch(
                f"{self.PIPELINES_URL}/{draft.id}",
                self.json_data(lifecycle_state=Pipeline.State.PAUSED),
            ),
            "Invalid Pipeline lifecycle transition.",
        )
        self.assert_json_error(
            self.client_post(
                self.PIPELINES_URL,
                self.pipeline_payload(lifecycle_state=Pipeline.State.PAUSED),
            ),
            "New Pipelines must be active or draft.",
        )

    def test_activation_reauthorizes_output_access(self) -> None:
        self.login_user(self.actor)
        private_output = self.make_stream(
            "Private lifecycle output", realm=self.actor.realm, invite_only=True
        )
        self.subscribe(self.actor, private_output.name)
        draft = self.create_pipeline(
            lifecycle_state=Pipeline.State.DRAFT,
            output_destination_name=private_output.name,
        )
        self.unsubscribe(self.actor, private_output.name)
        self.assert_json_error(
            self.client_patch(
                f"{self.PIPELINES_URL}/{draft.id}",
                self.json_data(lifecycle_state=Pipeline.State.ACTIVE),
            ),
            f"Not authorized to send to channel '{private_output.name}'",
        )
        draft.refresh_from_db()
        self.assertEqual(draft.state, Pipeline.State.DRAFT)

    def test_admin_activation_uses_creator_as_execution_identity(self) -> None:
        administrator = self.example_user("iago")
        private_output = self.make_stream(
            "Admin-visible private output", realm=self.actor.realm, invite_only=True
        )
        self.subscribe(self.actor, private_output.name)
        self.subscribe(administrator, private_output.name)
        self.login_user(self.actor)
        draft = self.create_pipeline(
            lifecycle_state=Pipeline.State.DRAFT,
            output_destination_name=private_output.name,
        )
        self.unsubscribe(self.actor, private_output.name)

        self.login_user(administrator)
        self.assert_json_error(
            self.client_patch(
                f"{self.PIPELINES_URL}/{draft.id}",
                self.json_data(lifecycle_state=Pipeline.State.ACTIVE),
            ),
            f"Not authorized to send to channel '{private_output.name}'",
        )
        draft.refresh_from_db()
        self.assertEqual(draft.state, Pipeline.State.DRAFT)

    def test_paused_executor_rejection_has_no_side_effects(self) -> None:
        self.login_user(self.actor)
        pipeline = self.create_pipeline()
        pipeline.state = Pipeline.State.PAUSED
        pipeline.input_cursor_message_id = 42
        pipeline.save(update_fields=["state", "input_cursor_message_id"])
        with self.assertRaisesRegex(JsonableError, "This Pipeline is not active"):
            execute_pipeline(
                pipeline_id=pipeline.id,
                request_key="paused:1",
                summarize=lambda _pipeline, _messages: "Should not run",
            )
        pipeline.refresh_from_db()
        self.assertEqual(pipeline.input_cursor_message_id, 42)
        self.assertFalse(PipelineRun.objects.filter(pipeline=pipeline).exists())

    def test_run_lock_first_completes_then_pause_blocks_future_runs(self) -> None:
        self.login_user(self.actor)
        pipeline = self.create_pipeline()
        first = execute_pipeline(
            pipeline_id=pipeline.id,
            request_key="race:run-first",
            summarize=lambda _pipeline, _messages: "Completed before pause",
        )
        self.assertEqual(first.status, PipelineRun.Status.SUCCEEDED)
        self.assert_json_success(
            self.client_patch(
                f"{self.PIPELINES_URL}/{pipeline.id}",
                self.json_data(lifecycle_state=Pipeline.State.PAUSED),
            )
        )
        pipeline.refresh_from_db()
        cursor_after_completed_run = pipeline.input_cursor_message_id
        with self.assertRaisesRegex(JsonableError, "This Pipeline is not active"):
            execute_pipeline(
                pipeline_id=pipeline.id,
                request_key="race:pause-next",
                summarize=lambda _pipeline, _messages: "Must not publish",
            )
        pipeline.refresh_from_db()
        self.assertEqual(pipeline.input_cursor_message_id, cursor_after_completed_run)
        self.assertEqual(PipelineRun.objects.filter(pipeline=pipeline).count(), 1)

    def test_topic_availability_is_orthogonal_to_paused_state(self) -> None:
        self.login_user(self.actor)
        pipeline = self.create_pipeline()
        pipeline.state = Pipeline.State.PAUSED
        pipeline.save(update_fields=["state"])
        moved_stream = self.make_stream("Moved pipeline input", realm=self.actor.realm)
        self.subscribe(self.actor, moved_stream.name)
        self.assertEqual(
            do_update_pipeline_inputs_for_topic_move(
                source_stream=self.source_stream,
                source_topic="Release activity",
                target_stream=moved_stream,
                target_topic="Moved release activity",
            ),
            1,
        )
        pipeline.refresh_from_db()
        self.assertEqual(pipeline.input_destination, moved_stream)
        self.assertEqual(pipeline.input_topic, "Moved release activity")
        self.assertEqual(pipeline.state, Pipeline.State.PAUSED)

        inaccessible_stream = self.make_stream(
            "Inaccessible moved input", realm=self.actor.realm, invite_only=True
        )
        self.assertEqual(
            do_update_pipeline_inputs_for_topic_move(
                source_stream=moved_stream,
                source_topic="Moved release activity",
                target_stream=inaccessible_stream,
                target_topic="Protected moved activity",
            ),
            1,
        )
        pipeline.refresh_from_db()
        self.assertEqual(pipeline.state, Pipeline.State.PAUSED)
        self.assertEqual(pipeline.input_availability, Pipeline.InputAvailability.TOPIC_UNAVAILABLE)
        listed = self.assert_json_success(self.client_get(self.PIPELINES_URL))["pipelines"][0]
        self.assertEqual(listed["status"], "needs_attention")
        self.assertEqual(listed["lifecycle_state"], Pipeline.State.PAUSED)
        self.assertEqual(listed["available_transitions"], ["edit"])

        self.subscribe(self.actor, inaccessible_stream.name)
        self.assertEqual(do_restore_stream_pipeline_inputs(stream=inaccessible_stream), 1)
        pipeline.refresh_from_db()
        self.assertEqual(pipeline.state, Pipeline.State.PAUSED)
        self.assertEqual(pipeline.input_availability, Pipeline.InputAvailability.AVAILABLE)

    def test_create_and_list_topic_first_pipeline(self) -> None:
        self.login_user(self.actor)
        connector = self.create_connector()
        created = self.assert_json_success(
            self.client_post(self.PIPELINES_URL, self.pipeline_payload())
        )["pipeline"]

        pipeline = Pipeline.objects.get(id=created["id"])
        self.assertEqual(pipeline.input_destination, self.source_stream)
        self.assertEqual(pipeline.input_topic, "Release activity")
        self.assertEqual(created["input_destination"], self.source_stream.name)
        self.assertEqual(created["input_topic"], "Release activity")
        self.assertEqual(created["data_sources"][0]["id"], connector.id)
        self.assertEqual(created["source_warnings"], [])
        self.assertEqual(created["input_availability"], Pipeline.InputAvailability.AVAILABLE)
        self.assertEqual(created["run_health"], Pipeline.RunHealth.NOT_RUN)

        response = self.assert_json_success(self.client_get(self.PIPELINES_URL))
        self.assertEqual([item["id"] for item in response["pipelines"]], [pipeline.id])
        topic = next(
            item for item in response["topics"] if item["input_topic"] == "Release activity"
        )
        self.assertEqual(topic["data_sources"][0]["id"], connector.id)

    def test_ordinary_topic_multiple_pipelines_and_same_topic_output(self) -> None:
        self.login_user(self.actor)
        self.send_stream_message(self.actor, self.source_stream.name, topic_name="Human discussion")
        first = self.create_pipeline(
            input_topic="Human discussion",
            output_destination_name=self.source_stream.name,
            output_topic="human DISCUSSION",
        )
        second = self.create_pipeline(input_topic="Human discussion", name="Second brief")
        self.assertNotEqual(first.id, second.id)
        self.assertFalse(
            Connector.objects.filter(
                destination=self.source_stream, topic__iexact="Human discussion"
            ).exists()
        )

        response = self.assert_json_success(self.client_get(self.PIPELINES_URL))
        ordinary = next(
            item for item in response["topics"] if item["input_topic"] == "Human discussion"
        )
        self.assertEqual(ordinary["data_sources"], [])

    def test_source_health_and_lifecycle_are_independent(self) -> None:
        self.login_user(self.actor)
        connector = self.create_connector()
        second = self.create_connector(name="Second source")
        pipeline = self.create_pipeline()

        connector.health_status = Connector.HealthStatus.DEGRADED
        connector.save(update_fields=["health_status", "date_updated"])
        listed = self.assert_json_success(self.client_get(self.PIPELINES_URL))["pipelines"][0]
        self.assertEqual(listed["status"], Pipeline.State.ACTIVE)
        self.assert_length(listed["data_sources"], 2)
        self.assert_length(listed["source_warnings"], 1)

        connector.state = Connector.State.DISABLED
        connector.save(update_fields=["state", "date_updated"])
        second.delete()
        pipeline.refresh_from_db()
        self.assertEqual(pipeline.state, Pipeline.State.ACTIVE)
        self.assertEqual(pipeline.input_availability, Pipeline.InputAvailability.AVAILABLE)

    def test_create_and_update_permissions(self) -> None:
        self.login_user(self.actor)
        pipeline = self.create_pipeline()

        PipelineCreatorAssignment.objects.filter(user=self.actor).delete()
        self.assert_json_error(
            self.client_post(self.PIPELINES_URL, self.pipeline_payload(name="Denied")),
            "You do not have permission to create Pipelines.",
        )
        self.login_user(self.other_user)
        response = self.assert_json_success(self.client_get(self.PIPELINES_URL))
        self.assertEqual(response["pipelines"], [])
        self.assertFalse(response["can_create"])
        self.assert_json_error(
            self.client_patch(f"{self.PIPELINES_URL}/{pipeline.id}", self.json_data(name="Stolen")),
            "You do not have permission to update this Pipeline.",
            status_code=403,
        )

    def test_timezone_inherits_and_partial_patch_preserves_weekday(self) -> None:
        self.actor.timezone = "Asia/Tokyo"
        self.actor.save(update_fields=["timezone"])
        self.login_user(self.actor)
        self.send_stream_message(self.actor, self.source_stream.name, topic_name="Release activity")
        values = self.pipeline_payload(cadence="weekly", weekday=4)
        values.pop("timezone")
        created = self.assert_json_success(self.client_post(self.PIPELINES_URL, values))["pipeline"]
        self.assertEqual(created["timezone"], "Asia/Tokyo")
        updated = self.assert_json_success(
            self.client_patch(
                f"{self.PIPELINES_URL}/{created['id']}", self.json_data(name="Friday brief")
            )
        )["pipeline"]
        self.assertEqual(updated["weekday"], Pipeline.Weekday.FRIDAY)

    def test_patch_repairs_topic_and_validates_output_send_access(self) -> None:
        self.login_user(self.actor)
        pipeline = self.create_pipeline()
        repaired_topic = "Customer feedback"
        self.send_stream_message(self.actor, self.source_stream.name, topic_name=repaired_topic)
        updated = self.assert_json_success(
            self.client_patch(
                f"{self.PIPELINES_URL}/{pipeline.id}",
                self.json_data(input_topic=repaired_topic, cadence="weekly", weekday=2),
            )
        )["pipeline"]
        pipeline.refresh_from_db()
        self.assertEqual(updated["input_topic"], repaired_topic)
        self.assertEqual(updated["weekday"], Pipeline.Weekday.WEDNESDAY)
        self.assertIsNone(pipeline.input_cursor_message_id)

        private_output = self.make_stream(
            "Private output", realm=self.actor.realm, invite_only=True
        )
        self.assert_json_error(
            self.client_patch(
                f"{self.PIPELINES_URL}/{pipeline.id}",
                self.json_data(output_destination_name=private_output.name),
            ),
            f"Invalid channel name '{private_output.name}'",
        )

    def test_schedule_validation(self) -> None:
        self.login_user(self.actor)
        for overrides, error in [
            ({"cadence": "hourly"}, "Invalid Pipeline schedule."),
            ({"timezone": "Mars/Olympus_Mons"}, "Invalid IANA timezone."),
            ({"local_time": "09:00:30"}, "Pipeline schedules must use whole minutes."),
            ({"cadence": "weekly"}, "Choose a weekday for a weekly Pipeline."),
        ]:
            self.assert_json_error(
                self.client_post(self.PIPELINES_URL, self.pipeline_payload(**overrides)), error
            )

    def test_same_topic_execution_excludes_authored_output_and_replays_idempotently(self) -> None:
        self.login_user(self.actor)
        pipeline = self.create_pipeline(
            input_topic="Release activity",
            output_destination_name=self.source_stream.name,
            output_topic="Release activity",
        )
        topic_messages = get_topic_messages(self.actor, self.source_stream, "Release activity")
        pipeline.input_cursor_message_id = topic_messages[-1].id
        pipeline.save(update_fields=["input_cursor_message_id"])
        source_id = self.send_stream_message(
            self.actor,
            self.source_stream.name,
            topic_name="Release activity",
            content="Version 4 shipped",
        )
        seen: list[list[int]] = []

        def summarize(_pipeline: Pipeline, messages: list[Message]) -> str:
            seen.append([message.id for message in messages])
            return "Pipeline result"

        first = execute_pipeline(
            pipeline_id=pipeline.id, request_key="scheduled:1", summarize=summarize
        )
        replay = execute_pipeline(
            pipeline_id=pipeline.id, request_key="scheduled:1", summarize=summarize
        )
        second = execute_pipeline(
            pipeline_id=pipeline.id, request_key="scheduled:2", summarize=summarize
        )
        self.assertEqual(first.id, replay.id)
        self.assertEqual(seen, [[source_id]])
        self.assertIsNotNone(first.output_message_id)
        self.assertIsNone(second.output_message_id)
        self.assertEqual(PipelineAuthoredMessage.objects.filter(pipeline=pipeline).count(), 1)

    def test_publish_and_provenance_are_atomic_and_failed_run_can_retry(self) -> None:
        self.login_user(self.actor)
        pipeline = self.create_pipeline()
        topic_messages = get_topic_messages(self.actor, self.source_stream, "Release activity")
        pipeline.input_cursor_message_id = topic_messages[-1].id
        pipeline.save(update_fields=["input_cursor_message_id"])
        self.send_stream_message(
            self.actor, self.source_stream.name, topic_name="Release activity", content="Input"
        )
        with patch.object(PipelineAuthoredMessage.objects, "create", side_effect=RuntimeError):
            failed = execute_pipeline(
                pipeline_id=pipeline.id,
                request_key="retryable:1",
                summarize=lambda _pipeline, _messages: "Atomic output",
            )
        self.assertEqual(failed.status, PipelineRun.Status.FAILED)
        self.assertFalse(
            Message.objects.filter(realm=self.actor.realm, content="Atomic output").exists()
        )

        succeeded = execute_pipeline(
            pipeline_id=pipeline.id,
            request_key="retryable:1",
            summarize=lambda _pipeline, _messages: "Atomic output",
        )
        self.assertEqual(succeeded.status, PipelineRun.Status.SUCCEEDED)
        self.assertEqual(
            Message.objects.filter(realm=self.actor.realm, content="Atomic output").count(), 1
        )

    def test_complete_topic_rename_follows_pipeline_but_partial_move_does_not(self) -> None:
        self.login_user(self.actor)
        pipeline = self.create_pipeline()
        pipeline.input_cursor_message_id = 17
        pipeline.state = Pipeline.State.PAUSED
        pipeline.save(update_fields=["input_cursor_message_id", "state"])
        first_id = self.send_stream_message(
            self.actor, self.source_stream.name, topic_name="Release activity"
        )
        self.send_stream_message(self.actor, self.source_stream.name, topic_name="Release activity")
        self.assert_json_success(
            self.client_patch(
                f"/json/messages/{first_id}",
                {"topic": "Renamed activity", "propagate_mode": "change_all"},
            )
        )
        pipeline.refresh_from_db()
        self.assertEqual(pipeline.input_topic, "Renamed activity")
        self.assertEqual(pipeline.input_cursor_message_id, 17)
        self.assertEqual(pipeline.input_availability, Pipeline.InputAvailability.AVAILABLE)
        self.assertEqual(pipeline.state, Pipeline.State.PAUSED)

        partial_pipeline = self.create_pipeline(
            input_topic="Partial source", name="Partial pipeline"
        )
        partial_id = self.send_stream_message(
            self.actor, self.source_stream.name, topic_name="Partial source"
        )
        self.send_stream_message(self.actor, self.source_stream.name, topic_name="Partial source")
        self.assert_json_success(
            self.client_patch(
                f"/json/messages/{partial_id}",
                {"topic": "Partial target", "propagate_mode": "change_one"},
            )
        )
        partial_pipeline.refresh_from_db()
        self.assertEqual(partial_pipeline.input_topic, "Partial source")

    def test_topic_delete_and_stream_archive_expose_repair_state(self) -> None:
        self.login_user(self.actor)
        pipeline = self.create_pipeline()
        self.send_stream_message(self.actor, self.source_stream.name, topic_name="Release activity")
        administrator = self.example_user("iago")
        self.login_user(administrator)
        self.assert_json_success(
            self.client_post(
                f"/json/streams/{self.source_stream.id}/delete_topic",
                {"topic_name": "Release activity"},
            )
        )
        pipeline.refresh_from_db()
        self.assertEqual(pipeline.input_availability, Pipeline.InputAvailability.TOPIC_UNAVAILABLE)

        self.login_user(self.actor)
        response = self.assert_json_success(self.client_get(self.PIPELINES_URL))
        self.assertEqual(response["pipelines"][0]["status"], "needs_attention")
        unavailable_topic = next(
            topic
            for topic in response["topics"]
            if topic["input_destination"] == self.source_stream.name
            and topic["input_topic"] == "Release activity"
        )
        self.assertEqual(
            unavailable_topic["input_availability"],
            Pipeline.InputAvailability.TOPIC_UNAVAILABLE,
        )

        self.send_stream_message(
            self.actor, self.source_stream.name, topic_name="Replacement topic"
        )
        repaired = self.assert_json_success(
            self.client_patch(
                f"{self.PIPELINES_URL}/{pipeline.id}",
                self.json_data(input_topic="Replacement topic"),
            )
        )["pipeline"]
        self.assertEqual(repaired["input_availability"], Pipeline.InputAvailability.AVAILABLE)

        self.login_user(administrator)
        self.assert_json_success(self.client_delete(f"/json/streams/{self.source_stream.id}"))
        pipeline.refresh_from_db()
        self.assertEqual(pipeline.input_availability, Pipeline.InputAvailability.TOPIC_UNAVAILABLE)

    def test_protected_history_topics_and_execution_window_do_not_leak(self) -> None:
        administrator = self.example_user("iago")
        private_stream = self.make_stream(
            "Protected pipeline input", realm=self.actor.realm, invite_only=True
        )
        self.subscribe(administrator, private_stream.name)
        hidden_id = self.send_stream_message(
            administrator, private_stream.name, topic_name="Protected activity", content="hidden"
        )
        self.send_stream_message(
            administrator, private_stream.name, topic_name="Hidden topic name", content="hidden"
        )
        self.subscribe(self.actor, private_stream.name)
        visible_id = self.send_stream_message(
            self.actor, private_stream.name, topic_name="Protected activity", content="visible"
        )
        self.login_user(self.actor)
        self.assert_json_success(
            self.client_post(
                self.CONNECTORS_URL,
                self.json_data(
                    provider_key="github",
                    name="Protected source",
                    destination_name=private_stream.name,
                    topic="Protected activity",
                    event_options=[],
                ),
            )
        )
        created = self.assert_json_success(
            self.client_post(
                self.PIPELINES_URL,
                self.pipeline_payload(
                    input_destination_name=private_stream.name,
                    input_topic="Protected activity",
                ),
            )
        )["pipeline"]
        topics = self.assert_json_success(self.client_get(self.PIPELINES_URL))["topics"]
        self.assertNotIn("Hidden topic name", [topic["input_topic"] for topic in topics])

        seen: list[int] = []

        def summarize(_pipeline: Pipeline, messages: list[Message]) -> str:
            seen.extend(message.id for message in messages)
            return "Safe summary"

        execute_pipeline(pipeline_id=created["id"], request_key="protected:1", summarize=summarize)
        self.assertNotIn(hidden_id, seen)
        self.assertIn(visible_id, seen)

        self.assert_json_error(
            self.client_post(
                self.PIPELINES_URL,
                self.pipeline_payload(
                    input_destination_name=private_stream.name,
                    input_topic="Hidden topic name",
                    name="Leaky pipeline",
                ),
            ),
            "Choose an accessible input Topic.",
        )
