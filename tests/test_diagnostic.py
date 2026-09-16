"""Check independent answers, measurement contracts and incomplete comparisons."""

import json
from pathlib import Path
import tempfile
import unittest

from lkc_bench import diagnostic


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
        for inputs in ([], [-1], [True], [1.5]):
            with self.subTest(inputs=inputs), self.assertRaises(ValueError):
                diagnostic.expected_values("fib", inputs)

    def test_primecount_matches_trial_division_including_zero_and_one(self):
        total, expected = 0, {}
        for n in range(1001):
            if n >= 2 and all(n % divisor for divisor in range(2, n)):
                total += 1
            expected[n] = total
        self.assertEqual(diagnostic.expected_values("primecount", list(expected)), expected)
        self.assertEqual(expected[1000], 168)


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
