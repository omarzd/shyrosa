#!/usr/bin/env python3
"""Optionally choose Claude preferences for this copy of shyrosa (#141)."""
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

from preferences import PYTHON_INSTALL_CHOICES, read_file


FIELDS = (
    ("python_install", "Python package install (" + ", ".join(PYTHON_INSTALL_CHOICES) + ")"),
    ("environment_manager", "Environment manager"),
    ("python", "Python interpreter"),
)


def read_document(path):
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
    if not isinstance(document, dict):
        raise ValueError(f"{path}: expected a JSON object")
    return document


def ask(label, current, inherited=None, choices=None):
    default = current or (f"inherit: {inherited}" if inherited else "none")
    while True:
        answer = input(f"{label} [{default}]: ").strip()
        if not answer:
            return current
        if answer == "-":
            return None
        if choices is None or answer in choices:
            return answer
        print("Choose one of: " + ", ".join(choices) + ".")


def write_document(path, document):
    if read_document(path) == document:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent,
            prefix=f".{path.name}.", delete=False,
        ) as output:
            temporary = Path(output.name)
            json.dump(document, output, indent=2)
            output.write("\n")
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main():
    root = Path(__file__).resolve().parent.parent
    saving = False
    try:
        kind = subprocess.run(
            ["uname", "-s"], check=True, capture_output=True, text=True, timeout=10,
        ).stdout.strip().lower()
        if not re.fullmatch(r"[a-z][a-z0-9_-]*", kind):
            raise ValueError("uname -s did not return an operating system kind")
        user_path = root / "fleet/preferences/user.json"
        machine_path = root / "fleet/preferences/machines" / f"{kind}.json"
        settings_path = root / "fleet/settings.json"
        user_values = read_file(user_path)
        machine_values = read_file(machine_path)
        user = read_document(user_path)
        machine = read_document(machine_path)
        settings = read_document(settings_path)
        if "model" in settings and (
            not isinstance(settings["model"], str) or not settings["model"].strip()
        ):
            raise ValueError(f"{settings_path}: model must be a non-empty string")

        print("Optional Claude preferences. Enter keeps the current value; - clears it.")
        print("Machine choices override user choices for the detected OS only.")
        print("Enter tool names and a model only. Keep API keys and secrets out of these files.")
        for key, label in FIELDS:
            choices = PYTHON_INSTALL_CHOICES if key == "python_install" else None
            value = ask(f"User: {label}", user_values.get(key), choices=choices)
            if value is None:
                user_values.pop(key, None)
            else:
                user_values[key] = value
        for key, label in FIELDS:
            choices = PYTHON_INSTALL_CHOICES if key == "python_install" else None
            value = ask(f"{kind}: {label}", machine_values.get(key), user_values.get(key), choices)
            if value is None:
                machine_values.pop(key, None)
            else:
                machine_values[key] = value
        model = ask("Claude model", settings.get("model"))

        saving = True
        if user_values or "claude" in user or not user_path.exists():
            user["claude"] = user_values
        write_document(user_path, user)
        if machine_values or machine_path.exists():
            if machine_values or "claude" in machine:
                machine["claude"] = machine_values
            write_document(machine_path, machine)
        settings = read_document(settings_path)
        if model is None:
            settings.pop("model", None)
        else:
            settings["model"] = model
        write_document(settings_path, settings)
    except (EOFError, KeyboardInterrupt):
        message = ("Setup interrupted while saving. Some files may have changed."
                   if saving else "Setup cancelled. No files changed.")
        print("\n" + message, file=sys.stderr)
        return 1
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        print(f"Setup preferences: {exc}", file=sys.stderr)
        return 2
    print("Preferences saved in this checkout.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
