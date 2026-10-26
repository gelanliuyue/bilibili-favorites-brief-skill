import importlib.util
import pathlib
import sys
import tempfile
import types
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
DOWNLOADER = ROOT / "app" / "downloaders" / "bilibili_downloader.py"


class FakeYoutubeDL:
    captured = None

    def __init__(self, options):
        type(self).captured = options

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def extract_info(self, _url, download=True):
        return {
            "id": "BV1",
            "title": "合集",
            "duration": 10,
            "thumbnail": "cover",
            "ext": "m4a",
        }


class BilibiliMultipartDownloadTests(unittest.TestCase):
    def setUp(self):
        self.original_modules = {
            name: sys.modules.get(name)
            for name in (
                "app",
                "app.downloaders",
                "app.downloaders.base",
                "app.downloaders.bilibili_dm_patch",
                "app.downloaders.bilibili_subtitle",
                "app.models",
                "app.models.notes_model",
                "app.models.transcriber_model",
                "app.services",
                "app.services.cookie_manager",
                "app.utils",
                "app.utils.logger",
                "app.utils.path_helper",
                "app.utils.url_parser",
                "yt_dlp",
            )
        }
        modules = {
            "app": types.ModuleType("app"),
            "app.downloaders": types.ModuleType("app.downloaders"),
            "app.models": types.ModuleType("app.models"),
            "app.services": types.ModuleType("app.services"),
            "app.utils": types.ModuleType("app.utils"),
        }
        base = types.ModuleType("app.downloaders.base")

        class Downloader:
            def __init__(self):
                self.cache_data = "/tmp"

        base.Downloader = Downloader
        base.DownloadQuality = str
        base.QUALITY_MAP = {"fast": "32"}
        base.YDL_RETRY_OPTS = {
            "retries": 3,
            "fragment_retries": 3,
            "socket_timeout": 30,
        }
        modules["app.downloaders.base"] = base
        patch = types.ModuleType("app.downloaders.bilibili_dm_patch")
        patch.apply_bilibili_dm_img_patch = lambda: None
        modules["app.downloaders.bilibili_dm_patch"] = patch
        subtitle = types.ModuleType("app.downloaders.bilibili_subtitle")
        subtitle.BilibiliSubtitleFetcher = object
        modules["app.downloaders.bilibili_subtitle"] = subtitle
        notes = types.ModuleType("app.models.notes_model")
        notes.AudioDownloadResult = type(
            "AudioDownloadResult",
            (),
            {"__init__": lambda self, **kwargs: self.__dict__.update(kwargs)},
        )
        modules["app.models.notes_model"] = notes
        transcript = types.ModuleType("app.models.transcriber_model")
        transcript.TranscriptResult = object
        transcript.TranscriptSegment = object
        modules["app.models.transcriber_model"] = transcript
        cookie = types.ModuleType("app.services.cookie_manager")
        cookie.CookieConfigManager = type(
            "CookieConfigManager",
            (),
            {"__init__": lambda self: None, "get": lambda self, _platform: None},
        )
        modules["app.services.cookie_manager"] = cookie
        paths = types.ModuleType("app.utils.path_helper")
        paths.get_data_dir = lambda: "/tmp"
        modules["app.utils.path_helper"] = paths
        urls = types.ModuleType("app.utils.url_parser")
        urls.extract_video_id = lambda _url, _platform: "BV1"
        urls.extract_bilibili_p_number = lambda _url: 2
        modules["app.utils.url_parser"] = urls
        yt_dlp = types.ModuleType("yt_dlp")
        yt_dlp.YoutubeDL = FakeYoutubeDL
        modules["yt_dlp"] = yt_dlp
        sys.modules.update(modules)

        spec = importlib.util.spec_from_file_location("bilibili_downloader_under_test", DOWNLOADER)
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)
        self.downloader = self.module.BilibiliDownloader()

    def tearDown(self):
        for name, module in self.original_modules.items():
            if module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module

    def test_skip_download_uses_part_specific_name_without_postprocessing(self):
        with tempfile.TemporaryDirectory() as temp:
            result = self.downloader.download(
                "https://www.bilibili.com/video/BV1?p=2",
                output_dir=temp,
                skip_download=True,
            )

        options = FakeYoutubeDL.captured
        self.assertTrue(options["skip_download"])
        self.assertNotIn("postprocessors", options)
        self.assertIn("BV1_p2.%(ext)s", options["outtmpl"])
        self.assertTrue(result.file_path.endswith("BV1_p2.m4a"))


if __name__ == "__main__":
    unittest.main()
