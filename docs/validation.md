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

## Rule 110 diagnostics

The Python suite checks the documented one-step example, zero-step initialization, seeds 0 and 0xffffffff, and agreement with a second implementation using integer rotations and a Boolean identity. It also checks the full `Nat` output in generated targets, decoded steps and seed in Markdown, the six default inputs, and the 4096 MiB default through the CLI. All 67 tests pass on WSL; native Windows passes 66 and skips the POSIX process-group test.

The independent cell simulation agrees with the pinned official reference on 51 inputs: all six local public cases and steps 0 through 8 with seeds 0, 1, 0x12345678, 0x80000000 and 0xffffffff. The six defaults also match the pinned evaluator's empty-key sampler. The publication check passes for all 52 files and verifies the eight unchanged official Lean source hashes.

The public CLI completed this wall-time smoke check against the bundled official example:

```bash
python3 benchmark.py setup --problem ca-rule110
python3 benchmark.py diagnostic --problem ca-rule110 \
  --inputs 0 1 2 4294967297 --metric wall-time --repetitions 1 \
  --output results/rule110-public-smoke
```

All four targets compiled, passed the export axiom audit, and completed one kernel replay each. Input `4294967297` returned the documented exact 256-bit output. The JSON report records steps and seed for every input, the expected natural-number output, and the default 4096 MiB watchdog. Setup reused the pinned shared tools and built Rule 110's fixed `Spec` in the managed cache.

## SHA-256 diagnostics

The Python tests check the documented one-step example, zero-step initialization, seed extremes, and big-endian byte order. A seed-2 digest begins with a zero byte; a two-step fixture checks that the byte survives into the next hash input. Seed expansion is also checked against the closed form of the LCG.

Expected outputs agree with the pinned official reference on 42 inputs: all six local public cases and steps 0, 1, 2, 4, 32 and 512 with seeds 0, 1, 2, 0x12345678, 0x80000000 and 0xffffffff. The six defaults match the pinned evaluator's empty-key sampler. The publication check passes for all 52 files and verifies the eight unchanged official Lean source hashes.

The public CLI completed this wall-time smoke check against the bundled official example:

```bash
python3 benchmark.py setup --problem sha256
python3 benchmark.py diagnostic --problem sha256 \
  --inputs 0 4294967295 4294967297 4294967298 \
  --metric wall-time --repetitions 1 --timeout 120 \
  --output results/sha256-public-smoke
```

All four targets compiled, passed the export axiom audit, and completed one kernel replay each. The check covers zero steps with seeds 0 and 0xffffffff, and one step with seeds 1 and 2. Input `4294967297` returned the documented exact output. The JSON report retains outputs as decimal strings, decoded steps and seed, and the default 4096 MiB watchdog. Setup reused the pinned shared tools and built SHA-256's fixed `Spec` in the managed cache.

A separate run of all six default SHA-256 inputs, with one wall-time replay per input and the default 4096 MiB watchdog, completed the four cases at 4 and 32 steps. Both 512-step cases exceeded the memory limit during target compilation. The report in `results/sha256-public-plan` records those preparation failures and leaves the full-plan total unavailable.

The preparation-memory option is covered by tests that drive both baseline and candidate through the diagnostic runner. They check that only target compilation and export receive the larger cap, both Lean compilation commands use the correct `-M` value, and source or replay failures still leave totals unavailable. All 78 tests pass on WSL; native Windows passes 77 and skips the POSIX process-group test.

The public CLI then completed all six inputs with a larger preparation allowance:

```bash
python3 benchmark.py diagnostic --problem sha256 --metric wall-time \
  --repetitions 1 --timeout 120 --preparation-memory-mb 8192 \
  --output results/sha256-public-plan-preparation8192
```

All six targets passed the export axiom audit and completed one kernel replay. Source compilation, axiom audits and replay retained the default 4096 MiB watchdog. Target compilation and export used 8192 MiB. For the two 512-step cases, sampled process-tree RSS peaked at about 4893 MiB during target compilation and 3390 MiB during replay. The JSON and Markdown reports record the separate limits. These are local wall-time diagnostics of the unchanged official example, not an official score.
