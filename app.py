"""Stanley Black & Decker Innovation Assessment — independent Streamlit app."""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

import jwt
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from assessment import render_innovation_app, set_app_language
from email_smtp import send_email, smtp_configured
from portal_enterprise_ui import ensure_enterprise_session_defaults, enterprise_brand_markup
import sbd_db

st.set_page_config(page_title="SBD Innovation Assessment", page_icon="🔹", layout="wide")

REMEMBER_DAYS = 30
TOKEN_QUERY = "sbd"
DEFAULT_PUBLIC_URL = "https://sbd-innovation.streamlit.app"


def _secret(name: str, default: str = "") -> str:
    try:
        val = st.secrets.get(name)
        if val is not None and str(val).strip():
            return str(val).strip()
    except Exception:
        pass
    return str(os.environ.get(name, default) or default).strip()


def admin_username() -> str:
    return _secret("ADMIN_USERNAME") or "Laurence_ku"


def admin_password() -> str:
    return _secret("ADMIN_PASSWORD") or "Ku_product$2026"


def jwt_secret() -> str:
    return _secret("JWT_SECRET_KEY") or _secret("SBD_JWT_SECRET") or "sbd-change-me"


def t() -> dict:
    zh = st.session_state.get("lang", "zh") == "zh"
    if zh:
        return {
            "title": "Innovation Assessment  创新评估",
            "subtitle": "请使用已开通的邮箱登录。新用户请先申请开通。",
            "email": "邮箱",
            "password": "密码",
            "login": "登录",
            "apply": "申请开通",
            "apply_hint": "提交后由管理员审核。通过后会发邮件通知您如何登录。",
            "apply_msg": "备注（可选）",
            "apply_ok": "申请已提交，请等待管理员审核。",
            "login_fail": "邮箱或密码不正确，或账号尚未开通。",
            "pending": "该邮箱已提交申请，正在等待审核。",
            "disabled": "该账号已被停用，请联系管理员。",
            "chinese": "中文",
            "english": "English",
            "admin_title": "管理员登录",
            "admin_user": "登录名",
            "admin_pw": "密码",
            "admin_btn": "管理员登录",
            "admin_back": "返回",
            "admin_error": "管理员账号或密码错误",
            "admin_panel": "管理员",
            "users": "用户列表",
            "add_user": "新增用户",
            "delete": "删除",
            "requests": "开通申请",
            "approve": "通过",
            "reject": "拒绝",
            "admin_emails": "管理员邮箱（申请通知，逗号分隔）",
            "save": "保存",
            "logout": "退出管理员",
            "last5": "最近 5 次登录",
            "col_email": "用户名字（Email）",
            "col_created": "用户建立时间",
            "col_login": "最近登录",
            "none": "无",
            "org_logo": "企业 Logo",
            "upload_logo": "上传 Logo（PNG/JPG/WebP，不超过 500KB）",
            "save_logo": "保存 Logo",
            "remove_logo": "删除 Logo",
            "logo_saved": "Logo 已更新",
            "logo_removed": "Logo 已删除",
            "logo_too_large": "图片过大，请小于 500KB",
            "logo_invalid_type": "仅支持 PNG、JPG 或 WebP",
            "logo_migration_hint": "请先在 Supabase 执行 sql/sbd_migration_logo.sql",
            "mail_admin_ok": "已邮件通知管理员。",
            "mail_admin_fail": "申请已提交，但未能通知管理员：",
            "mail_no_admin": "请先在管理员后台填写管理员邮箱，并配置 SMTP。",
            "mail_user_ok": "已邮件通知用户登录密码。",
            "mail_user_fail": "账号已开通，但发信失败：",
            "smtp_missing": "邮件未配置。请在 Streamlit Secrets 填写与 TechLife 相同的 SMTP_HOST / SMTP_USER / SMTP_PASSWORD / SMTP_FROM。",
            "link_invalid": "审核链接无效或已过期。",
            "already_approved": "该申请已经开通。",
            "approved_mail_ok": "已开通，登录密码已发到用户邮箱。",
            "approved_mail_fail": "已开通，但给用户发信失败：",
            "rejected_ok": "已拒绝该申请。",
        }
    return {
        "title": "Innovation Assessment  创新评估",
        "subtitle": "Sign in with an approved email. New users should apply first.",
        "email": "Email",
        "password": "Password",
        "login": "Sign in",
        "apply": "Apply for access",
        "apply_hint": "An admin will review your request. After approval you will receive an email with how to sign in.",
        "apply_msg": "Note (optional)",
        "apply_ok": "Application submitted. Please wait for admin approval.",
        "login_fail": "Wrong email or password, or the account is not approved yet.",
        "pending": "This email has a pending application.",
        "disabled": "This account is disabled. Contact an administrator.",
        "chinese": "中文",
        "english": "English",
        "admin_title": "Admin login",
        "admin_user": "Username",
        "admin_pw": "Password",
        "admin_btn": "Admin sign in",
        "admin_back": "Back",
        "admin_error": "Wrong admin username or password",
        "admin_panel": "Admin",
        "users": "Users",
        "add_user": "Add user",
        "delete": "Delete",
        "requests": "Access requests",
        "approve": "Approve",
        "reject": "Reject",
        "admin_emails": "Admin emails (application notices, comma-separated)",
        "save": "Save",
        "logout": "Leave admin",
        "last5": "Last 5 logins",
        "col_email": "User name (Email)",
        "col_created": "Created at",
        "col_login": "Last login",
        "none": "None",
        "org_logo": "Organization Logo",
        "upload_logo": "Upload logo (PNG/JPG/WebP, max 500KB)",
        "save_logo": "Save Logo",
        "remove_logo": "Remove Logo",
        "logo_saved": "Logo updated",
        "logo_removed": "Logo removed",
        "logo_too_large": "Image too large. Max 500KB.",
        "logo_invalid_type": "Only PNG, JPG, or WebP is supported",
        "logo_migration_hint": "Run sql/sbd_migration_logo.sql in Supabase first",
        "mail_admin_ok": "Admins have been emailed.",
        "mail_admin_fail": "Application saved, but the admin email failed: ",
        "mail_no_admin": "Set admin emails in the admin panel and configure SMTP.",
        "mail_user_ok": "The user was emailed their login password.",
        "mail_user_fail": "Account approved, but the email failed: ",
        "smtp_missing": "Email is not configured. In Streamlit Secrets set the same SMTP_HOST / SMTP_USER / SMTP_PASSWORD / SMTP_FROM as TechLife.",
        "link_invalid": "This review link is invalid or expired.",
        "already_approved": "This request was already approved.",
        "approved_mail_ok": "Approved. The login password was emailed to the user.",
        "approved_mail_fail": "Approved, but the user email failed: ",
        "rejected_ok": "This request was rejected.",
    }


