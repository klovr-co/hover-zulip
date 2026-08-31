import uuid

import django.db.models.deletion
import django.db.models.functions.text
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("hover", "0027_topic_first_pipelines")]

    operations = [
        migrations.RemoveField(model_name="pipeline", name="connector"),
        migrations.AddConstraint(
            model_name="pipeline",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(
                        input_destination__isnull=True,
                        state="draft",
                        input_availability="topic_unavailable",
                    )
                    | models.Q(input_destination__isnull=False) & ~models.Q(input_topic="")
                ),
                name="hover_pipeline_input_recoverable_or_resolved",
            ),
        ),
        migrations.AddIndex(
            model_name="pipeline",
            index=models.Index(
                "input_destination",
                django.db.models.functions.text.Lower("input_topic"),
                name="hover_pipeline_input_topic",
            ),
        ),
        migrations.AddIndex(
            model_name="pipeline",
            index=models.Index(
                "state", "input_availability", "local_time", name="hover_pipeline_schedule"
            ),
        ),
        migrations.CreateModel(
            name="PipelineRun",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4, editable=False, primary_key=True, serialize=False
                    ),
                ),
                ("request_key", models.CharField(max_length=64)),
                ("input_first_message_id", models.PositiveBigIntegerField(blank=True, null=True)),
                ("input_last_message_id", models.PositiveBigIntegerField(blank=True, null=True)),
                (
                    "status",
                    models.TextField(
                        choices=[
                            ("pending", "Pending"),
                            ("succeeded", "Succeeded"),
                            ("failed", "Failed"),
                        ],
                        default="pending",
                    ),
                ),
                ("failure_code", models.CharField(blank=True, max_length=64)),
                ("date_created", models.DateTimeField(default=django.utils.timezone.now)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                (
                    "output_message",
                    models.OneToOneField(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.RESTRICT,
                        related_name="hover_pipeline_run",
                        to="zerver.message",
                    ),
                ),
                (
                    "pipeline",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="runs",
                        to="hover.pipeline",
                    ),
                ),
            ],
            options={
                "constraints": [
                    models.UniqueConstraint(
                        fields=("pipeline", "request_key"), name="hover_pipeline_run_unique_request"
                    )
                ]
            },
        ),
        migrations.CreateModel(
            name="PipelineAuthoredMessage",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("date_created", models.DateTimeField(default=django.utils.timezone.now)),
                (
                    "message",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="hover_pipeline_authorship",
                        to="zerver.message",
                    ),
                ),
                (
                    "pipeline",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="authored_messages",
                        to="hover.pipeline",
                    ),
                ),
                (
                    "run",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="authorship",
                        to="hover.pipelinerun",
                    ),
                ),
            ],
        ),
    ]
