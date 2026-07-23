# OTTER — Frontend Integration Guide (yangi API lar)

> **Kim uchun:** Flutter / React Native / Web frontend dasturchilar  
> **Maqsad:** yangi backend API larni qanday chaqirish, UI da nima qilish  
> **PROD Base URL:** `https://admin.ottertime.ru`  
> **API prefix:** `/api/v1/`  
> **Auth:** `Authorization: Bearer <access_token>`  
> **Content-Type:** `application/json` (fayl yuklashda `multipart/form-data`)

Bog‘liq hujjatlar:
- Umumiy API: [MOBILE_API.md](./MOBILE_API.md)
- Premium / Robokassa SDK: [PAYMENT_MOBILE_SDK.md](./PAYMENT_MOBILE_SDK.md)
- Texnik backend notes: [BACKLOG_BACKEND_API.md](./BACKLOG_BACKEND_API.md)

---

## 0. 30 soniyada nima o‘zgardi

| Modul | Nima qilish kerak (frontend) |
|---|---|
| **FCM Devices** | Login dan keyin token yuborish, logout da o‘chirish |
| **Notifications inbox** | `GET /notifications/` — o‘z notificationlari; badge uchun unread-count |
| **Reminders / Push** | Notification action → complete / snooze API |
| **Repeat tasks** | Complete → `next_task`; delete → `scope` |
| **Attachments** | Multipart upload / list / delete |
| **Calendar** | `all_day_tasks` + `timed_tasks` ishlatish |
| **Search** | `list_key` bo‘yicha to‘g‘ri list ochish |
| **Matrix** | `date_filters` + `allowed_priorities` sozlash |
| **Settings** | `timezone` saqlash |
| **FAQ** | `?search=` bilan qidirish |
| **Register** | Welcome email backend yuboradi — UI o‘zgarmaydi |

---

## 1. Headers (hamma himoyalangan so‘rov)

```http
Authorization: Bearer <access_token>
Content-Type: application/json
```

Token olish: `POST /auth/login/`, `/auth/register/`, `/auth/google/`.

---

## 2. FCM Devices (push uchun majburiy)

### Oqim

```text
1. User login / Google login
2. App FCM token oladi (Firebase Messaging)
3. POST /devices/  → token + device_id
4. Token yangilansa → yana POST /devices/ (upsert)
5. Logout → DELETE /devices/{id}/
```

### 2.1 Qurilmani ro‘yxatga olish / yangilash

| | |
|---|---|
| **METHOD** | `POST` |
| **URL** | `/api/v1/devices/` |
| **Auth** | Bearer |

```json
{
  "token": "<FCM_TOKEN>",
  "device_id": "<STABLE_DEVICE_ID>",
  "name": "Samsung S24",
  "platform": "android",
  "app_version": "1.0.0"
}
```

| Field | Type | Required | Izoh |
|---|---|---|---|
| `token` | string | **yes** | Firebase FCM token |
| `device_id` | string | **yes** | Qurilma uchun barqaror ID (qayta o‘zgarmasin) |
| `name` | string | no | «Samsung S24», «iPhone 15» |
| `platform` | string | **yes** | `android` \| `ios` \| `web` |
| `app_version` | string | no | Masalan `1.0.0` |

**Success:** `201` (yangi) yoki `200` (yangilandi).

> Bir xil `device_id` → upsert. Token response da **qaytarilmaydi** (xavfsizlik).

### 2.2 Qurilmalar ro‘yxati

```http
GET /api/v1/devices/
```

```json
[
  {
    "id": 1,
    "device_id": "phone-abc",
    "name": "Samsung S24",
    "platform": "android",
    "app_version": "1.0.0",
    "is_active": true,
    "last_seen_at": "2026-07-22T09:00:00+03:00",
    "created_at": "2026-07-21T12:00:00+03:00"
  }
]
```

### 2.3 Qurilmani o‘chirish (logout)

```http
DELETE /api/v1/devices/{id}/
```

`{id}` — `GET /devices/` dagi raqamli `id` (device_id emas!).

### Flutter — misol

```dart
Future<void> registerFcmDevice(String fcmToken) async {
  await api.post('/api/v1/devices/', {
    'token': fcmToken,
    'device_id': await getStableDeviceId(), // UUID saqlab qo‘ying
    'name': await getDeviceModel(),
    'platform': Platform.isIOS ? 'ios' : 'android',
    'app_version': packageInfo.version,
  });
}
```