def _init_state() -> None:
    defaults = {
        "lang": "zh",
        "sbd_authenticated": False,
        "sbd_user_email": "",
        "sbd_admin": False,
        "show_admin_login": False,
        "sbd_shell": True,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v
    if st.session_state.lang not in ("zh", "en"):
        st.session_state.lang = "zh"
    ensure_enterprise_session_defaults()


def _issue_token(email: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "email": sbd_db.normalize_email(email),
        "exp": now + timedelta(days=REMEMBER_DAYS),
        "iat": now,
        "typ": "sbd",
    }
    return jwt.encode(payload, jwt_secret(), algorithm="HS256")


def _decode_token(token: str) -> str:
    try:
        payload = jwt.decode(token, jwt_secret(), algorithms=["HS256"])
    except jwt.PyJWTError:
        return ""
    if payload.get("typ") != "sbd":
        return ""
    return sbd_db.normalize_email(str(payload.get("email") or ""))


def _persist_token(token: str) -> None:
    st.query_params[TOKEN_QUERY] = token
    components.html(
        f"""
        <script>
        try {{ localStorage.setItem("sbd_ia", {token!r}); }} catch (e) {{}}
        </script>
        """,
        height=0,
    )


def _clear_token() -> None:
    try:
        del st.query_params[TOKEN_QUERY]
    except Exception:
        pass
    components.html(
        """
        <script>
        try { localStorage.removeItem("sbd_ia"); } catch (e) {}
        </script>
        """,
        height=0,
    )


def _restore_session() -> None:
    if st.session_state.sbd_authenticated:
        return
    token = ""
    raw = st.query_params.get(TOKEN_QUERY)
    if isinstance(raw, list):
        token = raw[0] if raw else ""
    else:
        token = raw or ""
    email = _decode_token(token) if token else ""
    if not email:
        return
    user = sbd_db.get_user(email)
    if not user or user.get("status") != "approved":
        return
    _enter_user(email, record=False, persist=False)


def _remember_bridge() -> None:
    components.html(
        """
        <script>
        (function () {
          try {
            var t = localStorage.getItem("sbd_ia");
            if (!t) return;
            var url = new URL(window.parent.location.href);
            if (url.searchParams.get("sbd")) return;
            url.searchParams.set("sbd", t);
            window.parent.location.href = url.toString();
          } catch (e) {}
        })();
        </script>
        """,
        height=0,
    )


def _enter_user(email: str, *, record: bool, persist: bool) -> None:
    email = sbd_db.normalize_email(email)
    st.session_state.sbd_authenticated = True
    st.session_state.sbd_user_email = email
    st.session_state.user_email = email
    st.session_state.username = email.split("@")[0] if "@" in email else email
    st.session_state.user_id = email
    st.session_state.show_admin_login = False
    apply_branding()
    if persist:
        _persist_token(_issue_token(email))
    if record:
        try:
            sbd_db.record_login(email)
        except Exception:
            pass


def _logout_user() -> None:
    st.session_state.sbd_authenticated = False
    st.session_state.sbd_user_email = ""
    st.session_state.user_email = ""
    st.session_state.user_id = None
    st.session_state.organization_id = None
    st.session_state["_sbd_logout"] = False
    st.session_state.pop("_sbd_change_pw", None)
    _clear_token()


def smtp_settings() -> dict:
    user = _secret("SMTP_USER") or _secret("SMTP_USERNAME")
    return {
        "host": _secret("SMTP_HOST") or _secret("SMTP_SERVER") or "smtp.gmail.com",
        "port": int(_secret("SMTP_PORT") or "587"),
        "user": user,
        "password": _secret("SMTP_PASSWORD"),
        "mail_from": _secret("SMTP_FROM") or _secret("SMTP_FROM_EMAIL") or user,
        "use_tls": _secret("SMTP_USE_TLS") not in ("0", "false", "False"),
    }


def smtp_ready() -> bool:
    cfg = smtp_settings()
    return smtp_configured(host=cfg["host"], user=cfg["user"], password=cfg["password"])


def _send_mail(
    to_addr: str, subject: str, text_body: str, html_body: str = ""
) -> tuple[bool, str]:
    cfg = smtp_settings()
    if not smtp_configured(host=cfg["host"], user=cfg["user"], password=cfg["password"]):
        return False, "smtp_not_configured"
    return send_email(
        host=cfg["host"],
        port=cfg["port"],
        user=cfg["user"],
        password=cfg["password"],
        mail_from=cfg["mail_from"],
        to_addr=to_addr,
        subject=subject,
        text_body=text_body,
        html_body=html_body,
        use_tls=cfg["use_tls"],
    )


def app_base_url() -> str:
    configured = (_secret("SBD_APP_URL") or _secret("APP_BASE_URL")).rstrip("/")
    if configured and "techlife-app.streamlit.app" not in configured:
        return configured
    return DEFAULT_PUBLIC_URL


def _qp(name: str) -> str:
    raw = st.query_params.get(name)
    if isinstance(raw, list):
        return str(raw[0] if raw else "")
    return str(raw or "")


def issue_review_token(request_id: str, email: str, action: str) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {
            "typ": "sbd_review",
            "act": action,
            "rid": request_id,
            "email": sbd_db.normalize_email(email),
            "exp": now + timedelta(days=14),
            "iat": now,
        },
        jwt_secret(),
        algorithm="HS256",
    )


