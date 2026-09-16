"""Prepare a dedicated checkout of the pinned public evaluator."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import platform
import shlex
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
PROBLEMS = ("fib", "partition", "mertens", "primecount", "permanent", "ca-rule110", "sha256", "polydisc")
BENCHMARK_DIRS = {problem: f"{number}-{problem}" for number, problem in enumerate(PROBLEMS, start=1)}
CACHE = ROOT / ".cache"
UPSTREAM = CACHE / "upstream"
TOOLS = CACHE / "repro"


def lock() -> dict:
    return json.loads((ROOT / "upstream.lock.json").read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def capture(command: list[str], cwd: Path | None = None) -> str:
    result = subprocess.run(command, cwd=cwd, capture_output=True, text=True, check=False)
    if result.returncode:
        raise RuntimeError(f"Command failed: {' '.join(command)}\n{result.stderr[-4000:]}")
    return result.stdout.strip()


def official_baseline(problem: str) -> Path:
    """Return the bundled upstream example after checking its pinned content."""
    if problem not in PROBLEMS:
        raise ValueError(f"Unsupported problem: {problem}")
    references = json.loads((ROOT / "baselines.lock.json").read_text(encoding="utf-8"))
    if references["upstream_revision"] != lock()["revision"]:
        raise RuntimeError("Baseline hashes refer to a different upstream revision.")
    record = references["baselines"][problem]["example"]
    relative = f"benchmarks/{BENCHMARK_DIRS[problem]}/official/Submission.lean"
    source = ROOT / relative
    if (record.get("bundled_path") != relative or source.is_symlink()
            or not source.resolve().is_relative_to(ROOT) or not source.is_file()
            or sha256(source) != record["sha256"]):
        raise RuntimeError(f"Bundled official baseline hash mismatch: {problem}")
    return source


def _managed_cache() -> None:
    # Upstream setup resets its tool checkouts. Only give it our own cache.
    if CACHE.is_symlink() or CACHE.resolve() != ROOT / ".cache":
        raise RuntimeError("The managed .cache directory must not be a symlink or junction.")
    marker = CACHE / ".benchmark-managed"
    if CACHE.exists() and not marker.is_file() and any(CACHE.iterdir()):
        raise RuntimeError("Existing .cache is not managed by this tool. Move it aside before setup.")
    CACHE.mkdir(exist_ok=True)
    marker.write_text("Managed benchmark downloads and builds.\n", encoding="utf-8")
    for directory in (UPSTREAM, TOOLS, TOOLS / "comparator", TOOLS / "lean4export"):
        if directory.is_symlink() or not directory.resolve().is_relative_to(CACHE):
            raise RuntimeError(f"Managed dependency path escapes .cache: {directory.name}")


def validate_upstream() -> dict:
    pins = lock()
    if not (UPSTREAM / ".git").is_dir():
        raise RuntimeError("Run `python3 benchmark.py setup --problem PROBLEM` first.")
    actual = capture(["git", "rev-parse", "HEAD"], UPSTREAM)
    if actual != pins["revision"]:
        raise RuntimeError(f"Upstream revision mismatch: expected {pins['revision']}, found {actual}.")
    dirty = capture(["git", "status", "--porcelain", "--untracked-files=no"], UPSTREAM)
    if dirty:
        raise RuntimeError("Tracked files in the managed upstream checkout changed. Restore them before benchmarking.\n" + dirty)
    config = json.loads((UPSTREAM / "evaluation/config.json").read_text(encoding="utf-8"))["toolchain"]
    actual_pins = (config["lean"], config["comparator_rev"], config["lean4export_rev"])
    expected_pins = (pins["lean"], pins["comparator_revision"], pins["lean4export_revision"])
    if actual_pins != expected_pins:
        raise RuntimeError("The upstream toolchain configuration differs from upstream.lock.json.")
    references = json.loads((ROOT / "baselines.lock.json").read_text(encoding="utf-8"))
    if references["upstream_revision"] != actual:
        raise RuntimeError("Baseline hashes refer to a different upstream revision.")
    for problem in PROBLEMS:
        for label, folder in (("example", "examples"), ("starter", "problems")):
            record = references["baselines"][problem][label]
            relative = f"{folder}/{problem}/Submission.lean"
            if record["path"] != relative or sha256(UPSTREAM / relative) != record["sha256"]:
                raise RuntimeError(f"Public baseline hash mismatch: {problem}/{label}")
        official_baseline(problem)
    return pins


def require_platform() -> None:
    if sys.platform == "win32":
        raise RuntimeError("Run setup and benchmarks inside Linux or WSL. Native Windows supports list, help, and tests only.")


def tool_paths() -> dict[str, Path]:
    return {
        "COMPARATOR_BIN": TOOLS / "comparator/.lake/build/bin/comparator",
        "LEAN4EXPORT_BIN": TOOLS / "lean4export/.lake/build/bin",
        "TIMER_BIN": UPSTREAM / "evaluation/judge/timer-kernel/.lake/build/bin/kernel",
    }


def runtime_environment() -> None:
    # All runs use this checkout's tools, independent of a caller's judge configuration.
    for name in list(os.environ):
        if (name.startswith(("TIMING_", "PERF_", "EVALUATION_", "SAIR_"))
                or name in {"OFFICIAL_EVAL", "DEFER_TIMING", "SANDBOX_MODE", "SHIM_DIR",
                            "ISOLATION_ATTESTATION", "LEAN_PATH", "LEAN_SRC_PATH", "LEAN_SYSROOT",
                            "ELAN_TOOLCHAIN", "COMPARATOR_LEAN4EXPORT"}):
            os.environ.pop(name, None)
    os.environ.update({name: str(path) for name, path in tool_paths().items()})
    os.environ["TIMING_METRIC"] = "wall_time"
    os.environ["LEAN_NUM_THREADS"] = "1"


def setup(problems: list[str], fetch_only: bool = False) -> None:
    require_platform()
    for program in (["git"] if fetch_only else ["git", "bash", "elan", "lake", "cc", "c++"]):
        if shutil.which(program) is None:
            raise RuntimeError(f"Missing prerequisite: {program}. See docs/setup.md.")
    _managed_cache()
    pins = lock()
    if not UPSTREAM.exists():
        UPSTREAM.mkdir()
    if not (UPSTREAM / ".git").exists():
        if any(UPSTREAM.iterdir()):
            raise RuntimeError("The managed upstream directory is nonempty but has no Git checkout.")
        subprocess.run(["git", "init", "--quiet"], cwd=UPSTREAM, check=True)
    subprocess.run(["git", "config", "core.autocrlf", "false"], cwd=UPSTREAM, check=True)
    origin = subprocess.run(["git", "remote", "get-url", "origin"], cwd=UPSTREAM, capture_output=True, text=True)
    if origin.returncode:
        subprocess.run(["git", "remote", "add", "origin", pins["repository"]], cwd=UPSTREAM, check=True)
    elif origin.stdout.strip() != pins["repository"]:
        raise RuntimeError("Managed upstream remote does not match upstream.lock.json.")
    head = subprocess.run(["git", "rev-parse", "--verify", "HEAD"], cwd=UPSTREAM, capture_output=True)
    if head.returncode:
        if any(item.name != ".git" for item in UPSTREAM.iterdir()):
            raise RuntimeError("An unfinished upstream checkout contains files. Inspect it before retrying setup.")
        subprocess.run(["git", "-c", "core.autocrlf=false", "fetch", "--depth", "1", "origin", pins["revision"]], cwd=UPSTREAM, check=True)
        subprocess.run(["git", "-c", "core.autocrlf=false", "checkout", "--quiet", "--detach", "FETCH_HEAD"], cwd=UPSTREAM, check=True)
    validate_upstream()
    if fetch_only:
        print(f"Fetched upstream {pins['revision']}.")
        return
    env = dict(os.environ)
    env["TOOLS_DIR"] = str(TOOLS)
    for name in ("LEAN_PATH", "LEAN_SRC_PATH", "LEAN_SYSROOT", "ELAN_TOOLCHAIN"):
        env.pop(name, None)
    # GCC 15 defaults to C23, whose glibc scanf symbols are absent from Lean's
    # bundled linker sysroot. Build upstream's C helper as GNU C17 on all hosts.
    cc = shutil.which("cc")
    shims = CACHE / "build-bin"
    shims.mkdir(exist_ok=True)
    shim = shims / "cc"
    shim_text = f'#!/bin/sh\nexec {shlex.quote(cc)} -std=gnu17 "$@"\n'
    if not shim.exists() or shim.read_text(encoding="utf-8") != shim_text:
        shim.write_text(shim_text, encoding="utf-8")
        shim.chmod(0o755)
        # Invalidate only the known generated C outputs, never tracked source.
        build = UPSTREAM / "evaluation/judge/timer-kernel/.lake/build"
        for relative in ("c/timer_control.o", "c/timer_control.o.trace",
                         "lib/liblean_kernel_timer_control.a", "lib/liblean_kernel_timer_control.a.trace"):
            artifact = build / relative
            if not artifact.resolve().is_relative_to(CACHE):
                raise RuntimeError("Timer build artifact escapes the managed cache.")
            artifact.unlink(missing_ok=True)
    env["PATH"] = str(shims) + os.pathsep + env.get("PATH", os.defpath)
    build_info = {"c_standard": "gnu17", "c_compiler": capture([cc, "--version"]).splitlines()[0]}
    (CACHE / "build-info.json").write_text(json.dumps(build_info, indent=2) + "\n", encoding="utf-8")
    command = ["bash", "evaluation/setup.sh"]
    for problem in problems:
        command.extend(["--problem", problem])
    subprocess.run(command, cwd=UPSTREAM, env=env, check=True)
    for problem in problems:
        subprocess.run(["lake", "build", "Spec"], cwd=UPSTREAM / "evaluation/problems" / problem, env=env, check=True)
    validate_upstream()
    print("Setup complete for: " + ", ".join(problems))


def doctor(problem: str, metric: str = "wall-time") -> dict:
    require_platform()
    pins = validate_upstream()
    missing = []
    for name, path in tool_paths().items():
        binary = path / "lean4export" if name == "LEAN4EXPORT_BIN" else path
        if not binary.is_file() or not os.access(binary, os.X_OK):
            missing.append(name)
    for program in ("lean", "lake", "git"):
        if shutil.which(program) is None:
            missing.append(program)
    if metric == "callgrind" and shutil.which("valgrind") is None:
        missing.append("valgrind")
    package = UPSTREAM / "evaluation/problems" / problem
    if not (package / ".lake/build/lib/lean/Spec.olean").is_file():
        missing.append(f"{problem} Spec.olean")
    if missing:
        raise RuntimeError("Missing setup outputs: " + ", ".join(missing) + f". Run setup --problem {problem}.")
    version = capture(["lean", "--version"], package)
    if "version 4.33.1" not in version:
        raise RuntimeError(f"Unexpected Lean version: {version}")
    result = {"problem": problem, "upstream_revision": pins["revision"], "lean_version": version,
            "python_version": platform.python_version(), "platform": platform.system(),
            "kernel_release": platform.release(), "architecture": platform.machine(),
            "build": json.loads((CACHE / "build-info.json").read_text(encoding="utf-8")),
            "tools": {name: sha256(path / "lean4export" if name == "LEAN4EXPORT_BIN" else path)
                      for name, path in tool_paths().items()}}
    if metric == "pmu":
        from .pmu import probe_pmu
        result["pmu"] = probe_pmu()
    return result
