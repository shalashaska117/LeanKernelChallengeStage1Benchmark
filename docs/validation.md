# Validation of the initial release

The initial release was checked on 2026-09-16 using the revision in `upstream.lock.json`.

The Python suite covers independent expected answers, measurement parsing, incomplete runs, comparison eligibility, local report privacy, interrupted setup recovery, source and baseline pins, and PMU error handling. Linux tests also exercise cleanup of a worker's nested tool process group after interruption.

Functional checks used public upstream files only:

- A fresh managed setup built the pinned comparator, exporter, timer, and partition specification.
- The canonical full partition baseline evaluation was accepted and completed all six cases, including correctness replay.
- Wall-time diagnostics completed partition inputs 0, 1, and 5 with three repetitions each.
- Callgrind diagnostics compared the public partition example with a second copy of the same public example on inputs 0 and 5. Every requested sample, profile check, and comparison completed.
- The PMU failure path preserved unavailable measurements. The standalone probe distinguishes permission denial from unavailable hardware without loading a submission.
- Per-problem manifest sampling, limits, and memory settings match all eight pinned upstream configurations.

These are functional checks. No participant result or performance ranking is included. Complete benchmark runs for all eight problems and successful hardware PMU counting have not been verified on this host. The remaining problem comparisons delegate to the same pinned canonical evaluator; their runtime and resource demands depend on the problem and source.

Run the suite with:

```bash
python3 -m unittest discover -s tests -v
python3 scripts/check_release.py
```

The release check permits only the eight official Lean examples at their listed paths and verifies their contents against the pinned SHA-256 hashes. It rejects other tracked Lean files, generated targets, caches, local reports, and files outside the publication file list. It complements review of the staged diff.