### Android / iOS sozlash

| Platform | Nima qilish |
|---|---|
| **Android** | Channel ID: `task_reminders` |
| **iOS** | Category: `OTTER_TASK_REMINDER` |
| **Actions** | `Выполнить` → complete API; `Отложить` → snooze API |

---

## 3. Reminders / Notifications

### 3.0 In-app notification markazi (o‘z notificationlari)

Push dan tashqari har bir user uchun **inbox** bor. Reminder yuborilganda (qurilma bo‘lmasa ham) yozuv yaratiladi.

```http
GET /api/v1/notifications/
GET /api/v1/notifications/?is_read=false
GET /api/v1/notifications/?limit=20&offset=0
```

**Response:**

```json
{
  "count": 2,
  "next": null,
  "previous": null,
  "unread_count": 1,
  "results": [
    {
      "id": 15,
      "type": "task_reminder",
      "title": "Напоминание о задаче",
      "body": "Hisobot",
      "data": {
        "type": "task_reminder",
        "task_id": "123",
        "notification_id": "15",
        "complete_action": "complete",
        "snooze_action": "snooze",
        "snooze_minutes": "10",
        "deeplink": "otter://tasks/123"
      },
      "task": 123,
      "is_read": false,
      "read_at": null,
      "created_at": "2026-07-22T14:45:01+05:00"
    }
  ]
}
```

Boshqa user notificationlari **hech qachon** qaytmaydi (`user=request.user` filter).

```http
GET  /api/v1/notifications/unread-count/
→ { "unread_count": 1 }

POST /api/v1/notifications/{id}/read/
→ bitta o‘qilgan qilib belgilaydi

POST /api/v1/notifications/read-all/
→ { "updated": 3, "unread_count": 0 }

GET    /api/v1/notifications/{id}/
DELETE /api/v1/notifications/{id}/
```

**UI tavsiya:** badge → `unread-count`; ochilganda list; tap → `read` + deeplink (`data.task_id` / `data.deeplink`).

### 3.1 Task da reminder sozlash

```http
POST /api/v1/tasks/
PATCH /api/v1/tasks/{id}/
```

**Variant A — aniq vaqt:**

```json
{
  "title": "Hisobot",
  "due_at": "2026-07-22T15:00:00+05:00",
  "reminder_at": "2026-07-22T14:45:00+05:00"
}
```

**Variant B — muddatdan oldin (daqiqa):**

```json
{
  "title": "Hisobot",
  "due_at": "2026-07-22T15:00:00+05:00",
  "reminder_offset_minutes": 15
}
```

Backend `reminder_at = due_at − 15 min` ni o‘zi hisoblaydi.

| `reminder_offset_minutes` | Ma’nosi |
|---|---|
| `0` | Muddatda («В момент срока») |
| `15` | 15 daqiqa oldin |
| `60` | 1 soat oldin |
| `1440` | 1 kun oldin |

### 3.2 Push kelganda (FCM data)

```json
{
  "type": "task_reminder",
  "task_id": "123",
  "complete_action": "complete",
  "snooze_action": "snooze",
  "snooze_minutes": "10",
  "deeplink": "otter://tasks/123"
}
```

### 3.3 Complete (notification action)

```http
POST /api/v1/reminders/{task_id}/complete/
```

Body: `{}`

Javob — task + ixtiyoriy `next_task` (agar repeat bo‘lsa).

### 3.4 Snooze (отложить)

```http
POST /api/v1/reminders/{task_id}/snooze/
```

```json
{ "minutes": 10 }
```

`minutes`: 1 … 1440.

Keyin server yangi vaqtda yana push yuboradi.

### 3.5 Polling fallback (web yoki FCM ishlamasa)

```http
GET /api/v1/reminders/due/
```

Ko‘rsatgandan keyin:

```http
POST /api/v1/reminders/{task_id}/ack/
```

**Asosiy yo‘l:** FCM. Polling — zaxira.

### 3.6 Server cron (DevOps, frontend emas)

```bash
# Har daqiqada
python manage.py dispatch_task_reminders
```

Frontend faqat device token + actionlarni to‘g‘ri ulashi kerak.

---

