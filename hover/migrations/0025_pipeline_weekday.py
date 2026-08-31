from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("hover", "0024_pipelines")]

    operations = [
        migrations.AddField(
            model_name="pipeline",
            name="weekday",
            field=models.PositiveSmallIntegerField(
                blank=True,
                choices=[
                    (0, "Monday"),
                    (1, "Tuesday"),
                    (2, "Wednesday"),
                    (3, "Thursday"),
                    (4, "Friday"),
                    (5, "Saturday"),
                    (6, "Sunday"),
                ],
                null=True,
            ),
        )
    ]
