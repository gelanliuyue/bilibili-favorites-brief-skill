from __future__ import annotations

import secrets
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable
from urllib.parse import parse_qs, urlparse

import requests

from app.services.cookie_manager import CookieConfigManager

QR_GENERATE_API = (
    "https://passport.bilibili.com/x/passport-login/web/qrcode/generate"
)
QR_POLL_API = "https://passport.bilibili.com/x/passport-login/web/qrcode/poll"
NAV_API = "https://api.bilibili.com/x/web-interface/nav"
QR_TTL_SECONDS = 180

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)


@dataclass(frozen=True)
class QrStart:
    session_id: str
    qr_url: str
    expires_in: int


@dataclass(frozen=True)
class BiliAccount:
    logged_in: bool
    uname: str = ""
    face: str = ""


@dataclass(frozen=True)
class QrPoll:
    status: str
    message: str
    account: BiliAccount | None = None


@dataclass
class _QrSession:
    qrcode_key: str
    session: requests.Session
    expires_at: float
    lock: threading.Lock


_QR_SESSIONS: dict[str, _QrSession] = {}
_COOKIE_MANAGER = CookieConfigManager()


def clear_qr_sessions() -> None:
    _QR_SESSIONS.clear()


def _session_headers(cookie: str | None = None) -> dict[str, str]:
    headers = {
        "User-Agent": USER_AGENT,
        "Referer": "https://www.bilibili.com/",
    }
    if cookie:
        headers["Cookie"] = cookie
    return headers


def _new_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(_session_headers())
    return session


def _json(response: Any) -> dict[str, Any]:
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict):
        raise ValueError("Bilibili returned a non-object JSON response")
    return payload


def start_qr_login(
    *,
    session: requests.Session | None = None,
    now: float | None = None,
) -> QrStart:
    client = session or _new_session()
    payload = _json(
        client.get(
            QR_GENERATE_API,
            params={"source": "main-fe-header"},
            timeout=10,
        )
    )
    if payload.get("code") != 0:
        raise ValueError("Failed to generate Bilibili login QR code")
    data = payload.get("data")
    if not isinstance(data, dict):
        raise ValueError("Bilibili QR response is missing data")
    qr_url = data.get("url")
    qrcode_key = data.get("qrcode_key")
    if not isinstance(qr_url, str) or not isinstance(qrcode_key, str):
        raise ValueError("Bilibili QR response is missing url or qrcode_key")

    session_id = secrets.token_urlsafe(24)
    current_time = time.time() if now is None else now
    _QR_SESSIONS[session_id] = _QrSession(
        qrcode_key=qrcode_key,
        session=client,
        expires_at=current_time + QR_TTL_SECONDS,
        lock=threading.Lock(),
    )
    return QrStart(
        session_id=session_id,
        qr_url=qr_url,
        expires_in=QR_TTL_SECONDS,
    )


def poll_qr_login(
    session_id: str,
    *,
    cookie_manager: CookieConfigManager | None = None,
    now: float | None = None,
    session_factory: Callable[[], requests.Session] | None = None,
) -> QrPoll:
    del session_factory  # Reserved for tests and job runners; the client is stateful.
    qr_session = _QR_SESSIONS[session_id]
    current_time = time.time() if now is None else now
    if current_time >= qr_session.expires_at:
        _QR_SESSIONS.pop(session_id, None)
        return QrPoll(status="expired", message="二维码已过期，请重新生成")

    with qr_session.lock:
        payload = _json(
            qr_session.session.get(
                QR_POLL_API,
                params={
                    "qrcode_key": qr_session.qrcode_key,
                    "source": "main-fe-header",
                },
                timeout=10,
            )
        )
        if payload.get("code") != 0:
            _QR_SESSIONS.pop(session_id, None)
            return QrPoll(status="error", message="查询二维码状态失败")
        data = payload.get("data")
        if not isinstance(data, dict):
            _QR_SESSIONS.pop(session_id, None)
            return QrPoll(status="error", message="二维码状态响应异常")

        status_code = data.get("code")
        if status_code == 86101:
            return QrPoll(status="waiting", message="二维码待扫描")
        if status_code == 86090:
            return QrPoll(status="scanned", message="已扫码，请在手机中确认")
        if status_code == 86038:
            _QR_SESSIONS.pop(session_id, None)
            return QrPoll(status="expired", message="二维码已过期，请重新生成")
        if status_code != 0:
            _QR_SESSIONS.pop(session_id, None)
            return QrPoll(status="error", message="B 站返回了未知登录状态")

        redirect_url = data.get("url")
        if not isinstance(redirect_url, str):
            _QR_SESSIONS.pop(session_id, None)
            return QrPoll(status="error", message="登录成功但缺少确认地址")

        try:
            qr_session.session.get(redirect_url, timeout=10)
        except requests.RequestException:
            pass

        cookie_header = _extract_cookie_header(qr_session.session, redirect_url)
        if not cookie_header:
            _QR_SESSIONS.pop(session_id, None)
            return QrPoll(status="error", message="登录成功但未取得有效 Cookie")

        manager = cookie_manager or _COOKIE_MANAGER
        manager.set("bilibili", cookie_header)
        account = get_login_status(
            cookie=cookie_header,
            session=qr_session.session,
        )
        _QR_SESSIONS.pop(session_id, None)
        if not account.logged_in:
            return QrPoll(
                status="error",
                message="Cookie 已保存，但账号登录校验失败",
            )
        return QrPoll(
            status="success",
            message="登录成功",
            account=account,
        )


def _extract_cookie_header(
    session: requests.Session,
    redirect_url: str,
) -> str:
    cookies: dict[str, str] = {}
    for cookie in session.cookies:
        domain = str(getattr(cookie, "domain", "")).lower()
        if (
            domain.endswith("bilibili.com")
            and cookie.name
            and cookie.value is not None
        ):
            cookies[cookie.name] = cookie.value

    query = parse_qs(urlparse(redirect_url).query)
    for name in (
        "SESSDATA",
        "bili_jct",
        "DedeUserID",
        "DedeUserID__ckMd5",
        "sid",
    ):
        values = query.get(name)
        if values:
            cookies[name] = values[0]

    if not cookies.get("SESSDATA"):
        return ""
    return "; ".join(f"{name}={value}" for name, value in cookies.items())


def get_login_status(
    *,
    cookie: str | None = None,
    session: requests.Session | None = None,
) -> BiliAccount:
    effective_cookie = cookie or _COOKIE_MANAGER.get("bilibili")
    if not effective_cookie:
        return BiliAccount(logged_in=False)

    client = session or _new_session()
    payload = _json(
        client.get(
            NAV_API,
            headers=_session_headers(effective_cookie),
            timeout=10,
        )
    )
    data = payload.get("data")
    if not isinstance(data, dict) or not data.get("isLogin"):
        return BiliAccount(logged_in=False)
    return BiliAccount(
        logged_in=True,
        uname=str(data.get("uname") or ""),
        face=str(data.get("face") or ""),
    )


def logout_bilibili(*, cookie_manager: CookieConfigManager | None = None) -> None:
    (cookie_manager or _COOKIE_MANAGER).delete("bilibili")
