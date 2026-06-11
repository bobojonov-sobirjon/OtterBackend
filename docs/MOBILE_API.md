# OTTER Backend — Mobile API Documentation

> Документация для мобильных разработчиков (Flutter / React Native / Native).
> Все эндпоинты, параметры, типы и примеры запросов/ответов.

---

## 1. General Info

| Параметр | Значение |
|---|---|
| **Project** | OTTER — Planner app backend |
| **Framework** | Django + Django REST Framework (DRF) |
| **Auth** | JWT (SimpleJWT) |
| **API prefix** | `/api/v1/` |
| **Content-Type** | `application/json` (по умолчанию) |
| **Swagger UI** | `/docs/` |
| **OpenAPI schema** | `/schema/` |

### Base URL

| Окружение | URL |
|---|---|
| **DEV (local)** | `http://127.0.0.1:8000` |
| **STAGING** | `https://staging.example.com` |
| **PROD** | `http://159.194.221.54:8005` |

> Мобильное приложение строит URL как: `BASE_URL + /api/v1/...`

### Pagination (списки с пагинацией)

- Тип: `LimitOffsetPagination`
- Параметры query: `limit` (default: 20), `offset` (default: 0)
- Применяется к: `GET /api/v1/tasks/`

---

## 2. Authentication (JWT Flow)

### Как отправлять JWT

Для всех **protected** эндпоинтов добавляйте заголовок:

```
Authorization: Bearer <access_token>
```

### Token lifetime

| Токен | Срок жизни |
|---|---|
| `access` | 7 дней |
| `refresh` | 7 дней |
| Refresh rotation | **ON** (`ROTATE_REFRESH_TOKENS=True`) |

### Общий flow

```
1. POST /auth/register/  или  POST /auth/login/  или  POST /auth/google/
   → получить access + refresh

2. Все запросы:  Authorization: Bearer <access>

3. Если access истёк:
   POST /auth/token/refresh/  { "refresh": "..." }
   → новый access (+ новый refresh при ротации)
```

---

## 3. Этап 1 — Авторизация и профиль

---

### 3.1 Register

| | |
|---|---|
| **METHOD** | `POST` |
| **URL** | `/api/v1/auth/register/` |
| **Auth** | No |
| **Content-Type** | `application/json` |

#### Body params

| Поле | Тип | Required | Default | Описание |
|---|---|---|---|---|
| `email` | string (email) | **да** | — | Email пользователя |
| `password` | string | **да** | — | Пароль, min 8 символов |
| `first_name` | string | нет | `""` | Имя |
| `last_name` | string | нет | `""` | Фамилия |

#### Example request

```json
{
  "email": "user@example.com",
  "password": "StrongPass123!",
  "first_name": "Иван",
  "last_name": "Петров"
}
```

#### Success response `201`

```json
{
  "user": {
    "id": 1,
    "email": "user@example.com",
    "first_name": "Иван",
    "last_name": "Петров",
    "avatar": null
  },
  "tokens": {
    "refresh": "eyJ...refresh_token",
    "access": "eyJ...access_token"
  }
}
```

#### Error `400`

```json
{
  "email": ["Пользователь с таким email уже существует"]
}
```

---

### 3.2 Login

| | |
|---|---|
| **METHOD** | `POST` |
| **URL** | `/api/v1/auth/login/` |
| **Auth** | No |
| **Content-Type** | `application/json` |

#### Body params

| Поле | Тип | Required | Описание |
|---|---|---|---|
| `email` | string (email) | **да** | Email |
| `password` | string | **да** | Пароль |

#### Example request

```json
{
  "email": "user@example.com",
  "password": "StrongPass123!"
}
```

#### Success response `200`

```json
{
  "tokens": {
    "refresh": "eyJ...refresh_token",
    "access": "eyJ...access_token"
  }
}
```

#### Error `400`

```json
{
  "detail": "Неверный email или пароль"
}
```

---

### 3.3 Token Refresh

| | |
|---|---|
| **METHOD** | `POST` |
| **URL** | `/api/v1/auth/token/refresh/` |
| **Auth** | No |
| **Content-Type** | `application/json` |

#### Body params

| Поле | Тип | Required | Описание |
|---|---|---|---|
| `refresh` | string | **да** | Refresh JWT |

#### Example request

```json
{
  "refresh": "eyJ...refresh_token"
}
```

#### Success response `200`

```json
{
  "access": "eyJ...new_access_token",
  "refresh": "eyJ...new_refresh_token"
}
```

> При включённой ротации в ответе также приходит новый `refresh`.

#### Error `401`

Refresh-токен недействителен или просрочен.

---

### 3.4 Google Login (Firebase)

| | |
|---|---|
| **METHOD** | `POST` |
| **URL** | `/api/v1/auth/google/` |
| **Auth** | No |
| **Content-Type** | `application/json` |

#### Body params

| Поле | Тип | Required | Описание |
|---|---|---|---|
| `firebase_token` | string | **да** | Firebase ID Token после Google sign-in |

