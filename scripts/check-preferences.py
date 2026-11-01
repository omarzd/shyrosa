#!/usr/bin/env python3
"""PreToolUse Bash guard for the effective Python-install preference (#140).

Inspect plain installs joined by &&, || or ; without executing them. Uncertain
shell syntax and unknown installer options pass unjudged, per #140's director
rulings. Full paths, aliases and scripts are outside the guard. Errors fail open.
"""
import json
from pathlib import Path
import shlex
import sys

INSTALL_COMMANDS = {
    ("pip", "install"): "pip-venv",
    ("pip3", "install"): "pip-venv",
    ("python", "-m", "pip", "install"): "pip-venv",
    ("python3", "-m", "pip", "install"): "pip-venv",
    ("uv", "pip", "install"): "uv",
    ("uv", "add"): "uv",
    ("uv", "sync"): "uv",
    ("conda", "install"): "conda-forge",
    ("mamba", "install"): "conda-forge",
    ("pixi", "add"): "pixi",
    ("pixi", "install"): "pixi",
}
PREFERRED_COMMANDS = {
    "conda-forge": ("conda", "install", "-c", "conda-forge"),
    "uv": ("uv", "add"),
    "pixi": ("pixi", "add"),
    "pip-venv": ("python3", "-m", "pip", "install"),
}
PROJECT_FILES = {
    "uv": ("uv.lock",),
    "conda-forge": ("environment.yml",),
    "pixi": ("pixi.toml", "pixi.lock"),
}
VALUE_FREE_FLAGS = {
    "-q", "--quiet", "-U", "--upgrade", "--user", "--no-cache-dir",
    "-y", "--yes", "--dry-run", "-v", "--verbose",
}


def simple_commands(command):
    if any(part in command for part in ("\n", "\r", "$(", "${", "`", "\\")):
        return []
    # Non-POSIX mode keeps quotes so echo '|' cannot look like a pipeline.
    lexer = shlex.shlex(command, posix=False, punctuation_chars=";&|<>#()")
    lexer.whitespace_split = True
    lexer.commenters = ""
    commands = []
    words = []
    end = 0
    previous_word = False
    for token in lexer:
        start = command.find(token, end)
        if start < 0:
            return []
        if token[0] in ";&|<>#()":
            if token not in ("&&", "||", ";") or not words:
                return []
            commands.append(words)
            words = []
            previous_word = False
        else:
            if previous_word and start == end:
                return []  # adjacent quoted fragments require more shell parsing
            if any(quote in token for quote in "\"'") and token[0] not in "\"'":
                return []
            decoded = shlex.split(token)
            if len(decoded) != 1:
                return []
            words.extend(decoded)
            previous_word = True
        end = start + len(token)
    if not words:
        return []
    commands.append(words)
    return commands


def installation(words):
    for prefix, group in INSTALL_COMMANDS.items():
        if tuple(words[:len(prefix)]) == prefix:
            return group, words[len(prefix):]
    return None


def main():
    try:
        from preferences import find_tool, load

        payload = json.load(sys.stdin)
        if payload.get("tool_name") != "Bash":
            return 0
        commands = simple_commands(payload["tool_input"]["command"])
        preferred = load().get("claude", {}).get("python_install")
        if preferred not in PREFERRED_COMMANDS:
            return 0
        tool = "pip" if preferred == "pip-venv" else PREFERRED_COMMANDS[preferred][0]
        if not find_tool(tool):
            return 0
        project = Path(payload["cwd"])
        conflict = False
        seen_cd = False
        for words in commands:
            if words[:1] in (["cd"], ["pushd"], ["popd"]) or words[:2] == ["builtin", "cd"]:
                seen_cd = True
            install = installation(words)
            if install is None:
                continue
            group, arguments = install
            if seen_cd or any(argument.startswith("-") and argument not in VALUE_FREE_FLAGS
                              for argument in arguments):
                return 0
            declared = any((project / name).is_file() for name in PROJECT_FILES.get(group, ()))
            if group != preferred and not declared:
                conflict = True
        if not conflict:
            return 0
        replacement = shlex.join(PREFERRED_COMMANDS[preferred]) + " <packages>"
        if preferred == "pip-venv":
            replacement += " inside a venv"
    except Exception:
        return 0  # a broken guard must not freeze the machine
    print(f"Use {replacement} instead.", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
