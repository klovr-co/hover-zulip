import django.core.validators
import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):
    dependencies = [
        ("hover", "0003_connected_accounts"),
        ("zerver", "0809_alter_realm_can_create_spaces_group"),
    ]

    operations = [
        migrations.CreateModel(
            name="Source",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("adapter_key", models.CharField(max_length=32)),
                (
                    "provider_key",
                    models.CharField(
                        max_length=32,
                        validators=[
                            django.core.validators.RegexValidator(
                                message="Provider keys must start with a letter and contain only lowercase letters, digits, and underscores.",
                                regex="^[a-z][a-z0-9_]{0,31}$",
                            )
                        ],
                    ),
                ),
                (
                    "source_type",
                    models.CharField(
                        max_length=64,
                        validators=[
                            django.core.validators.RegexValidator(
                                message="Selector types must start with a letter and contain only lowercase letters, digits, and underscores.",
                                regex="^[a-z][a-z0-9_]{0,63}$",
                            )
                        ],
                    ),
                ),
                (
                    "external_ref",
                    models.CharField(
                        max_length=36,
                        validators=[
                            django.core.validators.RegexValidator(
                                message="Source references must be opaque Studio source IDs.",
                                regex="^src_[0-9a-f]{32}$",
                            )
                        ],
                    ),
                ),
                ("display_name", models.CharField(max_length=100)),
                ("date_created", models.DateTimeField(default=django.utils.timezone.now)),
                ("date_updated", models.DateTimeField(auto_now=True)),
                (
                    "account",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.RESTRICT,
                        related_name="sources",
                        to="hover.connectedaccount",
                    ),
                ),
                (
                    "realm",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="hover_sources",
                        to="zerver.realm",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="SpaceAttachment",
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
                        choices=[("pending_sync", "Pending sync"), ("active", "Active")],
                        default="pending_sync",
                    ),
                ),
                (
                    "history_window",
                    models.TextField(
                        choices=[
                            ("today", "Today"),
                            ("last_30_days", "Last 30 days"),
                            ("custom", "Custom start date"),
                        ]
                    ),
                ),
                ("history_timezone", models.CharField(max_length=64)),
                ("history_start_at", models.DateTimeField()),
                ("custom_start_date", models.DateField(null=True)),
                ("date_created", models.DateTimeField(default=django.utils.timezone.now)),
                ("date_updated", models.DateTimeField(auto_now=True)),
                (
                    "attached_by",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="hover_space_attachments_added",
                        to="zerver.userprofile",
                    ),
                ),
                (
                    "realm",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="hover_space_attachments",
                        to="zerver.realm",
                    ),
                ),
                (
                    "source",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.RESTRICT,
                        related_name="space_attachments",
                        to="hover.source",
                    ),
                ),
                (
                    "space",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="attachments",
                        to="hover.space",
                    ),
                ),
            ],
        ),
        migrations.AddConstraint(
            model_name="source",
            constraint=models.UniqueConstraint(
                fields=("account", "external_ref"),
                name="hover_source_unique_account_external_ref",
            ),
        ),
        migrations.AddConstraint(
            model_name="spaceattachment",
            constraint=models.UniqueConstraint(
                fields=("space", "source"), name="hover_space_attachment_unique_source"
            ),
        ),
        migrations.AddConstraint(
            model_name="spaceattachment",
            constraint=models.CheckConstraint(
                condition=(
                    Q(("custom_start_date__isnull", False), ("history_window", "custom"))
                    | Q(
                        ("custom_start_date__isnull", True),
                        ("history_window__in", ["today", "last_30_days"]),
                    )
                ),
                name="hover_space_attachment_custom_date_matches_window",
            ),
        ),
    ]
