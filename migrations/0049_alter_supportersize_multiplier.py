# Generated by Django 3.2.18 on 2024-01-30 13:20

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('consortial_billing', '0048_supportlevel_default'),
    ]

    operations = [
        migrations.AlterField(
            model_name='supportersize',
            name='multiplier',
            field=models.DecimalField(
                decimal_places=2,
                default=1,
                help_text='Usually a decimal number between 0.00 and 5.00. '
                          'The base rate is multiplied by this number '
                          'as part of the support fee calculation.',
                max_digits=3
            ),
        ),
    ]
