import argparse
import importlib.util
from pathlib import Path
import unittest

from lkc_bench.cli import natural, parser, positive_int
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

    def test_lock_has_full_revisions(self):
        for field in ("revision", "comparator_revision", "lean4export_revision"):
            self.assertRegex(lock()[field], r"^[a-f0-9]{40}$")

    def test_publication_filter_rejects_sources_and_artifacts(self):
        spec = importlib.util.spec_from_file_location("release_check", ROOT / "scripts/check_release.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        for path in ("Submission.lean", "benchmarks/fib/Submission.lean", "results/report.json",
                     ".cache/upstream/README.md", "docs/private.txt", "tests/fixture.lean",
                     "benchmarks/fib/official/Candidate.lean", "benchmarks/unknown/official/Submission.lean",
                     "benchmarks/fib/selected/hardcoded/Submission.lean",
                     "benchmarks/primecount/selected/no-table/Submission.lean",
                     "benchmarks/primecount/selected/results.json", "candidates.lock.json"):
            self.assertFalse(module.allowed(path), path)
        for path in ("README.md", "benchmarks/fib/cases.json", "lkc_bench/cli.py",
                     "benchmarks/fib/official/Submission.lean", "third_party/lean-kernel-challenge/LICENSE"):
            self.assertTrue(module.allowed(path), path)


if __name__ == "__main__":
    unittest.main()
