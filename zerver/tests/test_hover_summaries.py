import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from unittest.mock import patch
from uuid import uuid4

import orjson
import time_machine
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.utils.timezone import now as timezone_now
from typing_extensions import override

from hover.actions_modules import (
    do_disable_module,
    ensure_prebuilt_module_catalog,
    installation_data,
)
from hover.actions_spaces import do_create_space, do_launch_space
from hover.actions_summaries import SummaryInputSpec, do_create_summary, do_update_summary
from hover.actions_summary_executions import (
    MAX_SERIALIZED_EVIDENCE_CHARACTERS,
    MAX_SNAPSHOT_MESSAGES,
    SummaryExecutionConflictError,
    _balanced_selection,
    _hash,
    do_accept_summary_result,
    do_prepare_summary_execution,
    do_publish_summary_execution,
    execution_data,
    prepare_due_summary_executions,
    retry_stale_scheduled_dispatch,
)
from hover.lib import add_hover_metadata
from hover.lib_spaces import get_space_data, space_projection_queryset
from hover.models import (
    ConnectedAccount,
    EvidenceLink,
    GeneratedInputSnapshot,
    GeneratedItem,
    ModuleInstallation,
    ModuleInstallationTrigger,
    ModuleVersion,
    Source,
    SpaceAttachment,
    SpaceMembership,
    SummaryExecution,
    SummaryExecutionMessage,
)
from zerver.actions.channel_folders import check_add_channel_folder
from zerver.actions.streams import bulk_remove_subscriptions
from zerver.lib.exceptions import JsonableError
from zerver.lib.streams import access_stream_by_id
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.user_groups import get_system_user_group_by_name
from zerver.models import Message, Subscription
from zerver.models.groups import SystemGroups


