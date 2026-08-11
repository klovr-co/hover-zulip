from datetime import datetime, timedelta, timezone
from typing import Any, cast
from unittest.mock import patch
from uuid import UUID, uuid4

import orjson
from django.utils import timezone as django_timezone
from typing_extensions import override

from hover.actions_connected_accounts import (
    ConnectedAccountSelectorSpec,
    do_create_connected_account,
    do_set_connected_account_approval_state,
    do_upsert_connected_account_grant,
)
from hover.actions_sources import do_attach_source
from hover.actions_spaces import do_create_space
from hover.clawer_sync import ClawerSource, ClawerSyncError, InMemoryClawerSync
from hover.lib import add_hover_metadata
from hover.models import (
    ConnectedAccount,
    DisputedDetail,
    DisputedEvidenceLink,
    EvidenceLink,
    GeneratedItem,
    PublicationSyncAttempt,
    ReviewRequest,
    ReviewRequestTarget,
    Source,
    SourceParticipantBinding,
    Space,
    SpaceAttachment,
    SpaceMembership,
    SuggestedAction,
)
from hover.publication_contracts import (
    ClawerPublication,
    ClawerPublicationPage,
    DigestPayload,
    ProgressUpdatePayload,
    ResolvedEvidence,
    publication_envelope_hash,
)
from hover.publication_sync import (
    MAX_PUBLICATION_SYNC_BATCH,
    PublicationSyncError,
    sync_space_attachment,
)
from zerver.actions.channel_folders import check_add_channel_folder
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.user_groups import get_system_user_group_by_name
from zerver.models import Message, Subscription, UserMessage
from zerver.models.groups import SystemGroups


