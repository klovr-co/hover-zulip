import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("hover", "0007_publication_sync_hardening")]

    operations = [
        migrations.AlterField(
            model_name="spaceattachment",
            name="state",
            field=models.TextField(
                choices=[
                    ("pending_sync", "Pending sync"),
                    ("active", "Active"),
                    ("detached", "Detached with retained history"),
                ],
                default="pending_sync",
            ),
        ),
        migrations.AddField(
            model_name="spaceattachment",
            name="detached_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddConstraint(
            model_name="spaceattachment",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(detached_at__isnull=False, state="detached")
                    | models.Q(
                        detached_at__isnull=True,
                        state__in=["pending_sync", "active"],
                    )
                ),
                name="hover_space_attachment_detachment_matches_state",
            ),
        ),
        migrations.AddField(
            model_name="spaceattachment",
            name="detached_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="hover_space_attachments_detached",
                to="zerver.userprofile",
            ),
        ),
    ]
