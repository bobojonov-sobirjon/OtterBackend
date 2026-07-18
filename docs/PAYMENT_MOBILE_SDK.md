# OTTER — Premium to‘lovlari (Mobile App + Robokassa SDK)

> **Kim uchun:** Flutter / React Native / native Android & iOS dasturchilar.  
> **Maqsad:** app ichida Robokassa SDK orqali premium to‘lash.  
> **Web / Desktop:** bu hujjat **emas** — ular uchun [PAYMENT_FRONTEND.md](./PAYMENT_FRONTEND.md).  
> **Umumiy API:** [MOBILE_API.md](./MOBILE_API.md)

---

## 0. 30 soniyada tushunish

| Savol | Javob |
|---|---|
| App qaysi API dan foydalanadi? | `/api/v1/mobile/premium/...` |
| Web/Desktop qaysidan? | `/api/v1/premium/...` (tegmaymiz) |
| Checkout nima qaytaradi? | `sdk` obyekti (`signature_value` bilan) — **URL emas** |
| Parollarni app ga qo‘yamanmi? | **Yo‘q.** `Password1` / `Password2` faqat backendda |
| Premium qachon yoqiladi? | Robokassa → backend ResultURL. App faqat statusni so‘raydi |
| To‘lovdan keyin nima qilaman? | `payments/{invoice_id}/` ni poll qilaman → keyin `subscription/` |

---

## 1. Umumiy ma’lumot

