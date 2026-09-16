#!/usr/bin/env python3
"""Reject source submissions and generated artifacts in the tracked release tree."""
from pathlib import Path, PurePosixPath
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
ROOT_FILES = {".gitignore", ".gitattributes", "README.md", "CONTRIBUTING.md", "LICENSE", "NOTICE.md",
              "benchmark.py", "upstream.lock.json", "baselines.lock.json"}


def allowed(path: str) -> bool:
    item = PurePosixPath(path)
    if path in ROOT_FILES:
        return True
    if len(item.parts) == 2 and item.parts[0] in ("lkc_bench", "tests", "scripts") and item.suffix == ".py":
        return True
    if len(item.parts) == 2 and item.parts[0] == "docs" and item.suffix == ".md":
        return True
    return (len(item.parts) == 3 and item.parts[0] == "benchmarks"
            and item.name in ("README.md", "cases.json"))


def main() -> int:
    result = subprocess.run(["git", "ls-files", "--stage", "-z"], cwd=ROOT, capture_output=True, check=True)
    failures = []
    count = 0
    for entry in result.stdout.decode("utf-8").split("\0"):
        if not entry:
            continue
        metadata, path = entry.split("\t", 1)
        count += 1
        if metadata.split()[0] not in ("100644", "100755") or not allowed(path):
            failures.append(path)
    if not count:
        print("No tracked files. Stage the intended release files before this check.", file=sys.stderr)
        return 1
    if failures:
        print("Unexpected tracked publication files:\n" + "\n".join(failures), file=sys.stderr)
        return 1
    print(f"Checked {count} tracked files: benchmark code, guides, configuration, and tests only.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
