import django.core.validators
import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("hover", "0002_space_setup"),
        ("zerver", "0809_alter_realm_can_create_spaces_group"),
    ]

    operations = [
        migrations.CreateModel(
            name="ConnectedAccount",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
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
                ("provider_name", models.CharField(max_length=60)),
                ("external_account_id", models.UUIDField()),
                ("display_name", models.CharField(max_length=100)),
                (
                    "approval_state",
                    models.TextField(
                        choices=[
                            ("pending", "Pending approval"),
                            ("approved", "Approved"),
                            ("revoked", "Revoked"),
                        ],
                        default="pending",
                    ),
                ),
                (
                    "health_status",
                    models.TextField(
                        choices=[
                            ("unknown", "Unknown"),
                            ("healthy", "Healthy"),
                            ("degraded", "Degraded"),
                            ("unavailable", "Unavailable"),
                        ],
                        default="unknown",
                    ),
                ),
                ("health_checked_at", models.DateTimeField(blank=True, null=True)),
                ("date_created", models.DateTimeField(default=django.utils.timezone.now)),
                ("date_updated", models.DateTimeField(auto_now=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="created_hover_connected_accounts",
                        to="zerver.userprofile",
                    ),
                ),
                (
                    "owner",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="owned_hover_connected_accounts",
                        to="zerver.userprofile",
                    ),
                ),
                (
                    "realm",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="hover_connected_accounts",
                        to="zerver.realm",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="ConnectedAccountGrant",
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
                        choices=[("active", "Active"), ("revoked", "Revoked")],
                        default="active",
                    ),
                ),
                ("all_selectors", models.BooleanField(default=False)),
                ("date_created", models.DateTimeField(default=django.utils.timezone.now)),
                ("date_updated", models.DateTimeField(auto_now=True)),
                (
                    "account",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="grants",
                        to="hover.connectedaccount",
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="created_hover_connected_account_grants",
                        to="zerver.userprofile",
                    ),
                ),
                (
                    "realm",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="hover_connected_account_grants",
                        to="zerver.realm",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="hover_connected_account_grants",
                        to="zerver.userprofile",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="ConnectedAccountGrantSelector",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                (
                    "selector_type",
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
                    "source_ref",
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
                (
                    "grant",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="selectors",
                        to="hover.connectedaccountgrant",
                    ),
                ),
                (
                    "realm",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, to="zerver.realm"
                    ),
                ),
            ],
        ),
        migrations.AddConstraint(
            model_name="connectedaccount",
            constraint=models.UniqueConstraint(
                fields=("realm", "provider_key", "external_account_id"),
                name="hover_connected_account_unique_external_id",
            ),
        ),
        migrations.AddConstraint(
            model_name="connectedaccountgrant",
            constraint=models.UniqueConstraint(
                fields=("account", "user"),
                name="hover_connected_account_grant_unique_user",
            ),
        ),
        migrations.AddConstraint(
            model_name="connectedaccountgrantselector",
            constraint=models.UniqueConstraint(
                fields=("grant", "selector_type", "source_ref"),
                name="hover_connected_account_grant_unique_selector",
            ),
        ),
    ]
