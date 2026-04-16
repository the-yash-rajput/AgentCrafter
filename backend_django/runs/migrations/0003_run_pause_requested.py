from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('runs', '0002_run_checkpoint_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='run',
            name='pause_requested',
            field=models.BooleanField(default=False),
        ),
    ]
