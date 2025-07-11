# Generated by Django 5.0.7 on 2025-07-10 10:51

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('iaweb', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='SampleImageVisualizer',
            fields=[
            ],
            options={
                'verbose_name': 'Visualizer',
                'verbose_name_plural': 'Visualizer',
                'proxy': True,
                'indexes': [],
                'constraints': [],
            },
            bases=('iaweb.sampleimage',),
        ),
        migrations.AddField(
            model_name='sampleimage',
            name='is_mosaic',
            field=models.BooleanField(default=False, editable=False),
        ),
    ]
