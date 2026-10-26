import importlib.util
import json
import pathlib
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[2]
RENDERER = ROOT / "skills" / "bilibili-favorites-brief" / "scripts" / "render_report.py"


def load_renderer():
    spec = importlib.util.spec_from_file_location("bili_favorites_renderer", RENDERER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class BiliFavoritesRenderingTests(unittest.TestCase):
    def setUp(self):
        self.module = load_renderer()

    def test_video_card_renders_summary_mindmap_fallback_and_escapes_title(self):
        result = {
            "markdown": (
                "## 一句话结论\n"
                "这个视频值得优先看。\n\n"
                "## 核心摘要\n"
                "- 第一条重点\n"
                "- 第二条重点\n\n"
                "## 章节\n"
                "- [00:00] 开场\n"
                "- [00:10] 深入\n"
            ),
            "audio_meta": {
                "title": "视频<script>alert(1)</script>",
                "video_id": "BV1",
                "cover_url": "https://example.com/cover.jpg",
            },
            "transcript": {
                "language": "zh",
                "full_text": "开场全文 深入全文",
                "segments": [
                    {"start": 0.0, "end": 9.0, "text": "开场全文"},
                    {"start": 10.0, "end": 20.0, "text": "深入全文"},
                ],
            },
        }
        with tempfile.TemporaryDirectory() as temp:
            destination = pathlib.Path(temp) / "知识卡.html"
            self.module.render_video_card(
                result,
                destination,
                source_url="https://www.bilibili.com/video/BV1",
            )
            html = destination.read_text(encoding="utf-8")
            svg_exists = (pathlib.Path(temp) / "思维导图.svg").is_file()
            chapter_exists = (pathlib.Path(temp) / "章节全文.md").is_file()

        self.assertIn("一句话结论", html)
        self.assertIn("知识卡", html)
        self.assertIn("文字版思维导图", html)
        self.assertIn("static-mindmap", html)
        self.assertIn("章节全文", html)
        self.assertIn("开场全文", html)
        self.assertIn("深入全文", html)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", html)
        self.assertNotIn("<script>alert(1)</script>", html)
        self.assertTrue(svg_exists)
        self.assertTrue(chapter_exists)

    def test_batch_report_lists_success_failure_and_skipped_items(self):
        with tempfile.TemporaryDirectory() as temp:
            batch_dir = pathlib.Path(temp) / "产品_2026-10-24_2130"
            batch_dir.mkdir()
            success_dir = batch_dir / "videos" / "BV1"
            success_dir.mkdir(parents=True)
            (success_dir / "result.json").write_text(
                json.dumps(
                    {
                        "markdown": "## 一句话结论\n值得看。\n\n## 核心摘要\n- 重点",
                        "audio_meta": {"title": "视频标题"},
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            manifest = {
                "schema_version": 1,
                "folder": {"media_id": 1001, "title": "产品<script>alert(1)</script>"},
                "items": [
                    {
                        "bvid": "BV1",
                        "title": "视频标题",
                        "state": "success",
                        "task_id": "task-1",
                    },
                    {
                        "bvid": "BV2",
                        "title": "失败视频",
                        "state": "failed",
                        "message": "模型调用失败",
                    },
                    {
                        "bvid": "",
                        "title": "失效收藏",
                        "state": "skipped",
                        "message": "unsupported_type",
                    },
                ],
            }
            report_path = batch_dir / "总报告.html"

            self.module.render_batch_report(manifest, report_path)

            html = report_path.read_text(encoding="utf-8")
            markdown = (batch_dir / "总报告.md").read_text(encoding="utf-8")

        self.assertIn("失败项", html)
        self.assertIn("已跳过", html)
        self.assertIn("视频标题", html)
        self.assertIn("值得看", html)
        self.assertNotIn("<script>alert(1)</script>", html)
        self.assertIn("跨视频分析", markdown)
        self.assertIn("模型调用失败", markdown)
        self.assertIn("unsupported_type", markdown)

    def test_rerender_preserves_existing_cross_video_analysis(self):
        with tempfile.TemporaryDirectory() as temp:
            batch_dir = pathlib.Path(temp)
            (batch_dir / "videos" / "BV1").mkdir(parents=True)
            (batch_dir / "videos" / "BV1" / "result.json").write_text(
                json.dumps(
                    {
                        "markdown": "## 一句话结论\n值得看。",
                        "audio_meta": {"title": "视频标题"},
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            manifest = {
                "folder": {"title": "产品"},
                "items": [
                    {
                        "bvid": "BV1",
                        "title": "视频标题",
                        "state": "success",
                    }
                ],
            }
            report_path = batch_dir / "总报告.html"
            (batch_dir / "总报告.md").write_text(
                "# 旧报告\n\n## 跨视频分析\n\n已有的人工分析：先看基础，再看实战。\n",
                encoding="utf-8",
            )

            self.module.render_batch_report(manifest, report_path)

            html = report_path.read_text(encoding="utf-8")
            markdown = (batch_dir / "总报告.md").read_text(encoding="utf-8")

        self.assertIn("先看基础，再看实战", html)
        self.assertIn("先看基础，再看实战", markdown)
        self.assertNotIn("请让 Codex/WorkBuddy", html)

    def test_report_links_multipart_items_to_page_specific_directories(self):
        with tempfile.TemporaryDirectory() as temp:
            batch_dir = pathlib.Path(temp)
            video_dir = batch_dir / "videos" / "BV1_p02"
            video_dir.mkdir(parents=True)
            (video_dir / "result.json").write_text(
                json.dumps(
                    {
                        "markdown": "## 一句话结论\n第二集。",
                        "audio_meta": {"title": "第二集"},
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            manifest = {
                "folder": {"title": "课程"},
                "items": [
                    {
                        "bvid": "BV1",
                        "parent_bvid": "BV1",
                        "page": 2,
                        "title": "课程 - p02 第二集",
                        "state": "success",
                    }
                ],
            }

            self.module.render_batch_report(manifest, batch_dir / "总报告.html")

            html = (batch_dir / "总报告.html").read_text(encoding="utf-8")

        self.assertIn("videos/BV1_p02/知识卡.html", html)


if __name__ == "__main__":
    unittest.main()
