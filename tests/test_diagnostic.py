"""Check independent answers, measurement contracts and incomplete comparisons."""

import hashlib
import hmac
import itertools
import json
from pathlib import Path
import tempfile
import unittest

from lkc_bench import diagnostic
from lkc_bench.workspace import BENCHMARK_DIRS, ROOT


class ExpectedOutputTests(unittest.TestCase):
    def test_fibonacci_matches_iterative_recurrence(self):
        a, b, expected = 0, 1, {}
        for n in range(201):
            expected[n] = a
            a, b = b, a + b
        self.assertEqual(diagnostic.expected_values("fib", list(expected)), expected)

    def test_partition_known_values_and_zero(self):
        expected = {0: 1, 1: 1, 2: 2, 5: 7, 10: 42, 20: 627, 100: 190569292}
        self.assertEqual(diagnostic.expected_values("partition", list(expected)), expected)

    def test_mertens_matches_divisor_inversion(self):
        mu, expected, total = [0, 1], {0: 0}, 0
        for n in range(1, 151):
            if n > 1:
                mu.append(-sum(mu[d] for d in range(1, n) if n % d == 0))
            total += mu[n]
            expected[n] = total
        self.assertEqual(diagnostic.expected_values("mertens", list(expected)), expected)

    def test_invalid_inputs_fail(self):
        for problem in ("fib", "permanent"):
            for inputs in ([], [-1], [True], [1.5]):
                with self.subTest(problem=problem, inputs=inputs), self.assertRaises(ValueError):
                    diagnostic.expected_values(problem, inputs)

    def test_primecount_matches_trial_division_including_zero_and_one(self):
        total, expected = 0, {}
        for n in range(1001):
            if n >= 2 and all(n % divisor for divisor in range(2, n)):
                total += 1
            expected[n] = total
        self.assertEqual(diagnostic.expected_values("primecount", list(expected)), expected)
        self.assertEqual(expected[1000], 168)

    def test_permanent_matches_exhaustive_permutations(self):
        inputs, expected = [], {}
        for dimension in range(8):
            for seed in (0, 1, 0x12345678, 0xffffffff):
                n = (dimension << 32) | seed
                columns = diagnostic.permanent_columns(dimension, seed)
                if dimension >= 3:
                    for row, allowed in enumerate(columns):
                        self.assertEqual(len(set(allowed)), 3)
                        self.assertIn(row, allowed)
                        self.assertTrue(all(0 <= column < dimension for column in allowed))
                expected[n] = sum(all(column in columns[row] for row, column in enumerate(permutation))
                                  for permutation in itertools.permutations(range(dimension)))
                inputs.append(n)
        self.assertEqual(diagnostic.expected_values("permanent", inputs), expected)

    def test_permanent_public_plan_exact_answers(self):
        values = [8, 20, 18, 8, 12, 53, 78, 70, 94, 52, 165, 429, 140, 195, 93]
        inputs = diagnostic.DEFAULT_INPUTS["permanent"]
        self.assertEqual(len(inputs), 15)
        self.assertEqual(diagnostic.expected_values("permanent", inputs), dict(zip(inputs, values)))
        self.assertEqual(diagnostic.expected_values("permanent", [0, 4294967295, 8589934591, 12884901887,
                                                                  17179869183, 17179869186]),
                         {0: 1, 4294967295: 1, 8589934591: 1, 12884901887: 2, 17179869183: 6, 17179869186: 8})

    def test_manifest_inputs_match_diagnostic_defaults_and_public_packed_sampler(self):
        for problem, inputs in diagnostic.DEFAULT_INPUTS.items():
            manifest = json.loads((ROOT / "benchmarks" / BENCHMARK_DIRS[problem] / "cases.json").read_text())
            self.assertEqual(manifest["diagnostic_inputs"], inputs)
        manifest = json.loads((ROOT / "benchmarks/5-permanent/cases.json").read_text())
        sampled = []
        for group in manifest["groups"]:
            policy, seen = group["sampling"], set()
            for case in range(policy["count"]):
                attempt = 0
                while True:
                    message = json.dumps(["permanent", group["id"], case, "packed-seed", attempt],
                                         separators=(",", ":")).encode()
                    seed = int.from_bytes(hmac.new(b"", b"lean-kernel-challenge/grouped-evaluation-sample-v1\0"
                                                  + message, hashlib.sha256).digest()[:4], "big")
                    attempt += 1
                    if seed not in seen:
                        seen.add(seed)
                        break
                sampled.append((policy["scale"] << policy["seed_bits"]) | seed)
        self.assertEqual(sampled, diagnostic.DEFAULT_INPUTS["permanent"])
        self.assertEqual(manifest["memory_mb"], diagnostic.DEFAULT_MEMORY_MB["permanent"])

    def test_permanent_target_preserves_the_packed_nat_literal(self):
        source = diagnostic.target_source(71077100717, 165, "Test.permanent", "Nat")
        self.assertIn("Lean.mkNatLit 71077100717", source)
        self.assertIn("let rhs := Lean.mkNatLit 165", source)
        self.assertIn("let pf ← mkEqRefl rhs", source)


class MeasurementTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.log = Path(self.directory.name) / "timer.log"
        self.record = {
            "measurement_contract": "kernel-replay-v2",
            "boundary": "target-declaration-replay-v1", "target": "Test.check",
            "phase": "complete", "wall_ns": 17, "instructions": 29,
            "peak_rss_kb": 1024,
        }

    def write_timer(self, record=None):
        self.log.write_text("KERNEL_TIMING=" + json.dumps(self.record if record is None else record) + "\n", encoding="utf-8")

    def test_valid_timer_retains_raw_record(self):
        self.write_timer()
        self.assertEqual(diagnostic.parse_timer(self.log, "Test.check", "pmu"), self.record)

    def test_contract_mismatch_or_nonpositive_metric_fails(self):
        for field, value in (("measurement_contract", "old"), ("boundary", "full-closure-replay-v1"),
                             ("target", "Wrong.check"), ("phase", "error"), ("wall_ns", 0),
                             ("instructions", None), ("instructions", 0), ("instructions", True)):
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                self.write_timer({**self.record, field: value})
                diagnostic.parse_timer(self.log, "Test.check", "pmu")

    def test_missing_or_duplicate_timer_records_fail(self):
        for text in ("no measurement\n", ("KERNEL_TIMING=" + json.dumps(self.record) + "\n") * 2):
            with self.subTest(text=text), self.assertRaises(ValueError):
                self.log.write_text(text, encoding="utf-8")
                diagnostic.parse_timer(self.log, "Test.check", "wall-time")

    def test_wall_time_accepts_absent_pmu_counter(self):
        self.write_timer({**self.record, "instructions": None})
        self.assertEqual(diagnostic.parse_timer(self.log, "Test.check", "wall-time")["wall_ns"], 17)

    def test_callgrind_selects_ir_and_requires_one_replay(self):
        path = Path(self.directory.name) / "profile.out"
        profile = (
            "events: Dr Ir\nsummary: 12 345\n"
            f"cfn=(7) {diagnostic.REPLAY_SYMBOL}\ncalls=1 0\n"
        )
        path.write_text(profile, encoding="utf-8")
        self.assertEqual(diagnostic.parse_callgrind(path), 345)
        for invalid in (profile.replace("calls=1", "calls=2"), profile.replace("345", "0"),
                        profile.replace(diagnostic.REPLAY_SYMBOL, "unknown")):
            with self.subTest(profile=invalid), self.assertRaises(ValueError):
                path.write_text(invalid, encoding="utf-8")
                diagnostic.parse_callgrind(path)


class SummaryTests(unittest.TestCase):
    def test_incomplete_case_has_no_total_or_ratio(self):
        report = {
            "inputs": [1, 2],
            "runs": [
                {"role": "baseline", "cases": [{"n": 1, "status": "complete", "median": 10},
                                                {"n": 2, "status": "timeout", "median": None}]},
                {"role": "candidate", "cases": [{"n": 1, "status": "complete", "median": 5},
                                                 {"n": 2, "status": "complete", "median": 8}]},
            ],
        }
        diagnostic._summarize(report)
        self.assertFalse(report["complete"])
        self.assertIsNone(report["totals"]["baseline"])
        self.assertEqual(report["totals"]["candidate"], 13)
        self.assertIsNone(report["total_baseline_over_candidate"])
        self.assertEqual(report["comparisons"][0]["baseline_over_candidate"], 2)
        self.assertEqual(report["comparisons"][0]["reduction_percent"], 50)
        self.assertIsNone(report["comparisons"][1]["baseline_over_candidate"])

    def test_complete_baseline_only(self):
        report = {"inputs": [1], "runs": [{"role": "baseline", "cases": [
            {"n": 1, "status": "complete", "median": 7}]}]}
        diagnostic._summarize(report)
        self.assertTrue(report["complete"])
        self.assertEqual(report["totals"], {"baseline": 7})
        self.assertEqual(report["comparisons"], [])


if __name__ == "__main__":
    unittest.main()
