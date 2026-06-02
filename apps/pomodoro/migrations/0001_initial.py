import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("planner", "0004_alter_sound_options_and_more"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.CreateModel(
                    name="Sound",
                    fields=[
                        ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                        ("key", models.CharField(max_length=50, verbose_name="Ключ")),
                        (
                            "category",
                            models.CharField(
                                choices=[
                                    ("timer_end", "Звук завершения таймера"),
                                    ("work_background", "Фоновый звук"),
                                    ("notification", "Звук уведомления"),
                                    ("completion", "Звук завершения задачи"),
                                ],
                                max_length=30,
                                verbose_name="Категория",
                            ),
                        ),
                        ("title", models.CharField(max_length=120, verbose_name="Название")),
                        ("emoji", models.CharField(blank=True, default="", max_length=16, verbose_name="Emoji")),
                        ("audio_file", models.FileField(blank=True, null=True, upload_to="sounds/", verbose_name="Аудиофайл")),
                        ("sort_order", models.PositiveIntegerField(default=0, verbose_name="Порядок")),
                        ("is_active", models.BooleanField(default=True, verbose_name="Активен")),
                    ],
                    options={
                        "verbose_name": "Аудиофайл",
                        "verbose_name_plural": "1. Аудио — все звуки",
                        "db_table": "planner_sound",
                        "ordering": ("category", "sort_order", "key"),
                    },
                ),
                migrations.CreateModel(
                    name="PomodoroSettings",
                    fields=[
                        ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                        ("duration_minutes", models.PositiveIntegerField(default=30, verbose_name="Длительность таймера")),
                        ("short_break_minutes", models.PositiveIntegerField(default=5, verbose_name="Короткий перерыв")),
                        ("show_on_lock_screen", models.BooleanField(default=True, verbose_name="Показывать на экране блокировки")),
                        (
                            "timer_end_sound",
                            models.ForeignKey(
                                limit_choices_to={"category": "timer_end", "is_active": True},
                                on_delete=django.db.models.deletion.PROTECT,
                                related_name="+",
                                to="pomodoro.sound",
                                verbose_name="Звук завершения таймера",
                            ),
                        ),
                        (
                            "work_sound",
                            models.ForeignKey(
                                limit_choices_to={"category": "work_background", "is_active": True},
                                on_delete=django.db.models.deletion.PROTECT,
                                related_name="+",
                                to="pomodoro.sound",
                                verbose_name="Фоновая мелодия",
                            ),
                        ),
                        (
                            "user",
                            models.OneToOneField(
                                on_delete=django.db.models.deletion.CASCADE,
                                related_name="pomodoro_settings",
                                to=settings.AUTH_USER_MODEL,
                                verbose_name="Пользователь",
                            ),
                        ),
                    ],
                    options={
                        "verbose_name": "Настройки пользователя",
                        "verbose_name_plural": "2. Настройки пользователей",
                        "db_table": "planner_pomodorosettings",
                    },
                ),
                migrations.CreateModel(
                    name="PomodoroSession",
                    fields=[
                        ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                        ("duration_minutes", models.PositiveIntegerField(default=30, verbose_name="Длительность")),
                        (
                            "state",
                            models.CharField(
                                choices=[
                                    ("idle", "Ожидание"),
                                    ("running", "Запущен"),
                                    ("paused", "На паузе"),
                                    ("stopped", "Остановлен"),
                                    ("completed", "Завершен"),
                                ],
                                default="idle",
                                max_length=20,
                                verbose_name="Состояние",
                            ),
                        ),
                        ("started_at", models.DateTimeField(blank=True, null=True, verbose_name="Старт")),
                        ("ended_at", models.DateTimeField(blank=True, null=True, verbose_name="Окончание")),
                        ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Создано")),
                        (
                            "task",
                            models.ForeignKey(
                                blank=True,
                                null=True,
                                on_delete=django.db.models.deletion.SET_NULL,
                                related_name="pomodoro_sessions",
                                to="planner.task",
                                verbose_name="Задача",
                            ),
                        ),
                        (
                            "user",
                            models.ForeignKey(
                                on_delete=django.db.models.deletion.CASCADE,
                                related_name="pomodoro_sessions",
                                to=settings.AUTH_USER_MODEL,
                                verbose_name="Пользователь",
                            ),
                        ),
                    ],
                    options={
                        "verbose_name": "Сессия",
                        "verbose_name_plural": "3. Сессии",
                        "db_table": "planner_pomodorosession",
                        "ordering": ("-created_at",),
                    },
                ),
                migrations.AddConstraint(
                    model_name="sound",
                    constraint=models.UniqueConstraint(fields=("key", "category"), name="uniq_sound_key_category"),
                ),
            ],
        ),
    ]
