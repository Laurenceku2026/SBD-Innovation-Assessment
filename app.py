"""Stanley Black & Decker Innovation Assessment — independent Streamlit app."""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import jwt
import streamlit as st
import streamlit.components.v1 as components

from assessment import render_innovation_app, set_app_language
from email_smtp import send_email, smtp_configured
from portal_enterprise_ui import ensure_enterprise_session_defaults
import sbd_db

st.set_page_config(page_title="SBD Innovation Assessment", page_icon="🔹", layout="wide")

REMEMBER_DAYS = 30
TOKEN_QUERY = "sbd"


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
            "title": "Stanley Black & Decker 创新评估",
            "subtitle": "请使用已开通的邮箱登录。新用户请先申请开通。",
            "email": "邮箱",
            "password": "密码",
            "login": "登录",
            "apply": "申请开通",
            "apply_hint": "提交后由管理员审核。开通后初始密码为 1234567，登录后请自行修改。",
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
            "none": "无",
        }
    return {
        "title": "Stanley Black & Decker Innovation Assessment",
        "subtitle": "Sign in with an approved email. New users should apply first.",
        "email": "Email",
        "password": "Password",
        "login": "Sign in",
        "apply": "Apply for access",
        "apply_hint": "An admin will review your request. Initial password is 1234567; change it after you sign in.",
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
        "none": "None",
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
    st.session_state.organization_id = "sbd"
    st.session_state.organization_name = "Stanley Black & Decker"
    st.session_state.organization_name_zh = "Stanley Black & Decker"
    st.session_state.organization_name_en = "Stanley Black & Decker"
    st.session_state.show_admin_login = False
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
    return {
        "host": _secret("SMTP_HOST") or _secret("SMTP_SERVER"),
        "port": int(_secret("SMTP_PORT") or "587"),
        "user": _secret("SMTP_USER") or _secret("SMTP_USERNAME"),
        "password": _secret("SMTP_PASSWORD"),
        "mail_from": _secret("SMTP_FROM_EMAIL") or _secret("SMTP_USER"),
    }


def notify_admins_of_request(email: str, message: str) -> None:
    cfg = smtp_settings()
    if not smtp_configured(host=cfg["host"], user=cfg["user"], password=cfg["password"]):
        return
    admins = sbd_db.get_admin_emails()
    lang = st.session_state.get("lang", "zh")
    subject = (
        "SBD 创新评估：新的开通申请"
        if lang == "zh"
        else "SBD Innovation Assessment: new access request"
    )
    body = f"Email: {email}\n\n{message or ''}"
    for to_addr in admins:
        send_email(
            host=cfg["host"],
            port=cfg["port"],
            user=cfg["user"],
            password=cfg["password"],
            mail_from=cfg["mail_from"],
            to_addr=to_addr,
            subject=subject,
            text_body=body,
        )


def notify_user_approved(email: str) -> None:
    cfg = smtp_settings()
    if not smtp_configured(host=cfg["host"], user=cfg["user"], password=cfg["password"]):
        return
    lang = st.session_state.get("lang", "zh")
    if lang == "zh":
        subject = "SBD 创新评估账号已开通"
        body = "您的账号已开通。请用申请邮箱登录，初始密码为 1234567，登录后请立即修改密码。"
    else:
        subject = "SBD Innovation Assessment access approved"
        body = "Your account is approved. Sign in with this email. Initial password is 1234567; please change it after login."
    send_email(
        host=cfg["host"],
        port=cfg["port"],
        user=cfg["user"],
        password=cfg["password"],
        mail_from=cfg["mail_from"],
        to_addr=email,
        subject=subject,
        text_body=body,
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


def render_admin_panel() -> None:
    labels = t()
    st.markdown(f"## {labels['admin_panel']}")
    if st.button(labels["logout"]):
        st.session_state.sbd_admin = False
        st.rerun()

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
                sbd_db.upsert_user(email, status="approved")
                sbd_db.set_request_status(req["id"], "approved")
                notify_user_approved(email)
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
            sbd_db.upsert_user(new_email, status="approved")
            st.success(new_email)
            st.rerun()

    st.markdown(f"### {labels['users']}")
    users = sbd_db.list_users()
    if not users:
        st.caption(labels["none"])
    for user in users:
        email = user.get("email") or ""
        logins = sbd_db.last_logins(email, 5)
        c1, c2 = st.columns([6, 1])
        with c1:
            st.markdown(f"**{email}** · {user.get('status')}")
            st.caption(f"{labels['last5']}: {', '.join(logins) if logins else labels['none']}")
        with c2:
            if st.button(labels["delete"], key=f"del_{email}"):
                sbd_db.delete_user(email)
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
                        sbd_db.create_access_request(email_n, apply_msg)
                        notify_admins_of_request(email_n, apply_msg)
                        st.success(labels["apply_ok"])


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

    if st.session_state.sbd_admin:
        render_top_buttons(show_gear=False)
        render_admin_panel()
        return

    if st.session_state.show_admin_login:
        render_top_buttons(show_gear=False)
        render_admin_login()
        return

    if not st.session_state.sbd_authenticated:
        render_top_buttons(show_gear=True)
        render_user_gate()
        return

    _handle_assessment_side_effects()
    render_top_buttons(show_gear=True)
    render_innovation_app(embedded=False)


main()