#### Example request

```json
{
  "firebase_token": "eyJhbGciOiJSUzI1NiIs..."
}
```

#### Success response `200`

```json
{
  "tokens": {
    "refresh": "eyJ...refresh_token",
    "access": "eyJ...access_token"
  },
  "user": {
    "id": 1,
    "email": "user@gmail.com",
    "first_name": "Иван",
    "last_name": "",
    "avatar": null
  }
}
```

#### Error `401`

```json
{
  "detail": "Invalid Firebase ID token."
}
```

---

### 3.5 Forgot Password — Send code

| | |
|---|---|
| **METHOD** | `POST` |
| **URL** | `/api/v1/auth/forgot-password/` |
| **Auth** | No |

#### Body params

| Поле | Тип | Required | Описание |
|---|---|---|---|
| `email` | string (email) | **да** | Email для отправки кода |

#### Example request

```json
{
  "email": "user@example.com"
}
```

#### Success response `200`

> Всегда 200 (без раскрытия существования email).

```json
{
  "detail": "Если email существует, код отправлен"
}
```

---

### 3.6 Forgot Password — Verify code

| | |
|---|---|
| **METHOD** | `POST` |
| **URL** | `/api/v1/auth/forgot-password/verify/` |
| **Auth** | No |

#### Body params

| Поле | Тип | Required | Описание |
|---|---|---|---|
| `email` | string (email) | **да** | Email |
| `code` | string | **да** | 6-значный код (строка) |

#### Example request

```json
{
  "email": "user@example.com",
  "code": "123456"
}
```

#### Success response `200`

```json
{
  "reset_token": "550e8400-e29b-41d4-a716-446655440000"
}
```

#### Error `400`

```json
{
  "detail": "Неверный код или срок истёк"
}
```

---

### 3.7 Forgot Password — Confirm new password

| | |
|---|---|
| **METHOD** | `POST` |
| **URL** | `/api/v1/auth/forgot-password/confirm/` |
| **Auth** | No |

#### Body params

| Поле | Тип | Required | Описание |
|---|---|---|---|
| `reset_token` | string (UUID) | **да** | Токен из шага verify |
| `new_password` | string | **да** | Новый пароль, min 8 |

#### Example request

```json
{
  "reset_token": "550e8400-e29b-41d4-a716-446655440000",
  "new_password": "NewStrongPass123!"
}
```

#### Success response `200`

```json
{
  "detail": "Пароль обновлён"
}
```

---

### 3.8 Get Profile

| | |
|---|---|
| **METHOD** | `GET` |
| **URL** | `/api/v1/profile/` |
| **Auth** | **Bearer required** |

#### Success response `200`

```json
{
  "id": 1,
  "email": "user@example.com",
  "first_name": "Иван",
  "last_name": "Петров",
  "avatar": "http://159.194.221.54:8005/media/avatars/file.jpg"
}
```

---

### 3.9 Update Profile (PUT / PATCH)

| | |
|---|---|
| **METHOD** | `PUT` или `PATCH` |
| **URL** | `/api/v1/profile/` |
| **Auth** | **Bearer required** |
| **Content-Type** | `application/json` или `multipart/form-data` (для avatar) |

#### Body params

| Поле | Тип | Required | Описание |
|---|---|---|---|
| `first_name` | string | нет | Имя |
| `last_name` | string | нет | Фамилия |
| `avatar` | file | нет | Файл изображения (только multipart) |

#### Success response `200`

```json
{
  "id": 1,
  "email": "user@example.com",
  "first_name": "Иван",
  "last_name": "Петров",
  "avatar": "http://159.194.221.54:8005/media/avatars/new.jpg"
}
```

---

### 3.10 Change Password

| | |
|---|---|
| **METHOD** | `POST` |
| **URL** | `/api/v1/profile/change-password/` |
| **Auth** | **Bearer required** |

#### Body params

| Поле | Тип | Required | Описание |
|---|---|---|---|
| `new_password` | string | **да** | Новый пароль, min 8 |

#### Example request

```json
{
  "new_password": "NewStrongPass123!"
}
```

#### Success response `200`

```json
{
  "detail": "Пароль обновлён"
}
```

---

## 4. Этап 2 — Управление задачами (Core)

### Объект Task (общая схема)

| Поле | Тип | Read-only | Default | Описание |
|---|---|---|---|---|
| `id` | integer | да | auto | ID задачи |
| `title` | string | нет | — | Название (max 255) |
| `description` | string \| null | нет | `null` | Описание |
| `due_at` | datetime (ISO 8601) \| null | нет | `null` | Срок выполнения |
| `start_at` | datetime \| null | нет | `null` | Начало (для календаря/длительности) |
| `end_at` | datetime \| null | нет | `null` | Окончание |
| `reminder_at` | datetime \| null | нет | `null` | Время уведомления |
| `repeat_unit` | enum | нет | `"none"` | См. enum ниже |
| `repeat_interval` | integer | нет | `1` | Интервал повтора |
| `priority` | enum | нет | `"medium"` | См. enum ниже |
| `matrix_block` | enum | нет | `"not_urgent_important"` | См. enum ниже |
| `image` | string (URL) \| null | нет | `null` | URL изображения |
| `is_completed` | boolean | нет | `false` | Выполнена |
| `completed_at` | datetime \| null | да | `null` | Дата выполнения |
| `created_at` | datetime | да | auto | Дата создания |
| `updated_at` | datetime | да | auto | Дата обновления |

