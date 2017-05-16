# -*- coding: utf-8 -*-
# Generated by Django 1.9.13 on 2017-05-16 23:07
from __future__ import unicode_literals

import django.core.files.storage
from django.db import migrations, models
import plugins.consortial_billing.models


class Migration(migrations.Migration):

    dependencies = [
        ('consortial_billing', '0020_option_all'),
    ]

    operations = [
        migrations.AddField(
            model_name='poll',
            name='file',
            field=models.FileField(blank=True, null=True, storage=django.core.files.storage.FileSystemStorage(location='/home/ajrbyers/Code/acta/src/media'), upload_to=plugins.consortial_billing.models.file_upload_path),
        ),
    ]
