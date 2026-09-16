"""Run local exact-output kernel diagnostics for the supported benchmark problems.

The runner compiles an upstream baseline and, optionally, a supplied submission.
For each input it creates a direct Eq.refl target, exports its dependency closure,
audits that export's axioms, and measures the official timer's target replay.
Python computes the expected outputs independently. Universal correctness and
submission eligibility are not checked by this mode. Callgrind counts are local
user-space instruction counts; PMU and wall-time results are also local results.
Process-tree RSS is sampled every 100 ms. The limit is a watchdog, not a sandbox.
All source copies, generated Lean files and measurement logs stay in output.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import platform
import re
import signal
import statistics
import subprocess
import sys
import time
import uuid

from .workspace import official_baseline


DEFAULT_INPUTS = {
    "fib": [5000, 10000, 20000, 40000, 80000, 150000],
    "partition": [14, 18, 22, 26, 32, 36],
    "mertens": [25, 50, 80, 150, 300, 500],
    "primecount": [50, 100, 150, 300, 600, 1000],
    "permanent": [
        28064292647, 26230790088, 26754739663, 28361232070, 29556043951,
        53794586207, 54079857374, 54224806958, 51875434732, 54751654040,
        71077100717, 72835838140, 72703668916, 70268834944, 69508517010,
    ],
}
DEFAULT_MEMORY_MB = {problem: 8192 if problem == "permanent" else 4096 for problem in DEFAULT_INPUTS}
TARGET_ENCODING = "direct-rfl-v1-experimental"
MEASUREMENT_CONTRACT = "kernel-replay-v2"
REPLAY_BOUNDARY = "target-declaration-replay-v1"
REPLAY_SYMBOL = "l_Lean_Environment_replay___boxed"
AXIOMS = "propext,Quot.sound,Classical.choice"
METRICS = {
    "wall-time": ("wall_ns", "ns"),
    "callgrind": ("ir", "instructions"),
    "pmu": ("instructions", "instructions"),
}


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def permanent_columns(dimension: int, seed: int) -> list[list[int]]:
    """Generate the enabled columns, using explicit exclusion lists for each row."""
    mask32 = (1 << 32) - 1

    def mix(value: int) -> int:
        value = ((value ^ (value >> 16)) * 0x7feb352d) & mask32
        value = ((value ^ (value >> 15)) * 0x846ca68b) & mask32
        return (value ^ (value >> 16)) & mask32

    rows = []
    for row in range(dimension):
        if dimension < 3:
            rows.append(list(range(dimension)))
            continue
        key = seed ^ (row * 0x9e3779b9)
        available = [column for column in range(dimension) if column != row]
        first = available[mix(key ^ 0x85ebca6b) % (dimension - 1)]
        available.remove(first)
        second = available[mix(key ^ 0xc2b2ae35) % (dimension - 2)]
        rows.append([row, first, second])
    return rows


def permanent_value(n: int) -> int:
    """Count injective row choices with one dynamic-programming layer per row."""
    dimension, seed = n >> 32, n & 0xffffffff
    states = {0: 1}
    for columns in permanent_columns(dimension, seed):
        following = {}
        for used, count in states.items():
            for column in columns:
                bit = 1 << column
                if not used & bit:
                    target = used | bit
                    following[target] = following.get(target, 0) + count
        states = following
    return states.get((1 << dimension) - 1, 0)


def expected_values(problem: str, inputs: list[int]) -> dict[int, int]:
    """Compute integer test answers without invoking the submitted Lean code."""
    if not inputs or any(isinstance(n, bool) or not isinstance(n, int) or n < 0 for n in inputs):
        raise ValueError("Inputs must be a nonempty list of natural numbers.")
    if problem == "permanent":
        return {n: permanent_value(n) for n in inputs}
    if problem == "fib":
        answers = {}
        for n in inputs:
            a, b = 0, 1
            for bit in bin(n)[2:]:
                c, d = a * (2 * b - a), a * a + b * b
                a, b = (d, c + d) if bit == "1" else (c, d)
            answers[n] = a
        return answers
    limit = max(inputs)
    if problem == "primecount":
        composite = bytearray(limit + 1)
        for prime in range(2, math.isqrt(limit) + 1):
            if not composite[prime]:
                start = prime * prime
                composite[start:limit + 1:prime] = b"\x01" * ((limit - start) // prime + 1)
        values, total = [0] * (limit + 1), 0
        for n in range(2, limit + 1):
            total += not composite[n]
            values[n] = total
        return {n: values[n] for n in inputs}
    if problem == "partition":
        values = [1] + [0] * limit
        for part in range(1, limit + 1):
            for index in range(part, limit + 1):
                values[index] += values[index - part]
        return {n: values[n] for n in inputs}
    if problem == "mertens":
        mu, composite, primes = [0] * (limit + 1), [False] * (limit + 1), []
        if limit:
            mu[1] = 1
        for n in range(2, limit + 1):
            if not composite[n]:
                primes.append(n)
                mu[n] = -1
            for prime in primes:
                product = n * prime
                if product > limit:
                    break
                composite[product] = True
                if n % prime == 0:
                    break
                mu[product] = -mu[n]
        values = [0] * (limit + 1)
        for n in range(1, limit + 1):
            values[n] = values[n - 1] + mu[n]
        return {n: values[n] for n in inputs}
    raise ValueError(f"Unsupported diagnostic problem: {problem}")


def target_source(n: int, value: int, target: str, output_type: str) -> str:
    if output_type == "Int":
        constructor, argument = ("Int.ofNat", value) if value >= 0 else ("Int.negSucc", -value - 1)
        rhs = f"Lean.mkApp (Lean.mkConst ``{constructor}) (Lean.mkNatLit {argument})"
    else:
        rhs = f"Lean.mkNatLit {value}"
    return (
        "import Submission\nimport Lean\n"
        "set_option maxRecDepth 4000000\nset_option maxHeartbeats 0\n"
        "open Lean Meta Elab in\nrun_meta do\n"
        "  let implC := Lean.mkConst ``Submission.impl\n"
        f"  let lhs := Lean.mkApp implC (Lean.mkNatLit {n})\n"
        "  let out \u2190 whnf (\u2190 inferType implC).bindingBody!\n"
        f"  unless out.isConstOf ``{output_type} do\n"
        '    throwError "unsupported impl output type {out}"\n'
        f"  let rhs := {rhs}\n"
        "  let ty \u2190 mkEq lhs rhs\n"
        "  let pf \u2190 mkEqRefl rhs\n"
        "  Lean.addDecl (.thmDecl {\n"
        f"    name := `{target},\n"
        "    levelParams := [], type := ty, value := pf })\n"
    )


def _raise_stack() -> None:
    import resource

    soft, hard = resource.getrlimit(resource.RLIMIT_STACK)
    if soft == resource.RLIM_INFINITY:
        return
    cap = 512 * 1024 * 1024 if hard == resource.RLIM_INFINITY else hard
    for target in (cap, cap - 1024 * 1024, 256 * 1024 * 1024, 64 * 1024 * 1024):
        if target <= soft:
            return
        try:
            resource.setrlimit(resource.RLIMIT_STACK, (target, hard))
            return
        except (ValueError, OSError):
            continue


def _tree_rss(pid: int) -> int:
    total, pending, seen = 0, [pid], set()
    while pending:
        current = pending.pop()
        if current in seen:
            continue
        seen.add(current)
        try:
            status = Path(f"/proc/{current}/status").read_text()
            match = re.search(r"^VmRSS:\s+(\d+)\s+kB", status, re.MULTILINE)
            if match:
                total += int(match.group(1))
            pending.extend(map(int, Path(f"/proc/{current}/task/{current}/children").read_text().split()))
        except (OSError, ValueError):
            continue
    return total


def _kill_group(process: subprocess.Popen) -> None:
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    process.wait()


def _step(command: list[str], *, cwd: Path, env: dict[str, str], log: Path,
          root: Path, timeout: float, memory_mb: int, stdout_path: Path | None = None) -> dict:
    started, peak, failure, process = time.monotonic(), 0, None, None
    with log.open("w", encoding="utf-8") as errors:
        output = stdout_path.open("w", encoding="utf-8") if stdout_path else errors
        try:
            process = subprocess.Popen(
                command, cwd=cwd, env=env, stdout=output, stderr=errors,
                start_new_session=True, preexec_fn=_raise_stack,
            )
            while process.poll() is None:
                rss = _tree_rss(process.pid)
                peak = max(peak, rss)
                remaining = timeout - (time.monotonic() - started)
                if rss > memory_mb * 1024:
                    failure = "memory-limit"
                elif remaining <= 0:
                    failure = "timeout"
                if failure:
                    _kill_group(process)
                    break
                try:
                    process.wait(timeout=min(0.1, remaining))
                except subprocess.TimeoutExpired:
                    pass
        except OSError as error:
            failure = "failed"
            errors.write(str(error) + "\n")
        finally:
            if process is not None and process.poll() is None:
                _kill_group(process)
            if stdout_path:
                output.close()
    return {
        "status": failure or ("complete" if process is not None and process.returncode == 0 else "failed"),
        "exit_code": process.returncode if process is not None else None,
        "elapsed_seconds": time.monotonic() - started,
        "peak_sampled_process_tree_rss_kb": peak,
        "log": log.relative_to(root).as_posix(),
        "log_sha256": _sha(log),
    }


def parse_timer(log: Path, target: str, metric: str) -> dict:
    records = [line.split("=", 1)[1] for line in log.read_text(encoding="utf-8", errors="replace").splitlines()
               if line.startswith("KERNEL_TIMING=")]
    if len(records) != 1:
        raise ValueError("Expected exactly one completed timer measurement.")
    record = json.loads(records[0])
    for field, expected in (("measurement_contract", MEASUREMENT_CONTRACT),
                            ("boundary", REPLAY_BOUNDARY), ("target", target), ("phase", "complete")):
        if record.get(field) != expected:
            raise ValueError(f"Unexpected timer {field}: {record.get(field)!r}")
    for field in (["wall_ns", "instructions"] if metric == "pmu" else ["wall_ns"]):
        if type(record.get(field)) is not int or record[field] <= 0:
            raise ValueError(f"Timer {field} must be a positive integer.")
    if record.get("peak_rss_kb") is not None and (
            type(record["peak_rss_kb"]) is not int or record["peak_rss_kb"] <= 0):
        raise ValueError("Timer peak_rss_kb must be null or a positive integer.")
    return record


def parse_callgrind(path: Path) -> int:
    data = path.read_text(encoding="utf-8", errors="replace")
    events = re.search(r"^events:\s+(.+)$", data, re.MULTILINE)
    summary = re.search(r"^summary:\s+([\d ]+)$", data, re.MULTILINE)
    if not events or not summary or "Ir" not in events.group(1).split():
        raise ValueError("Callgrind profile has no Ir event summary.")
    names, values = events.group(1).split(), summary.group(1).split()
    if len(names) != len(values):
        raise ValueError("Callgrind event and summary columns differ.")
    count = int(values[names.index("Ir")])
    symbol = re.search(r"^(?:c?fn)=\((\d+)\) " + re.escape(REPLAY_SYMBOL) + r"$", data, re.MULTILINE)
    entries = [] if not symbol else re.findall(
        r"^cfn=\(" + symbol.group(1) + r"\)(?: " + re.escape(REPLAY_SYMBOL)
        + r")?\ncalls=(\d+) ", data, re.MULTILINE)
    if count <= 0 or sum(map(int, entries)) != 1:
        raise ValueError("Callgrind must contain a positive Ir count and exactly one measured replay thunk call.")
    return count


def _write_report(output: Path, report: dict) -> None:
    temporary = output / "diagnostic.json.tmp"
    temporary.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    temporary.replace(output / "diagnostic.json")


def _summarize(report: dict) -> None:
    runs = {run["role"]: run for run in report["runs"]}
    report["complete"] = all(case["status"] == "complete" for run in runs.values() for case in run["cases"])
    report["totals"] = {
        role: sum(case["median"] for case in run["cases"])
        if all(case["status"] == "complete" for case in run["cases"]) else None
        for role, run in runs.items()
    }
    report["comparisons"] = []
    if "candidate" not in runs:
        return
    baseline = {case["n"]: case for case in runs["baseline"]["cases"]}
    candidate = {case["n"]: case for case in runs["candidate"]["cases"]}
    for n in report["inputs"]:
        old, new = baseline[n], candidate[n]
        row = {"n": n, "status": "unavailable", "baseline_over_candidate": None, "reduction_percent": None}
        if old["status"] == new["status"] == "complete":
            row.update(status="complete", baseline_over_candidate=old["median"] / new["median"],
                       reduction_percent=100 * (1 - new["median"] / old["median"]))
        report["comparisons"].append(row)
    report["total_baseline_over_candidate"] = (
        report["totals"]["baseline"] / report["totals"]["candidate"] if report["complete"] else None
    )


def _write_markdown(output: Path, report: dict) -> None:
    input_label = "Packed input (dimension, seed)" if report["problem"] == "permanent" else "Input"
    lines = [
        f"# {report['problem']} local diagnostic", "",
        f"Metric: `{report['metric']}`. Repetitions per input: {report['repetitions']}. "
        f"All requested measurements completed: {'yes' if report['complete'] else 'no'}.", "",
        "These results check selected exact outputs. Universal correctness and submission eligibility "
        "were not checked. This is not an official score or a complete hosted evaluation plan.", "",
        f"| Role | {input_label} | Status | Raw samples | Median | Unit |",
        "| --- | ---: | --- | --- | ---: | --- |",
    ]
    for run in report["runs"]:
        for case in run["cases"]:
            samples = ", ".join(str(sample["value"]) for sample in case["samples"] if sample.get("status") == "complete") or "n/a"
            median = str(case["median"]) if case.get("median") is not None else "n/a"
            status = case["status"] + (f" ({case['failure_phase']})" if case.get("failure_phase") else "")
            shown_input = (f"{case['n']} ({case['dimension']}, {case['seed']})"
                           if report["problem"] == "permanent" else str(case["n"]))
            lines.append(f"| {run['role']} | {shown_input} | {status} | {samples} | {median} | {report['unit']} |")
    if report["comparisons"]:
        lines += ["", "| Input | Baseline / candidate | Candidate reduction |", "| ---: | ---: | ---: |"]
        for row in report["comparisons"]:
            ratio = f"{row['baseline_over_candidate']:.6g}" if row["status"] == "complete" else "n/a"
            reduction = f"{row['reduction_percent']:.4f}%" if row["status"] == "complete" else "n/a"
            lines.append(f"| {row['n']} | {ratio} | {reduction} |")
        lines += ["", "A ratio above 1 means the candidate used less of the selected metric on that input. "
                  "Comparisons require every requested repetition for both sources."]
    lines += ["", "Totals are sums of input medians and are available only when every requested input completed.", ""]
    for role, total in report["totals"].items():
        lines.append(f"- {role}: {str(total) if total is not None else 'unavailable'} {report['unit']}")
    lines += ["", "Preparation, axiom audits, export parsing and dependency preload are outside the measured "
              "target replay. Callgrind's timer wall duration includes instrumentation overhead; use its Ir "
              "count for comparisons. RSS watchdog samples can miss short peaks and can count shared pages "
              "more than once. No container memory limit or sandbox is provided.", "",
              "[Full report and raw measurement records](diagnostic.json)", ""]
    (output / "diagnostic.md").write_text("\n".join(lines), encoding="utf-8")


def run_diagnostic(args, upstream: Path, output: Path) -> dict:
    """Write diagnostic.json and diagnostic.md in output and return the report."""
    if platform.system() != "Linux":
        raise ValueError("Measured diagnostics require Linux or WSL with procfs.")
    if args.problem not in DEFAULT_INPUTS or args.metric not in METRICS:
        raise ValueError("Unsupported diagnostic problem or metric.")
    if args.memory_mb is None:
        args.memory_mb = DEFAULT_MEMORY_MB[args.problem]
    if args.baseline not in ("example", "starter"):
        raise ValueError("Baseline must be example or starter.")
    if args.repetitions < 1 or not math.isfinite(args.timeout) or args.timeout <= 0 or args.memory_mb <= 0:
        raise ValueError("Repetitions, timeout and memory must be positive.")
    inputs = list(DEFAULT_INPUTS[args.problem] if args.inputs is None else args.inputs)
    if len(set(inputs)) != len(inputs):
        raise ValueError("Inputs must not contain duplicates.")
    values = expected_values(args.problem, inputs)
    if hasattr(sys, "set_int_max_str_digits"):
        sys.set_int_max_str_digits(0)
    upstream, output = upstream.resolve(), output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    if (output / "diagnostic.json").exists() or (output / "baseline").exists() or (output / "candidate").exists():
        raise ValueError("Choose a fresh output directory; existing diagnostic artifacts will not be overwritten.")
    package = upstream / "evaluation" / "problems" / args.problem
    fallback_export = Path(__file__).resolve().parents[1] / ".cache" / "repro" / "lean4export" / ".lake" / "build" / "bin"
    export_bin = Path(os.environ.get("LEAN4EXPORT_BIN", str(fallback_export))) / "lean4export"
    timer_bin = Path(os.environ.get("TIMER_BIN", str(upstream / "evaluation/judge/timer-kernel/.lake/build/bin/kernel")))
    export_bin, timer_bin = export_bin.resolve(), timer_bin.resolve()
    for path in (export_bin, timer_bin):
        if not path.is_file():
            raise ValueError(f"Required benchmark tool is missing: {path}. Run setup first.")
    env = dict(os.environ)
    env["LEAN_NUM_THREADS"] = "1"
    environment = _step(["lake", "env", "printenv", "LEAN_PATH"], cwd=package, env=env,
                        log=output / "lean-path.log", root=output, timeout=args.timeout,
                        memory_mb=args.memory_mb, stdout_path=output / "lean-path.txt")
    if environment["status"] != "complete":
        raise RuntimeError(f"Cannot resolve the prepared Lean environment; see {output / 'lean-path.log'}")
    lean_path = (output / "lean-path.txt").read_text(encoding="utf-8").strip()
    environment["lean_path_artifact"] = "lean-path.txt"
    report = {
        "schema": "lkc-local-diagnostic-v1", "problem": args.problem,
        "metric": args.metric, "metric_field": METRICS[args.metric][0], "unit": METRICS[args.metric][1],
        "inputs": inputs, "repetitions": args.repetitions, "complete": False,
        "target_proof_encoding": TARGET_ENCODING, "measurement_contract": MEASUREMENT_CONTRACT,
        "boundary": REPLAY_BOUNDARY, "universal_correctness_checked": False,
        "allowed_axioms": AXIOMS.split(","), "baseline": args.baseline,
        "limits": {"timeout_seconds_per_process": args.timeout, "memory_mb": args.memory_mb,
                   "memory_method": "process-tree RSS sampled every 100 ms; Lean -M during compilation",
                   "sandbox": False},
        "host": {"system": platform.system(), "release": platform.release(),
                 "machine": platform.machine(), "python": platform.python_version()},
        "toolchain": (package / "lean-toolchain").read_text(encoding="utf-8").strip(),
        "timer_sha256": _sha(timer_bin), "exporter_sha256": _sha(export_bin),
        "collection_symbol": REPLAY_SYMBOL if args.metric == "callgrind" else None,
        "environment": environment, "runs": [], "comparisons": [], "totals": {},
        "limitations": ["Selected-input diagnostics do not establish universal correctness or submission eligibility.",
                        "Local metrics do not reproduce official hosted scores or hidden input plans.",
                        "The timeout covers one whole tool process, including any untimed preparation.",
                        "RSS sampling is an approximate watchdog, not an enforced container memory limit."],
    }
    if args.problem == "permanent":
        report["input_encoding"] = "packed-v1: (dimension << 32) | seed"
        report["expected_output_method"] = "Independent Python matrix generator and subset dynamic programming"
    for tool in ("lean", "lake", *(["valgrind"] if args.metric == "callgrind" else [])):
        step = _step([tool, "--version"], cwd=package, env=env, log=output / f"{tool}-version.log",
                     root=output, timeout=args.timeout, memory_mb=args.memory_mb)
        if step["status"] != "complete":
            raise RuntimeError(f"Cannot run {tool}; see {output / step['log']}")
        report["host"][f"{tool}_version"] = (output / step["log"]).read_text(encoding="utf-8").strip()
    token = uuid.uuid4().hex
    targets = {n: f"LkcBench_{token}.case_{index}" for index, n in enumerate(inputs)}
    baseline = (official_baseline(args.problem) if args.baseline == "example"
                else upstream / "problems" / args.problem / "Submission.lean")
    sources = [("baseline", baseline)]
    if args.submission is not None:
        sources.append(("candidate", Path(args.submission).resolve()))
    for role, source in sources:
        print(f"{role}: compiling source", flush=True)
        work = output / role
        work.mkdir()
        copied = work / "Submission.lean"
        copied.write_bytes(source.read_bytes())
        record = {"role": role, "source_sha256": _sha(copied),
                  "source_artifact": copied.relative_to(output).as_posix(),
                  "cases": [{"n": n, "expected": str(values[n]), "target": targets[n],
                             "status": "pending", "samples": [], "median": None} for n in inputs]}
        if args.problem == "permanent":
            for case in record["cases"]:
                case.update(dimension=case["n"] >> 32, seed=case["n"] & 0xffffffff)
        report["runs"].append(record)
        local_env = dict(env)
        local_env["LEAN_PATH"] = str(work) + (os.pathsep + lean_path if lean_path else "")
        lean = ["lean", "-j", "1", "-M", str(args.memory_mb), "-D", "Elab.async=false", "-R", str(work)]
        def run(command, log, stdout_path=None):
            return _step(command, cwd=package, env=local_env, log=work / log, root=output,
                         timeout=args.timeout, memory_mb=args.memory_mb, stdout_path=stdout_path)
        record["compile"] = run([*lean, "-o", str(work / "Submission.olean"), str(copied)], "submission-compile.log")
        if record["compile"]["status"] == "complete":
            record["olean_sha256"] = _sha(work / "Submission.olean")
        else:
            for case in record["cases"]:
                case.update(status=record["compile"]["status"], failure_phase="submission-compile")
            print(f"{role}: source compilation {record['compile']['status']}", flush=True)
            _write_report(output, report)
            continue
        for case in record["cases"]:
            n, target = case["n"], case["target"]
            print(f"{role}: input {n}, preparing target", flush=True)
            generated = work / "Target.lean"
            generated.write_text(target_source(n, values[n], target, "Int" if args.problem == "mertens" else "Nat"), encoding="utf-8")
            saved_source = work / f"target-{n}.lean"
            saved_source.write_bytes(generated.read_bytes())
            exported = work / f"target-{n}.ndjson"
            case["generated_source"] = saved_source.relative_to(output).as_posix()
            case["generated_source_sha256"] = _sha(saved_source)
            phases = [
                ("target-compile", [*lean, "-o", str(work / "Target.olean"), str(generated)], None),
                ("target-export", [str(export_bin), "Target", "--", target], exported),
                ("axiom-audit", [str(timer_bin), "--check-axioms", AXIOMS, str(exported)], None),
            ]
            case["preparation"] = {}
            for phase, command, stdout_path in phases:
                result = run(command, f"{phase}-{n}.log", stdout_path)
                case["preparation"][phase] = result
                if result["status"] != "complete":
                    case.update(status=result["status"], failure_phase=phase)
                    break
            if case["status"] != "pending":
                print(f"{role}: input {n}, {case['status']} during {case['failure_phase']}", flush=True)
                _write_report(output, report)
                continue
            case.update(export=exported.relative_to(output).as_posix(), export_sha256=_sha(exported))
            for repetition in range(args.repetitions):
                log = f"replay-{n}-{repetition + 1}.log"
                command = [str(timer_bin)] + (["--count-instructions"] if args.metric == "pmu" else [])
                command += ["--target", target, str(exported)]
                profile = work / f"callgrind-{n}-{repetition + 1}.out"
                if args.metric == "callgrind":
                    command = ["valgrind", "--tool=callgrind", "--collect-atstart=no",
                               f"--toggle-collect={REPLAY_SYMBOL}", f"--callgrind-out-file={profile}", *command]
                sample = {"repetition": repetition + 1, "process": run(command, log)}
                sample["status"] = sample["process"]["status"]
                if sample["status"] == "complete":
                    try:
                        sample["timer"] = parse_timer(work / log, target, args.metric)
                        sample["value"] = parse_callgrind(profile) if args.metric == "callgrind" else sample["timer"][METRICS[args.metric][0]]
                        if args.metric == "callgrind":
                            sample.update(profile=profile.relative_to(output).as_posix(), profile_sha256=_sha(profile))
                    except (ValueError, OSError, KeyError) as error:
                        sample.update(status="failed", error=str(error))
                case["samples"].append(sample)
                if sample["status"] != "complete":
                    case.update(status=sample["status"], failure_phase="target-replay")
                    break
                _write_report(output, report)
            if case["status"] == "pending":
                case.update(status="complete", median=statistics.median(sample["value"] for sample in case["samples"]))
            suffix = f", median {case['median']} {report['unit']}" if case["status"] == "complete" else ""
            print(f"{role}: input {n}, {case['status']}{suffix}", flush=True)
            _write_report(output, report)
    _summarize(report)
    _write_report(output, report)
    _write_markdown(output, report)
    return report