#### Enum: `priority`

| Значение | Описание |
|---|---|
| `low` | Низкий |
| `medium` | Средний |
| `high` | Высокий |
| `critical` | Критичный |

#### Enum: `matrix_block`

| Значение | Описание |
|---|---|
| `urgent_important` | Срочно и важно |
| `not_urgent_important` | Не срочно и важно |
| `urgent_not_important` | Срочно и не важно |
| `not_urgent_not_important` | Не срочно и не важно |

#### Enum: `repeat_unit`

| Значение | Описание |
|---|---|
| `none` | Без повтора |
| `day` | День |
| `week` | Неделя |
| `month` | Месяц |
| `year` | Год |

---

### 4.1 List Tasks

| | |
|---|---|
| **METHOD** | `GET` |
| **URL** | `/api/v1/tasks/` |
| **Auth** | **Bearer required** |

#### Query params

| Параметр | Тип | Required | Default | Описание |
|---|---|---|---|---|
| `search` | string | нет | — | Поиск по title/description |
| `is_completed` | string | нет | — | `"true"` или `"false"` |
| `matrix_block` | enum | нет | — | Фильтр по блоку матрицы |
| `limit` | integer | нет | `20` | Пагинация |
| `offset` | integer | нет | `0` | Пагинация |

#### Success response `200`

```json
{
  "count": 42,
  "next": "http://.../api/v1/tasks/?limit=20&offset=20",
  "previous": null,
  "results": [
    {
      "id": 1,
      "title": "Купить продукты",
      "description": null,
      "due_at": "2026-05-30T18:00:00+03:00",
      "start_at": null,
      "end_at": null,
      "reminder_at": "2026-05-30T17:30:00+03:00",
      "repeat_unit": "none",
      "repeat_interval": 1,
      "priority": "medium",
      "matrix_block": "not_urgent_important",
      "image": null,
      "is_completed": false,
      "completed_at": null,
      "created_at": "2026-05-28T10:00:00+03:00",
      "updated_at": "2026-05-28T10:00:00+03:00"
    }
  ]
}
```

---

### 4.2 Create Task

| | |
|---|---|
| **METHOD** | `POST` |
| **URL** | `/api/v1/tasks/` |
| **Auth** | **Bearer required** |
| **Content-Type** | `application/json` или `multipart/form-data` (если есть image) |

#### Body params

| Поле | Тип | Required | Default | Описание |
|---|---|---|---|---|
| `title` | string | **да** | — | Название задачи |
| `description` | string | нет | `null` | Описание |
| `due_at` | datetime | нет | `null` | Срок (если нет → «Без срока») |
| `start_at` | datetime | нет | `null` | Начало |
| `end_at` | datetime | нет | `null` | Окончание |
| `reminder_at` | datetime | нет | `null` | Напоминание |
| `repeat_unit` | enum | нет | `"none"` | Повтор |
| `repeat_interval` | integer | нет | `1` | Интервал |
| `priority` | enum | нет | `"medium"` | Приоритет |
| `matrix_block` | enum | нет | `"not_urgent_important"` | Блок матрицы |
| `image` | file | нет | `null` | Изображение (multipart) |

#### Example request (JSON)

```json
{
  "title": "Подготовить отчёт",
  "due_at": "2026-05-30T15:00:00+03:00",
  "priority": "high",
  "reminder_at": "2026-05-30T14:30:00+03:00"
}
```

#### Success response `201`

Полный объект Task (см. схему выше).

---

### 4.3 Get Task

| | |
|---|---|
| **METHOD** | `GET` |
| **URL** | `/api/v1/tasks/{id}/` |
| **Auth** | **Bearer required** |

#### Success response `200`

Полный объект Task.

---

### 4.4 Update Task (PUT / PATCH)

| | |
|---|---|
| **METHOD** | `PUT` или `PATCH` |
| **URL** | `/api/v1/tasks/{id}/` |
| **Auth** | **Bearer required** |

#### Body params

Те же поля, что при создании. `PATCH` — только переданные поля.

#### Success response `200`

Полный объект Task.

---

### 4.5 Delete Task

| | |
|---|---|
| **METHOD** | `DELETE` |
| **URL** | `/api/v1/tasks/{id}/` |
| **Auth** | **Bearer required** |

#### Success response `204`

Пустое тело.

> Аналог свайпа влево в мобильном приложении.

