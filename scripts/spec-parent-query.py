#!/usr/bin/env python3
"""List open GitHub issues naming a spec in their Parent section; never close one."""
import argparse
from html.parser import HTMLParser
import json
import re
import subprocess
import sys
from urllib.parse import urlsplit


class ParentHTML(HTMLParser):
    """Traverse GitHub's rendered headings and links, suppressing link-label identity."""

    def __init__(self, spec, repo, alias):
        super().__init__(convert_charrefs=True)
        self.spec = spec
        self.repo = repo.lower()
        self.local_names = {self.repo, self.repo.rsplit("/", 1)[-1]}
        if alias:
            self.local_names.add(alias.lower())
        self.reference = re.compile(
            rf"https://github\.com/(?P<url_repo>[^/\s]+/[^/\s]+)/issues/{spec}(?!\w)"
            rf"|(?<![\w/])(?P<qualifier>[\w.-]+(?:/[\w.-]+)?)?#{spec}(?!\w)")
        self.in_parent = False
        self.heading = None
        self.heading_text = []
        self.text = []
        self.pre_depth = self.link_depth = self.quote_depth = 0
        self.found = self.saw_tag = self.has_content = False

    def flush_text(self):
        for match in self.reference.finditer("".join(self.text)):
            if match["url_repo"]:
                self.found |= match["url_repo"].lower() == self.repo
            else:
                self.found |= not match["qualifier"] or match["qualifier"].lower() in self.local_names
        self.text.clear()

    def handle_starttag(self, tag, attrs):
        self.saw_tag = True
        self.has_content |= tag in {"img", "hr", "pre", "input"}
        if tag == "pre":
            self.flush_text()
            self.pre_depth += 1
        if self.pre_depth:
            return
        if tag == "blockquote":
            self.flush_text()
            self.quote_depth += 1
        elif tag in {"h1", "h2"} and not self.quote_depth:
            self.flush_text()
            self.in_parent = False
            self.heading, self.heading_text = tag, []
        elif tag == "a":
            self.flush_text()
            self.link_depth += 1
            if self.in_parent and self.heading is None:
                url = urlsplit(dict(attrs).get("href") or "")
                self.found |= (url.scheme in {"http", "https"}
                               and url.netloc.lower() == "github.com"
                               and url.path.rstrip("/").lower() == f"/{self.repo}/issues/{self.spec}")
        elif tag in {"p", "div", "li", "ul", "ol", "br", "hr", "table", "tr", "td", "h1", "h2", "h3", "h4", "h5", "h6"}:
            self.flush_text()

    def handle_endtag(self, tag):
        if self.pre_depth:
            if tag == "pre":
                self.pre_depth -= 1
            return
        if tag == "blockquote":
            self.flush_text()
            self.quote_depth = max(0, self.quote_depth - 1)
        elif tag == self.heading:
            self.in_parent = tag == "h2" and " ".join("".join(self.heading_text).split()) == "Parent"
            self.heading = None
        elif tag == "a":
            self.link_depth = max(0, self.link_depth - 1)
        elif tag in {"p", "div", "li", "ul", "ol", "table", "tr", "td", "h1", "h2", "h3", "h4", "h5", "h6"}:
            self.flush_text()

    def handle_data(self, data):
        self.has_content |= bool(data.strip())
        if self.pre_depth:
            return
        if self.heading:
            self.heading_text.append(data)
        elif self.in_parent and not self.link_depth:
            self.text.append(data)


def parent_names(issue, spec, repo, alias):
    rendered = issue.get("body_html")
    if rendered is None or rendered == "":
        if not (issue.get("body") or "").strip():
            return False
        raise ValueError(f'issue {issue["number"]} has no rendered body')
    if not isinstance(rendered, str):
        raise ValueError(f'issue {issue["number"]} has an invalid rendered body')
    parser = ParentHTML(spec, repo, alias)
    parser.feed(rendered)
    parser.close()
    parser.flush_text()
    if (not parser.saw_tag or not parser.has_content or parser.heading
            or parser.pre_depth or parser.link_depth or parser.quote_depth):
        raise ValueError(f'issue {issue["number"]} has an unusable rendered body')
    return parser.found


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True, help="owner/repository holding the tickets")
    parser.add_argument("--spec", required=True, type=int, help="spec issue number")
    parser.add_argument("--alias", help="project shorthand when tickets use a separate tracker")
    args = parser.parse_args()
    if args.spec < 1:
        parser.error("--spec must be positive")
    try:
        result = subprocess.run(
            ["gh", "api", "--paginate", "--slurp", "-H", "Accept: application/vnd.github.full+json",
             f"repos/{args.repo}/issues?state=open&per_page=100"],
            check=True, capture_output=True, text=True, encoding="utf-8")
        pages = json.loads(result.stdout)
        matches = [issue for page in pages for issue in page
                   if "pull_request" not in issue
                   and parent_names(issue, args.spec, args.repo, args.alias)]
    except (OSError, subprocess.CalledProcessError, ValueError) as exc:
        print(f"Spec Parent query failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(matches))
    return 0


if __name__ == "__main__":
    sys.exit(main())
