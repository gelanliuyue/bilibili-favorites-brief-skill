from dataclasses import asdict
from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

from app.services import bilibili_auth
from app.services.browser_cookie_import import import_bilibili_cookies
from app.utils.response import ResponseWrapper as R

router = APIRouter(prefix="/bilibili_auth", tags=["Bilibili authentication"])


class BrowserImportRequest(BaseModel):
    browser: Literal["edge", "chrome"]


@router.post("/qr/start")
def qr_start():
    try:
        result = bilibili_auth.start_qr_login()
        return R.success(data=asdict(result))
    except Exception as exc:
        return R.error(msg=f"生成二维码失败：{exc}")


@router.get("/qr/poll/{session_id}")
def qr_poll(session_id: str):
    try:
        result = bilibili_auth.poll_qr_login(session_id)
        payload = {
            "status": result.status,
            "message": result.message,
        }
        if result.account:
            payload["account"] = asdict(result.account)
        return R.success(data=payload)
    except KeyError:
        return R.error(msg="二维码会话不存在或已过期", code=404)
    except Exception as exc:
        return R.error(msg=f"查询登录状态失败：{exc}")


@router.get("/status")
def login_status():
    try:
        return R.success(data=asdict(bilibili_auth.get_login_status()))
    except Exception as exc:
        return R.error(msg=f"读取登录状态失败：{exc}")


@router.post("/import_browser")
def browser_import(data: BrowserImportRequest):
    try:
        import_bilibili_cookies(data.browser)
        account = bilibili_auth.get_login_status()
        return R.success(
            msg="已从浏览器导入 B 站登录状态",
            data=asdict(account),
        )
    except ValueError as exc:
        return R.error(msg=str(exc), code=400)
    except Exception as exc:
        return R.error(msg=f"浏览器 Cookie 导入失败：{exc}")


@router.post("/logout")
def logout():
    try:
        bilibili_auth.logout_bilibili()
        return R.success(msg="已退出 B 站登录")
    except Exception as exc:
        return R.error(msg=f"退出登录失败：{exc}")
