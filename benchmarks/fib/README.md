# Fibonacci (`fib`)

Compute the exact Fibonacci number at index `n`, with F(0) = 0, F(1) = 1, and F(n + 2) = F(n) + F(n + 1). The return value is an arbitrary-precision natural number.

## Official Lean baseline

[Read the official public `Submission.lean`](official/Submission.lean). This is an unchanged copy of the organizers' pinned example and is the default comparison baseline. Its upstream path and SHA-256 are recorded in [baselines.lock.json](../../baselines.lock.json). It is distributed under [Apache-2.0](../../third_party/lean-kernel-challenge/LICENSE) and imports the fixed specification linked below.

## Interface

Declarations belong in `namespace Submission`:

```text
impl : Nat → Nat
impl_correct : ∀ n, impl n = Nat.fib n
```

The theorem must cover every natural-number input, including inputs outside the benchmark groups. Import the fixed `Spec` and preserve the exact theorem statement. All inputs are Lean function arguments; no standard-input protocol is involved.

## Input and output

`n` is the direct function argument. It is neither a count of bytes nor a packed input. The fixed target is Mathlib's `Nat.fib`; `fibSpec` is a compatibility abbreviation in the locked specification.

`impl 0 = 0`, `impl 1 = 1`, `impl 10 = 55`, and `impl 20 = 6765`.

## Naive specification cost

Linear (brecOn).

The input scale is `n`. The `brecOn` label identifies Lean's recursion mechanism in the naive specification. Arithmetic on the growing Fibonacci values also contributes to measured runtime.

The site's description is qualitative. It is not a formal complexity bound or a measured baseline runtime.

## Public performance groups

| Group | Input selection | Cases | Target replay limit per repetition |
| --- | --- | ---: | ---: |
| F1 | 5,000 through 10,000, inclusive | 2 | 30 s |
| F2 | 20,000 through 40,000, inclusive | 2 | 60 s |
| F3 | 80,000 through 150,000, inclusive | 2 | 120 s |

The canonical unseeded local plan uses the six range endpoints. The official schedule derives two distinct increasing inputs per group using inward jitter of up to 15% from a hidden cohort seed. Local endpoint results do not predict the hidden inputs.

The pinned whole-job memory policy is 4096 MiB and remains provisional in upstream documentation. The local comparison command does not enforce the official container memory limit. See [measurement and limits](../../docs/methodology.md).

`cases.json` records these groups for inspection. The pinned canonical evaluator resolves and validates the full comparison plan; this manifest does not replace its configuration.

## Dependencies

Lean 4.33.1 and the pinned Mathlib 4.33.1 dependency closure rooted at `Mathlib.Data.Nat.Fib.Basic`. Only modules admitted by the problem's dependency lock are available. Use the setup command below to prepare the fixed environment.

## Run a comparison

From the benchmark repository root:

```bash
python3 benchmark.py setup --problem fib
python3 benchmark.py compare --problem fib --submission /path/to/Submission.lean
```

The default baseline is the bundled [official public example](official/Submission.lean). Select `--baseline starter` to use the untouched starter downloaded from the same pinned revision. Omit `--submission` to measure the baseline alone. Both baselines may exceed performance limits.

This command runs the full canonical local evaluation with one wall-time replay per case. Check both the correctness verdict and full-plan eligibility. An accepted submission can still have failed cases and no computation total.

## Optional diagnostic

For a short check of the diagnostic setup:

```bash
python3 benchmark.py diagnostic --problem fib --submission /path/to/Submission.lean --inputs 0 1 10 --metric wall-time
```

To measure the default six inputs:

```bash
python3 benchmark.py diagnostic --problem fib --submission /path/to/Submission.lean --metric wall-time --repetitions 3
```

Default inputs: `5000, 10000, 20000, 40000, 80000, 150000`. Change them with `--inputs`. These exact-output diagnostics do not verify the universal correctness theorem. They provide local measurements under the separate [diagnostic methodology](../../docs/methodology.md#diagnostic-runs).

## Pinned upstream references

- [Problem statement](https://github.com/SAIRcompetition/lean-kernel-challenge/blob/eb5e8850cdec9acf52d615529f9d1d64894e44b9/rules/problems/fib.md)
- [Locked specification](https://github.com/SAIRcompetition/lean-kernel-challenge/blob/eb5e8850cdec9acf52d615529f9d1d64894e44b9/evaluation/problems/fib/Spec.lean)
- [Default public example baseline](https://github.com/SAIRcompetition/lean-kernel-challenge/blob/eb5e8850cdec9acf52d615529f9d1d64894e44b9/examples/fib/Submission.lean)
- [Untouched public starter baseline](https://github.com/SAIRcompetition/lean-kernel-challenge/blob/eb5e8850cdec9acf52d615529f9d1d64894e44b9/problems/fib/Submission.lean)
- [Canonical group configuration](https://github.com/SAIRcompetition/lean-kernel-challenge/blob/eb5e8850cdec9acf52d615529f9d1d64894e44b9/evaluation/problems/fib/config.json)
- [Dependency lock](https://github.com/SAIRcompetition/lean-kernel-challenge/blob/eb5e8850cdec9acf52d615529f9d1d64894e44b9/evaluation/problems/fib/dependency-lock.json)
- [Submission and scoring rules](../../docs/rules.md)
