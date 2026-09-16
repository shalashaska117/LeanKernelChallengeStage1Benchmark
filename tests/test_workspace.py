"""Offline setup recovery and provenance checks using temporary Git repositories."""

import hashlib
from contextlib import ExitStack
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from lkc_bench import workspace


@unittest.skipUnless(shutil.which("git"), "setup tests require Git")
class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="lkc-workspace-test-")
        self.addCleanup(self.temporary.cleanup)
        self.contexts = ExitStack()
        self.addCleanup(self.contexts.close)
        directory = Path(self.temporary.name).resolve()
        self.root = directory / "benchmark"
        self.root.mkdir()
        self.origin = directory / "origin"
        self.origin.mkdir()
        self.cache = self.root / ".cache"
        self.upstream = self.cache / "upstream"
        self.contexts.enter_context(patch.dict(os.environ, {
            "GIT_ALLOW_PROTOCOL": "file", "GIT_TERMINAL_PROMPT": "0",
            "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_COUNT": "0",
        }))
        self._git(self.origin, "init", "--quiet")
        self._git(self.origin, "config", "user.name", "Benchmark tests")
        self._git(self.origin, "config", "user.email", "benchmark-tests@example.invalid")
        self._git(self.origin, "config", "core.autocrlf", "false")
        self.pins = {
            "repository": self.origin.as_uri(), "lean": "leanprover/lean4:v4.33.1",
            "comparator_revision": "a" * 40, "lean4export_revision": "b" * 40,
        }
        evaluation = self.origin / "evaluation"
        evaluation.mkdir()
        (evaluation / "config.json").write_text(json.dumps({"toolchain": {
            "lean": self.pins["lean"], "comparator_rev": self.pins["comparator_revision"],
            "lean4export_rev": self.pins["lean4export_revision"],
        }}) + "\n", encoding="utf-8")
        (self.origin / "README.md").write_text("Synthetic upstream fixture.\n", encoding="utf-8")
        self.references = {"baselines": {}}
        for problem in workspace.PROBLEMS:
            self.references["baselines"][problem] = {}
            for role, folder in (("example", "examples"), ("starter", "problems")):
                relative = f"{folder}/{problem}/Submission.lean"
                target = self.origin / relative
                target.parent.mkdir(parents=True)
                # These are arbitrary test bytes, not Lean definitions or proofs.
                data = f"synthetic {role} bytes for {problem}\n".encode("utf-8")
                target.write_bytes(data)
                self.references["baselines"][problem][role] = {
                    "path": relative, "sha256": hashlib.sha256(data).hexdigest(),
                }
                if role == "example":
                    bundled = f"benchmarks/{workspace.BENCHMARK_DIRS[problem]}/official/Submission.lean"
                    self.references["baselines"][problem][role]["bundled_path"] = bundled
                    destination = self.root / bundled
                    destination.parent.mkdir(parents=True)
                    destination.write_bytes(data)
        self._git(self.origin, "add", ".")
        self._git(self.origin, "-c", "commit.gpgsign=false", "commit", "--quiet", "-m", "Add synthetic upstream fixture")
        self.pins["revision"] = self._git(self.origin, "rev-parse", "HEAD")
        self.references["upstream_revision"] = self.pins["revision"]
        (self.root / "upstream.lock.json").write_text(json.dumps(self.pins), encoding="utf-8")
        self._write_references()
        for name, value in (("ROOT", self.root), ("CACHE", self.cache),
                            ("UPSTREAM", self.upstream), ("TOOLS", self.cache / "repro")):
            self.contexts.enter_context(patch.object(workspace, name, value))
        # Fetch-only setup has no platform-specific build steps.
        self.contexts.enter_context(patch.object(workspace, "require_platform"))

    def _git(self, directory, *arguments):
        return subprocess.run(["git", "-C", str(directory), *arguments], check=True,
                              capture_output=True, text=True).stdout.strip()

    def _write_references(self):
        (self.root / "baselines.lock.json").write_text(json.dumps(self.references), encoding="utf-8")

    def _setup(self):
        workspace.setup(["partition"], fetch_only=True)

    def test_interrupted_initial_fetch_resumes_without_network(self):
        real_run = subprocess.run
        attempts = []

        def interrupt_first_fetch(command, *args, **kwargs):
            if command[0] == "git" and "fetch" in command:
                attempts.append(command)
                if len(attempts) == 1:
                    raise subprocess.CalledProcessError(128, command, stderr="simulated interrupted fetch")
            return real_run(command, *args, **kwargs)

        with patch.object(workspace.subprocess, "run", side_effect=interrupt_first_fetch):
            with self.assertRaises(subprocess.CalledProcessError):
                self._setup()
            self.assertTrue((self.upstream / ".git").is_dir())
            self._setup()
        self.assertEqual(len(attempts), 2)
        self.assertEqual(self._git(self.upstream, "rev-parse", "HEAD"), self.pins["revision"])
        self.assertEqual(workspace.validate_upstream()["revision"], self.pins["revision"])

    def test_setup_preserves_dirty_tracked_files(self):
        self._setup()
        document = self.upstream / "README.md"
        document.write_text("Local edits to preserve.\n", encoding="utf-8")
        with self.assertRaisesRegex(RuntimeError, "Tracked files"):
            self._setup()
        self.assertEqual(document.read_text(), "Local edits to preserve.\n")
        self.assertEqual(self._git(self.upstream, "rev-parse", "HEAD"), self.pins["revision"])

    def test_setup_preserves_a_different_existing_revision(self):
        self._setup()
        document = self.upstream / "README.md"
        document.write_text("Another local revision.\n", encoding="utf-8")
        self._git(self.upstream, "add", "README.md")
        self._git(self.upstream, "-c", "user.name=Benchmark tests", "-c", "user.email=benchmark-tests@example.invalid",
                  "-c", "commit.gpgsign=false", "commit", "--quiet", "-m", "Change synthetic upstream fixture")
        local_revision = self._git(self.upstream, "rev-parse", "HEAD")
        with self.assertRaisesRegex(RuntimeError, "revision mismatch"):
            self._setup()
        self.assertEqual(self._git(self.upstream, "rev-parse", "HEAD"), local_revision)
        self.assertEqual(document.read_text(), "Another local revision.\n")

    def test_modified_baseline_is_detected_even_if_git_ignores_its_stat(self):
        self._setup()
        relative = "examples/partition/Submission.lean"
        baseline = self.upstream / relative
        self._git(self.upstream, "update-index", "--assume-unchanged", relative)
        baseline.write_bytes(b"different synthetic baseline bytes\n")
        self.assertEqual(self._git(self.upstream, "status", "--porcelain", "--untracked-files=no"), "")
        with self.assertRaisesRegex(RuntimeError, "baseline hash mismatch"):
            workspace.validate_upstream()
        self.assertEqual(baseline.read_bytes(), b"different synthetic baseline bytes\n")

    def test_baseline_pins_must_match_revision_hash_and_public_path(self):
        self._setup()
        original = json.loads(json.dumps(self.references))
        mutations = (
            ("different upstream revision", lambda: self.references.update(upstream_revision="f" * 40)),
            ("hash mismatch", lambda: self.references["baselines"]["partition"]["example"].update(sha256="0" * 64)),
            ("hash mismatch", lambda: self.references["baselines"]["partition"]["starter"].update(path="../outside")),
        )
        for message, change in mutations:
            with self.subTest(message=message):
                self.references = json.loads(json.dumps(original))
                change()
                self._write_references()
                with self.assertRaisesRegex(RuntimeError, message):
                    workspace.validate_upstream()

    def test_retry_preserves_files_in_an_unfinished_checkout(self):
        workspace._managed_cache()
        self.upstream.mkdir()
        self._git(self.upstream, "init", "--quiet")
        local_file = self.upstream / "work-in-progress.txt"
        local_file.write_text("Preserve this file.\n", encoding="utf-8")
        with self.assertRaisesRegex(RuntimeError, "unfinished upstream checkout contains files"):
            self._setup()
        self.assertEqual(local_file.read_text(), "Preserve this file.\n")

    def test_bundled_example_is_checked_and_selected_without_a_cache(self):
        expected = self.root / "benchmarks/2-partition/official/Submission.lean"
        self.assertFalse(self.upstream.exists())
        self.assertEqual(workspace.official_baseline("partition"), expected)
        expected.write_bytes(b"unapproved replacement\n")
        with self.assertRaisesRegex(RuntimeError, "Bundled official baseline hash mismatch"):
            workspace.official_baseline("partition")

    def test_bundled_path_must_be_the_exact_problem_path(self):
        self.references["baselines"]["partition"]["example"]["bundled_path"] = "../outside"
        self._write_references()
        with self.assertRaisesRegex(RuntimeError, "Bundled official baseline hash mismatch"):
            workspace.official_baseline("partition")

    def test_setup_refuses_a_changed_origin(self):
        self._setup()
        different_origin = (self.origin.parent / "different-origin").as_uri()
        self._git(self.upstream, "remote", "set-url", "origin", different_origin)
        with self.assertRaisesRegex(RuntimeError, "remote does not match"):
            self._setup()
        self.assertEqual(self._git(self.upstream, "remote", "get-url", "origin"), different_origin)
        self.assertEqual(self._git(self.upstream, "rev-parse", "HEAD"), self.pins["revision"])

    def test_setup_preserves_an_unmanaged_cache(self):
        self.cache.mkdir()
        local_file = self.cache / "existing.txt"
        local_file.write_text("Unmanaged contents.\n", encoding="utf-8")
        with self.assertRaisesRegex(RuntimeError, "not managed"):
            self._setup()
        self.assertEqual(local_file.read_text(), "Unmanaged contents.\n")
        self.assertFalse((self.cache / ".benchmark-managed").exists())


