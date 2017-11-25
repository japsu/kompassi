# -*- coding: utf-8 -*-
# Generated by Django 1.10.8 on 2017-11-13 19:58
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('programme', '0059_room_remove_venue'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='room',
            options={'ordering': ['event', 'order'], 'verbose_name': 'Room', 'verbose_name_plural': 'Rooms'},
        ),
        migrations.AlterField(
            model_name='room',
            name='event',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='rooms', to='core.Event'),
        ),
    ]