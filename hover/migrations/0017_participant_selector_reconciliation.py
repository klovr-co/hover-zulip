import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("hover", "0016_source_evidence_deletion")]

    operations = [
        migrations.CreateModel(
            name="ParticipantSelectorReconciliation",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                (
                    "state",
                    models.TextField(
                        choices=[
                            ("pending", "Pending"),
                            ("leased", "Leased"),
                            ("backoff", "Backoff"),
                            ("current", "Current"),
                        ],
                        default="pending",
                    ),
                ),
                ("generation", models.PositiveBigIntegerField(default=1)),
                ("attempts", models.PositiveIntegerField(default=0)),
                ("next_attempt_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("last_error_code", models.CharField(blank=True, max_length=64)),
                ("last_reconciled_at", models.DateTimeField(blank=True, null=True)),
                ("date_created", models.DateTimeField(default=django.utils.timezone.now)),
                ("date_updated", models.DateTimeField(auto_now=True)),
                (
                    "account",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="participant_selector_reconciliation",
                        to="hover.connectedaccount",
                    ),
                ),
                ("lease_token", models.UUIDField(blank=True, null=True)),
                ("lease_expires_at", models.DateTimeField(blank=True, null=True)),
                (
                    "realm",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, to="zerver.realm"
                    ),
                ),
            ],
            options={
                "indexes": [
                    models.Index(
                        fields=["state", "next_attempt_at"], name="hover_participant_reconcile_due"
                    ),
                    models.Index(
                        fields=["state", "lease_expires_at"],
                        name="hover_participant_lease_due",
                    ),
                ],
            },
        ),
    ]
