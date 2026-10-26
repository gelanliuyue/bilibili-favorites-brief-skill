import contextlib
import importlib.util
import io
import json
import os
import pathlib
import tempfile
import unittest
from unittest.mock import patch


ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "skills" / "bilibili-favorites-brief" / "scripts" / "bili_favorites.py"


def load_skill_module():
    spec = importlib.util.spec_from_file_location("bili_favorites_skill_cli", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeClient:
    def __init__(self, *, login=True):
        self.login = login
        self.submissions = []

    def health(self):
        return {"backend": "ok"}

    def login_status(self):
        return {"logged_in": self.login}

    def list_folders(self):
        return [
            {"media_id": 1001, "title": "产品", "media_count": 1, "cover": ""},
        ]

    def list_videos(self, media_id, author=None):
        assert media_id == 1001
        self.last_author = author
        return {
            "folder": {"media_id": 1001, "title": "产品", "media_count": 1},
            "videos": [
                {
                    "bvid": "BV1",
                    "title": "视频标题",
                    "url": "https://www.bilibili.com/video/BV1",
                    "cover": "",
                    "duration": 10,
                    "upper": "UP",
                    "fav_time": 1760000000,
                    "available": True,
                }
            ],
            "skipped": [],
            "total": 1,
        }

    def video_pages(self, bvid):
        assert bvid == "BV1"
        return {
            "bvid": "BV1",
            "title": "视频标题",
            "pages": [
                {
                    "page": 1,
                    "part": "视频标题",
                    "duration": 10,
                    "cid": 101,
                    "url": "https://www.bilibili.com/video/BV1?p=1",
                }
            ],
        }

    def provider_configured(self, _provider_id):
        return True

    def submit(self, _video, _provider_id, _model_name, _task_id):
        self.submissions.append("submitted")
        return "task-1"


class BiliFavoritesSkillCliTests(unittest.TestCase):
    def setUp(self):
        self.module = load_skill_module()
        self.temp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.temp.name)
        self.config_path = self.root / "config.json"
        self.config = {
            "project_root": str(self.root / "project"),
            "backend_url": "http://127.0.0.1:8483",
            "output_root": str(self.root / "output"),
            "provider_id": "deepseek",
            "model_name": "deepseek-chat",
        }
        self.config_path.write_text(
            json.dumps(self.config, ensure_ascii=False),
            encoding="utf-8",
        )

    def tearDown(self):
        self.temp.cleanup()

    def invoke(self, argv, client):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with patch.dict(
            os.environ,
            {"BILIBRIEF_SKILL_CONFIG": str(self.config_path)},
        ):
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                code = self.module.main(
                    argv,
                    client_factory=lambda _base_url: client,
                )
        return code, stdout.getvalue(), stderr.getvalue()

    def test_list_prints_folders_without_credentials(self):
        code, stdout, stderr = self.invoke(["list"], FakeClient())

        self.assertEqual(code, 0, stderr)
        self.assertIn("产品", stdout)
        self.assertNotIn("SESSDATA", stdout)
        self.assertNotIn("Cookie", stdout)

    def test_run_stops_before_submission_when_login_is_invalid(self):
        client = FakeClient(login=False)

        code, stdout, stderr = self.invoke(
            ["run", "--folder", "产品", "--yes"],
            client,
        )

        self.assertEqual(code, 2)
        self.assertIn("B 站", stderr + stdout)
        self.assertEqual(client.submissions, [])
        self.assertFalse(pathlib.Path(self.config["output_root"]).exists())

    def test_author_filter_is_used_by_preview_without_submitting(self):
        client = FakeClient()

        code, stdout, stderr = self.invoke(
            ["run", "--folder", "产品", "--author", "测试UP主"],
            client,
        )

        self.assertEqual(code, 0, stderr)
        self.assertEqual(client.last_author, "测试UP主")
        self.assertIn("可处理：1", stdout)
        self.assertIn("尚未提交", stdout)
        self.assertEqual(client.submissions, [])

    def test_status_reports_partial_without_rewriting_manifest(self):
        batch_dir = self.root / "batch"
        batch_dir.mkdir()
        manifest = {
            "schema_version": 1,
            "folder": {"media_id": 1001, "title": "产品"},
            "items": [
                {"bvid": "BV1", "title": "一", "state": "success"},
                {"bvid": "BV2", "title": "二", "state": "failed", "message": "失败"},
            ],
        }
        self.module.write_manifest(batch_dir, manifest)
        before = (batch_dir / "manifest.json").read_bytes()

        code, stdout, stderr = self.invoke(
            ["status", "--batch-dir", str(batch_dir)],
            FakeClient(),
        )

        self.assertEqual(code, 0, stderr)
        self.assertIn("PARTIAL", stdout)
        self.assertEqual((batch_dir / "manifest.json").read_bytes(), before)

    def test_invalid_arguments_exit_nonzero_with_usage(self):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            with self.assertRaises(SystemExit) as raised:
                self.module.main([], client_factory=lambda _url: FakeClient())

        self.assertNotEqual(raised.exception.code, 0)
        self.assertIn("usage", stderr.getvalue().lower())

    def test_default_output_root_uses_documents_bilibrief(self):
        with patch.dict(
            os.environ,
            {"USERPROFILE": r"C:\Users\tester", "HOME": r"C:\Users\tester"},
        ):
            expected = pathlib.Path(r"C:\Users\tester") / "Documents" / "BiliBrief"
            self.assertEqual(self.module.default_output_root(), expected)

    def test_sort_video_items_oldest_uses_publish_time(self):
        videos = [
            {"bvid": "BV3", "pub_time": 300, "fav_time": 3},
            {"bvid": "BV1", "pub_time": 100, "fav_time": 1},
            {"bvid": "BV2", "pub_time": 200, "fav_time": 2},
        ]

        sorted_items = self.module.sort_video_items(videos, "oldest")

        self.assertEqual([item["bvid"] for item in sorted_items], ["BV1", "BV2", "BV3"])

    def test_render_regenerates_existing_video_cards_and_chapter_exports(self):
        batch_dir = self.root / "render-batch"
        video_dir = batch_dir / "videos" / "BV1"
        video_dir.mkdir(parents=True)
        result = {
            "markdown": (
                "## 一句话结论\n值得看。\n\n"
                "## 章节\n- [00:00] 开场\n"
            ),
            "audio_meta": {"title": "视频标题"},
            "transcript": {
                "language": "zh",
                "segments": [{"start": 0, "end": 2, "text": "章节正文"}],
            },
        }
        (video_dir / "result.json").write_text(
            json.dumps(result, ensure_ascii=False),
            encoding="utf-8",
        )
        self.module.write_manifest(
            batch_dir,
            {
                "schema_version": 1,
                "folder": {"title": "产品"},
                "items": [
                    {
                        "bvid": "BV1",
                        "title": "视频标题",
                        "url": "https://www.bilibili.com/video/BV1",
                        "state": "success",
                    }
                ],
            },
        )

        code, _stdout, stderr = self.invoke(
            ["render", "--batch-dir", str(batch_dir)],
            FakeClient(),
        )

        self.assertEqual(code, 0, stderr)
        card = (video_dir / "知识卡.html").read_text(encoding="utf-8")
        self.assertIn("static-mindmap", card)
        self.assertTrue((video_dir / "思维导图.svg").is_file())
        self.assertTrue((video_dir / "章节全文.md").is_file())

    def test_multi_part_video_expands_into_ordered_course_sections(self):
        videos = [
            {
                "bvid": "BV1",
                "title": "Python 合集",
                "url": "https://www.bilibili.com/video/BV1",
                "duration": 30,
                "pub_time": 100,
                "fav_time": 1,
                "upper": "老师",
                "cover": "",
                "available": True,
            }
        ]

        def page_loader(_bvid):
            return {
                "title": "Python 合集",
                "pages": [
                    {"page": 2, "part": "元组", "duration": 20},
                    {"page": 1, "part": "列表", "duration": 10},
                ],
            }

        expanded = self.module.expand_video_pages(videos, page_loader)

        self.assertEqual([item["page"] for item in expanded], [1, 2])
        self.assertEqual(expanded[0]["title"], "Python 合集 - p01 列表")
        self.assertEqual(expanded[1]["url"], "https://www.bilibili.com/video/BV1?p=2")
        self.assertEqual(self.module.item_output_id(expanded[0]), "BV1_p01")
        self.assertEqual(self.module.item_output_id(expanded[1]), "BV1_p02")


if __name__ == "__main__":
    unittest.main()