class RuntimeEnvironmentTests(unittest.TestCase):
    def test_local_configuration_replaces_judge_overrides_and_keeps_host_paths(self):
        discarded = {
            "OFFICIAL_EVAL": "1", "DEFER_TIMING": "1", "PERF_COUNT": "1", "PERF_SEED": "synthetic-seed",
            "EVALUATION_COHORT": "another-cohort", "EVALUATION_RUN_ID": "another-run",
            "TIMING_EXECUTOR_URLS": "https://example.invalid", "TIMING_TIMEOUT_SECONDS": "1",
            "SAIR_PROGRESS_FILE": "unused-progress-file", "SANDBOX_MODE": "container", "SHIM_DIR": "other-shims",
            "ISOLATION_ATTESTATION": "synthetic", "LEAN_PATH": "other-libraries", "LEAN_SRC_PATH": "other-sources",
            "LEAN_SYSROOT": "other-runtime", "ELAN_TOOLCHAIN": "other-toolchain", "COMPARATOR_LEAN4EXPORT": "other-exporter",
        }
        preserved = {"PATH": "host-path", "HOME": "host-home", "ELAN_HOME": "host-elan", "BENCHMARK_SENTINEL": "keep"}
        replaced = {"TIMING_METRIC": "perf_instructions", "LEAN_NUM_THREADS": "8", "COMPARATOR_BIN": "other-comparator",
                    "LEAN4EXPORT_BIN": "other-exporter-directory", "TIMER_BIN": "other-timer"}
        with patch.dict(os.environ, {**discarded, **preserved, **replaced}, clear=True):
            workspace.runtime_environment()
            for name in discarded:
                self.assertNotIn(name, os.environ, name)
            for name, value in preserved.items():
                self.assertEqual(os.environ[name], value)
            self.assertEqual(os.environ["TIMING_METRIC"], "wall_time")
            self.assertEqual(os.environ["LEAN_NUM_THREADS"], "1")
            for name, path in workspace.tool_paths().items():
                self.assertEqual(os.environ[name], str(path))


if __name__ == "__main__":
    unittest.main()
