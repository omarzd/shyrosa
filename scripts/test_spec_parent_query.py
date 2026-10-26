"""Discharge query regression tests for #54; gh reads synthetic scratch fixtures."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).with_name("spec-parent-query.py")

# Handwritten rendered counterparts for the retained raw-body regressions.
RENDERED_BODIES = {
    18: '<p>Start watching at 50%, then merge <a href="https://github.com/example/tracker/issues/50">#50</a>.</p>',
    51: '<h2>Parent</h2><p><a href="https://github.com/example/tracker/issues/50">#50</a></p><h2>What to build</h2><p>A feature</p>',
    52: '<h2>Parent</h2><p>tracker#50, a spec.</p>',
    53: '<h2>Parent</h2><p><a href="https://github.com/example/tracker/issues/50">Spec</a></p>',
    54: '<h2>Parent</h2><p>#500</p><h2>Notes</h2><p>#50</p>',
    55: '<h2>Parent</h2><p>#5</p><h1>Notes</h1><p>#50</p>',
    56: '<h2>Notes</h2><p>A <code>## Parent</code> mentions #50.</p>',
    57: '<h2>Parent</h2><p>50%</p>',
    58: '',
    59: '<h2>Parent</h2><p>#50</p>',
    60: '<pre><code>## Parent\n#50\n</code></pre>',
    61: '<h2>Parent</h2><pre><code>#50\n</code></pre><h2>Notes</h2><p>#50</p>',
    62: '<h2>Parenthood</h2><p>#50</p>',
    63: '<h2>Parent</h2><p>#50extra</p>',
    64: '<h2>Parent</h2><p><a href="https://github.com/example/tracker/issues/500">https://github.com/example/tracker/issues/500</a></p>',
    65: '<h2>Parent</h2><h3>Spec</h3><p>#50</p>',
    66: '<h2>Parent</h2><p>#5</p><h2>Notes</h2><p>#50</p><h2>Parent</h2><p>#50</p>',
    70: '<h2>Parent</h2><p><a href="https://github.com/unrelated/another/issues/50">https://github.com/unrelated/another/issues/50</a></p>',
    71: '<h2>Parent</h2><p><a href="https://github.com/unrelated/another/issues/50">unrelated/another#50</a></p>',
    72: '<h2>Parent</h2><p>another#50</p>',
    73: '<h2>Parent</h2><p><a href="https://github.com/example/tracker/issues/50">example/tracker#50</a></p>',
    74: '<h2>Parent</h2><p>project#50</p>',
    80: '<h2>Parent</h2><p><a href="https://github.com/foreign/repo/issues/50">#50</a></p>',
    81: '<h2>Parent</h2><p><a href="https://github.com/example/tracker/issues/50">#50</a></p>',
    82: '<h2>Parent</h2><p><a href="https://github.com/example/tracker/issues/51">#50</a></p>',
    83: '<h2>Parent</h2><p><a href="https://github.com/foreign/repo/issues/50">project#50</a></p>',
    84: '<h2>Parent</h2><p><a href="https://github.com/foreign/repo/issues/50">Spec</a> and project#50</p>',
    90: '<h2>Parent</h2><p>#51</p><h1>Notes</h1><p>#50</p>',
    91: '<h2>Parent</h2><p>#51</p><h2>Notes</h2><p>#50</p>',
    92: '<h2>Parent</h2><p>#50</p><h2>Notes</h2><p>#51</p>',
    93: '<h2>Parent</h2><h3>Details</h3><p>#50</p>',
    94: '<h2>Parent</h2><pre><code>Notes\n-----\n#51\n</code></pre><p>#50</p>',
    95: '<h2>Parent</h2><p>#51</p><h1>#50</h1>',
    96: '<h2>Parent</h2><h3>Details</h3><hr><p>#50</p>',
    100: '<h2>Parent</h2><p><a href="https://github.com/foreign/repo/issues/50">#50</a></p>',
    101: '<h2>Parent</h2><p><a href="https://github.com/example/tracker/issues/50">#50</a></p><h2>Notes</h2>',
    102: '<h2>Parent</h2><p><a href="https://github.com/foreign/repo/issues/50">#50</a></p>',
    103: '<h2>Parent</h2><p><a href="https://github.com/example/tracker/issues/50">#50</a></p>',
    104: '<h2>Parent</h2><p><a href="https://github.com/foreign/repo/issues/50">#50</a> and project#50</p>',
    105: '<h2>Parent</h2><p>#51</p>',
}


class SpecParentQueryTests(unittest.TestCase):
    def query(self, pages, failure=False, alias=None):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pages = [[dict(issue, body_html=issue.get("body_html", RENDERED_BODIES.get(issue["number"])))
                      for issue in page] for page in pages]
            (root / "issues.json").write_text(json.dumps(pages), encoding="utf-8")
            gh = root / "gh"
            gh.write_text(
                "#!/bin/bash\n"
                'if [ "$QUERY_FAILURE" = 1 ]; then echo unavailable >&2; exit 1; fi\n'
                'if [ "$*" != "api --paginate --slurp -H Accept: application/vnd.github.full+json repos/example/tracker/issues?state=open&per_page=100" ]; then\n'
                '  echo "unexpected gh invocation: $*" >&2; exit 2\nfi\n'
                'cat "$QUERY_FIXTURE"\n', encoding="utf-8")
            gh.chmod(0o755)
            env = dict(os.environ, PATH=tmp + os.pathsep + os.environ["PATH"],
                       QUERY_FIXTURE=str(root / "issues.json"),
                       QUERY_FAILURE="1" if failure else "0")
            command = [sys.executable, str(SCRIPT), "--repo", "example/tracker", "--spec", "50"]
            if alias:
                command.extend(["--alias", alias])
            return subprocess.run(command,
                env=env, capture_output=True, text=True)

    def test_counts_only_parent_references_across_all_pages(self):
        pages = [[
            {"number": 18, "body": "Start watching at 50%, then merge #50."},
            {"number": 51, "body": "## Parent\n\n#50\n\n## What to build\nA feature"},
            {"number": 52, "body": "## Parent\n\ntracker#50, a spec.\n"},
        ], [
            {"number": 53, "body": "## Parent\n\n[Spec](https://github.com/example/tracker/issues/50)\n"},
            {"number": 54, "body": "## Parent\n#500\n\n## Notes\n#50"},
            {"number": 55, "body": "## Parent\n#5\n# Notes\n#50"},
            {"number": 56, "body": "## Notes\nA `## Parent` mentions #50."},
            {"number": 57, "body": "## Parent\n50%"},
            {"number": 58, "body": None},
            {"number": 59, "body": "## Parent\n#50", "pull_request": {}},
        ]]
        result = self.query(pages)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual([issue["number"] for issue in json.loads(result.stdout)],
                         [51, 52, 53])

    def test_failed_query_cannot_report_no_remaining_tickets(self):
        result = self.query([], failure=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")
        self.assertIn("query failed", result.stderr)

    def test_foreign_repository_reference_does_not_block_this_spec(self):
        result = self.query([[
            {"number": 70, "body": "## Parent\nhttps://github.com/unrelated/another/issues/50"},
            {"number": 71, "body": "## Parent\nunrelated/another#50"},
            {"number": 72, "body": "## Parent\nanother#50"},
            {"number": 73, "body": "## Parent\nexample/tracker#50"},
        ]])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual([issue["number"] for issue in json.loads(result.stdout)], [73])

    def test_project_shorthand_can_name_a_separate_private_tracker(self):
        pages = [[{"number": 74, "body": "## Parent\nproject#50"}]]
        result = self.query(pages, alias="project")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual([issue["number"] for issue in json.loads(result.stdout)], [74])

    def test_markdown_link_destination_controls_repository_identity(self):
        result = self.query([[
            {"number": 80, "body": "## Parent\n[#50](https://github.com/foreign/repo/issues/50)"},
            {"number": 81, "body": "## Parent\n[#50](https://github.com/example/tracker/issues/50)"},
            {"number": 82, "body": "## Parent\n[#50](https://github.com/example/tracker/issues/51)"},
            {"number": 83, "body": "## Parent\n[project#50](https://github.com/foreign/repo/issues/50)"},
            {"number": 84, "body": "## Parent\n[Spec](https://github.com/foreign/repo/issues/50) and project#50"},
        ]], alias="project")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual([issue["number"] for issue in json.loads(result.stdout)], [81, 84])

    def test_setext_headings_end_parent_without_breaking_nested_headings_or_fences(self):
        result = self.query([[
            {"number": 90, "body": "## Parent\n#51\n\nNotes\n=====\n#50"},
            {"number": 91, "body": "## Parent\n#51\n\nNotes\n-----\n#50"},
            {"number": 92, "body": "## Parent\n#50\n\nNotes\n-----\n#51"},
            {"number": 93, "body": "## Parent\n### Details\n#50"},
            {"number": 94, "body": "## Parent\n```\nNotes\n-----\n#51\n```\n#50"},
            {"number": 95, "body": "## Parent\n#51\n\n#50\n====="},
            {"number": 96, "body": "## Parent\n### Details\n-----\n#50"},
        ]])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual([issue["number"] for issue in json.loads(result.stdout)],
                         [92, 93, 94, 96])

    def test_reference_style_link_destination_controls_repository_identity(self):
        result = self.query([[
            {"number": 100, "body": "## Parent\n[#50][foreign]\n\n[foreign]: https://github.com/foreign/repo/issues/50"},
            {"number": 101, "body": "## Parent\n[#50][LOCAL]\n\n## Notes\n[local]: https://github.com/example/tracker/issues/50"},
            {"number": 102, "body": "## Parent\n[#50][]\n\n[#50]: https://github.com/foreign/repo/issues/50"},
            {"number": 103, "body": "## Parent\n[#50]\n\n[#50]: https://github.com/example/tracker/issues/50"},
            {"number": 104, "body": "## Parent\n[#50][foreign] and project#50\n\n[foreign]: https://github.com/foreign/repo/issues/50"},
            {"number": 105, "body": "## Parent\n#51\n\n[unused]: https://github.com/example/tracker/issues/50"},
        ]], alias="project")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual([issue["number"] for issue in json.loads(result.stdout)],
                         [101, 103, 104])

    def test_no_parent_references_reports_empty_list(self):
        result = self.query([[{"number": 18, "body": "Watch at 50%."}], []])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), [])

    def test_split_line_foreign_reference_definition_does_not_block_local_spec(self):
        result = self.query([[{
            "number": 110,
            "body": "## Parent\n[#50][foreign]\n\n[foreign]:\n    https://github.com/foreign/repo/issues/50",
            "body_html": '<h2>Parent</h2><p><a href="https://github.com/foreign/repo/issues/50">#50</a></p>',
        }]])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), [])

    def test_split_line_local_reference_definition_prevents_premature_discharge(self):
        result = self.query([[{
            "number": 111,
            "body": "## Parent\n[Spec][local]\n\n## Notes\n[local]:\n    https://github.com/example/tracker/issues/50",
            "body_html": '<h2>Parent</h2><p><a href="https://github.com/example/tracker/issues/50">Spec</a></p><h2>Notes</h2>',
        }]])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual([issue["number"] for issue in json.loads(result.stdout)], [111])

    def test_balanced_brackets_in_label_cannot_override_foreign_destination(self):
        result = self.query([[{
            "number": 112,
            "body": "## Parent\n[spec [#50]](https://github.com/foreign/repo/issues/50)",
            "body_html": '<h2>Parent</h2><p><a href="https://github.com/foreign/repo/issues/50">spec [#50]</a></p>',
        }]])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), [])

    def test_unusable_rendered_body_cannot_authorize_discharge(self):
        for rendered in (None, '', ' ', 42, 'not HTML', '<h2>Parent', '<p></p>'):
            with self.subTest(rendered=rendered):
                result = self.query([[{"number": 120, "body": "## Parent\n#50", "body_html": rendered}]])
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(result.stdout, '')
                self.assertIn('query failed', result.stderr)

    def test_quoted_headings_do_not_create_or_reset_parent_metadata(self):
        result = self.query([[
            {"number": 130, "body": "> ## Parent\n> #50",
             "body_html": '<blockquote><h2>Parent</h2><p>#50</p></blockquote>'},
            {"number": 131, "body": "## Parent\n#51\n\n> ## Notes\n> #51\n\n#50",
             "body_html": '<h2>Parent</h2><p>#51</p><blockquote><h2>Notes</h2><p>#51</p></blockquote><p>#50</p>'},
            {"number": 132, "body": "> ## Parent\n> #51\n\n#50",
             "body_html": '<blockquote><h2>Parent</h2><p>#51</p></blockquote><p>#50</p>'},
            {"number": 133, "body": "> > ## Parent\n> > #50",
             "body_html": '<blockquote><blockquote><h2>Parent</h2><p>#50</p></blockquote></blockquote>'},
            {"number": 134, "body": "## Parent\n#51\n\n> # Notes\n> #51\n\n#50",
             "body_html": '<h2>Parent</h2><p>#51</p><blockquote><h1>Notes</h1><p>#51</p></blockquote><p>#50</p>'},
            {"number": 135, "body": "## Parent\n> #50",
             "body_html": '<h2>Parent</h2><blockquote><p>#50</p></blockquote>'},
        ]])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual([issue["number"] for issue in json.loads(result.stdout)], [131, 134, 135])

    def test_markdown_examples_are_not_parent_sections(self):
        result = self.query([[
            {"number": 60, "body": "```md\n## Parent\n#50\n```"},
            {"number": 61, "body": "## Parent\n~~~\n#50\n~~~\n## Notes\n#50"},
            {"number": 62, "body": "## Parenthood\n#50"},
            {"number": 63, "body": "## Parent\n#50extra"},
            {"number": 64, "body": "## Parent\nhttps://github.com/example/tracker/issues/500"},
            {"number": 65, "body": "## Parent ##\r\n### Spec\r\n#50\r\n"},
            {"number": 66, "body": "## Parent\n#5\n## Notes\n#50\n## Parent\n#50"},
        ]])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual([issue["number"] for issue in json.loads(result.stdout)],
                         [65, 66])


if __name__ == "__main__":
    unittest.main()
