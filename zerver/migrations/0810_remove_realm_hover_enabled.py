from django.db import migrations


class Migration(migrations.Migration):
    # This migration was added after the already-deployed 0808/0809 chain.
    # Depending on its tip keeps the migration graph linear.
    dependencies = [("zerver", "0809_alter_realm_can_create_spaces_group")]

    operations = [
        migrations.RemoveField(
            model_name="realm",
            name="hover_enabled",
        ),
    ]