| Parametr | Qiymat |
|---|---|
| **PROD Base URL** | `https://admin.ottertime.ru` |
| **DEV Base URL** | `http://127.0.0.1:8000` |
| **Mobile API prefix** | `/api/v1/mobile/` |
| **Auth** | JWT: `Authorization: Bearer <access_token>` |
| **Content-Type** | `application/json` |
| **To‘lov** | Robokassa Mobile SDK ([Android](https://github.com/robokassa/sdk-android) / [iOS](https://github.com/robokassa/sdk-ios)) |

### Header (har bir himoyalangan so‘rov)

```http
Authorization: Bearer <access_token>
Content-Type: application/json
```

### Token

| Token | Muddat |
|---|---|
| `access` | 7 kun |
| `refresh` | 7 kun |

Avval login / register / Google → JWT oling. Keyin premium API lar.

---

## 2. Nima uchun alohida mobile API?

| | Web / Desktop | **Mobile App (siz)** |
|---|---|---|
| Prefix | `/api/v1/premium/` | `/api/v1/mobile/premium/` |
| Checkout javobi | `checkout_url` | **`sdk`** (parametrlar + imzo) |
| To‘lov UI | Brauzer / WebView | **Robokassa SDK** (native) |
| Status tekshiruvi | Success sahifa + subscription | **Polling** `payments/{id}/` |
| Parollar | Yo‘q | Yo‘q |
| Premium status | Bitta backend, bitta obuna | Bitta backend, bitta obuna |

**Qoida:** App faqat `/api/v1/mobile/...` chaqirsin. Web uchun `/api/v1/premium/checkout/` ni **ishlatmang**.

---

## 3. To‘liq oqim (copy-paste mental model)

```text
┌─────────────────────────────────────────────────────────────┐
│  1. Login → JWT                                             │
│  2. GET  /mobile/premium/subscription/   → is_premium?      │
│  3. GET  /mobile/premium/tariffs/        → narxlar          │
│  4. (ixtiyoriy) POST /mobile/premium/trial/  → bepul kunlar │
│  5. POST /mobile/premium/checkout/       → sdk + invoice_id │
│  6. Robokassa SDK ochish (sdk parametrlari bilan)           │
│  7. Foydalanuvchi to‘laydi                                  │
│  8. Robokassa → backend ResultURL (app chaqirmaydi!)        │
│  9. GET  /mobile/premium/payments/{invoice_id}/  → paid?    │
│ 10. GET  /mobile/premium/subscription/   → is_premium:true  │
│ 11. UI ni yangilash (premium ochiq)                         │
└─────────────────────────────────────────────────────────────┘
```

### Kim nima qiladi?

| Kim | Vazifa |
|---|---|
| **App** | JWT, tariflar, checkout, SDK ochish, polling, UI |
| **Backend** | InvId, signature, payment yozuvi, premium yoqish |
| **Robokassa** | Pul olish, ResultURL ga xabar |

App **hech qachon** `POST /premium/robokassa/result/` ni chaqirmasin — bu faqat Robokassa serveri uchun.

---

## 4. Biznes qoidalari (UI uchun)

1. **Promo** backendda hisoblanadi (`promo_days`). Robokassa kabinetida promo yo‘q.
2. Yangi user avtomatik trial olmaydi — `POST .../trial/` chaqirish kerak (yoki to‘g‘ridan-to‘g‘ri checkout).
3. `is_premium == true` bo‘lsa — premium ekranlar ochiq (trial yoki paid).
4. **Recurring checkbox** UI da default **OFF**. Faqat foydalanuvchi qo‘lda yoqsa `recurring_consent: true`.
5. Hozir serverda Robokassa recurring odatda **o‘chiq** (`ROBOKASSA_RECURRING_ENABLED=0`) → `sdk.is_recurring` ko‘pincha `false`. Checkboxni baribir saqlang (kelajak uchun).
6. To‘lov muvaffaqiyatini **faqat** backend statusidan bilasiz (`paid` / `is_premium`). SDK “success” callbackiga 100% ishonmang — 1–5 soniya kechikishi mumkin.

---

## 5. API — batafsil

Barcha URL lar: `BASE_URL + /api/v1/mobile/...`

### 5.1 Tariflar

| | |
|---|---|
| **METHOD** | `GET` |
| **URL** | `/api/v1/mobile/premium/tariffs/` |
| **Auth** | Bearer |

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
  }
]
```

| Field | UI da |
|---|---|
| `code` | Checkout/trial body ga yuboriladi (`"monthly"`) |
| `title` / `price` | Kartochkada ko‘rsatish |
| `promo_days` | «7 kun bepul» matni |
| `duration_days` | «30 kun» |

---

### 5.2 Obuna statusi

| | |
|---|---|
| **METHOD** | `GET` |
| **URL** | `/api/v1/mobile/premium/subscription/` |
| **Auth** | Bearer |

#### Success `200`

```json
{
  "status": "none",
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
  "promo_until": null,
  "premium_until": null,
  "recurring_enabled": false,
  "cancelled_at": null,
  "is_premium": false,
  "updated_at": "2026-07-18T10:00:00+03:00"
}
```

| `status` | Ma’nosi | UI |
|---|---|---|
| `none` | Obuna yo‘q | «Попробовать» / «Купить» |
| `trial` | Bepul promo | Muddat: `promo_until` |
| `active` | To‘langan | Muddat: `premium_until` |
| `past_due` | Promo tugagan, to‘lov kerak | Paywall |
| `cancelled` | Avtoprodlenie o‘chirilgan | Muddatgacha ishlaydi |
| `expired` | Tugagan | Paywall |

**Asosiy flag:** `is_premium` — true bo‘lsa premium funksiyalar ochiq.

App ochilganda / resume da shu endpointni chaqiring.

---

### 5.3 Bepul promo (trial)

| | |
|---|---|
| **METHOD** | `POST` |
| **URL** | `/api/v1/mobile/premium/trial/` |
| **Auth** | Bearer |

#### Body

| Field | Type | Required | Default | Izoh |
|---|---|---|---|---|
| `tariff` | string | **yes** | — | Masalan `"monthly"` |
| `recurring_consent` | boolean | conditional | `false` | Checkbox (default OFF) |
| `offer_version` | string | no | `""` | Oferta versiyasi (log) |

```json
{
  "tariff": "monthly",
  "recurring_consent": false,
  "offer_version": "2026-07-01"
}
```

#### Success `200`

Subscription obyekti (`status: "trial"`, `is_premium: true`).

#### Errors

| Code | Sabab | UI |
|---|---|---|
| `400` | Promo yo‘q / allaqachon faol | Snackbar |
| `400` | Consent kerak | Checkbox majburiy |

---

### 5.4 Checkout — eng muhim endpoint (SDK)

| | |
|---|---|
| **METHOD** | `POST` |
| **URL** | `/api/v1/mobile/premium/checkout/` |
| **Auth** | Bearer |

Bu endpoint **`checkout_url` bermaydi**. U Robokassa SDK ga kerak bo‘lgan parametrlarni beradi.

#### Body

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
  "provider": "robokassa",
  "payment": {
    "invoice_id": 100123,
    "tariff": "monthly",
    "amount": "299.00",
    "currency": "RUB",
    "kind": "one_time",
    "status": "pending",
    "channel": "mobile_sdk",
    "checkout_url": "",
    "paid_at": null,
    "created_at": "2026-07-18T10:05:00+03:00"
  },
  "sdk": {
    "merchant_login": "ottertime",
    "invoice_id": 100123,
    "out_sum": "299.00",
    "description": "Otter Premium: Месячная подписка",
    "signature_value": "a1b2c3d4e5f6789...",
    "culture": "ru",
    "encoding": "utf-8",
    "is_test": true,
    "is_recurring": false,
    "email": "user@example.com"
  }
}
```

