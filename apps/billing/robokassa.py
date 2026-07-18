"""Robokassa payment helpers (signature, checkout URL, recurring, fiscal receipt)."""

from __future__ import annotations

import hashlib
import json
import logging
from decimal import Decimal
from typing import Any
from urllib.parse import quote, urlencode

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


class RobokassaError(Exception):
    pass


def _md5(value: str) -> str:
    return hashlib.md5(value.encode("utf-8")).hexdigest()


def _cfg(name: str, default: str = "") -> str:
    return str(getattr(settings, name, default) or default)


def is_configured() -> bool:
    return bool(_cfg("ROBOKASSA_MERCHANT_LOGIN") and _cfg("ROBOKASSA_PASSWORD1") and _cfg("ROBOKASSA_PASSWORD2"))


def recurring_enabled() -> bool:
    """Robokassa must approve recurrents first; otherwise error 34."""
    return bool(getattr(settings, "ROBOKASSA_RECURRING_ENABLED", False))


def is_test_mode() -> bool:
    return _cfg("ROBOKASSA_IS_TEST", "1") in ("1", "true", "True", "yes")


def build_receipt(tariff, quantity: int = 1) -> dict[str, Any]:
    """Номенклатура для фискализации (мать и дочь — одинаково по смыслу)."""
    return {
        "sno": _cfg("ROBOKASSA_SNO", "usn_income"),
        "items": [
            {
                "name": (tariff.receipt_name or tariff.title)[:128],
                "quantity": quantity,
                "sum": float(Decimal(tariff.price) * quantity),
                "payment_method": tariff.payment_method or "full_payment",
                "payment_object": tariff.payment_object or "service",
                "tax": tariff.vat or "none",
            }
        ],
    }


def receipt_json(tariff) -> str:
    return json.dumps(build_receipt(tariff), ensure_ascii=False, separators=(",", ":"))


def _receipt_for_signature(receipt: str) -> str:
    """Receipt в подписи должен быть URL-кодирован (документация Robokassa)."""
    return quote(receipt, safe="")


def _shp_part(shp: dict[str, str] | None) -> str:
    if not shp:
        return ""
    # После Password: :Shp_key=value в алфавитном порядке
    parts = [f"{k}={shp[k]}" for k in sorted(shp.keys())]
    return ":" + ":".join(parts)


def payment_signature(
    out_sum: str | Decimal,
    invoice_id: int,
    receipt: str | None = None,
    shp: dict[str, str] | None = None,
) -> str:
    """
    Официальная формула:
    MerchantLogin:OutSum:InvId[:Receipt]:Password1[:Shp_*=*]

    Receipt в подписи — URL-encoded.
    Shp_* — строго после Password1, по алфавиту.
    """
    login = _cfg("ROBOKASSA_MERCHANT_LOGIN")
    password1 = _cfg("ROBOKASSA_PASSWORD1")
    out = f"{Decimal(out_sum):.2f}"
    chunks = [login, out, str(invoice_id)]
    if receipt:
        chunks.append(_receipt_for_signature(receipt))
    chunks.append(password1)
    raw = ":".join(chunks) + _shp_part(shp)
    return _md5(raw)


def result_signature(out_sum: str, invoice_id: int, shp: dict[str, str] | None = None) -> str:
    """OutSum:InvId:Password2[:Shp_*=*]"""
    password2 = _cfg("ROBOKASSA_PASSWORD2")
    raw = f"{out_sum}:{invoice_id}:{password2}" + _shp_part(shp)
    return _md5(raw)


def extract_shp(data: dict) -> dict[str, str]:
    return {k: str(v) for k, v in data.items() if str(k).startswith("Shp_")}


def verify_result_signature(out_sum: str, invoice_id: int, signature: str, shp: dict[str, str] | None = None) -> bool:
    candidates = {
        result_signature(out_sum, invoice_id, shp).lower(),
    }
    try:
        normalized = f"{Decimal(out_sum):.2f}"
        candidates.add(result_signature(normalized, invoice_id, shp).lower())
    except Exception:
        pass
    return (signature or "").lower() in candidates


