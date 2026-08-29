from django.db import migrations, models
import django.db.models.deletion


def copy_profile_addresses(apps, schema_editor):
    UserProfile = apps.get_model('core', 'UserProfile')
    CustomerAddress = apps.get_model('core', 'CustomerAddress')
    for profile in UserProfile.objects.exclude(address='').exclude(role='ADMIN').iterator():
        CustomerAddress.objects.create(
            user_id=profile.user_id,
            label='Home',
            address=profile.address,
            city=profile.city,
            postal_code=profile.postal_code,
            latitude=profile.latitude,
            longitude=profile.longitude,
            is_default=True,
        )


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0032_notification_settings_and_alert_state'),
    ]

    operations = [
        migrations.CreateModel(
            name='CustomerAddress',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('label', models.CharField(max_length=100)),
                ('address', models.TextField()),
                ('city', models.CharField(max_length=100)),
                ('postal_code', models.CharField(max_length=20)),
                ('latitude', models.DecimalField(blank=True, decimal_places=6, max_digits=9, null=True)),
                ('longitude', models.DecimalField(blank=True, decimal_places=6, max_digits=9, null=True)),
                ('is_default', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='delivery_addresses', to='auth.user')),
            ],
            options={
                'ordering': ['-is_default', '-updated_at'],
            },
        ),
        migrations.AddField(
            model_name='order',
            name='delivery_distance_km',
            field=models.DecimalField(blank=True, decimal_places=1, max_digits=8, null=True),
        ),
        migrations.AddField(
            model_name='order',
            name='shipping_fee',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=10),
        ),
        migrations.RunPython(copy_profile_addresses, migrations.RunPython.noop),
    ]
