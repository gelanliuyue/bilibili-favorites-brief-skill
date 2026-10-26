import importlib.util
import tempfile
import unittest
from pathlib import Path

MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "app"
    / "services"
    / "transcriber_config_manager.py"
)


def load_manager_module():
    spec = importlib.util.spec_from_file_location(
        "transcriber_config_manager_under_test",
        MODULE_PATH,
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class AsrSettingsTests(unittest.TestCase):
    def setUp(self):
        self.module = load_manager_module()
        self.temp = tempfile.TemporaryDirectory()
        self.manager = self.module.TranscriberConfigManager(
            filepath=str(Path(self.temp.name) / "transcriber.json")
        )

    def tearDown(self):
        self.temp.cleanup()

    def test_subtitle_only_is_saved_and_never_ready_for_transcription(self):
        config = self.manager.update_brief_mode("subtitle_only")
        readiness = self.manager.is_model_ready()

        self.assertEqual(config["transcriber_type"], "subtitle_only")
        self.assertFalse(readiness["ready"])
        self.assertIn("仅处理有字幕", readiness["reason"])

    def test_online_brief_modes_are_ready_without_local_models(self):
        for mode in ("bcut", "kuaishou", "groq"):
            config = self.manager.update_brief_mode(mode)
            readiness = self.manager.is_model_ready()
            self.assertEqual(config["transcriber_type"], mode)
            self.assertTrue(readiness["ready"], mode)
            self.assertFalse(readiness["downloading"], mode)

    def test_invalid_brief_mode_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Unsupported ASR mode"):
            self.manager.update_brief_mode("local-whisper")


if __name__ == "__main__":
    unittest.main()