## 4. Repeat (takrorlanuvchi vazifalar)

### 4.1 Yaratish / yangilash

```json
{
  "title": "Har kuni mashq",
  "due_at": "2026-07-22T18:00:00+05:00",
  "repeat_unit": "day",
  "repeat_interval": 1,
  "repeat_until": "2026-12-31"
}
```

| `repeat_unit` | Izoh |
|---|---|
| `none` | Takror yo‘q |
| `day` | Har N kun |
| `week` | Har N hafta |
| `month` | Har N oy |
| `year` | Har N yil |

### 4.2 Complete

```http
POST /api/v1/tasks/{id}/complete/
```

```json
{
  "id": 10,
  "is_completed": true,
  "series_id": "uuid...",
  "next_task": {
    "id": 11,
    "due_at": "2026-07-23T18:00:00+05:00",
    "is_completed": false,
    "series_id": "uuid..."
  }
}
```

UI: agar `next_task != null` — yangi vazifani listga qo‘shing.

> Complete ni **ikkita marta** bosish xavfsiz — backend duplicate yaratmaydi.

### 4.3 O‘chirish dialogi

```text
Удалить задачу?
[ Только это повторение ]  → DELETE ?scope=this
[ Все повторения ]         → DELETE ?scope=series
[ Отмена ]
```

```http
DELETE /api/v1/tasks/{id}/?scope=this
DELETE /api/v1/tasks/{id}/?scope=series
```

---

## 5. Attachments (fayllar)

### List

```http
GET /api/v1/tasks/{id}/attachments/
```

### Upload

```http
POST /api/v1/tasks/{id}/attachments/
Content-Type: multipart/form-data
```

Form field nomi: **`file`**

```json
{
  "id": 5,
  "file_url": "https://admin.ottertime.ru/media/task_attachments/doc.pdf",
  "original_name": "doc.pdf",
  "content_type": "application/pdf",
  "size": 12345,
  "created_at": "..."
}
```

### Delete

```http
DELETE /api/v1/tasks/{id}/attachments/{attachment_id}/
```

Eski `image` / `image_url` ham ishlaydi (bitta rasm). Ko‘p fayl uchun `attachments`.

Task detail da ham `attachments` array keladi.

---

## 6. Calendar

```http
GET /api/v1/calendar/?view=day&date=2026-07-22
GET /api/v1/calendar/?view=week&date=2026-07-22
GET /api/v1/calendar/?view=month&date=2026-07-22
GET /api/v1/calendar/?view=year&date=2026-07-22
```

```json
{
  "view": "week",
  "date": "2026-07-22",
  "range_start": "2026-07-20",
  "range_end": "2026-07-27",
  "timezone": "Asia/Tashkent",
  "all_day_tasks": [ /* sana bor, vaqt yo‘q */ ],
  "timed_tasks": [ /* vaqtli */ ],
  "tasks": [ /* flat — eski kod uchun */ ]
}
```

| Qoida | UI |
|---|---|
| Sana **yo‘q** | Calendarga **tushmaydi** |
| `is_all_day: true` | Yuqori blok (`all_day_tasks`) |
| Vaqtli | Shkala (`timed_tasks`) |

### All-day task yaratish

```json
{
  "title": "Tug‘ilgan kun",
  "due_at": "2026-07-25T00:00:00+05:00",
  "is_all_day": true
}
```

---

## 7. Search → to‘g‘ri list

```http
GET /api/v1/tasks/?search=hisobot
```

Har natijada:

```json
{
  "id": 123,
  "title": "Hisobot",
  "list_key": "today"
}
```

| `list_key` | Chap panel |
|---|---|
| `overdue` | Просрочено |
| `today` | Сегодня |
| `tomorrow` | Завтра |
| `later` | Позже |
| `no_deadline` | Без срока |
| `completed` | Выполнено |

**UI oqim:**

```text
Search natijasi bosildi
  → list_key ni o‘qi
  → shu guruhni och
  → taskni highlight / edit och
```

### Guruhlangan list

```http
GET /api/v1/tasks/grouped/
```

Settings dagi `show_*` flaglar guruhlarni yashiradi.

---

## 8. Eisenhower Matrix

### Sozlamalar

```http
GET /api/v1/matrix/settings/
PATCH /api/v1/matrix/settings/
```

