# OTTER — Premium / Payments API (Mobile Frontend)

> Production-ready guide for Flutter / React Native / Web / Desktop.  
> Focus: **JWT auth + tariffs + free trial + Robokassa checkout**.  
> Full product API (tasks, calendar, pomodoro…): [MOBILE_API.md](./MOBILE_API.md)  
> Swagger: `{BASE_URL}/docs/`

---

## 1. General Info

| Parameter | Value |
|---|---|
| **Project** | OTTER — Planner app backend |
| **Framework** | Django + Django REST Framework (DRF) |
| **Auth** | JWT (SimpleJWT) |
| **API prefix** | `/api/v1/` |
| **Content-Type** | `application/json` |
| **Payment provider** | Robokassa |

### Base URL

| Environment | URL |
|---|---|
| **DEV (local)** | `http://127.0.0.1:8000` |
| **PROD** | `https://admin.skkamni.ru` |

Client builds requests as: `BASE_URL + /api/v1/...`

### Headers (all protected endpoints)

```http
Authorization: Bearer <access_token>
Content-Type: application/json
```

### Token lifetime

| Token | Lifetime |
|---|---|
| `access` | 7 days |
| `refresh` | 7 days |
| Refresh rotation | ON |

---

## 2. Authentication (JWT Flow)

```text
1. POST /auth/register/  OR  /auth/login/  OR  /auth/google/
   → tokens.access + tokens.refresh

2. Every request:  Authorization: Bearer <access>

3. If 401:
   POST /auth/token/refresh/  { "refresh": "..." }
   → new access (+ new refresh)
```

---

### 2.1 Register

| | |
|---|---|
| **METHOD** | `POST` |
| **URL** | `/api/v1/auth/register/` |
| **Auth** | No |

#### Body params

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `email` | string (email) | **yes** | — | Unique email |
| `password` | string | **yes** | — | Min 8 chars |
| `first_name` | string | no | `""` | First name |
| `last_name` | string | no | `""` | Last name |

#### Example request

```json
{
  "email": "user@example.com",
  "password": "StrongPass123!",
  "first_name": "Иван",
  "last_name": "Петров"
}
```

