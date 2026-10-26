import importlib.util
import json
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path

SERVICES = Path(__file__).resolve().parents[1] / "app" / "services"


def load_module(name: str):
    app_package = types.ModuleType("app")
    app_package.__path__ = [str(SERVICES.parent)]
    services_package = types.ModuleType("app.services")
    services_package.__path__ = [str(SERVICES)]
    sys.modules["app"] = app_package
    sys.modules["app.services"] = services_package
    module_name = f"app.services.{name}"
    spec = importlib.util.spec_from_file_location(module_name, SERVICES / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


secure_store_module = load_module("secure_store")
cookie_manager_module = load_module("cookie_manager")


class SecureStoreTests(unittest.TestCase):
    def test_aes_round_trip_never_writes_plaintext(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "credentials.json"
            store = secure_store_module.SecureStore(
                path,
                backend="aesgcm",
                secret="test-master-secret",
            )
            payload = {
                "bilibili": {
                    "cookie": "SESSDATA=secret-cookie; bili_jct=csrf",
                }
            }

            store.write(payload)

            self.assertNotIn("secret-cookie", path.read_text(encoding="utf-8"))
            self.assertEqual(store.read(), payload)
            self.assertEqual(store.backend_name, "aesgcm")

    @unittest.skipUnless(os.name == "nt", "DPAPI is Windows-only")
    def test_dpapi_round_trip_never_writes_plaintext(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "credentials.json"
            store = secure_store_module.SecureStore(path, backend="dpapi")
            payload = {"bilibili": {"cookie": "SESSDATA=dpapi-secret"}}

            store.write(payload)

            self.assertNotIn("dpapi-secret", path.read_text(encoding="utf-8"))
            self.assertEqual(store.read(), payload)

    def test_aes_requires_explicit_secret(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = secure_store_module.SecureStore(
                Path(tmp) / "credentials.json",
                backend="aesgcm",
                secret="",
            )
            with self.assertRaisesRegex(ValueError, "BILIBILI_CREDENTIAL_SECRET"):
                store.write({"bilibili": {"cookie": "secret"}})


class CookieManagerMigrationTests(unittest.TestCase):
    def test_migrates_plaintext_cookie_file_and_removes_secret(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "downloader.json"
            path.write_text(
                json.dumps(
                    {"bilibili": {"cookie": "SESSDATA=legacy-secret"}},
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            store = secure_store_module.SecureStore(
                path,
                backend="aesgcm",
                secret="migration-secret",
            )
            manager = cookie_manager_module.CookieConfigManager(
                filepath=str(path),
                secure_store=store,
            )

            self.assertEqual(manager.get("bilibili"), "SESSDATA=legacy-secret")
            self.assertNotIn("legacy-secret", path.read_text(encoding="utf-8"))
            self.assertEqual(store.read()["bilibili"]["cookie"], "SESSDATA=legacy-secret")


if __name__ == "__main__":
    unittest.main()
