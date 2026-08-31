from datetime import time

from django.db import IntegrityError, transaction
from django.db.migrations.state import StateApps
from typing_extensions import override

from zerver.lib.test_classes import MigrationsTestCase


class PipelineLifecycleMigrationTest(MigrationsTestCase):
    migrate_from = "0028_topic_first_pipeline_cutover"
    migrate_to = "0030_pipeline_lifecycle_cutover"

    @override
    def setUpBeforeMigration(self, apps: StateApps) -> None:
        Pipeline = apps.get_model("hover", "Pipeline")
        Realm = apps.get_model("zerver", "Realm")
        Stream = apps.get_model("zerver", "Stream")
        UserProfile = apps.get_model("zerver", "UserProfile")
        realm = Realm.objects.get(string_id="zulip")
        streams = list(Stream.objects.filter(realm=realm).order_by("id")[:2])
        creator = UserProfile.objects.filter(realm=realm, is_active=True, is_bot=False).first()
        assert len(streams) == 2
        assert creator is not None

        common = {
            "realm_id": realm.id,
            "input_destination_id": streams[0].id,
            "input_topic": "Migration input",
            "instruction": "Summarize migration input.",
            "cadence": "daily",
            "local_time": time(9),
            "timezone": "UTC",
            "output_destination_id": streams[1].id,
            "output_topic": "Migration output",
            "created_by_id": creator.id,
        }
        self.active_id = Pipeline.objects.create(
            **common, name="Active migration pipeline", state="active"
        ).id
        self.draft_id = Pipeline.objects.create(
            **common, name="Draft migration pipeline", state="draft"
        ).id
        self.needs_attention_id = Pipeline.objects.create(
            **common,
            name="Unavailable migration pipeline",
            state="needs_attention",
            input_availability="topic_unavailable",
        ).id
        self.before_count = Pipeline.objects.count()

    def test_lifecycle_rows_are_backfilled_before_cutover(self) -> None:
        Pipeline = self.apps.get_model("hover", "Pipeline")
        self.assertEqual(Pipeline.objects.count(), self.before_count)
        self.assertEqual(Pipeline.objects.get(id=self.active_id).state, "active")
        self.assertEqual(Pipeline.objects.get(id=self.draft_id).state, "draft")
        repaired = Pipeline.objects.get(id=self.needs_attention_id)
        self.assertEqual(repaired.state, "active")
        self.assertEqual(repaired.input_availability, "topic_unavailable")

        with self.assertRaises(IntegrityError), transaction.atomic():
            Pipeline.objects.filter(id=self.active_id).update(state="needs_attention")
        Pipeline.objects.filter(
            id__in=[self.active_id, self.draft_id, self.needs_attention_id]
        ).delete()
