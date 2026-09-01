from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('core', '0033_customer_addresses_and_order_delivery_snapshot'),
    ]

    operations = [
        migrations.AddField(model_name='userprofile', name='region_code', field=models.CharField(blank=True, max_length=20)),
        migrations.AddField(model_name='userprofile', name='region', field=models.CharField(blank=True, max_length=100)),
        migrations.AddField(model_name='userprofile', name='province_code', field=models.CharField(blank=True, max_length=20)),
        migrations.AddField(model_name='userprofile', name='province', field=models.CharField(blank=True, max_length=100)),
        migrations.AddField(model_name='userprofile', name='city_code', field=models.CharField(blank=True, max_length=20)),
        migrations.AddField(model_name='userprofile', name='barangay_code', field=models.CharField(blank=True, max_length=20)),
        migrations.AddField(model_name='userprofile', name='barangay', field=models.CharField(blank=True, max_length=100)),
        migrations.AddField(model_name='customeraddress', name='region_code', field=models.CharField(blank=True, max_length=20)),
        migrations.AddField(model_name='customeraddress', name='region', field=models.CharField(blank=True, max_length=100)),
        migrations.AddField(model_name='customeraddress', name='province_code', field=models.CharField(blank=True, max_length=20)),
        migrations.AddField(model_name='customeraddress', name='province', field=models.CharField(blank=True, max_length=100)),
        migrations.AddField(model_name='customeraddress', name='city_code', field=models.CharField(blank=True, max_length=20)),
        migrations.AddField(model_name='customeraddress', name='barangay_code', field=models.CharField(blank=True, max_length=20)),
        migrations.AddField(model_name='customeraddress', name='barangay', field=models.CharField(blank=True, max_length=100)),
    ]
