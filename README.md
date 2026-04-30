# OTTER — Backend (Django / DRF / ASGI)

Backend для мобильного приложения‑планировщика **«OTTER»**.

## Технологии
- **Django + Django REST Framework**
- **JWT (SimpleJWT)**
- **OpenAPI/Swagger (drf-spectacular)**
- **ASGI + Daphne**
- **Admin UI: Jazzmin**
- **PostgreSQL**
- **Google login: Firebase Admin SDK**

## Быстрый старт

### 1) Установка зависимостей

```bash
pip install -r requirements.txt
```

### 2) Настройка окружения
- Скопируйте `.env.example` → `.env`
- Заполните значения (БД, email SMTP, Firebase)

### 3) Миграции

```bash
python manage.py migrate
```

### 4) Создать админа

```bash
python manage.py createsuperuser
```

### 5) Запуск ASGI (Daphne)

```bash
daphne -b 127.0.0.1 -p 8000 config.asgi:application
```

## Документация API
- **Swagger UI**: `/docs/`
- **OpenAPI schema (yaml)**: `/schema/`

Базовый префикс API: `/api/v1/`

## Админ‑панель
- URL: `/admin/`
- UI: **Jazzmin**
- В админке отключены разделы:
  - Blacklisted Tokens
  - Outstanding Tokens
  - Группы
  - Сайты
- Сбросы пароля показываются **inline** внутри пользователя.

## Реализованные API (1 этап)

### Авторизация
- `POST /api/v1/auth/register/` — регистрация (JWT)
- `POST /api/v1/auth/login/` — вход (JWT)
- `POST /api/v1/auth/token/refresh/` — refresh → access
- `POST /api/v1/auth/google/` — вход через Google (Firebase token → JWT)

### Восстановление пароля (код на email)
- `POST /api/v1/auth/forgot-password/` — отправить код на email (HTML письмо)
- `POST /api/v1/auth/forgot-password/verify/` — проверить код → `reset_token`
- `POST /api/v1/auth/forgot-password/confirm/` — новый пароль по `reset_token`

### Профиль
- `GET /api/v1/profile/` — текущий профиль
- `PUT /api/v1/profile/` — обновление (в т.ч. `avatar`, multipart/form-data)
- `PATCH /api/v1/profile/` — частичное обновление (multipart/form-data)

## Примечания
- Имена полей в API **на английском** (`email`, `password`, `reset_token`, ...), а **описания/лейблы** в Swagger и `verbose_name` в моделях — **на русском**.
- Email отправка требует SMTP‑учётки. Для Gmail используйте **App Password**.

