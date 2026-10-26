import importlib.util
import sys
import types
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

BACKEND_ROOT = Path(__file__).resolve().parents[1]
PROVIDER_PATH = BACKEND_ROOT / "app" / "services" / "provider.py"


def load_provider_module(row):
    app = types.ModuleType("app")
    app.__path__ = [str(BACKEND_ROOT / "app")]
    services = types.ModuleType("app.services")
    services.__path__ = [str(BACKEND_ROOT / "app" / "services")]

    fastapi = types.ModuleType("fastapi")
    encoders = types.ModuleType("fastapi.encoders")
    encoders.jsonable_encoder = lambda value: value
    fastapi.encoders = encoders

    kombu = types.ModuleType("kombu")
    kombu.uuid = lambda: "generated-id"

    db_models = types.ModuleType("app.db.models.providers")
    db_models.Provider = object
    provider_dao = types.ModuleType("app.db.provider_dao")
    provider_dao.get_all_providers = lambda: [row]
    provider_dao.insert_provider = lambda *args, **kwargs: None
    provider_dao.get_provider_by_name = lambda name: None
    provider_dao.get_provider_by_id = lambda provider_id: None
    provider_dao.update_provider = lambda *args, **kwargs: None
    provider_dao.delete_provider = lambda provider_id: None
    provider_dao.get_enabled_providers = lambda: []

    gpt_factory = types.ModuleType("app.gpt.gpt_factory")
    gpt_factory.GPTFactory = object
    model_config = types.ModuleType("app.models.model_config")
    model_config.ModelConfig = object

    modules = {
        "app": app,
        "app.services": services,
        "fastapi": fastapi,
        "fastapi.encoders": encoders,
        "kombu": kombu,
        "app.db": types.ModuleType("app.db"),
        "app.db.models": types.ModuleType("app.db.models"),
        "app.db.models.providers": db_models,
        "app.db.provider_dao": provider_dao,
        "app.gpt": types.ModuleType("app.gpt"),
        "app.gpt.gpt_factory": gpt_factory,
        "app.models": types.ModuleType("app.models"),
        "app.models.model_config": model_config,
    }
    sys.modules.update(modules)

    spec = importlib.util.spec_from_file_location("provider_under_test", PROVIDER_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ProviderKeyMaskingTests(unittest.TestCase):
    def test_safe_provider_list_never_returns_full_api_key(self):
        row = SimpleNamespace(
            id="deepseek",
            name="DeepSeek",
            logo="DeepSeek",
            type="built-in",
            api_key="sk-test-placeholder-0000",
            base_url="https://api.deepseek.com",
            enabled=1,
            created_at=None,
        )
        module = load_provider_module(row)

        providers = module.ProviderService.get_all_providers_safe()

        self.assertEqual(len(providers), 1)
        self.assertNotEqual(providers[0]["api_key"], row.api_key)
        self.assertIn("*", providers[0]["api_key"])
        self.assertTrue(providers[0]["api_key"].endswith("0000"))

    def test_update_provider_never_logs_full_api_key(self):
        row = SimpleNamespace(
            id="deepseek",
            name="DeepSeek",
            logo="DeepSeek",
            type="built-in",
            api_key="",
            base_url="https://api.deepseek.com",
            enabled=1,
            created_at=None,
        )
        secret = "sk-test-placeholder-0000"
        module = load_provider_module(row)

        with patch("builtins.print") as printed:
            module.ProviderService.update_provider(
                "deepseek",
                {"api_key": secret, "enabled": 1},
            )

        logged = " ".join(str(call) for call in printed.call_args_list)
        self.assertNotIn(secret, logged)


if __name__ == "__main__":
    unittest.main()
