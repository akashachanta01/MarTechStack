from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('jobs', '0012_certificationguide'),
    ]

    operations = [
        migrations.AddField(
            model_name='job',
            name='went_live_at',
            field=models.DateTimeField(blank=True, db_index=True, null=True),
        ),
        migrations.AddField(
            model_name='job',
            name='digest_sent',
            field=models.BooleanField(default=False, db_index=True),
        ),
    ]
