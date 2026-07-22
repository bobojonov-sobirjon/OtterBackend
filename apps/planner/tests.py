from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from .models import (
    FAQEntry,
    FCMDevice,
    MatrixBlockSetting,
    NotificationDelivery,
    Task,
)
from .notifications import send_task_reminder
from .services import complete_task_with_repeat, reassign_matrix_tasks, snooze_reminder


class PlannerBacklogTests(TestCase):
    """Проверки критической backend-логики из мобильного ТЗ."""

    def setUp(self):
        """Создаёт пользователя и авторизованный API client."""
        self.user = get_user_model().objects.create_user(
            email="planner@example.com",
            password="StrongPassword123!",
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_recurring_complete_is_idempotent(self):
        """Повторный complete не должен создавать вторую следующую задачу."""
        task = Task.objects.create(
            user=self.user,
            title="Ежедневная задача",
            due_at=timezone.now() + timedelta(hours=1),
            repeat_unit=Task.RepeatUnit.DAY,
            repeat_interval=1,
        )
        completed, first_next = complete_task_with_repeat(task)
        completed_again, second_next = complete_task_with_repeat(completed)

        self.assertTrue(completed_again.is_completed)
        self.assertIsNotNone(first_next)
        self.assertEqual(first_next.id, second_next.id)
        self.assertEqual(Task.objects.filter(parent_task=task).count(), 1)

    def test_matrix_rules_reassign_task(self):
        """Комбинация overdue + high переносит задачу в первый блок."""
        MatrixBlockSetting.objects.create(
            user=self.user,
            block=Task.MatrixBlock.URGENT_IMPORTANT,
            title="Срочно и важно",
            allowed_priorities=[Task.Priority.HIGH],
            date_filter="overdue",
        )
        task = Task.objects.create(
            user=self.user,
            title="Просроченная важная",
            due_at=timezone.now() - timedelta(hours=1),
            priority=Task.Priority.HIGH,
            matrix_block=Task.MatrixBlock.NOT_URGENT_NOT_IMPORTANT,
        )

        self.assertEqual(reassign_matrix_tasks(self.user), 1)
        task.refresh_from_db()
        self.assertEqual(task.matrix_block, Task.MatrixBlock.URGENT_IMPORTANT)

    def test_snooze_resets_delivery(self):
        """Snooze переносит reminder и разрешает повторную отправку."""
        old_time = timezone.now() - timedelta(minutes=1)
        task = Task.objects.create(
            user=self.user,
            title="Напоминание",
            reminder_at=old_time,
            reminder_delivered_at=timezone.now(),
        )
        task = snooze_reminder(task, 10)

        self.assertIsNone(task.reminder_delivered_at)
        self.assertGreater(task.reminder_at, timezone.now())

    def test_device_registration_is_upsert(self):
        """Одинаковый device_id обновляет token, а не создаёт дубль."""
        payload = {
            "token": "token-one",
            "device_id": "phone-1",
            "name": "Pixel",
            "platform": "android",
            "app_version": "1.0.0",
        }
        first = self.client.post("/api/v1/devices/", payload, format="json")
        self.assertEqual(first.status_code, 201)

        payload["token"] = "token-two"
        second = self.client.post("/api/v1/devices/", payload, format="json")
        self.assertEqual(second.status_code, 200)
        self.assertEqual(FCMDevice.objects.filter(user=self.user).count(), 1)
        self.assertEqual(FCMDevice.objects.get(user=self.user).token, "token-two")

    def test_faq_search(self):
        """FAQ search фильтрует вопрос и ответ."""
        FAQEntry.objects.create(
            question="Как создать задачу?",
            answer="Нажмите плюс.",
        )
        FAQEntry.objects.create(
            question="Как оплатить?",
            answer="Откройте Премиум.",
        )
        response = self.client.get("/api/v1/help/?search=оплатить")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["question"], "Как оплатить?")

    @patch("apps.planner.notifications.messaging.send", return_value="message-1")
    @patch("apps.planner.notifications.get_firebase_app", return_value=object())
    def test_fcm_reminder_delivery(self, firebase_app_mock, send_mock):
        """FCM отправка создаёт delivery и отмечает reminder доставленным."""
        device = FCMDevice.objects.create(
            user=self.user,
            token="push-token",
            device_id="phone-fcm",
            platform=FCMDevice.Platform.ANDROID,
        )
        task = Task.objects.create(
            user=self.user,
            title="Push задача",
            reminder_at=timezone.now() - timedelta(seconds=1),
        )

        result = send_task_reminder(task)

        self.assertEqual(result["sent"], 1)
        task.refresh_from_db()
        self.assertIsNotNone(task.reminder_delivered_at)
        delivery = NotificationDelivery.objects.get(task=task, device=device)
        self.assertEqual(delivery.status, NotificationDelivery.Status.SENT)
        self.assertEqual(delivery.message_id, "message-1")
        send_mock.assert_called_once()
