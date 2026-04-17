from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('runs', '0003_run_pause_requested'),
    ]

    operations = [
        migrations.AddField(
            model_name='run',
            name='interrupt_metadata',
            field=models.JSONField(blank=True, default=None, null=True),
        ),
    ]