def build_checkout_url(
    *,
    out_sum: Decimal,
    invoice_id: int,
    description: str,
    tariff,
    recurring: bool = False,
    user_email: str | None = None,
    shp: dict[str, str] | None = None,
) -> str:
    if not is_configured():
        raise RobokassaError("Robokassa credentials are not configured in .env")

    send_receipt = bool(getattr(settings, "ROBOKASSA_SEND_RECEIPT", False))
    receipt = receipt_json(tariff) if send_receipt else None
    out = f"{Decimal(out_sum):.2f}"
    signature = payment_signature(out, invoice_id, receipt=receipt, shp=shp)

    params: dict[str, Any] = {
        "MerchantLogin": _cfg("ROBOKASSA_MERCHANT_LOGIN"),
        "OutSum": out,
        "InvId": invoice_id,
        "Description": description[:100],
        "SignatureValue": signature,
        "Culture": "ru",
        "Encoding": "utf-8",
    }
    if receipt:
        params["Receipt"] = receipt
    if recurring:
        params["Recurring"] = "true"
    if user_email:
        params["Email"] = user_email
    if is_test_mode():
        params["IsTest"] = "1"
    if shp:
        params.update(shp)

    base = _cfg("ROBOKASSA_PAYMENT_URL", "https://auth.robokassa.ru/Merchant/Index.aspx")
    return f"{base}?{urlencode(params)}"


def build_sdk_params(
    *,
    out_sum: Decimal,
    invoice_id: int,
    description: str,
    tariff,
    recurring: bool = False,
    user_email: str | None = None,
    shp: dict[str, str] | None = None,
) -> dict[str, Any]:
    """
    Параметры для Robokassa Mobile SDK (Android / iOS).
    Пароли Password1/Password2 клиенту не отдаём — только SignatureValue с бэкенда.
    """
    if not is_configured():
        raise RobokassaError("Robokassa credentials are not configured in .env")

    send_receipt = bool(getattr(settings, "ROBOKASSA_SEND_RECEIPT", False))
    receipt_obj = build_receipt(tariff) if send_receipt else None
    receipt = receipt_json(tariff) if send_receipt else None
    out = f"{Decimal(out_sum):.2f}"
    signature = payment_signature(out, invoice_id, receipt=receipt, shp=shp)

    params: dict[str, Any] = {
        "merchant_login": _cfg("ROBOKASSA_MERCHANT_LOGIN"),
        "invoice_id": invoice_id,
        "out_sum": out,
        "description": description[:100],
        "signature_value": signature,
        "culture": "ru",
        "encoding": "utf-8",
        "is_test": is_test_mode(),
        "is_recurring": bool(recurring),
    }
    if user_email:
        params["email"] = user_email
    if receipt:
        params["receipt_json"] = receipt
    if receipt_obj:
        params["receipt"] = receipt_obj
    if shp:
        params["shp"] = shp
    return params


def charge_recurring(
    *,
    out_sum: Decimal,
    invoice_id: int,
    previous_invoice_id: int,
    description: str,
    tariff,
    shp: dict[str, str] | None = None,
) -> tuple[bool, str]:
    if not is_configured():
        raise RobokassaError("Robokassa credentials are not configured in .env")

    send_receipt = bool(getattr(settings, "ROBOKASSA_SEND_RECEIPT", False))
    receipt = receipt_json(tariff) if send_receipt else None
    out = f"{Decimal(out_sum):.2f}"
    signature = payment_signature(out, invoice_id, receipt=receipt, shp=shp)

    data = {
        "MerchantLogin": _cfg("ROBOKASSA_MERCHANT_LOGIN"),
        "InvoiceID": str(invoice_id),
        "PreviousInvoiceID": str(previous_invoice_id),
        "OutSum": out,
        "Description": description[:100],
        "SignatureValue": signature,
    }
    if receipt:
        data["Receipt"] = receipt
    if shp:
        data.update(shp)
    if _cfg("ROBOKASSA_IS_TEST", "1") in ("1", "true", "True", "yes"):
        data["IsTest"] = "1"

    url = _cfg("ROBOKASSA_RECURRING_URL", "https://auth.robokassa.ru/Merchant/Recurring")
    try:
        response = requests.post(url, data=data, timeout=30)
        body = (response.text or "").strip()
        logger.info("Robokassa recurring response invoice=%s body=%s", invoice_id, body[:200])
        return body.upper().startswith("OK"), body
    except requests.RequestException as exc:
        logger.exception("Robokassa recurring request failed")
        return False, str(exc)