#### Success `201`

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
    "refresh": "eyJ...",
    "access": "eyJ..."
  }
}
```

> After register: user is **free**, `is_premium = false`. Trial is **not** auto-started.

---

### 2.2 Login

| | |
|---|---|
| **METHOD** | `POST` |
| **URL** | `/api/v1/auth/login/` |
| **Auth** | No |

#### Body params

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `email` | string (email) | **yes** | — | User email |
| `password` | string | **yes** | — | Password |

#### Example request

```json
{
  "email": "user@example.com",
  "password": "StrongPass123!"
}
```

#### Success `200`

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

### 2.3 Google Login (Firebase)

| | |
|---|---|
| **METHOD** | `POST` |
| **URL** | `/api/v1/auth/google/` |
| **Auth** | No |

#### Body params

| Field | Type | Required | Description |
|---|---|---|---|
| `firebase_token` | string | **yes** | Firebase ID Token after Google Sign-In |

#### Example request

```json
{
  "firebase_token": "eyJhbGciOiJSUzI1NiIs..."
}
```

#### Success `200`

```json
{
  "tokens": {
    "refresh": "eyJ...",
    "access": "eyJ..."
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

---

### 2.4 Refresh token

| | |
|---|---|
| **METHOD** | `POST` |
| **URL** | `/api/v1/auth/token/refresh/` |
| **Auth** | No |

#### Body params

| Field | Type | Required | Description |
|---|---|---|---|
| `refresh` | string | **yes** | Refresh JWT |

#### Example request

```json
{
  "refresh": "eyJ...refresh_token"
}
```

#### Success `200`

```json
{
  "access": "eyJ...new_access",
  "refresh": "eyJ...new_refresh"
}
```

---

## 3. Product rules (must understand before UI)

| Rule | Behavior |
|---|---|
| New user after login/register | **Free account**, no premium |
| Free trial auto-start? | **No** |
| How to start trial | `POST /premium/trial/` |
| Trial length | Tariff `promo_days` → **7 days** for `monthly` / `yearly` |
| Payment | Open `checkout_url` in WebView / browser / system browser |
| Who activates premium after pay | **Backend ResultURL** (Robokassa → server). Client must **not** call fake activate in production |
| After payment | Poll / refresh `GET /premium/subscription/` or `GET /settings/` |

### Default tariffs (seed)

| `code` | Price | Paid duration | Free trial (`promo_days`) |
|---|---|---|---|
| `monthly` | `299.00` RUB | 30 days | **7 days** |
| `yearly` | `2490.00` RUB | 365 days | **7 days** |
| `lifetime` | `4990.00` RUB | unlimited (`duration_days=0`) | 0 (no trial) |

Prices can change in Admin → Биллинг → Тарифы. Always read from API.

### Subscription `status` enum

| Value | Meaning |
|---|---|
| `none` | No subscription |
| `trial` | Free promo period |
| `active` | Paid active |
| `past_due` | Payment overdue / trial ended without pay |
| `cancelled` | Auto-renew off; access until `premium_until` |
| `expired` | Access ended |

Use field **`is_premium`** (computed) for UI gates.

---

## 4. Premium / Payment APIs

### 4.1 List tariffs

| | |
|---|---|
| **METHOD** | `GET` |
| **URL** | `/api/v1/premium/tariffs/` |
| **Auth** | **Bearer required** |

#### Query params

None.

#### Success `200`

```json
[
  {
    "code": "monthly",
    "title": "Месячная подписка",
    "description": "Премиум на 30 дней. Промо-период настраивается на стороне Otter.",
    "price": "299.00",
    "currency": "RUB",
    "duration_days": 30,
    "promo_days": 7,
    "is_recurring": true,
    "sort_order": 1
  },
  {
    "code": "yearly",
    "title": "Годовая подписка",
    "description": "Премиум на 365 дней.",
    "price": "2490.00",
    "currency": "RUB",
    "duration_days": 365,
    "promo_days": 7,
    "is_recurring": true,
    "sort_order": 2
  },
  {
    "code": "lifetime",
    "title": "Навсегда",
    "description": "Разовый платёж без автопродления.",
    "price": "4990.00",
    "currency": "RUB",
    "duration_days": 0,
    "promo_days": 0,
    "is_recurring": false,
    "sort_order": 3
  }
]
```

| Field | Type | Description |
|---|---|---|
| `code` | string | Send this in trial/checkout body |
| `price` | string (decimal) | Display price |
| `duration_days` | integer | Paid period; `0` = lifetime |
| `promo_days` | integer | Free trial days if user starts trial |
| `is_recurring` | boolean | Business flag; Robokassa Recurring may still be off on server |

---

### 4.2 Subscription status

| | |
|---|---|
| **METHOD** | `GET` |
| **URL** | `/api/v1/premium/subscription/` |
| **Auth** | **Bearer required** |

#### Success `200`

```json
{
  "status": "trial",
  "tariff": {
    "code": "monthly",
    "title": "Месячная подписка",
    "description": "...",
    "price": "299.00",
    "currency": "RUB",
    "duration_days": 30,
    "promo_days": 7,
    "is_recurring": true,
    "sort_order": 1
  },
  "promo_until": "2026-07-22T12:00:00+03:00",
  "premium_until": "2026-07-22T12:00:00+03:00",
  "recurring_enabled": false,
  "cancelled_at": null,
  "is_premium": true,
  "updated_at": "2026-07-15T12:00:00+03:00"
}
```

| Field | Type | Description |
|---|---|---|
| `is_premium` | boolean | **Use this for UI** (trial or paid still valid) |
| `promo_until` | datetime \| null | Trial end |
| `premium_until` | datetime \| null | Access end; `null` + active = lifetime |
| `recurring_enabled` | boolean | Auto-charge enabled on backend |

Also mirrored in:

```http
GET /api/v1/settings/
```

→ `is_premium`, `premium_activated_at`, `premium_until` (read-only).

---

### 4.3 Start free trial (promo)

| | |
|---|---|
| **METHOD** | `POST` |
| **URL** | `/api/v1/premium/trial/` |
| **Auth** | **Bearer required** |

Promo is calculated **on Otter backend** (not in Robokassa cabinet).

#### Body params

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `tariff` | string (slug) | **yes** | — | e.g. `"monthly"` |
| `recurring_consent` | boolean | conditional | `false` | Required **only if** server has Robokassa recurring enabled **and** tariff.is_recurring. Checkbox must be OFF by default in UI. |
| `offer_version` | string | no | `""` | Offer document version for consent log |

#### Example request (current server: recurring OFF)

```json
{
  "tariff": "monthly"
}
```

#### Example request (when recurring is ON on server)

```json
{
  "tariff": "monthly",
  "recurring_consent": true,
  "offer_version": "2026-07-01"
}
```

#### Success `200`

Same shape as subscription status (`status: "trial"`, `is_premium: true`, dates set).

#### Errors

| HTTP | When |
|---|---|
| `400` | Unknown tariff / no promo_days / already active / consent required |
| `401` | Missing/invalid JWT |

#### Frontend UX

1. Show tariffs (`GET /premium/tariffs/`)
2. If `promo_days > 0` → button «Попробовать бесплатно»
3. Call `POST /premium/trial/`
4. Unlock premium UI for `promo_until`

---

### 4.4 Create checkout (Robokassa)

| | |
|---|---|
| **METHOD** | `POST` |
| **URL** | `/api/v1/premium/checkout/` |
| **Auth** | **Bearer required** |

#### Body params

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `tariff` | string (slug) | **yes** | — | `monthly` \| `yearly` \| `lifetime` |
| `recurring_consent` | boolean | conditional | `false` | Required only when Robokassa recurring is enabled server-side and tariff is recurring |
| `offer_version` | string | no | `""` | Offer version for consent history |

#### Example request

```json
{
  "tariff": "monthly",
  "recurring_consent": false,
  "offer_version": "2026-07-01"
}
```

#### Success `200`

```json
{
  "checkout_url": "https://auth.robokassa.ru/Merchant/Index.aspx?MerchantLogin=ottertime&OutSum=299.00&...",
  "provider": "robokassa",
  "payment": {
    "invoice_id": 100010,
    "tariff": "monthly",
    "amount": "299.00",
    "currency": "RUB",
    "kind": "one_time",
    "status": "pending",
    "checkout_url": "https://auth.robokassa.ru/Merchant/Index.aspx?...",
    "paid_at": null,
    "created_at": "2026-07-15T15:00:00+03:00"
  }
}
```

| Field | Type | Description |
|---|---|---|
| `checkout_url` | string | **Open this URL** |
| `provider` | string | Always `"robokassa"` |
| `payment.invoice_id` | integer | Robokassa InvId |
| `payment.kind` | string | `one_time` \| `initial` \| `recurring` |
| `payment.status` | string | `pending` until ResultURL |

#### Client open rules

| Platform | How to open |
|---|---|
| **Web** | `window.location = checkout_url` or new tab |
| **App** | WebView / Custom Tabs / SFSafariViewController |
| **Desktop** | System browser |

#### Errors

| HTTP | Body | Meaning |
|---|---|---|
| `400` | `{ "detail": "Тариф не найден." }` | Bad tariff code |
| `400` | `{ "detail": "Нужно согласие..." }` | Consent required |
| `401` | — | JWT |
| `503` | Robokassa not configured | Server `.env` missing |

---

### 4.5 After payment (critical)

```text
User pays on Robokassa
        ↓
Robokassa → POST /api/v1/premium/robokassa/result/   (server only)
        ↓
Backend sets is_premium = true
        ↓
User lands on Success URL (web): https://ottertime.ru/premium/success
        ↓
App calls GET /premium/subscription/  (or settings)
```

| | |
|---|---|
| **METHOD** | `POST` (also GET) |
| **URL** | `/api/v1/premium/robokassa/result/` |
| **Auth** | **No** — called by Robokassa, not by mobile app |

**Mobile/web client must NOT call ResultURL.**

On Success / app resume:

```http
GET /api/v1/premium/subscription/
```

Expect `status: "active"`, `is_premium: true`.

Fail URL: `https://ottertime.ru/premium/fail` → keep paywall.

---

### 4.6 Cancel auto-renew

| | |
|---|---|
| **METHOD** | `POST` |
| **URL** | `/api/v1/premium/cancel/` |
| **Auth** | **Bearer required** |
| **Body** | empty `{}` or none |

Turns off auto-renew. Access remains until `premium_until`.

#### Success `200`

Subscription object with `cancelled_at` set, `recurring_enabled: false`.

---

### 4.7 Feature flags

| | |
|---|---|
| **METHOD** | `GET` |
| **URL** | `/api/v1/premium/features/` |
| **Auth** | **Bearer required** |

```json
[
  {
    "key": "calendar",
    "title": "Календарь",
    "is_premium": true,
    "is_enabled": true
  }
]
```

Use together with `is_premium` to gate screens.

---

### 4.8 DEV activate (DEBUG only)

| | |
|---|---|
| **METHOD** | `POST` |
| **URL** | `/api/v1/premium/activate/` |
| **Auth** | **Bearer required** |

In **production** → `403`. Do **not** rely on this in app builds.

---

## 5. Recommended frontend flows

### Flow A — Free trial then pay

```text
1. Login / Register / Google → save JWT
2. GET /premium/tariffs/
3. User taps «Попробовать» (promo_days > 0)
4. POST /premium/trial/  { "tariff": "monthly" }
5. Unlock premium until promo_until
6. When trial ends / user taps «Оплатить»:
7. POST /premium/checkout/  { "tariff": "monthly" }
8. Open checkout_url
9. On return / resume → GET /premium/subscription/
```

### Flow B — Pay immediately

```text
1. Auth
2. GET /premium/tariffs/
3. UI: checkbox OFF by default
   «Я согласен на автоматические списания…» + offer link
   (required later when server recurring is ON)
4. POST /premium/checkout/
5. Open checkout_url
6. GET /premium/subscription/
```

### Consent UI (Robokassa requirement for recurrents)

- Checkbox **not** checked by default
- Clickable offer link
- Text about billing period (month/year)
- Save history is on backend when `recurring_consent: true`

---

## 6. Legal documents (for offer checkbox)

| | |
|---|---|
| **METHOD** | `GET` |
| **URL** | `/api/v1/legal/documents/` |
| **Auth** | No |

Returns offer / privacy / personal data texts (`doc_type`, `title`, `content`).

---

## 7. Error handling cheat-sheet

| HTTP | Meaning | Client action |
|---|---|---|
| `401` | JWT expired | Refresh token |
| `400` | Validation / consent / bad tariff | Show `detail` |
| `403` | activate in prod | Ignore activate endpoint |
| `503` | Robokassa env missing | Show «payment unavailable» |

Robokassa page errors (not API):

| Code | Meaning |
|---|---|
| `23` | Test settings incomplete on Robokassa side |
| `29` | Bad signature / wrong Password #1 |
| `34` | Recurring not approved for shop |

---

## 8. Endpoint index (payments + auth)

| # | Method | URL | Auth |
|---|---|---|---|
| 1 | POST | `/api/v1/auth/register/` | No |
| 2 | POST | `/api/v1/auth/login/` | No |
| 3 | POST | `/api/v1/auth/google/` | No |
| 4 | POST | `/api/v1/auth/token/refresh/` | No |
| 5 | GET | `/api/v1/premium/tariffs/` | Yes |
| 6 | GET | `/api/v1/premium/subscription/` | Yes |
| 7 | POST | `/api/v1/premium/trial/` | Yes |
| 8 | POST | `/api/v1/premium/checkout/` | Yes |
| 9 | POST | `/api/v1/premium/cancel/` | Yes |
| 10 | GET | `/api/v1/premium/features/` | Yes |
| 11 | POST | `/api/v1/premium/activate/` | Yes (DEBUG only) |
| 12 | POST | `/api/v1/premium/robokassa/result/` | No (Robokassa only) |
| 13 | GET | `/api/v1/settings/` | Yes (`is_premium`) |
| 14 | GET | `/api/v1/legal/documents/` | No |

Other modules (tasks, calendar, matrix, pomodoro, help…): see [MOBILE_API.md](./MOBILE_API.md).

---

## 9. TypeScript types (recommended)

```typescript
interface JwtTokens {
  access: string;
  refresh: string;
}

interface Tariff {
  code: string;
  title: string;
  description: string;
  price: string;
  currency: string;
  duration_days: number;
  promo_days: number;
  is_recurring: boolean;
  sort_order: number;
}

type SubscriptionStatus =
  | "none"
  | "trial"
  | "active"
  | "past_due"
  | "cancelled"
  | "expired";

interface Subscription {
  status: SubscriptionStatus;
  tariff: Tariff | null;
  promo_until: string | null;
  premium_until: string | null;
  recurring_enabled: boolean;
  cancelled_at: string | null;
  is_premium: boolean;
  updated_at: string;
}

interface CheckoutResponse {
  checkout_url: string;
  provider: "robokassa";
  payment: {
    invoice_id: number;
    tariff: string;
    amount: string;
    currency: string;
    kind: "one_time" | "initial" | "recurring";
    status: "pending" | "paid" | "failed" | "cancelled";
    checkout_url: string;
    paid_at: string | null;
    created_at: string;
  };
}
```

---

## 10. Minimal client sketch

```typescript
const API = "https://admin.skkamni.ru/api/v1";

async function api(path: string, options: RequestInit = {}) {
  const token = await getAccessToken();
  const res = await fetch(`${API}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers,
    },
  });
  if (res.status === 401) throw new AuthError();
  if (!res.ok) throw await res.json();
  return res.json();
}

export const premiumApi = {
  tariffs: () => api("/premium/tariffs/"),
  subscription: () => api("/premium/subscription/"),
  startTrial: (tariff: string) =>
    api("/premium/trial/", {
      method: "POST",
      body: JSON.stringify({ tariff }),
    }),
  checkout: (tariff: string, recurring_consent = false) =>
    api("/premium/checkout/", {
      method: "POST",
      body: JSON.stringify({ tariff, recurring_consent }),
    }),
  cancel: () => api("/premium/cancel/", { method: "POST", body: "{}" }),
  features: () => api("/premium/features/"),
};
```

---

## 11. QA checklist for mobile

- [ ] Login stores `tokens.access` / `refresh`
- [ ] 401 → refresh → retry
- [ ] New user: premium locked until trial or pay
- [ ] Trial: 7 days for monthly/yearly
- [ ] Checkout opens Robokassa URL
- [ ] After pay: refresh subscription, not `/activate/`
- [ ] Consent checkbox default OFF (when recurrents enabled)
- [ ] Cancel keeps access until `premium_until`
