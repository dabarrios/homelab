from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="LiveSyncState",
            fields=[
                ("id", models.PositiveSmallIntegerField(default=1, editable=False, primary_key=True, serialize=False)),
                ("current_fingerprint", models.TextField(blank=True)),
                ("requested", models.BooleanField(default=False)),
                ("refreshing", models.BooleanField(default=False)),
                ("last_refresh_at", models.DateTimeField(blank=True, null=True)),
                ("last_result", models.JSONField(blank=True, default=dict)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "live sync state",
                "verbose_name_plural": "live sync state",
            },
        ),
    ]