```json
{
  "block": "urgent_important",
  "title": "Срочно и важно",
  "allowed_priorities": ["high", "critical"],
  "date_filters": ["overdue", "today"]
}
```

| Field | Izoh |
|---|---|
| `allowed_priorities` | `low` \| `medium` \| `high` \| `critical` |
| `date_filters` | **Array** (bir nechta): `overdue`, `today`, `tomorrow`, `later`, `no_deadline`, `with_deadline`, `any` |

**Logika:** `priority IN allowed` **AND** `date IN date_filters`.

Sozlama saqlanganda backend tasklarni **avtomatik** bloklarga qayta taqsimlaydi (`reassigned_tasks` keladi).

### Matrix ko‘rinishi

```http
GET /api/v1/matrix/
```

4 blok + har birida `tasks` + `count`.

Taskni qo‘lda ko‘chirish: `PATCH /tasks/{id}/` → `{ "matrix_block": "..." }`.

---

## 9. Settings (timezone muhim)

```http
GET /api/v1/settings/
PATCH /api/v1/settings/
```

```json
{
  "language": "ru",
  "timezone": "Asia/Tashkent",
  "notification_sound": "default",
  "completion_sound": "default",
  "vibration_enabled": true,
  "show_overdue": true,
  "show_today": true,
  "show_tomorrow": true,
  "show_later": true,
  "show_no_deadline": true,
  "show_completed": true,
  "bottom_tabs": ["tasks", "calendar", "matrix", "pomodoro", "settings"]
}
```

`timezone` — IANA (`Europe/Moscow`, `Asia/Tashkent`, …).  
Today / Overdue / Calendar / Reminder shu timezone bilan hisoblanadi.

Birinchi ochilishda foydalanuvchi timezone ni device timezone ga o‘rnating.

---

## 10. FAQ

```http
GET /api/v1/help/
GET /api/v1/help/?search=помодоро
```

```json
[
  {
    "id": 7,
    "question": "Как работает Помодоро?",
    "answer": "...",
    "sort_order": 7,
    "updated_at": "..."
  }
]
```

Support xabar:

```http
POST /api/v1/help/
Content-Type: multipart/form-data
```

Fields: `message`, `screenshot` (ixtiyoriy).

---

## 11. Task maydonlari (yangi)

Har task response da qo‘shimcha:

| Field | Type | Frontend uchun |
|---|---|---|
| `is_all_day` | bool | Calendar yuqori blok |
| `reminder_at` | datetime\|null | Budilnik ikonkasi |
| `reminder_offset_minutes` | int\|null | UI picker |
| `reminder_delivered_at` | datetime\|null | Odatda UI ga kerak emas |
| `repeat_unit` | enum | Repeat UI |
| `repeat_interval` | int | Interval |
| `repeat_until` | date\|null | Oxirgi sana |
| `series_id` | uuid\|null | Series delete |
| `parent_task` | id\|null | Debug / chain |
| `list_key` | string | Search → list |
| `attachments` | array | Fayllar |
| `image_url` | string\|null | Absolute image URL |

---

## 12. TypeScript tiplar (qisqa)

```typescript
type Platform = "android" | "ios" | "web";

type FcmDevice = {
  id: number;
  device_id: string;
  name: string;
  platform: Platform;
  app_version: string;
  is_active: boolean;
  last_seen_at: string;
  created_at: string;
};

type ListKey =
  | "overdue"
  | "today"
  | "tomorrow"
  | "later"
  | "no_deadline"
  | "completed";

type RepeatUnit = "none" | "day" | "week" | "month" | "year";

type Task = {
  id: number;
  title: string;
  description: string | null;
  due_at: string | null;
  start_at: string | null;
  end_at: string | null;
  is_all_day: boolean;
  reminder_at: string | null;
  reminder_offset_minutes: number | null;
  repeat_unit: RepeatUnit;
  repeat_interval: number;
  repeat_until: string | null;
  series_id: string | null;
  priority: "low" | "medium" | "high" | "critical";
  matrix_block: string;
  image_url: string | null;
  attachments: Attachment[];
  is_completed: boolean;
  list_key: ListKey;
  next_task?: Task | null; // faqat complete javobida
};

type Attachment = {
  id: number;
  file_url: string;
  original_name: string;
  content_type: string;
  size: number;
  created_at: string;
};

type CalendarResponse = {
  view: "day" | "week" | "month" | "year";
  date: string;
  range_start: string;
  range_end: string;
  timezone: string;
  all_day_tasks: Task[];
  timed_tasks: Task[];
  tasks: Task[];
};
```

