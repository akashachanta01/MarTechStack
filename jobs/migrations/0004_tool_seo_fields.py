from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('jobs', '0003_zero_noise_screening'),
    ]

    operations = [
        migrations.AddField(
            model_name='tool',
            name='description',
            field=models.TextField(blank=True, default='', help_text='SEO Content: What is this tool?'),
        ),
        migrations.AddField(
            model_name='tool',
            name='logo_url',
            field=models.URLField(blank=True, help_text='Official logo of the tool', max_length=500, null=True),
        ),
    ]