class HoverSummariesTest(ZulipTestCase):
    @override
    def setUp(self) -> None:
        super().setUp()
        self.creator = self.example_user("hamlet")
        self.other_member = self.example_user("othello")
        self.realm = self.creator.realm
        self.realm.can_create_spaces_group = get_system_user_group_by_name(
            SystemGroups.MEMBERS, self.realm.id
        )
        self.realm.save(update_fields=["can_create_spaces_group"])
        category = check_add_channel_folder(
            self.realm, "Programs", "", acting_user=self.example_user("iago")
        )
        self.space = do_create_space(
            self.creator,
            name="Summary authorization",
            description="",
            category=category,
        )
        SpaceMembership.objects.create(
            realm=self.realm,
            space=self.space,
            user=self.other_member,
            role=SpaceMembership.Role.SUBSCRIBER,
            added_by=self.creator,
        )
        account = ConnectedAccount.objects.create(
            realm=self.realm,
            provider_key="github",
            provider_name="GitHub",
            external_account_id=uuid4(),
            display_name="Repositories",
            created_by=self.creator,
            owner=self.creator,
            approval_state=ConnectedAccount.ApprovalState.APPROVED,
        )
        source = Source.objects.create(
            realm=self.realm,
            account=account,
            adapter_key="clawer_sync",
            provider_key="github",
            provider_name="GitHub",
            source_type="repository",
            external_ref=f"src_{'a' * 32}",
            display_name="hover",
        )
        SpaceAttachment.objects.create(
            realm=self.realm,
            space=self.space,
            source=source,
            state=SpaceAttachment.State.ACTIVE,
            history_window=SpaceAttachment.HistoryWindow.LAST_30_DAYS,
            history_timezone="UTC",
            history_start_at=timezone_now() - timedelta(days=30),
            destination_topic="GitHub activity",
            attached_by=self.creator,
        )
        self.space, _created = do_launch_space(self.space, acting_user=self.creator)
        assert self.space.stream is not None
        self.parent_stream = self.space.stream
        ensure_prebuilt_module_catalog(self.realm)
        self.version = ModuleVersion.objects.get(
            definition__realm=self.realm,
            definition__stable_key="conversation_digest",
        )
        self.citation_id = self.send_stream_message(
            self.creator,
            self.parent_stream.name,
            topic_name="Launch plan",
            content="Ship the native topic list.",
        )

    def create_summary(self) -> ModuleInstallation:
        return do_create_summary(
            acting_user=self.creator,
            space=self.space,
            version_id=self.version.id,
            label="Daily launch brief",
            inputs=[
                SummaryInputSpec(
                    topic_name="Launch plan",
                    kind="regular",
                    attachment_id=None,
                )
            ],
            interval_seconds=24 * 60 * 60,
            timezone="Asia/Kuala_Lumpur",
            member_ids=[self.creator.id],
        )

    def successful_result(
        self, dispatch: Any, *, evidence_tokens: list[str] | None = None
    ) -> dict[str, object]:
        assert dispatch.operation is not None
        result: dict[str, object] = {
            "schema_version": "1.0",
            "status": "succeeded",
            "snapshot_hash": dispatch.operation["snapshot_hash"],
            "digest": {
                "title": "Launch ready",
                "main_thread": "The native topic list is ready to ship.",
                "what_changed": ["The implementation moved to ready."],
                "confirmed_facts": ["The topic list is native."],
                "unresolved_points": [],
                "why_it_matters": "The team can proceed with launch.",
            },
            "evidence_tokens": evidence_tokens or ["evidence_0001"],
            "failure_code": "",
        }
        result["result_hash"] = hashlib.sha256(
            json.dumps(result, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        return result

    def test_anonymous_execution_callback_uses_scoped_bearer(self) -> None:
        installation = self.create_summary()
        window_end = timezone_now()
        dispatch = do_prepare_summary_execution(
            installation=installation,
            kind=SummaryExecution.Kind.MANUAL,
            window_start=window_end - timedelta(hours=1),
            window_end=window_end,
            requester=self.creator,
            manual_request_id="anonymous-callback",
        )
        assert dispatch.callback_bearer is not None

        response = self.client_post(
            f"/json/hover/v1/summary-executions/{dispatch.execution.id}/callback",
            orjson.dumps(self.successful_result(dispatch)),
            content_type="application/json",
            headers={"Authorization": f"Bearer {dispatch.callback_bearer}"},
        )

        self.assert_json_success(response)
        dispatch.execution.refresh_from_db()
        self.assertEqual(dispatch.execution.status, SummaryExecution.Status.SUCCEEDED)

    def test_cross_repository_execution_fixture_hashes(self) -> None:
        fixture = json.loads(
            (Path(__file__).parent / "fixtures" / "hover" / "summary_execution_v1.json").read_text()
        )
        self.assertEqual(_hash(fixture["operation"]), fixture["request_hash"])
        self.assertEqual(
            _hash({key: value for key, value in fixture["result"].items() if key != "result_hash"}),
            fixture["result"]["result_hash"],
        )

    def test_snapshot_selection_is_balanced_deterministic_and_bounded(self) -> None:
        started_at = datetime(2026, 8, 1, tzinfo=timezone.utc)
        candidates = {
            input_position: [
                Message(
                    id=input_position * 1_000 + offset,
                    date_sent=started_at + timedelta(seconds=offset * 2 + input_position),
                    content=f"Input {input_position}, message {offset}",
                )
                for offset in range(80)
            ]
            for input_position in range(2)
        }
        selected = _balanced_selection(candidates)

        self.assert_length(selected, MAX_SNAPSHOT_MESSAGES)
        self.assertEqual({item.input_position for item in selected}, {0, 1})
        self.assertEqual(
            [(item.message.date_sent, item.message.id) for item in selected],
            sorted((item.message.date_sent, item.message.id) for item in selected),
        )

        oversized = {
            0: [Message(id=1, date_sent=started_at, content="a" * 40_000)],
            1: [Message(id=2, date_sent=started_at, content="b" * 40_000)],
        }
        content_bounded = _balanced_selection(oversized)
        self.assert_length(content_bounded, 1)
        self.assertLessEqual(
            len(content_bounded[0].message.content), MAX_SERIALIZED_EVIDENCE_CHARACTERS
        )

    def test_input_limits_and_manual_permissions_fail_closed(self) -> None:
        with self.assertRaisesRegex(JsonableError, "between 1 and 20"):
            do_create_summary(
                acting_user=self.creator,
                space=self.space,
                version_id=self.version.id,
                label="Too many inputs",
                inputs=[
                    SummaryInputSpec(
                        topic_name=f"Topic {index}", kind="regular", attachment_id=None
                    )
                    for index in range(21)
                ],
                interval_seconds=3_600,
                timezone="UTC",
                member_ids=[self.creator.id],
            )

        installation = self.create_summary()
        window_end = timezone_now()
        with self.assertRaisesRegex(JsonableError, "permission"):
            do_prepare_summary_execution(
                installation=installation,
                kind=SummaryExecution.Kind.MANUAL,
                window_start=window_end - timedelta(hours=1),
                window_end=window_end,
                requester=self.other_member,
                manual_request_id="unauthorized-preview",
            )

    def test_create_uses_an_independent_private_stream_and_sanitized_projection(self) -> None:
        installation = self.create_summary()
        trigger = installation.triggers.get()
        self.assertEqual(trigger.anchor_at, installation.date_created)
        self.assertEqual(trigger.interval_seconds, 24 * 60 * 60)
        self.assertEqual(
            trigger.next_due_at,
            installation.date_created + timedelta(days=1),
        )
        assert installation.summary_stream is not None
        summary_stream = installation.summary_stream
        self.assertTrue(summary_stream.invite_only)
        self.assertFalse(summary_stream.history_public_to_subscribers)
        self.assertTrue(
            Subscription.objects.filter(
                user_profile=self.creator,
                recipient=summary_stream.recipient,
                active=True,
            ).exists()
        )
        self.assertFalse(
            Subscription.objects.filter(
                user_profile=self.other_member,
                recipient=summary_stream.recipient,
                active=True,
            ).exists()
        )
        access_stream_by_id(self.creator, summary_stream.id)
        with self.assertRaises(JsonableError):
            access_stream_by_id(self.other_member, summary_stream.id)

        projected = space_projection_queryset().get(id=self.space.id)
        creator_data = get_space_data(projected, viewer=self.creator)
        other_data = get_space_data(projected, viewer=self.other_member)
        self.assertEqual(creator_data["topic_descriptors"][-1]["kind"], "summary")
        self.assertNotIn("Daily launch brief", orjson.dumps(other_data).decode())

    def test_manual_execution_freezes_boundary_and_publishes_idempotently(self) -> None:
        installation = self.create_summary()
        window_end = timezone_now()
        dispatch = do_prepare_summary_execution(
            installation=installation,
            kind=SummaryExecution.Kind.MANUAL,
            window_start=window_end - timedelta(hours=1),
            window_end=window_end,
            requester=self.creator,
            manual_request_id="manual-preview-1",
        )
        assert dispatch.operation is not None
        assert dispatch.callback_bearer is not None
        operation_json = orjson.dumps(dispatch.operation).decode()
        self.assertNotIn("message_id", operation_json)
        self.assertNotIn("sender_id", operation_json)
        self.assertNotIn(self.creator.email, operation_json)
        evidence = dispatch.operation["evidence"]
        assert isinstance(evidence, list)
        first_evidence = evidence[0]
        assert isinstance(first_evidence, dict)
        self.assertEqual(first_evidence["sender_label"], "Participant 1")

        snapshot = SummaryExecutionMessage.objects.get(execution=dispatch.execution)
        self.assertEqual(snapshot.frozen_content, "Ship the native topic list.")
        Message.objects.filter(id=self.citation_id).update(content="Edited after generation")
        snapshot.refresh_from_db()
        self.assertEqual(snapshot.frozen_content, "Ship the native topic list.")

        do_update_summary(
            acting_user=self.creator,
            installation=installation,
            label="Daily launch brief",
            inputs=[
                SummaryInputSpec(
                    topic_name="Launch plan",
                    kind="regular",
                    attachment_id=None,
                )
            ],
            interval_seconds=6 * 60 * 60,
            timezone="UTC",
            member_ids=[self.creator.id],
        )
        dispatch.execution.refresh_from_db()
        self.assertTrue(execution_data(dispatch.execution)["uses_previous_settings"])

        payload = self.successful_result(dispatch)
        accepted = do_accept_summary_result(
            execution_id=str(dispatch.execution.id),
            callback_bearer=dispatch.callback_bearer,
            payload=payload,
        )
        replayed = do_accept_summary_result(
            execution_id=str(dispatch.execution.id),
            callback_bearer=dispatch.callback_bearer,
            payload=payload,
        )
        self.assertEqual(accepted.id, replayed.id)

        published = do_publish_summary_execution(execution=accepted, acting_user=self.creator)
        republished = do_publish_summary_execution(execution=published, acting_user=self.creator)
        self.assertEqual(published.published_item_id, republished.published_item_id)
        assert published.published_item is not None
        self.assertEqual(GeneratedItem.objects.filter(installation=installation).count(), 1)
        self.assertEqual(
            EvidenceLink.objects.filter(generated_item=published.published_item).count(),
            1,
        )

    def test_callback_conflict_and_publication_failure_are_atomic(self) -> None:
        installation = self.create_summary()
        window_end = timezone_now()
        dispatch = do_prepare_summary_execution(
            installation=installation,
            kind=SummaryExecution.Kind.MANUAL,
            window_start=window_end - timedelta(hours=1),
            window_end=window_end,
            requester=self.creator,
            manual_request_id="atomic-preview",
        )
        assert dispatch.callback_bearer is not None
        payload = self.successful_result(dispatch)
        accepted = do_accept_summary_result(
            execution_id=str(dispatch.execution.id),
            callback_bearer=dispatch.callback_bearer,
            payload=payload,
        )

        conflicting = self.successful_result(dispatch)
        digest = conflicting["digest"]
        assert isinstance(digest, dict)
        digest["title"] = "Conflicting replay"
        conflicting["result_hash"] = _hash(
            {key: value for key, value in conflicting.items() if key != "result_hash"}
        )
        with self.assertRaises(SummaryExecutionConflictError):
            do_accept_summary_result(
                execution_id=str(dispatch.execution.id),
                callback_bearer=dispatch.callback_bearer,
                payload=conflicting,
            )

        assert installation.summary_stream is not None
        before_messages = Message.objects.filter(
            realm=self.realm, recipient=installation.summary_stream.recipient
        ).count()
        with (
            patch(
                "hover.actions_summary_executions.GeneratedItem.objects.create",
                side_effect=IntegrityError("injected metadata failure"),
            ),
            self.assertRaises(IntegrityError),
        ):
            do_publish_summary_execution(execution=accepted, acting_user=self.creator)
        accepted.refresh_from_db()
        self.assertEqual(accepted.status, SummaryExecution.Status.SUCCEEDED)
        self.assertEqual(
            Message.objects.filter(
                realm=self.realm,
                recipient=installation.summary_stream.recipient,
            ).count(),
            before_messages,
        )
        self.assertFalse(GeneratedItem.objects.filter(installation=installation).exists())

    def test_unknown_citation_fails_closed_without_result_prose(self) -> None:
        installation = self.create_summary()
        window_end = timezone_now()
        dispatch = do_prepare_summary_execution(
            installation=installation,
            kind=SummaryExecution.Kind.MANUAL,
            window_start=window_end - timedelta(hours=1),
            window_end=window_end,
            requester=self.creator,
            manual_request_id="manual-preview-rogue-citation",
        )
        assert dispatch.callback_bearer is not None
        accepted = do_accept_summary_result(
            execution_id=str(dispatch.execution.id),
            callback_bearer=dispatch.callback_bearer,
            payload=self.successful_result(dispatch, evidence_tokens=["evidence_9999"]),
        )
        self.assertEqual(accepted.status, SummaryExecution.Status.FAILED)
        self.assertEqual(accepted.failure_code, "citation_boundary_violation")
        self.assertEqual(accepted.result, {})

    def test_manual_no_change_remains_private_and_cannot_publish(self) -> None:
        installation = self.create_summary()
        window_end = timezone_now() - timedelta(days=30)
        dispatch = do_prepare_summary_execution(
            installation=installation,
            kind=SummaryExecution.Kind.MANUAL,
            window_start=window_end - timedelta(days=60),
            window_end=window_end,
            requester=self.creator,
            manual_request_id="manual-no-change",
        )
        self.assertEqual(dispatch.execution.status, SummaryExecution.Status.NO_CHANGE)
        self.assertIsNone(dispatch.operation)
        self.assertFalse(execution_data(dispatch.execution)["can_publish"])
        with self.assertRaisesRegex(JsonableError, "no publishable result"):
            do_publish_summary_execution(execution=dispatch.execution, acting_user=self.creator)

    def test_scheduler_backfills_contiguously_and_publishes_no_change(self) -> None:
        installation = self.create_summary()
        trigger = ModuleInstallationTrigger.objects.get(installation=installation)
        at = timezone_now()
        first_due = at - timedelta(hours=2)
        trigger.anchor_at = first_due - timedelta(hours=1)
        trigger.interval_seconds = 60 * 60
        trigger.next_due_at = first_due
        trigger.save(update_fields=["anchor_at", "interval_seconds", "next_due_at"])

        first = prepare_due_summary_executions(at=at)
        self.assert_length(first, 1)
        self.assertEqual(first[0].execution.window_start, first_due - timedelta(hours=1))
        self.assertEqual(first[0].execution.window_end, first_due)
        self.assertEqual(first[0].execution.status, SummaryExecution.Status.NO_CHANGE)
        do_publish_summary_execution(execution=first[0].execution)
        trigger.refresh_from_db()
        self.assertIsNone(trigger.lease_expires_at)
        self.assertEqual(trigger.next_due_at, first_due + timedelta(hours=1))

        second = prepare_due_summary_executions(at=at)
        self.assert_length(second, 1)
        self.assertEqual(second[0].execution.window_start, first_due)
        self.assertEqual(second[0].execution.window_end, first_due + timedelta(hours=1))
        published = do_publish_summary_execution(execution=second[0].execution)
        assert published.published_item is not None
        self.assertFalse(published.published_item.material_change)
        self.assertFalse(
            EvidenceLink.objects.filter(generated_item=published.published_item).exists()
        )

    def test_scheduler_blocks_parallel_run_then_continues_after_terminal_failure(self) -> None:
        installation = self.create_summary()
        trigger = ModuleInstallationTrigger.objects.get(installation=installation)
        at = timezone_now()
        trigger.anchor_at = at - timedelta(hours=1)
        trigger.interval_seconds = 60 * 60
        trigger.next_due_at = at
        trigger.save(update_fields=["anchor_at", "interval_seconds", "next_due_at"])

        with time_machine.travel(at, tick=False):
            first = prepare_due_summary_executions(at=at)
        self.assert_length(first, 1)
        self.assertEqual(first[0].execution.status, SummaryExecution.Status.DISPATCHED)
        retried = retry_stale_scheduled_dispatch(first[0].execution)
        self.assertEqual(retried.operation, first[0].operation)
        self.assertNotEqual(retried.callback_bearer, first[0].callback_bearer)
        assert first[0].callback_bearer is not None
        with self.assertRaisesRegex(JsonableError, "callback credential"):
            do_accept_summary_result(
                execution_id=str(first[0].execution.id),
                callback_bearer=first[0].callback_bearer,
                payload=self.successful_result(retried),
            )
        trigger.refresh_from_db()
        trigger.lease_expires_at = at - timedelta(seconds=1)
        trigger.save(update_fields=["lease_expires_at"])

        later = at + timedelta(hours=2)
        with time_machine.travel(later, tick=False):
            self.assertEqual(prepare_due_summary_executions(at=later), [])

        assert retried.callback_bearer is not None
        failed: dict[str, object] = {
            "schema_version": "1.0",
            "status": "failed",
            "snapshot_hash": first[0].execution.snapshot_hash,
            "digest": None,
            "evidence_tokens": [],
            "failure_code": "generation_failed",
        }
        failed["result_hash"] = _hash(failed)
        do_accept_summary_result(
            execution_id=str(first[0].execution.id),
            callback_bearer=retried.callback_bearer,
            payload=failed,
        )
        first[0].execution.refresh_from_db()
        failure_data = installation_data(installation)["latest_scheduled_failure"]
        assert isinstance(failure_data, dict)
        self.assertEqual(failure_data["failure_code"], "generation_failed")
        self.assertEqual(failure_data["scheduled_for"], at.isoformat())

        with time_machine.travel(later, tick=False):
            second = prepare_due_summary_executions(at=later)
        self.assert_length(second, 1)
        self.assertEqual(second[0].execution.window_start, at)
        self.assertEqual(second[0].execution.window_end, at + timedelta(hours=1))

    def test_schedule_edit_resets_anchor_and_discards_unqueued_occurrences(self) -> None:
        installation = self.create_summary()
        reset_at = timezone_now() + timedelta(minutes=5)
        with time_machine.travel(reset_at, tick=False):
            do_update_summary(
                acting_user=self.creator,
                installation=installation,
                label="Daily launch brief",
                inputs=[
                    SummaryInputSpec(
                        topic_name="Launch plan",
                        kind="regular",
                        attachment_id=None,
                    )
                ],
                interval_seconds=6 * 60 * 60,
                timezone="UTC",
                member_ids=[self.creator.id],
            )
        trigger = ModuleInstallationTrigger.objects.get(installation=installation)
        self.assertEqual(trigger.anchor_at, reset_at)
        self.assertEqual(trigger.next_due_at, reset_at + timedelta(hours=6))
        self.assertIsNone(trigger.lease_expires_at)

    def test_grouped_evidence_uses_generation_snapshot_and_rejects_rogue_citation(self) -> None:
        installation = self.create_summary()
        assert installation.summary_stream is not None
        summary_message_id = self.send_stream_message(
            self.creator,
            installation.summary_stream.name,
            topic_name=installation.label,
            content="Daily overview",
        )
        generated_item = GeneratedItem.objects.create(
            realm=self.realm,
            message_id=summary_message_id,
            installation=installation,
            output_type=GeneratedItem.OutputType.DIGEST,
            module_key="conversation_digest",
            module_name="Conversation Digest",
            module_version=self.version.version,
            source_summary="From Launch plan",
        )
        GeneratedInputSnapshot.objects.create(
            generated_item=generated_item,
            stream=self.parent_stream,
            topic_name="Launch plan",
            kind="regular",
            position=0,
        )
        citation = Message.objects.get(id=self.citation_id)
        link = EvidenceLink(
            generated_item=generated_item,
            realm=self.realm,
            citation_message=citation,
            position=0,
            provider_key="",
            provider_name="",
            display_name="",
        )
        link.full_clean()
        link.save()

        message_dict: dict[str, Any] = {"id": generated_item.message_id}
        add_hover_metadata([message_dict], realm_id=self.realm.id, user_profile=self.creator)
        self.assertEqual(
            message_dict["hover_generated_item"]["evidence_url"],
            f"/json/hover/spaces/{self.space.id}/generated-items/{generated_item.id}/evidence",
        )

        self.login_user(self.creator)
        payload = self.assert_json_success(
            self.client_post(
                f"/json/hover/spaces/{self.space.id}/generated-items/{generated_item.id}/evidence"
            )
        )
        self.assertEqual(payload["groups"][0]["topic"]["topic_name"], "Launch plan")
        self.assertEqual(payload["groups"][0]["messages"][0]["message_id"], self.citation_id)
        self.assertEqual(payload["forbidden_count"], 0)

        rogue_id = self.send_stream_message(
            self.creator,
            self.parent_stream.name,
            topic_name="Undeclared topic",
            content="Not an input",
        )
        rogue = EvidenceLink(
            generated_item=generated_item,
            realm=self.realm,
            citation_message_id=rogue_id,
            position=1,
            provider_key="",
            provider_name="",
            display_name="",
        )
        with self.assertRaisesRegex(ValidationError, "generation-time input"):
            rogue.full_clean()

        bulk_remove_subscriptions(
            self.realm,
            [self.creator],
            [self.parent_stream],
            acting_user=self.example_user("iago"),
        )
        assert installation.summary_stream is not None
        with self.assertRaises(JsonableError):
            access_stream_by_id(self.creator, installation.summary_stream.id)
        withdrawn = self.client_post(
            f"/json/hover/spaces/{self.space.id}/generated-items/{generated_item.id}/evidence"
        )
        self.assert_json_error(withdrawn, "Invalid message(s)")

    def test_update_and_disable_reconcile_native_authorization(self) -> None:
        installation = self.create_summary()
        assert installation.summary_stream is not None
        updated = do_update_summary(
            acting_user=self.creator,
            installation=installation,
            label="Team launch brief",
            inputs=[
                SummaryInputSpec(
                    topic_name="Launch plan",
                    kind="regular",
                    attachment_id=None,
                )
            ],
            interval_seconds=6 * 60 * 60,
            timezone="UTC",
            member_ids=[self.creator.id, self.other_member.id],
        )
        self.assertEqual(updated.label, "Team launch brief")
        self.assertEqual(updated.policy_revision, 2)
        self.assertTrue(
            Subscription.objects.filter(
                user_profile=self.other_member,
                recipient=installation.summary_stream.recipient,
                active=True,
            ).exists()
        )
        access_stream_by_id(self.other_member, installation.summary_stream.id)

        do_update_summary(
            acting_user=self.creator,
            installation=updated,
            label="Team launch brief",
            inputs=[
                SummaryInputSpec(
                    topic_name="Launch plan",
                    kind="regular",
                    attachment_id=None,
                )
            ],
            interval_seconds=6 * 60 * 60,
            timezone="UTC",
            member_ids=[self.creator.id],
        )
        with self.assertRaises(JsonableError):
            access_stream_by_id(self.other_member, installation.summary_stream.id)

        do_disable_module(updated, acting_user=self.creator)
        with self.assertRaises(JsonableError):
            access_stream_by_id(self.creator, installation.summary_stream.id)
