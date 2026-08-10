import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models
from django.db.models import Q
from django.db.models.functions import Lower


class Migration(migrations.Migration):
    dependencies = [
        ("hover", "0001_initial"),
        ("zerver", "0809_alter_realm_can_create_spaces_group"),
    ]

    operations = [
        migrations.CreateModel(
            name="Space",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("name", models.CharField(max_length=60)),
                ("description", models.CharField(default="", max_length=1024)),
                (
                    "state",
                    models.TextField(
                        choices=[("setup", "Setup"), ("launched", "Launched")],
                        default="setup",
                    ),
                ),
                ("date_created", models.DateTimeField(default=django.utils.timezone.now)),
                ("date_updated", models.DateTimeField(auto_now=True)),
                (
                    "category",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.RESTRICT,
                        related_name="hover_spaces",
                        to="zerver.channelfolder",
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="created_hover_spaces",
                        to="zerver.userprofile",
                    ),
                ),
                (
                    "realm",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, to="zerver.realm"
                    ),
                ),
                (
                    "stream",
                    models.OneToOneField(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.RESTRICT,
                        related_name="hover_space",
                        to="zerver.stream",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="SpaceAdministrator",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("date_created", models.DateTimeField(default=django.utils.timezone.now)),
                (
                    "added_by",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="hover_space_administrator_assignments_added",
                        to="zerver.userprofile",
                    ),
                ),
                (
                    "realm",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, to="zerver.realm"
                    ),
                ),
                (
                    "space",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="administrator_assignments",
                        to="hover.space",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="hover_space_administrator_assignments",
                        to="zerver.userprofile",
                    ),
                ),
            ],
        ),
        migrations.AddConstraint(
            model_name="space",
            constraint=models.UniqueConstraint(
                Lower("name"), "realm", name="hover_space_unique_name_in_realm"
            ),
        ),
        migrations.AddConstraint(
            model_name="space",
            constraint=models.CheckConstraint(
                condition=(
                    Q(("state", "setup"), ("stream__isnull", True))
                    | Q(("state", "launched"), ("stream__isnull", False))
                ),
                name="hover_space_state_requires_stream",
            ),
        ),
        migrations.AddConstraint(
            model_name="spaceadministrator",
            constraint=models.UniqueConstraint(
                fields=("space", "user"), name="hover_space_administrator_unique_user"
            ),
        ),
    ]
