from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [("hover", "0023_connectors")]

    operations = [
        migrations.CreateModel(
            name="Pipeline",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=80)),
                ("instruction", models.TextField(max_length=2000)),
                ("cadence", models.TextField(choices=[("daily", "Every day"), ("weekdays", "Weekdays"), ("weekly", "Every week")], default="daily")),
                ("local_time", models.TimeField()),
                ("timezone", models.CharField(max_length=64)),
                ("output_topic", models.CharField(max_length=60)),
                ("state", models.TextField(choices=[("active", "Active"), ("draft", "Draft"), ("needs_attention", "Needs attention")], default="active")),
                ("last_run_at", models.DateTimeField(blank=True, null=True)),
                ("date_created", models.DateTimeField(default=django.utils.timezone.now)),
                ("date_updated", models.DateTimeField(auto_now=True)),
                ("connector", models.OneToOneField(on_delete=django.db.models.deletion.RESTRICT, related_name="pipeline", to="hover.connector")),
                ("created_by", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="created_hover_pipelines", to="zerver.userprofile")),
                ("output_destination", models.ForeignKey(on_delete=django.db.models.deletion.RESTRICT, related_name="hover_pipeline_outputs", to="zerver.stream")),
                ("realm", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="hover_pipelines", to="zerver.realm")),
            ],
        ),
    ]
