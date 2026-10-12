from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('core', '0038_yieldtrainingsample'),
    ]

    operations = [
        migrations.AlterField(
            model_name='productionbatch',
            name='yield_kg',
            field=models.DecimalField(blank=True, decimal_places=3, max_digits=5, null=True),
        ),
    ]
