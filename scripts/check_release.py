#!/usr/bin/env python3
"""Allow pinned official baselines; reject other submissions and generated artifacts."""
import hashlib
import json
from pathlib import Path, PurePosixPath
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
ROOT_FILES = {".gitignore", ".gitattributes", "README.md", "CONTRIBUTING.md", "LICENSE", "NOTICE.md",
              "benchmark.py", "upstream.lock.json", "baselines.lock.json"}
PROBLEMS = ("fib", "partition", "mertens", "primecount", "permanent", "ca-rule110", "sha256", "polydisc")
OFFICIAL_BASELINES = {f"benchmarks/{problem}/official/Submission.lean": problem for problem in PROBLEMS}


def allowed(path: str) -> bool:
    item = PurePosixPath(path)
    if path in ROOT_FILES:
        return True
    if path in OFFICIAL_BASELINES or path == "third_party/lean-kernel-challenge/LICENSE":
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
    blobs = {}
    for entry in result.stdout.decode("utf-8").split("\0"):
        if not entry:
            continue
        metadata, path = entry.split("\t", 1)
        count += 1
        mode, object_id, stage = metadata.split()
        blobs[path] = object_id
        if mode not in ("100644", "100755") or stage != "0" or not allowed(path):
            failures.append(path)
    if not count:
        print("No tracked files. Stage the intended release files before this check.", file=sys.stderr)
        return 1
    # Read staged blobs, so an unstaged worktree edit cannot hide a bad commit.
    def staged(path):
        return subprocess.run(["git", "cat-file", "blob", blobs[path]], cwd=ROOT,
                              capture_output=True, check=True).stdout
    try:
        pins = json.loads(staged("upstream.lock.json"))
        references = json.loads(staged("baselines.lock.json"))
        if references["upstream_revision"] != pins["revision"]:
            failures.append("baselines.lock.json: upstream revision mismatch")
        for path, problem in OFFICIAL_BASELINES.items():
            record = references["baselines"][problem]["example"]
            if (path not in blobs or record.get("bundled_path") != path
                    or record["path"] != f"examples/{problem}/Submission.lean"
                    or hashlib.sha256(staged(path)).hexdigest() != record["sha256"]):
                failures.append(f"{path}: missing or does not match its official source hash")
        if "third_party/lean-kernel-challenge/LICENSE" not in blobs:
            failures.append("third_party/lean-kernel-challenge/LICENSE: missing")
    except (KeyError, ValueError, subprocess.CalledProcessError) as error:
        failures.append(f"Cannot verify staged baseline provenance: {error}")
    if failures:
        print("Unexpected tracked publication files:\n" + "\n".join(failures), file=sys.stderr)
        return 1
    print(f"Checked {count} tracked files, including 8 hash-verified official baselines; no other submission files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
