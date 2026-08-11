import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("zerver", "0806_stream_default_push_notifications")]

    operations = [
        migrations.AddField(
            model_name="realm",
            name="hover_enabled",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="realm",
            name="can_create_spaces_group",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.RESTRICT,
                related_name="+",
                to="zerver.usergroup",
            ),
        ),
    ]
