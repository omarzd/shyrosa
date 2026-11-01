"""Optional board assets must never stop the rest of the Stop hook."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from test_board_html import Page


SCRIPTS = Path(__file__).resolve().parent


class BoardAssetProcessTests(unittest.TestCase):
    def test_generation_succeeds_when_either_asset_cannot_be_read(self):
        for filename in ("board.css", "board-theme.js"):
            for failure in ("missing", "unreadable", "undecodable"):
                with self.subTest(asset=filename, failure=failure):
                    if failure == "unreadable" and os.geteuid() == 0:
                        self.skipTest("Root can read files with all permissions removed")
                    with tempfile.TemporaryDirectory() as tmp:
                        root = Path(tmp)
                        scripts = root / "scripts"
                        scripts.mkdir()
                        for source in (
                            "board.py", "fleet_config.py", "collect_local_scratch.py",
                            "md_render.py", "board.css", "board-theme.js",
                        ):
                            shutil.copyfile(SCRIPTS / source, scripts / source)
                        config = root / ".claude"
                        config.mkdir()
                        (config / "fleet.json").write_text(json.dumps({
                            "tracker": "local-scratch", "board_html": "board.html",
                        }), encoding="utf-8")
                        asset = scripts / filename
                        if failure == "missing":
                            asset.unlink()
                        elif failure == "unreadable":
                            asset.chmod(0)
                            self.assertFalse(os.access(asset, os.R_OK))
                        else:
                            asset.write_bytes(b"\xff\xfe\x80")
                        try:
                            result = subprocess.run(
                                [sys.executable, str(scripts / "board.py"), str(root)],
                                cwd=root, capture_output=True, text=True, timeout=15,
                            )
                        finally:
                            if asset.exists():
                                asset.chmod(0o600)
                        self.assertEqual(result.returncode, 0, result.stderr)
                        self.assertTrue((root / "board.html").is_file())
                        doc = (root / "board.html").read_text(encoding="utf-8")
                        page = Page()
                        page.feed(doc)
                        self.assertIn("WAITING ON YOU", page.text)
                        self.assertIn("MOVING WITHOUT YOU", page.text)
                        self.assertIn("0 tickets at ready-for-human", page.text)
                        if filename == "board.css":
                            self.assertNotIn("--serif:", doc)
                            self.assertIn("window.matchMedia", doc)
                        else:
                            self.assertNotIn("Dark mode", page.text)
                            self.assertNotIn("window.localStorage", doc)
                            self.assertIn('--serif: "Iowan Old Style"', doc)


if __name__ == "__main__":
    unittest.main()
