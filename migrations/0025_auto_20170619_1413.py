# -*- coding: utf-8 -*-
# Generated by Django 1.9.13 on 2017-06-19 14:13
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('consortial_billing', '0024_auto_20170607_1349'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='institution',
            options={'ordering': ('country', 'name')},
        ),
        migrations.AlterField(
            model_name='institution',
            name='banding',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='consortial_billing.Banding'),
        ),
        migrations.AlterField(
            model_name='institution',
            name='billing_agent',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='consortial_billing.BillingAgent'),
        ),
        migrations.AlterField(
            model_name='institution',
            name='consortium',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='consortial_billing.Institution'),
        ),
    ]
