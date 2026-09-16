import argparse
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from lkc_bench.cli import main, natural, parser, positive_int
from lkc_bench.diagnostic import DEFAULT_INPUTS
from lkc_bench.workspace import ROOT, PROBLEMS, lock


class CliTests(unittest.TestCase):
    def test_invalid_numeric_bounds(self):
        for value in ("0", "-1"):
            with self.assertRaises(argparse.ArgumentTypeError):
                positive_int(value)
        with self.assertRaises(argparse.ArgumentTypeError):
            natural("-1")
        self.assertEqual(natural("0"), 0)

    def test_baseline_only_and_diagnostic_defaults(self):
        args = parser().parse_args(["diagnostic", "--problem", "partition"])
        self.assertIsNone(args.submission)
        self.assertEqual(args.baseline, "example")
        self.assertEqual(args.repetitions, 3)
        self.assertEqual(args.metric, "wall-time")

    def test_all_problem_comparisons_parse(self):
        for problem in PROBLEMS:
            self.assertEqual(parser().parse_args(["compare", "--problem", problem]).problem, problem)

    def test_primecount_diagnostic_parse(self):
        args = parser().parse_args(["diagnostic", "--problem", "primecount"])
        self.assertEqual(args.problem, "primecount")
        self.assertIsNone(args.submission)

    def test_diagnostic_default_memory_inputs_and_explicit_overrides_reach_the_runner(self):
        for problem, options, memory, inputs in (
            ("permanent", [], 8192, DEFAULT_INPUTS["permanent"]),
            ("partition", [], 4096, DEFAULT_INPUTS["partition"]),
            ("ca-rule110", [], 4096, DEFAULT_INPUTS["ca-rule110"]),
            ("permanent", ["--memory-mb", "3072", "--inputs", "17179869186"], 3072, [17179869186]),
            ("ca-rule110", ["--memory-mb", "2048", "--inputs", "4294967297"], 2048, [4294967297]),
        ):
            with self.subTest(problem=problem, options=options), tempfile.TemporaryDirectory() as temporary:
                output = Path(temporary) / "run"
                with patch("lkc_bench.cli.sys.platform", "linux"), patch("lkc_bench.cli.runtime_environment"), \
                        patch("lkc_bench.cli.doctor", return_value={}), patch("sys.stdout", new_callable=io.StringIO), \
                        patch("lkc_bench.diagnostic.run_diagnostic", return_value={"complete": True}) as run:
                    status = main(["diagnostic", "--problem", problem, "--output", str(output), *options])
                self.assertEqual(status, 0)
                self.assertEqual(run.call_args.args[0].memory_mb, memory)
                self.assertEqual(run.call_args.args[0].inputs, inputs)
                manifest = json.loads((output / "run.json").read_text())
                self.assertEqual(manifest["options"]["memory_mb"], memory)
                self.assertEqual(manifest["options"]["inputs"], inputs)

    def test_lock_has_full_revisions(self):
        for field in ("revision", "comparator_revision", "lean4export_revision"):
            self.assertRegex(lock()[field], r"^[a-f0-9]{40}$")

    def test_publication_filter_rejects_sources_and_artifacts(self):
        spec = importlib.util.spec_from_file_location("release_check", ROOT / "scripts/check_release.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        for path in ("Submission.lean", "benchmarks/1-fib/Submission.lean", "results/report.json",
                     ".cache/upstream/README.md", "docs/private.txt", "tests/fixture.lean",
                     "benchmarks/1-fib/official/Candidate.lean", "benchmarks/unknown/official/Submission.lean",
                     "benchmarks/1-fib/selected/hardcoded/Submission.lean",
                     "benchmarks/4-primecount/selected/no-table/Submission.lean",
                     "benchmarks/4-primecount/selected/results.json", "candidates.lock.json"):
            self.assertFalse(module.allowed(path), path)
        for path in ("README.md", "benchmarks/1-fib/cases.json", "lkc_bench/cli.py",
                     "benchmarks/1-fib/official/Submission.lean", "third_party/lean-kernel-challenge/LICENSE"):
            self.assertTrue(module.allowed(path), path)


if __name__ == "__main__":
    unittest.main()
