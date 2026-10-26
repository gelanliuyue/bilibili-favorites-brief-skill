import importlib.util
import sys
import tempfile
import types
import unittest
from pathlib import Path
from requests.cookies import RequestsCookieJar

APP_ROOT = Path(__file__).resolve().parents[1] / "app"


def load_services():
    app_package = types.ModuleType("app")
    app_package.__path__ = [str(APP_ROOT)]
    services_package = types.ModuleType("app.services")
    services_package.__path__ = [str(APP_ROOT / "services")]
    sys.modules["app"] = app_package
    sys.modules["app.services"] = services_package

    for name in ("secure_store", "cookie_manager", "browser_cookie_import"):
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
        sys.modules["app.services.browser_cookie_import"],
    )


class BrowserCookieImportTests(unittest.TestCase):
    def setUp(self):
        self.secure_store_module, self.cookie_manager_module, self.module = load_services()
        self.temp = tempfile.TemporaryDirectory()
        path = Path(self.temp.name) / "downloader.json"
        self.store = self.secure_store_module.SecureStore(
            path,
            backend="aesgcm",
            secret="browser-import-secret",
        )
        self.manager = self.cookie_manager_module.CookieConfigManager(
            filepath=str(path),
            secure_store=self.store,
        )

    def tearDown(self):
        self.temp.cleanup()

    def jar(self):
        jar = RequestsCookieJar()
        jar.set("SESSDATA", "browser-sess", domain=".bilibili.com")
        jar.set("bili_jct", "browser-jct", domain=".bilibili.com")
        jar.set("DedeUserID", "123", domain=".bilibili.com")
        jar.set("unrelated", "nope", domain=".example.com")
        return jar

    def test_imports_edge_and_chrome_cookie_headers(self):
        for browser in ("edge", "chrome"):
            cookie = self.module.import_bilibili_cookies(
                browser,
                extractor=lambda _browser: self.jar(),
                cookie_manager=self.manager,
            )
            self.assertIn("SESSDATA=browser-sess", cookie)
            self.assertIn("bili_jct=browser-jct", cookie)
            self.assertNotIn("unrelated", cookie)
            self.assertEqual(self.manager.get("bilibili"), cookie)

    def test_rejects_unsupported_browser(self):
        with self.assertRaisesRegex(ValueError, "edge.*chrome"):
            self.module.import_bilibili_cookies(
                "firefox",
                extractor=lambda _browser: self.jar(),
            )

    def test_rejects_missing_sessdata(self):
        jar = RequestsCookieJar()
        jar.set("bili_jct", "only-csrf", domain=".bilibili.com")
        with self.assertRaisesRegex(ValueError, "SESSDATA"):
            self.module.import_bilibili_cookies(
                "edge",
                extractor=lambda _browser: jar,
            )

    def test_handoff_stores_encrypted_cookie(self):
        cookie = self.module.import_bilibili_cookies(
            "edge",
            extractor=lambda _browser: self.jar(),
            cookie_manager=self.manager,
        )
        self.assertEqual(self.manager.get("bilibili"), cookie)
        self.assertNotIn(
            "browser-sess",
            Path(self.temp.name, "downloader.json").read_text(encoding="utf-8"),
        )


if __name__ == "__main__":
    unittest.main()
