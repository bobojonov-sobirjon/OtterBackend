# OTTER — Robokassa + Подписки (Setup Guide)

> Kod yozilmaydi — faqat sozlash, kalitlar, tariflar va arxitektura.  
> Magazin: **OTTER** · Identifikator: **`ottertime`** · Sayt: `https://otters.me.ru/`

---

## 1. Asosiy g‘oya (app + web + desktop)

**Bitta backend, bitta Robokassa, bitta premium status.**

```
┌─────────┐   ┌─────────┐   ┌──────────┐
│  App    │   │   Web   │   │ Desktop  │
└────┬────┘   └────┬────┘   └────┬─────┘
     │             │             │
     └─────────────┼─────────────┘
                   ▼
         ┌──────────────────┐
         │  Otter Backend   │  ← JWT bilan user aniqlanadi
         │  /premium/...    │
         └────────┬─────────┘
                  ▼
         ┌──────────────────┐
         │    Robokassa     │  ← to‘lov
         │  Merchant: ottertime
         └────────┬─────────┘
                  ▼
         Result URL → Backend
         (premium yoqiladi)
```

| Platforma | Nima qiladi |
|---|---|
| App / Web / Desktop | Tarif tanlaydi → backenddan `checkout_url` oladi → brauzer/WebView ochadi |
| Backend | To‘lov linkini yaratadi, Robokassa callbackini qabul qiladi, `is_premium` ni yoqadi |
| Robokassa | Pulni oladi, Result URL ga xabar yuboradi |

**Muhim:** Har bir platforma uchun alohida Robokassa kaliti **kerak emas**. Bitta magazin (`ottertime`) yetadi.

---

## 2. Robokassa dan qanday kalitlar olish

