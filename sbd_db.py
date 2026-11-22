"""Supabase access for Stanley Black & Decker Innovation Assessment (sbd_* tables)."""
from __future__ import annotations

import base64
import hmac
import hashlib
import os
from datetime import datetime, timezone
from typing import Any, Optional

import streamlit as st
from supabase import Client, create_client

DEFAULT_PASSWORD = "1234567"
PBKDF2_ROUNDS = 120_000
LOGO_MAX_BYTES = 500_000
LOGO_ALLOWED_TYPES = {"image/png", "image/jpeg", "image/jpg", "image/webp"}
ORG_NAME = "Stanley Black & Decker"


def _secret(*names: str, default: str = "") -> str:
    for name in names:
        try:
            val = st.secrets.get(name)
            if val is not None and str(val).strip():
                return str(val).strip()
        except Exception:
            pass
        env = os.environ.get(name, "")
        if env and str(env).strip():
            return str(env).strip()
    return str(default or "").strip()


def get_client() -> Optional[Client]:
    # Same aliases as TechLife / Innovation Analysis Cloud secrets.
    url = _secret("SUPABASE_STOCK_URL", "SUPABASE_URL")
    key = _secret(
        "SUPABASE_STOCK_SECRET_KEY",
        "SUPABASE_SERVICE_ROLE_KEY",
        "SUPABASE_KEY",
        "SUPABASE_ANON_KEY",
    )
    if not url or not key:
        return None
    return create_client(url.rstrip("/"), key)


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ROUNDS)
    return salt.hex() + "$" + dk.hex()


def verify_password(password: str, stored: str) -> bool:
    try:
        salt_hex, dk_hex = stored.split("$", 1)
        salt = bytes.fromhex(salt_hex)
        dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ROUNDS)
        return hmac.compare_digest(dk.hex(), dk_hex)
    except Exception:
        return False


def normalize_email(email: str) -> str:
    return (email or "").strip().lower()


def get_user(email: str) -> Optional[dict[str, Any]]:
    client = get_client()
    if not client:
        return None
    email = normalize_email(email)
    if not email:
        return None
    res = client.table("sbd_users").select("*").eq("email", email).limit(1).execute()
    rows = res.data or []
    return rows[0] if rows else None


def list_users() -> list[dict[str, Any]]:
    client = get_client()
    if not client:
        return []
    res = client.table("sbd_users").select("*").order("created_at", desc=True).execute()
    return list(res.data or [])


