"""Command-line interface for benchmark setup and comparisons."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
import uuid

from .workspace import ROOT, UPSTREAM, PROBLEMS, BENCHMARK_DIRS, doctor, runtime_environment, setup
from .diagnostic import DEFAULT_INPUTS, DEFAULT_MEMORY_MB


def positive_int(value: str) -> int:
    number = int(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return number


def natural(value: str) -> int:
    number = int(value)
    if number < 0:
        raise argparse.ArgumentTypeError("must be a natural number")
    return number


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Per-problem benchmarks against pinned upstream examples. Local measurements are not official scores.")
    commands = result.add_subparsers(dest="command", required=True)
    commands.add_parser("list", help="List problems and available benchmark modes")
    install = commands.add_parser("setup", help="Fetch and build the pinned public evaluator in .cache")
    install.add_argument("--problem", choices=PROBLEMS, action="append", help="Repeat for several problems; default: all eight")
    install.add_argument("--fetch-only", action="store_true", help="Fetch pinned sources without building tools")
    check = commands.add_parser("doctor", help="Check the selected problem's local prerequisites and tool hashes")
    check.add_argument("--problem", choices=PROBLEMS, required=True)
    check.add_argument("--metric", choices=("wall-time", "callgrind", "pmu"), default="wall-time")
    for name, description in (("compare", "Complete public plan through the upstream local evaluator"),
                              ("diagnostic", "Selected exact-output targets with detailed local measurements")):
        command = commands.add_parser(name, help=description, description=description)
        command.add_argument("--problem", choices=PROBLEMS if name == "compare" else tuple(DEFAULT_INPUTS), required=True)
        command.add_argument("--submission", type=Path, help="Your local Submission.lean; omit to benchmark the upstream baseline only")
        command.add_argument("--baseline", choices=("example", "starter"), default="example")
        command.add_argument("--timeout", type=positive_int, default=120, help="Per-step timeout in seconds, not a total runtime limit (default: 120)")
        command.add_argument("--output", type=Path, help="New output directory; default: results/PROBLEM/TIMESTAMP-ID")
        if name == "diagnostic":
            command.add_argument("--metric", choices=("wall-time", "callgrind", "pmu"), default="wall-time")
            command.add_argument("--inputs", type=natural, nargs="+", help="Exact natural-number inputs; default: documented endpoints or packed cases from the public local plan")
            command.add_argument("--repetitions", type=positive_int, default=3)
            command.add_argument("--memory-mb", type=positive_int,
                                 help="Process RSS watchdog and Lean allocation limit; default: 8192 for permanent, 4096 otherwise")
    return result


def main(argv: list[str] | None = None) -> int:
    arguments = parser()
    args = arguments.parse_args(argv)
    try:
        if args.command == "list":
            for problem in PROBLEMS:
                config = ROOT / "benchmarks" / BENCHMARK_DIRS[problem] / "cases.json"
                title = json.loads(config.read_text(encoding="utf-8"))["title"] if config.exists() else problem
                modes = "compare, diagnostic" if problem in DEFAULT_INPUTS else "compare"
                print(f"{BENCHMARK_DIRS[problem]:14} {title:28} {modes}")
            return 0
        if args.command == "setup":
            setup(list(dict.fromkeys(args.problem or PROBLEMS)), args.fetch_only)
            return 0
        runtime_environment()
        if args.command == "doctor":
            details = doctor(args.problem, args.metric)
            print(json.dumps(details, indent=2))
            return 0 if details.get("pmu", {}).get("available", True) else 1
        if args.submission is not None:
            args.submission = args.submission.expanduser().resolve()
            if not args.submission.is_file() or args.submission.suffix.lower() != ".lean":
                arguments.error("--submission must be an existing .lean file")
            if args.submission.stat().st_size > 1048576:
                arguments.error("--submission exceeds the 1 MiB limit")
        if args.command == "diagnostic":
            if sys.platform != "linux":
                arguments.error("diagnostic measurements require Linux or WSL")
            if args.inputs is None:
                config = json.loads((ROOT / "benchmarks" / BENCHMARK_DIRS[args.problem] / "cases.json").read_text(encoding="utf-8"))
                args.inputs = config["diagnostic_inputs"]
            if args.memory_mb is None:
                args.memory_mb = DEFAULT_MEMORY_MB[args.problem]
            if len(set(args.inputs)) != len(args.inputs):
                arguments.error("--inputs must not contain duplicates")
        environment = doctor(args.problem, getattr(args, "metric", "wall-time"))
        if args.command == "diagnostic" and args.metric == "pmu" and not environment["pmu"]["available"]:
            print(json.dumps(environment["pmu"], indent=2), file=sys.stderr)
            raise RuntimeError("PMU preflight failed before compiling source. See docs/pmu.md.")
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        output = (args.output or ROOT / "results" / args.problem / f"{stamp}-{uuid.uuid4().hex[:8]}").expanduser().resolve()
        output.mkdir(parents=True, exist_ok=False)
        manifest = {"schema": "lkc-benchmark-run-v1", "created_at": stamp, "mode": args.command,
                    "environment": environment,
                    "options": {name: value for name, value in vars(args).items() if name not in ("submission", "output")}}
        (output / "run.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        print(f"Results: {output}", flush=True)
        if args.command == "compare":
            from .official import run_comparison
            report = run_comparison(args, UPSTREAM, output)
        else:
            from .diagnostic import run_diagnostic
            report = run_diagnostic(args, UPSTREAM, output)
        print(f"Completed: {'yes' if report.get('complete') else 'no'}. Results: {output}")
        return 0 if report.get("complete") else 2 if report.get("status") == "error" else 1
    except KeyboardInterrupt:
        print("Interrupted. Completed artifacts remain in the output directory.", file=sys.stderr)
        return 130
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
