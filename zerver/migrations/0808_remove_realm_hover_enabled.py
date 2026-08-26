from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("zerver", "0807_realm_hover_settings")]

    operations = [
        migrations.RemoveField(
            model_name="realm",
            name="hover_enabled",
        ),
    ]