#### `sdk` maydonlari → SDK ga

| Backend field | SDK ga | Majburiy |
|---|---|---|
| `merchant_login` | MerchantLogin | ha |
| `invoice_id` | InvoiceId / InvId | ha |
| `out_sum` | OutSum (string `"299.00"`) | ha |
| `description` | Description | ha |
| `signature_value` | SignatureValue | ha |
| `is_test` | IsTest / test mode | ha |
| `is_recurring` | Recurring / isRecurrent | ha |
| `email` | Email | ixtiyoriy |
| `culture` | Culture (`ru`) | ixtiyoriy |
| `receipt` / `receipt_json` | Receipt (agar kelgan bo‘lsa) | ixtiyoriy |

#### Local saqlang

Checkout dan keyin **`payment.invoice_id`** ni saqlang — polling uchun kerak.

#### Errors

| Code | Sabab | UI |
|---|---|---|
| `400` | Tarif topilmadi / consent | Xabar |
| `401` | Token yo‘q / eskirgan | Login |
| `503` | Robokassa serverda sozlanmagan | «Оплата временно недоступна» |

---

### 5.5 To‘lov statusi (polling)

SDK yopilgandan keyin ResultURL 1–5 soniya kechikishi mumkin. Shu sababli **polling** qiling.

| | |
|---|---|
| **METHOD** | `GET` |
| **URL** | `/api/v1/mobile/premium/payments/{invoice_id}/` |
| **Auth** | Bearer |

#### Success `200`

```json
{
  "invoice_id": 100123,
  "tariff": "monthly",
  "amount": "299.00",
  "currency": "RUB",
  "kind": "one_time",
  "status": "paid",
  "channel": "mobile_sdk",
  "checkout_url": "",
  "paid_at": "2026-07-18T10:06:12+03:00",
  "created_at": "2026-07-18T10:05:00+03:00"
}
```

| `status` | Ma’nosi |
|---|---|
| `pending` | Hali kutilyapti — yana poll |
| `paid` | Muvaffaqiyat — subscription ni yangilang |
| `failed` | Xato |
| `cancelled` | Bekor |

#### Polling tavsiyasi

```text
Har 2 soniyada, maksimum 15 marta (~30 soniya).
status == "paid"  → GET subscription → UI success
timeout           → «Проверьте статус позже» + subscription refresh
```

#### Errors

| Code | Sabab |
|---|---|
| `404` | Bu userning shu invoice_id si yo‘q |

---

### 5.6 Oxirgi pending to‘lov

| | |
|---|---|
| **METHOD** | `GET` |
| **URL** | `/api/v1/mobile/premium/payments/pending/` |
| **Auth** | Bearer |

App resume qilinganda: agar oldin to‘lov ochilgan bo‘lsa, shu yerda topib pollingni davom ettirish mumkin.  
Yo‘q bo‘lsa → `404`.

---

### 5.7 Avtoprodlenieni bekor qilish

| | |
|---|---|
| **METHOD** | `POST` |
| **URL** | `/api/v1/mobile/premium/cancel/` |
| **Auth** | Bearer |
| **Body** | `{}` |

#### Success `200`

Yangilangan Subscription (`recurring_enabled: false`, odatda `status: cancelled`).  
**Premium darhol o‘chmaydi** — `premium_until` gacha ishlaydi.

---

### 5.8 Feature flags

| | |
|---|---|
| **METHOD** | `GET` |
| **URL** | `/api/v1/mobile/premium/features/` |
| **Auth** | Bearer |

Premium bo‘limlarini feature flag orqali yoqish/o‘chirish (admin paneldan).

---

## 6. Robokassa SDK ga ulash

### Xavfsizlik (majburiy)

