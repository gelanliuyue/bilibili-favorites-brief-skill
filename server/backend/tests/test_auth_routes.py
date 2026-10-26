import importlib.util
import sys
import types
import unittest
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

APP_ROOT = Path(__file__).resolve().parents[1] / "app"


def load_module(module_name: str, path: Path):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def load_environment():
    packages = {
        "app": APP_ROOT,
        "app.services": APP_ROOT / "services",
        "app.routers": APP_ROOT / "routers",
        "app.utils": APP_ROOT / "utils",
    }
    for name, path in packages.items():
        package = types.ModuleType(name)
        package.__path__ = [str(path)]
        sys.modules[name] = package

    load_module("app.utils.status_code", APP_ROOT / "utils" / "status_code.py")
    load_module("app.utils.response", APP_ROOT / "utils" / "response.py")

    for name in (
        "secure_store",
        "cookie_manager",
        "bilibili_auth",
        "browser_cookie_import",
        "transcriber_config_manager",
    ):
        load_module(
            f"app.services.{name}",
            APP_ROOT / "services" / f"{name}.py",
        )

    auth_router = load_module(
        "app.routers.bilibili_auth",
        APP_ROOT / "routers" / "bilibili_auth.py",
    )
    asr_router = load_module(
        "app.routers.brief_asr",
        APP_ROOT / "routers" / "brief_asr.py",
    )
    return auth_router, asr_router


class AuthRouteTests(unittest.TestCase):
    def setUp(self):
        self.auth_router, self.asr_router = load_environment()
        app = FastAPI()
        app.include_router(self.auth_router.router, prefix="/api")
        app.include_router(self.asr_router.router, prefix="/api")
        self.client = TestClient(app)

    def test_qr_start_and_poll_do_not_expose_qrcode_key_or_cookie(self):
        auth_service = self.auth_router.bilibili_auth
        auth_service.start_qr_login = lambda: auth_service.QrStart(
            session_id="session-1",
            qr_url="https://www.bilibili.com/login-qr",
            expires_in=180,
        )
        auth_service.poll_qr_login = lambda _session_id: auth_service.QrPoll(
            status="waiting",
            message="二维码待扫描",
        )

        started_response = self.client.post("/api/bilibili_auth/qr/start")
        polled_response = self.client.get(
            "/api/bilibili_auth/qr/poll/session-1"
        )
        self.assertEqual(started_response.json()["code"], 0, started_response.text)
        self.assertEqual(polled_response.json()["code"], 0, polled_response.text)
        started = started_response.json()
        polled = polled_response.json()

        self.assertEqual(started["data"]["session_id"], "session-1")
        self.assertNotIn("qrcode_key", str(started))
        self.assertEqual(polled["data"]["status"], "waiting")
        self.assertNotIn("cookie", str(polled).lower())

    def test_success_poll_returns_account_without_cookie(self):
        self.auth_router.bilibili_auth.poll_qr_login = (
            lambda _session_id: self.auth_router.bilibili_auth.QrPoll(
            status="success",
            message="登录成功",
            account=self.auth_router.bilibili_auth.BiliAccount(
                logged_in=True,
                uname="测试用户",
                face="https://example.com/avatar.jpg",
            ),
            )
        )

        response = self.client.get("/api/bilibili_auth/qr/poll/session-1")
        self.assertEqual(response.json()["code"], 0, response.text)
        payload = response.json()

        self.assertEqual(payload["data"]["status"], "success")
        self.assertEqual(payload["data"]["account"]["uname"], "测试用户")
        self.assertNotIn("SESSDATA", response.text)

    def test_import_browser_accepts_edge_and_rejects_unknown_browser(self):
        calls = []

        def fake_import(browser):
            calls.append(browser)
            return "SESSDATA=secret; bili_jct=csrf"

        self.auth_router.import_bilibili_cookies = fake_import
        self.auth_router.get_login_status = lambda: self.auth_router.bilibili_auth.BiliAccount(
            logged_in=True,
            uname="浏览器账号",
        )
        self.auth_router.bilibili_auth.get_login_status = (
            self.auth_router.get_login_status
        )

        accepted = self.client.post(
            "/api/bilibili_auth/import_browser",
            json={"browser": "edge"},
        )
        rejected = self.client.post(
            "/api/bilibili_auth/import_browser",
            json={"browser": "firefox"},
        )

        self.assertEqual(calls, ["edge"])
        self.assertEqual(accepted.status_code, 200)
        self.assertNotIn("SESSDATA=secret", accepted.text)
        self.assertEqual(rejected.status_code, 422)

    def test_status_and_logout_never_return_cookie(self):
        self.auth_router.bilibili_auth.get_login_status = (
            lambda: self.auth_router.bilibili_auth.BiliAccount(logged_in=False)
        )
        self.auth_router.bilibili_auth.logout_bilibili = lambda: None

        status = self.client.get("/api/bilibili_auth/status")
        logout = self.client.post("/api/bilibili_auth/logout")

        self.assertEqual(status.status_code, 200)
        self.assertEqual(logout.status_code, 200)
        self.assertNotIn("SESSDATA", status.text + logout.text)


class FakeTranscriberManager:
    current = {"transcriber_type": "subtitle_only", "whisper_model_size": None}

    def get_config(self):
        return dict(self.current)

    def update_config(self, transcriber_type, whisper_model_size=None):
        self.current = {
            "transcriber_type": transcriber_type,
            "whisper_model_size": whisper_model_size,
        }
        return dict(self.current)

    def update_brief_mode(self, mode):
        return self.update_config(mode)


class AsrRouteTests(unittest.TestCase):
    def setUp(self):
        self.auth_router, self.asr_router = load_environment()
        self.asr_router.TranscriberConfigManager = FakeTranscriberManager
        app = FastAPI()
        app.include_router(self.asr_router.router, prefix="/api")
        self.client = TestClient(app)

    def test_get_and_put_asr_settings(self):
        initial = self.client.get("/api/asr/settings").json()
        updated = self.client.put(
            "/api/asr/settings",
            json={"mode": "bcut"},
        ).json()

        self.assertEqual(initial["data"]["mode"], "subtitle_only")
        self.assertEqual(updated["data"]["mode"], "bcut")
        self.assertIn("groq", updated["data"]["available_modes"])

    def test_invalid_asr_mode_is_rejected(self):
        response = self.client.put(
            "/api/asr/settings",
            json={"mode": "local-whisper"},
        )
        self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()