---

### 4.6 Grouped Tasks (системные списки)

| | |
|---|---|
| **METHOD** | `GET` |
| **URL** | `/api/v1/tasks/grouped/` |
| **Auth** | **Bearer required** |

Возвращает задачи в 6 группах по логике ТЗ:

| key | title (RU) | Логика |
|---|---|---|
| `overdue` | Просрочено | `due_at < now` и не выполнена |
| `today` | Сегодня | срок = сегодня |
| `tomorrow` | Завтра | срок = завтра |
| `later` | Позже | срок > завтра |
| `no_deadline` | Без срока | `due_at = null` |
| `completed` | Выполнено | `is_completed = true` |

#### Success response `200`

```json
[
  {
    "key": "overdue",
    "title": "Просрочено",
    "count": 2,
    "tasks": [ /* массив Task */ ]
  },
  {
    "key": "today",
    "title": "Сегодня",
    "count": 5,
    "tasks": [ /* ... */ ]
  },
  {
    "key": "tomorrow",
    "title": "Завтра",
    "count": 3,
    "tasks": [ /* ... */ ]
  },
  {
    "key": "later",
    "title": "Позже",
    "count": 10,
    "tasks": [ /* ... */ ]
  },
  {
    "key": "no_deadline",
    "title": "Без срока",
    "count": 1,
    "tasks": [ /* ... */ ]
  },
  {
    "key": "completed",
    "title": "Выполнено",
    "count": 7,
    "tasks": [ /* ... */ ]
  }
]
```

---

### 4.7 Complete Task

| | |
|---|---|
| **METHOD** | `POST` |
| **URL** | `/api/v1/tasks/{id}/complete/` |
| **Auth** | **Bearer required** |
| **Body** | пустое |

> Аналог свайпа вправо.

#### Success response `200`

Полный объект Task с `is_completed: true`.

---

### 4.8 Uncomplete Task

| | |
|---|---|
| **METHOD** | `POST` |
| **URL** | `/api/v1/tasks/{id}/uncomplete/` |
| **Auth** | **Bearer required** |
| **Body** | пустое |

#### Success response `200`

Полный объект Task с `is_completed: false`.

---

## 5. Этап 3 — Календарь, Матрица, Помодоро

> **Frontend (Pomodoro):** [POMODORO_BEGIN.md](./POMODORO_BEGIN.md) (быстрый старт) · [POMODORO_FRONTEND.md](./POMODORO_FRONTEND.md) (полный гайд)

---

### 5.1 Calendar — Get tasks by view

| | |
|---|---|
| **METHOD** | `GET` |
| **URL** | `/api/v1/calendar/` |
| **Auth** | **Bearer required** |

#### Query params

| Параметр | Тип | Required | Default | Описание |
|---|---|---|---|---|
| `view` | enum | **да** | `"day"` | `day` \| `week` \| `month` \| `year` |
| `date` | string | **да** | — | Опорная дата, формат `YYYY-MM-DD` |

#### Example

```
GET /api/v1/calendar/?view=week&date=2026-05-30
```

#### Success response `200`

```json
{
  "view": "week",
  "date": "2026-05-30",
  "range_start": "2026-05-26",
  "range_end": "2026-06-02",
  "tasks": [ /* массив Task */ ]
}
```

#### Error `400`

```json
{
  "date": ["Параметр date обязателен."]
}
```

---

### 5.2 Matrix — Get blocks with tasks

| | |
|---|---|
| **METHOD** | `GET` |
| **URL** | `/api/v1/matrix/` |
| **Auth** | **Bearer required** |

Возвращает 4 блока матрицы Эйзенхауэра с задачами.

#### Success response `200`

```json
[
  {
    "block": "urgent_important",
    "title": "Срочно и важно",
    "allowed_priorities": [],
    "date_filter": "",
    "count": 3,
    "tasks": [ /* массив Task (только активные) */ ]
  },
  {
    "block": "not_urgent_important",
    "title": "Не срочно и важно",
    "allowed_priorities": [],
    "date_filter": "",
    "count": 5,
    "tasks": [ /* ... */ ]
  },
  {
    "block": "urgent_not_important",
    "title": "Срочно и не важно",
    "allowed_priorities": [],
    "date_filter": "",
    "count": 1,
    "tasks": [ /* ... */ ]
  },
  {
    "block": "not_urgent_not_important",
    "title": "Не срочно и не важно",
    "allowed_priorities": [],
    "date_filter": "",
    "count": 2,
    "tasks": [ /* ... */ ]
  }
]
```

---

### 5.3 Matrix Settings — Get

| | |
|---|---|
| **METHOD** | `GET` |
| **URL** | `/api/v1/matrix/settings/` |
| **Auth** | **Bearer required** |

#### Success response `200`

```json
[
  {
    "id": 1,
    "block": "urgent_important",
    "title": "Срочно и важно",
    "allowed_priorities": ["high", "critical"],
    "date_filter": "today"
  }
]
```

