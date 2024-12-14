# Generated by Django 5.0.10 on 2024-12-12 18:49

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("tickets", "0043_remove_product_requires_accommodation_information_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="order",
            name="language",
            field=models.CharField(
                blank=True,
                choices=[("en", "English"), ("fi", "Finnish"), ("sv", "Swedish")],
                default="en",
                max_length=2,
                verbose_name="Kieli",
            ),
        ),
    ]
