# Generated by Django 5.0.4 on 2024-06-09 12:39

from django.db import migrations

import core.csv_export


class Migration(migrations.Migration):
    dependencies = [
        ("tracon2024", "0003_alter_signupextra_shirt_size"),
    ]

    operations = [
        migrations.CreateModel(
            name="SignupExtraAfterpartyProxy",
            fields=[],
            options={
                "proxy": True,
                "indexes": [],
                "constraints": [],
            },
            bases=("tracon2024.signupextra", core.csv_export.CsvExportMixin),
        ),
    ]
