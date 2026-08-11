import django.db.models.deletion
from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):
    dependencies = [("hover", "0015_personal_editions")]

    operations = [
        migrations.AddField(
            model_name="spaceattachment",
            name="evidence_deleted_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="spaceattachment",
            name="evidence_deleted_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="hover_space_attachment_evidence_deleted",
                to="zerver.userprofile",
            ),
        ),
        migrations.AddConstraint(
            model_name="spaceattachment",
            constraint=models.CheckConstraint(
                condition=(
                    Q(evidence_deleted_at__isnull=True, evidence_deleted_by__isnull=True)
                    | Q(state="detached", evidence_deleted_at__isnull=False)
                ),
                name="hover_attachment_evidence_deletion_requires_detachment",
            ),
        ),
    ]
