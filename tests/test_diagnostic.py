"""Check independent answers, measurement contracts and incomplete comparisons."""

import hashlib
import hmac
import itertools
import json
import io
import sys
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from lkc_bench import diagnostic
from lkc_bench.workspace import BENCHMARK_DIRS, ROOT


def packed_rule110_oracle(steps, seed):
    """Use integer rotations and a Boolean identity, independently of cell updates."""
    word = 1
    for position in range(2, 256):
        value = seed + (position + 1) * 2654435769
        value = ((value ^ (value // 65536)) * 2146121005) % 4294967296
        value = ((value ^ (value // 32768)) * 2221713035) % 4294967296
        value ^= value // 65536
        word |= (value // 2147483648) << position
    mask = (1 << 256) - 1
    for _ in range(steps):
        left = ((word << 1) | (word >> 255)) & mask
        right = (word >> 1) | ((word & 1) << 255)
        word = (word | right) & ~(left & word & right) & mask
    return word


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
        for problem in ("fib", "permanent", "ca-rule110", "sha256", "polydisc"):
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
        for problem in ("permanent", "ca-rule110", "sha256"):
            manifest = json.loads((ROOT / "benchmarks" / BENCHMARK_DIRS[problem] / "cases.json").read_text())
            sampled = []
            for group in manifest["groups"]:
                policy, seen = group["sampling"], set()
                for case in range(policy["count"]):
                    attempt = 0
                    while True:
                        message = json.dumps([problem, group["id"], case, "packed-seed", attempt],
                                             separators=(",", ":")).encode()
                        seed = int.from_bytes(hmac.new(b"", b"lean-kernel-challenge/grouped-evaluation-sample-v1\0"
                                                      + message, hashlib.sha256).digest()[:4], "big")
                        attempt += 1
                        if seed not in seen:
                            seen.add(seed)
                            break
                    sampled.append((policy["scale"] << policy["seed_bits"]) | seed)
            self.assertEqual(sampled, diagnostic.DEFAULT_INPUTS[problem])
            self.assertEqual(manifest["memory_mb"], diagnostic.DEFAULT_MEMORY_MB[problem])

    def test_rule110_official_one_step_example(self):
        value = 62412942364118713680778432052760708221590981514164502482365323362230212198349
        self.assertEqual(diagnostic.expected_values("ca-rule110", [4294967297]), {4294967297: value})

    def test_rule110_zero_steps_preserves_seeded_row_and_forced_cells(self):
        seeds = (0, 1, 2, 0x80000000, 0xffffffff)
        answers = diagnostic.expected_values("ca-rule110", list(seeds))
        for seed in seeds:
            with self.subTest(seed=seed):
                self.assertEqual(answers[seed], packed_rule110_oracle(0, seed))
                self.assertEqual(answers[seed] & 3, 1)
                self.assertLess(answers[seed], 1 << 256)
        self.assertEqual(len(set(answers.values())), len(seeds))

    def test_rule110_matches_independent_packed_oracle_at_seed_extremes(self):
        expected = {(steps << 32) | seed: packed_rule110_oracle(steps, seed)
                    for steps in (1, 2, 4, 8, 17)
                    for seed in (0, 1, 0x12345678, 0x80000000, 0xffffffff)}
        self.assertEqual(diagnostic.expected_values("ca-rule110", list(expected)), expected)

    def test_rule110_public_plan_matches_independent_packed_oracle(self):
        inputs = diagnostic.DEFAULT_INPUTS["ca-rule110"]
        self.assertEqual([n >> 32 for n in inputs], [2, 2, 4, 4, 8, 8])
        expected = {n: packed_rule110_oracle(n >> 32, n & 0xffffffff) for n in inputs}
        self.assertEqual(diagnostic.expected_values("ca-rule110", inputs), expected)

    def test_rule110_target_preserves_full_nat_output(self):
        value = 62412942364118713680778432052760708221590981514164502482365323362230212198349
        source = diagnostic.target_source(4294967297, value, "Test.rule110", "Nat")
        self.assertIn("Lean.mkNatLit 4294967297", source)
        self.assertIn(f"let rhs := Lean.mkNatLit {value}", source)

    def test_sha256_official_one_step_example(self):
        value = 6974916886958575962243026017989799625410957637305596483321224775681667163855
        self.assertEqual(diagnostic.expected_values("sha256", [4294967297]), {4294967297: value})

    def test_sha256_zero_steps_and_seed_extremes(self):
        for seed in (0, 1, 2, 0x12345678, 0x80000000, 0xffffffff):
            # Closed form of the LCG checks its update order independently.
            words = [(1664525 ** k * seed + 1013904223 * (1664525 ** k - 1) // 1664524) % 2 ** 32
                     for k in range(1, 9)]
            expected = sum(word << (32 * (7 - index)) for index, word in enumerate(words))
            with self.subTest(seed=seed):
                self.assertEqual(diagnostic.expected_values("sha256", [seed]), {seed: expected})
                self.assertEqual(diagnostic.sha256_initial_bytes(seed), expected.to_bytes(32, "big"))

    def test_sha256_initial_digest_byte_order(self):
        expected = bytes.fromhex("3c88596c5e8885db8116017eb4733ac50cf06d605e98c13fc656dd928e625fc9")
        self.assertEqual(diagnostic.sha256_initial_bytes(1), expected)
        self.assertEqual(diagnostic.sha256_initial_bytes((1 << 32) | 1), expected)

    def test_sha256_chain_preserves_leading_zero_bytes(self):
        first = bytes.fromhex("00b3f8a7850d66a9df82ba0bc51201f619f6a508a44ce7c3c9d7a007e2931e07")
        second = bytes.fromhex("34858626ac0af78543c65eee2c18e379ab61a76eeca30ad4caa62ace9335911b")
        inputs = [(1 << 32) | 2, (2 << 32) | 2]
        self.assertEqual(diagnostic.expected_values("sha256", inputs),
                         dict(zip(inputs, (int.from_bytes(first, "big"), int.from_bytes(second, "big")))))
        self.assertEqual(hashlib.sha256(first).digest(), second)
        self.assertNotEqual(hashlib.sha256(first.lstrip(b"\x00")).digest(), second)

    def test_sha256_public_plan_and_binary_chain(self):
        inputs = diagnostic.DEFAULT_INPUTS["sha256"]
        self.assertEqual([n >> 32 for n in inputs], [4, 4, 32, 32, 512, 512])
        expected = {}
        for n in inputs:
            seed = n & 0xffffffff
            words = [(1664525 ** k * seed + 1013904223 * (1664525 ** k - 1) // 1664524) % 2 ** 32
                     for k in range(1, 9)]
            digest = b"".join(word.to_bytes(4, "big") for word in words)
            for _ in range(n >> 32):
                digest = hashlib.sha256(digest).digest()
            expected[n] = int.from_bytes(digest, "big")
        self.assertEqual(diagnostic.expected_values("sha256", inputs), expected)

    def test_sha256_target_preserves_full_nat_output(self):
        value = 6974916886958575962243026017989799625410957637305596483321224775681667163855
        source = diagnostic.target_source(4294967297, value, "Test.sha256", "Nat")
        self.assertIn("Lean.mkNatLit 4294967297", source)
        self.assertIn(f"let rhs := Lean.mkNatLit {value}", source)

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


class PreparationMemoryTests(unittest.TestCase):
    def run_case(self, preparation_memory, failed_phase=None, problem="sha256", inputs=None):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        root = Path(directory.name)
        package = root / "upstream/evaluation/problems" / problem
        package.mkdir(parents=True)
        (package / "lean-toolchain").write_text("leanprover/lean4:v4.33.1\n")
        source = root / "Submission.lean"
        source.write_text("import Spec\n")
        exporter, timer = root / "lean4export", root / "kernel"
        exporter.write_text("exporter")
        timer.write_text("timer")
        calls = []

        def step(command, *, log, root, memory_mb, stdout_path=None, **kwargs):
            phase = log.name
            calls.append((phase, memory_mb, command))
            status = "memory-limit" if failed_phase and phase.startswith(failed_phase) else "complete"
            log.write_text("mock tool process\n")
            if stdout_path:
                stdout_path.write_text("" if phase == "lean-path.log" else "mock export\n")
            if "-o" in command and status == "complete":
                Path(command[command.index("-o") + 1]).write_bytes(b"mock compiled source")
            return {"status": status, "memory_limit_mb": memory_mb, "log": log.relative_to(root).as_posix()}

        args = SimpleNamespace(problem=problem, metric="wall-time", memory_mb=4096,
                               preparation_memory_mb=preparation_memory, baseline="example", inputs=[0] if inputs is None else inputs,
                               repetitions=1, timeout=120, submission=source)
        with patch.object(diagnostic.platform, "system", return_value="Linux"), \
                patch.object(diagnostic, "official_baseline", return_value=source), \
                patch.dict(diagnostic.os.environ, {"LEAN4EXPORT_BIN": str(root), "TIMER_BIN": str(timer)}), \
                patch.object(diagnostic, "_step", side_effect=step), \
                patch.object(diagnostic, "parse_timer", return_value={"wall_ns": 17}), \
                patch("sys.stdout", new_callable=io.StringIO):
            report = diagnostic.run_diagnostic(args, root / "upstream", root / "output")
        return report, calls, (root / "output/diagnostic.md").read_text()

    def test_override_changes_only_target_compile_and_export_for_both_sources(self):
        report, calls, markdown = self.run_case(8192)
        self.assertTrue(report["complete"])
        for phase, memory_mb, command in calls:
            preparation = phase.startswith(("target-compile-", "target-export-"))
            self.assertEqual(memory_mb, 8192 if preparation else 4096, phase)
            if "-M" in command:
                self.assertEqual(int(command[command.index("-M") + 1]), memory_mb)
        for run in report["runs"]:
            self.assertEqual(run["compile"]["memory_limit_mb"], 4096)
            case = run["cases"][0]
            self.assertEqual(case["preparation"]["target-export"]["memory_limit_mb"], 8192)
            self.assertEqual(case["preparation"]["axiom-audit"]["memory_limit_mb"], 4096)
            self.assertEqual(case["samples"][0]["process"]["memory_limit_mb"], 4096)
        self.assertEqual(report["limits"]["target_preparation_memory_mb"], 8192)
        self.assertEqual(report["limits"]["source_compile_memory_mb"], 4096)
        self.assertEqual(report["limits"]["replay_memory_mb"], 4096)
        self.assertIn("4096 MiB for source compilation, axiom audits and replay", markdown)
        self.assertIn("8192 MiB for target compilation and export", markdown)
        self.assertIn("| --- | ---: | --- | --- | ---: | --- |\n| baseline", markdown)

    def test_default_keeps_all_processes_at_original_limit(self):
        report, calls, _ = self.run_case(None)
        self.assertTrue(report["complete"])
        self.assertTrue(all(memory == 4096 for _, memory, _ in calls))
        self.assertEqual(report["limits"]["target_preparation_memory_mb"], 4096)

    def test_larger_preparation_does_not_hide_compile_or_replay_memory_failure(self):
        for phase in ("submission-compile", "replay-"):
            with self.subTest(phase=phase):
                report, calls, _ = self.run_case(8192, failed_phase=phase)
                self.assertFalse(report["complete"])
                self.assertIsNone(report["totals"]["baseline"])
                self.assertIsNone(report["total_baseline_over_candidate"])
                self.assertTrue(all(case["status"] == "memory-limit" for run in report["runs"] for case in run["cases"]))
                self.assertTrue(all(memory == 4096 for name, memory, _ in calls if name.startswith(phase)))

    def test_polydisc_records_signed_large_int_and_only_matching_group_metadata(self):
        value = -(1 << 80748) + 19
        old_limit = sys.get_int_max_str_digits() if hasattr(sys, "get_int_max_str_digits") else None
        if old_limit is not None:
            sys.set_int_max_str_digits(4300)
            self.addCleanup(sys.set_int_max_str_digits, old_limit)
        with patch.object(diagnostic, "polydisc_value", return_value=value), \
                patch.object(diagnostic, "target_source", wraps=diagnostic.target_source) as target:
            report, calls, markdown = self.run_case(None, problem="polydisc", inputs=[0, 5042242704654352709])
        self.assertTrue(report["complete"])
        self.assertTrue(all(memory == 4096 for _, memory, _ in calls))
        self.assertTrue(all(call.args[3] == "Int" for call in target.call_args_list))
        for run in report["runs"]:
            first, second = run["cases"]
            self.assertNotIn("group", first)
            self.assertNotIn("case", first)
            self.assertEqual((second["group"], second["case"]), ("D5", 0))
            self.assertEqual(second["degree"], 24)
            self.assertEqual(second["coefficient_width_bits"], 3484)
            self.assertNotIn("seed", second)
            self.assertEqual(second["expected"], str(value))
            self.assertGreater(len(second["expected"]), 24000)
        self.assertEqual([case["n"] for case in report["public_local_plan"]], diagnostic.DEFAULT_INPUTS["polydisc"])
        self.assertIn("full Sylvester determinant", report["expected_output_method"])
        self.assertIn("Input (degree, max coefficient bits)", markdown)
        self.assertIn("5042242704654352709 (24, 3484)", markdown)
        negative = diagnostic.target_source(0, value, "Test.polydisc", "Int")
        positive = diagnostic.target_source(19337098, -value, "Test.polydisc", "Int")
        self.assertTrue(f"Lean.mkApp (Lean.mkConst ``Int.negSucc) (Lean.mkNatLit {-value - 1})" in negative,
                        "The negative target must contain the complete Int.negSucc argument.")
        self.assertTrue(f"Lean.mkApp (Lean.mkConst ``Int.ofNat) (Lean.mkNatLit {-value})" in positive,
                        "The positive target must contain the complete Int.ofNat argument.")


class SummaryTests(unittest.TestCase):
    def test_rule110_markdown_shows_decoded_steps_and_seed(self):
        report = {"problem": "ca-rule110", "inputs": [4294967297], "metric": "wall-time", "unit": "ns",
                  "repetitions": 1, "runs": [{"role": "baseline", "cases": [
                      {"n": 4294967297, "steps": 1, "seed": 1, "status": "complete", "median": 7,
                       "samples": [{"status": "complete", "value": 7}]}]}]}
        diagnostic._summarize(report)
        with tempfile.TemporaryDirectory() as temporary:
            diagnostic._write_markdown(Path(temporary), report)
            text = (Path(temporary) / "diagnostic.md").read_text()
        self.assertIn("Packed input (steps, seed)", text)
        self.assertIn("4294967297 (1, 1)", text)

    def test_sha256_markdown_shows_decoded_steps_and_seed(self):
        report = {"problem": "sha256", "inputs": [4294967297], "metric": "wall-time", "unit": "ns",
                  "repetitions": 1, "runs": [{"role": "baseline", "cases": [
                      {"n": 4294967297, "steps": 1, "seed": 1, "status": "complete", "median": 7,
                       "samples": [{"status": "complete", "value": 7}]}]}]}
        diagnostic._summarize(report)
        with tempfile.TemporaryDirectory() as temporary:
            diagnostic._write_markdown(Path(temporary), report)
            text = (Path(temporary) / "diagnostic.md").read_text()
        self.assertIn("Packed input (steps, seed)", text)
        self.assertIn("4294967297 (1, 1)", text)

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
