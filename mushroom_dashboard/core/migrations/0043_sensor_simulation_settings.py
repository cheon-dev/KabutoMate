from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0042_environmentsettings_manual_watch_until'),
    ]

    operations = [
        migrations.CreateModel(
            name='SensorSimulationSettings',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('temperature_min', models.DecimalField(decimal_places=1, default=20.0, max_digits=4)),
                ('temperature_max', models.DecimalField(decimal_places=1, default=24.0, max_digits=4)),
                ('humidity_min', models.DecimalField(decimal_places=1, default=80.0, max_digits=4)),
                ('humidity_max', models.DecimalField(decimal_places=1, default=90.0, max_digits=4)),
                ('air_quality_min', models.PositiveIntegerField(default=250)),
                ('air_quality_max', models.PositiveIntegerField(default=390)),
            ],
        ),
    ]