---

### 5.4 Matrix Settings — Update block

| | |
|---|---|
| **METHOD** | `PATCH` |
| **URL** | `/api/v1/matrix/settings/` |
| **Auth** | **Bearer required** |

#### Body params

| Поле | Тип | Required | Описание |
|---|---|---|---|
| `block` | enum | **да** | Код блока (см. matrix_block enum) |
| `title` | string | нет | Название блока |
| `allowed_priorities` | array[string] | нет | Разрешённые приоритеты |
| `date_filter` | string | нет | Фильтр по дате |

#### Example request

```json
{
  "block": "urgent_important",
  "title": "Срочно и важно",
  "allowed_priorities": ["high", "critical"],
  "date_filter": "today"
}
```

#### Success response `200`

Обновлённый объект настройки блока.

---

### 5.5 Sound Catalog — List

| | |
|---|---|
| **METHOD** | `GET` |
| **URL** | `/api/v1/sounds/` |
| **Auth** | **Bearer required** |

#### Query params

| Параметр | Тип | Required | Описание |
|---|---|---|---|
| `category` | enum | нет | `timer_end` \| `work_background` \| `notification` \| `completion` |

#### Example

```
GET /api/v1/sounds/?category=work_background
```

#### Success response `200`

```json
[
  {
    "key": "rain",
    "category": "work_background",
    "title": "Дождь",
    "emoji": "🌧️",
    "audio_url": "http://159.194.221.54:8005/media/sounds/rain.mp3",
    "sort_order": 1
  },
  {
    "key": "none",
    "category": "work_background",
    "title": "Без звука",
    "emoji": "🔇",
    "audio_url": null,
    "sort_order": 99
  }
]
```

| Поле | Тип | Описание |
|---|---|---|
| `key` | string | Ключ для сохранения в настройках (`timer_end_sound`, `work_sound`, …) |
| `category` | string | Категория звука |
| `title` | string | Подпись в UI (например «Колокольчик») |
| `emoji` | string | Emoji для кнопки выбора |
| `audio_url` | string \| null | URL аудиофайла с сервера (`null` пока файл не загружен в админке) |
| `sort_order` | integer | Порядок в списке |

#### Enum: `category`

| Значение | Где используется |
|---|---|
| `timer_end` | Настройки помодоро — «Звук завершения» |
| `work_background` | Экран помодоро — «Звук фоновый» |
| `notification` | Настройки — «Звук уведомления» |
| `completion` | Настройки — «Звук завершения» задачи |

#### Ключи по умолчанию (макет)

**timer_end:** `bell`, `chime`, `success`, `ding`, `soft`, `none`  
**work_background:** `rain`, `forest`, `coffee`, `wind`, `none`  
**notification:** `default`, `gentle`, `alert`, `none`  
**completion:** `default`, `chime`, `pop`, `none`

> Аудиофайлы загружаются в Django Admin → «Звуки». Мобильный клиент для preview и воспроизведения использует `audio_url` из каталога.

---

### 5.6 Pomodoro Settings — Get

| | |
|---|---|
| **METHOD** | `GET` |
| **URL** | `/api/v1/pomodoro/settings/` |
| **Auth** | **Bearer required** |

#### Success response `200`

```json
{
  "duration_minutes": 30,
  "short_break_minutes": 5,
  "show_on_lock_screen": true,
  "timer_end_sound": "bell",
  "timer_end_sound_detail": {
    "key": "bell",
    "category": "timer_end",
    "title": "Колокольчик",
    "emoji": "🔔",
    "audio_url": "http://159.194.221.54:8005/media/sounds/bell.mp3",
    "sort_order": 1
  },
  "work_sound": "coffee",
  "work_sound_detail": {
    "key": "coffee",
    "category": "work_background",
    "title": "Кафе",
    "emoji": "☕",
    "audio_url": "http://159.194.221.54:8005/media/sounds/coffee.mp3",
    "sort_order": 3
  }
}
```

| Поле | Тип | Default | Описание |
|---|---|---|---|
| `duration_minutes` | integer | `30` | Длительность таймера (мин). Допустимо: 15, 20, 25, 30, 45, 60 |
| `short_break_minutes` | integer | `5` | Короткий перерыв (мин). Допустимо: 3, 5, 7, 10 |
| `show_on_lock_screen` | boolean | `true` | Показывать на экране блокировки |
| `timer_end_sound` | string | `"bell"` | Ключ звука завершения (см. `GET /sounds/?category=timer_end`) |
| `timer_end_sound_detail` | object | — | **read-only** — emoji, title, audio_url |
| `work_sound` | string | `"none"` | Ключ фонового звука (см. `GET /sounds/?category=work_background`) |
| `work_sound_detail` | object | — | **read-only** — emoji, title, audio_url |

---

### 5.7 Pomodoro Settings — Update

| | |
|---|---|
| **METHOD** | `PATCH` |
| **URL** | `/api/v1/pomodoro/settings/` |
| **Auth** | **Bearer required** |

