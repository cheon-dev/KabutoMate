from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('core', '0037_remove_environmentsettings_wifi_credentials'),
    ]

    operations = [
        migrations.CreateModel(
            name='YieldTrainingSample',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('sample_code', models.CharField(max_length=100, unique=True)),
                ('start_date', models.DateField()),
                ('harvest_date', models.DateField()),
                ('yield_grams', models.PositiveIntegerField()),
                ('cost', models.DecimalField(blank=True, decimal_places=2, max_digits=7, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('product', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='yield_training_samples', to='core.product')),
            ],
            options={
                'ordering': ['harvest_date', 'start_date', 'id'],
            },
        ),
    ]
