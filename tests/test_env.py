import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from pipeline import env


class LoadLocalEnvTest(unittest.TestCase):
    """HF_TOKEN lives in `.env` (gitignored), not exported.

    Without this, a manual run pulled with no token and the 401 read as
    "the repository does not exist".
    """

    def _write_env(self, tmp: str, content: str) -> Path:
        path = Path(tmp) / ".env"
        path.write_text(content, encoding="utf-8")
        return Path(tmp)

    def test_loads_the_token_from_env_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._write_env(tmp, "HF_TOKEN=hf_secret\n")
            with mock.patch.dict(os.environ, {}, clear=True):
                env.load_local_env(root)
                self.assertEqual(os.environ["HF_TOKEN"], "hf_secret")

    def test_does_not_override_exported_values(self):
        """`HF_TOKEN=... python -m pipeline ...` on the command line wins."""
        with tempfile.TemporaryDirectory() as tmp:
            root = self._write_env(tmp, "HF_TOKEN=hf_from_file\n")
            with mock.patch.dict(os.environ, {"HF_TOKEN": "hf_exported"}, clear=True):
                env.load_local_env(root)
                self.assertEqual(os.environ["HF_TOKEN"], "hf_exported")

    def test_ignores_comments_blanks_and_spaces(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._write_env(tmp, '# comment\n\n  HF_TOKEN = "hf_spaced"  \nNO_EQUALS\n')
            with mock.patch.dict(os.environ, {}, clear=True):
                env.load_local_env(root)
                self.assertEqual(os.environ["HF_TOKEN"], "hf_spaced")

    def test_missing_file_is_fine(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.dict(os.environ, {}, clear=True):
                env.load_local_env(Path(tmp))  # must not raise

    def test_unreadable_file_does_not_crash(self):
        """A broken .env must not take down a capture run."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".env").write_text("HF_TOKEN=x\n", encoding="utf-8")
            (root / ".env").chmod(0o000)
            try:
                with mock.patch.dict(os.environ, {}, clear=True):
                    env.load_local_env(root)  # must not raise
            finally:
                (root / ".env").chmod(0o600)

    def test_never_prints_the_token(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._write_env(tmp, "HF_TOKEN=hf_do_not_print\n")
            with mock.patch.dict(os.environ, {}, clear=True):
                with mock.patch("builtins.print") as printer:
                    env.load_local_env(root)
                self.assertFalse(printer.called, "load_local_env must not print")


if __name__ == "__main__":
    unittest.main()
