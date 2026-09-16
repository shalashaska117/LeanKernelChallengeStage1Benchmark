# Lean Kernel Challenge Stage 1 benchmark

Local benchmarks for testing your Lean Kernel Challenge submission against the public upstream baseline for the same problem. Each problem has a guide with its rules, input format, test groups, and limits.

The eight official public examples are included in `benchmarks/<number>-<problem>/official/Submission.lean` and linked below. They are unchanged copies of `examples/<problem>/Submission.lean` from the [organizers' pinned repository](https://github.com/SAIRcompetition/lean-kernel-challenge/tree/eb5e8850cdec9acf52d615529f9d1d64894e44b9). The default baseline uses this bundled source and verifies its SHA-256 against [baselines.lock.json](baselines.lock.json). `--baseline starter` selects the participant starter downloaded from the same revision. These references do not claim to be the fastest submissions on the website.

This repository contains benchmark tools, documentation, and the eight official public baselines. Use `--submission` to test a Lean file against the corresponding baseline.

## Start with one problem

Use Linux or Ubuntu under WSL, Python 3.10+, Git, [elan](https://github.com/leanprover/elan), and a C/C++ build toolchain. The pinned evaluator uses Lean 4.33.1. See [setup](docs/setup.md) for installation and troubleshooting.

```bash
git clone https://github.com/shalashaska117/LeanKernelChallengeStage1Benchmark.git
cd LeanKernelChallengeStage1Benchmark
python3 benchmark.py setup --problem partition
python3 benchmark.py doctor --problem partition
```

First run a small baseline-only check:

```bash
python3 benchmark.py diagnostic --problem partition --inputs 0 1 5
```

Compare your file with the upstream example on the complete public plan:

```bash
python3 benchmark.py compare --problem partition \
  --submission /path/to/Submission.lean
```

Omit `--submission` to measure only the baseline. The file must use the problem's exact `Submission.impl` and `Submission.impl_correct` interface. Setup downloads dependencies into `.cache/`; each run creates a new directory under `results/<problem>/`.

## Problems

The numbered folders follow the order below. Use the ID column with `--problem`.

| Problem | ID | Official Lean source | Full public comparison | Detailed diagnostics |
| --- | --- | --- | --- | --- |
| [Fibonacci](benchmarks/1-fib/README.md) | `fib` | [Submission.lean](benchmarks/1-fib/official/Submission.lean) | Available | Wall time, Callgrind, PMU |
| [Integer partitions](benchmarks/2-partition/README.md) | `partition` | [Submission.lean](benchmarks/2-partition/official/Submission.lean) | Available | Wall time, Callgrind, PMU |
| [Mertens function](benchmarks/3-mertens/README.md) | `mertens` | [Submission.lean](benchmarks/3-mertens/official/Submission.lean) | Available | Wall time, Callgrind, PMU |
| [Prime counting](benchmarks/4-primecount/README.md) | `primecount` | [Submission.lean](benchmarks/4-primecount/official/Submission.lean) | Available | Wall time, Callgrind, PMU |
| [Matrix permanent](benchmarks/5-permanent/README.md) | `permanent` | [Submission.lean](benchmarks/5-permanent/official/Submission.lean) | Available | Wall time, Callgrind, PMU |
| [Rule 110](benchmarks/6-ca-rule110/README.md) | `ca-rule110` | [Submission.lean](benchmarks/6-ca-rule110/official/Submission.lean) | Available | Planned |
| [SHA-256](benchmarks/7-sha256/README.md) | `sha256` | [Submission.lean](benchmarks/7-sha256/official/Submission.lean) | Available | Planned |
| [Polynomial discriminant](benchmarks/8-polydisc/README.md) | `polydisc` | [Submission.lean](benchmarks/8-polydisc/official/Submission.lean) | Available | Planned |

`python3 benchmark.py list` lists the supported modes. Guides and `cases.json` files are separate for each problem. The pinned upstream evaluator determines the full comparison plan; diagnostic inputs are an explicit local selection.

## Naive specification costs

| Problem | Site description |
| --- | --- |
| Fibonacci | Linear (brecOn) |
| Integer partitions | Approximately p(n) · n |
| Mertens function | Quadratic |
| Prime counting | Quadratic |
| Seeded matrix permanent | Exponential in dimension (pruned DFS) |
| Rule 110 cellular automaton | Linear in steps, list-based |
| Seeded SHA-256 chains | Linear in steps, word-per-Nat |
| Polynomial discriminant | Normal subresultant PRS; reduced Bareiss fallback |

These descriptions refer to the naive specification. Each problem guide explains the relevant input scale. They are qualitative descriptions, not measured baseline runtimes or formal complexity bounds; an official example can use a different evaluation method.

## Choose the measurement

`compare` calls the upstream local evaluator separately for the baseline and your file. It checks the interface, universal proof, and axioms, then attempts the complete unseeded public plan with one wall-time measurement per case. Read the completion result as well as acceptance: an accepted submission can have failed or unattempted cases. Full runs can take a long time, and a baseline can exceed the limits.

`diagnostic` prepares exact-output targets for selected Fibonacci, partition, Mertens, prime-counting, or matrix-permanent inputs and measures kernel target replay. It keeps individual samples, export hashes, step logs, and per-case failures. It checks the selected output equalities and exported axioms; it does not verify the universal correctness theorem.

Matrix-permanent inputs pack a dimension and seed as `(dimension << 32) | seed`. Its default diagnostic uses all 15 cases from the pinned evaluator's unseeded local plan and an 8192 MiB memory watchdog. Other diagnostic problems use six documented endpoints and a 4096 MiB watchdog. Override these defaults with `--inputs` and `--memory-mb`; see the [permanent guide](benchmarks/5-permanent/README.md#run-diagnostics) for an example.

```bash
# Repeated kernel wall-time measurements on selected inputs.
python3 benchmark.py diagnostic --problem partition \
  --submission /path/to/Submission.lean --inputs 14 18 22 \
  --repetitions 3 --metric wall-time

# Instrumented instruction counts, useful when hardware counters are unavailable.
python3 benchmark.py diagnostic --problem partition \
  --submission /path/to/Submission.lean --inputs 14 18 \
  --metric callgrind --timeout 600

# Hardware instruction counts, if Linux permits access to the PMU.
python3 benchmark.py doctor --problem partition --metric pmu
python3 benchmark.py diagnostic --problem partition \
  --submission /path/to/Submission.lean --inputs 14 18 --metric pmu
```

Wall seconds, Callgrind `Ir`, and PMU instruction counts are different metrics. Local measurements do not establish a website score or rank. The official score uses the sum of per-case median instruction counts over three replays, with every required case and check passing. See [rules](docs/rules.md) and [measurement details](docs/methodology.md).

PMU mode checks counter access before compiling a submission. The [PMU guide](docs/pmu.md) explains permission failures and hosts that do not expose hardware counters. `python3 -m lkc_bench.pmu` runs the probe without installing Lean or opening a submission.

## Read the results

The terminal prints the output directory. Each run includes `run.json` with the upstream revision, tool hashes, machine details, and options. Full comparisons write `summary.md` and `summary.json`; diagnostics write `diagnostic.md` and `diagnostic.json`. Detailed local artifacts remain alongside them.

A baseline/candidate ratio greater than 1 means the candidate used less of that metric on the compared input. Missing or failed measurements have no ratio. Incomplete full comparisons have no total ratio. See [report interpretation](docs/results.md).

Exit code `0` means the requested benchmark completed, `1` means incomplete measurements, and `2` means a setup or harness error. An interrupted command exits with `130`.

## Rules and contributions

Read the [general rules](docs/rules.md) and your problem's guide before interpreting results. The organizers' current rules govern competition submissions; this repository documents the revision in [upstream.lock.json](upstream.lock.json).

Benchmark additions should include their input policy, measurement limits, and tests. See [contribution guidance](CONTRIBUTING.md). The benchmark tools are under the [MIT license](LICENSE). The bundled official Lean files are under [Apache-2.0](third_party/lean-kernel-challenge/LICENSE); see [third-party sources](NOTICE.md) for their provenance.

See [validation](docs/validation.md) for the checks completed on the initial release and their scope.
