"""Run the pinned canonical local evaluator and report comparable replay results."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import platform
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from typing import Any


_PROBLEMS = ("fib", "ca-rule110", "mertens", "partition", "permanent", "polydisc", "primecount", "sha256")
_OUTCOMES = {
    "ok", "not-run", "invalid", "timeout", "error", "failed", "wrong-answer",
    "instruction-limit", "memory-limit", "budget-exhausted", "rejected", "oom",
    "build-error", "export-error", "audit-error", "binding-error",
    "value-eval-timeout", "value-eval-error", "build-timeout", "axiom-audit-timeout", "resource-limit",
}
_STATUSES = {"accepted", "rejected", "error", "retry"}


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".report-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, indent=2, allow_nan=False)
            handle.write("\n")
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def _source_hash(source: Path) -> str:
    digest = hashlib.sha256()
    with source.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _number(value: Any, *, positive: bool = False) -> int | float | None:
    if type(value) not in (int, float) or not math.isfinite(value):
        return None
    if value < 0 or (positive and value == 0):
        return None
    return value


def _tag(value: Any) -> str | None:
    # Identifiers come from the public plan. Do not carry free-form diagnostics,
    # compiler targets, environment strings, or filesystem paths into summaries.
    if isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9_.:-]{1,160}", value):
        return value
    return None


def _object(value: Any) -> dict:
    return value if isinstance(value, dict) else {}


def _outcome(value: Any) -> str:
    return value if isinstance(value, str) and value in _OUTCOMES else "unknown"


def _measurements(record: dict, metric: str | None) -> dict:
    wall_ns = _number(record.get("median_wall_ns"), positive=True)
    seconds = wall_ns / 1_000_000_000 if wall_ns is not None else None
    if seconds is None and metric == "wall_time":
        seconds = _number(record.get("median_s"), positive=True)
    return {
        "wall_seconds": seconds,
        "median_instructions": _number(record.get("median_instructions"), positive=True),
        "peak_rss_kib": _number(record.get("peak_rss_kb"), positive=True),
    }


def summarize_verdict(verdict: dict, *, role: str, source_sha256: str, elapsed_seconds: float) -> dict:
    """Allowlist public metadata and measurements; leave diagnostics in raw files."""
    report = _object(verdict.get("replay_report"))
    cohort = _object(verdict.get("evaluation_cohort"))
    policy = _object(cohort.get("policy"))
    plan = policy.get("performance_plan")
    plan = plan if isinstance(plan, list) else []
    reported = report.get("cases")
    reported = reported if isinstance(reported, list) else []
    metric = report.get("metric")
    metric = metric if metric in ("wall_time", "perf_instructions") else None
    correctness = _object(report.get("correctness"))
    status = verdict.get("status")
    status = status if isinstance(status, str) and status in _STATUSES else "error"
    cases = []
    identity_valid = bool(plan) and len(plan) == len(reported)
    for slot, raw in enumerate(reported):
        raw = _object(raw)
        planned = _object(plan[slot]) if slot < len(plan) else {}
        case_id = _tag(raw.get("case_id"))
        group = _tag(raw.get("group"))
        bound = (
            planned.get("slot") == slot
            and type(planned.get("slot")) is int
            and case_id == f"case-{slot + 1:04d}"
            and group is not None and group == planned.get("group")
            and type(planned.get("case")) is int
            and type(planned.get("n")) is int
        )
        identity_valid = identity_valid and bound
        limits = _object(planned.get("limits"))
        cases.append({
            "case_id": case_id,
            "group": group,
            "slot": slot,
            "group_case": planned.get("case") if bound else None,
            "input": planned.get("n") if bound else None,
            "scale": _number(planned.get("scale")) if bound else None,
            "limits": {
                name: _number(limits.get(name))
                for name in ("timeout_seconds", "kernel_instructions", "memory_mb")
                if _number(limits.get(name)) is not None
            } if bound else {},
            "result": _outcome(raw.get("result")),
            **_measurements(raw, metric),
        })
    correctness_result = _outcome(correctness.get("result", "not-run"))
    total = _number(report.get("computation_total"), positive=True)
    complete = (
        status == "accepted" and report.get("eligible") is True
        and total is not None and metric is not None
        and report.get("metric") == verdict.get("metric")
        and correctness_result == "ok" and identity_valid
        and all(case["result"] == "ok" for case in cases)
    )
    return {
        "role": role,
        "source_sha256": source_sha256,
        "status": status,
        "complete": bool(complete),
        "eligible": report.get("eligible") is True,
        "metric": metric,
        "ranking_contract": _tag(report.get("ranking_contract")),
        "repetitions": report.get("reps") if type(report.get("reps")) is int else None,
        "cohort_id": _tag(cohort.get("id")),
        "cohort_policy_sha256": _tag(cohort.get("policy_sha256")),
        "performance_plan_sha256": _tag(policy.get("performance_plan_sha256")),
        "case_identities_valid": bool(identity_valid),
        "passed_cases": sum(case["result"] == "ok" for case in cases),
        "reported_cases": len(cases),
        "planned_cases": len(plan) if plan else None,
        "computation_total": total if complete else None,
        "computation_unit": "seconds" if metric == "wall_time" else "instructions" if metric else None,
        "correctness": {"result": correctness_result, "verification_only": True,
                        **_measurements(correctness, metric)},
        "elapsed_seconds": round(elapsed_seconds, 3),
        "cases": cases,
    }


def compare_results(baseline: dict, candidate: dict) -> dict:
    """Return ratios only after validating a complete shared measurement cohort."""
    failures = []
    if not baseline.get("complete") or not candidate.get("complete"):
        failures.append("Both runs must complete every case and correctness replay.")
    for field, label in (
        ("metric", "metric"), ("cohort_id", "cohort"),
        ("ranking_contract", "ranking contract"), ("repetitions", "repetition count"),
        ("cohort_policy_sha256", "cohort policy hash"),
        ("performance_plan_sha256", "performance plan hash"),
    ):
        if baseline.get(field) is None or baseline.get(field) != candidate.get(field):
            failures.append(f"The {label} is missing or differs.")
    if (baseline.get("correctness", {}).get("result") != "ok"
            or candidate.get("correctness", {}).get("result") != "ok"):
        failures.append("Both correctness replays must pass.")
    fields = ("case_id", "group", "slot", "group_case", "input", "scale", "limits", "result")
    identities = lambda result: [[row.get(field) for field in fields] for row in result.get("cases", [])]
    if (not baseline.get("case_identities_valid") or not candidate.get("case_identities_valid")
            or identities(baseline) != identities(candidate)):
        failures.append("The full ordered case identities and outcomes must match.")
    comparable = not failures
    ratios = []
    if comparable:
        for left, right in zip(baseline["cases"], candidate["cases"]):
            key = "wall_seconds" if baseline["metric"] == "wall_time" else "median_instructions"
            a, b = _number(left.get(key), positive=True), _number(right.get(key), positive=True)
            ratios.append({
                "case_id": left["case_id"],
                "baseline_over_candidate": a / b if a is not None and b is not None else None,
            })
    a = _number(baseline.get("computation_total"), positive=True)
    b = _number(candidate.get("computation_total"), positive=True)
    return {
        "comparable": comparable,
        "reasons": failures,
        "ratio_definition": "baseline / candidate; greater than 1 means the candidate used less measured work",
        "total_ratio": a / b if comparable and a is not None and b is not None else None,
        "cases": ratios,
    }


def _display(value: Any) -> str:
    if value is None:
        return "-"
    if type(value) is float:
        return f"{value:.9g}"
    return str(value).replace("|", "\\|").replace("\n", " ")


def render_markdown(summary: dict) -> str:
    lines = [
        f"# {summary['problem']} local comparison", "",
        "Canonical local judge, complete public plan, one wall-time repetition. "
        "These measurements are not official leaderboard scores.", "",
        f"Upstream revision: `{summary['upstream_revision']}`.", "",
        f"Run status: {summary['status']}.", "",
        "| Role | Verdict | Complete | Cases passed/reported | Computation T | Unit | Correctness C (s) | Elapsed (s) |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for role, result in summary["results"].items():
        cells = (role, result["status"], "yes" if result["complete"] else "no",
                 f"{result['passed_cases']}/{result['reported_cases']}", result["computation_total"], result["computation_unit"],
                 result["correctness"]["wall_seconds"], result["elapsed_seconds"])
        lines.append("| " + " | ".join(_display(cell) for cell in cells) + " |")
    lines += ["", "Correctness C is verification only and is excluded from T. Missing measurements "
              "are shown as `-`. Accepted alone does not establish a complete pass."]
    comparison = summary.get("comparison")
    if comparison:
        lines += ["", "## Comparison", "", comparison["ratio_definition"] + ".", ""]
        if comparison["comparable"]:
            lines.append(f"Total ratio: {_display(comparison['total_ratio'])}.")
        else:
            lines += ["No ratios are available:", ""] + [f"- {reason}" for reason in comparison["reasons"]]
    ratios = {row["case_id"]: row["baseline_over_candidate"]
              for row in (comparison or {}).get("cases", [])}
    for role, result in summary["results"].items():
        lines += ["", f"## {role.capitalize()}", "",
                  f"Source SHA-256: `{result['source_sha256']}`.", "",
                  f"Cohort: `{result['cohort_id'] or 'unavailable'}`; metric: `{result['metric'] or 'unavailable'}`.", "",
                  f"Correctness: {result['correctness']['result']}; peak replay RSS: "
                  f"{_display(result['correctness']['peak_rss_kib'])} KiB.", "",
                  "| Case | Group | Input | Outcome | Group replay limit (s) | Replay wall (s) | Peak replay RSS (KiB) | Baseline / candidate |",
                  "| --- | --- | --- | --- | --- | --- | --- | --- |"]
        for row in result["cases"]:
            cells = (row["case_id"], row["group"], row["input"], row["result"],
                     row["limits"].get("timeout_seconds"), row["wall_seconds"], row["peak_rss_kib"],
                     ratios.get(row["case_id"]) if role == "candidate" else None)
            lines.append("| " + " | ".join(_display(cell) for cell in cells) + " |")
    lines += ["", "## Environment", ""]
    lines += [f"Local timeout: {summary['timeout_seconds']} s. Each target replay uses the smaller of this value and its group limit.", ""]
    env = summary["environment"]
    lines.append(f"{env['system']} {env['release']}, {env['machine']}; Python {env['python']}; "
                 f"{env['logical_cpus']} logical CPUs.")
    lines += ["", "Replay RSS is the process high-water mark sampled during replay, including preloaded "
              "dependencies. It is not whole-run memory consumption.", "",
              "The portable summary contains hashes and measurements, without Lean source text or source paths. "
              "Raw verdict JSON and worker logs under `raw/` may contain local paths and compiler diagnostics; "
              "review them before sharing.", ""]
    return "\n".join(lines)


def _terminate_process_tree(process: subprocess.Popen) -> None:
    if os.name == "nt":
        # taskkill follows the process tree even when a Lean subprocess has no console.
        subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
    else:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            return
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        if os.name != "nt":
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        else:
            process.kill()
        process.wait()


def _run_worker(*, upstream: Path, source: Path, problem: str, timeout: int,
                output: Path, role: str) -> tuple[dict, float]:
    raw = output / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    verdict_path = raw / f"{role}.json"
    log_path = raw / f"{role}.log"
    # A stale raw result must never be mistaken for this attempt's verdict.
    verdict_path.unlink(missing_ok=True)
    env = os.environ.copy()
    package_root = str(Path(__file__).resolve().parent.parent)
    env["PYTHONPATH"] = package_root + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    command = [sys.executable, "-u", "-m", "lkc_bench.official", "--worker",
               "--upstream", str(upstream), "--source", str(source), "--problem", problem,
               "--timeout", str(timeout), "--verdict", str(verdict_path)]
    started = time.monotonic()
    print(f"[{role}] Running the canonical local evaluator; each stage has its own budget.", flush=True)
    with log_path.open("w", encoding="utf-8") as log:
        options = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt" else {"start_new_session": True}
        process = subprocess.Popen(command, cwd=upstream, env=env,
                                   stdout=log, stderr=subprocess.STDOUT, **options)
        last_progress = started
        try:
            while True:
                try:
                    code = process.wait(timeout=1)
                    break
                except subprocess.TimeoutExpired:
                    now = time.monotonic()
                    if now - last_progress >= 30:
                        elapsed = round(now - started)
                        print(f"[{role}] Still running ({elapsed} s).", flush=True)
                        _write_json(output / "progress.json", {"role": role, "status": "running", "elapsed_seconds": elapsed})
                        last_progress = now
        except BaseException as exc:
            _terminate_process_tree(process)
            _write_json(output / "progress.json", {
                "role": role, "status": "interrupted" if isinstance(exc, KeyboardInterrupt) else "error"})
            raise
    elapsed = time.monotonic() - started
    if not verdict_path.is_file():
        verdict = {"problem": problem, "status": "error", "harness_error": True,
                   "reason": f"Evaluator worker exited with code {code}; inspect its local log."}
        _write_json(verdict_path, verdict)
    else:
        try:
            verdict = json.loads(verdict_path.read_text(encoding="utf-8"))
            if not isinstance(verdict, dict):
                raise ValueError("verdict must be a JSON object")
            if code != 0:
                verdict["status"] = "error"
                verdict["harness_error"] = True
                _write_json(verdict_path, verdict)
        except (ValueError, OSError):
            verdict = {"problem": problem, "status": "error", "harness_error": True,
                       "reason": "Evaluator worker produced unreadable verdict JSON; inspect its local log."}
            _write_json(verdict_path, verdict)
    print(f"[{role}] Verdict: {verdict.get('status', 'error')} ({elapsed:.1f} s).", flush=True)
    return verdict, elapsed


def run_comparison(args: argparse.Namespace, upstream: Path, output: Path) -> dict:
    """Evaluate a public baseline, optionally a candidate, and save local reports."""
    upstream, output = Path(upstream).resolve(), Path(output).resolve()
    if args.problem not in _PROBLEMS or args.baseline not in ("example", "starter"):
        raise ValueError("Unsupported problem or baseline")
    if type(args.timeout) is not int or args.timeout <= 0:
        raise ValueError("timeout must be a positive integer")
    output.mkdir(parents=True, exist_ok=True)
    revision = subprocess.run(["git", "-C", str(upstream), "rev-parse", "HEAD"],
                              check=True, capture_output=True, text=True).stdout.strip()
    baseline_root = "examples" if args.baseline == "example" else "problems"
    sources = {"baseline": upstream / baseline_root / args.problem / "Submission.lean"}
    if args.submission is not None:
        sources["candidate"] = Path(args.submission).expanduser().resolve()
    summary = {
        "schema": "lkc-local-comparison-v1", "problem": args.problem,
        "created_utc": datetime.now(timezone.utc).isoformat(), "upstream_revision": revision,
        "baseline": args.baseline, "local_only": True, "timeout_seconds": args.timeout,
        "environment": {"system": platform.system(), "release": platform.release(),
                        "machine": platform.machine(), "python": platform.python_version(),
                        "logical_cpus": os.cpu_count()},
        "results": {}, "comparison": None, "status": "running", "complete": False,
    }
    _write_json(output / "summary.json", summary)
    for role, source in sources.items():
        # Snapshot once so the recorded hash identifies exactly the evaluated bytes,
        # even when the user edits their original file while the judge is running.
        # This copy lives outside the repository and is removed after evaluation.
        with tempfile.TemporaryDirectory(prefix="lkc-benchmark-source-") as temporary:
            snapshot = Path(temporary) / "Submission.lean"
            shutil.copyfile(source, snapshot)
            source_sha256 = _source_hash(snapshot)
            _write_json(output / "progress.json", {"role": role, "status": "running", "elapsed_seconds": 0})
            verdict, elapsed = _run_worker(upstream=upstream, source=snapshot, problem=args.problem,
                                           timeout=args.timeout, output=output, role=role)
        result = summarize_verdict(verdict, role=role, source_sha256=source_sha256, elapsed_seconds=elapsed)
        summary["results"][role] = result
        _write_json(output / "summary.json", summary)
    if "candidate" in summary["results"]:
        summary["comparison"] = compare_results(summary["results"]["baseline"], summary["results"]["candidate"])
    results = list(summary["results"].values())
    summary["complete"] = all(row["complete"] for row in results) and (
        summary["comparison"] is None or summary["comparison"]["comparable"])
    summary["status"] = ("complete" if summary["complete"] else "error" if any(
        row["status"] == "error" for row in results) else "incomplete")
    _write_json(output / "summary.json", summary)
    (output / "summary.md").write_text(render_markdown(summary), encoding="utf-8")
    _write_json(output / "progress.json", {"status": summary["status"], "complete": summary["complete"]})
    return summary


def _worker_main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Internal canonical-evaluator worker")
    parser.add_argument("--worker", action="store_true", required=True)
    parser.add_argument("--upstream", required=True, type=Path)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--problem", required=True, choices=_PROBLEMS)
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--verdict", required=True, type=Path)
    args = parser.parse_args(argv)
    if os.name != "nt":
        # The canonical judge starts each tool in another process group. Raising
        # here lets its finally blocks kill those groups before the worker exits.
        def interrupt_worker(signum: int, frame: Any) -> None:
            raise KeyboardInterrupt

        signal.signal(signal.SIGTERM, interrupt_worker)
    try:
        spec = importlib.util.spec_from_file_location("lkc_canonical_run", args.upstream / "evaluation" / "run.py")
        if spec is None or spec.loader is None:
            raise ImportError("Cannot load the canonical evaluator")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        print("Running evaluation/run.py evaluate_file().", flush=True)
        verdict = module.evaluate_file(args.source, args.timeout, problem=args.problem)
        _write_json(args.verdict, verdict)
        return 0
    except Exception as exc:
        _write_json(args.verdict, {"problem": args.problem, "status": "error",
                                  "harness_error": True, "reason": f"{type(exc).__name__}: {exc}"})
        print(f"Worker error: {type(exc).__name__}: {exc}", file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(_worker_main())
