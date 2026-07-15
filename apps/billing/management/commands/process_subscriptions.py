from django.core.management.base import BaseCommand

from apps.billing.services import refresh_expired_subscriptions


class Command(BaseCommand):
    help = (
        "Обрабатывает истечение промо/премиума и инициирует recurring-списания. "
        "Запускайте по cron (например каждый час)."
    )

    def handle(self, *args, **options):
        stats = refresh_expired_subscriptions()
        self.stdout.write(self.style.SUCCESS(f"Done: {stats}"))