Kabinet: [https://auth.robokassa.ru](https://auth.robokassa.ru) → magazin **OTTER**.

### 2.1 «Технические настройки» tabiga o‘ting

Hozir screenshot da «Карточка магазина» ochiq. Kerakli joy:

**Технические настройки**

U yerda quyidagilar bo‘ladi:

| Kalit / maydon | Nima uchun | Kim ishlatadi |
|---|---|---|
| **Идентификатор магазина** | `MerchantLogin` | Backend (allaqachon: `ottertime`) |
| **Пароль #1** | To‘lov linki / Signature yaratish | **Faqat Backend** |
| **Пароль #2** | Result URL (callback) tekshirish | **Faqat Backend** |
| **Пароль #3** (ixtiyoriy) | Success URL tekshirish | Backend / kam ishlatiladi |

### 2.2 `.env` ga qo‘yiladiganlar (server)

```env
ROBOKASSA_MERCHANT_LOGIN=ottertime
ROBOKASSA_PASSWORD1=xxxxxxxx          # Пароль #1
ROBOKASSA_PASSWORD2=yyyyyyyy          # Пароль #2
ROBOKASSA_IS_TEST=1                   # Test rejim: 1, Production: 0
ROBOKASSA_RESULT_URL=https://admin.ottertime.ru/api/v1/premium/robokassa/result/
ROBOKASSA_SUCCESS_URL=https://otters.me.ru/premium/success
ROBOKASSA_FAIL_URL=https://otters.me.ru/premium/fail
```

| Qoida | |
|---|---|
| Password1 / Password2 | **Hech qachon** app/web/desktop ga bermang |
| Frontend | Faqat backend bergan `checkout_url` ni ochadi |
| Test | Avval `IsTest=1` bilan sinang, keyin production |

---

## 3. Robokassa «Технические настройки» da URL lar

| Maydon | Qiymat (misol) | Kimga |
|---|---|---|
| **Result URL** | `https://admin.ottertime.ru/api/v1/premium/robokassa/result/` | Backend (server-to-server) |
| **Success URL** | `https://otters.me.ru/premium/success` | Foydalanuvchi brauzeri (web) |
| **Fail URL** | `https://otters.me.ru/premium/fail` | Foydalanuvchi brauzeri (web) |
| Method | **POST** (Result URL uchun tavsiya) | — |

### Nima farqi?

| URL | Vazifa |
|---|---|
| **Result URL** | Robokassa serverga «to‘lov muvaffaqiyatli» deb yozadi. **Premium shu yerda yoqiladi.** |
| **Success URL** | Foydalanuvchiga «Rahmat, to‘lov o‘tdi» sahifasi. Premium yoqish uchun **ishonchli emas**. |
| **Fail URL** | To‘lov bekor / xato sahifasi. |

> App va Desktop da Success/Fail URL brauzerda ochiladi; premium statusni ilova `GET /settings/` yoki `GET /premium/features/` orqali yangilab oladi.

---

## 4. Tariflar (подписки) — qanday tuzish

Sizda podpiska + tariflar bo‘lishi kerak. Tavsiya: **tariflar backendda**, Robokassa faqat **summa + InvId** oladi.

### 4.1 Tariflar jadvali (biznes)

| Kod (`tariff`) | Nom | Narx (misol) | Muddat | Robokassa |
|---|---|---|---|---|
| `monthly` | Месяц | 299 ₽ | 30 kun | Bir martalik to‘lov |
| `yearly` | Год | 2490 ₽ | 365 kun | Bir martalik to‘lov |
| `lifetime` | Навсегда | 4990 ₽ | cheksiz | Bir martalik to‘lov |

Narxlarni o‘zingiz belgilaysiz — bu faqat misol.

### 4.2 Promo-period (пробный период) — muhim qaror

Mijoz / integrator tasdiqlagan:

| Variant | Qayerda | Natija |
|---|---|---|
| RusPay | Kabinetda promo sozlanadi | Robokassa emas |
| **Robokassa** | Kabinetda promo **yo‘q** | To‘lov darhol boshlanadi |
| **Variant 2 (tanlangan)** | **Bizning backend/sayt** | Promo muddatni o‘zimiz hisoblaymiz |

**Xulosa:** Promo-period Robokassa da emas — **bizning tizimda**.

```text
User obuna tanladi
    ↓
Backend: promo_days beriladi (masalan 7 kun)
    ↓
is_premium = true, premium_until = now + 7 kun
    ↓  (hali Robokassa ga pul yuborilmaydi)
Cron / script: promo tugadi?
    ↓ Ha
Birinchi to‘lov (yoki recurring maternal) ishga tushadi
```

Yoki boshqa model: birinchi to‘lov 0 ₽ emas, balki promo tugagach birinchi yechim — biznes qarori.

### 4.3 Recurring (автосписание) — Robokassa

Hujjatlar:
- [Recurring payments](https://docs.robokassa.ru/ru/recurring-payments)
- [Fiscalization / номенклатура](https://docs.robokassa.ru/ru/fiscalization)

**Texnik:**
1. **Materinskiy** to‘lov: oddiy checkout + `Recurring=true`
2. Keyingi oy: backend → `https://auth.robokassa.ru/Merchant/Recurring` + `PreviousInvoiceID`
3. Har bir to‘lovda (ona + bola) **номенклатура** (чек uchun) majburiy
4. Muvaffaqiyat — faqat Result URL / XML orqali tekshiriladi (`OK+InvoiceId` = operatsiya yaratildi, pul hali kafolatlanmagan)

**Robokassa yoqishi uchun** (kabinet so‘rovi + skrinshotlar):

#### Hujjatlar (saytda)
- [ ] Публичная оферта — recurring bo‘limi bilan
- [ ] Политика конфиденциальности
- [ ] Согласие на обработку ПДн

#### Офертада majburiy
- [ ] Obuna shartlari (muddat, narx)
- [ ] Pul yechish tartibi (sana, vaqt)
- [ ] Bekor qilish usullari
- [ ] Pul qaytarish tartibi
- [ ] Narx o‘zgarishi shartlari

#### To‘lov formasi (web)
- [ ] Checkbox: «Я согласен на автоматические списания…» (**default OFF**)
- [ ] Офертаga klikable link
- [ ] Periodiklik haqida matn
- [ ] Rozilik tarixi DB da saqlanadi

#### Taqiqlangan
- Yashirin to‘lovlar
- Bekor qilishni qiyinlashtirish
- Ogohlantirishsiz avtoprolongatsiya
- Ogohlantirishsiz narx o‘zgartirish

#### Robokassa ga yuborish
Kabinetda so‘rov: magazin ID = **`ottertime`** + obuna/bekor UI + checkbox skrinshotlari.

### 4.4 Boshlash tartibi (tavsiya)

| Bosqich | Nima |
|---|---|
| **A** | Oddiy to‘lov + tariflar + `premium_until` (promo backendda) |
| **B** | Yuridik hujjatlar + checkbox + rozilik tarixi |
| **C** | Recurring yoqish (Robokassa so‘rovi) + maternal/child to‘lovlar |
| **D** | Fiscalization (номенклатура) har to‘lovda |

### 4.5 Backendda nima saqlanadi (konsept)

Har bir user uchun:

| Maydon | Ma’nosi |
|---|---|
| `is_premium` | Hozir premium bormi |
| `premium_activated_at` | Qachon yoqilgan |
| `premium_until` | Qachongacha (promo yoki to‘langan muddat) |
| `promo_until` | Promo tugash sanasi (agar bor) |
| `tariff` | Qaysi tarif (`monthly` / `yearly` / …) |
| `parent_invoice_id` | Recurring ona to‘lov InvId |
| `recurring_consent_at` | Avtosписание ga rozilik vaqti |
| `last_payment_id` | Oxirgi Robokassa InvId |

Tarif katalogi (admin yoki DB):

| Maydon | Misollar |
|---|---|
| `code` | `monthly` |
| `title` | `Месячная подписка` |
| `price` | `299.00` |
| `currency` | `RUB` |
| `duration_days` | `30` |
| `is_active` | `true` |

---

## 5. To‘lov flow (barcha platformalar bir xil)

```text
1. User tarif tanlaydi (monthly / yearly)
2. Client → POST /api/v1/premium/checkout/  { "tariff": "monthly" }
3. Backend:
   - user + tariff bo‘yicha summa oladi
   - InvId yaratadi (unique)
   - Signature = MD5(MerchantLogin:OutSum:InvId:Password1)
   - checkout_url qaytaradi
4. Client checkout_url ni ochadi (WebView / browser / system browser)
5. User Robokassa da to‘laydi
6. Robokassa → POST Result URL (backend)
7. Backend Signature2 ni Password2 bilan tekshiradi
8. To‘lov OK → is_premium=true, premium_until=now+duration
9. Backend Robokassa ga javob: OK{InvId}
10. Client Success sahifaga tushadi / ilova statusni yangilaydi
```

### Platforma farqlari (faqat UI)

| Platforma | Checkout ochish |
|---|---|
| **Web** | `window.location = checkout_url` yoki yangi tab |
| **App** | WebView yoki tashqi brauzer |
| **Desktop** | System browser |

Backend API **bir xil**.

---

## 6. Hozirgi backend holati (Otter)

Implementatsiya: app `apps/billing`.

| Endpoint | Holat |
|---|---|
| `GET /premium/tariffs/` | ✅ |
| `GET /premium/subscription/` | ✅ |
| `POST /premium/trial/` | ✅ promo bizda |
| `POST /premium/checkout/` | ✅ haqiqiy Robokassa URL (+ Receipt + Recurring) |
| `POST /premium/robokassa/result/` | ✅ ResultURL |
| `POST /premium/cancel/` | ✅ |
| `POST /premium/activate/` | ✅ faqat DEBUG |
| `GET /premium/features/` | ✅ |
| Cron | `python manage.py process_subscriptions` |

Default tariflar: `monthly` (7 kun promo), `yearly`, `lifetime`.

---

## 7. Checklist — Robokassa kabinet

- [ ] Magazin **OTTER** aktiv (`ottertime`)
- [ ] **Технические настройки** ochildi
- [ ] **Пароль #1** va **Пароль #2** nusxa olindi (xavfsiz joyga)
- [ ] **Result URL** = `https://admin.ottertime.ru/api/v1/premium/robokassa/result/`
- [ ] **Success URL** / **Fail URL** = web sahifalar
- [ ] **Алгоритм** = MD5
- [ ] Test rejim yoqilgan
- [ ] Recurring yoqish uchun kabinetga so‘rov + skrinshotlar

---

## 8. Checklist — Backend `.env`

- [ ] `ROBOKASSA_MERCHANT_LOGIN=ottertime`
- [ ] `ROBOKASSA_PASSWORD1=...`
- [ ] `ROBOKASSA_PASSWORD2=...`
- [ ] `ROBOKASSA_IS_TEST=1` (keyin `0`)
- [ ] `ROBOKASSA_RESULT_URL=...`

---

## 9. Checklist — Tariflar / frontend

- [ ] Admin da narxlar to‘g‘ri
- [ ] Checkbox default OFF + оферта link
- [ ] `POST /premium/trial/` yoki `checkout` + `recurring_consent`
- [ ] Cron: `python manage.py process_subscriptions` (soatiga)

---

## 10. Xavfsizlik

| Qilish | Qilmaslik |
|---|---|
| Password1/2 faqat server `.env` | Kalitlarni mobil/web kodga yozish |
| Premium faqat Result URL dan yoqish | Faqat Success URL ga ishonish |
| Signature tekshirish majburiy | `activate` ni production da ochiq qoldirish |

---

## 11. Kalitlar kelganda

`.env` ga qo‘ying va serverni restart qiling:

```env
ROBOKASSA_PASSWORD1=...
ROBOKASSA_PASSWORD2=...
ROBOKASSA_RESULT_URL=https://admin.ottertime.ru/api/v1/premium/robokassa/result/
ROBOKASSA_IS_TEST=1
```
