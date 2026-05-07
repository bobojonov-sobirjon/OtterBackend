# OTTER Backend — Mobile API Documentation (DRF + JWT)

## General Info
- **Project**: OTTER (Planner app backend)
- **Framework**: Django + Django REST Framework
- **Auth**: **JWT (SimpleJWT)**
- **API Base path**: `/api/v1/`
- **Content-Type**: `application/json` (default)
- **Swagger UI**: `/docs/`
- **OpenAPI schema**: `/schema/`

### Base URL (examples)
- **DEV (local)**: `http://127.0.0.1:8000`
- **STAGING**: `https://staging.example.com`
- **PROD**: `http://159.194.221.54:8005/`

> Frontend всегда строит URL как: `BASE_URL + /api/v1/...`.

---

## Authentication (JWT Flow — IMPORTANT)

### How to send JWT
Для всех protected endpoints отправляйте header:

- **Header**: `Authorization: Bearer <access_token>`

### Token lifetime (текущие настройки)
- `access`: 7 days
- `refresh`: 7 days
- Refresh token rotation: **ON** (`ROTATE_REFRESH_TOKENS=True`)

---

# API Endpoints

## 1) Register
### METHOD: POST
### URL: `/api/v1/auth/register/`
### Auth: No
### Content-Type: `application/json`

#### Body params
- `email`: string (required) — user email
- `password`: string (required, minLength=8)
- `first_name`: string (optional, can be empty string)
- `last_name`: string (optional, can be empty string)

#### Example request
```json
{
  "email": "user@example.com",
  "password": "StrongPass123!",
  "first_name": "John",
  "last_name": "Doe"
}
```

#### Success response (201)
```json
{
  "user": {
    "id": 1,
    "email": "user@example.com",
    "first_name": "John",
    "last_name": "Doe",
    "avatar": null
  },
  "tokens": {
    "refresh": "jwt_refresh_token",
    "access": "jwt_access_token"
  }
}
```

#### Error responses
- **400** validation errors (e.g. weak password)

---

## 2) Login
### METHOD: POST
### URL: `/api/v1/auth/login/`
### Auth: No
### Content-Type: `application/json`

#### Body params
- `email`: string (required)
- `password`: string (required)

#### Example request
```json
{
  "email": "user@example.com",
  "password": "StrongPass123!"
}
```

#### Success response (200)
```json
{
  "tokens": {
    "refresh": "jwt_refresh_token",
    "access": "jwt_access_token"
  }
}
```

#### Error responses
- **400**:
```json
{ "detail": "Неверный email или пароль" }
```

---

## 3) Refresh → Access (Token refresh)
### METHOD: POST
### URL: `/api/v1/auth/token/refresh/`
### Auth: No
### Content-Type: `application/json`

#### Body params
- `refresh`: string (required) — refresh JWT

#### Example request
```json
{
  "refresh": "jwt_refresh_token"
}
```

#### Success response (200)
```json
{
  "access": "new_jwt_access_token",
  "refresh": "new_refresh_token_if_rotation_enabled"
}
```

#### Error responses
- **401** invalid/expired refresh token

---

## 4) Google Login (Firebase ID Token → JWT)
### METHOD: POST
### URL: `/api/v1/auth/google/`
### Auth: No
### Content-Type: `application/json`

#### Body params
- `firebase_token`: string (required) — Firebase ID Token (после Google sign-in)

#### Example request
```json
{
  "firebase_token": "firebase_id_token_here"
}
```

#### Success response (200)
```json
{
  "tokens": {
    "refresh": "jwt_refresh_token",
    "access": "jwt_access_token"
  },
  "user": {
    "id": 1,
    "email": "user@gmail.com",
    "first_name": "",
    "last_name": "",
    "avatar": null
  }
}
```

#### Error responses
- **400**:
```json
{ "detail": "В токене отсутствует email" }
```

---

# Password Recovery (Email code)

## 5) Forgot Password — Send code
### METHOD: POST
### URL: `/api/v1/auth/forgot-password/`
### Auth: No
### Content-Type: `application/json`

#### Body params
- `email`: string (required)

#### Example request
```json
{
  "email": "user@example.com"
}
```

#### Success response (200)
> Security: даже если пользователь не найден — возвращаем 200 (не раскрываем).

```json
{
  "detail": "Если email существует, код отправлен"
}
```

---

## 6) Forgot Password — Verify code → get reset_token
### METHOD: POST
### URL: `/api/v1/auth/forgot-password/verify/`
### Auth: No
### Content-Type: `application/json`

#### Body params
- `email`: string (required)
- `code`: string (required) — 6-digit code (отправляйте как строку)

#### Example request
```json
{
  "email": "user@example.com",
  "code": "123456"
}
```

#### Success response (200)
```json
{
  "reset_token": "550e8400-e29b-41d4-a716-446655440000"
}
```

#### Error response (400)
```json
{ "detail": "Неверный код или срок истёк" }
```

---

## 7) Forgot Password — Confirm new password (reset_token)
### METHOD: POST
### URL: `/api/v1/auth/forgot-password/confirm/`
### Auth: No
### Content-Type: `application/json`

#### Body params
- `reset_token`: string(uuid) (required)
- `new_password`: string (required, minLength=8)

#### Example request
```json
{
  "reset_token": "550e8400-e29b-41d4-a716-446655440000",
  "new_password": "NewStrongPass123!"
}
```

#### Success response (200)
```json
{
  "detail": "Пароль обновлён"
}
```

#### Error response (400)
```json
{ "detail": "Токен недействителен или истёк" }
```

---

# Profile

## 8) Get my profile
### METHOD: GET
### URL: `/api/v1/profile/`
### Auth: **Bearer access token required**
### Content-Type: `application/json`

#### Success response (200)
```json
{
  "id": 1,
  "email": "user@example.com",
  "first_name": "John",
  "last_name": "Doe",
  "avatar": "http://<host>/media/avatars/file.jpg"
}
```

---

## 9) Update profile (full)
### METHOD: PUT
### URL: `/api/v1/profile/`
### Auth: **Bearer access token required**

### Content-Type options
- `application/json` (только текстовые поля)
- **`multipart/form-data`** (рекомендуется при загрузке аватара)

#### Body params (JSON or multipart)
- `first_name`: string (optional)
- `last_name`: string (optional)
- `avatar`: file (optional, can be null) — **только multipart/form-data**

#### Example (multipart/form-data)
Fields:
- `first_name`: `John`
- `last_name`: `Doe`
- `avatar`: *(file)*

#### Success response (200)
```json
{
  "id": 1,
  "email": "user@example.com",
  "first_name": "John",
  "last_name": "Doe",
  "avatar": "http://<host>/media/avatars/new.jpg"
}
```

---

## 10) Update profile (partial)
### METHOD: PATCH
### URL: `/api/v1/profile/`
### Auth: **Bearer access token required**
### Content-Type: `multipart/form-data` (для аватара)

#### Body params
То же, что в PUT, но любое поле можно опустить.

---

# Common Errors / Notes

### Auth errors
- **401 Unauthorized**: access token отсутствует / некорректен / истёк
- **403 Forbidden**: нет прав

### Validation errors
- **400**:
```json
{
  "field_name": ["error message"]
}
```

---

## Quick Frontend Checklist
- Отправляйте **access token** в `Authorization: Bearer ...`
- Если access истёк — обновляйте через `POST /auth/token/refresh/`
- Avatar upload: **multipart/form-data**
- Forgot password flow:
  1) `/auth/forgot-password/`
  2) `/auth/forgot-password/verify/` → `reset_token`
  3) `/auth/forgot-password/confirm/`
