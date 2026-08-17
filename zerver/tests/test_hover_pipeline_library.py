import hashlib
import json

import orjson
from django.core.exceptions import ValidationError
from django.db import DatabaseError, transaction
from typing_extensions import override

from hover.actions_modules import ensure_prebuilt_module_catalog
from hover.models import (
    MAX_PIPELINE_RUNTIME_SECONDS,
    ModuleDefinition,
    ModuleSourceRequirement,
    ModuleSupportedTrigger,
    ModuleVersion,
    PipelineCreatorAssignment,
)
from zerver.lib.test_classes import ZulipTestCase
from zerver.models.realm_audit_logs import AuditLogEventType, RealmAuditLog


class HoverPipelineLibraryTest(ZulipTestCase):
    @override
    def setUp(self) -> None:
        super().setUp()
        self.admin = self.example_user("iago")
        self.author = self.example_user("hamlet")
        self.collaborator = self.example_user("othello")
        self.outsider = self.example_user("aaron")
        self.other_realm_user = self.lear_user("cordelia")
        self.realm = self.author.realm
        self.realm.hover_enabled = True
        self.realm.save(update_fields=["hover_enabled"])
        self.login_user(self.admin)

    def draft_data(self, **overrides: object) -> dict[str, str]:
        values: dict[str, object] = {
            "stable_key": "weekly_signal",
            "version": "1.0.0",
            "name": "Weekly Signal",
            "description": "A private signal summary.",
            "output_type": "analysis",
            "runtime_key": "hover.weekly_signal.v1",
            "prompt_key": "hover.weekly_signal.v1",
            "destination_topic": "Weekly Signal",
            "navigation_icon": "zulip-icon-sparkles",
            "navigation_order": orjson.dumps(90).decode(),
            "input_contract": orjson.dumps(
                {"kind": "attached_sources", "record_type": "message"}
            ).decode(),
            "lookback_days": orjson.dumps(7).decode(),
            "integration_keys": orjson.dumps(["calendar_read"]).decode(),
            "output_template": orjson.dumps(
                {"format": "hover_generated_update", "sections": ["strongest_signals"]}
            ).decode(),
            "maximum_runtime_seconds": orjson.dumps(600).decode(),
            "requirements": orjson.dumps(
                [
                    {
                        "key": "conversation_history",
                        "capability": "message_history",
                        "minimum_count": 1,
                        "maximum_count": 5,
                    }
                ]
            ).decode(),
            "supported_triggers": orjson.dumps(["schedule", "manual"]).decode(),
        }
        values.update(overrides)
        return {
            key: value if isinstance(value, str) else str(value) for key, value in values.items()
        }

    def grant_creator(self, user_id: int) -> None:
        result = self.client_post(
            "/json/hover/pipeline-library/creators",
            {"user_id": orjson.dumps(user_id).decode()},
        )
        self.assert_json_success(result)

    def create_draft(self, **overrides: object) -> dict[str, object]:
        result = self.client_post(
            "/json/hover/pipeline-library/drafts", self.draft_data(**overrides)
        )
        self.assert_json_success(result)
        return orjson.loads(result.content)["draft"]

    def test_library_seeds_ordinary_examples_and_hides_execution_identities(self) -> None:
        result = self.client_get("/json/hover/pipeline-library")
        self.assert_json_success(result)
        payload = orjson.loads(result.content)
        definitions = payload["definitions"]
        self.assertIn("topic_analysis", {item["stable_key"] for item in definitions})
        self.assertIn("marketing_digest", {item["stable_key"] for item in definitions})
        version = definitions[0]["versions"][0]
        self.assertNotIn("runtime_key", version)
        self.assertNotIn("prompt_key", version)
        self.assertNotIn("integration_keys", version)
        self.assertNotIn("input_contract", version)
        self.assertIn("lookback_days", version)
        self.assertNotIn("output_template", version)
        self.assertIn("maximum_runtime_seconds", version)
        self.assertEqual(payload["permissions"]["can_manage_creators"], True)

        catalog_version = orjson.loads(self.client_get("/json/hover/modules").content)["modules"][0]
        self.assertNotIn("runtime_key", catalog_version)
        self.assertNotIn("prompt_key", catalog_version)
        self.assertNotIn("integration_keys", catalog_version)

    def test_creator_roles_are_admin_managed_idempotent_and_content_safe(self) -> None:
        result = self.client_post(
            "/json/hover/pipeline-library/creators",
            {"user_id": orjson.dumps(self.author.id).decode()},
        )
        self.assert_json_success(result)
        self.assertTrue(orjson.loads(result.content)["changed"])
        replay = self.client_post(
            "/json/hover/pipeline-library/creators",
            {"user_id": orjson.dumps(self.author.id).decode()},
        )
        self.assert_json_success(replay)
        self.assertFalse(orjson.loads(replay.content)["changed"])

        self.login_user(self.collaborator)
        denied = self.client_post(
            "/json/hover/pipeline-library/creators",
            {"user_id": orjson.dumps(self.collaborator.id).decode()},
        )
        self.assert_json_error(denied, "Must be an organization administrator")

        self.login_user(self.admin)
        revoked = self.client_delete(f"/json/hover/pipeline-library/creators/{self.author.id}")
        self.assert_json_success(revoked)
        self.assertTrue(orjson.loads(revoked.content)["changed"])
        assignment = PipelineCreatorAssignment.objects.get(user=self.author)
        self.assertIsNotNone(assignment.revoked_at)
        events = list(
            RealmAuditLog.objects.filter(
                event_type__in=[
                    AuditLogEventType.HOVER_PIPELINE_CREATOR_GRANTED,
                    AuditLogEventType.HOVER_PIPELINE_CREATOR_REVOKED,
                ]
            )
        )
        self.assert_length(events, 2)
        self.assertNotIn("email", json.dumps([event.extra_data for event in events]))

    def test_private_collaboration_and_revoked_author_read_only(self) -> None:
        self.grant_creator(self.author.id)
        self.grant_creator(self.collaborator.id)
        self.login_user(self.author)
        draft = self.create_draft()

        self.login_user(self.collaborator)
        hidden = orjson.loads(self.client_get("/json/hover/pipeline-library").content)
        self.assertEqual(hidden["drafts"], [])

        self.login_user(self.author)
        added = self.client_post(
            f"/json/hover/pipeline-library/drafts/{draft['id']}/collaborators",
            {"user_id": orjson.dumps(self.collaborator.id).decode()},
        )
        self.assert_json_success(added)
        self.assertEqual(
            orjson.loads(added.content)["draft"]["collaborator_user_ids"],
            [self.collaborator.id],
        )

        self.login_user(self.collaborator)
        visible = orjson.loads(self.client_get("/json/hover/pipeline-library").content)
        self.assertEqual([item["id"] for item in visible["drafts"]], [draft["id"]])
        self.assertEqual(visible["drafts"][0]["contract"]["runtime_key"], "hover.weekly_signal.v1")
        denied_acl_change = self.client_delete(
            f"/json/hover/pipeline-library/drafts/{draft['id']}/collaborators/{self.collaborator.id}"
        )
        self.assert_json_error(
            denied_acl_change,
            "Only the draft author or an organization administrator can manage collaborators.",
        )

        self.login_user(self.outsider)
        outsider_view = orjson.loads(self.client_get("/json/hover/pipeline-library").content)
        self.assertEqual(outsider_view["drafts"], [])

        self.other_realm_user.realm.hover_enabled = True
        self.other_realm_user.realm.save(update_fields=["hover_enabled"])
        self.login_user(self.other_realm_user)
        other_realm = orjson.loads(
            self.client_get(
                "/json/hover/pipeline-library",
                subdomain=self.other_realm_user.realm.subdomain,
            ).content
        )
        self.assertEqual(other_realm["drafts"], [])

        self.login_user(self.admin)
        self.assert_json_success(
            self.client_delete(f"/json/hover/pipeline-library/creators/{self.author.id}")
        )
        self.login_user(self.author)
        still_visible = orjson.loads(self.client_get("/json/hover/pipeline-library").content)
        self.assertEqual([item["id"] for item in still_visible["drafts"]], [draft["id"]])
        denied = self.client_patch(
            f"/json/hover/pipeline-library/drafts/{draft['id']}",
            self.draft_data(revision=orjson.dumps(draft["revision"]).decode()),
        )
        self.assert_json_error(denied, "You do not have permission to edit this Pipeline draft.")
        publish_denied = self.client_post(
            f"/json/hover/pipeline-library/drafts/{draft['id']}/publish",
            {"revision": orjson.dumps(draft["revision"]).decode()},
        )
        self.assert_json_error(
            publish_denied, "You do not have permission to edit this Pipeline draft."
        )

    def test_publish_snapshots_complete_contract_and_successor_is_append_only(self) -> None:
        self.grant_creator(self.author.id)
        self.login_user(self.author)
        draft = self.create_draft()
        published = self.client_post(
            f"/json/hover/pipeline-library/drafts/{draft['id']}/publish",
            {"revision": orjson.dumps(draft["revision"]).decode()},
        )
        self.assert_json_success(published)
        payload = orjson.loads(published.content)
        version = ModuleVersion.objects.get(id=payload["version"]["id"])
        self.assertEqual(version.input_contract["kind"], "attached_sources")
        self.assertEqual(version.lookback_seconds, 604800)
        self.assertEqual(version.runtime_key, "hover.weekly_signal.v1")
        self.assertEqual(version.prompt_key, "hover.weekly_signal.v1")
        self.assertEqual(version.integration_keys, ["calendar_read"])
        self.assertEqual(
            version.output_template,
            {"format": "hover_generated_update", "sections": ["strongest_signals"]},
        )
        self.assertEqual(version.maximum_runtime_seconds, 600)
        self.assertEqual(version.version, "1.0.0")
        self.assertNotIn("runtime_key", payload["version"])
        self.assertNotIn("prompt_key", payload["version"])
        self.assertNotIn("integration_keys", payload["version"])

        contract = {
            "definition_key": "weekly_signal",
            "version": "1.0.0",
            "input_contract": {"kind": "attached_sources", "record_type": "message"},
            "lookback_seconds": 604800,
            "runtime_key": "hover.weekly_signal.v1",
            "prompt_key": "hover.weekly_signal.v1",
            "integration_keys": ["calendar_read"],
            "output_type": "analysis",
            "output_template": {
                "format": "hover_generated_update",
                "sections": ["strongest_signals"],
            },
            "maximum_runtime_seconds": 600,
            "destination_topic": "Weekly Signal",
            "navigation_icon": "zulip-icon-sparkles",
            "navigation_order": 90,
            "requirements": [
                {
                    "key": "conversation_history",
                    "capability": "message_history",
                    "minimum_count": 1,
                    "maximum_count": 5,
                }
            ],
            "supported_triggers": ["manual", "schedule"],
        }
        self.assertEqual(
            version.content_hash,
            hashlib.sha256(
                json.dumps(contract, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest(),
        )
        version.output_template = {"mutated": True}
        with self.assertRaisesRegex(ValidationError, "immutable"):
            version.save()
        with self.assertRaises(DatabaseError), transaction.atomic(savepoint=False):
            ModuleSourceRequirement.objects.bulk_create(
                [
                    ModuleSourceRequirement(
                        version=version,
                        key="late_requirement",
                        capability="message_history",
                        minimum_count=1,
                        maximum_count=1,
                    )
                ]
            )
        with self.assertRaises(DatabaseError), transaction.atomic(savepoint=False):
            ModuleSupportedTrigger.objects.filter(version=version).delete()
        with self.assertRaises(DatabaseError), transaction.atomic(savepoint=False):
            ModuleVersion.objects.filter(id=version.id).update(runtime_key="changed.runtime")
        ModuleVersion.objects.filter(id=version.id).update(published_by=None)
        version.refresh_from_db()
        self.assertIsNone(version.published_by)

        successor = self.client_post(
            f"/json/hover/pipeline-library/versions/{version.id}/successor"
        )
        self.assert_json_success(successor)
        successor_draft = orjson.loads(successor.content)["draft"]
        self.assertEqual(successor_draft["based_on_version_id"], version.id)
        successor_replay = self.client_post(
            f"/json/hover/pipeline-library/versions/{version.id}/successor"
        )
        self.assert_json_success(successor_replay)
        replay_payload = orjson.loads(successor_replay.content)
        self.assertFalse(replay_payload["created"])
        self.assertEqual(replay_payload["draft"]["id"], successor_draft["id"])
        updated = self.client_patch(
            f"/json/hover/pipeline-library/drafts/{successor_draft['id']}",
            self.draft_data(
                stable_key="weekly_signal",
                name="Weekly Signal",
                description="A private signal summary.",
                revision=orjson.dumps(successor_draft["revision"]).decode(),
                version="1.0.1",
                output_template=orjson.dumps(
                    {"format": "hover_generated_update", "sections": ["revised_summary"]}
                ).decode(),
            ),
        )
        self.assert_json_success(updated)
        updated_draft = orjson.loads(updated.content)["draft"]
        successor_publish = self.client_post(
            f"/json/hover/pipeline-library/drafts/{successor_draft['id']}/publish",
            {"revision": orjson.dumps(updated_draft["revision"]).decode()},
        )
        self.assert_json_success(successor_publish)
        successor_version = ModuleVersion.objects.get(
            id=orjson.loads(successor_publish.content)["version"]["id"]
        )
        self.assertEqual(successor_version.version, "1.0.1")
        version.refresh_from_db()
        self.assertEqual(
            version.output_template,
            {"format": "hover_generated_update", "sections": ["strongest_signals"]},
        )

    def test_runtime_cap_secret_rejection_and_revision_conflict(self) -> None:
        self.grant_creator(self.author.id)
        self.login_user(self.author)
        over_cap = self.client_post(
            "/json/hover/pipeline-library/drafts",
            self.draft_data(
                maximum_runtime_seconds=orjson.dumps(MAX_PIPELINE_RUNTIME_SECONDS + 1).decode()
            ),
        )
        self.assert_json_error(
            over_cap,
            f"Maximum runtime must be between 1 and {MAX_PIPELINE_RUNTIME_SECONDS} seconds.",
        )
        for unsafe_key in [
            "api_key",
            "access_token",
            "bearerToken",
            "webhook_url",
            "providerId",
            "jid",
            "phone_number",
        ]:
            with self.subTest(unsafe_key=unsafe_key):
                secret = self.client_post(
                    "/json/hover/pipeline-library/drafts",
                    self.draft_data(
                        input_contract=orjson.dumps({unsafe_key: "not-allowed"}).decode()
                    ),
                )
                self.assert_json_error(
                    secret, "Input contracts cannot contain credentials or endpoints."
                )
        disguised_secret = self.client_post(
            "/json/hover/pipeline-library/drafts",
            self.draft_data(
                input_contract=orjson.dumps(
                    {
                        "kind": "attached_sources",
                        "record_type": "message",
                        "value": "https://private.example/?token=secret",
                    }
                ).decode()
            ),
        )
        self.assert_json_error(disguised_secret, "Invalid Pipeline input contract.")
        disguised_output_secret = self.client_post(
            "/json/hover/pipeline-library/drafts",
            self.draft_data(
                output_template=orjson.dumps(
                    {"format": "hover_generated_update", "title": "Bearer reusable-secret"}
                ).decode()
            ),
        )
        self.assert_json_error(
            disguised_output_secret,
            "Pipeline output titles must match the Pipeline name.",
        )

        draft = self.create_draft()
        revision = draft["revision"]
        assert isinstance(revision, int)
        stale = self.client_patch(
            f"/json/hover/pipeline-library/drafts/{draft['id']}",
            self.draft_data(revision=orjson.dumps(revision - 1).decode()),
        )
        self.assertEqual(stale.status_code, 409)

    def test_archive_is_admin_only_and_keeps_rows_while_hiding_discovery(self) -> None:
        ensure_prebuilt_module_catalog(self.realm)
        definition = ModuleDefinition.objects.get(realm=self.realm, stable_key="topic_analysis")
        version = definition.versions.get()

        self.login_user(self.author)
        denied = self.client_post(f"/json/hover/pipeline-library/versions/{version.id}/archive")
        self.assert_json_error(denied, "Must be an organization administrator")

        self.login_user(self.admin)
        archived = self.client_post(f"/json/hover/pipeline-library/versions/{version.id}/archive")
        self.assert_json_success(archived)
        self.assertTrue(orjson.loads(archived.content)["version"]["archived"])
        catalog_ids = {
            item["id"]
            for item in orjson.loads(self.client_get("/json/hover/modules").content)["modules"]
        }
        self.assertNotIn(version.id, catalog_ids)
        self.assertTrue(ModuleVersion.objects.filter(id=version.id).exists())

        self.login_user(self.author)
        member_library = orjson.loads(self.client_get("/json/hover/pipeline-library").content)
        member_definition = next(
            item for item in member_library["definitions"] if item["id"] == definition.id
        )
        self.assertEqual(member_definition["versions"], [])

        self.login_user(self.admin)
        definition_archive = self.client_post(
            f"/json/hover/pipeline-library/definitions/{definition.id}/archive"
        )
        self.assert_json_success(definition_archive)
        library = orjson.loads(self.client_get("/json/hover/pipeline-library").content)
        archived_definition = next(
            item for item in library["definitions"] if item["id"] == definition.id
        )
        self.assertTrue(archived_definition["archived"])
        self.login_user(self.author)
        member_library = orjson.loads(self.client_get("/json/hover/pipeline-library").content)
        self.assertNotIn(definition.id, {item["id"] for item in member_library["definitions"]})
        audits = RealmAuditLog.objects.filter(
            event_type__in=[
                AuditLogEventType.HOVER_MODULE_VERSION_ARCHIVED,
                AuditLogEventType.HOVER_MODULE_DEFINITION_ARCHIVED,
            ]
        )
        self.assert_length(audits, 2)
        self.assertNotIn("runtime", json.dumps([item.extra_data for item in audits]))
