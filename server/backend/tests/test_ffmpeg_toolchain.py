import importlib.util
import logging
import os
import pathlib
import sys
import tempfile
import types
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
BUNDLED_FFMPEG = ROOT / "tools" / "ffmpeg" / "bin" / "ffmpeg.exe"


def load_ffmpeg_helper():
    inserted = []
    if "app" not in sys.modules:
        for name in ("app", "app.utils"):
            module = types.ModuleType(name)
            if name == "app":
                module.__path__ = [str(ROOT / "app")]
            else:
                module.__path__ = [str(ROOT / "app" / "utils")]
            sys.modules[name] = module
            inserted.append(name)
    if "app.utils.logger" not in sys.modules:
        logger_module = types.ModuleType("app.utils.logger")
        logger_module.get_logger = logging.getLogger
        sys.modules["app.utils.logger"] = logger_module
        inserted.append("app.utils.logger")

    spec = importlib.util.spec_from_file_location(
        "ffmpeg_helper_under_test",
        ROOT / "ffmpeg_helper.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for name in reversed(inserted):
        sys.modules.pop(name, None)
    return module


class FfmpegToolchainTests(unittest.TestCase):
    def setUp(self):
        if not BUNDLED_FFMPEG.is_file():
            self.skipTest("bundled ffmpeg.exe is unavailable")
        self.ffmpeg_helper = load_ffmpeg_helper()
        self.original_bin_path = os.environ.get("FFMPEG_BIN_PATH")
        self.original_process_path = os.environ.get("PATH", "")

    def tearDown(self):
        if self.original_bin_path is None:
            os.environ.pop("FFMPEG_BIN_PATH", None)
        else:
            os.environ["FFMPEG_BIN_PATH"] = self.original_bin_path
        os.environ["PATH"] = self.original_process_path

    @staticmethod
    def _link_ffmpeg(tools: pathlib.Path, name: str) -> None:
        target = tools / name
        try:
            os.link(BUNDLED_FFMPEG, target)
        except OSError:
            target.write_bytes(BUNDLED_FFMPEG.read_bytes())

    def test_only_ffmpeg_is_not_reported_as_complete_toolchain(self):
        with tempfile.TemporaryDirectory() as temp:
            tools = pathlib.Path(temp)
            self._link_ffmpeg(tools, "ffmpeg.exe")
            os.environ["FFMPEG_BIN_PATH"] = str(tools)

            self.assertFalse(self.ffmpeg_helper.check_ffmpeg_exists())

    def test_ffmpeg_and_ffprobe_are_reported_as_complete_toolchain(self):
        with tempfile.TemporaryDirectory() as temp:
            tools = pathlib.Path(temp)
            self._link_ffmpeg(tools, "ffmpeg.exe")
            self._link_ffmpeg(tools, "ffprobe.exe")
            os.environ["FFMPEG_BIN_PATH"] = str(tools)

            self.assertTrue(self.ffmpeg_helper.check_ffmpeg_exists())


if __name__ == "__main__":
    unittest.main()
