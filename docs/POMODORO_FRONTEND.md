# OTTER — Pomodoro (Frontend / Mobile)

> Документация для мобильного фронтенда: экран «Помодоро», звуки, таймер, сессии.  
> **Быстрый старт:** [POMODORO_BEGIN.md](./POMODORO_BEGIN.md) · **Полная API:** [MOBILE_API.md](./MOBILE_API.md)

---

## 1. Базовые параметры

| Параметр | Значение |
|---|---|
| **Base URL (PROD)** | `https://admin.ottertime.ru` |
| **Base URL (DEV)** | `http://127.0.0.1:8000` |
| **Prefix** | `/api/v1/` |
| **Auth** | JWT — заголовок `Authorization: Bearer <access_token>` |
| **Content-Type** | `application/json` |
| **Swagger** | `{BASE_URL}/docs/` |

Все эндпоинты ниже — **protected** (нужен access token).

---

## 2. Архитектура (важно для фронта)

```
┌─────────────────────────────────────────────────────────┐
│  Backend API                                            │
│  • Каталог звуков (emoji + audio_url)                   │
│  • Настройки пользователя (какой key выбран)            │
│  • История сессий                                       │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│  Mobile App (ваша зона ответственности)                 │
│  • Отсчёт секунд таймера                                │
│  • Воспроизведение mp3 по audio_url                     │
│  • Loop фонового звука                                  │
│  • Звук при завершении таймера                          │
│  • Lock screen / background audio (OS permissions)      │
└─────────────────────────────────────────────────────────┘
```

**Mp3 файлы не вшиты в приложение.** URL приходит с сервера в поле `audio_url`.  
Если `audio_url === null` — админ ещё не загрузил файл (можно показать заглушку или скрыть preview).

---

## 3. TypeScript типы (рекомендуемые)

```typescript
type SoundCategory = "timer_end" | "work_background" | "notification" | "completion";

interface Sound {
  key: string;
  category: SoundCategory;
  title: string;
  emoji: string;
  audio_url: string | null;
  sort_order: number;
}

interface PomodoroSettings {
  duration_minutes: number;       // 15 | 20 | 25 | 30 | 45 | 60
  short_break_minutes: number;    // 3 | 5 | 7 | 10
  show_on_lock_screen: boolean;
  timer_end_sound: string;        // key, напр. "bell"
  timer_end_sound_detail: Sound;  // read-only
  work_sound: string;             // key, напр. "coffee" | "none"
  work_sound_detail: Sound;       // read-only
}

type PomodoroSessionState = "idle" | "running" | "paused" | "stopped" | "completed";

interface PomodoroSession {
  id: number;
  task: number | null;
  duration_minutes: number;
  state: PomodoroSessionState;
  started_at: string | null;  // ISO 8601
  ended_at: string | null;
  created_at: string;
}
```

---

## 4. Эндпоинты Pomodoro

### 4.1 Каталог звуков

| | |
|---|---|
| **GET** | `/api/v1/sounds/` |
| **Query** | `category` (optional) |

**Примеры:**

```http
GET /api/v1/sounds/?category=work_background
GET /api/v1/sounds/?category=timer_end
```

**Response `200`:**

```json
[
  {
    "key": "coffee",
    "category": "work_background",
    "title": "Кафе",
    "emoji": "☕",
    "audio_url": "https://admin.ottertime.ru/media/sounds/coffee.mp3",
    "sort_order": 3
  }
]
```

| `category` | UI (по макету) |
|---|---|
| `work_background` | Полоска «Звук фоновый» на главном экране помодоро |
| `timer_end` | Модалка «Настройки Помодоро» → «Звук завершения» |

**Дефолтные key (если кэшируете локально):**

| category | keys |
|---|---|
| `timer_end` | `bell`, `chime`, `success`, `ding`, `soft`, `none` |
| `work_background` | `rain`, `forest`, `coffee`, `wind`, `none` |

---

### 4.2 Настройки помодоро

| | |
|---|---|
| **GET** | `/api/v1/pomodoro/settings/` |
| **PATCH** | `/api/v1/pomodoro/settings/` |

