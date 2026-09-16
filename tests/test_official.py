"""Synthetic canonical verdicts and worker tests, with no Lean solution fixtures."""

from argparse import Namespace
from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from lkc_bench import official


def verdict(seconds=(2.0, 4.0)):
    plan = [
        {"slot": index, "group": "P1", "case": index, "n": 14 + index,
         "limits": {"timeout_seconds": 30}}
        for index in range(len(seconds))
    ]
    return {
        "problem": "partition", "status": "accepted", "metric": "wall_time",
        "evaluation_cohort": {
            "id": "a" * 24, "policy_sha256": "b" * 64,
            "policy": {"performance_plan_sha256": "c" * 64, "performance_plan": plan},
        },
        "replay_report": {
            "schema": "replay-report-v1", "ranking_contract": "computation-total-v1",
            "metric": "wall_time", "reps": 1, "eligible": True,
            "computation_total": sum(seconds),
            "correctness": {"result": "ok", "median_s": 9.0, "median_wall_ns": 9_000_000_000,
                            "peak_rss_kb": 12345, "verification_only": True},
            "cases": [
                {"case_id": f"case-{index + 1:04d}", "group": "P1", "result": "ok",
                 "median_s": elapsed, "median_wall_ns": int(elapsed * 1_000_000_000),
                 "peak_rss_kb": 20000 + index}
                for index, elapsed in enumerate(seconds)
            ],
        },
    }


def summarized(raw=None, *, role="baseline"):
    return official.summarize_verdict(raw or verdict(), role=role, source_sha256="d" * 64, elapsed_seconds=17.5)


class VerdictTests(unittest.TestCase):
    def test_complete_keeps_verification_separate_and_binds_public_inputs(self):
        result = summarized()
        self.assertTrue(result["complete"])
        self.assertEqual(result["computation_total"], 6)
        self.assertEqual(result["correctness"]["wall_seconds"], 9)
        self.assertEqual([row["input"] for row in result["cases"]], [14, 15])
        self.assertEqual(result["cases"][0]["peak_rss_kib"], 20000)
        self.assertEqual(result["cases"][1]["limits"], {"timeout_seconds": 30})

    def test_accepted_does_not_imply_complete(self):
        edits = [
            lambda raw: raw.pop("replay_report"),
            lambda raw: raw["replay_report"].update(eligible=False),
            lambda raw: raw["replay_report"].update(computation_total=None),
            lambda raw: raw["replay_report"].update(computation_total=float("nan")),
            lambda raw: raw["replay_report"].update(computation_total=True),
            lambda raw: raw["replay_report"]["correctness"].update(result="timeout"),
            lambda raw: raw["replay_report"]["cases"][1].update(result="not-run"),
            lambda raw: raw["replay_report"]["cases"].pop(),
            lambda raw: raw["evaluation_cohort"]["policy"].pop("performance_plan"),
            lambda raw: raw.update(metric="perf_instructions"),
            lambda raw: raw.update(status="rejected"),
        ]
        for index, edit in enumerate(edits):
            with self.subTest(index=index):
                raw = verdict()
                edit(raw)
                result = summarized(raw)
                self.assertFalse(result["complete"])
                self.assertIsNone(result["computation_total"])

    def test_reordered_or_misbound_cases_fail_closed(self):
        for field, changed in (("case_id", "case-0002"), ("group", "P2")):
            with self.subTest(field=field):
                raw = verdict()
                raw["replay_report"]["cases"][0][field] = changed
                result = summarized(raw)
                self.assertFalse(result["case_identities_valid"])
                self.assertFalse(result["complete"])
                self.assertIsNone(result["cases"][0]["input"])

    def test_missing_measurements_stay_null(self):
        raw = verdict()
        raw["replay_report"].update(eligible=False, computation_total=None)
        raw["replay_report"]["cases"][1] = {"case_id": "case-0002", "group": "P1", "result": "build-timeout"}
        result = summarized(raw)
        self.assertEqual(result["cases"][1]["result"], "build-timeout")
        self.assertIsNone(result["cases"][1]["wall_seconds"])
        self.assertIsNone(result["cases"][1]["peak_rss_kib"])

    def test_summary_omits_paths_source_and_free_form_diagnostics(self):
        raw = verdict()
        secret = "/home/private-user/private-source/Secret.lean"
        raw.update(submission=secret, reason=secret, source_contents="private source text", stages={"error": secret})
        raw["replay_report"]["correctness"]["measurement_target"] = "private_theorem_name"
        raw["replay_report"]["cases"][0].update(measurement_target="private_theorem_name", error=secret)
        serialized = json.dumps(summarized(raw))
        for omitted in (secret, "private_theorem_name", "private source text"):
            self.assertNotIn(omitted, serialized)

    def test_path_shaped_identifiers_are_discarded(self):
        raw = verdict()
        raw["evaluation_cohort"]["id"] = "/tmp/private"
        raw["replay_report"]["cases"][0]["group"] = "C:\\private\\source"
        result = summarized(raw)
        self.assertIsNone(result["cohort_id"])
        self.assertIsNone(result["cases"][0]["group"])
        self.assertFalse(result["complete"])


