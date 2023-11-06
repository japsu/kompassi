# Generated by Django 1.9.1 on 2016-01-31 22:50


import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("programme", "0020_make_role_event_specific"),
    ]

    operations = [
        migrations.AlterField(
            model_name="role",
            name="personnel_class",
            field=models.ForeignKey(
                help_text="The personnel class for the programme hosts that have this role.",
                on_delete=django.db.models.deletion.CASCADE,
                to="labour.PersonnelClass",
                verbose_name="Personnel class",
            ),
        ),
    ]