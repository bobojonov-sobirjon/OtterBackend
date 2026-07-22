# OTTER — Backend backlog updates (Frontend / Mobile)

> Yangilanish: 2026-07-21  
> Nima o‘zgardi: FCM push, devices, snooze, repeat, attachments, calendar, search `list_key`, Matrix auto-routing, timezone, FAQ search.

**Base:** `https://admin.ottertime.ru/api/v1/`  
**Auth:** `Authorization: Bearer <token>`

---

## 1. Task — yangi maydonlar

Har bir task response da:

| Field | Type | Izoh |
|---|---|---|
| `is_all_day` | bool | `true` = sana bor, vaqt yo‘q (kalendar yuqori bloki) |
| `reminder_offset_minutes` | int\|null | `0` = muddatda, `15` = 15 daq oldin |
| `reminder_delivered_at` | datetime\|null | Ack qilingan |
| `repeat_until` | date\|null | Takrorlash oxiri |
| `series_id` | uuid\|null | Bir xil seriya |
| `parent_task` | id\|null | Oldingi occurrence |
| `list_key` | string | **Search uchun:** `overdue\|today\|tomorrow\|later\|no_deadline\|completed` |
| `attachments` | array | Fayllar ro‘yxati |
| `image_url` | string\|null | Absolute URL |

### Search → to‘g‘ri list ochish

```http
GET /api/v1/tasks/?search=текст
```

Har bir natijada `list_key` bor. UI: chap paneldagi shu guruhni ochib, taskni highlight qiling.

---

## 2. Repeat (takrorlash)

### Sozlash

```json
{
  "repeat_unit": "day",
  "repeat_interval": 1,
  "repeat_until": "2026-12-31"
}
```

`repeat_unit`: `none` | `day` | `week` | `month` | `year`

### Complete

```http
POST /api/v1/tasks/{id}/complete/
```

Javob — task maydonlari + `next_task` (yoki `null`):

```json
{
  "id": 10,
  "is_completed": true,
  "next_task": {
    "id": 11,
    "due_at": "2026-07-22T10:00:00+03:00",
    "series_id": "...",
    "is_completed": false
  }
}
```

Agar `repeat_unit != none` — keyingi kun/hafta/... uchun yangi task avtomatik yaratiladi.

### O‘chirish

```http
DELETE /api/v1/tasks/{id}/?scope=this
DELETE /api/v1/tasks/{id}/?scope=series
```

| scope | Natija |
|---|---|
| `this` | Faqat shu occurrence |
| `series` | Shu `series_id` dagi barcha tasklar |

---

## 3. Attachments (fayllar)

```http
GET  /api/v1/tasks/{id}/attachments/
POST /api/v1/tasks/{id}/attachments/   multipart: file=<binary>
DELETE /api/v1/tasks/{id}/attachments/{attachment_id}/
```

**POST response:**

```json
{
  "id": 1,
  "file_url": "https://admin.ottertime.ru/media/task_attachments/...",
  "original_name": "doc.pdf",
  "content_type": "application/pdf",
  "size": 12345,
  "created_at": "..."
}
```

Eski `image` maydoni ham qoladi (bitta rasm). Ko‘p fayl uchun `attachments` ishlating.

---

## 4. Notifications / Reminders

### 4.1 Device token ro‘yxatdan o‘tkazish

App login qilgandan va FCM token olgandan keyin:

```http
POST /api/v1/devices/
Content-Type: application/json

{
  "token": "<FCM_TOKEN>",
  "device_id": "<STABLE_DEVICE_ID>",
  "name": "Samsung S24",
  "platform": "android",
  "app_version": "1.0.0"
}
```

```http
GET    /api/v1/devices/
DELETE /api/v1/devices/{id}/
```

`id` — `GET /devices/` response ichidagi raqamli ID. Logout paytida device endpointga `DELETE` yuboring.

### 4.2 FCM push

Backend due tasklarni FCM HTTP v1 orqali yuboradi. Notification `data`:

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

Android notification channel: `task_reminders`.  
iOS category: `OTTER_TASK_REMINDER`.

Serverda har daqiqada:

```bash
python manage.py dispatch_task_reminders
```

### 4.3 Complete / Snooze notification action

```http
POST /api/v1/reminders/{task_id}/complete/
POST /api/v1/reminders/{task_id}/snooze/
Content-Type: application/json

{ "minutes": 10 }
```

