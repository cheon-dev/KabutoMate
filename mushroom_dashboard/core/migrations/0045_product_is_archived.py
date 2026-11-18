from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0044_sensor_simulation_toggle_and_presets'),
    ]

    operations = [
        migrations.AddField(
            model_name='product',
            name='is_archived',
            field=models.BooleanField(default=False, help_text='Archived - hidden from inventory, shop and POS but kept for sales history'),
        ),
    ]
