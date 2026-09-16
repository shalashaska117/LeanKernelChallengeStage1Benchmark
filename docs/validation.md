# Validation

The initial release was checked on 2026-09-16 using the revision in `upstream.lock.json`.

The Python suite covers independent expected answers, measurement parsing, incomplete runs, comparison eligibility, local report privacy, interrupted setup recovery, source and baseline pins, and PMU error handling. Linux tests also exercise cleanup of a worker's nested tool process group after interruption.

Functional checks used public upstream files only:

- A fresh managed setup built the pinned comparator, exporter, timer, and partition specification.
- The canonical full partition baseline evaluation was accepted and completed all six cases, including correctness replay.
- Wall-time diagnostics completed partition inputs 0, 1, and 5 with three repetitions each.
- Callgrind diagnostics compared the public partition example with a second copy of the same public example on inputs 0 and 5. Every requested sample, profile check, and comparison completed.
- The PMU failure path preserved unavailable measurements. The standalone probe distinguishes permission denial from unavailable hardware without loading a submission.
- Per-problem manifest sampling, limits, and memory settings match all eight pinned upstream configurations.

These checks concern the harness. Complete benchmark runs for all eight problems and successful hardware PMU counting have not been verified on this host. The remaining problem comparisons delegate to the same pinned canonical evaluator; their runtime and resource demands depend on the problem and source.

Run the suite with:

```bash
python3 -m unittest discover -s tests -v
python3 scripts/check_release.py
```

The release check verifies the eight official Lean examples against their pinned hashes and checks the publication file list. The default checks staged blobs; `--worktree` checks intended files before staging. It complements review of the diff.

## Prime-counting diagnostics

The Python suite includes independent prime-counting answers for every input from 0 through 1000 and checks the publication file filter.

The unchanged public CLI also completed this prime-counting smoke check against the bundled official example:

```bash
python3 benchmark.py diagnostic --problem primecount --inputs 0 1 2 \
  --metric wall-time --repetitions 1 --timeout 120 --memory-mb 3072 \
  --output results/primecount-public-runner-native-packages-smoke
```

All three exact-output targets compiled, passed the export axiom audit, and completed one kernel replay each. This checks the added diagnostic branch against the unchanged official example.

The smoke check reused prepared dependencies with matching package pins and artifact hashes, including `Spec`, on WSL's native filesystem. It did not repeat a fresh setup. Earlier attempts using mounted dependency paths reached the per-process timeout during dependency loading; those reports remain incomplete. The timeout includes environment preparation and dependency loading, while the reported replay metric measures only the target replay. After the successful run, the temporary native cache links were restored to durable paths.

## Matrix-permanent diagnostics

The Python suite checks the subset-DP answers against exhaustive permutations for dimensions 0 through 7 with four seeds, including 0 and 0xffffffff. It also checks all 15 public-plan answers, the packed `Nat` target, and propagation of default and overridden CLI limits into the run manifest.

The independent generator and answers were compared with the pinned official reference on 51 inputs: all 15 local public cases and dimensions 0 through 8 with seeds 0, 1, 0x12345678 and 0xffffffff. The 15 default inputs match the original evaluator's unseeded sampler. All eight bundled official source hashes still match the lock.

The 61-test suite passes on WSL. On native Windows, 60 tests pass and the POSIX process-group test is skipped.

The public CLI completed a wall-time smoke check against the bundled official example:

```bash
python3 benchmark.py diagnostic --problem permanent \
  --inputs 0 4294967296 8589934592 12884901888 28064292647 \
  --repetitions 1 --output results/permanent-public-smoke
```

All five targets compiled, passed the export axiom audit, and completed one kernel replay each. Their outputs were 1, 1, 2, 6 and 8. The run used the default 8192 MiB watchdog, the existing pinned tools, and a freshly built permanent `Spec` in the managed cache. It checks dimensions 0, 1, 2, 3 and one public dimension-6 instance.
