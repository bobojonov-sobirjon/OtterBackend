"""Отправка task-reminder push уведомлений через Firebase Cloud Messaging."""

from __future__ import annotations

import logging

from django.db import transaction
from django.utils import timezone
from firebase_admin import messaging

from apps.accounts.utils import get_firebase_app

from .models import FCMDevice, NotificationDelivery, Task, UserNotification


logger = logging.getLogger(__name__)


def _notification_data(task: Task, *, notification_id: int | None = None) -> dict[str, str]:
    """Формирует строковые data-поля для действий mobile notification."""
    payload = {
        "type": "task_reminder",
        "task_id": str(task.id),
        "complete_action": "complete",
        "snooze_action": "snooze",
        "snooze_minutes": "10",
        "deeplink": f"otter://tasks/{task.id}",
    }
    if notification_id is not None:
        payload["notification_id"] = str(notification_id)
    return payload


def create_task_reminder_inbox(task: Task) -> UserNotification:
    """Создаёт или обновляет непрочитанное in-app уведомление по задаче."""
    data = _notification_data(task)
    existing = (
        UserNotification.objects.filter(
            user=task.user,
            task=task,
            type=UserNotification.Type.TASK_REMINDER,
            is_read=False,
        )
        .order_by("-created_at")
        .first()
    )
    if existing:
        existing.title = "Напоминание о задаче"
        existing.body = task.title
        existing.data = {**data, "notification_id": str(existing.id)}
        existing.save(update_fields=["title", "body", "data"])
        return existing

    notification = UserNotification.objects.create(
        user=task.user,
        task=task,
        type=UserNotification.Type.TASK_REMINDER,
        title="Напоминание о задаче",
        body=task.title,
        data=data,
        is_read=False,
    )
    notification.data = {**data, "notification_id": str(notification.id)}
    notification.save(update_fields=["data"])
    return notification


def _message_for_device(
    task: Task,
    device: FCMDevice,
    *,
    notification_id: int | None = None,
) -> messaging.Message:
    """Создаёт FCM message с high-priority и данными для lock-screen actions."""
    title = "Напоминание о задаче"
    body = task.title
    return messaging.Message(
        token=device.token,
        notification=messaging.Notification(title=title, body=body),
        data=_notification_data(task, notification_id=notification_id),
        android=messaging.AndroidConfig(
            priority="high",
            notification=messaging.AndroidNotification(
                sound="default",
                channel_id="task_reminders",
                click_action="OTTER_TASK_REMINDER",
            ),
        ),
        apns=messaging.APNSConfig(
            headers={"apns-priority": "10"},
            payload=messaging.APNSPayload(
                aps=messaging.Aps(
                    sound="default",
                    category="OTTER_TASK_REMINDER",
                    content_available=True,
                )
            ),
        ),
    )


def _is_invalid_token_error(exc: Exception) -> bool:
    """Определяет ошибки, после которых FCM token нужно отключить."""
    return type(exc).__name__ in {
        "UnregisteredError",
        "InvalidArgumentError",
        "SenderIdMismatchError",
    }


@transaction.atomic
def send_task_reminder(task: Task) -> dict[str, int]:
    """Отправляет напоминание: inbox + FCM на активные устройства."""
    task = Task.objects.select_for_update().get(pk=task.pk)
    if task.is_completed or not task.reminder_at or task.reminder_delivered_at:
        return {"sent": 0, "failed": 0, "skipped": 1}

    inbox = create_task_reminder_inbox(task)
    devices = list(FCMDevice.objects.filter(user=task.user, is_active=True))
    if not devices:
        # In-app inbox still gets the notification even without FCM tokens.
        task.reminder_delivered_at = timezone.now()
        task.save(update_fields=["reminder_delivered_at", "updated_at"])
        return {"sent": 0, "failed": 0, "skipped": 0, "inbox": 1}

    app = get_firebase_app()
    sent = 0
    failed = 0
    attempted_at = timezone.now()

    for device in devices:
        delivery, created = NotificationDelivery.objects.get_or_create(
            task=task,
            device=device,
        )
        if not created and delivery.status == NotificationDelivery.Status.SENT:
            continue

        delivery.attempted_at = attempted_at
        try:
            message_id = messaging.send(
                _message_for_device(task, device, notification_id=inbox.id),
                app=app,
            )
            delivery.status = NotificationDelivery.Status.SENT
            delivery.message_id = message_id
            delivery.error = ""
            delivery.sent_at = timezone.now()
            sent += 1
        except Exception as exc:
            logger.exception(
                "FCM task reminder failed task=%s device=%s",
                task.id,
                device.id,
            )
            delivery.status = NotificationDelivery.Status.FAILED
            delivery.error = f"{type(exc).__name__}: {exc}"[:2000]
            if _is_invalid_token_error(exc):
                device.is_active = False
                device.save(update_fields=["is_active", "updated_at"])
            failed += 1
        delivery.save()

    # Delivered to inbox; mark reminder processed even if all FCM failed.
    task.reminder_delivered_at = timezone.now()
    task.save(update_fields=["reminder_delivered_at", "updated_at"])

    return {"sent": sent, "failed": failed, "skipped": 0, "inbox": 1}


def dispatch_due_task_reminders(*, limit: int = 500) -> dict[str, int]:
    """Находит просроченные reminder_at и отправляет inbox + FCM push."""
    now = timezone.now()
    tasks = list(
        Task.objects.filter(
            is_completed=False,
            reminder_at__isnull=False,
            reminder_at__lte=now,
            reminder_delivered_at__isnull=True,
        )
        .order_by("reminder_at")[:limit]
    )
    stats = {"tasks": len(tasks), "sent": 0, "failed": 0, "skipped": 0, "inbox": 0}
    for task in tasks:
        result = send_task_reminder(task)
        stats["sent"] += result["sent"]
        stats["failed"] += result["failed"]
        stats["skipped"] += result["skipped"]
        stats["inbox"] += int(result.get("inbox") or 0)
    return stats
