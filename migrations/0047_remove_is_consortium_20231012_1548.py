# Generated by Django 3.2.18 on 2023-10-12 14:48

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('consortial_billing', '0046_currency_symbol'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='supportersize',
            options={'ordering': ('-multiplier',)},
        ),
        migrations.RemoveField(
            model_name='supportersize',
            name='is_consortium',
        ),
    ]