def review_link(request_id: str, email: str, action: str) -> str:
    base = app_base_url()
    token = issue_review_token(request_id, email, action)
    if not base:
        return ""
    return f"{base}/?sbd_{action}={quote(token, safe='')}"


def notify_admins_of_request(email: str, message: str, request_id: str) -> tuple[bool, str]:
    admins = sbd_db.get_admin_emails()
    if not admins:
        return False, "no_admin_email"
    if not smtp_ready():
        return False, "smtp_not_configured"
    approve_url = review_link(request_id, email, "approve")
    reject_url = review_link(request_id, email, "reject")
    subject = "Innovation Assessment：请点击 Approve 开通 / click Approve"
    if approve_url:
        link_text = (
            f"Approve: {approve_url}\n"
            f"Reject: {reject_url}\n"
        )
        html_body = (
            "<p>A user applied for Innovation Assessment access.<br>"
            "有用户申请开通 Innovation Assessment。</p>"
            f"<p>Email: {email}<br>Note: {message or '-'}</p>"
            f'<p><a href="{approve_url}" style="display:inline-block;padding:10px 18px;'
            'background:#1f6feb;color:#fff;text-decoration:none;border-radius:6px;">Approve</a></p>'
            f'<p><a href="{reject_url}">Reject</a></p>'
        )
    else:
        link_text = (
            "Please open the app, click ⚙️, and approve the request.\n"
            "请打开应用，点击右上角齿轮审核。\n"
        )
        html_body = ""
    body = (
        "A user applied for Innovation Assessment access.\n"
        "有用户申请开通 Innovation Assessment。\n\n"
        f"Email: {email}\n"
        f"Note: {message or '-'}\n\n"
        f"{link_text}"
        "Clicking Approve will email the user their login password.\n"
        "点击 Approve 后，系统会自动给用户发送登录密码。"
    )
    errors = []
    sent = 0
    for to_addr in admins:
        ok, err = _send_mail(to_addr, subject, body, html_body)
        if ok:
            sent += 1
        else:
            errors.append(f"{to_addr}: {err}")
    if sent:
        return True, ""
    return False, "; ".join(errors) or "send_failed"