**GET — Response `200`:**

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
    "audio_url": "https://admin.ottertime.ru/media/sounds/bell.mp3",
    "sort_order": 1
  },
  "work_sound": "none",
  "work_sound_detail": {
    "key": "none",
    "category": "work_background",
    "title": "Без звука",
    "emoji": "🔇",
    "audio_url": null,
    "sort_order": 99
  }
}
```

**PATCH — Body (частичное обновление):**

```json
{
  "duration_minutes": 25,
  "short_break_minutes": 5,
  "show_on_lock_screen": true,
  "timer_end_sound": "chime",
  "work_sound": "rain"
}
```

| Поле | PATCH | Допустимые значения |
|---|---|---|
| `duration_minutes` | ✅ | `15`, `20`, `25`, `30`, `45`, `60` |
| `short_break_minutes` | ✅ | `3`, `5`, `7`, `10` |
| `show_on_lock_screen` | ✅ | `true` / `false` |
| `timer_end_sound` | ✅ | key из `GET /sounds/?category=timer_end` |
| `work_sound` | ✅ | key из `GET /sounds/?category=work_background` |
| `*_detail` | ❌ | read-only, не отправлять |

**Ошибка `400`:** неверный key или недопустимая длительность.

---

### 4.3 Сессии помодоро

| Действие | Method | URL |
|---|---|---|
| Список | GET | `/api/v1/pomodoro/sessions/` |
| Создать | POST | `/api/v1/pomodoro/sessions/` |
| Сменить state | POST | `/api/v1/pomodoro/sessions/{id}/state/` |

**POST create — Body:**

```json
{
  "task": 5,
  "duration_minutes": 25
}
```

| Поле | Required | Default | Описание |
|---|---|---|---|
| `task` | нет | `null` | ID задачи для фокуса |
| `duration_minutes` | нет | `30` | Длительность сессии |
| `state` | нет | `"idle"` | Обычно не передавать при создании |

**POST state — Body:**

```json
{ "state": "running" }
```

| `state` | Когда вызывать |
|---|---|
| `running` | Нажали Play / продолжили после паузы |
| `paused` | Нажали Pause |
| `stopped` | Нажали Stop (сброс таймера) |
| `completed` | Таймер дошёл до 0 |

> **Таймер считает секунды на клиенте.** Backend хранит только метаданные сессии и timestamps.

---

### 4.4 Выбор задачи для фокуса

Задачи для поиска «Выбрать задачу…»:

```http
GET /api/v1/tasks/?search=текст&is_completed=false
```

Или grouped:

```http
GET /api/v1/tasks/grouped/
```

Выбранный `task.id` передаётся в `POST /api/v1/pomodoro/sessions/`.

---

## 5. Привязка к UI (макет)

### 5.1 Главный экран «Помодоро»

| UI элемент | API |
|---|---|
| Кольцо таймера + цифры | Локально: `duration_minutes` из settings |
| «Задача для фокуса» | `GET /tasks/` + `POST /pomodoro/sessions/` с `task` |
| «Звук фоновый» (🌧️ 🌲 ☕ 💨) | `GET /sounds/?category=work_background` |
| Выбранный фон | `PATCH /pomodoro/settings/` → `work_sound` |
| Play / Pause / Stop | Локальный таймер + `POST .../sessions/{id}/state/` |
| Фоновая музыка при Play | `work_sound_detail.audio_url` (loop) |
| Звук при 0:00 | `timer_end_sound_detail.audio_url` (one-shot) |

### 5.2 Модалка «Настройки Помодоро»

| UI элемент | API |
|---|---|
| Длительность: 15/20/25/30/45/60 | `PATCH` → `duration_minutes` |
| Короткий перерыв: 3/5/7/10 | `PATCH` → `short_break_minutes` |
| Показывать при блокировке | `PATCH` → `show_on_lock_screen` |
| Звук завершения (🔔 🎵 ✅ …) | `GET /sounds/?category=timer_end` + `PATCH` → `timer_end_sound` |
| Preview звука при tap | Воспроизвести `audio_url` из каталога |
| Кнопка «Готово» | Один или несколько `PATCH /pomodoro/settings/` |

---

## 6. Recommended flow (пошагово)

### При открытии экрана

```text
1. GET /api/v1/pomodoro/settings/     → текущие настройки + detail
2. GET /api/v1/sounds/?category=work_background
3. GET /api/v1/sounds/?category=timer_end   (можно кэшировать)
```

### Выбор фонового звука

```text
1. Пользователь tap ☕
2. PATCH /api/v1/pomodoro/settings/  { "work_sound": "coffee" }
3. Если таймер уже running → переключить player на новый audio_url
```

### Старт таймера

```text
1. POST /api/v1/pomodoro/sessions/  { "task": 5, "duration_minutes": 25 }
2. POST /api/v1/pomodoro/sessions/{id}/state/  { "state": "running" }
3. Локально: countdown 25 * 60 сек
4. Если work_sound != "none" → loop play work_sound_detail.audio_url
```

### Завершение таймера

```text
1. Локально: secondsLeft === 0
2. Stop background audio
3. Play timer_end_sound_detail.audio_url (если key != "none")
4. POST /api/v1/pomodoro/sessions/{id}/state/  { "state": "completed" }
5. Push/local notification (если нужно по ТЗ)
```

### Stop

```text
1. POST .../state/  { "state": "stopped" }
2. Сброс UI на duration_minutes
3. Stop all audio
```

---

## 7. Аудио на клиенте

| Сценарий | Поведение |
|---|---|
| Фон (`work_sound`) | Loop, играет пока `state === running` |
| Завершение (`timer_end_sound`) | One-shot при `secondsLeft === 0` |
| Preview в настройках | One-shot по tap на кнопку звука |
| `audio_url === null` | Не играть; опционально toast «Файл скоро будет» |
| `key === "none"` | Без звука |

**Flutter:** `audioplayers` / `just_audio`  
**React Native:** `react-native-sound` / `expo-av`

Для lock screen / background: отдельные OS permissions (не часть REST API).

---

## 8. Ошибки

| HTTP | Причина | Действие фронта |
|---|---|---|
| `401` | Token expired | `POST /api/v1/auth/token/refresh/` |
| `400` | Неверный `work_sound` / `duration_minutes` | Показать validation error |
| `404` | Session not found | Создать новую сессию |

---

## 9. Чеклист интеграции

- [ ] Header `Authorization: Bearer` на всех запросах
- [ ] При `401` — refresh token flow
- [ ] Экран помодоро: `GET /pomodoro/settings/` при mount
- [ ] «Звук фоновый»: список из `GET /sounds/?category=work_background`
- [ ] Сохранение звука: `PATCH /pomodoro/settings/`
- [ ] Модалка настроек: duration + short_break + timer_end_sound
- [ ] Preview звука по `audio_url`
- [ ] Таймер локальный (не polling backend)
- [ ] Фон loop + end sound one-shot
- [ ] Сессии: create + state changes (running/paused/stopped/completed)
- [ ] Выбор задачи: `GET /tasks/` с search

---

## 10. Сводка URL

| # | Method | URL |
|---|---|---|
| 1 | GET | `/api/v1/sounds/?category=work_background` |
| 2 | GET | `/api/v1/sounds/?category=timer_end` |
| 3 | GET | `/api/v1/pomodoro/settings/` |
| 4 | PATCH | `/api/v1/pomodoro/settings/` |
| 5 | GET | `/api/v1/pomodoro/sessions/` |
| 6 | POST | `/api/v1/pomodoro/sessions/` |
| 7 | POST | `/api/v1/pomodoro/sessions/{id}/state/` |
| 8 | GET | `/api/v1/tasks/?search=...` |

---

## 11. Пример сервиса (pseudo-code)

```typescript
const API = "https://admin.ottertime.ru/api/v1";

async function api(path: string, options: RequestInit = {}) {
  const token = await getAccessToken();
  const res = await fetch(`${API}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
      ...options.headers,
    },
  });
  if (res.status === 401) throw new AuthError();
  if (!res.ok) throw await res.json();
  return res.status === 204 ? null : res.json();
}

export const pomodoroApi = {
  getSettings: () => api("/pomodoro/settings/"),
  updateSettings: (body: Partial<PomodoroSettings>) =>
    api("/pomodoro/settings/", { method: "PATCH", body: JSON.stringify(body) }),
  getBackgroundSounds: () => api("/sounds/?category=work_background"),
  getTimerEndSounds: () => api("/sounds/?category=timer_end"),
  createSession: (task: number | null, duration_minutes: number) =>
    api("/pomodoro/sessions/", {
      method: "POST",
      body: JSON.stringify({ task, duration_minutes }),
    }),
  setSessionState: (id: number, state: PomodoroSessionState) =>
    api(`/pomodoro/sessions/${id}/state/`, {
      method: "POST",
      body: JSON.stringify({ state }),
    }),
};
```