Mobil app Android/iOS notification actionlarini shu endpointlarga bog‘laydi.

### 4.4 Polling fallback

```http
GET /api/v1/reminders/due/
GET /api/v1/reminders/due/?until=2026-07-21T12:00:00+03:00
```

```json
{
  "until": "...",
  "count": 2,
  "tasks": [ /* tasks with reminder_at */ ]
}
```

### Ack (ko‘rsatildi)

```http
POST /api/v1/reminders/{task_id}/ack/
```

Polling browser yoki FCM yetib kelmagan holat uchun fallback. Local notification ko‘rsatilsa `ack` chaqiring.

Task yaratishda:

```json
{
  "reminder_at": "2026-07-21T15:00:00+03:00",
  "reminder_offset_minutes": 0
}
```

---

## 5. Calendar (tuzatilgan)

```http
GET /api/v1/calendar/?view=week&date=2026-07-21
```

**Yangi response:**

```json
{
  "view": "week",
  "date": "2026-07-21",
  "range_start": "2026-07-20",
  "range_end": "2026-07-27",
  "timezone": "Europe/Moscow",
  "all_day_tasks": [ /* is_all_day=true, sana bor */ ],
  "timed_tasks": [ /* vaqtli */ ],
  "tasks": [ /* flat, backwards-compatible */ ]
}
```

| Qoida | |
|---|---|
| Sana **yo‘q** tasklar | Kalendarga **tushmaydi** |
| Sana bor, vaqt yo‘q | `is_all_day=true` → `all_day_tasks` |
| Vaqtli | `timed_tasks` |

---

## 6. Eisenhower Matrix filters

`PATCH /api/v1/matrix/settings/`:

```json
{
  "block": "urgent_important",
  "allowed_priorities": ["high", "critical"],
  "date_filters": ["overdue", "today"]
}
```

`date_filters`: bir nechta qiymat: `any` | `overdue` | `today` | `tomorrow` | `later` | `no_deadline` | `with_deadline`.

Kombinatsiya: `allowed_priorities` **AND** (`date_filters` ichidagi istalgan qiymat). Sozlama saqlanganda backend barcha active tasklarni avtomatik qayta taqsimlaydi. `GET /api/v1/matrix/` ham qoidalarni qayta qo‘llaydi.

---

## 7. Settings — timezone

```http
PATCH /api/v1/settings/
{
  "language": "ru",
  "timezone": "Asia/Tashkent",
  "notification_sound": "default",
  "vibration_enabled": true
}
```

IANA timezone majburiy format: `Europe/Moscow`, `Asia/Tashkent`, …  
Guruhlash (`/tasks/grouped/`) va kalendar user timezone bilan hisoblanadi.  
`show_*` flaglar grouped javobda guruhlarni yashirish uchun ishlatiladi.

---

## 8. Tez checklist (frontend)

- [ ] Search natijasidan `list_key` bo‘yicha list ochish
- [ ] Complete dan keyin `next_task` ni UI ga qo‘shish
- [ ] Delete dialog: «Только это» / «Все повторы» → `scope`
- [ ] Attachments multipart upload
- [ ] Calendar: `all_day_tasks` vs `timed_tasks`; undated emas
- [ ] Login/token refresh dan keyin FCM tokenni `/devices/` ga yuborish
- [ ] Android `task_reminders` channel yaratish
- [ ] iOS `OTTER_TASK_REMINDER` category yaratish
- [ ] Notification action: complete / snooze endpointlari
- [ ] Polling fallback + ack
- [ ] Settings da timezone saqlash
- [ ] Matrix settings filtrlari endi serverda ishlaydi

---

## 9. FAQ search

```http
GET /api/v1/help/
GET /api/v1/help/?search=помодоро
```

FAQ Admin panel orqali boshqariladi. Boshlang‘ich savollar migration bilan qo‘shiladi.

---

## 10. Registration email

Email/password va yangi Google akkaunt yaratilganda welcome email avtomatik yuboriladi. SMTP ishlamasa registration bloklanmaydi, xato server logiga yoziladi.

---

## 11. Deploy

```bash
python manage.py migrate planner
python manage.py dispatch_task_reminders
```

Production scheduler (cron/systemd timer) `dispatch_task_reminders` ni **har daqiqada** ishga tushirishi shart.
