from django.db import migrations, models
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps


def lifecycle_backfill_values(
    state: str, input_availability: str, input_destination_id: int | None, input_topic: str
) -> tuple[str, str]:
    if state != "needs_attention":
        return state, input_availability
    if input_destination_id is not None and input_topic.strip():
        return "active", "topic_unavailable"
    return "draft", "topic_unavailable"


def backfill_pipeline_lifecycle(
    apps: StateApps, schema_editor: BaseDatabaseSchemaEditor
) -> None:
    Pipeline = apps.get_model("hover", "Pipeline")
    before = Pipeline.objects.count()
    for pipeline in Pipeline.objects.filter(state="needs_attention").iterator():
        state, availability = lifecycle_backfill_values(
            pipeline.state,
            pipeline.input_availability,
            pipeline.input_destination_id,
            pipeline.input_topic,
        )
        pipeline.state = state
        pipeline.input_availability = availability
        pipeline.save(update_fields=["state", "input_availability"])
    assert Pipeline.objects.count() == before
    assert not Pipeline.objects.filter(state="needs_attention").exists()


class Migration(migrations.Migration):
    dependencies = [("hover", "0028_topic_first_pipeline_cutover")]

    operations = [
        migrations.AlterField(
            model_name="pipeline",
            name="state",
            field=models.TextField(
                choices=[
                    ("active", "Active"),
                    ("draft", "Draft"),
                    ("paused", "Paused"),
                    ("needs_attention", "Needs attention"),
                ],
                default="active",
            ),
        ),
        migrations.RunPython(backfill_pipeline_lifecycle, migrations.RunPython.noop),
    ]
