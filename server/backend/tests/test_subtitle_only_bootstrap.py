import os
import pathlib
import subprocess
import sys
import textwrap
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class SubtitleOnlyBootstrapTests(unittest.TestCase):
    def test_subtitle_only_mode_can_construct_note_generator_without_transcriber(self):
        env = os.environ.copy()
        env["PYTHONPATH"] = os.pathsep.join(
            filter(None, [str(ROOT), env.get("PYTHONPATH")])
        )
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                textwrap.dedent(
                    """
                    import app.services.transcriber_config_manager as config_module
                    from app.services import note as note_service

                    class FakeConfigManager:
                        def get_whisper_model_size(self):
                            return "tiny"

                        def get_transcriber_type(self):
                            return "subtitle_only"

                    config_module.TranscriberConfigManager = FakeConfigManager

                    generator = note_service.NoteGenerator()

                    assert generator.transcriber_type == "subtitle_only"
                    assert generator.transcriber is None
                    """
                ),
            ],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
        )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