#### Body params

Любое из полей выше (частичное обновление).

#### Success response `200`

Обновлённый объект настроек.

---

### 5.8 Pomodoro Sessions — List

| | |
|---|---|
| **METHOD** | `GET` |
| **URL** | `/api/v1/pomodoro/sessions/` |
| **Auth** | **Bearer required** |

#### Success response `200`

```json
[
  {
    "id": 1,
    "task": 5,
    "duration_minutes": 30,
    "state": "completed",
    "started_at": "2026-05-30T14:00:00+03:00",
    "ended_at": "2026-05-30T14:30:00+03:00",
    "created_at": "2026-05-30T13:59:00+03:00"
  }
]
```

#### Enum: `state`

| Значение | Описание |
|---|---|
| `idle` | Ожидание |
| `running` | Запущен |
| `paused` | На паузе |
| `stopped` | Остановлен |
| `completed` | Завершён |

---

### 5.9 Pomodoro Sessions — Create

| | |
|---|---|
| **METHOD** | `POST` |
| **URL** | `/api/v1/pomodoro/sessions/` |
| **Auth** | **Bearer required** |

#### Body params

| Поле | Тип | Required | Default | Описание |
|---|---|---|---|---|
| `task` | integer | нет | `null` | ID задачи для фокуса |
| `duration_minutes` | integer | нет | `30` | Длительность |
| `state` | enum | нет | `"idle"` | Начальное состояние |

#### Example request

```json
{
  "task": 5,
  "duration_minutes": 25
}
```

#### Success response `201`

Объект сессии.

---

### 5.10 Pomodoro Session — Change state

| | |
|---|---|
| **METHOD** | `POST` |
| **URL** | `/api/v1/pomodoro/sessions/{session_id}/state/` |
| **Auth** | **Bearer required** |

#### Body params

| Поле | Тип | Required | Описание |
|---|---|---|---|
| `state` | enum | **да** | `running` \| `paused` \| `stopped` \| `completed` |

#### Example request

```json
{
  "state": "running"
}
```

#### Success response `200`

Обновлённый объект сессии.

---

## 6. Этап 4 — Настройки, Премиум, Помощь, Юридические документы

---

### 6.1 App Settings — Get

| | |
|---|---|
| **METHOD** | `GET` |
| **URL** | `/api/v1/settings/` |
| **Auth** | **Bearer required** |

#### Success response `200`

```json
{
  "language": "ru",
  "show_overdue": true,
  "show_today": true,
  "show_tomorrow": true,
  "show_later": true,
  "show_no_deadline": true,
  "show_completed": true,
  "bottom_tabs": ["tasks", "calendar", "matrix", "pomodoro", "settings"],
  "notification_sound": "default",
  "notification_sound_detail": {
    "key": "default",
    "category": "notification",
    "title": "По умолчанию",
    "emoji": "🔔",
    "audio_url": null,
    "sort_order": 0
  },
  "completion_sound": "default",
  "completion_sound_detail": {
    "key": "default",
    "category": "completion",
    "title": "По умолчанию",
    "emoji": "✅",
    "audio_url": null,
    "sort_order": 0
  },
  "vibration_enabled": true,
  "is_premium": false,
  "premium_activated_at": null
}
```

| Поле | Тип | Default | Описание |
|---|---|---|---|
| `language` | string | `"ru"` | Язык интерфейса |
| `show_overdue` | boolean | `true` | Показывать «Просрочено» |
| `show_today` | boolean | `true` | Показывать «Сегодня» |
| `show_tomorrow` | boolean | `true` | Показывать «Завтра» |
| `show_later` | boolean | `true` | Показывать «Позже» |
| `show_no_deadline` | boolean | `true` | Показывать «Без срока» |
| `show_completed` | boolean | `true` | Показывать «Выполнено» |
| `bottom_tabs` | array[string] | см. выше | Порядок вкладок нижнего меню |
| `notification_sound` | string | `"default"` | Ключ звука уведомления (`GET /sounds/?category=notification`) |
| `notification_sound_detail` | object | — | **read-only** — emoji, title, audio_url |
| `completion_sound` | string | `"default"` | Ключ звука завершения задачи (`GET /sounds/?category=completion`) |
| `completion_sound_detail` | object | — | **read-only** — emoji, title, audio_url |
| `vibration_enabled` | boolean | `true` | Вибрация при уведомлении |
| `is_premium` | boolean | `false` | **read-only** — премиум статус |
| `premium_activated_at` | datetime \| null | `null` | **read-only** — дата активации |

#### Enum: `bottom_tabs` values

`tasks`, `calendar`, `matrix`, `pomodoro`, `settings`

---

### 6.2 App Settings — Update

| | |
|---|---|
| **METHOD** | `PATCH` |
| **URL** | `/api/v1/settings/` |
| **Auth** | **Bearer required** |

#### Body params

