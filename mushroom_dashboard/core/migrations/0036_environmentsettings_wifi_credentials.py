from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('core', '0035_userprofile_registration_consent'),
    ]

    operations = [
        migrations.AddField(
            model_name='environmentsettings',
            name='wifi_credentials_updated_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='environmentsettings',
            name='wifi_credentials_version',
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name='environmentsettings',
            name='wifi_password_encrypted',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AddField(
            model_name='environmentsettings',
            name='wifi_ssid',
            field=models.CharField(blank=True, default='', max_length=32),
        ),
    ]
