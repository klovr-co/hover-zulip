import django.db.models.deletion
from django.db import migrations, models
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps


def topic_input_backfill_values(
    destination_id: int | None, topic: str, *, same_realm: bool = True
) -> tuple[int | None, str, str, str]:
    normalized_topic = topic.strip()
    if destination_id is not None and normalized_topic and same_realm:
        return destination_id, normalized_topic, "active", "available"
    return None, normalized_topic, "draft", "topic_unavailable"


def backfill_topic_inputs(apps: StateApps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    Pipeline = apps.get_model("hover", "Pipeline")
    valid = 0
    invalid = 0
    for pipeline in Pipeline.objects.select_related("connector__destination").all().iterator():
        connector = pipeline.connector
        destination_id, topic, state, availability = topic_input_backfill_values(
            connector.destination_id,
            connector.topic,
            same_realm=(
                connector.destination_id is not None
                and connector.destination.realm_id == pipeline.realm_id
            ),
        )
        pipeline.input_destination_id = destination_id
        pipeline.input_topic = topic
        pipeline.state = state if availability == "topic_unavailable" else pipeline.state
        pipeline.input_availability = availability
        if availability == "available":
            valid += 1
        else:
            invalid += 1
        pipeline.save(
            update_fields=["input_destination", "input_topic", "state", "input_availability"]
        )
    assert valid + invalid == Pipeline.objects.count()
    assert not Pipeline.objects.filter(input_destination__isnull=False, input_topic="").exists()


class Migration(migrations.Migration):
    dependencies = [("hover", "0026_connector_name")]

    operations = [
        migrations.AddField(
            model_name="pipeline",
            name="input_destination",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.RESTRICT,
                related_name="hover_pipeline_inputs",
                to="zerver.stream",
            ),
        ),
        migrations.AddField(
            model_name="pipeline",
            name="input_topic",
            field=models.CharField(blank=True, max_length=60),
        ),
        migrations.AddField(
            model_name="pipeline",
            name="input_availability",
            field=models.TextField(
                choices=[("available", "Available"), ("topic_unavailable", "Topic unavailable")],
                default="available",
            ),
        ),
        migrations.AddField(
            model_name="pipeline",
            name="run_health",
            field=models.TextField(
                choices=[
                    ("not_run", "Not run yet"),
                    ("healthy", "Healthy"),
                    ("failed", "Run failed"),
                ],
                default="not_run",
            ),
        ),
        migrations.AddField(
            model_name="pipeline",
            name="input_cursor_message_id",
            field=models.PositiveBigIntegerField(blank=True, null=True),
        ),
        migrations.RunPython(backfill_topic_inputs, migrations.RunPython.noop),
    ]