def upsert_user(email: str, *, status: str = "approved", password: Optional[str] = None) -> None:
    client = get_client()
    if not client:
        raise RuntimeError(
            "Supabase is not configured. In Streamlit Cloud Secrets set "
            "SUPABASE_STOCK_URL and SUPABASE_STOCK_SECRET_KEY "
            "(same values as TechLife), or SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY."
        )
    email = normalize_email(email)
    if not email or "@" not in email:
        raise ValueError("Invalid email")
    existing = get_user(email)
    payload: dict[str, Any] = {
        "email": email,
        "status": status,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    if existing is None:
        payload["password_hash"] = hash_password(password or DEFAULT_PASSWORD)
        client.table("sbd_users").insert(payload).execute()
        return
    if password:
        payload["password_hash"] = hash_password(password)
    client.table("sbd_users").update(payload).eq("email", email).execute()


def set_password(email: str, password: str) -> None:
    client = get_client()
    if not client:
        raise RuntimeError(
            "Supabase is not configured. In Streamlit Cloud Secrets set "
            "SUPABASE_STOCK_URL and SUPABASE_STOCK_SECRET_KEY "
            "(same values as TechLife), or SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY."
        )
    email = normalize_email(email)
    client.table("sbd_users").update(
        {
            "password_hash": hash_password(password),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
    ).eq("email", email).execute()


def delete_user(email: str) -> None:
    client = get_client()
    if not client:
        raise RuntimeError(
            "Supabase is not configured. In Streamlit Cloud Secrets set "
            "SUPABASE_STOCK_URL and SUPABASE_STOCK_SECRET_KEY "
            "(same values as TechLife), or SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY."
        )
    email = normalize_email(email)
    client.table("sbd_users").delete().eq("email", email).execute()


def record_login(email: str) -> None:
    client = get_client()
    if not client:
        return
    email = normalize_email(email)
    client.table("sbd_login_events").insert({"email": email}).execute()


def last_logins(email: str, n: int = 5) -> list[str]:
    client = get_client()
    if not client:
        return []
    email = normalize_email(email)
    res = (
        client.table("sbd_login_events")
        .select("logged_at")
        .eq("email", email)
        .order("logged_at", desc=True)
        .limit(n)
        .execute()
    )
    out = []
    for row in res.data or []:
        ts = row.get("logged_at") or ""
        out.append(str(ts).replace("T", " ")[:19])
    return out


def create_access_request(email: str, message: str = "") -> None:
    client = get_client()
    if not client:
        raise RuntimeError(
            "Supabase is not configured. In Streamlit Cloud Secrets set "
            "SUPABASE_STOCK_URL and SUPABASE_STOCK_SECRET_KEY "
            "(same values as TechLife), or SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY."
        )
    email = normalize_email(email)
    client.table("sbd_access_requests").insert(
        {"email": email, "message": (message or "").strip(), "status": "pending"}
    ).execute()


def list_pending_requests() -> list[dict[str, Any]]:
    client = get_client()
    if not client:
        return []
    res = (
        client.table("sbd_access_requests")
        .select("*")
        .eq("status", "pending")
        .order("created_at", desc=True)
        .execute()
    )
    return list(res.data or [])


def set_request_status(request_id: str, status: str) -> None:
    client = get_client()
    if not client:
        return
    client.table("sbd_access_requests").update({"status": status}).eq("id", request_id).execute()


def get_admin_emails() -> list[str]:
    emails: list[str] = []
    fallback = _secret("ADMIN_EMAIL") or _secret("SMTP_FROM") or _secret("SMTP_FROM_EMAIL") or _secret("SMTP_USER")
    if fallback:
        emails.append(normalize_email(fallback))
    client = get_client()
    if client:
        try:
            res = client.table("sbd_settings").select("admin_emails").eq("id", 1).limit(1).execute()
            rows = res.data or []
            if rows:
                raw = rows[0].get("admin_emails") or ""
                for part in str(raw).replace(";", ",").split(","):
                    e = normalize_email(part)
                    if e and e not in emails:
                        emails.append(e)
        except Exception:
            pass
    return emails


def set_admin_emails(raw: str) -> None:
    client = get_client()
    if not client:
        raise RuntimeError(
            "Supabase is not configured. In Streamlit Cloud Secrets set "
            "SUPABASE_STOCK_URL and SUPABASE_STOCK_SECRET_KEY "
            "(same values as TechLife), or SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY."
        )
    cleaned = ",".join(
        normalize_email(p) for p in str(raw).replace(";", ",").split(",") if normalize_email(p)
    )
    client.table("sbd_settings").upsert({"id": 1, "admin_emails": cleaned}).execute()


def get_settings() -> dict[str, Any]:
    client = get_client()
    if not client:
        return {}
    try:
        res = client.table("sbd_settings").select("*").eq("id", 1).limit(1).execute()
        rows = res.data or []
        return dict(rows[0]) if rows else {}
    except Exception:
        return {}


def _portal_sbd_logo() -> str:
    """Reuse the logo already uploaded on the TechLife SBD organization, if any."""
    client = get_client()
    if not client:
        return ""
    try:
        res = (
            client.table("organizations")
            .select("logo_url,name,name_zh,name_en")
            .execute()
        )
    except Exception:
        return ""
    for row in res.data or []:
        blob = " ".join(
            str(row.get(k) or "") for k in ("name", "name_zh", "name_en")
        ).lower()
        if "stanley" in blob or "black & decker" in blob or "black and decker" in blob:
            return str(row.get("logo_url") or "").strip()
    return ""


def get_logo_url() -> str:
    settings = get_settings()
    if "logo_url" not in settings:
        return _portal_sbd_logo()
    stored = settings.get("logo_url")
    if stored is None:
        return _portal_sbd_logo()
    text = str(stored).strip()
    return text


def set_logo(file_bytes: bytes, content_type: str) -> tuple[bool, str]:
    client = get_client()
    if not client:
        return False, "not_configured"
    if not file_bytes:
        return False, "empty_file"
    if len(file_bytes) > LOGO_MAX_BYTES:
        return False, "too_large"
    normalized_type = (content_type or "").lower()
    if normalized_type == "image/jpg":
        normalized_type = "image/jpeg"
    if normalized_type not in LOGO_ALLOWED_TYPES:
        return False, "invalid_type"
    encoded = base64.b64encode(file_bytes).decode("ascii")
    data_url = f"data:{normalized_type};base64,{encoded}"
    try:
        client.table("sbd_settings").upsert({"id": 1, "logo_url": data_url}).execute()
        return True, ""
    except Exception as exc:
        detail = str(exc)
        if "logo_url" in detail and "column" in detail.lower():
            return False, "missing_column"
        return False, detail or "update_failed"


def clear_logo() -> tuple[bool, str]:
    client = get_client()
    if not client:
        return False, "not_configured"
    try:
        client.table("sbd_settings").upsert({"id": 1, "logo_url": ""}).execute()
        return True, ""
    except Exception as exc:
        detail = str(exc)
        if "logo_url" in detail and "column" in detail.lower():
            return False, "missing_column"
        return False, detail or "update_failed"
