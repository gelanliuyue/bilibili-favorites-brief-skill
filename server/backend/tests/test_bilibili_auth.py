import importlib.util
import sys
import tempfile
import types
import unittest
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from requests.cookies import RequestsCookieJar

APP_ROOT = Path(__file__).resolve().parents[1] / "app"


def load_services():
    app_package = types.ModuleType("app")
    app_package.__path__ = [str(APP_ROOT)]
    services_package = types.ModuleType("app.services")
    services_package.__path__ = [str(APP_ROOT / "services")]
    sys.modules["app"] = app_package
    sys.modules["app.services"] = services_package

    for name in ("secure_store", "cookie_manager", "bilibili_auth"):
        module_name = f"app.services.{name}"
        spec = importlib.util.spec_from_file_location(
            module_name,
            APP_ROOT / "services" / f"{name}.py",
        )
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)

    return (
        sys.modules["app.services.secure_store"],
        sys.modules["app.services.cookie_manager"],
        sys.modules["app.services.bilibili_auth"],
    )


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code
        self.url = payload.get("_url", "")

    def json(self):
        return {key: value for key, value in self._payload.items() if key != "_url"}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class FakeSession:
    def __init__(self, responder):
        self.responder = responder
        self.cookies = RequestsCookieJar()
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self.responder(url, kwargs, self)


class BilibiliAuthTests(unittest.TestCase):
    def setUp(self):
        self.secure_store_module, self.cookie_manager_module, self.auth_module = (
            load_services()
        )
        self.auth_module.clear_qr_sessions()
        self.temp = tempfile.TemporaryDirectory()
        store = self.secure_store_module.SecureStore(
            Path(self.temp.name) / "downloader.json",
            backend="aesgcm",
            secret="test-secret",
        )
        self.cookie_manager = self.cookie_manager_module.CookieConfigManager(
            filepath=str(Path(self.temp.name) / "downloader.json"),
            secure_store=store,
        )

    def tearDown(self):
        self.auth_module.clear_qr_sessions()
        self.temp.cleanup()

    def make_session(self, poll_payloads):
        queue = list(poll_payloads)

        def responder(url, _kwargs, session):
            if "qrcode/generate" in url:
                return FakeResponse(
                    {
                        "code": 0,
                        "data": {
                            "url": "https://www.bilibili.com/login-qr",
                            "qrcode_key": "secret-qr-key",
                        },
                    }
                )
            if "qrcode/poll" in url:
                return FakeResponse({"code": 0, "data": queue.pop(0)})
            if "passport.bilibili.com/login-confirm" in url:
                session.cookies.set("buvid3", "browser-cookie")
                session.cookies.set("unrelated", "other-domain", domain=".example.com")
                return FakeResponse({"code": 0, "_url": url})
            if "web-interface/nav" in url:
                return FakeResponse(
                    {
                        "code": 0,
                        "data": {
                            "isLogin": True,
                            "uname": "测试用户",
                            "face": "https://example.com/avatar.jpg",
                        },
                    }
                )
            raise AssertionError(f"unexpected URL: {url}")

        return FakeSession(responder)

    def test_start_returns_qr_data_without_exposing_qrcode_key(self):
        session = self.make_session([])

        result = self.auth_module.start_qr_login(session=session, now=100)

        self.assertEqual(result.qr_url, "https://www.bilibili.com/login-qr")
        self.assertEqual(result.expires_in, 180)
        self.assertNotIn("secret-qr-key", repr(result))

    def test_poll_maps_waiting_scanned_and_expired_states(self):
        session = self.make_session(
            [
                {"code": 86101, "message": "waiting"},
                {"code": 86090, "message": "scanned"},
                {"code": 86038, "message": "expired"},
            ]
        )
        started = self.auth_module.start_qr_login(session=session, now=100)

        waiting = self.auth_module.poll_qr_login(
            started.session_id,
            cookie_manager=self.cookie_manager,
            now=101,
        )
        scanned = self.auth_module.poll_qr_login(
            started.session_id,
            cookie_manager=self.cookie_manager,
            now=102,
        )
        expired = self.auth_module.poll_qr_login(
            started.session_id,
            cookie_manager=self.cookie_manager,
            now=103,
        )

        self.assertEqual(waiting.status, "waiting")
        self.assertEqual(scanned.status, "scanned")
        self.assertEqual(expired.status, "expired")

    def test_success_extracts_cookie_and_validates_account(self):
        redirect_url = (
            "https://passport.bilibili.com/login-confirm"
            "?SESSDATA=test-sess&bili_jct=test-jct"
            "&DedeUserID=123&DedeUserID__ckMd5=checksum"
        )
        session = self.make_session(
            [
                {
                    "code": 0,
                    "url": redirect_url,
                }
            ]
        )
        started = self.auth_module.start_qr_login(session=session, now=100)

        result = self.auth_module.poll_qr_login(
            started.session_id,
            cookie_manager=self.cookie_manager,
            now=101,
        )

        self.assertEqual(result.status, "success")
        self.assertEqual(result.account.uname, "测试用户")
        cookie = self.cookie_manager.get("bilibili")
        self.assertIn("SESSDATA=test-sess", cookie)
        self.assertIn("bili_jct=test-jct", cookie)
        self.assertIn("DedeUserID=123", cookie)
        self.assertNotIn("unrelated", cookie)
        nav_calls = [call for call in session.calls if "nav" in call[0]]
        self.assertEqual(len(nav_calls), 1)
        nav_cookie = nav_calls[0][1]["headers"]["Cookie"]
        self.assertIn("SESSDATA=test-sess", nav_cookie)

    def test_get_login_status_returns_account_without_cookie(self):
        self.cookie_manager.set("bilibili", "SESSDATA=test-sess; bili_jct=test-jct")
        session = self.make_session([])

        status = self.auth_module.get_login_status(
            cookie=self.cookie_manager.get("bilibili"),
            session=session,
        )

        self.assertTrue(status.logged_in)
        self.assertEqual(status.uname, "测试用户")
        self.assertNotIn("Cookie", status.__dict__)

    def test_expired_local_session_is_removed(self):
        session = self.make_session([])
        started = self.auth_module.start_qr_login(session=session, now=100)

        result = self.auth_module.poll_qr_login(
            started.session_id,
            cookie_manager=self.cookie_manager,
            now=281,
        )

        self.assertEqual(result.status, "expired")
        with self.assertRaises(KeyError):
            self.auth_module.poll_qr_login(
                started.session_id,
                cookie_manager=self.cookie_manager,
                now=282,
            )


if __name__ == "__main__":
    unittest.main()
