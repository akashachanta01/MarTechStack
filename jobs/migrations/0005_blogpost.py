from django.db import migrations, models
import django.utils.timezone

class Migration(migrations.Migration):

    dependencies = [
        ('jobs', '0004_tool_seo_fields'),
    ]

    operations = [
        migrations.CreateModel(
            name='BlogPost',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=255)),
                ('slug', models.SlugField(help_text='URL friendly version of title', max_length=255, unique=True)),
                ('excerpt', models.TextField(help_text='Short summary for the blog card (2-3 sentences).')),
                ('content', models.TextField(help_text='Full HTML content of the article.')),
                ('meta_title', models.CharField(blank=True, max_length=255)),
                ('meta_description', models.CharField(blank=True, max_length=300)),
                ('author', models.CharField(default='MarTechJobs Team', max_length=100)),
                ('category', models.CharField(default='Career Advice', max_length=50)),
                ('read_time', models.CharField(default='5 min read', max_length=20)),
                ('published_at', models.DateField(default=django.utils.timezone.now)),
                ('is_published', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'ordering': ['-published_at'],
            },
        ),
    ]
