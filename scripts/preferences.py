#!/usr/bin/env python3
"""Print or brief the Claude preferences in effect in this copy of shyrosa (#136, #138, #139)."""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys


PYTHON_INSTALL_CHOICES = ("conda-forge", "uv", "pip-venv", "pixi")
CLAUDE_KEYS = {"python_install", "environment_manager", "python"}

# Missing-tool commands agreed in #138's 2026-10-30 director ruling. These are text only.
INSTALL_METHODS = {
    "conda-forge": (
        ("conda", "mamba"), "conda from conda-forge", "{tool} install -c conda-forge <package>",
        {"darwin": "brew install --cask miniforge",
         "linux": "curl -L -O https://github.com/conda-forge/miniforge/releases/latest/"
                  "download/Miniforge3-$(uname)-$(uname -m).sh && "
                  "bash Miniforge3-$(uname)-$(uname -m).sh"},
    ),
    "uv": (
        ("uv",), "uv", "uv pip install <package>",
        {"darwin": "brew install uv", "linux": "curl -LsSf https://astral.sh/uv/install.sh | sh"},
    ),
    "pixi": (
        ("pixi",), "pixi", "pixi add <package>",
        {"darwin": "brew install pixi", "linux": "curl -fsSL https://pixi.sh/install.sh | sh"},
    ),
    "pip-venv": (
        ("python3",), "pip with a venv", "python3 -m pip install <package> inside a venv",
        {"darwin": "brew install python", "linux": "sudo apt install python3 python3-venv"},
    ),
}


def read_file(path):
    """Read the active harness's choices; omitted files and keys set no preference."""
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {}
    except UnicodeError as exc:
        raise ValueError(f"{path}: expected UTF-8 JSON") from exc
    try:
        document = json.loads(text)
    except ValueError as exc:
        raise ValueError(f"{path}: invalid JSON") from exc
    if not isinstance(document, dict) or not isinstance(document.get("claude", {}), dict):
        raise ValueError(f"{path}: expected a JSON object with a claude object")
    values = document.get("claude", {})
    if values.keys() - CLAUDE_KEYS:
        raise ValueError(f"{path}: supported claude keys: " + ", ".join(sorted(CLAUDE_KEYS)))
    if "python_install" in values and values["python_install"] not in PYTHON_INSTALL_CHOICES:
        raise ValueError(
            f"{path}: claude.python_install must be one of "
            + ", ".join(PYTHON_INSTALL_CHOICES)
            + " (conda from conda-forge, uv, pip with a venv, or pixi)"
        )
    for key, value in values.items():
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{path}: claude.{key} must be a non-empty string")
    return values


def machine_kind():
    kind = subprocess.run(
        ["uname", "-s"], check=True, capture_output=True, text=True, timeout=10,
    ).stdout.strip().lower()
    if not re.fullmatch(r"[a-z][a-z0-9_-]*", kind):
        raise ValueError("uname -s did not return an operating system kind")
    return kind


def load():
    """Read preferences from this module's checkout, independently of the caller's cwd."""
    directory = Path(__file__).resolve().parent.parent / "fleet/preferences"
    kind = machine_kind()
    effective = {}
    for path in (directory / "user.json", directory / "machines" / f"{kind}.json"):
        effective.update(read_file(path))
    return {"claude": effective} if effective else {}


def find_tool(tool):
    """Return an executable path, or None, without invoking the tool."""
    installed = shutil.which(tool)
    if installed:
        return installed
    candidates = []
    if tool in ("conda", "mamba"):
        configured = os.environ.get("CONDA_EXE" if tool == "conda" else "MAMBA_EXE")
        if configured:
            candidates.append(Path(configured))
        bases = [Path.home() / base
                 for base in ("miniforge3", "mambaforge", "miniconda3", "anaconda3")]
        bases.extend(Path(base) for base in (
            "/opt/homebrew/Caskroom/miniforge/base", "/opt/miniconda3", "/opt/conda",
        ))
        candidates.extend(base / folder / tool for base in bases for folder in ("bin", "condabin"))
    elif tool in ("uv", "pixi"):
        candidates.extend(Path.home() / folder / tool
                          for folder in (".local/bin", ".cargo/bin", ".pixi/bin"))
    for candidate in candidates:
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return str(candidate)
    return None


def briefing(effective):
    """Describe the effective choices for the agent without changing the machine."""
    if not effective:
        return "No preferences are set."
    values = effective["claude"]
    lines = []
    missing = {}
    if "python_install" in values:
        tools, description, usage, installers = INSTALL_METHODS[values["python_install"]]
        installed = next((tool for tool in tools if find_tool(tool)), None)
        command = usage.format(tool=installed or tools[0])
        lines.append(f"Python packages: {description}; use {command}.")
        if installed is None:
            missing[tools[0]] = installers.get(machine_kind())
    for key, label in (("environment_manager", "Environment manager"),
                       ("python", "Python interpreter")):
        if key in values:
            tool = values[key]
            lines.append(f"{label}: {tool}.")
            if not find_tool(tool):
                missing.setdefault(tool, None)
    for tool, installer in missing.items():
        line = f"{tool} is not on PATH."
        if installer:
            line += f" To install it, run: {installer}"
        lines.append(line)
    return "\n".join(lines)


def model_drift_notice():
    """Compare saved and committed fleet models without rewriting either one."""
    root = Path(__file__).resolve().parent.parent
    try:
        saved = json.loads((root / "fleet/settings.json").read_text(encoding="utf-8"))
        committed = json.loads(subprocess.run(
            ["git", "show", "HEAD:fleet/settings.json"], cwd=root, check=True,
            capture_output=True, text=True, encoding="utf-8", timeout=2,
        ).stdout)
    except (OSError, ValueError, subprocess.SubprocessError):
        return ""
    if not isinstance(saved, dict) or not isinstance(committed, dict):
        return ""
    saved_model, committed_model = saved.get("model"), committed.get("model")
    if not isinstance(committed_model, str):
        return ""
    if "model" not in saved:
        saved_description = "has no model line"
    elif isinstance(saved_model, str) and saved_model != committed_model:
        saved_description = f"says {json.dumps(saved_model)}"
    else:
        return ""
    committed_value = json.dumps(committed_model)
    return (f"Claude model: fleet/settings.json {saved_description} but git has {committed_value}. "
            f"Ask the person whether to keep the change or put {committed_value} back; "
            "do not change it yourself.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--print", action="store_true", help="print the effective preferences (default)")
    modes.add_argument("--brief", action="store_true", help="brief the agent at session start")
    args = parser.parse_args()
    try:
        effective = load()
        output = briefing(effective) if args.brief else (
            json.dumps(effective, indent=2, sort_keys=True) if effective else "No preferences are set."
        )
        if args.brief:
            notice = model_drift_notice()
            if notice:
                output += "\n" + notice
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        if args.brief:
            print(f"Preferences: {exc}")
            return 0
        print(f"Preferences: {exc}", file=sys.stderr)
        return 2
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