class ComparisonTests(unittest.TestCase):
    def test_total_and_per_case_ratios_use_baseline_over_candidate(self):
        result = official.compare_results(summarized(), summarized(verdict((1, 2)), role="candidate"))
        self.assertTrue(result["comparable"])
        self.assertEqual(result["total_ratio"], 2)
        self.assertEqual([row["baseline_over_candidate"] for row in result["cases"]], [2, 2])

    def test_partial_runs_never_get_a_ratio(self):
        candidate = summarized()
        candidate["complete"] = False
        candidate["computation_total"] = None
        result = official.compare_results(summarized(), candidate)
        self.assertFalse(result["comparable"])
        self.assertIsNone(result["total_ratio"])
        self.assertEqual(result["cases"], [])

    def test_each_comparison_identity_is_required(self):
        baseline = summarized()
        changes = [
            lambda row: row.update(metric="perf_instructions"),
            lambda row: row.update(cohort_id=None),
            lambda row: row.update(cohort_id="another-cohort"),
            lambda row: row.update(ranking_contract="other-contract"),
            lambda row: row.update(repetitions=3),
            lambda row: row.update(cohort_policy_sha256="e" * 64),
            lambda row: row.update(performance_plan_sha256="e" * 64),
            lambda row: row["correctness"].update(result="timeout"),
            lambda row: row["cases"][0].update(input=99),
            lambda row: row["cases"][0].update(group="P2"),
            lambda row: row["cases"][0]["limits"].update(timeout_seconds=60),
            lambda row: row["cases"][0].update(result="timeout"),
            lambda row: row["cases"].reverse(),
        ]
        for index, change in enumerate(changes):
            with self.subTest(index=index):
                candidate = deepcopy(baseline)
                change(candidate)
                result = official.compare_results(baseline, candidate)
                self.assertFalse(result["comparable"])
                self.assertIsNone(result["total_ratio"])
                self.assertEqual(result["cases"], [])


