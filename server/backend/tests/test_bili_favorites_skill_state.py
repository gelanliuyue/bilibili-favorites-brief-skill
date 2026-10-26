import importlib.util
import json
import pathlib
import tempfile
import unittest
from datetime import datetime


ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "skills" / "bilibili-favorites-brief" / "scripts" / "bili_favorites.py"


def load_skill_module():
    spec = importlib.util.spec_from_file_location("bili_favorites_skill_state", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class BiliFavoritesSkillStateTests(unittest.TestCase):
    def setUp(self):
        self.module = load_skill_module()

    def test_safe_name_replaces_windows_illegal_characters(self):
        self.assertEqual(
            self.module.safe_name("产品/经理:入门?"),
            "产品_经理_入门_",
        )
        self.assertEqual(self.module.safe_name("  CON.  "), "_CON")

    def test_batch_status_obeys_success_partial_and_failed_contract(self):
        self.assertEqual(
            self.module.batch_status([{"state": "success"}]),
            "SUCCESS",
        )
        self.assertEqual(
            self.module.batch_status([{"state": "success"}, {"state": "failed"}]),
            "PARTIAL",
        )
        self.assertEqual(
            self.module.batch_status([{"state": "success"}, {"state": "skipped"}]),
            "PARTIAL",
        )
        self.assertEqual(
            self.module.batch_status([{"state": "failed"}, {"state": "skipped"}]),
            "FAILED",
        )

    def test_resume_includes_pending_running_and_failed_items_in_order(self):
        manifest = {
            "items": [
                {"bvid": "BV1", "state": "pending"},
                {"bvid": "BV2", "state": "running"},
                {"bvid": "BV3", "state": "failed"},
                {"bvid": "BV4", "state": "success"},
                {"bvid": "BV5", "state": "skipped"},
            ]
        }

        resumed = self.module.next_pending_items(manifest)

        self.assertEqual([item["bvid"] for item in resumed], ["BV1", "BV2", "BV3"])

    def test_write_manifest_is_atomic_and_keeps_previous_file_on_failure(self):
        with tempfile.TemporaryDirectory() as temp:
            batch_dir = pathlib.Path(temp)
            original = {"schema_version": 1, "items": []}
            self.module.write_manifest(batch_dir, original)
            before = self.module.load_manifest(batch_dir)

            with self.assertRaises(TypeError):
                self.module.write_manifest(batch_dir, {"bad": {1, 2}})

            self.assertEqual(
                json.loads((batch_dir / "manifest.json").read_text(encoding="utf-8")),
                before,
            )
            self.assertEqual(list(batch_dir.glob("*.tmp")), [])

    def test_same_title_and_timestamp_gets_distinct_batch_directories(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            fixed = datetime(2026, 10, 24, 21, 30)

            first = self.module.create_batch_dir(root, "产品", fixed)
            second = self.module.create_batch_dir(root, "产品", fixed)

            self.assertTrue(first.is_dir())
            self.assertTrue(second.is_dir())
            self.assertNotEqual(first, second)
            self.assertEqual(first.name, "产品_2026-10-24_2130")
            self.assertEqual(second.name, "产品_2026-10-24_2130_2")

    def test_manifest_round_trip_preserves_structure(self):
        with tempfile.TemporaryDirectory() as temp:
            batch_dir = pathlib.Path(temp)
            manifest = {
                "schema_version": 1,
                "folder": {"media_id": 1001, "title": "产品"},
                "provider": {"id": "deepseek", "model": "deepseek-chat"},
                "items": [{"bvid": "BV1", "state": "pending"}],
            }

            self.module.write_manifest(batch_dir, manifest)

            loaded = self.module.load_manifest(batch_dir)
            self.assertEqual(loaded["folder"], manifest["folder"])
            self.assertEqual(loaded["items"], manifest["items"])
            self.assertIn("updated_at", loaded)


if __name__ == "__main__":
    unittest.main()
