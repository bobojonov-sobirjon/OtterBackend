import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("planner", "0004_alter_sound_options_and_more"),
        ("pomodoro", "0001_initial"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.AlterField(
                    model_name="appsettings",
                    name="completion_sound",
                    field=models.ForeignKey(
                        limit_choices_to={"category": "completion", "is_active": True},
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="+",
                        to="pomodoro.sound",
                        verbose_name="Звук завершения",
                    ),
                ),
                migrations.AlterField(
                    model_name="appsettings",
                    name="notification_sound",
                    field=models.ForeignKey(
                        limit_choices_to={"category": "notification", "is_active": True},
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="+",
                        to="pomodoro.sound",
                        verbose_name="Звук уведомления",
                    ),
                ),
                migrations.DeleteModel(name="PomodoroSession"),
                migrations.DeleteModel(name="PomodoroSettings"),
                migrations.DeleteModel(name="Sound"),
            ],
        ),
        migrations.AlterModelOptions(
            name="appsettings",
            options={"verbose_name": "Настройки приложения", "verbose_name_plural": "3. Настройки приложения"},
        ),
        migrations.AlterModelOptions(
            name="helprequest",
            options={"ordering": ("-created_at",), "verbose_name": "Запрос в поддержку", "verbose_name_plural": "4. Запросы в поддержку"},
        ),
        migrations.AlterModelOptions(
            name="legaldocument",
            options={"ordering": ("doc_type",), "verbose_name": "Юридический документ", "verbose_name_plural": "6. Юридические документы"},
        ),
        migrations.AlterModelOptions(
            name="matrixblocksetting",
            options={"verbose_name": "Настройка блока Эйзенхауэра", "verbose_name_plural": "2. Матрица — блоки"},
        ),
        migrations.AlterModelOptions(
            name="premiumfeatureflag",
            options={"ordering": ("key",), "verbose_name": "Флаг премиум функции", "verbose_name_plural": "5. Премиум — функции"},
        ),
        migrations.AlterModelOptions(
            name="task",
            options={"ordering": ("is_completed", "due_at", "-created_at"), "verbose_name": "Задача", "verbose_name_plural": "1. Задачи"},
        ),
    ]
