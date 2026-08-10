import django.db.models.deletion
from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):
    dependencies = [
        ("hover", "0004_source_attachments"),
        ("zerver", "0809_alter_realm_can_create_spaces_group"),
    ]

    operations = [
        migrations.AddField(
            model_name="spaceattachment",
            name="publication_cursor",
            field=models.TextField(default=""),
        ),
        migrations.AddField(
            model_name="spaceattachment",
            name="last_publication_sync_at",
            field=models.DateTimeField(null=True),
        ),
        migrations.AddField(
            model_name="spaceattachment",
            name="last_publication_sync_error",
            field=models.CharField(default="", max_length=64),
        ),
        migrations.AddField(
            model_name="spaceattachment",
            name="publication_sync_failures",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="generateditem",
            name="attachment",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.RESTRICT,
                related_name="generated_items",
                to="hover.spaceattachment",
            ),
        ),
        migrations.AddField(
            model_name="generateditem",
            name="publication_id",
            field=models.TextField(null=True, unique=True),
        ),
        migrations.AddField(
            model_name="generateditem",
            name="idempotency_key",
            field=models.TextField(null=True),
        ),
        migrations.AddField(
            model_name="generateditem",
            name="business_identity",
            field=models.TextField(default=""),
        ),
        migrations.AddField(
            model_name="generateditem",
            name="payload",
            field=models.JSONField(default=dict),
        ),
        migrations.AddField(
            model_name="generateditem",
            name="importance",
            field=models.TextField(
                choices=[
                    ("low", "Low"),
                    ("normal", "Normal"),
                    ("high", "High"),
                    ("urgent", "Urgent"),
                ],
                default="normal",
            ),
        ),
        migrations.AddField(
            model_name="generateditem",
            name="run_reference",
            field=models.TextField(default=""),
        ),
        migrations.AddField(
            model_name="generateditem",
            name="covered_start_at",
            field=models.DateTimeField(null=True),
        ),
        migrations.AddField(
            model_name="generateditem",
            name="covered_end_at",
            field=models.DateTimeField(null=True),
        ),
        migrations.AddField(
            model_name="generateditem",
            name="occurred_at",
            field=models.DateTimeField(null=True),
        ),
        migrations.AddField(
            model_name="generateditem",
            name="generated_at",
            field=models.DateTimeField(null=True),
        ),
        migrations.AddField(
            model_name="generateditem",
            name="published_at",
            field=models.DateTimeField(null=True),
        ),
        migrations.AddField(
            model_name="generateditem",
            name="lineage_key",
            field=models.TextField(null=True),
        ),
        migrations.AddField(
            model_name="generateditem",
            name="parent_publication_id",
            field=models.TextField(null=True),
        ),
        migrations.AddField(
            model_name="generateditem",
            name="material_change",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="evidencelink",
            name="source",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.RESTRICT,
                related_name="evidence_links",
                to="hover.source",
            ),
        ),
        migrations.AddField(
            model_name="evidencelink",
            name="evidence_ref",
            field=models.TextField(default=""),
        ),
        migrations.AddConstraint(
            model_name="evidencelink",
            constraint=models.UniqueConstraint(
                fields=("generated_item", "evidence_ref"),
                condition=~Q(evidence_ref=""),
                name="hover_evidence_link_unique_ref",
            ),
        ),
    ]
