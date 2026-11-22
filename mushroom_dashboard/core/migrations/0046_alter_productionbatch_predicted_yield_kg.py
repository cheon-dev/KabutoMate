from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0045_product_is_archived'),
    ]

    operations = [
        migrations.AlterField(
            model_name='productionbatch',
            name='predicted_yield_kg',
            field=models.DecimalField(blank=True, decimal_places=4, help_text='ML predicted yield', max_digits=8, null=True),
        ),
    ]
