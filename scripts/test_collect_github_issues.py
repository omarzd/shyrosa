#!/usr/bin/env python3
"""Tests for the Docker.raw board row (g28, shyrosa#51).

The contract under test is real disk blocks, not apparent size — a sparse scratch
file pins that a huge st_size alone must never trip the row.
"""
import os
import tempfile
import unittest

import collect_github_issues as cgi


class DockerDiskRowTests(unittest.TestCase):
    def test_sparse_file_with_huge_apparent_size_yields_no_row(self):
        with tempfile.NamedTemporaryFile() as fh:
            fh.truncate(100 * 1024**3)  # 100 GB apparent, ~0 real blocks
            self.assertIsNone(cgi.docker_disk_row(path=fh.name, threshold=1024))

    def test_small_real_file_over_tiny_threshold_yields_one_row(self):
        with tempfile.NamedTemporaryFile() as fh:
            fh.write(b"x" * 4096)
            fh.flush()
            row = cgi.docker_disk_row(path=fh.name, threshold=1024)
            self.assertIsNotNone(row)
            kind, text, md_ref, href = row
            self.assertEqual(kind, "row")
            self.assertIn("GB", text)
            self.assertIsNone(md_ref)
            self.assertIsNone(href)

    def test_missing_path_yields_no_row_and_no_error(self):
        missing = "/tmp/shyrosa-test-docker-raw-does-not-exist"
        self.assertFalse(os.path.exists(missing))
        self.assertIsNone(cgi.docker_disk_row(path=missing, threshold=1))

    def test_production_defaults(self):
        self.assertTrue(cgi.DOCKER_RAW_PATH.endswith(
            "Library/Containers/com.docker.docker/Data/vms/0/data/Docker.raw"
        ))
        self.assertEqual(cgi.DOCKER_RAW_THRESHOLD, 40 * 1024**3)


if __name__ == "__main__":
    unittest.main()
