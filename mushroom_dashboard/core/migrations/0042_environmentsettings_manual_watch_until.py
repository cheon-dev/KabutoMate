from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0041_waterrefilllog'),
    ]

    operations = [
        migrations.AddField(
            model_name='environmentsettings',
            name='manual_watch_until',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
