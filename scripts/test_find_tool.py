#!/usr/bin/env python3
"""Test the shared finder seam agreed for #138 fix round 2 and #140."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import preferences


class FindTool(unittest.TestCase):
    def setUp(self):
        scratch = tempfile.TemporaryDirectory(prefix="shyrosa-find-tool-")
        self.addCleanup(scratch.cleanup)
        self.scratch = Path(scratch.name)
        self.home = self.scratch / "home"
        self.home.mkdir()
        self.bin = self.scratch / "bin"
        self.bin.mkdir()
        environment = mock.patch.dict(os.environ, {"HOME": str(self.home), "PATH": str(self.bin)},
                                      clear=True)
        environment.start()
        self.addCleanup(environment.stop)
        # Only /opt checks are synthetic; HOME and PATH use real scratch files.
        self.system_tools = set()
        real_isfile, real_access = os.path.isfile, os.access

        def isfile(path):
            if str(path).startswith("/opt/"):
                return str(path) in self.system_tools
            return real_isfile(path)

        def access(path, mode):
            if str(path).startswith("/opt/"):
                return str(path) in self.system_tools
            return real_access(path, mode)

        for patcher in (mock.patch("os.path.isfile", side_effect=isfile),
                        mock.patch("os.access", side_effect=access)):
            patcher.start()
            self.addCleanup(patcher.stop)

    def program(self, path):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('#!/bin/sh\nprintf invoked >> "$HOME/tool-invocations"\nexit 99\n')
        path.chmod(0o755)
        return str(path)

    def test_path_then_matching_environment_variable_then_home_first_hit_wins(self):
        for tool, variable in (("conda", "CONDA_EXE"), ("mamba", "MAMBA_EXE")):
            with self.subTest(tool=tool):
                on_path = self.bin / tool
                configured = self.scratch / "custom" / tool
                home_install = self.home / "miniforge3/bin" / tool
                self.program(on_path)
                self.program(configured)
                self.program(home_install)
                os.environ[variable] = str(configured)
                self.assertEqual(preferences.find_tool(tool), str(on_path))
                on_path.unlink()
                self.assertEqual(preferences.find_tool(tool), str(configured))
                configured.unlink()
                self.assertEqual(preferences.find_tool(tool), str(home_install))
                os.environ.pop(variable)

    def test_all_conda_home_locations_before_system_locations_in_the_agreed_order(self):
        for tool in ("conda", "mamba"):
            with self.subTest(tool=tool):
                homes = [self.home / base / folder / tool
                         for base in ("miniforge3", "mambaforge", "miniconda3", "anaconda3")
                         for folder in ("bin", "condabin")]
                systems = [f"{base}/{folder}/{tool}"
                           for base in ("/opt/homebrew/Caskroom/miniforge/base",
                                        "/opt/miniconda3", "/opt/conda")
                           for folder in ("bin", "condabin")]
                for path in homes:
                    self.program(path)
                self.system_tools.update(systems)
                for path in homes:
                    self.assertEqual(preferences.find_tool(tool), str(path))
                    path.unlink()
                for path in systems:
                    self.assertEqual(preferences.find_tool(tool), path)
                    self.system_tools.remove(path)
                self.assertIsNone(preferences.find_tool(tool))

    def test_uv_and_pixi_path_then_all_home_locations_in_the_agreed_order(self):
        for tool in ("uv", "pixi"):
            with self.subTest(tool=tool):
                paths = [self.bin / tool] + [self.home / folder / tool
                                            for folder in (".local/bin", ".cargo/bin", ".pixi/bin")]
                for path in paths:
                    self.program(path)
                for path in paths:
                    self.assertEqual(preferences.find_tool(tool), str(path))
                    path.unlink()
                self.assertIsNone(preferences.find_tool(tool))

    def test_missing_nonexecutable_and_directory_candidates_are_skipped(self):
        for tool, variable in (("conda", "CONDA_EXE"), ("mamba", "MAMBA_EXE")):
            with self.subTest(tool=tool):
                configured = self.scratch / "configured" / tool
                os.environ[variable] = str(configured)
                first = self.home / "miniforge3/bin" / tool
                fallback = self.home / "miniforge3/condabin" / tool
                self.program(first)
                self.program(fallback)
                self.assertEqual(preferences.find_tool(tool), str(first))
                self.program(configured)
                configured.chmod(0o600)
                first.chmod(0o600)
                self.assertEqual(preferences.find_tool(tool), str(fallback))
                configured.unlink()
                configured.mkdir()
                self.assertEqual(preferences.find_tool(tool), str(fallback))
                fallback.unlink()
                self.assertIsNone(preferences.find_tool(tool))
                os.environ.pop(variable)

    def test_conda_and_mamba_use_only_their_own_environment_variable(self):
        configured = self.scratch / "configured-conda"
        self.program(configured)
        os.environ["CONDA_EXE"] = str(configured)
        self.assertEqual(preferences.find_tool("conda"), str(configured))
        self.assertIsNone(preferences.find_tool("mamba"))
        os.environ.pop("CONDA_EXE")
        os.environ["MAMBA_EXE"] = str(configured)
        self.assertEqual(preferences.find_tool("mamba"), str(configured))
        self.assertIsNone(preferences.find_tool("conda"))

    def test_other_command_names_keep_path_lookup_including_explicit_paths(self):
        self.program(self.home / ".local/bin/custom-python")
        self.assertIsNone(preferences.find_tool("custom-python"))
        command = self.bin / "custom-python"
        self.program(command)
        self.assertEqual(preferences.find_tool("custom-python"), str(command))
        self.assertEqual(preferences.find_tool(str(command)), str(command))

    def test_discovery_does_not_execute_tools_or_change_files(self):
        for tool, location in (("conda", "miniforge3/bin"), ("mamba", "mambaforge/condabin"),
                               ("uv", ".cargo/bin"), ("pixi", ".pixi/bin")):
            self.program(self.home / location / tool)
        before = {p.relative_to(self.scratch): p.read_bytes()
                  for p in self.scratch.rglob("*") if p.is_file()}
        for tool in ("conda", "mamba", "uv", "pixi"):
            self.assertIsNotNone(preferences.find_tool(tool))
        after = {p.relative_to(self.scratch): p.read_bytes()
                 for p in self.scratch.rglob("*") if p.is_file()}
        self.assertEqual(after, before)


if __name__ == "__main__":
    unittest.main()
