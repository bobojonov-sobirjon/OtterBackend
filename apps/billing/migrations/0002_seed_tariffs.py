from decimal import Decimal

from django.db import migrations


def seed_tariffs(apps, schema_editor):
    Tariff = apps.get_model("billing", "Tariff")
    defaults = [
        {
            "code": "monthly",
            "title": "Месячная подписка",
            "description": "Премиум на 30 дней. Промо-период настраивается на стороне Otter.",
            "price": Decimal("299.00"),
            "currency": "RUB",
            "duration_days": 30,
            "promo_days": 7,
            "is_recurring": True,
            "receipt_name": "Подписка Otter Premium (месяц)",
            "sort_order": 1,
        },
        {
            "code": "yearly",
            "title": "Годовая подписка",
            "description": "Премиум на 365 дней.",
            "price": Decimal("2490.00"),
            "currency": "RUB",
            "duration_days": 365,
            "promo_days": 7,
            "is_recurring": True,
            "receipt_name": "Подписка Otter Premium (год)",
            "sort_order": 2,
        },
        {
            "code": "lifetime",
            "title": "Навсегда",
            "description": "Разовый платёж без автопродления.",
            "price": Decimal("4990.00"),
            "currency": "RUB",
            "duration_days": 0,
            "promo_days": 0,
            "is_recurring": False,
            "receipt_name": "Otter Premium (бессрочно)",
            "sort_order": 3,
        },
    ]
    for item in defaults:
        Tariff.objects.update_or_create(code=item["code"], defaults=item)


def unseed_tariffs(apps, schema_editor):
    Tariff = apps.get_model("billing", "Tariff")
    Tariff.objects.filter(code__in=["monthly", "yearly", "lifetime"]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("billing", "0001_billing_and_premium_until"),
    ]

    operations = [
        migrations.RunPython(seed_tariffs, unseed_tariffs),
    ]