Любое из полей выше, кроме read-only (`is_premium`, `premium_activated_at`).

#### Example request

```json
{
  "show_completed": false,
  "bottom_tabs": ["tasks", "pomodoro", "calendar", "matrix", "settings"],
  "vibration_enabled": false
}
```

#### Success response `200`

Обновлённый объект настроек.

---

### 6.3 Settings Stub (функции в разработке)

| | |
|---|---|
| **METHOD** | `POST` |
| **URL** | `/api/v1/settings/stub-action/` |
| **Auth** | **Bearer required** |
| **Body** | пустое |

Для пунктов меню: «Вид», «Дата и время», «Интеграция и импорт», «Управление устройствами» и т.д.

#### Success response `202`

```json
{
  "detail": "Уже разрабатываем, скоро будет готово :)"
}
```

---

### 6.4 Help Center — FAQ

| | |
|---|---|
| **METHOD** | `GET` |
| **URL** | `/api/v1/help/` |
| **Auth** | **Bearer required** |

#### Success response `200`

```json
[
  {
    "question": "Как создать задачу?",
    "answer": "Нажмите кнопку + на главной странице."
  },
  {
    "question": "Как работает помодоро?",
    "answer": "Выберите задачу, нажмите старт и работайте до сигнала."
  }
]
```

---

### 6.5 Help Center — Send message

| | |
|---|---|
| **METHOD** | `POST` |
| **URL** | `/api/v1/help/` |
| **Auth** | **Bearer required** |
| **Content-Type** | `application/json` или `multipart/form-data` |

#### Body params

| Поле | Тип | Required | Описание |
|---|---|---|---|
| `message` | string | **да** | Текст обращения |
| `screenshot` | file | нет | Скриншот (multipart) |

#### Example request (JSON)

```json
{
  "message": "Не могу синхронизировать задачи"
}
```

#### Success response `201`

```json
{
  "id": 1,
  "message": "Не могу синхронизировать задачи",
  "screenshot": null,
  "created_at": "2026-05-30T12:00:00+03:00"
}
```

---

### 6.6 Premium — Checkout

| | |
|---|---|
| **METHOD** | `POST` |
| **URL** | `/api/v1/premium/checkout/` |
| **Auth** | **Bearer required** |

#### Body params

| Поле | Тип | Required | Default | Описание |
|---|---|---|---|---|
| `tariff` | string | нет | `"monthly"` | Тарифный план |

#### Example request

```json
{
  "tariff": "monthly"
}
```

#### Success response `200`

```json
{
  "checkout_url": "https://auth.robokassa.ru/Merchant/Index.aspx?tariff=monthly&user=1",
  "provider": "robokassa"
}
```

> Мобильное приложение открывает `checkout_url` в WebView / браузере.

---

### 6.7 Premium — Activate

| | |
|---|---|
| **METHOD** | `POST` |
| **URL** | `/api/v1/premium/activate/` |
| **Auth** | **Bearer required** |
| **Body** | пустое |

Вызывается после успешной оплаты.

#### Success response `200`

```json
{
  "language": "ru",
  "show_overdue": true,
  "show_today": true,
  "show_tomorrow": true,
  "show_later": true,
  "show_no_deadline": true,
  "show_completed": true,
  "bottom_tabs": ["tasks", "calendar", "matrix", "pomodoro", "settings"],
  "notification_sound": "default",
  "completion_sound": "default",
  "vibration_enabled": true,
  "is_premium": true,
  "premium_activated_at": "2026-05-30T15:00:00+03:00"
}
```

---

### 6.8 Premium — Feature flags

| | |
|---|---|
| **METHOD** | `GET` |
| **URL** | `/api/v1/premium/features/` |
| **Auth** | **Bearer required** |

#### Success response `200`

```json
[
  {
    "key": "calendar_week_view",
    "title": "Календарь — вид «Неделя»",
    "is_premium": true,
    "is_enabled": true
  }
]
```

---

### 6.9 Legal Documents

| | |
|---|---|
| **METHOD** | `GET` |
| **URL** | `/api/v1/legal/documents/` |
| **Auth** | No |

#### Success response `200`

```json
[
  {
    "doc_type": "offer",
    "title": "Публичная оферта",
    "content": "Текст оферты...",
    "updated_at": "2026-05-01T00:00:00+03:00"
  },
  {
    "doc_type": "privacy",
    "title": "Политика конфиденциальности",
    "content": "Текст политики...",
    "updated_at": "2026-05-01T00:00:00+03:00"
  },
  {
    "doc_type": "refund",
    "title": "Политика возвратов",
    "content": "Текст политики возвратов...",
    "updated_at": "2026-05-01T00:00:00+03:00"
  },
  {
    "doc_type": "personal_data",
    "title": "Согласие на обработку ПДн",
    "content": "Текст согласия...",
    "updated_at": "2026-05-01T00:00:00+03:00"
  }
]
```

#### Enum: `doc_type`

