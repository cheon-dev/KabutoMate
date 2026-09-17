from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ('core', '0036_environmentsettings_wifi_credentials'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='environmentsettings',
            name='wifi_credentials_updated_at',
        ),
        migrations.RemoveField(
            model_name='environmentsettings',
            name='wifi_credentials_version',
        ),
        migrations.RemoveField(
            model_name='environmentsettings',
            name='wifi_password_encrypted',
        ),
        migrations.RemoveField(
            model_name='environmentsettings',
            name='wifi_ssid',
        ),
    ]