def notify_user_approved(email: str) -> tuple[bool, str]:
    if not smtp_ready():
        return False, "smtp_not_configured"
    password = sbd_db.DEFAULT_PASSWORD
    login_url = app_base_url()
    subject = "Innovation Assessment 账号已开通 / access approved"
    extra = f"\nSign in: {login_url}\n登录地址: {login_url}\n" if login_url else ""
    body = (
        "Your Innovation Assessment account is approved.\n"
        "您的 Innovation Assessment 账号已开通。\n\n"
        f"Email / 登录邮箱: {email}\n"
        f"Password / 登录密码: {password}\n"
        f"{extra}\n"
        "Please sign in and change your password.\n"
        "请登录后立即修改密码。"
    )
    return _send_mail(email, subject, body)


def consume_review_link() -> bool:
    token = _qp("sbd_approve") or _qp("sbd_reject")
    if not token:
        return False
    action = "approve" if _qp("sbd_approve") else "reject"
    labels = t()
    render_top_brand()
    render_top_buttons(show_gear=True)
    try:
        payload = jwt.decode(token, jwt_secret(), algorithms=["HS256"])
    except jwt.PyJWTError:
        st.error(labels["link_invalid"])
        return True
    if payload.get("typ") != "sbd_review" or payload.get("act") != action:
        st.error(labels["link_invalid"])
        return True
    email = sbd_db.normalize_email(str(payload.get("email") or ""))
    request_id = str(payload.get("rid") or "")
    req = sbd_db.get_request(request_id) if request_id else None
    if not email:
        st.error(labels["link_invalid"])
        return True
    if action == "reject":
        if request_id:
            sbd_db.set_request_status(request_id, "rejected")
        st.success(labels["rejected_ok"] + f" ({email})")
        return True
    existing = sbd_db.get_user(email)
    if existing and existing.get("status") == "approved":
        if request_id:
            sbd_db.set_request_status(request_id, "approved")
        st.info(labels["already_approved"] + f" ({email})")
        return True
    sbd_db.upsert_user(email, status="approved", password=sbd_db.DEFAULT_PASSWORD)
    if request_id:
        sbd_db.set_request_status(request_id, "approved")
    elif req:
        sbd_db.set_request_status(str(req.get("id")), "approved")
    ok, err = notify_user_approved(email)
    if ok:
        st.success(labels["approved_mail_ok"] + f" ({email})")
    else:
        st.error(labels["approved_mail_fail"] + str(err))
    return True


