import importlib.util
import unittest
from dataclasses import dataclass
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "app" / "services" / "brief_preflight.py"


def load_preflight_module():
    spec = importlib.util.spec_from_file_location("brief_preflight", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@dataclass
class FakeTranscript:
    language: str
    full_text: str
    segments: list[dict]


class BriefPreflightTests(unittest.TestCase):
    def setUp(self):
        self.module = load_preflight_module()

    def test_existing_prefetched_transcript_skips_subtitle_fetch(self):
        payload = {"language": "zh", "full_text": "hello", "segments": []}

        result = self.module.resolve_brief_transcript(
            prefetched_transcript=payload,
            readiness={"ready": False},
            fetch_subtitles=lambda _url: self.fail("subtitle fetch should be skipped"),
            video_url="https://www.bilibili.com/video/BV1xx411c7mD",
        )

        self.assertEqual(result.transcript, payload)
        self.assertIsNone(result.blocking_reason)

    def test_ready_online_transcriber_proceeds_without_sync_fetch(self):
        result = self.module.resolve_brief_transcript(
            prefetched_transcript=None,
            readiness={"ready": True, "transcriber_type": "bcut"},
            fetch_subtitles=lambda _url: self.fail("ready transcriber should proceed"),
            video_url="https://www.bilibili.com/video/BV1xx411c7mD",
        )

        self.assertIsNone(result.transcript)
        self.assertIsNone(result.blocking_reason)

    def test_unready_local_transcriber_proceeds_when_subtitle_exists(self):
        fetched = FakeTranscript(
            language="zh",
            full_text="字幕内容",
            segments=[{"start": 0.0, "end": 2.0, "text": "字幕内容"}],
        )

        result = self.module.resolve_brief_transcript(
            prefetched_transcript=None,
            readiness={"ready": False, "transcriber_type": "fast-whisper"},
            fetch_subtitles=lambda _url: fetched,
            video_url="https://www.bilibili.com/video/BV1xx411c7mD",
        )

        self.assertEqual(result.transcript["language"], "zh")
        self.assertEqual(result.transcript["full_text"], "字幕内容")
        self.assertEqual(result.transcript["segments"][0]["text"], "字幕内容")
        self.assertIsNone(result.blocking_reason)

    def test_unready_local_transcriber_blocks_only_when_no_subtitle_exists(self):
        readiness = {
            "ready": False,
            "transcriber_type": "fast-whisper",
            "model_size": "tiny",
            "downloading": False,
            "reason": "转写模型尚未下载就绪",
        }

        result = self.module.resolve_brief_transcript(
            prefetched_transcript=None,
            readiness=readiness,
            fetch_subtitles=lambda _url: None,
            video_url="https://www.bilibili.com/video/BV1xx411c7mD",
        )

        self.assertIsNone(result.transcript)
        self.assertEqual(result.blocking_reason["reason"], "transcriber_model_not_ready")
        self.assertEqual(result.blocking_reason["transcriber_type"], "fast-whisper")
        self.assertTrue(result.blocking_reason["subtitle_checked"])

    def test_subtitle_fetch_error_falls_back_to_readiness_reason(self):
        def fail_fetch(_url):
            raise RuntimeError("subtitle endpoint unavailable")

        result = self.module.resolve_brief_transcript(
            prefetched_transcript=None,
            readiness={
                "ready": False,
                "transcriber_type": "fast-whisper",
                "model_size": "tiny",
                "reason": "转写模型尚未下载就绪",
            },
            fetch_subtitles=fail_fetch,
            video_url="https://www.bilibili.com/video/BV1xx411c7mD",
        )

        self.assertIsNone(result.transcript)
        self.assertEqual(result.blocking_reason["reason"], "transcriber_model_not_ready")
        self.assertTrue(result.blocking_reason["subtitle_checked"])


if __name__ == "__main__":
    unittest.main()
