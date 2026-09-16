# Mertens function (`mertens`)

Compute the signed sum of the Möbius function through `n`: M(n) = μ(1) + ... + μ(n), with M(0) = 0.

## Official Lean baseline

[Read the official public `Submission.lean`](official/Submission.lean). This is an unchanged copy of the organizers' pinned example and is the default comparison baseline. Its upstream path and SHA-256 are recorded in [baselines.lock.json](../../baselines.lock.json). It is distributed under [Apache-2.0](../../third_party/lean-kernel-challenge/LICENSE) and imports the fixed specification linked below.

## Interface

Declarations belong in `namespace Submission`:

```text
impl : Nat → Int
impl_correct : ∀ n, impl n = mertensSpec n
```

The theorem must cover every natural-number input, including inputs outside the benchmark groups. Import the fixed `Spec` and preserve the exact theorem statement. All inputs are Lean function arguments; no standard-input protocol is involved.

## Input and output

The bound is inclusive. Mathlib's `ArithmeticFunction.moebius` is 1 at 1, zero at 0 and on numbers divisible by a prime square, and otherwise (-1)^r for r distinct prime factors. The locked sum includes zero, which contributes zero. Return an `Int`; negative values must keep their sign.

`impl 0 = 0`, `impl 1 = 1`, `impl 2 = 0`, `impl 5 = -2`, and `impl 10 = -1`.

## Naive specification cost

Quadratic.

The input scale is `n`, the upper limit of the Mertens sum. The quadratic label describes the naive specification across that range; it is not a bound on every valid implementation.

The site's description is qualitative. It is not a formal complexity bound or a measured baseline runtime.

## Public performance groups

| Group | Input selection | Cases | Target replay limit per repetition |
| --- | --- | ---: | ---: |
| M1 | 25 through 50, inclusive | 2 | 30 s |
| M2 | 80 through 150, inclusive | 2 | 60 s |
| M3 | 300 through 500, inclusive | 2 | 120 s |

The canonical unseeded local plan uses the six range endpoints. The official schedule derives two distinct increasing inputs per group using inward jitter of up to 15% from a hidden cohort seed. Local endpoint results do not predict the hidden inputs.

The pinned whole-job memory policy is 4096 MiB and remains provisional in upstream documentation. The local comparison command does not enforce the official container memory limit. See [measurement and limits](../../docs/methodology.md).

`cases.json` records these groups for inspection. The pinned canonical evaluator resolves and validates the full comparison plan; this manifest does not replace its configuration.

## Dependencies

Lean 4.33.1 and the pinned Mathlib 4.33.1 dependency closure rooted at `Mathlib.NumberTheory.ArithmeticFunction.Moebius`. Only modules admitted by the problem's dependency lock are available. Use the setup command below to prepare the fixed environment.

## Run a comparison

From the benchmark repository root:

```bash
python3 benchmark.py setup --problem mertens
python3 benchmark.py compare --problem mertens --submission /path/to/Submission.lean
```

The default baseline is the bundled [official public example](official/Submission.lean). Select `--baseline starter` to use the untouched starter downloaded from the same pinned revision. Omit `--submission` to measure the baseline alone. Both baselines may exceed performance limits.

This command runs the full canonical local evaluation with one wall-time replay per case. Check both the correctness verdict and full-plan eligibility. An accepted submission can still have failed cases and no computation total.

## Optional diagnostic

For a short check of the diagnostic setup:

```bash
python3 benchmark.py diagnostic --problem mertens --submission /path/to/Submission.lean --inputs 0 1 5 --metric wall-time
```

To measure the default six inputs:

```bash
python3 benchmark.py diagnostic --problem mertens --submission /path/to/Submission.lean --metric wall-time --repetitions 3
```

Default inputs: `25, 50, 80, 150, 300, 500`. Change them with `--inputs`. These exact-output diagnostics do not verify the universal correctness theorem. They provide local measurements under the separate [diagnostic methodology](../../docs/methodology.md#diagnostic-runs).

## Pinned upstream references

- [Problem statement](https://github.com/SAIRcompetition/lean-kernel-challenge/blob/eb5e8850cdec9acf52d615529f9d1d64894e44b9/rules/problems/mertens.md)
- [Locked specification](https://github.com/SAIRcompetition/lean-kernel-challenge/blob/eb5e8850cdec9acf52d615529f9d1d64894e44b9/evaluation/problems/mertens/Spec.lean)
- [Default public example baseline](https://github.com/SAIRcompetition/lean-kernel-challenge/blob/eb5e8850cdec9acf52d615529f9d1d64894e44b9/examples/mertens/Submission.lean)
- [Untouched public starter baseline](https://github.com/SAIRcompetition/lean-kernel-challenge/blob/eb5e8850cdec9acf52d615529f9d1d64894e44b9/problems/mertens/Submission.lean)
- [Canonical group configuration](https://github.com/SAIRcompetition/lean-kernel-challenge/blob/eb5e8850cdec9acf52d615529f9d1d64894e44b9/evaluation/problems/mertens/config.json)
- [Dependency lock](https://github.com/SAIRcompetition/lean-kernel-challenge/blob/eb5e8850cdec9acf52d615529f9d1d64894e44b9/evaluation/problems/mertens/dependency-lock.json)
- [Submission and scoring rules](../../docs/rules.md)