def render_top_brand() -> None:
    apply_branding()
    logo_url = st.session_state.get("organization_logo_url") or None
    st.markdown(
        enterprise_brand_markup(sbd_db.ORG_NAME, logo_url, variant="main"),
        unsafe_allow_html=True,
    )


def render_top_buttons(*, show_gear: bool) -> None:
    labels = t()
    col1, col2, col3, col4, col5 = st.columns([8, 1.2, 1.2, 1.2, 1])
    with col2:
        if st.button(labels["chinese"], key="zh_btn", use_container_width=True, type="primary"):
            if st.session_state.lang != "zh":
                set_app_language("zh")
                st.rerun()
    with col3:
        if st.button(labels["english"], key="en_btn", use_container_width=True, type="primary"):
            if st.session_state.lang != "en":
                set_app_language("en")
                st.rerun()
    with col4:
        if show_gear and st.button("⚙️", key="gear_btn", help="Admin Login", use_container_width=True):
            st.session_state.show_admin_login = True
            st.rerun()


def render_admin_login() -> None:
    labels = t()
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown(f"<h2 style='text-align:center;'>{labels['admin_title']}</h2>", unsafe_allow_html=True)
        with st.form("sbd_admin_login_form", border=True):
            username = st.text_input(labels["admin_user"])
            password = st.text_input(labels["admin_pw"], type="password")
            submitted = st.form_submit_button(labels["admin_btn"], type="primary", use_container_width=True)
            if submitted:
                if username.strip() == admin_username() and password == admin_password():
                    st.session_state.sbd_admin = True
                    st.session_state.show_admin_login = False
                    st.rerun()
                st.error(labels["admin_error"])
        if st.button(labels["admin_back"], use_container_width=True):
            st.session_state.show_admin_login = False
            st.rerun()


def apply_branding() -> None:
    st.session_state.organization_id = "sbd"
    st.session_state.organization_name = sbd_db.ORG_NAME
    st.session_state.organization_name_zh = sbd_db.ORG_NAME
    st.session_state.organization_name_en = sbd_db.ORG_NAME
    st.session_state.organization_logo_url = sbd_db.get_logo_url()
    st.session_state._enterprise_branding_loaded = True


def _handle_logo_upload_result(ok: bool, reason: str) -> None:
    labels = t()
    if ok:
        apply_branding()
        st.success(labels["logo_saved"])
        st.rerun()
    elif reason == "too_large":
        st.error(labels["logo_too_large"])
    elif reason == "invalid_type":
        st.error(labels["logo_invalid_type"])
    elif reason == "missing_column":
        st.error(labels["logo_migration_hint"])
    elif reason == "empty_file":
        st.warning(labels["upload_logo"])
    else:
        st.error(reason or labels["logo_invalid_type"])


