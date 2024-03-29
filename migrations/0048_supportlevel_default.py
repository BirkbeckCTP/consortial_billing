# Generated by Django 3.2.18 on 2023-10-19 06:12

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('consortial_billing', '0047_remove_is_consortium_20231012_1548'),
    ]

    operations = [
        migrations.AddField(
            model_name='supportlevel',
            name='default',
            field=models.BooleanField(default=False, help_text='Designates this level as the standard level, set apart from higher levels. If checked, institution size will be factored in to fees on this level. If unchecked, institution size will not matter.'),
        ),
    ]
