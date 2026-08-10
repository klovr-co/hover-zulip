import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("zerver", "0808_backfill_can_create_spaces_group")]

    operations = [
        migrations.AlterField(
            model_name="realm",
            name="can_create_spaces_group",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.RESTRICT,
                related_name="+",
                to="zerver.usergroup",
            ),
        )
    ]