| Значение | Описание |
|---|---|
| `offer` | Публичная оферта |
| `privacy` | Политика конфиденциальности |
| `refund` | Политика возвратов |
| `personal_data` | Согласие на обработку ПДн |

---

## 7. Общие ошибки

| HTTP | Описание |
|---|---|
| **400** | Ошибка валидации. Формат: `{ "field": ["сообщение"] }` или `{ "detail": "..." }` |
| **401** | Access-токен отсутствует, некорректен или истёк |
| **403** | Нет прав доступа |
| **404** | Объект не найден |
| **429** | Rate limit превышен |

---

## 8. Quick Checklist для мобильного фронтенда

- [ ] Хранить `access` и `refresh` токены в secure storage
- [ ] Отправлять `Authorization: Bearer <access>` во всех protected запросах
- [ ] При `401` — обновлять через `POST /auth/token/refresh/`
- [ ] Avatar / image upload — использовать `multipart/form-data`
- [ ] Datetime — ISO 8601 с timezone (`2026-05-30T15:00:00+03:00`)
- [ ] Главный экран задач — `GET /tasks/grouped/`
- [ ] Свайп вправо (complete) — `POST /tasks/{id}/complete/`
- [ ] Свайп влево (delete) — `DELETE /tasks/{id}/`
- [ ] Календарь — `GET /calendar/?view=day&date=YYYY-MM-DD`
- [ ] Матрица — `GET /matrix/`
- [ ] Каталог звуков — `GET /sounds/?category=...` (emoji + audio_url)
- [ ] Помодоро — settings + sessions + state
- [ ] Настройки — `GET/PATCH /settings/`
- [ ] Премиум — checkout → WebView → activate
- [ ] Юридические документы — `GET /legal/documents/` (без auth)

---

## 9. Полный список эндпоинтов (сводка)

| # | Method | URL | Auth | Этап |
|---|---|---|---|---|
| 1 | POST | `/api/v1/auth/register/` | No | 1 |
| 2 | POST | `/api/v1/auth/login/` | No | 1 |
| 3 | POST | `/api/v1/auth/token/refresh/` | No | 1 |
| 4 | POST | `/api/v1/auth/google/` | No | 1 |
| 5 | POST | `/api/v1/auth/forgot-password/` | No | 1 |
| 6 | POST | `/api/v1/auth/forgot-password/verify/` | No | 1 |
| 7 | POST | `/api/v1/auth/forgot-password/confirm/` | No | 1 |
| 8 | GET | `/api/v1/profile/` | Yes | 1 |
| 9 | PUT/PATCH | `/api/v1/profile/` | Yes | 1 |
| 10 | POST | `/api/v1/profile/change-password/` | Yes | 1 |
| 11 | GET | `/api/v1/tasks/` | Yes | 2 |
| 12 | POST | `/api/v1/tasks/` | Yes | 2 |
| 13 | GET | `/api/v1/tasks/{id}/` | Yes | 2 |
| 14 | PUT/PATCH | `/api/v1/tasks/{id}/` | Yes | 2 |
| 15 | DELETE | `/api/v1/tasks/{id}/` | Yes | 2 |
| 16 | GET | `/api/v1/tasks/grouped/` | Yes | 2 |
| 17 | POST | `/api/v1/tasks/{id}/complete/` | Yes | 2 |
| 18 | POST | `/api/v1/tasks/{id}/uncomplete/` | Yes | 2 |
| 19 | GET | `/api/v1/calendar/` | Yes | 3 |
| 20 | GET | `/api/v1/matrix/` | Yes | 3 |
| 21 | GET | `/api/v1/matrix/settings/` | Yes | 3 |
| 22 | PATCH | `/api/v1/matrix/settings/` | Yes | 3 |
| 23 | GET | `/api/v1/sounds/` | Yes | 3 |
| 24 | GET | `/api/v1/pomodoro/settings/` | Yes | 3 |
| 25 | PATCH | `/api/v1/pomodoro/settings/` | Yes | 3 |
| 26 | GET | `/api/v1/pomodoro/sessions/` | Yes | 3 |
| 27 | POST | `/api/v1/pomodoro/sessions/` | Yes | 3 |
| 28 | POST | `/api/v1/pomodoro/sessions/{id}/state/` | Yes | 3 |
| 29 | GET | `/api/v1/settings/` | Yes | 4 |
| 30 | PATCH | `/api/v1/settings/` | Yes | 4 |
| 31 | POST | `/api/v1/settings/stub-action/` | Yes | 4 |
| 32 | GET | `/api/v1/help/` | Yes | 4 |
| 33 | POST | `/api/v1/help/` | Yes | 4 |
| 34 | POST | `/api/v1/premium/checkout/` | Yes | 4 |
| 35 | POST | `/api/v1/premium/activate/` | Yes | 4 |
| 36 | GET | `/api/v1/premium/features/` | Yes | 4 |
| 37 | GET | `/api/v1/legal/documents/` | No | 4 |
