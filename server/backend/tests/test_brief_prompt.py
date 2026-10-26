import importlib.util
import sys
import types
import unittest
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
APP_ROOT = BACKEND_ROOT / "app"


def load_prompt_builder():
    app_package = types.ModuleType("app")
    app_package.__path__ = [str(APP_ROOT)]
    gpt_package = types.ModuleType("app.gpt")
    gpt_package.__path__ = [str(APP_ROOT / "gpt")]
    sys.modules["app"] = app_package
    sys.modules["app.gpt"] = gpt_package

    for module_name, file_name in (
        ("app.gpt.prompt", "prompt.py"),
        ("app.gpt.prompt_builder", "prompt_builder.py"),
    ):
        spec = importlib.util.spec_from_file_location(module_name, APP_ROOT / "gpt" / file_name)
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)

    return sys.modules["app.gpt.prompt_builder"]


get_style_format = load_prompt_builder().get_style_format


class BriefPromptTests(unittest.TestCase):
    def test_brief_style_defines_required_sections_and_grounding_rules(self):
        prompt = get_style_format("brief")

        for heading in (
            "一句话结论",
            "是否值得看",
            "核心摘要",
            "章节",
            "术语",
            "行动清单",
        ):
            self.assertIn(heading, prompt)

        self.assertIn("MM:SS", prompt)
        self.assertIn("不得虚构", prompt)
        self.assertIn("字幕", prompt)


if __name__ == "__main__":
    unittest.main()