class WorkerTests(unittest.TestCase):
    def _fake_upstream(self, root, body):
        upstream = root / "upstream"
        (upstream / "evaluation").mkdir(parents=True)
        (upstream / "evaluation" / "run.py").write_text(body, encoding="utf-8")
        return upstream

    def test_worker_loads_canonical_entrypoint_in_its_own_process(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            upstream = self._fake_upstream(root,
                "import os\n"
                "def evaluate_file(source, timeout, *, problem):\n"
                "    return {'status': 'rejected', 'problem': problem, 'received_timeout': timeout,\n"
                "            'pid': os.getpid(), 'cwd': os.getcwd(), 'source': str(source)}\n")
            result, elapsed = official._run_worker(upstream=upstream, source=root / "unused-source", problem="partition",
                                                  timeout=23, output=root / "output", role="baseline")
            self.assertEqual(result["received_timeout"], 23)
            self.assertEqual(result["problem"], "partition")
            self.assertEqual(Path(result["cwd"]), upstream)
            self.assertNotEqual(result["pid"], os.getpid())
            self.assertGreater(elapsed, 0)
            self.assertTrue((root / "output" / "raw" / "baseline.log").is_file())
            self.assertEqual(json.loads((root / "output" / "raw" / "baseline.json").read_text()), result)

    def test_worker_preserves_exception_details_only_in_raw_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            upstream = self._fake_upstream(root,
                "def evaluate_file(source, timeout, *, problem):\n"
                "    raise ValueError('/private/path/diagnostic')\n")
            result, _ = official._run_worker(upstream=upstream, source=root / "unused-source", problem="fib",
                                             timeout=120, output=root / "output", role="candidate")
            self.assertEqual(result["status"], "error")
            self.assertIn("/private/path/diagnostic", result["reason"])
            self.assertNotIn("/private/path/diagnostic", json.dumps(summarized(result)))

    def test_worker_crash_cannot_reuse_a_stale_verdict(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            upstream = self._fake_upstream(root,
                "def evaluate_file(source, timeout, *, problem):\n"
                "    raise SystemExit(7)\n")
            raw = root / "output" / "raw"
            raw.mkdir(parents=True)
            (raw / "baseline.json").write_text(json.dumps(verdict()), encoding="utf-8")
            result, _ = official._run_worker(upstream=upstream, source=root / "unused-source", problem="fib",
                                             timeout=120, output=root / "output", role="baseline")
            self.assertEqual(result["status"], "error")
            self.assertTrue(result["harness_error"])
            self.assertIn("code 7", result["reason"])

    @unittest.skipIf(os.name == "nt", "POSIX process groups are used on Linux/WSL")
    def test_interrupt_allows_nested_tool_group_cleanup(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            upstream = self._fake_upstream(root,
                "import os, signal, subprocess, sys\n"
                "from pathlib import Path\n"
                "def evaluate_file(source, timeout, *, problem):\n"
                "    child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'], start_new_session=True)\n"
                "    try:\n"
                "        Path('child.pid').write_text(str(child.pid))\n"
                "        child.wait()\n"
                "    finally:\n"
                "        os.killpg(child.pid, signal.SIGKILL)\n"
                "        child.wait()\n")
            env = os.environ.copy()
            env["PYTHONPATH"] = str(Path(official.__file__).resolve().parent.parent)
            process = subprocess.Popen([
                sys.executable, "-m", "lkc_bench.official", "--worker", "--upstream", str(upstream),
                "--source", str(root / "unused-source"), "--problem", "fib", "--verdict", str(root / "result.json"),
            ], cwd=upstream, env=env, start_new_session=True,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            try:
                deadline = time.monotonic() + 10
                while not (upstream / "child.pid").exists() and time.monotonic() < deadline:
                    time.sleep(0.05)
                self.assertTrue((upstream / "child.pid").exists(), "worker did not launch its tool")
                child_pid = int((upstream / "child.pid").read_text())
                official._terminate_process_tree(process)
                self.assertIsNotNone(process.returncode)
                with self.assertRaises(ProcessLookupError):
                    os.kill(child_pid, 0)
            finally:
                if process.poll() is None:
                    official._terminate_process_tree(process)


class ReportTests(unittest.TestCase):
    def test_run_writes_portable_reports_and_cleans_source_snapshot(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            args = Namespace(problem="partition", baseline="example", submission=root / "private-location" / "private-name",
                             timeout=120)
            command = subprocess.CompletedProcess([], 0, "a" * 40 + "\n", "")
            with patch.object(official.subprocess, "run", return_value=command), \
                 patch.object(official.shutil, "copyfile") as copy, \
                 patch.object(official, "_source_hash", return_value="d" * 64), \
                 patch.object(official, "_run_worker", side_effect=[(verdict(), 17), (verdict((1, 2)), 12)]) as worker:
                result = official.run_comparison(args, root / "upstream", root / "out")
            self.assertTrue(result["complete"])
            self.assertEqual(result["comparison"]["total_ratio"], 2)
            self.assertEqual(copy.call_args_list[0].args[0], root / "upstream" / "examples" / "partition" / "Submission.lean")
            self.assertFalse(worker.call_args.kwargs["source"].parent.exists())
            saved = json.loads((root / "out" / "summary.json").read_text())
            self.assertEqual(saved, result)
            markdown = (root / "out" / "summary.md").read_text(encoding="utf-8")
            self.assertIn("Correctness C is verification only", markdown)
            self.assertIn("case-0001 | P1 | 14", markdown)
            self.assertIn("Total ratio: 2", markdown)
            self.assertIn("raw/", markdown)
            for content in (json.dumps(result), markdown):
                self.assertNotIn("private-location", content)
                self.assertNotIn("private-name", content)

    def test_baseline_only_does_not_invent_a_comparison(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            args = Namespace(problem="partition", baseline="starter", submission=None, timeout=120)
            with patch.object(official.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, "a" * 40)), \
                 patch.object(official.shutil, "copyfile") as copy, \
                 patch.object(official, "_source_hash", return_value="d" * 64), \
                 patch.object(official, "_run_worker", return_value=(verdict(), 17)):
                result = official.run_comparison(args, root / "upstream", root / "out")
            self.assertIsNone(result["comparison"])
            self.assertTrue(result["complete"])
            self.assertEqual(copy.call_args.args[0], root / "upstream" / "problems" / "partition" / "Submission.lean")


if __name__ == "__main__":
    unittest.main()
