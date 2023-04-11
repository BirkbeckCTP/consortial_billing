# -*- coding: utf-8 -*-
# Generated by Django 1.11.23 on 2019-08-23 10:44
from __future__ import unicode_literals

from django.db import migrations

from plugins.consortial_billing import plugin_settings


def upgrade_plugin_version(apps, schema_editor):
    Plugin = apps.get_model('utils', 'Plugin')

    try:
        _plugin = Plugin.objects.get(
            name=plugin_settings.SHORT_NAME,
        )
        _plugin.version = '1.1'
        _plugin.save()
    except BaseException:
        pass


def downgrade_plugin_version(apps, schema_editor):
    Plugin = apps.get_model('utils', 'Plugin')

    try:
        _plugin = Plugin.objects.get(
            name=plugin_settings.SHORT_NAME,
        )
        _plugin.version = '1.0'
        _plugin.save()
    except Plugin.object.DoesNotExist:
        pass


class Migration(migrations.Migration):

    dependencies = [
        ('consortial_billing', '0037_auto_20190823_1144'),
    ]

    operations = [
        migrations.RunPython(
            upgrade_plugin_version,
            reverse_code=downgrade_plugin_version,
        )
    ]