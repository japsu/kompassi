# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0001_initial'),
        ('payments', '0002_paymentseventmeta'),
    ]

    operations = [
        migrations.AddField(
            model_name='payment',
            name='event',
            field=models.ForeignKey(default=1, to='core.Event'),
            preserve_default=False,
        ),
    ]
