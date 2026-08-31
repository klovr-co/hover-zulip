from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("hover", "0029_pipeline_lifecycle_expand")]

    operations = [
        migrations.AlterField(
            model_name="pipeline",
            name="state",
            field=models.TextField(
                choices=[("active", "Active"), ("draft", "Draft"), ("paused", "Paused")],
                default="active",
            ),
        ),
        migrations.AddConstraint(
            model_name="pipeline",
            constraint=models.CheckConstraint(
                condition=models.Q(state__in=["active", "draft", "paused"]),
                name="hover_pipeline_lifecycle_state_valid",
            ),
        ),
    ]
