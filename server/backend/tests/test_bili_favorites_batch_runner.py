import importlib.util
import json
import pathlib
import tempfile
import threading
import time
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "skills" / "bilibili-favorites-brief" / "scripts" / "bili_favorites.py"


def load_skill_module():
    spec = importlib.util.spec_from_file_location("bili_favorites_batch_runner", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return json.dumps(self.payload, ensure_ascii=False).encode("utf-8")


class FakeBackendClient:
    def __init__(self, *, login=True, provider_ready=True, task_responses=None):
        self.login = login
        self.provider_ready = provider_ready
        self.task_responses = task_responses or {}
        self.submissions = []
        self.polls = []

    def health(self):
        return {"backend": "ok"}

    def login_status(self):
        return {"logged_in": self.login}

    def provider_configured(self, _provider_id):
        return self.provider_ready

    def submit(self, video, provider_id, model_name, task_id):
        self.submissions.append(
            {
                "bvid": video["bvid"],
                "provider_id": provider_id,
                "model_name": model_name,
                "task_id": task_id,
            }
        )
        if task_id:
            return task_id
        return f"task-{video['bvid']}"

    def task(self, task_id):
        self.polls.append(task_id)
        response = self.task_responses[task_id]
        if isinstance(response, Exception):
            raise response
        return response


class BiliFavoritesBatchRunnerTests(unittest.TestCase):
    def setUp(self):
        self.module = load_skill_module()

    def make_batch(self, root, items):
        batch_dir = pathlib.Path(root) / "batch"
        batch_dir.mkdir()
        manifest = {
            "schema_version": 1,
            "project_root": str(root),
            "folder": {"media_id": 1001, "title": "产品"},
            "provider": {"id": "deepseek", "model": "deepseek-chat"},
            "items": items,
        }
        self.module.write_manifest(batch_dir, manifest)
        return batch_dir

    def write_backend_result(self, root, task_id):
        result_dir = pathlib.Path(root) / "backend" / "note_results"
        result_dir.mkdir(parents=True, exist_ok=True)
        (result_dir / f"{task_id}.json").write_text(
            json.dumps(
                {
                    "markdown": f"# 摘要 {task_id}",
                    "transcript": {"language": "zh", "full_text": "内容", "segments": []},
                    "audio_meta": {"title": "视频", "video_id": "BV1"},
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

    def test_new_failed_retry_and_later_items_finish_as_partial(self):
        with tempfile.TemporaryDirectory() as temp:
            items = [
                {"bvid": "BV1", "title": "一", "state": "pending", "attempts": 0},
                {
                    "bvid": "BV2",
                    "title": "二",
                    "state": "failed",
                    "task_id": "retry-task",
                    "attempts": 1,
                },
                {"bvid": "BV3", "title": "三", "state": "pending", "attempts": 0},
            ]
            batch_dir = self.make_batch(temp, items)
            self.write_backend_result(temp, "task-BV1")
            self.write_backend_result(temp, "task-BV3")
            client = FakeBackendClient(
                task_responses={
                    "task-BV1": {"status": "SUCCESS"},
                    "retry-task": {
                        "status": "FAILED",
                        "message": "模型调用失败",
                    },
                    "task-BV3": {"status": "SUCCESS"},
                }
            )

            summary = self.module.run_batch(
                batch_dir,
                client,
                "deepseek",
                "deepseek-chat",
                poll_seconds=0,
            )

            manifest = self.module.load_manifest(batch_dir)
            self.assertEqual(summary["status"], "PARTIAL")
            self.assertEqual(
                [item["state"] for item in manifest["items"]],
                ["success", "failed", "success"],
            )
            self.assertEqual(manifest["items"][1]["task_id"], "retry-task")
            self.assertEqual(
                [call["task_id"] for call in client.submissions],
                [None, "retry-task", None],
            )
            self.assertTrue((batch_dir / "videos" / "BV1" / "摘要.md").is_file())

    def test_running_item_resumes_existing_task_without_resubmitting(self):
        with tempfile.TemporaryDirectory() as temp:
            items = [
                {
                    "bvid": "BV1",
                    "title": "一",
                    "state": "running",
                    "task_id": "task-live",
                    "attempts": 1,
                }
            ]
            batch_dir = self.make_batch(temp, items)
            self.write_backend_result(temp, "task-live")
            client = FakeBackendClient(
                task_responses={"task-live": {"status": "SUCCESS"}}
            )

            summary = self.module.run_batch(
                batch_dir,
                client,
                "deepseek",
                "deepseek-chat",
                poll_seconds=0,
            )

            self.assertEqual(summary["status"], "SUCCESS")
            self.assertEqual(client.submissions, [])
            self.assertEqual(client.polls, ["task-live"])

    def test_successful_batch_writes_video_card_and_collection_report(self):
        with tempfile.TemporaryDirectory() as temp:
            items = [
                {
                    "bvid": "BV1",
                    "title": "视频标题",
                    "url": "https://www.bilibili.com/video/BV1",
                    "state": "running",
                    "task_id": "task-render",
                    "attempts": 1,
                }
            ]
            batch_dir = self.make_batch(temp, items)
            self.write_backend_result(temp, "task-render")
            client = FakeBackendClient(
                task_responses={"task-render": {"status": "SUCCESS"}}
            )

            self.module.run_batch(
                batch_dir,
                client,
                "deepseek",
                "deepseek-chat",
                poll_seconds=0,
            )

            self.assertTrue((batch_dir / "videos" / "BV1" / "知识卡.html").is_file())
            self.assertTrue((batch_dir / "总报告.html").is_file())
            self.assertTrue((batch_dir / "总报告.md").is_file())

    def test_multipart_success_uses_page_specific_output_directory(self):
        with tempfile.TemporaryDirectory() as temp:
            items = [
                {
                    "bvid": "BV1",
                    "parent_bvid": "BV1",
                    "page": 2,
                    "title": "合集 - p02 元组",
                    "url": "https://www.bilibili.com/video/BV1?p=2",
                    "state": "running",
                    "task_id": "task-p2",
                    "attempts": 1,
                }
            ]
            batch_dir = self.make_batch(temp, items)
            self.write_backend_result(temp, "task-p2")
            client = FakeBackendClient(
                task_responses={"task-p2": {"status": "SUCCESS"}}
            )

            self.module.run_batch(
                batch_dir,
                client,
                "deepseek",
                "deepseek-chat",
                poll_seconds=0,
            )

            self.assertTrue((batch_dir / "videos" / "BV1_p02" / "摘要.md").is_file())
            self.assertFalse((batch_dir / "videos" / "BV1").exists())

    def test_success_without_backend_result_file_is_marked_failed(self):
        with tempfile.TemporaryDirectory() as temp:
            items = [
                {
                    "bvid": "BV1",
                    "title": "一",
                    "state": "running",
                    "task_id": "task-missing",
                    "attempts": 1,
                }
            ]
            batch_dir = self.make_batch(temp, items)
            client = FakeBackendClient(
                task_responses={"task-missing": {"status": "SUCCESS"}}
            )
            self.module.RESULT_FILE_GRACE_SECONDS = 0.05

            summary = self.module.run_batch(
                batch_dir,
                client,
                "deepseek",
                "deepseek-chat",
                poll_seconds=0,
            )

            item = self.module.load_manifest(batch_dir)["items"][0]
            self.assertEqual(summary["status"], "FAILED")
            self.assertEqual(item["state"], "failed")
            self.assertEqual(item["message"], "result_file_missing")

    def test_success_waits_briefly_for_result_file_to_finish_saving(self):
        with tempfile.TemporaryDirectory() as temp:
            items = [
                {
                    "bvid": "BV1",
                    "title": "一",
                    "state": "running",
                    "task_id": "task-delayed",
                    "attempts": 1,
                }
            ]
            batch_dir = self.make_batch(temp, items)
            client = FakeBackendClient(
                task_responses={"task-delayed": {"status": "SUCCESS"}}
            )
            self.module.RESULT_FILE_GRACE_SECONDS = 0.5

            writer = threading.Timer(
                0.05,
                self.write_backend_result,
                args=(temp, "task-delayed"),
            )
            writer.start()

            summary = self.module.run_batch(
                batch_dir,
                client,
                "deepseek",
                "deepseek-chat",
                poll_seconds=0,
            )
            writer.join()

            item = self.module.load_manifest(batch_dir)["items"][0]
            self.assertEqual(summary["status"], "SUCCESS")
            self.assertEqual(item["state"], "success")

    def test_login_failure_stops_before_any_submission(self):
        with tempfile.TemporaryDirectory() as temp:
            items = [{"bvid": "BV1", "title": "一", "state": "pending"}]
            batch_dir = self.make_batch(temp, items)
            client = FakeBackendClient(login=False)

            summary = self.module.run_batch(
                batch_dir,
                client,
                "deepseek",
                "deepseek-chat",
                poll_seconds=0,
            )

            self.assertEqual(summary["status"], "FAILED")
            self.assertEqual(summary["fatal_reason"], "bilibili_login_required")
            self.assertEqual(client.submissions, [])

    def test_unconfigured_provider_stops_before_any_submission(self):
        with tempfile.TemporaryDirectory() as temp:
            items = [{"bvid": "BV1", "title": "一", "state": "pending"}]
            batch_dir = self.make_batch(temp, items)
            client = FakeBackendClient(provider_ready=False)

            summary = self.module.run_batch(
                batch_dir,
                client,
                "deepseek",
                "deepseek-chat",
                poll_seconds=0,
            )

            self.assertEqual(summary["status"], "FAILED")
            self.assertEqual(summary["fatal_reason"], "provider_not_configured")
            self.assertEqual(client.submissions, [])

    def test_backend_client_returns_data_and_preserves_business_errors(self):
        payloads = [
            {"code": 0, "msg": "success", "data": {"status": "SUCCESS"}},
            {"code": 500, "msg": "任务失败", "data": {"reason": "provider"}},
        ]

        def opener(_request, timeout):
            self.assertEqual(timeout, 15)
            return FakeResponse(payloads.pop(0))

        client = self.module.BackendClient("http://127.0.0.1:8483", opener=opener)

        self.assertEqual(client.task("task-1"), {"status": "SUCCESS"})
        with self.assertRaises(self.module.BackendRequestError) as raised:
            client.task("task-2")
        self.assertEqual(raised.exception.code, 500)
        self.assertEqual(raised.exception.message, "任务失败")


if __name__ == "__main__":
    unittest.main()
