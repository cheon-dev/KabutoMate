from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('core', '0039_alter_productionbatch_yield_kg'),
    ]

    operations = [
        migrations.CreateModel(
            name='WaterRefillStatus',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False)),
                ('device_id', models.CharField(default='ESP32_WATER_REFILL_001', max_length=80)),
                ('container_status', models.CharField(choices=[('NORMAL', 'Normal'), ('LOW', 'Low'), ('UNKNOWN', 'Unknown')], default='UNKNOWN', max_length=10)),
                ('source_status', models.CharField(choices=[('AVAILABLE', 'Available'), ('LOW', 'Low'), ('UNKNOWN', 'Unknown')], default='UNKNOWN', max_length=12)),
                ('refill_state', models.CharField(choices=[('IDLE', 'Idle'), ('REFILLING', 'Refilling'), ('SOURCE_EMPTY', 'Source Empty'), ('TIMEOUT', 'Timeout'), ('SENSOR_ERROR', 'Sensor Error')], default='SENSOR_ERROR', max_length=15)),
                ('pump_on', models.BooleanField(default=False)),
                ('sensor_valid', models.BooleanField(default=False)),
                ('last_error', models.TextField(blank=True, default='')),
                ('last_reported_at', models.DateTimeField(blank=True, null=True)),
                ('last_refill_started_at', models.DateTimeField(blank=True, null=True)),
                ('last_refill_completed_at', models.DateTimeField(blank=True, null=True)),
                ('last_refill_failed_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
        ),
    ]
