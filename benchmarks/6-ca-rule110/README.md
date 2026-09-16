# Rule 110 cellular automaton (`ca-rule110`)

Evolve a seeded cyclic row of 256 Boolean cells using Rule 110, then return the final row as a natural-number bit vector.

## Official Lean baseline

[Read the official public `Submission.lean`](official/Submission.lean). This is an unchanged copy of the organizers' pinned example and is the default comparison baseline. Its upstream path and SHA-256 are recorded in [baselines.lock.json](../../baselines.lock.json). It is distributed under [Apache-2.0](../../third_party/lean-kernel-challenge/LICENSE) and imports the fixed specification linked below.

## Interface

Declarations belong in `namespace Submission`:

```text
impl : Nat → Nat
impl_correct : ∀ n, impl n = caSpecN n
```

The theorem must cover every natural-number input, including inputs outside the benchmark groups. Import the fixed `Spec` and preserve the exact theorem statement. All inputs are Lean function arguments; no standard-input protocol is involved.

## Input and output

Decode `steps = n >> 32` and `seed = n & 0xffffffff`; pack with `(steps << 32) | seed` for a 32-bit seed. Each simultaneous update reads the left neighbor, current cell, and right neighbor, with indices modulo 256. In neighborhood order 111, 110, 101, 100, 011, 010, 001, 000, the next bits are 0, 1, 1, 0, 1, 1, 1, 0.

The initial cells 0 and 1 are true and false. For `i >= 2`, cell `i` is bit 31 of `caMix32(seed + (i + 1) * 0x9e3779b9)`. The fixed specification defines the 32-bit mixer. Its argument is a natural number: the sum is not truncated before the mixer's first xor and shift. The result places cell `i` at bit `i`, with cell zero least significant and no bits above 255. Zero steps returns the seeded initial row.

Input `4294967297` means one step with seed 1. Its output is `62412942364118713680778432052760708221590981514164502482365323362230212198349`.

## Naive specification cost

Linear in steps, list-based.

The scale is the decoded step count, with the row width fixed at 256 cells. The naive specification updates a list of cells at each step. The packed input also contains the seed and is not itself the step count.

The site's description is qualitative. It is not a formal complexity bound or a measured baseline runtime.

## Public performance groups

| Group | Input selection | Cases | Target replay limit per repetition |
| --- | --- | ---: | ---: |
| C1 | 2 steps; distinct 32-bit seeds | 2 | 30 s |
| C2 | 4 steps; distinct 32-bit seeds | 2 | 60 s |
| C3 | 8 steps; distinct 32-bit seeds | 2 | 120 s |

The official schedule selects distinct 32-bit seeds within each group. The canonical evaluator derives a deterministic schedule for local unseeded runs. The diagnostic defaults use its six empty-key inputs, recorded in [cases.json](cases.json):

| Group | Packed input | Steps | Seed |
| --- | ---: | ---: | ---: |
| C1 | 12551916119 | 2 | 3961981527 |
| C1 | 10588838281 | 2 | 1998903689 |
| C2 | 18550129185 | 4 | 1370260001 |
| C2 | 18418222002 | 4 | 1238352818 |
| C3 | 34820276714 | 8 | 460538346 |
| C3 | 38244662432 | 8 | 3884924064 |

The pinned whole-job memory policy is 4096 MiB and remains provisional in upstream documentation. The local comparison command does not enforce the official container memory limit. See [measurement and limits](../../docs/methodology.md).

`cases.json` records these groups for inspection. The pinned canonical evaluator resolves and validates the full comparison plan; this manifest does not replace its configuration.

## Dependencies

Core Lean 4.33.1, without Mathlib. Keep the fixed specification and package files unchanged. The benchmark setup still builds the shared evaluator tools.

## Run a comparison

From the benchmark repository root:

```bash
python3 benchmark.py setup --problem ca-rule110
python3 benchmark.py compare --problem ca-rule110 --submission /path/to/Submission.lean
```

The default baseline is the bundled [official public example](official/Submission.lean). Select `--baseline starter` to use the untouched starter downloaded from the same pinned revision. Omit `--submission` to measure the baseline alone. Both baselines may exceed performance limits.

This command runs the full canonical local evaluation with one wall-time replay per case. Check both the correctness verdict and full-plan eligibility. An accepted submission can still have failed cases and no computation total.

## Run diagnostics

After setup, measure the official example on all six local public inputs:

```bash
python3 benchmark.py diagnostic --problem ca-rule110 --metric wall-time
```

Use `--submission /path/to/Submission.lean` to include your file. Select `--metric callgrind` for local instruction counts or `--metric pmu` on a host that permits hardware counting. A smaller check includes three seeds at zero steps and the one-step example:

```bash
python3 benchmark.py diagnostic --problem ca-rule110 \
  --inputs 0 1 2 4294967297 --metric wall-time --repetitions 1
```

Expected outputs come from an independent Python simulation of 256 Boolean cells with the Rule 110 truth table. Reports retain the exact natural-number output, decoded steps and seed, raw replay samples, and failed cases. The default process-tree memory watchdog is 4096 MiB; override it with `--memory-mb`. Diagnostic limits and measurements are described in [the methodology](../../docs/methodology.md). These selected-output checks do not establish the universal theorem or an official score.

## Pinned upstream references

- [Problem statement](https://github.com/SAIRcompetition/lean-kernel-challenge/blob/eb5e8850cdec9acf52d615529f9d1d64894e44b9/rules/problems/ca-rule110.md)
- [Locked specification](https://github.com/SAIRcompetition/lean-kernel-challenge/blob/eb5e8850cdec9acf52d615529f9d1d64894e44b9/evaluation/problems/ca-rule110/Spec.lean)
- [Default public example baseline](https://github.com/SAIRcompetition/lean-kernel-challenge/blob/eb5e8850cdec9acf52d615529f9d1d64894e44b9/examples/ca-rule110/Submission.lean)
- [Untouched public starter baseline](https://github.com/SAIRcompetition/lean-kernel-challenge/blob/eb5e8850cdec9acf52d615529f9d1d64894e44b9/problems/ca-rule110/Submission.lean)
- [Canonical group configuration](https://github.com/SAIRcompetition/lean-kernel-challenge/blob/eb5e8850cdec9acf52d615529f9d1d64894e44b9/evaluation/problems/ca-rule110/config.json)
- [Submission and scoring rules](../../docs/rules.md)
