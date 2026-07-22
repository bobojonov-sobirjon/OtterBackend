"""Planner business logic: recurrence, calendar, matrix filters, groups, reminders."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import calendar

from django.db import transaction
from django.db.models import Q, QuerySet
from django.utils import timezone

from .models import AppSettings, MatrixBlockSetting, NotificationDelivery, Task


def _add_months(value, months: int):
    """Shift datetime by N months without python-dateutil."""
    month = value.month - 1 + months
    year = value.year + month // 12
    month = month % 12 + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return value.replace(year=year, month=month, day=day)


def resolve_user_timezone(user) -> ZoneInfo:
    """IANA timezone from AppSettings, fallback to Django default."""
    tz_name = "Europe/Moscow"
    try:
        settings_obj = AppSettings.objects.filter(user=user).only("timezone").first()
        if settings_obj and settings_obj.timezone:
            tz_name = settings_obj.timezone
    except Exception:
        pass
    try:
        return ZoneInfo(tz_name)
    except ZoneInfoNotFoundError:
        return ZoneInfo("Europe/Moscow")


def activate_user_timezone(user):
    """Activate user timezone for the current request/thread."""
    timezone.activate(resolve_user_timezone(user))


def local_now(user=None):
    if user is not None:
        return timezone.now().astimezone(resolve_user_timezone(user))
    return timezone.localtime()


def task_group_key(task: Task, *, now=None) -> str:
    """Which system list the task belongs to (for search → open in correct list)."""
    if now is None:
        now = timezone.localtime()
    if task.is_completed:
        return "completed"
    if not task.due_at and not task.start_at:
        return "no_deadline"
    anchor = task.due_at or task.start_at
    due_local = timezone.localtime(anchor)
    today = now.date()
    tomorrow = today + timedelta(days=1)
    due_date = due_local.date()
    if not task.is_all_day and anchor < now:
        return "overdue"
    if task.is_all_day and due_date < today:
        return "overdue"
    if due_date == today:
        return "today"
    if due_date == tomorrow:
        return "tomorrow"
    return "later"


def shift_dt(value, unit: str, interval: int):
    if value is None:
        return None
    interval = max(int(interval or 1), 1)
    if unit == Task.RepeatUnit.DAY:
        return value + timedelta(days=interval)
    if unit == Task.RepeatUnit.WEEK:
        return value + timedelta(weeks=interval)
    if unit == Task.RepeatUnit.MONTH:
        return _add_months(value, interval)
    if unit == Task.RepeatUnit.YEAR:
        return _add_months(value, interval * 12)
    return value


def ensure_series_id(task: Task) -> uuid.UUID:
    if task.series_id:
        return task.series_id
    task.series_id = uuid.uuid4()
    task.save(update_fields=["series_id", "updated_at"])
    return task.series_id


@transaction.atomic
def complete_task_with_repeat(task: Task) -> tuple[Task, Task | None]:
    """
    Mark task completed. If recurring — create next occurrence in same series.
    Returns (completed_task, next_task_or_none).
    """
    task = Task.objects.select_for_update().get(pk=task.pk)
    existing_next = task.child_occurrences.order_by("created_at", "id").first()
    if task.is_completed:
        return task, existing_next

    task.mark_completed(True)
    task.save(update_fields=["is_completed", "completed_at", "updated_at"])

    if task.repeat_unit == Task.RepeatUnit.NONE:
        return task, None

    series_id = ensure_series_id(task)
    unit = task.repeat_unit
    interval = task.repeat_interval or 1

    next_due = shift_dt(task.due_at, unit, interval)
    next_start = shift_dt(task.start_at, unit, interval)
    next_end = shift_dt(task.end_at, unit, interval)
    next_reminder = shift_dt(task.reminder_at, unit, interval)

    if task.repeat_until:
        anchor = next_due or next_start
        if anchor and timezone.localtime(anchor).date() > task.repeat_until:
            return task, None

    next_task = Task.objects.create(
        user=task.user,
        title=task.title,
        description=task.description,
        due_at=next_due,
        start_at=next_start,
        end_at=next_end,
        reminder_at=next_reminder,
        reminder_offset_minutes=task.reminder_offset_minutes,
        repeat_unit=task.repeat_unit,
        repeat_interval=task.repeat_interval,
        repeat_until=task.repeat_until,
        series_id=series_id,
        parent_task=task,
        priority=task.priority,
        matrix_block=task.matrix_block,
        is_all_day=task.is_all_day,
        is_completed=False,
    )
    if task.image:
        next_task.image.name = task.image.name
        next_task.save(update_fields=["image", "updated_at"])
    return task, next_task


@transaction.atomic
def delete_task(task: Task, *, scope: str = "this") -> dict:
    """
    scope=this — delete only this occurrence.
    scope=series — delete this and all other tasks in the series.
    """
    scope = (scope or "this").lower()
    if scope == "series" and task.series_id:
        deleted, _ = Task.objects.filter(user=task.user, series_id=task.series_id).delete()
        return {"deleted": deleted, "scope": "series"}
    task_id = task.id
    task.delete()
    return {"deleted": 1, "scope": "this", "id": task_id}


def apply_matrix_filters(queryset: QuerySet, setting, *, now=None) -> QuerySet:
    """Применяет комбинацию priority AND (любой из date_filters)."""
    if now is None:
        now = timezone.localtime()

    priorities = setting.allowed_priorities or []
    if isinstance(priorities, list) and priorities:
        queryset = queryset.filter(priority__in=priorities)

    date_filters = list(getattr(setting, "date_filters", None) or [])
    legacy_filter = (setting.date_filter or "").strip().lower()
    if not date_filters and legacy_filter:
        date_filters = [legacy_filter]
    date_filters = [str(item).strip().lower() for item in date_filters if str(item).strip()]
    if not date_filters or any(item in {"any", "all"} for item in date_filters):
        return queryset

    today = now.date()
    tomorrow = today + timedelta(days=1)
    start_today = timezone.make_aware(datetime.combine(today, datetime.min.time()))
    start_tomorrow = timezone.make_aware(datetime.combine(tomorrow, datetime.min.time()))
    start_day_after = timezone.make_aware(
        datetime.combine(tomorrow + timedelta(days=1), datetime.min.time())
    )

    conditions = Q()
    for date_filter in date_filters:
        if date_filter == "overdue":
            conditions |= (
                Q(is_all_day=False, due_at__lt=now)
                | Q(is_all_day=False, due_at__isnull=True, start_at__lt=now)
                | Q(is_all_day=True, due_at__date__lt=today)
                | Q(is_all_day=True, due_at__isnull=True, start_at__date__lt=today)
            )
        elif date_filter == "today":
            conditions |= (
                Q(due_at__gte=start_today, due_at__lt=start_tomorrow)
                | Q(start_at__gte=start_today, start_at__lt=start_tomorrow)
            )
        elif date_filter == "tomorrow":
            conditions |= (
                Q(due_at__gte=start_tomorrow, due_at__lt=start_day_after)
                | Q(start_at__gte=start_tomorrow, start_at__lt=start_day_after)
            )
        elif date_filter == "later":
            conditions |= Q(due_at__gte=start_day_after) | Q(start_at__gte=start_day_after)
        elif date_filter in {"no_deadline", "no_date"}:
            conditions |= Q(due_at__isnull=True, start_at__isnull=True)
        elif date_filter in {"with_deadline", "with_date"}:
            conditions |= (
                Q(due_at__isnull=False) | Q(start_at__isnull=False)
            )

    if not conditions:
        return queryset
    return queryset.filter(conditions).distinct()


def matrix_block_for_task(task: Task, settings_items=None, *, now=None) -> str:
    """Определяет блок задачи по первой настроенной комбинации дата+приоритет."""
    if settings_items is None:
        settings_items = MatrixBlockSetting.objects.filter(user=task.user).order_by("id")
    if now is None:
        now = timezone.localtime()

    for setting in settings_items:
        priorities = setting.allowed_priorities or []
        date_filters = list(getattr(setting, "date_filters", None) or [])
        date_filter = (setting.date_filter or "").strip().lower()
        # Empty default rule must not capture every task.
        if not priorities and not date_filters and date_filter in {"", "any", "all"}:
            continue
        candidate = apply_matrix_filters(
            Task.objects.filter(pk=task.pk),
            setting,
            now=now,
        )
        if candidate.exists():
            return setting.block
    return task.matrix_block


@transaction.atomic
def reassign_matrix_tasks(user) -> int:
    """Перераспределяет активные задачи по пользовательским правилам матрицы."""
    settings_items = list(MatrixBlockSetting.objects.filter(user=user).order_by("id"))
    if not settings_items:
        return 0
    now = timezone.localtime()
    changed = 0
    for task in Task.objects.filter(user=user, is_completed=False):
        block = matrix_block_for_task(task, settings_items, now=now)
        if block != task.matrix_block:
            Task.objects.filter(pk=task.pk).update(matrix_block=block, updated_at=timezone.now())
            changed += 1
    return changed


def calendar_task_queryset(user, start_dt, end_dt) -> QuerySet:
    """
    Tasks for calendar range.
    - Timed / all-day with date in range (via start_at, due_at, or overlapping end_at)
    - Does NOT include undated tasks (both dates null) — backlog C10/C52
    """
    in_start = Q(start_at__gte=start_dt, start_at__lt=end_dt)
    in_due = Q(due_at__gte=start_dt, due_at__lt=end_dt)
    overlaps = Q(start_at__lt=end_dt, end_at__gt=start_dt)
    return (
        Task.objects.filter(user=user)
        .filter(in_start | in_due | overlaps)
        .exclude(start_at__isnull=True, due_at__isnull=True)
        .distinct()
        .order_by("start_at", "due_at", "id")
    )


def split_calendar_tasks(tasks) -> tuple[list[Task], list[Task]]:
    """Split into all-day (date only) vs timed."""
    all_day = []
    timed = []
    for task in tasks:
        if task.is_all_day:
            all_day.append(task)
        else:
            timed.append(task)
    return all_day, timed


def pending_reminders_queryset(user, *, until=None) -> QuerySet:
    """Reminders that should fire (for mobile/web local or push polling)."""
    if until is None:
        until = timezone.now()
    return Task.objects.filter(
        user=user,
        is_completed=False,
        reminder_at__isnull=False,
        reminder_at__lte=until,
        reminder_delivered_at__isnull=True,
    ).order_by("reminder_at")


def ack_reminder(task: Task) -> Task:
    """Подтверждает, что уведомление показано пользователю."""
    task.reminder_delivered_at = timezone.now()
    task.save(update_fields=["reminder_delivered_at", "updated_at"])
    return task


@transaction.atomic
def snooze_reminder(task: Task, minutes: int) -> Task:
    """Откладывает reminder и очищает старые delivery-записи для повторной отправки."""
    minutes = max(1, min(int(minutes), 24 * 60))
    task.reminder_at = timezone.now() + timedelta(minutes=minutes)
    task.reminder_delivered_at = None
    task.save(
        update_fields=[
            "reminder_at",
            "reminder_delivered_at",
            "updated_at",
        ]
    )
    NotificationDelivery.objects.filter(task=task).delete()
    return task
