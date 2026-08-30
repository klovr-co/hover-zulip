import uuid

import django.db.models.deletion
import django.db.models.functions.text
from django.db import migrations, models
from django.db.models import Q
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [
        ("hover", "0021_summary_topic_owners"),
        ("zerver", "0798_remove_userprofile_recipient_and_personal_recipients"),
    ]

    operations = [
        migrations.AddField(
            model_name="moduleinstallationtrigger",
            name="anchor_at",
            field=models.DateTimeField(null=True),
        ),
        migrations.AddField(
            model_name="moduleinstallationtrigger",
            name="interval_seconds",
            field=models.PositiveIntegerField(null=True),
        ),
        migrations.AddField(
            model_name="moduleinstallationtrigger",
            name="next_due_at",
            field=models.DateTimeField(null=True),
        ),
        migrations.AddField(
            model_name="moduleinstallationtrigger",
            name="lease_expires_at",
            field=models.DateTimeField(null=True),
        ),
        migrations.CreateModel(
            name="SummaryExecution",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4, editable=False, primary_key=True, serialize=False
                    ),
                ),
                ("kind", models.TextField(choices=[("manual", "Manual"), ("scheduled", "Scheduled")])),
                ("window_start", models.DateTimeField()),
                ("window_end", models.DateTimeField()),
                ("policy_revision", models.PositiveIntegerField()),
                ("policy_hash", models.CharField(max_length=64)),
                (
                    "status",
                    models.TextField(
                        choices=[
                            ("pending", "Pending"),
                            ("dispatched", "Dispatched"),
                            ("succeeded", "Succeeded"),
                            ("no_change", "No change"),
                            ("failed", "Failed"),
                            ("published", "Published"),
                        ],
                        default="pending",
                    ),
                ),
                ("request_hash", models.CharField(default="", max_length=64)),
                ("snapshot_hash", models.CharField(default="", max_length=64)),
                ("result_hash", models.CharField(default="", max_length=64)),
                ("callback_token_hash", models.CharField(default="", max_length=64)),
                ("manual_request_id", models.CharField(blank=True, max_length=64, null=True)),
                ("scheduled_for", models.DateTimeField(blank=True, null=True)),
                ("failure_code", models.CharField(default="", max_length=64)),
                ("result", models.JSONField(default=dict)),
                ("eligible_message_count", models.PositiveIntegerField(default=0)),
                ("snapshot_message_count", models.PositiveSmallIntegerField(default=0)),
                ("date_created", models.DateTimeField(default=django.utils.timezone.now)),
                ("dispatched_at", models.DateTimeField(null=True)),
                ("completed_at", models.DateTimeField(null=True)),
                ("published_at", models.DateTimeField(null=True)),
                (
                    "installation",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.RESTRICT,
                        related_name="summary_executions",
                        to="hover.moduleinstallation",
                    ),
                ),
                (
                    "published_item",
                    models.OneToOneField(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.RESTRICT,
                        related_name="summary_execution",
                        to="hover.generateditem",
                    ),
                ),
                (
                    "requester",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="requested_summary_executions",
                        to="zerver.userprofile",
                    ),
                ),
            ],
            options={"ordering": ["date_created", "id"]},
        ),
        migrations.CreateModel(
            name="SummaryExecutionInput",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("topic_name", models.CharField(max_length=60)),
                ("kind", models.TextField(choices=[("regular", "Regular"), ("source", "Source")])),
                ("provider_name", models.CharField(default="", max_length=60)),
                ("position", models.PositiveSmallIntegerField()),
                (
                    "execution",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="input_snapshots",
                        to="hover.summaryexecution",
                    ),
                ),
                (
                    "source_attachment",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.RESTRICT,
                        to="hover.spaceattachment",
                    ),
                ),
                (
                    "stream",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.RESTRICT, to="zerver.stream"
                    ),
                ),
            ],
            options={"ordering": ["position"]},
        ),
        migrations.CreateModel(
            name="SummaryExecutionMessage",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("frozen_content", models.TextField()),
                ("frozen_rendered_content", models.TextField()),
                ("content_digest", models.CharField(max_length=64)),
                ("sender_label", models.CharField(max_length=100)),
                ("sent_at", models.DateTimeField()),
                ("position", models.PositiveSmallIntegerField()),
                ("citation_token", models.CharField(max_length=32)),
                (
                    "execution",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="message_snapshots",
                        to="hover.summaryexecution",
                    ),
                ),
                (
                    "input",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="message_snapshots",
                        to="hover.summaryexecutioninput",
                    ),
                ),
                (
                    "message",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.RESTRICT,
                        related_name="hover_summary_execution_snapshots",
                        to="zerver.message",
                    ),
                ),
            ],
            options={"ordering": ["position"]},
        ),
        migrations.AddConstraint(
            model_name="summaryexecution",
            constraint=models.CheckConstraint(
                condition=Q(("window_end__gt", models.F("window_start"))),
                name="hover_summary_execution_valid_window",
            ),
        ),
        migrations.AddConstraint(
            model_name="summaryexecution",
            constraint=models.CheckConstraint(
                condition=Q(
                    Q(("kind", "manual"), ("manual_request_id__isnull", False), ("scheduled_for__isnull", True)),
                    Q(("kind", "scheduled"), ("manual_request_id__isnull", True), ("scheduled_for__isnull", False)),
                    _connector="OR",
                ),
                name="hover_summary_execution_identity_matches_kind",
            ),
        ),
        migrations.AddConstraint(
            model_name="summaryexecution",
            constraint=models.UniqueConstraint(
                condition=Q(("kind", "manual"), ("manual_request_id__isnull", False)),
                fields=("installation", "manual_request_id"),
                name="hover_summary_execution_unique_manual_request",
            ),
        ),
        migrations.AddConstraint(
            model_name="summaryexecution",
            constraint=models.UniqueConstraint(
                condition=Q(("kind", "scheduled"), ("scheduled_for__isnull", False)),
                fields=("installation", "scheduled_for"),
                name="hover_summary_execution_unique_occurrence",
            ),
        ),
        migrations.AddConstraint(
            model_name="summaryexecutioninput",
            constraint=models.UniqueConstraint(
                fields=("execution", "position"),
                name="hover_summary_execution_input_unique_position",
            ),
        ),
        migrations.AddConstraint(
            model_name="summaryexecutioninput",
            constraint=models.UniqueConstraint(
                django.db.models.functions.text.Lower("topic_name"),
                models.F("execution"),
                models.F("stream"),
                name="hover_summary_execution_input_unique_topic",
            ),
        ),
        migrations.AddConstraint(
            model_name="summaryexecutioninput",
            constraint=models.CheckConstraint(
                condition=Q(
                    Q(("kind", "source"), ("source_attachment__isnull", False)),
                    Q(("kind", "regular"), ("source_attachment__isnull", True)),
                    _connector="OR",
                ),
                name="hover_summary_execution_input_source_matches_kind",
            ),
        ),
        migrations.AddConstraint(
            model_name="summaryexecutionmessage",
            constraint=models.UniqueConstraint(
                fields=("execution", "position"),
                name="hover_summary_execution_message_unique_position",
            ),
        ),
        migrations.AddConstraint(
            model_name="summaryexecutionmessage",
            constraint=models.UniqueConstraint(
                fields=("execution", "message"),
                name="hover_summary_execution_message_unique_native",
            ),
        ),
        migrations.AddConstraint(
            model_name="summaryexecutionmessage",
            constraint=models.UniqueConstraint(
                fields=("execution", "citation_token"),
                name="hover_summary_execution_message_unique_token",
            ),
        ),
        migrations.AddConstraint(
            model_name="generateditem",
            constraint=models.UniqueConstraint(
                condition=Q(("installation__isnull", False), ("publication_id__isnull", False)),
                fields=("installation", "publication_id"),
                name="hover_generated_item_unique_installation_publication",
            ),
        ),
        migrations.AddConstraint(
            model_name="generateditem",
            constraint=models.UniqueConstraint(
                condition=Q(("idempotency_key__isnull", False), ("installation__isnull", False)),
                fields=("installation", "idempotency_key"),
                name="hover_generated_item_unique_installation_idempotency",
            ),
        ),
    ]
