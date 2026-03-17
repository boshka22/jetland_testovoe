"""Обновляет help_text поля discount_percent. Схема БД не меняется."""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("orders", "0001_initial")]

    operations = [
        migrations.AlterField(
            model_name="promocode",
            name="discount_percent",
            field=models.DecimalField(
                decimal_places=4,
                max_digits=6,
                help_text="Скидка в виде десятичной доли: 0.10 = 10%, 0.15 = 15%.",
            ),
        ),
    ]
