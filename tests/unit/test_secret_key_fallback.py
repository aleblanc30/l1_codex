import os
import subprocess
import sys
from pathlib import Path
from unittest import TestCase

ROOT = Path(__file__).resolve().parents[2]
PRINT_KEY = "import codex.main as m; print('KEY=' + m.codex.secret_key)"


def start_app(secret_key=None):
    """Import codex.main in a fresh process (as gunicorn does) and return (exit code, output, key)."""
    env = {k: v for k, v in os.environ.items() if k != "FLASK_SECRET_KEY"}
    if secret_key is not None:
        env["FLASK_SECRET_KEY"] = secret_key
    result = subprocess.run(
        [sys.executable, "-c", PRINT_KEY],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    output = result.stdout + result.stderr
    keys = [l[len("KEY=") :] for l in result.stdout.splitlines() if l.startswith("KEY=")]
    return result.returncode, output, keys[0] if keys else None


class SecretKeyFallbackTest(TestCase):
    def test_the_app_starts_without_a_secret_key_and_says_so(self):
        code, output, key = start_app()
        self.assertEqual(0, code, output[-500:])
        self.assertEqual(64, len(key))
        self.assertIn("FLASK_SECRET_KEY is not set", output)

    def test_each_start_without_a_key_gets_a_different_random_key(self):
        _, _, first = start_app()
        _, _, second = start_app()
        self.assertNotEqual(first, second)

    def test_an_empty_secret_key_counts_as_not_set(self):
        code, output, key = start_app("")
        self.assertEqual(0, code, output[-500:])
        self.assertEqual(64, len(key))

    def test_a_configured_secret_key_is_used_and_not_reported(self):
        code, output, key = start_app("my-configured-key")
        self.assertEqual(0, code, output[-500:])
        self.assertEqual("my-configured-key", key)
        self.assertNotIn("FLASK_SECRET_KEY is not set", output)
