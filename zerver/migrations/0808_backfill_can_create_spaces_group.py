from django.db import migrations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps


def backfill_can_create_spaces_group(
    apps: StateApps, schema_editor: BaseDatabaseSchemaEditor
) -> None:
    Realm = apps.get_model("zerver", "Realm")
    NamedUserGroup = apps.get_model("zerver", "NamedUserGroup")

    for realm in Realm.objects.filter(can_create_spaces_group=None).iterator():
        realm.can_create_spaces_group = NamedUserGroup.objects.get(
            realm=realm, name="role:administrators", is_system_group=True
        )
        realm.save(update_fields=["can_create_spaces_group"])


class Migration(migrations.Migration):
    atomic = False

    dependencies = [("zerver", "0807_realm_hover_settings")]

    operations = [
        migrations.RunPython(
            backfill_can_create_spaces_group,
            reverse_code=migrations.RunPython.noop,
            elidable=True,
        )
    ]
