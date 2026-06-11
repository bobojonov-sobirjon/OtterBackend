# OTTER — Pomodoro: Quick Start (Frontend)

> Короткий гайд «с нуля до рабочего экрана».  
> Полная документация: [POMODORO_FRONTEND.md](./POMODORO_FRONTEND.md) · [MOBILE_API.md](./MOBILE_API.md)

---

## 1. Что нужно знать за 30 секунд

| Что | Где |
|---|---|
| Base URL (PROD) | `http://159.194.221.54:8005` |
| API prefix | `/api/v1/` |
| Auth | `Authorization: Bearer <access_token>` |
| Swagger | `{BASE_URL}/docs/` |

**Backend не играет музыку.** Он отдаёт `audio_url` — mp3 воспроизводит мобильное приложение.

**Таймер считает клиент.** Backend хранит настройки и историю сессий.

---

## 2. Первый запрос (5 минут)

### Шаг 1 — получить token

```http
POST /api/v1/auth/login/
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "your_password"
}
```

Ответ:

```json
{
  "access": "eyJ...",
  "refresh": "eyJ..."
}
```

Сохраните `access` — он нужен для всех Pomodoro-запросов.

### Шаг 2 — загрузить настройки

```http
GET /api/v1/pomodoro/settings/
Authorization: Bearer eyJ...
```

Вы получите `duration_minutes`, `work_sound`, `timer_end_sound` и `*_detail` с emoji + `audio_url`.

### Шаг 3 — загрузить звуки для UI

```http
GET /api/v1/sounds/?category=work_background
GET /api/v1/sounds/?category=timer_end
```

Готово — можно рисовать экран.

---

## 3. Минимальный экран Pomodoro

```
┌──────────────────────────────────────┐
│  GET /pomodoro/settings/             │  ← при открытии экрана
│  GET /sounds/?category=work_background│
├──────────────────────────────────────┤
│         ⏱  25:00                     │  ← локальный countdown
│   Задача: «Написать отчёт»           │  ← GET /tasks/
│   🌧️ 🌲 ☕ 💨  (фон)                  │  ← tap → PATCH settings
│      ▶  ⏸  ⏹                        │  ← локально + POST state
└──────────────────────────────────────┘
```

---

## 4. Только нужные API (7 штук)

| # | Когда | Method | URL |
|---|---|---|---|
| 1 | Открыли экран | GET | `/api/v1/pomodoro/settings/` |
| 2 | Кнопки фона | GET | `/api/v1/sounds/?category=work_background` |
| 3 | Модалка «Звук завершения» | GET | `/api/v1/sounds/?category=timer_end` |
| 4 | Сохранили настройку | PATCH | `/api/v1/pomodoro/settings/` |
| 5 | Нажали Play | POST | `/api/v1/pomodoro/sessions/` |
| 6 | Play / Pause / Stop / Done | POST | `/api/v1/pomodoro/sessions/{id}/state/` |
| 7 | Выбор задачи | GET | `/api/v1/tasks/?search=...` |

---

## 5. Copy-paste примеры

### Сохранить фоновый звук «Кафе»

```http
PATCH /api/v1/pomodoro/settings/
Authorization: Bearer eyJ...
Content-Type: application/json

{ "work_sound": "coffee" }
```

### Сохранить длительность 25 мин

```http
PATCH /api/v1/pomodoro/settings/
Content-Type: application/json

{ "duration_minutes": 25, "short_break_minutes": 5 }
```

### Старт сессии

```http
POST /api/v1/pomodoro/sessions/
Content-Type: application/json

{ "task": 5, "duration_minutes": 25 }
```

Ответ → `id: 12`. Дальше:

```http
POST /api/v1/pomodoro/sessions/12/state/
Content-Type: application/json

{ "state": "running" }
```

### Завершение таймера

```http
POST /api/v1/pomodoro/sessions/12/state/
Content-Type: application/json

{ "state": "completed" }
```

---

## 6. Логика на клиенте (главное)

```text
Play:
  1. POST /sessions/           → получить id
  2. POST /sessions/{id}/state/ { "state": "running" }
  3. secondsLeft = duration_minutes * 60
  4. Если work_sound != "none" → loop play work_sound_detail.audio_url

Pause:
  POST state "paused" + stop countdown + pause audio

Stop:
  POST state "stopped" + reset UI + stop audio

Timer = 0:
  stop background audio
  play timer_end_sound_detail.audio_url (one-shot)
  POST state "completed"
```

---

## 7. PATCH — что можно отправлять

| Поле | Значения |
|---|---|
| `duration_minutes` | `15`, `20`, `25`, `30`, `45`, `60` |
| `short_break_minutes` | `3`, `5`, `7`, `10` |
| `show_on_lock_screen` | `true` / `false` |
| `timer_end_sound` | key из sounds (`bell`, `chime`, `none`, …) |
| `work_sound` | key из sounds (`rain`, `coffee`, `none`, …) |

Не отправляйте `*_detail` — это read-only.

---

## 8. Частые проблемы

| Проблема | Решение |
|---|---|
| `401 Unauthorized` | Token истёк → `POST /auth/token/refresh/` |
| `audio_url: null` | Админ ещё не загрузил mp3 — preview не играет |
| `400 Bad Request` | Неверный key звука или duration |
| Таймер «дёргается» | Не polling API — считайте секунды локально |

---

## 9. Чеклист «готово к сдаче»

- [ ] Login → token сохранён
- [ ] Экран грузит settings + sounds
- [ ] Фоновые кнопки меняют `work_sound` через PATCH
- [ ] Модалка настроек меняет duration + timer_end_sound
- [ ] Play создаёт session + state `running`
- [ ] Таймер локальный (не с сервера)
- [ ] Фон loop, завершение one-shot
- [ ] Pause / Stop / Completed шлют state
- [ ] Задача выбирается из `GET /tasks/`

---

## 10. Дальше читать

| Документ | Для чего |
|---|---|
| [POMODORO_FRONTEND.md](./POMODORO_FRONTEND.md) | TypeScript типы, UI mapping, pseudo-code |
| [MOBILE_API.md](./MOBILE_API.md) §5.5–5.10 | Полные схемы request/response |
| `{BASE_URL}/docs/` | Swagger — тест запросов в браузере |