def render_logo_section() -> None:
    labels = t()
    logo_url = sbd_db.get_logo_url()
    st.markdown(f"### {labels['org_logo']}")
    if logo_url:
        st.image(logo_url, width=140)
    uploaded = st.file_uploader(
        labels["upload_logo"],
        type=["png", "jpg", "jpeg", "webp"],
        key="sbd_admin_logo_uploader",
    )
    col_save, col_remove = st.columns(2)
    with col_save:
        if st.button(labels["save_logo"], key="sbd_admin_save_logo", use_container_width=True, type="primary"):
            if not uploaded:
                st.warning(labels["upload_logo"])
            else:
                ok, reason = sbd_db.set_logo(uploaded.getvalue(), uploaded.type or "")
                _handle_logo_upload_result(ok, reason)
    with col_remove:
        if logo_url and st.button(labels["remove_logo"], key="sbd_admin_remove_logo", use_container_width=True):
            ok, reason = sbd_db.clear_logo()
            if ok:
                apply_branding()
                st.success(labels["logo_removed"])
                st.rerun()
            elif reason == "missing_column":
                st.error(labels["logo_migration_hint"])
            else:
                st.error(reason or labels["logo_invalid_type"])


def render_admin_panel() -> None:
    labels = t()
    flash = st.session_state.pop("sbd_flash", None)
    if flash:
        kind, msg = flash
        if kind == "ok":
            st.success(msg)
        else:
            st.error(msg)
    st.markdown(f"## {labels['admin_panel']}")
    if st.button(labels["logout"]):
        st.session_state.sbd_admin = False
        st.rerun()
    if not smtp_ready():
        st.warning(labels["smtp_missing"])
    render_logo_section()

    st.markdown(f"### {labels['admin_emails']}")
    current = ",".join(sbd_db.get_admin_emails())
    emails_raw = st.text_area(labels["admin_emails"], value=current, key="sbd_admin_emails", label_visibility="collapsed")
    if st.button(labels["save"], key="save_admin_emails"):
        sbd_db.set_admin_emails(emails_raw)
        st.success("OK")
        st.rerun()

    st.markdown(f"### {labels['requests']}")
    for req in sbd_db.list_pending_requests():
        c1, c2, c3 = st.columns([4, 1, 1])
        with c1:
            st.write(req.get("email"), req.get("created_at"), req.get("message") or "")
        with c2:
            if st.button(labels["approve"], key=f"appr_{req.get('id')}"):
                email = req.get("email") or ""
                sbd_db.upsert_user(email, status="approved", password=sbd_db.DEFAULT_PASSWORD)
                sbd_db.set_request_status(req["id"], "approved")
                ok, err = notify_user_approved(email)
                st.session_state.sbd_flash = (
                    ("ok", labels["mail_user_ok"])
                    if ok
                    else ("err", labels["mail_user_fail"] + str(err))
                )
                st.rerun()
        with c3:
            if st.button(labels["reject"], key=f"rej_{req.get('id')}"):
                sbd_db.set_request_status(req["id"], "rejected")
                st.rerun()

    st.markdown(f"### {labels['add_user']}")
    with st.form("add_user_form"):
        new_email = st.text_input(labels["email"])
        submitted = st.form_submit_button(labels["add_user"])
        if submitted and new_email:
            sbd_db.upsert_user(new_email, status="approved", password=sbd_db.DEFAULT_PASSWORD)
            ok, err = notify_user_approved(sbd_db.normalize_email(new_email))
            st.session_state.sbd_flash = (
                ("ok", f"{new_email} — {labels['mail_user_ok']}")
                if ok
                else ("err", f"{new_email} — {labels['mail_user_fail']}{err}")
            )
            st.rerun()

    st.markdown(f"### {labels['users']}")
    users = sbd_db.list_users()
    if not users:
        st.caption(labels["none"])
    else:
        login_map = sbd_db.last_logins_map(5)
        rows = []
        for user in users:
            email = user.get("email") or ""
            logins = (login_map.get(sbd_db.normalize_email(email)) or []) + [""] * 5
            rows.append(
                {
                    labels["col_email"]: email,
                    labels["col_created"]: sbd_db.format_ts(user.get("created_at")),
                    f"{labels['col_login']} 1": logins[0],
                    f"{labels['col_login']} 2": logins[1],
                    f"{labels['col_login']} 3": logins[2],
                    f"{labels['col_login']} 4": logins[3],
                    f"{labels['col_login']} 5": logins[4],
                }
            )
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        del_email = st.selectbox(
            labels["delete"],
            options=[""] + [u.get("email") or "" for u in users],
            key="sbd_delete_user",
        )
        if del_email and st.button(labels["delete"], key="sbd_delete_user_btn"):
            sbd_db.delete_user(del_email)
            st.rerun()


