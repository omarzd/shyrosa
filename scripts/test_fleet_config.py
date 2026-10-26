"""Tests for fleet_config: one root and one board path, whichever machine and checkout.

Run: python3 -m unittest discover -s scripts
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fleet_config  # noqa: E402


def _git(*args, cwd):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


def _project(board_html):
    d = os.path.realpath(tempfile.mkdtemp())
    os.mkdir(os.path.join(d, ".claude"))
    with open(os.path.join(d, ".claude", "fleet.json"), "w") as fh:
        json.dump({"tracker": "local-scratch", "board_html": board_html}, fh)
    return d


class Load(unittest.TestCase):
    def test_relative_board_resolves_under_root(self):
        root = _project("demo-board.html")
        self.addCleanup(shutil.rmtree, root)
        got_root, cfg = fleet_config.load(root)
        self.assertEqual(got_root, root)
        self.assertEqual(cfg["board_html"], os.path.join(root, "demo-board.html"))

    def test_absolute_board_kept(self):
        root = _project("/elsewhere/demo-board.html")
        self.addCleanup(shutil.rmtree, root)
        _root, cfg = fleet_config.load(root)
        self.assertEqual(cfg["board_html"], "/elsewhere/demo-board.html")

    def test_missing_fleet_json_raises(self):
        root = os.path.realpath(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, root)
        with self.assertRaises(FileNotFoundError):
            fleet_config.load(root)


class MainCheckout(unittest.TestCase):
    def setUp(self):
        self.main = _project("demo-board.html")
        self.addCleanup(shutil.rmtree, self.main)
        _git("init", "-q", "-b", "main", cwd=self.main)
        _git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "--allow-empty", "-m", "seed",
             cwd=self.main)

    def test_main_checkout_is_itself(self):
        self.assertEqual(fleet_config.main_checkout(self.main), self.main)

    def test_subdirectory_of_main_is_unchanged(self):
        sub = os.path.join(self.main, "sub")
        os.mkdir(sub)
        self.assertEqual(fleet_config.main_checkout(sub), sub)

    def test_linked_worktree_points_at_main(self):
        wt = os.path.realpath(tempfile.mkdtemp())
        shutil.rmtree(wt)
        self.addCleanup(shutil.rmtree, wt, True)
        _git("worktree", "add", "-q", "-b", "side", wt, cwd=self.main)
        root, cfg = fleet_config.load(wt)
        self.assertEqual(root, self.main)
        self.assertEqual(cfg["board_html"], os.path.join(self.main, "demo-board.html"))

    def test_not_a_repo_is_unchanged(self):
        d = os.path.realpath(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, d)
        self.assertEqual(fleet_config.main_checkout(d), d)


if __name__ == "__main__":
    unittest.main()
