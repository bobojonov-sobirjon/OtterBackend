import django.db.models.deletion
from django.db import migrations, models


def _sound_id(Sound, key, category):
    sound = Sound.objects.filter(key=key, category=category).first()
    return sound.id if sound else None


def char_keys_to_fk(apps, schema_editor):
    Sound = apps.get_model("planner", "Sound")
    PomodoroSettings = apps.get_model("planner", "PomodoroSettings")
    AppSettings = apps.get_model("planner", "AppSettings")

    for row in PomodoroSettings.objects.all():
        timer_key = row.timer_end_sound_key
        work_key = row.work_sound_key
        row.timer_end_sound_id = _sound_id(Sound, timer_key, "timer_end") or _sound_id(Sound, "bell", "timer_end")
        row.work_sound_id = _sound_id(Sound, work_key, "work_background") or _sound_id(Sound, "none", "work_background")
        row.save(update_fields=["timer_end_sound_id", "work_sound_id"])

    for row in AppSettings.objects.all():
        row.notification_sound_id = _sound_id(Sound, row.notification_sound_key, "notification") or _sound_id(
            Sound, "default", "notification"
        )
        row.completion_sound_id = _sound_id(Sound, row.completion_sound_key, "completion") or _sound_id(
            Sound, "default", "completion"
        )
        row.save(update_fields=["notification_sound_id", "completion_sound_id"])


def fk_to_char_keys(apps, schema_editor):
    PomodoroSettings = apps.get_model("planner", "PomodoroSettings")
    AppSettings = apps.get_model("planner", "AppSettings")
    Sound = apps.get_model("planner", "Sound")

    for row in PomodoroSettings.objects.select_related("timer_end_sound", "work_sound"):
        if row.timer_end_sound_id:
            row.timer_end_sound_key = Sound.objects.get(pk=row.timer_end_sound_id).key
        if row.work_sound_id:
            row.work_sound_key = Sound.objects.get(pk=row.work_sound_id).key
        row.save(update_fields=["timer_end_sound_key", "work_sound_key"])

    for row in AppSettings.objects.all():
        if row.notification_sound_id:
            row.notification_sound_key = Sound.objects.get(pk=row.notification_sound_id).key
        if row.completion_sound_id:
            row.completion_sound_key = Sound.objects.get(pk=row.completion_sound_id).key
        row.save(update_fields=["notification_sound_key", "completion_sound_key"])


class Migration(migrations.Migration):

    dependencies = [
        ("planner", "0002_sound_catalog"),
    ]

    operations = [
        migrations.RenameField(
            model_name="pomodorosettings",
            old_name="timer_end_sound",
            new_name="timer_end_sound_key",
        ),
        migrations.RenameField(
            model_name="pomodorosettings",
            old_name="work_sound",
            new_name="work_sound_key",
        ),
        migrations.RenameField(
            model_name="appsettings",
            old_name="notification_sound",
            new_name="notification_sound_key",
        ),
        migrations.RenameField(
            model_name="appsettings",
            old_name="completion_sound",
            new_name="completion_sound_key",
        ),
        migrations.AddField(
            model_name="pomodorosettings",
            name="timer_end_sound",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="+",
                to="planner.sound",
                verbose_name="Звук завершения таймера",
            ),
        ),
        migrations.AddField(
            model_name="pomodorosettings",
            name="work_sound",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="+",
                to="planner.sound",
                verbose_name="Фоновая мелодия",
            ),
        ),
        migrations.AddField(
            model_name="appsettings",
            name="notification_sound",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="+",
                to="planner.sound",
                verbose_name="Звук уведомления",
            ),
        ),
        migrations.AddField(
            model_name="appsettings",
            name="completion_sound",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="+",
                to="planner.sound",
                verbose_name="Звук завершения",
            ),
        ),
        migrations.RunPython(char_keys_to_fk, fk_to_char_keys),
        migrations.RemoveField(model_name="pomodorosettings", name="timer_end_sound_key"),
        migrations.RemoveField(model_name="pomodorosettings", name="work_sound_key"),
        migrations.RemoveField(model_name="appsettings", name="notification_sound_key"),
        migrations.RemoveField(model_name="appsettings", name="completion_sound_key"),
        migrations.AlterField(
            model_name="pomodorosettings",
            name="timer_end_sound",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="+",
                to="planner.sound",
                verbose_name="Звук завершения таймера",
            ),
        ),
        migrations.AlterField(
            model_name="pomodorosettings",
            name="work_sound",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="+",
                to="planner.sound",
                verbose_name="Фоновая мелодия",
            ),
        ),
        migrations.AlterField(
            model_name="appsettings",
            name="notification_sound",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="+",
                to="planner.sound",
                verbose_name="Звук уведомления",
            ),
        ),
        migrations.AlterField(
            model_name="appsettings",
            name="completion_sound",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="+",
                to="planner.sound",
                verbose_name="Звук завершения",
            ),
        ),
    ]
