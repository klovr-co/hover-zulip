from datetime import datetime, timezone
from unittest.mock import patch
from uuid import UUID

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
from hover.models import ConnectedAccount, EvidenceLink, GeneratedItem, Space
from hover.publication_contracts import ClawerPublication, ClawerPublicationPage, ResolvedEvidence
from hover.publication_sync import PublicationSyncError, sync_space_attachment
from zerver.actions.channel_folders import check_add_channel_folder
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.user_groups import get_system_user_group_by_name
from zerver.models import Message
from zerver.models.groups import SystemGroups


class HoverPublicationSyncTest(ZulipTestCase):
    SOURCE_REF = "src_0123456789abcdef0123456789abcdef"

    @override
    def setUp(self) -> None:
        super().setUp()
        self.actor = self.example_user("hamlet")
        self.assistant = self.example_user("default_bot")
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
        stream = self.subscribe(self.actor, "AIMTO Events", invite_only=True)
        self.subscribe(self.assistant, "AIMTO Events", invite_only=True)
        self.space.state = Space.State.LAUNCHED
        self.space.stream = stream
        self.space.save(update_fields=["state", "stream", "date_updated"])

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
                "evidence_refs": [f"evidence-{number}-a", f"evidence-{number}-b"],
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
            ["evidence-3-a", "evidence-3-b"],
        )
        suggested = GeneratedItem.objects.get(publication_id="publication-3")
        self.assertIn("Awaiting confirmation", suggested.message.content)
        message_dict = {"id": suggested.message_id}
        add_hover_metadata([message_dict], realm_id=self.realm.id)
        self.assertEqual(
            message_dict["hover_generated_item"]["evidence_url"],
            f"/json/hover/spaces/{self.space.id}/generated-items/{suggested.id}/evidence",
        )

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
        self.attachment.refresh_from_db()
        self.assertEqual(self.attachment.publication_cursor, "cursor:two")

    def test_batch_failure_rolls_back_message_provenance_and_cursor(self) -> None:
        publications = self.six_publications()[:2]
        progress = publications[1]
        progress.payload.updates = ["x" * 20_000]
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
