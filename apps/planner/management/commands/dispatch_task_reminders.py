from django.core.management.base import BaseCommand, CommandError

from apps.planner.notifications import dispatch_due_task_reminders


class Command(BaseCommand):
    help = "Отправить через FCM все task reminders, время которых наступило."

    def add_arguments(self, parser):
        """Добавляет лимит задач за один запуск команды."""
        parser.add_argument("--limit", type=int, default=500)

    def handle(self, *args, **options):
        """Запускает отправку и выводит итоговую статистику."""
        limit = options["limit"]
        if limit < 1:
            raise CommandError("--limit должен быть >= 1")
        stats = dispatch_due_task_reminders(limit=limit)
        self.stdout.write(
            self.style.SUCCESS(
                "tasks={tasks} sent={sent} failed={failed} skipped={skipped}".format(
                    **stats
                )
            )
        )
