from django.db import migrations, models

from apps.planner.sound_catalog import DEFAULT_SOUNDS


def seed_sounds(apps, schema_editor):
    Sound = apps.get_model("planner", "Sound")
    for item in DEFAULT_SOUNDS:
        Sound.objects.update_or_create(
            key=item["key"],
            category=item["category"],
            defaults={
                "title": item["title"],
                "emoji": item["emoji"],
                "sort_order": item["sort_order"],
                "is_active": True,
            },
        )


def unseed_sounds(apps, schema_editor):
    Sound = apps.get_model("planner", "Sound")
    keys = {(s["key"], s["category"]) for s in DEFAULT_SOUNDS}
    for key, category in keys:
        Sound.objects.filter(key=key, category=category).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("planner", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Sound",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("key", models.CharField(max_length=50, verbose_name="Ключ")),
                ("category", models.CharField(
                    choices=[
                        ("timer_end", "Звук завершения таймера"),
                        ("work_background", "Фоновый звук помодоро"),
                        ("notification", "Звук уведомления"),
                        ("completion", "Звук завершения задачи"),
                    ],
                    max_length=30,
                    verbose_name="Категория",
                )),
                ("title", models.CharField(max_length=120, verbose_name="Название")),
                ("emoji", models.CharField(blank=True, default="", max_length=16, verbose_name="Emoji")),
                ("audio_file", models.FileField(blank=True, null=True, upload_to="sounds/", verbose_name="Аудиофайл")),
                ("sort_order", models.PositiveIntegerField(default=0, verbose_name="Порядок")),
                ("is_active", models.BooleanField(default=True, verbose_name="Активен")),
            ],
            options={
                "verbose_name": "Звук",
                "verbose_name_plural": "Звуки",
                "ordering": ("category", "sort_order", "key"),
            },
        ),
        migrations.AddConstraint(
            model_name="sound",
            constraint=models.UniqueConstraint(fields=("key", "category"), name="uniq_sound_key_category"),
        ),
        migrations.AddField(
            model_name="pomodorosettings",
            name="short_break_minutes",
            field=models.PositiveIntegerField(default=5, verbose_name="Короткий перерыв"),
        ),
        migrations.AlterField(
            model_name="pomodorosettings",
            name="timer_end_sound",
            field=models.CharField(default="bell", max_length=120, verbose_name="Звук завершения таймера"),
        ),
        migrations.RunPython(seed_sounds, unseed_sounds),
    ]
