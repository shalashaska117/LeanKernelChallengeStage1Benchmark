# Setup

Run all commands from the repository root unless a command explicitly changes directory. The supported measurement environment is Linux, including Ubuntu under WSL. The upstream local evaluator also documents macOS support, but this wrapper's diagnostic mode requires Linux. Native Windows can run the Python tests and list commands.

## Prerequisites

The wrapper requires Python 3.10 or later and uses only the standard library. Install Git, Bash, a C/C++ compiler, `make`, and elan. On Ubuntu:

```bash
sudo apt-get update
sudo apt-get install python3 git build-essential curl ca-certificates
```

Install elan using its [official installation instructions](https://github.com/leanprover/elan#installation). Make sure `elan`, `lean`, and `lake` are on your shell's `PATH`. The checkout's `lean-toolchain` selects Lean 4.33.1 automatically; no global default toolchain is required.

Callgrind is optional:

```bash
sudo apt-get install valgrind
```

On Windows, install Ubuntu under WSL and run the setup commands in its shell. A checkout in the Linux filesystem usually builds faster than one under `/mnt/c`. Use Linux paths for `--submission`, for example `/mnt/c/work/Submission.lean`.

## Download and build

```bash
python3 benchmark.py setup --problem partition
python3 benchmark.py doctor --problem partition
```

Setup creates a managed `.cache/` directory, fetches the exact commit in `upstream.lock.json`, builds the upstream comparator, exporter, and kernel timer, then builds the selected problem's specification. Fibonacci, Mertens, and prime counting also need the pinned Mathlib import closure. Initial downloads and builds can take several minutes and use several GiB of disk and memory.

The timer's C helper is compiled with `-std=gnu17` through a local compiler wrapper. This avoids a C23 `__isoc23_sscanf` linker failure with newer system compilers and Lean's bundled sysroot. Upstream source is unchanged. `run.json` records the compiler version, C standard, and resulting binary hashes.

To prepare several problems or all eight:

```bash
python3 benchmark.py setup --problem fib --problem mertens
python3 benchmark.py setup
```

The official examples are already included in `benchmarks/<number>-<problem>/official/Submission.lean`. You can read them without running setup. They import the problem's fixed `Spec`; use the benchmark commands to run them with the correct environment.

`setup --fetch-only` downloads the fixed upstream source without compiling it. It is useful for inspecting the specification, starter, evaluator, and rules, but does not prepare a runnable benchmark.

Setup owns `.cache/upstream/` and `.cache/repro/`. The upstream setup script resets its managed tool checkouts before applying the pinned comparator patch. Keep work you edit outside `.cache/`. The wrapper refuses to use a modified tracked upstream checkout or an existing non-managed cache.

Run setup before starting measurements, and avoid overlapping benchmark runs when comparing wall time. `baselines.lock.json` records the public example's bundled and upstream paths and the starter's upstream path, with hashes for both. The wrapper checks the selected baseline before each benchmark. Keep bundled official files unchanged; copy a baseline into `submissions/` before editing it.

## Supply a submission

Pass an existing `.lean` file:

```bash
python3 benchmark.py compare --problem sha256 \
  --submission /path/to/Submission.lean
```

Only the selected file is passed to the evaluator. Sibling modules and a custom Lake project are not included. Imports must be available in the problem's fixed environment. The source must fit within 1 MiB.

For a scratch copy of the official starter:

```bash
mkdir -p submissions/partition
cp .cache/upstream/problems/partition/Submission.lean submissions/partition/Submission.lean
```

Edit that local copy, then supply its path. `submissions/`, `.cache/`, and `results/` are ignored by Git. The release check verifies the exact content of the eight bundled official Lean examples.

Local evaluation executes Lean code without the competition's container isolation. Run files you trust. The `compare` command does not enforce the official container memory cap. Diagnostic memory monitoring is described in [methodology](methodology.md).

## Troubleshooting

- If `doctor` reports a missing binary or `Spec.olean`, rerun setup for that problem. A partial build is not a completed setup.
- If Lean reports no default toolchain when invoked outside the checkout, use the benchmark command from this repository. The wrapper runs Lean inside the pinned package.
- If PMU access fails, the preflight reports whether the counter could be opened before compiling source. Use the [PMU guide](pmu.md) to distinguish permissions from missing hardware support. The wrapper does not change counter permissions.
- If a step times out, its measurement remains missing. Increase `--timeout` for a local investigation. On full comparisons, target replay still uses the smaller of that timeout and the group's limit; some audit budgets remain fixed upstream.
- If a full run says accepted but incomplete, inspect the per-case results and correctness replay. Acceptance alone does not provide a complete total.
- If the pinned checkout has tracked modifications, inspect them before restoring or replacing the cache. The benchmark does not silently reset your changes.

The wrapper selects its own cached tools and local wall-time judge configuration. Environment overrides for official cohorts, hidden seeds, remote timing, and reduced plans are removed before running. Use the organizers' deployment workflow separately if you need their official evaluation environment.