class HoverPublicationSyncTest(ZulipTestCase):
    SOURCE_REF = "src_0123456789abcdef0123456789abcdef"

    @override
    def setUp(self) -> None:
        super().setUp()
        self.actor = self.example_user("hamlet")
        self.assistant = self.example_user("default_bot")
        self.settings_override = self.settings(HOVER_ASSISTANT_EMAIL=self.assistant.delivery_email)
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)
        self.realm = self.actor.realm
        self.realm.hover_enabled = True
        self.realm.can_create_spaces_group = get_system_user_group_by_name(
            SystemGroups.MEMBERS, self.realm.id
        )
        self.realm.save(update_fields=["hover_enabled", "can_create_spaces_group"])
        category = check_add_channel_folder(
            self.realm,
            "Programs",
            "",
            acting_user=self.example_user("iago"),
        )
        self.space = do_create_space(
            self.actor,
            name="AIMTO Events",
            description="",
            category=category,
        )
        self.account = do_create_connected_account(
            realm=self.realm,
            provider_key="whatsapp",
            provider_name="WhatsApp",
            external_account_id=UUID("d38c68c4-d70f-44ec-a17e-c7c845f91c03"),
            display_name="AIMTO conversations",
            created_by=self.actor,
            owner=self.actor,
        )
        do_set_connected_account_approval_state(
            self.account,
            ConnectedAccount.ApprovalState.APPROVED,
            acting_user=self.example_user("iago"),
        )
        do_upsert_connected_account_grant(
            self.account,
            self.actor,
            all_selectors=False,
            selector_specs=[
                ConnectedAccountSelectorSpec(
                    selector_type="whatsapp_group",
                    source_ref=self.SOURCE_REF,
                    display_name="AIMTO volunteers",
                )
            ],
            acting_user=self.example_user("iago"),
        )
        self.adapter = InMemoryClawerSync(
            {
                (str(self.realm.uuid), str(self.account.external_account_id)): [
                    ClawerSource(
                        source_ref=self.SOURCE_REF,
                        provider="whatsapp",
                        source_type="group",
                        display_name="AIMTO volunteers",
                    )
                ]
            }
        )
        self.attachment, _created = do_attach_source(
            acting_user=self.actor,
            space=self.space,
            account_id=self.account.id,
            source_ref=self.SOURCE_REF,
            history_window="today",
            history_timezone="UTC",
            custom_start_date=None,
            clawer_sync=self.adapter,
            now=datetime(2026, 8, 11, 12, tzinfo=timezone.utc),
        )
        stream = self.subscribe(self.actor, "AIMTO Events", invite_only=True)
        self.space.state = Space.State.LAUNCHED
        self.space.stream = stream
        self.space.save(update_fields=["state", "stream", "date_updated"])

    def publication(self, number: int, payload: dict[str, object]) -> ClawerPublication:
        timestamp = "2026-08-11T10:00:00Z"
        return ClawerPublication.model_validate(
            {
                "publication_id": f"publication-{number}",
                "idempotency_key": f"identity-{number}",
                "business_identity": f"aimto-output-{number}",
                "contract": payload["contract"],
                "schema_version": "1.0",
                "producer_key": f"aimto_pipeline_{number}",
                "producer_name": f"AIMTO Pipeline {number}",
                "producing_version": "prompt:aimto:v1",
                "run_reference": f"run-{number}",
                "source_ref": self.SOURCE_REF,
                "covered_period": {
                    "start": "2026-08-11T09:00:00Z",
                    "end": timestamp,
                },
                "payload": payload,
                "evidence_refs": [
                    f"evidence_{number:02x}a{'0' * 29}",
                    f"evidence_{number:02x}b{'0' * 29}",
                ],
                "importance": "normal",
                "occurred_at": timestamp,
                "generated_at": timestamp,
                "published_at": timestamp,
                "lineage_key": None,
                "parent_publication_id": None,
                "material_change": False,
            }
        )

    def six_publications(self) -> list[ClawerPublication]:
        return [
            self.publication(
                1,
                {
                    "contract": "digest",
                    "schema_version": "1.0",
                    "title": "Conversation digest",
                    "timezone": "UTC",
                    "operation": "Venue ownership was confirmed.",
                    "marketing": "The confirmed venue is ready to share.",
                    "metrics": {"messages": 2, "text": 2, "media": 0, "voice": 0},
                    "generation_context": "AI · test",
                },
            ),
            self.publication(
                2,
                {
                    "contract": "progress_update",
                    "schema_version": "1.0",
                    "title": "Lobby assets",
                    "status": "in_progress",
                    "updates": ["Final formats are being reviewed."],
                    "resolved_items": ["Draft approved."],
                    "blockers": [],
                },
            ),
            self.publication(
                3,
                {
                    "contract": "suggested_action",
                    "schema_version": "1.0",
                    "wording": "Confirm language coverage.",
                    "proposed_assignee": None,
                    "proposed_due_date": None,
                },
            ),
            self.publication(
                4,
                {
                    "contract": "decision",
                    "schema_version": "1.0",
                    "title": "Coordination channel",
                    "decision": "Keep coordination in the main group.",
                    "rationale": "The group already contains all leads.",
                    "lifecycle": "active",
                },
            ),
            self.publication(
                5,
                {
                    "contract": "digest",
                    "schema_version": "1.0",
                    "title": "Marketing digest",
                    "timezone": "UTC",
                    "operation": "The leaderboard is live.",
                    "marketing": "Share the confirmed leaderboard launch.",
                    "metrics": {"messages": 1, "text": 1, "media": 0, "voice": 0},
                    "generation_context": "AI · test",
                },
            ),
            self.publication(
                6,
                {
                    "contract": "analysis",
                    "schema_version": "1.0",
                    "title": "Volunteer readiness",
                    "timezone": "UTC",
                    "summary": "Headcount is strong while ownership remains incomplete.",
                    "findings": [
                        {
                            "title": "Ownership gap",
                            "detail": "Several roles still lack named owners.",
                        }
                    ],
                    "generation_context": "AI · test",
                    "sentiment": None,
                },
            ),
        ]

    def set_page(
        self,
        *,
        cursor: str | None,
        next_cursor: str,
        publications: list[ClawerPublication],
    ) -> None:
        self.adapter.publication_pages[
            (
                str(self.realm.uuid),
                str(self.account.external_account_id),
                self.SOURCE_REF,
                cursor,
            )
        ] = ClawerPublicationPage(
            publications=publications,
            next_cursor=next_cursor,
            has_more=False,
        )

    def test_contract_rejects_raw_provider_identifiers_in_display_names(self) -> None:
        raw = self.six_publications()[0].model_dump(mode="json")
        raw["producer_name"] = "12025550123@g.us"
        with self.assertRaisesRegex(ValueError, "provider identifier"):
            ClawerPublication.model_validate(raw)

        with self.assertRaisesRegex(ValueError, "source content or media"):
            ResolvedEvidence.model_validate(
                {
                    "evidence_ref": f"evidence_{'0' * 32}",
                    "source_ref": self.SOURCE_REF,
                    "sender": {"ref": f"person_{'a' * 32}", "display_name": "Participant"},
                    "timestamp": "2026-08-11T10:00:00Z",
                    "content": {
                        "text": None,
                        "voice_transcript": None,
                        "media_description": None,
                    },
                    "media": None,
                }
            )

    def test_v10_publication_hash_remains_frozen_without_default_disputes(self) -> None:
        legacy = ClawerPublication.model_validate(
            {
                "publication_id": "publication-legacy",
                "idempotency_key": "identity-legacy",
                "business_identity": "business-legacy",
                "contract": "progress_update",
                "schema_version": "1.0",
                "producer_key": "progress",
                "producer_name": "Progress",
                "producing_version": "v1",
                "run_reference": "run-legacy",
                "source_ref": self.SOURCE_REF,
                "covered_period": {
                    "start": "2026-08-11T09:00:00Z",
                    "end": "2026-08-11T10:00:00Z",
                },
                "payload": {
                    "contract": "progress_update",
                    "schema_version": "1.0",
                    "title": "Readiness",
                    "status": "in_progress",
                    "updates": ["Work continues."],
                    "resolved_items": [],
                    "blockers": [],
                },
                "evidence_refs": [],
                "importance": "normal",
                "occurred_at": "2026-08-11T10:00:00Z",
                "generated_at": "2026-08-11T10:00:00Z",
                "published_at": "2026-08-11T10:00:00Z",
                "lineage_key": None,
                "parent_publication_id": None,
                "material_change": False,
            }
        )
        self.assertEqual(legacy.disputed_details, [])
        self.assertEqual(
            publication_envelope_hash(legacy),
            "8be2243ab0e08f1c3919b77fa4e3d340469629c41a58a69c3d569aad3228a22f",
        )

    def test_all_six_outputs_materialize_once_and_replay_advances_cursor(self) -> None:
        publications = self.six_publications()
        self.set_page(cursor=None, next_cursor="cursor:one", publications=publications)

        first = sync_space_attachment(
            attachment_id=self.attachment.id,
            assistant=self.assistant,
            clawer_sync=self.adapter,
        )

        self.assertEqual(first.created, 6)
        self.assertEqual(first.replayed, 0)
        self.assertEqual(
            list(
                GeneratedItem.objects.order_by("publication_id").values_list(
                    "output_type", flat=True
                )
            ),
            ["digest", "progress_update", "suggested_action", "decision", "digest", "analysis"],
        )
        self.assertEqual(EvidenceLink.objects.count(), 12)
        self.assertEqual(
            list(
                EvidenceLink.objects.filter(generated_item__publication_id="publication-3")
                .order_by("position")
                .values_list("evidence_ref", flat=True)
            ),
            [f"evidence_03a{'0' * 29}", f"evidence_03b{'0' * 29}"],
        )
        suggested = GeneratedItem.objects.get(publication_id="publication-3")
        self.assertNotIn("Awaiting confirmation", suggested.message.content)
        action = SuggestedAction.objects.get(generated_item=suggested)
        self.assertEqual(action.state, SuggestedAction.State.PENDING)
        self.assertEqual(action.wording, "Confirm language coverage.")
        message_dict: dict[str, Any] = {"id": suggested.message_id}
        add_hover_metadata([message_dict], realm_id=self.realm.id, user_profile=self.actor)
        self.assertEqual(
            message_dict["hover_generated_item"]["evidence_url"],
            f"/json/hover/spaces/{self.space.id}/generated-items/{suggested.id}/evidence",
        )
        self.assertEqual(
            message_dict["hover_generated_item"]["suggested_action"]["state"], "pending"
        )

        GeneratedItem.objects.update(publication_envelope_hash="")

        self.set_page(
            cursor="cursor:one",
            next_cursor="cursor:two",
            publications=publications,
        )
        replay = sync_space_attachment(
            attachment_id=self.attachment.id,
            assistant=self.assistant,
            clawer_sync=self.adapter,
        )
        self.assertEqual(replay.created, 0)
        self.assertEqual(replay.replayed, 6)
        self.assertEqual(GeneratedItem.objects.count(), 6)
        self.assertEqual(Message.objects.filter(realm=self.realm, sender=self.assistant).count(), 6)
        assert self.space.stream is not None
        self.assertTrue(
            Subscription.objects.filter(
                user_profile=self.assistant,
                recipient=self.space.stream.recipient,
                active=True,
            ).exists()
        )
        self.assertFalse(
            SpaceMembership.objects.filter(space=self.space, user=self.assistant).exists()
        )
        self.assertFalse(GeneratedItem.objects.filter(publication_envelope_hash="").exists())
        self.attachment.refresh_from_db()
        self.assertEqual(self.attachment.publication_cursor, "cursor:two")

    def test_mixed_reordered_replay_and_lost_response_converge_once(self) -> None:
        first, second, third = self.six_publications()[:3]
        self.set_page(
            cursor=None,
            next_cursor="cursor:committed-but-response-lost",
            publications=[first, second],
        )

        # The caller never observes this result, simulating a lost response after
        # Hover has committed the messages and cursor.
        sync_space_attachment(
            attachment_id=self.attachment.id,
            assistant=self.assistant,
            clawer_sync=self.adapter,
        )
        self.set_page(
            cursor="cursor:committed-but-response-lost",
            next_cursor="cursor:recovered",
            publications=[second, first, third],
        )

        with self.assertLogs("zulip.hover.telemetry", level="INFO") as telemetry:
            recovered = sync_space_attachment(
                attachment_id=self.attachment.id,
                assistant=self.assistant,
                clawer_sync=self.adapter,
            )

        self.assertEqual((recovered.created, recovered.replayed), (1, 2))
        self.assertEqual(GeneratedItem.objects.count(), 3)
        self.assertEqual(Message.objects.filter(realm=self.realm, sender=self.assistant).count(), 3)
        self.assertTrue(any("outcome=duplicate_replayed" in line for line in telemetry.output))

    def test_interrupted_pagination_retries_from_last_committed_cursor(self) -> None:
        first, second = self.six_publications()[:2]
        first_page = ClawerPublicationPage(
            publications=[first],
            next_cursor="cursor:page-one",
            has_more=True,
        )
        second_page = ClawerPublicationPage(
            publications=[second],
            next_cursor="cursor:page-two",
            has_more=False,
        )
        interruption = ClawerSyncError(
            error_code="clawer_timeout",
            operation="sync",
            http_status_code=504,
            retryable=True,
        )

        with patch.object(
            self.adapter,
            "sync_publications",
            side_effect=[first_page, interruption, second_page],
        ):
            first_result = sync_space_attachment(
                attachment_id=self.attachment.id,
                assistant=self.assistant,
                clawer_sync=self.adapter,
            )
            with self.assertRaisesRegex(PublicationSyncError, "clawer_timeout"):
                sync_space_attachment(
                    attachment_id=self.attachment.id,
                    assistant=self.assistant,
                    clawer_sync=self.adapter,
                )
            self.attachment.refresh_from_db()
            self.assertEqual(self.attachment.publication_cursor, "cursor:page-one")

            recovered = sync_space_attachment(
                attachment_id=self.attachment.id,
                assistant=self.assistant,
                clawer_sync=self.adapter,
            )

        self.assertTrue(first_result.has_more)
        self.assertEqual((recovered.created, recovered.next_cursor), (1, "cursor:page-two"))
        self.assertEqual(
            list(
                GeneratedItem.objects.order_by("publication_id").values_list(
                    "publication_id", flat=True
                )
            ),
            ["publication-1", "publication-2"],
        )
        self.assertEqual(
            list(PublicationSyncAttempt.objects.order_by("id").values_list("outcome", flat=True)),
            ["success", "error", "success"],
        )

    def test_retry_after_native_message_creation_rolls_back_then_converges(self) -> None:
        publication = self.six_publications()[0]
        self.set_page(
            cursor=None,
            next_cursor="cursor:after-interruption",
            publications=[publication],
        )
        original_create = GeneratedItem.objects.create

        def create_then_interrupt(**kwargs: Any) -> GeneratedItem:
            original_create(**kwargs)
            raise PublicationSyncError("worker_interrupted", retryable=True)

        with (
            patch(
                "hover.publication_sync.GeneratedItem.objects.create",
                side_effect=create_then_interrupt,
            ),
            self.assertRaisesRegex(PublicationSyncError, "worker_interrupted"),
        ):
            sync_space_attachment(
                attachment_id=self.attachment.id,
                assistant=self.assistant,
                clawer_sync=self.adapter,
            )

        self.assertEqual(GeneratedItem.objects.count(), 0)
        self.assertEqual(Message.objects.filter(realm=self.realm, sender=self.assistant).count(), 0)
        self.attachment.refresh_from_db()
        self.assertEqual(self.attachment.publication_cursor, "")

        recovered = sync_space_attachment(
            attachment_id=self.attachment.id,
            assistant=self.assistant,
            clawer_sync=self.adapter,
        )
        self.assertEqual((recovered.created, recovered.replayed), (1, 0))
        self.assertEqual(GeneratedItem.objects.count(), 1)
        self.assertEqual(Message.objects.filter(realm=self.realm, sender=self.assistant).count(), 1)

    def test_lineage_history_uses_event_time_when_transport_is_reordered(self) -> None:
        parent, child = self.six_publications()[:2]
        parent.lineage_key = "scenario-lineage"
        child.lineage_key = "scenario-lineage"
        child.parent_publication_id = parent.publication_id
        child.occurred_at = parent.occurred_at + timedelta(minutes=1)
        child.generated_at = parent.generated_at + timedelta(minutes=1)
        child.published_at = parent.published_at + timedelta(minutes=1)
        self.set_page(
            cursor=None,
            next_cursor="cursor:lineage",
            publications=[child, parent],
        )

        sync_space_attachment(
            attachment_id=self.attachment.id,
            assistant=self.assistant,
            clawer_sync=self.adapter,
        )
        parent_item = GeneratedItem.objects.get(publication_id=parent.publication_id)
        child_item = GeneratedItem.objects.get(publication_id=child.publication_id)
        message_dicts: list[dict[str, Any]] = [
            {"id": parent_item.message_id},
            {"id": child_item.message_id},
        ]
        add_hover_metadata(message_dicts, realm_id=self.realm.id, user_profile=self.actor)
        by_id = {message["id"]: message["hover_generated_item"] for message in message_dicts}

        self.assertEqual(child_item.parent_publication_id, parent.publication_id)
        self.assertFalse(by_id[parent_item.message_id]["lineage"]["is_latest"])
        self.assertTrue(by_id[child_item.message_id]["lineage"]["is_latest"])
        self.assertEqual(
            [entry["message_id"] for entry in by_id[child_item.message_id]["lineage"]["history"]],
            [child_item.message_id, parent_item.message_id],
        )

    def test_attachment_failure_does_not_undo_another_attachment_success(self) -> None:
        publication = self.six_publications()[0]
        self.set_page(cursor=None, next_cursor="cursor:healthy", publications=[publication])
        successful = sync_space_attachment(
            attachment_id=self.attachment.id,
            assistant=self.assistant,
            clawer_sync=self.adapter,
        )

        second_account = ConnectedAccount.objects.create(
            realm=self.realm,
            provider_key="github",
            provider_name="GitHub",
            external_account_id=uuid4(),
            display_name="Recovery source",
            created_by=self.actor,
            owner=self.actor,
            approval_state=ConnectedAccount.ApprovalState.APPROVED,
        )
        second_source = Source.objects.create(
            realm=self.realm,
            account=second_account,
            adapter_key="github",
            provider_key="github",
            source_type="repository",
            external_ref="src_eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee",
            display_name="Recovery source",
        )
        second_attachment = SpaceAttachment.objects.create(
            realm=self.realm,
            space=self.space,
            source=second_source,
            state=SpaceAttachment.State.ACTIVE,
            history_window=SpaceAttachment.HistoryWindow.TODAY,
            history_timezone="UTC",
            history_start_at=datetime(2026, 8, 11, tzinfo=timezone.utc),
            attached_by=self.actor,
        )

        class FailingAdapter(InMemoryClawerSync):
            @override
            def sync_publications(self, **_kwargs: object) -> ClawerPublicationPage:
                raise ClawerSyncError(
                    error_code="clawer_unavailable",
                    operation="sync",
                    http_status_code=503,
                    retryable=True,
                )

        with self.assertRaisesRegex(PublicationSyncError, "clawer_unavailable"):
            sync_space_attachment(
                attachment_id=second_attachment.id,
                assistant=self.assistant,
                clawer_sync=FailingAdapter(),
            )

        self.assertEqual(successful.created, 1)
        self.assertEqual(GeneratedItem.objects.filter(attachment=self.attachment).count(), 1)
        self.assertEqual(GeneratedItem.objects.filter(attachment=second_attachment).count(), 0)

    def test_batch_failure_rolls_back_message_provenance_and_cursor(self) -> None:
        publications = self.six_publications()[:2]
        progress = publications[1]
        cast(ProgressUpdatePayload, progress.payload).updates = ["x" * 20_000]
        self.set_page(cursor=None, next_cursor="cursor:invalid", publications=publications)

        with self.assertRaisesRegex(PublicationSyncError, "publication_content_too_long"):
            sync_space_attachment(
                attachment_id=self.attachment.id,
                assistant=self.assistant,
                clawer_sync=self.adapter,
            )

        self.assertEqual(GeneratedItem.objects.count(), 0)
        self.assertEqual(EvidenceLink.objects.count(), 0)
        self.assertEqual(Message.objects.filter(realm=self.realm, sender=self.assistant).count(), 0)
        self.attachment.refresh_from_db()
        self.assertEqual(self.attachment.publication_cursor, "")
        self.assertEqual(
            self.attachment.last_publication_sync_error, "publication_content_too_long"
        )
        self.assertEqual(self.attachment.publication_sync_failures, 1)
        self.assertEqual(
            self.attachment.publication_sync_state,
            SpaceAttachment.PublicationSyncState.BLOCKED,
        )
        attempt = PublicationSyncAttempt.objects.get()
        self.assertEqual(attempt.error_code, "publication_content_too_long")
        self.assertFalse(attempt.retryable)
        self.assertEqual(attempt.publication_count, 2)

    def test_authorized_evidence_resolution_uses_stored_refs_in_order(self) -> None:
        publication = self.six_publications()[0]
        self.set_page(
            cursor=None,
            next_cursor="cursor:evidence",
            publications=[publication],
        )
        sync_space_attachment(
            attachment_id=self.attachment.id,
            assistant=self.assistant,
            clawer_sync=self.adapter,
        )
        for index, evidence_ref in enumerate(publication.evidence_refs):
            self.adapter.evidence[(str(self.realm.uuid), self.SOURCE_REF, evidence_ref)] = (
                ResolvedEvidence.model_validate(
                    {
                        "evidence_ref": evidence_ref,
                        "source_ref": self.SOURCE_REF,
                        "sender": {
                            "ref": f"person_{index + 1:032x}",
                            "display_name": f"Participant {index + 1}",
                        },
                        "timestamp": "2026-08-11T10:00:00Z",
                        "content": {
                            "text": f"Exact evidence {index + 1}",
                            "voice_transcript": None,
                            "media_description": None,
                        },
                        "media": None,
                    }
                )
            )

        item = GeneratedItem.objects.get(publication_id=publication.publication_id)
        self.login_user(self.actor)
        with patch("hover.views_publications.get_clawer_sync", return_value=self.adapter):
            result = self.client_post(
                f"/json/hover/spaces/{self.space.id}/generated-items/{item.id}/evidence"
            )
        payload = self.assert_json_success(result)
        self.assertEqual(
            [entry["evidence_ref"] for entry in payload["evidence"]],
            publication.evidence_refs,
        )
        self.assertEqual(self.adapter.evidence_calls[-1]["refs"], publication.evidence_refs)

    def test_evidence_resolution_rechecks_membership_and_classifies_failures(self) -> None:
        publication = self.six_publications()[0]
        self.set_page(cursor=None, next_cursor="cursor:evidence-errors", publications=[publication])
        sync_space_attachment(
            attachment_id=self.attachment.id,
            assistant=self.assistant,
            clawer_sync=self.adapter,
        )
        item = GeneratedItem.objects.get(publication_id=publication.publication_id)

        non_member = self.example_user("iago")
        self.login_user(non_member)
        with patch("hover.views_publications.get_clawer_sync", return_value=self.adapter):
            denied = self.client_post(
                f"/json/hover/spaces/{self.space.id}/generated-items/{item.id}/evidence"
            )
        self.assert_json_error(denied, "Invalid Space ID")
        self.assertEqual(self.adapter.evidence_calls, [])

        SpaceMembership.objects.create(
            realm=self.realm,
            space=self.space,
            user=non_member,
            role=SpaceMembership.Role.SUBSCRIBER,
            added_by=self.actor,
        )
        denied_native_message = self.client_post(
            f"/json/hover/spaces/{self.space.id}/generated-items/{item.id}/evidence"
        )
        self.assert_json_error(denied_native_message, "Invalid message(s)")
        self.assertEqual(self.adapter.evidence_calls, [])
        SpaceMembership.objects.filter(space=self.space, user=non_member).delete()

        class RetryableEvidenceAdapter(InMemoryClawerSync):
            @override
            def resolve_evidence(self, **_kwargs: object) -> list[ResolvedEvidence]:
                raise ClawerSyncError(
                    error_code="clawer_timeout",
                    operation="evidence_resolution",
                    http_status_code=504,
                    retryable=True,
                )

        self.login_user(self.actor)
        with (
            self.settings(TEST_SUITE=False),
            patch(
                "hover.views_publications.get_clawer_sync",
                return_value=RetryableEvidenceAdapter(),
            ),
        ):
            self.client.raise_request_exception = False
            try:
                retrying = self.client_post(
                    f"/json/hover/spaces/{self.space.id}/generated-items/{item.id}/evidence"
                )
            finally:
                self.client.raise_request_exception = True
        retrying_payload = orjson.loads(retrying.content)
        self.assertEqual(retrying.status_code, 504)
        self.assertTrue(retrying_payload["retryable"])
        self.assertEqual(retrying_payload["error_code"], "clawer_timeout")

        self.account.approval_state = ConnectedAccount.ApprovalState.REVOKED
        self.account.save(update_fields=["approval_state", "date_updated"])
        with patch("hover.views_publications.get_clawer_sync", return_value=self.adapter):
            revoked_account = self.client_post(
                f"/json/hover/spaces/{self.space.id}/generated-items/{item.id}/evidence"
            )
        revoked_account_payload = orjson.loads(revoked_account.content)
        self.assertEqual(revoked_account.status_code, 404)
        self.assertEqual(revoked_account_payload["error_code"], "evidence_not_resolvable")
        self.account.approval_state = ConnectedAccount.ApprovalState.APPROVED
        self.account.save(update_fields=["approval_state", "date_updated"])

        EvidenceLink.objects.filter(generated_item=item).delete()
        missing = self.client_post(
            f"/json/hover/spaces/{self.space.id}/generated-items/{item.id}/evidence"
        )
        missing_payload = orjson.loads(missing.content)
        self.assertEqual(missing.status_code, 404)
        self.assertFalse(missing_payload["retryable"])
        self.assertEqual(missing_payload["error_code"], "evidence_not_resolvable")

        SpaceMembership.objects.filter(space=self.space, user=self.actor).delete()
        revoked = self.client_post(
            f"/json/hover/spaces/{self.space.id}/generated-items/{item.id}/evidence"
        )
        self.assert_json_error(revoked, "Invalid Space ID")

    def test_invalid_upstream_contract_records_content_free_failure(self) -> None:
        class InvalidAdapter(InMemoryClawerSync):
            @override
            def sync_publications(self, **_kwargs: object) -> ClawerPublicationPage:
                raise ClawerSyncError(
                    error_code="invalid_upstream_contract",
                    operation="sync",
                    http_status_code=502,
                    retryable=False,
                )

        with self.assertRaisesRegex(PublicationSyncError, "invalid_upstream_contract"):
            sync_space_attachment(
                attachment_id=self.attachment.id,
                assistant=self.assistant,
                clawer_sync=InvalidAdapter(),
            )

        self.assertEqual(GeneratedItem.objects.count(), 0)
        self.attachment.refresh_from_db()
        self.assertEqual(self.attachment.last_publication_sync_error, "invalid_upstream_contract")

    def test_changed_replay_is_rejected_by_immutable_envelope_hash(self) -> None:
        publication = self.six_publications()[0]
        self.set_page(cursor=None, next_cursor="cursor:accepted", publications=[publication])
        sync_space_attachment(
            attachment_id=self.attachment.id,
            assistant=self.assistant,
            clawer_sync=self.adapter,
        )

        cast(DigestPayload, publication.payload).title = "Changed after publication"
        self.set_page(
            cursor="cursor:accepted",
            next_cursor="cursor:collision",
            publications=[publication],
        )
        with self.assertRaisesRegex(PublicationSyncError, "publication_identity_conflict"):
            sync_space_attachment(
                attachment_id=self.attachment.id,
                assistant=self.assistant,
                clawer_sync=self.adapter,
            )

        self.assertEqual(GeneratedItem.objects.count(), 1)
        self.assertEqual(Message.objects.filter(realm=self.realm, sender=self.assistant).count(), 1)
        self.attachment.refresh_from_db()
        self.assertEqual(self.attachment.publication_cursor, "cursor:accepted")
        self.assertEqual(
            self.attachment.publication_sync_state,
            SpaceAttachment.PublicationSyncState.BLOCKED,
        )

    def test_material_dispute_creates_one_native_targeted_request_and_resolves(self) -> None:
        raw = self.six_publications()[1].model_dump(mode="json")
        raw["schema_version"] = "1.1"
        raw["payload"]["schema_version"] = "1.1"
        raw["disputed_details"] = [
            {
                "ambiguity_key": f"ambiguity_{'a' * 32}",
                "field_path": "status",
                "summary": "Credible updates disagree about completion status.",
                "evidence_refs": raw["evidence_refs"],
                "involved_person_refs": [],
                "material": True,
            }
        ]
        publication = ClawerPublication.model_validate(raw)
        self.set_page(cursor=None, next_cursor="cursor:review", publications=[publication])

        with (
            self.assertLogs("zulip.hover.telemetry", level="INFO") as request_telemetry,
            self.captureOnCommitCallbacks(execute=True),
        ):
            sync_space_attachment(
                attachment_id=self.attachment.id,
                assistant=self.assistant,
                clawer_sync=self.adapter,
            )
        self.assertTrue(
            any("event=review outcome=requested" in line for line in request_telemetry.output)
        )

        item = GeneratedItem.objects.get(publication_id=publication.publication_id)
        detail = DisputedDetail.objects.get(generated_item=item)
        request = ReviewRequest.objects.get(disputed_detail=detail)
        target = ReviewRequestTarget.objects.get(review_request=request)
        self.assertEqual(target.user, self.actor)
        self.assertEqual(target.reason, ReviewRequestTarget.Reason.SPACE_ADMIN_FALLBACK)
        self.assertEqual(
            list(
                DisputedEvidenceLink.objects.filter(disputed_detail=detail)
                .order_by("position")
                .values_list("evidence_link__evidence_ref", flat=True)
            ),
            publication.disputed_details[0].evidence_refs,
        )
        self.assertTrue(
            UserMessage.objects.get(
                user_profile=self.actor, message=request.message
            ).flags.mentioned
        )
        self.assertEqual(Message.objects.filter(realm=self.realm, sender=self.assistant).count(), 2)

        root_metadata: dict[str, Any] = {"id": item.message_id}
        request_metadata: dict[str, Any] = {"id": request.message_id}
        add_hover_metadata([root_metadata, request_metadata], realm_id=self.realm.id)
        serialized = root_metadata["hover_generated_item"]["disputed_details"][0]
        self.assertEqual(serialized["state"], "needs_review")
        self.assertEqual(serialized["review_request"]["message_id"], request.message_id)
        self.assertEqual(
            request_metadata["hover_review_request"]["root_message_id"], item.message_id
        )

        for index, evidence_ref in enumerate(publication.disputed_details[0].evidence_refs):
            self.adapter.evidence[(str(self.realm.uuid), self.SOURCE_REF, evidence_ref)] = (
                ResolvedEvidence.model_validate(
                    {
                        "evidence_ref": evidence_ref,
                        "source_ref": self.SOURCE_REF,
                        "sender": {
                            "ref": f"person_{index + 1:032x}",
                            "display_name": f"Participant {index + 1}",
                        },
                        "timestamp": "2026-08-11T10:00:00Z",
                        "content": {
                            "text": f"Conflicting evidence {index + 1}",
                            "voice_transcript": None,
                            "media_description": None,
                        },
                        "media": None,
                    }
                )
            )
        self.login_user(self.actor)
        with patch("hover.views_publications.get_clawer_sync", return_value=self.adapter):
            evidence_result = self.client_get(
                f"/json/hover/spaces/{self.space.id}/generated-items/{item.id}/"
                f"disputed-details/{detail.id}/evidence"
            )
        evidence_payload = self.assert_json_success(evidence_result)
        self.assertEqual(
            [entry["evidence_ref"] for entry in evidence_payload["evidence"]],
            publication.disputed_details[0].evidence_refs,
        )
        self.assertEqual(
            self.adapter.evidence_calls[-1]["refs"],
            publication.disputed_details[0].evidence_refs,
        )

        with (
            self.assertLogs("zulip.hover.telemetry", level="INFO") as resolution_telemetry,
            self.captureOnCommitCallbacks(execute=True),
        ):
            response = self.client_post(
                "/json/messages",
                {
                    "type": "channel",
                    "to": orjson.dumps(self.space.stream_id).decode(),
                    "topic": item.message.topic_name(),
                    "content": "Confirmed from the latest source update.",
                    "hover_generated_item_id": item.id,
                    "hover_response_type": "review",
                    "hover_review_field": "status",
                    "hover_review_value": '"completed"',
                },
            )
        self.assertTrue(
            any("event=review outcome=resolved" in line for line in resolution_telemetry.output)
        )
        response_data = self.assert_json_success(response)
        detail.refresh_from_db()
        request.refresh_from_db()
        self.assertEqual(detail.state, DisputedDetail.State.RESOLVED)
        self.assertEqual(request.state, ReviewRequest.State.RESOLVED)
        self.assertEqual(detail.resolved_by_revision_id, request.resolved_by_revision_id)
        response_metadata: dict[str, Any] = {"id": response_data["id"]}
        add_hover_metadata([response_metadata], realm_id=self.realm.id)
        self.assertEqual(
            response_metadata["hover_response"]["generated_item"]["disputed_details"][0]["state"],
            "resolved",
        )

    def test_non_material_dispute_is_visible_without_request_or_notification(self) -> None:
        raw = self.six_publications()[3].model_dump(mode="json")
        raw["schema_version"] = "1.1"
        raw["payload"]["schema_version"] = "1.1"
        raw["disputed_details"] = [
            {
                "ambiguity_key": f"ambiguity_{'b' * 32}",
                "field_path": "rationale",
                "summary": "Two credible explanations remain plausible.",
                "evidence_refs": raw["evidence_refs"],
                "involved_person_refs": [],
                "material": False,
            }
        ]
        publication = ClawerPublication.model_validate(raw)
        self.set_page(cursor=None, next_cursor="cursor:uncertain", publications=[publication])
        sync_space_attachment(
            attachment_id=self.attachment.id,
            assistant=self.assistant,
            clawer_sync=self.adapter,
        )
        detail = DisputedDetail.objects.get()
        self.assertFalse(detail.material)
        self.assertFalse(ReviewRequest.objects.exists())
        self.assertEqual(Message.objects.filter(realm=self.realm, sender=self.assistant).count(), 1)

    def test_material_dispute_targets_verified_involved_space_member(self) -> None:
        participant_ref = f"person_{'d' * 32}"
        SourceParticipantBinding.objects.create(
            realm=self.realm,
            source=self.attachment.source,
            participant_ref=participant_ref,
            user=self.actor,
            match_basis=SourceParticipantBinding.MatchBasis.VERIFIED_EMAIL,
            observation_basis=f"obs_{'e' * 32}",
        )
        raw = self.six_publications()[1].model_dump(mode="json")
        raw["schema_version"] = "1.1"
        raw["payload"]["schema_version"] = "1.1"
        raw["disputed_details"] = [
            {
                "ambiguity_key": f"ambiguity_{'d' * 32}",
                "field_path": "status",
                "summary": "Credible updates disagree about completion status.",
                "evidence_refs": raw["evidence_refs"],
                "involved_person_refs": [participant_ref],
                "material": True,
            }
        ]
        publication = ClawerPublication.model_validate(raw)
        self.set_page(cursor=None, next_cursor="cursor:involved", publications=[publication])
        sync_space_attachment(
            attachment_id=self.attachment.id,
            assistant=self.assistant,
            clawer_sync=self.adapter,
        )
        target = ReviewRequestTarget.objects.get()
        self.assertEqual(target.user, self.actor)
        self.assertEqual(target.reason, ReviewRequestTarget.Reason.INVOLVED_TEAMMATE)

    def test_v11_dispute_contract_rejects_unsafe_or_non_referential_fields(self) -> None:
        raw = self.six_publications()[1].model_dump(mode="json")
        raw["schema_version"] = "1.1"
        raw["payload"]["schema_version"] = "1.1"
        raw["disputed_details"] = [
            {
                "ambiguity_key": f"ambiguity_{'c' * 32}",
                "field_path": "status.value",
                "summary": "Status differs.",
                "evidence_refs": raw["evidence_refs"],
                "involved_person_refs": [],
                "material": True,
            }
        ]
        with self.assertRaisesRegex(ValueError, "field_path"):
            ClawerPublication.model_validate(raw)

        raw["disputed_details"][0]["field_path"] = "status"
        raw["disputed_details"][0]["evidence_refs"] = [
            raw["evidence_refs"][0],
            f"evidence_{'f' * 32}",
        ]
        with self.assertRaisesRegex(ValueError, "belong to the publication"):
            ClawerPublication.model_validate(raw)

        raw["disputed_details"][0]["evidence_refs"] = raw["evidence_refs"]
        raw["disputed_details"][0]["summary"] = "Ask lead@example.com to decide."
        with self.assertRaisesRegex(ValueError, "provider identifier"):
            ClawerPublication.model_validate(raw)

    def test_publication_identity_is_scoped_to_each_space_attachment(self) -> None:
        second_space = do_create_space(
            self.actor,
            name="AIMTO Archive",
            description="",
            category=self.space.category,
        )
        second_attachment, _created = do_attach_source(
            acting_user=self.actor,
            space=second_space,
            account_id=self.account.id,
            source_ref=self.SOURCE_REF,
            history_window="today",
            history_timezone="UTC",
            custom_start_date=None,
            clawer_sync=self.adapter,
            now=datetime(2026, 8, 11, 12, tzinfo=timezone.utc),
        )
        second_stream = self.subscribe(self.actor, "AIMTO Archive", invite_only=True)
        second_space.state = Space.State.LAUNCHED
        second_space.stream = second_stream
        second_space.save(update_fields=["state", "stream", "date_updated"])

        publication = self.six_publications()[0]
        self.set_page(cursor=None, next_cursor="cursor:shared", publications=[publication])
        for attachment in [self.attachment, second_attachment]:
            sync_space_attachment(
                attachment_id=attachment.id,
                assistant=self.assistant,
                clawer_sync=self.adapter,
            )

        self.assertEqual(
            GeneratedItem.objects.filter(publication_id=publication.publication_id).count(),
            2,
        )
        self.assertEqual(
            GeneratedItem.objects.filter(
                publication_id=publication.publication_id,
                attachment=second_attachment,
            ).count(),
            1,
        )

    def test_active_lease_prevents_duplicate_fetch_and_expired_lease_is_recoverable(self) -> None:
        self.attachment.publication_sync_state = SpaceAttachment.PublicationSyncState.LEASED
        self.attachment.publication_sync_lease_token = uuid4()
        self.attachment.publication_sync_lease_expires_at = django_timezone.now() + timedelta(
            minutes=1
        )
        self.attachment.save(
            update_fields=[
                "publication_sync_state",
                "publication_sync_lease_token",
                "publication_sync_lease_expires_at",
            ]
        )
        with self.assertRaisesRegex(PublicationSyncError, "publication_sync_already_leased"):
            sync_space_attachment(
                attachment_id=self.attachment.id,
                assistant=self.assistant,
                clawer_sync=self.adapter,
            )
        self.assertEqual(self.adapter.sync_calls, [])

        self.attachment.publication_sync_lease_expires_at = django_timezone.now() - timedelta(
            seconds=1
        )
        self.attachment.save(update_fields=["publication_sync_lease_expires_at"])
        self.set_page(cursor=None, next_cursor="cursor:recovered", publications=[])
        result = sync_space_attachment(
            attachment_id=self.attachment.id,
            assistant=self.assistant,
            clawer_sync=self.adapter,
        )
        self.assertEqual(result.next_cursor, "cursor:recovered")

    def test_retryable_transport_failure_enters_exponential_backoff(self) -> None:
        class RetryableAdapter(InMemoryClawerSync):
            @override
            def sync_publications(self, **_kwargs: object) -> ClawerPublicationPage:
                raise ClawerSyncError(
                    error_code="clawer_timeout",
                    operation="sync",
                    http_status_code=504,
                    retryable=True,
                )

        before = django_timezone.now()
        with self.assertRaisesRegex(PublicationSyncError, "clawer_timeout"):
            sync_space_attachment(
                attachment_id=self.attachment.id,
                assistant=self.assistant,
                clawer_sync=RetryableAdapter(),
            )
        self.attachment.refresh_from_db()
        self.assertEqual(
            self.attachment.publication_sync_state,
            SpaceAttachment.PublicationSyncState.BACKOFF,
        )
        assert self.attachment.next_publication_sync_at is not None
        self.assertGreaterEqual(
            self.attachment.next_publication_sync_at,
            before + timedelta(seconds=60),
        )
        self.assertTrue(PublicationSyncAttempt.objects.get().retryable)

    def test_sync_requires_one_explicitly_configured_assistant(self) -> None:
        with (
            self.settings(HOVER_ASSISTANT_EMAIL=""),
            self.assertRaisesRegex(PublicationSyncError, "invalid_hover_assistant"),
        ):
            sync_space_attachment(
                attachment_id=self.attachment.id,
                assistant=self.assistant,
                clawer_sync=self.adapter,
            )
        self.assertEqual(self.adapter.sync_calls, [])

    def test_attachment_lifecycle_is_rechecked_after_fetch(self) -> None:
        publication = self.six_publications()[0]

        class RacingAdapter(InMemoryClawerSync):
            @override
            def sync_publications(self, **_kwargs: object) -> ClawerPublicationPage:
                SpaceAttachment.objects.filter(id=self_attachment.id).update(
                    state=SpaceAttachment.State.PENDING_SYNC
                )
                return ClawerPublicationPage(
                    publications=[publication],
                    next_cursor="cursor:raced",
                    has_more=False,
                )

        self_attachment = self.attachment
        with self.assertRaisesRegex(PublicationSyncError, "attachment_not_syncable"):
            sync_space_attachment(
                attachment_id=self.attachment.id,
                assistant=self.assistant,
                clawer_sync=RacingAdapter(),
            )
        self.assertEqual(GeneratedItem.objects.count(), 0)
        self.assertEqual(Message.objects.filter(realm=self.realm, sender=self.assistant).count(), 0)

    def test_connected_account_approval_is_rechecked_after_fetch(self) -> None:
        publication = self.six_publications()[0]

        class RacingAdapter(InMemoryClawerSync):
            @override
            def sync_publications(self, **_kwargs: object) -> ClawerPublicationPage:
                ConnectedAccount.objects.filter(id=account.id).update(
                    approval_state=ConnectedAccount.ApprovalState.REVOKED
                )
                return ClawerPublicationPage(
                    publications=[publication],
                    next_cursor="cursor:revoked",
                    has_more=False,
                )

        account = self.account
        with self.assertRaisesRegex(PublicationSyncError, "attachment_not_syncable"):
            sync_space_attachment(
                attachment_id=self.attachment.id,
                assistant=self.assistant,
                clawer_sync=RacingAdapter(),
            )
        self.assertEqual(GeneratedItem.objects.count(), 0)
        self.assertEqual(Message.objects.filter(realm=self.realm, sender=self.assistant).count(), 0)

    def test_materialization_batch_limit_is_stricter_than_transport_limit(self) -> None:
        with self.assertRaisesRegex(PublicationSyncError, "invalid_publication_batch_limit"):
            sync_space_attachment(
                attachment_id=self.attachment.id,
                assistant=self.assistant,
                clawer_sync=self.adapter,
                limit=MAX_PUBLICATION_SYNC_BATCH + 1,
            )
        self.assertEqual(self.adapter.sync_calls, [])