| Qoida | |
|---|---|
| `Password1` / `Password2` | **Ilova kodiga qo‘ymang** (git, apk, env — hech qayerga) |
| Imzo | Faqat backend `sdk.signature_value` |
| Merchant login | Backend `sdk.merchant_login` dan oling (hardcode qilish mumkin, lekin backenddan yaxshiroq) |

### Flutter — pseudo-code

```dart
Future<void> buyPremium(String tariffCode) async {
  // 1) Checkout
  final res = await api.post('/api/v1/mobile/premium/checkout/', {
    'tariff': tariffCode,
    'recurring_consent': false, // checkbox qiymati
    'offer_version': '2026-07-01',
  });

  final invoiceId = res['payment']['invoice_id'] as int;
  final sdk = res['sdk'] as Map<String, dynamic>;

  // 2) Robokassa SDK ochish (paket API ga qarab map qiling)
  await RobokassaSdk.startPayment(
    merchantLogin: sdk['merchant_login'],
    invoiceId: invoiceId,
    outSum: sdk['out_sum'],           // "299.00"
    description: sdk['description'],
    signatureValue: sdk['signature_value'],
    isTest: sdk['is_test'] == true,
    isRecurring: sdk['is_recurring'] == true,
    email: sdk['email'],
  );

  // 3) Polling
  final paid = await pollPayment(invoiceId);
  if (paid) {
    final sub = await api.get('/api/v1/mobile/premium/subscription/');
    // sub['is_premium'] == true → UI yangilang
  }
}

Future<bool> pollPayment(int invoiceId) async {
  for (var i = 0; i < 15; i++) {
    await Future.delayed(const Duration(seconds: 2));
    final p = await api.get('/api/v1/mobile/premium/payments/$invoiceId/');
    if (p['status'] == 'paid') return true;
    if (p['status'] == 'failed' || p['status'] == 'cancelled') return false;
  }
  return false;
}
```

### Android (Kotlin) — g‘oya

```kotlin
val sdk = response.sdk
// Official SDK: https://github.com/robokassa/sdk-android
// Parametrlarni SDK PaymentParams ga map qiling:
// invoiceId, orderSum, description, signature, isTest, isRecurrent, email
```

### iOS (Swift) — g‘oya

```swift
// Official SDK: https://github.com/robokassa/sdk-ios
// Backend sdk.* maydonlarini SDK init / payment params ga uzating
// Password1/2 ni SDK ga hardcode qilmang — signature_value backenddan
```

> Aniq SDK method nomlari versiyaga bog‘liq. Backend maydonlari barqaror — ularni map qiling.

---

## 7. TypeScript / Dart tiplar

```typescript
type Tariff = {
  code: string;
  title: string;
  description: string;
  price: string;
  currency: string;
  duration_days: number;
  promo_days: number;
  is_recurring: boolean;
  sort_order: number;
};

type Subscription = {
  status: "none" | "trial" | "active" | "past_due" | "cancelled" | "expired";
  tariff: Tariff | null;
  promo_until: string | null;
  premium_until: string | null;
  recurring_enabled: boolean;
  cancelled_at: string | null;
  is_premium: boolean;
  updated_at: string;
};

type Payment = {
  invoice_id: number;
  tariff: string;
  amount: string;
  currency: string;
  kind: "initial" | "recurring" | "one_time";
  status: "pending" | "paid" | "failed" | "cancelled";
  channel: "web" | "mobile_sdk";
  checkout_url: string;
  paid_at: string | null;
  created_at: string;
};

type RobokassaSdkParams = {
  merchant_login: string;
  invoice_id: number;
  out_sum: string;
  description: string;
  signature_value: string;
  culture: string;
  encoding: string;
  is_test: boolean;
  is_recurring: boolean;
  email?: string;
  receipt_json?: string | null;
  receipt?: Record<string, unknown> | null;
};

type MobileCheckoutResponse = {
  provider: "robokassa";
  payment: Payment;
  sdk: RobokassaSdkParams;
};
```

---

## 8. Xatolar va UI

| HTTP | Qachon | UI |
|---|---|---|
| `400` | Validatsiya / consent / promo | `detail` matnini ko‘rsatish |
| `401` | Token | Refresh → qayta urinish / login |
| `404` | Payment topilmadi | Pollingni to‘xtatish |
| `503` | Robokassa sozlanmagan | «Оплата временно недоступна» |

Robokassa SDK ichidagi xatolar (API emas):

