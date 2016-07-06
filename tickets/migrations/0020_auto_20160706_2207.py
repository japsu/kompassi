# -*- coding: utf-8 -*-
# Generated by Django 1.9.5 on 2016-07-06 19:07
from __future__ import unicode_literals

import core.utils.model_utils
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tickets', '0019_auto_20160704_2222'),
    ]

    operations = [
        migrations.AlterField(
            model_name='accommodationinformation',
            name='phone_number',
            field=models.CharField(blank=True, default='', max_length=30, validators=[core.utils.model_utils.phone_number_validator], verbose_name='Puhelinnumero'),
        ),
    ]
