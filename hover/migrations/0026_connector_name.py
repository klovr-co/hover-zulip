from django.db import migrations, models
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps


def populate_connector_names(apps: StateApps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    Connector = apps.get_model("hover", "Connector")
    for connector in Connector.objects.filter(name="").iterator():
        connector.name = connector.provider_name
        connector.save(update_fields=["name"])


class Migration(migrations.Migration):
    dependencies = [("hover", "0025_pipeline_weekday")]

    operations = [
        migrations.AddField(
            model_name="connector",
            name="name",
            field=models.CharField(blank=True, max_length=80),
        ),
        migrations.RunPython(populate_connector_names, migrations.RunPython.noop),
    ]