---

## 13. Frontend QA checklist

### Push
- [ ] Login dan keyin `POST /devices/`
- [ ] Token refresh da qayta `POST /devices/`
- [ ] Logout da `DELETE /devices/{id}/`
- [ ] Notification markazi: `GET /notifications/` (faqat o‘zining)
- [ ] Badge: `GET /notifications/unread-count/`
- [ ] Tap → `POST /notifications/{id}/read/` + deeplink
- [ ] Android channel `task_reminders`
- [ ] iOS category `OTTER_TASK_REMINDER`
- [ ] Action «Выполнить» → `/reminders/{id}/complete/`
- [ ] Action «Отложить» → `/reminders/{id}/snooze/` `{minutes:10}`

### Tasks
- [ ] Repeat create + complete → `next_task` UI da
- [ ] Delete dialog: this / series
- [ ] Attachment multipart `file` field
- [ ] Reminder UI: offset yoki aniq vaqt

### Calendar / Search / Matrix
- [ ] `all_day_tasks` vs `timed_tasks`
- [ ] Undated task calendarga tushmasligi
- [ ] Search → `list_key` bo‘yicha list ochish
- [ ] Matrix `date_filters` array yuborish

### Settings / FAQ
- [ ] Device timezone ni `PATCH /settings/` ga yozish
- [ ] FAQ search input → `?search=`
- [ ] Register dan keyin welcome email (backend) — faqat SMTP ishlashini bilish

---

## 14. Xatolar

| HTTP | Qachon | UI |
|---|---|---|
| `400` | Validatsiya | `detail` / field xatolari |
| `401` | Token | Refresh yoki login |
| `404` | Topilmadi | Snackbar |
| `503` | Payment / tashqi servis | «Временно недоступно» |

---

## 15. Tez endpoint jadvali (yangi)

| # | Method | URL | Vazifa |
|---|---|---|---|
| 1 | POST | `/devices/` | FCM token upsert |
| 2 | GET | `/devices/` | Qurilmalar |
| 3 | DELETE | `/devices/{id}/` | O‘chirish |
| 4 | GET | `/notifications/` | O‘z notificationlari (+ unread_count) |
| 5 | GET | `/notifications/unread-count/` | Badge |
| 6 | POST | `/notifications/{id}/read/` | O‘qildi |
| 7 | POST | `/notifications/read-all/` | Hammasi o‘qildi |
| 8 | DELETE | `/notifications/{id}/` | O‘chirish |
| 9 | GET | `/reminders/due/` | Pending reminders |
| 10 | POST | `/reminders/{id}/ack/` | Ko‘rsatildi |
| 11 | POST | `/reminders/{id}/snooze/` | Kechiktirish |
| 12 | POST | `/reminders/{id}/complete/` | Notification dan complete |
| 13 | POST | `/tasks/{id}/complete/` | Complete + next_task |
| 14 | DELETE | `/tasks/{id}/?scope=` | this \| series |
| 15 | GET/POST | `/tasks/{id}/attachments/` | Fayllar |
| 16 | DELETE | `/tasks/{id}/attachments/{aid}/` | Fayl o‘chirish |
| 17 | GET | `/calendar/?view=&date=` | all_day + timed |
| 18 | GET | `/tasks/?search=` | + `list_key` |
| 19 | GET | `/tasks/grouped/` | 6 guruh |
| 20 | GET/PATCH | `/matrix/settings/` | date_filters |
| 21 | GET | `/matrix/` | Bloklar |
| 22 | GET/PATCH | `/settings/` | timezone |
| 23 | GET | `/help/?search=` | FAQ |

---

## 16. Minimal implementatsiya tartibi (tavsiya)

```text
1. Settings: timezone saqlash
2. Devices: FCM register + logout delete
3. Reminder create UI + complete/snooze actions
4. Repeat complete + delete scope dialog
5. Calendar all_day / timed
6. Search list_key navigation
7. Attachments upload
8. Matrix date_filters UI
9. FAQ search
```

Savollar bo‘lsa backend Swagger: `{BASE_URL}/docs/`
