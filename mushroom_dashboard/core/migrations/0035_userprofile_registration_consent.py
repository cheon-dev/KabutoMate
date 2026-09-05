from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('core', '0034_structured_philippine_addresses'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='accepted_privacy_policy',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='accepted_terms',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='accepted_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