def render_user_gate() -> None:
    labels = t()
    col1, col2, col3 = st.columns([1, 3, 1])
    with col2:
        st.markdown(f"<h1 style='text-align:center;'>{labels['title']}</h1>", unsafe_allow_html=True)
        st.markdown(f"<p style='text-align:center;color:gray;'>{labels['subtitle']}</p>", unsafe_allow_html=True)
        with st.form("sbd_login_form", border=True):
            email = st.text_input(labels["email"], key="login_email")
            password = st.text_input(labels["password"], type="password", key="login_password")
            submitted = st.form_submit_button(labels["login"], type="primary", use_container_width=True)
            if submitted:
                email_n = sbd_db.normalize_email(email)
                user = sbd_db.get_user(email_n)
                if not user:
                    st.error(labels["login_fail"])
                elif user.get("status") == "pending":
                    st.warning(labels["pending"])
                elif user.get("status") != "approved":
                    st.error(labels["disabled"])
                elif not sbd_db.verify_password(password, user.get("password_hash") or ""):
                    st.error(labels["login_fail"])
                else:
                    _enter_user(email_n, record=True, persist=True)
                    st.rerun()

        st.caption(labels["apply_hint"])
        with st.form("sbd_apply_form", border=True):
            apply_email = st.text_input(labels["email"], key="apply_email")
            apply_msg = st.text_area(labels["apply_msg"], key="apply_msg")
            applied = st.form_submit_button(labels["apply"], use_container_width=True)
            if applied:
                email_n = sbd_db.normalize_email(apply_email)
                if "@" not in email_n:
                    st.error(labels["email"])
                else:
                    existing = sbd_db.get_user(email_n)
                    if existing and existing.get("status") == "approved":
                        st.info(labels["login"] if st.session_state.lang == "en" else "该邮箱已开通，请直接登录。")
                    else:
                        if not existing:
                            sbd_db.upsert_user(email_n, status="pending")
                        request_id = sbd_db.create_access_request(email_n, apply_msg)
                        ok, err = notify_admins_of_request(email_n, apply_msg, request_id)
                        st.success(labels["apply_ok"])
                        if ok:
                            st.info(labels["mail_admin_ok"])
                        elif err == "no_admin_email":
                            st.warning(labels["mail_no_admin"])
                        else:
                            st.warning(labels["mail_admin_fail"] + str(err))


def _handle_assessment_side_effects() -> None:
    if st.session_state.get("_sbd_logout"):
        _logout_user()
        st.rerun()
    change = st.session_state.pop("_sbd_change_pw", None)
    if change:
        pw, pw2 = change
        lang = st.session_state.get("lang", "zh")
        if not pw or pw != pw2 or len(pw) < 6:
            st.sidebar.error("两次密码不一致或过短" if lang == "zh" else "Passwords do not match or are too short.")
        else:
            sbd_db.set_password(st.session_state.sbd_user_email, pw)
            _persist_token(_issue_token(st.session_state.sbd_user_email))
            st.sidebar.success("密码已更新" if lang == "zh" else "Password updated.")


def main() -> None:
    _init_state()
    _remember_bridge()
    _restore_session()
    st.session_state.sbd_shell = True
    set_app_language(st.session_state.lang)
    if consume_review_link():
        return

    if st.session_state.sbd_admin:
        render_top_brand()
        render_top_buttons(show_gear=False)
        render_admin_panel()
        return

    if st.session_state.show_admin_login:
        render_top_brand()
        render_top_buttons(show_gear=False)
        render_admin_login()
        return

    if not st.session_state.sbd_authenticated:
        render_top_brand()
        render_top_buttons(show_gear=True)
        render_user_gate()
        return

    _handle_assessment_side_effects()
    apply_branding()
    render_top_buttons(show_gear=True)
    render_innovation_app(embedded=False)


main()