| Kod | Ma’nosi |
|---|---|
| `23` | Test sozlamalari Robokassa kabinetida to‘liq emas |
| `29` | Imzo xato (backend/server) |
| `34` | Recurring hali do‘kon uchun yoqilmagan |

---

## 9. Jadval — barcha endpointlar

| # | Method | Mobile (APP) | Web/Desktop |
|---|--------|--------------|-------------|
| 1 | GET | `/api/v1/mobile/premium/tariffs/` | `/api/v1/premium/tariffs/` |
| 2 | GET | `/api/v1/mobile/premium/subscription/` | `/api/v1/premium/subscription/` |
| 3 | POST | `/api/v1/mobile/premium/trial/` | `/api/v1/premium/trial/` |
| 4 | POST | `/api/v1/mobile/premium/checkout/` → **sdk** | `/api/v1/premium/checkout/` → **url** |
| 5 | POST | `/api/v1/mobile/premium/cancel/` | `/api/v1/premium/cancel/` |
| 6 | GET | `/api/v1/mobile/premium/features/` | `/api/v1/premium/features/` |
| 7 | GET | `/api/v1/mobile/premium/payments/{id}/` | — |
| 8 | GET | `/api/v1/mobile/premium/payments/pending/` | — |
| 9 | — | — | `POST /api/v1/premium/robokassa/result/` (faqat Robokassa) |

---

## 10. QA checklist (mobil)

- [ ] JWT bilan `GET .../subscription/` ishlaydi
- [ ] `GET .../tariffs/` narxlarni qaytaradi
- [ ] `POST .../trial/` → `is_premium: true` (agar promo_days > 0)
- [ ] `POST .../checkout/` → `sdk.signature_value` va `invoice_id` keladi
- [ ] `checkout_url` bo‘sh bo‘lishi normal (mobile uchun)
- [ ] SDK ochiladi, test karta bilan to‘lov
- [ ] `GET .../payments/{id}/` → `status: "paid"`
- [ ] `GET .../subscription/` → `is_premium: true`
- [ ] App resume: `payments/pending/` yoki saqlangan `invoice_id` bilan poll
- [ ] `POST .../cancel/` avtoprodlenieni o‘chiradi
- [ ] Kodda `Password1` / `Password2` **yo‘q**
- [ ] Web API (`/api/v1/premium/checkout/`) app da ishlatilmaydi

---

## 11. Tez misol — Postman / curl

```bash
# 1) Status
curl -H "Authorization: Bearer $TOKEN" \
  https://admin.ottertime.ru/api/v1/mobile/premium/subscription/

# 2) Tariflar
curl -H "Authorization: Bearer $TOKEN" \
  https://admin.ottertime.ru/api/v1/mobile/premium/tariffs/

# 3) Checkout (SDK params)
curl -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"tariff":"monthly","recurring_consent":false}' \
  https://admin.ottertime.ru/api/v1/mobile/premium/checkout/

# 4) Polling
curl -H "Authorization: Bearer $TOKEN" \
  https://admin.ottertime.ru/api/v1/mobile/premium/payments/100123/
```

---

## 12. Savol-javob

**Q: Nima uchun web API dan foydalanmaymiz?**  
A: Web `checkout_url` beradi (brauzer). App ga `sdk` + imzo kerak. Ikkala kanal alohida, lekin premium status bitta.

**Q: ResultURL ni app chaqirsinmi?**  
A: Yo‘q. Faqat Robokassa server chaqiradi.

**Q: SDK «успешно» dedi, lekin `is_premium` false?**  
A: 2–5 soniya kutib `payments/{id}/` poll qiling, keyin `subscription/`.

**Q: `is_test: true` nima?**  
A: Robokassa test rejimi. Production da backend `false` qiladi — app faqat `sdk.is_test` ni SDK ga uzatsin.

**Q: Narx 150 ₽ saytda, API da boshqa?**  
A: Haqiqiy narx **Admin → Биллинг → Тарифы** dan keladi. UI da faqat API `price` ni ko‘rsating.

---

## Bog‘liq hujjatlar

| Fayl | Mazmun |
|---|---|
| [PAYMENT_FRONTEND.md](./PAYMENT_FRONTEND.md) | Web / Desktop to‘lovlari |
| [MOBILE_API.md](./MOBILE_API.md) | Umumiy mobile API |
| [ROBOKASSA_SETUP.md](./ROBOKASSA_SETUP.md) | Backend / kabinet sozlamasi (DevOps) |
