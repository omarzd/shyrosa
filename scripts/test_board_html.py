"""Generated boards carry their style and theme control without runtime assets."""
from html.parser import HTMLParser
from pathlib import Path
import tempfile
import unittest

from board import write_html


class Page(HTMLParser):
    def __init__(self):
        super().__init__()
        self.elements = []
        self.text = []

    def handle_starttag(self, tag, attrs):
        self.elements.append((tag, dict(attrs)))

    def handle_data(self, data):
        self.text.append(data)


class BoardHtmlTests(unittest.TestCase):
    def test_board_embeds_its_styles_and_accessible_theme_control(self):
        with tempfile.TemporaryDirectory() as root:
            dest = Path(root) / "board.html"
            write_html([
                ("h1", "Synthetic board", None, None),
                ("h2", "WAITING ON YOU", None, None),
                ("row", "2 tickets at ready-for-human", None, None),
                ("h2", "MOVING WITHOUT YOU", None, None),
                ("row", "1 tickets at needs-info", None, None),
                ("note", "HOLD <thread> or HOLD ALL", None, None),
            ], dest, "Synthetic board")
            doc = dest.read_text()
        page = Page()
        page.feed(doc)
        self.assertIn(("button", {
            "type": "button", "id": "theme-toggle", "aria-pressed": "false",
        }), page.elements)
        self.assertIn("Dark mode", page.text)
        self.assertIn("HOLD &lt;thread&gt; or HOLD ALL", doc)
        self.assertIn('name="viewport"', doc)
        self.assertIn('--serif: "Iowan Old Style"', doc)
        self.assertIn('--mono: "JetBrains Mono"', doc)
        self.assertIn("--paper: #1b1a17", doc)
        self.assertIn("prefers-color-scheme: dark", doc)
        self.assertTrue(any(tag == "style" for tag, _ in page.elements))
        self.assertTrue(any(tag == "script" for tag, _ in page.elements))
        self.assertFalse(any(tag == "link" or "src" in attrs
                             for tag, attrs in page.elements))


if __name__ == "__main__":
    unittest.main()
