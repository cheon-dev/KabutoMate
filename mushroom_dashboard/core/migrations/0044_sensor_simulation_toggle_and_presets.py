from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0043_sensor_simulation_settings'),
    ]

    operations = [
        migrations.AddField(
            model_name='sensorsimulationsettings',
            name='enabled',
            field=models.BooleanField(default=True),
        ),
        migrations.CreateModel(
            name='SensorSimulationPreset',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=50, unique=True)),
                ('temperature_min', models.DecimalField(decimal_places=1, max_digits=4)),
                ('temperature_max', models.DecimalField(decimal_places=1, max_digits=4)),
                ('humidity_min', models.DecimalField(decimal_places=1, max_digits=4)),
                ('humidity_max', models.DecimalField(decimal_places=1, max_digits=4)),
                ('air_quality_min', models.PositiveIntegerField()),
                ('air_quality_max', models.PositiveIntegerField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'ordering': ['name', 'id'],
            },
        ),
    ]
