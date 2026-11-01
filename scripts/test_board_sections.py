"""The board keeps its counts while separating work that waits on the manager."""
import tempfile
import unittest

import collect_github_issues as github
import collect_local_scratch as local


class BoardSectionsTests(unittest.TestCase):
    def test_both_collectors_split_existing_rows_under_the_agreed_headings(self):
        with tempfile.TemporaryDirectory() as root:
            github_lines = github.build_lines(
                root, {"github_repo": "example/synthetic"},
                {"ready-for-human": [1, 2], "needs-info": [1],
                 "ready-for-agent": [1, 2, 3]}, [], [], [], "12:34",
            )
            local_lines = local.build_lines(
                root, {"ready-for-human": [1, 2], "needs-info": [1],
                       "ready-for-agent": [1, 2, 3], "done": [1]},
                [], [], [], "12:34",
            )
        for name, lines, moving_rows in (
            ("github", github_lines, [
                "1 tickets at needs-info",
                "3 tickets at ready-for-agent, draining by default",
            ]),
            ("local", local_lines, [
                "1 tickets at needs-info",
                "1 tickets merged/done/resolved, 0 closed as wontfix — history, nothing pending",
            ]),
        ):
            with self.subTest(collector=name):
                headings = [text for kind, text, _, _ in lines if kind == "h2"]
                self.assertEqual(headings[:5], [
                    "Mandatum? Ik Willen!", "STUDIO ROUND — 0 briefs to carry",
                    "WAITING ON YOU", "MOVING WITHOUT YOU",
                    "GRILL QUEUE — 0 parked; each leaves only through a sitting with you",
                ])
                sections = {}
                for kind, text, _, _ in lines:
                    if kind == "h2":
                        section = sections.setdefault(text, [])
                    elif kind == "row":
                        section.append(text)
                self.assertEqual(sections["WAITING ON YOU"], [
                    "2 tickets at ready-for-human",
                ])
                self.assertEqual(sections["MOVING WITHOUT YOU"], moving_rows)
                self.assertFalse(any("skip" in h.lower() for h in headings))


if __name__ == "__main__":
    unittest.main()
