from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0031_manual_gcash_qr_payment'),
    ]

    operations = [
        migrations.CreateModel(
            name='NotificationSettings',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False)),
                ('email_enabled', models.BooleanField(default=True, help_text='Enable or disable email notifications')),
                ('recipient_emails', models.TextField(blank=True, default='', help_text='Comma-separated recipient email addresses')),
                ('alert_cooldown_minutes', models.PositiveIntegerField(default=60, help_text='Cooldown in minutes for repeated environmental alerts')),
                ('recovery_email_enabled', models.BooleanField(default=True, help_text='Send recovery emails when conditions return to normal')),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.CreateModel(
            name='NotificationLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('notification_type', models.CharField(help_text='Notification type, such as environmental_alert or order_confirmation', max_length=80)),
                ('recipient', models.EmailField(blank=True, default='', max_length=254, help_text='Primary recipient for the notification')),
                ('subject', models.CharField(max_length=255)),
                ('channel', models.CharField(choices=[('email', 'Email'), ('sms', 'SMS'), ('push', 'Push')], default='email', max_length=20)),
                ('status', models.CharField(choices=[('SUCCESS', 'Success'), ('FAILED', 'Failed')], default='SUCCESS', max_length=10)),
                ('sent_at', models.DateTimeField(auto_now_add=True)),
                ('error_message', models.TextField(blank=True, default='')),
                ('metadata', models.JSONField(blank=True, default=dict)),
            ],
            options={
                'ordering': ['-sent_at'],
            },
        ),
        migrations.CreateModel(
            name='EnvironmentalAlertState',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('alert_key', models.CharField(max_length=80, unique=True)),
                ('alert_name', models.CharField(max_length=120)),
                ('is_active', models.BooleanField(default=False)),
                ('last_alert_sent_at', models.DateTimeField(blank=True, null=True)),
                ('last_recovery_sent_at', models.DateTimeField(blank=True, null=True)),
                ('last_observed_value', models.JSONField(blank=True, default=dict)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
        ),
    ]
