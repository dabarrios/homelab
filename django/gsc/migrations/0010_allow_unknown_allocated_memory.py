from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("gsc", "0009_alter_name_to_world_name")]

    operations = [
        migrations.AlterField(
            model_name="gameserver",
            name="allocated_memory",
            field=models.PositiveSmallIntegerField(
                blank=True,
                db_column="ALLOCATED_MEMORY",
                null=True,
                verbose_name="Allocated Memory (GB)",
            ),
        ),
    ]
