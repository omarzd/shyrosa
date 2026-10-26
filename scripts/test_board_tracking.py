"""Generated board files must stay out of Git's index (shyrosa-private#12)."""
from pathlib import Path
import subprocess
import unittest


ROOT = Path(__file__).resolve().parent.parent
BOARD_FILES = (".claude/board-changed", "BOARD.html", "BOARD.md")


class BoardTracking(unittest.TestCase):
    def test_generated_board_files_are_not_tracked(self):
        tracked = subprocess.check_output(
            ["git", "ls-files", "--", *BOARD_FILES], cwd=ROOT, text=True,
        ).splitlines()
        self.assertEqual(tracked, [], "Generated board files must remain untracked")


if __name__ == "__main__":
    unittest.main()
