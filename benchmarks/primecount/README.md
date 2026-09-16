# Prime counting (`primecount`)

Count the primes less than or equal to `n`. The locked `primeCountSpec` targets Mathlib's `Nat.primeCounting`.

## Official Lean baseline

[Read the official public `Submission.lean`](official/Submission.lean). This is an unchanged copy of the organizers' pinned example and is the default comparison baseline. Its upstream path and SHA-256 are recorded in [baselines.lock.json](../../baselines.lock.json). It is distributed under [Apache-2.0](../../third_party/lean-kernel-challenge/LICENSE) and imports the fixed specification linked below.

## Interface

Declarations belong in `namespace Submission`:

```text
impl : Nat → Nat
impl_correct : ∀ n, impl n = primeCountSpec n
```

The theorem must cover every natural-number input, including inputs outside the benchmark groups. Import the fixed `Spec` and preserve the exact theorem statement. All inputs are Lean function arguments; no standard-input protocol is involved.

## Input and output

`n` is an inclusive upper bound passed directly to the function. Neither zero nor one is prime. Return the exact number of primes as a `Nat`.

`impl 0 = 0`, `impl 1 = 0`, `impl 2 = 1`, `impl 10 = 4`, and `impl 50 = 15`.

## Naive specification cost

Quadratic.

The input scale is `n`, the inclusive upper limit of the prime count. The quadratic label describes the naive specification. The official example uses a different primality test, so the label should not be assigned to its measured runtime.

The site's description is qualitative. It is not a formal complexity bound or a measured baseline runtime.

## Public performance groups

| Group | Input selection | Cases | Target replay limit per repetition |
| --- | --- | ---: | ---: |
| Q1 | 50 through 100, inclusive | 2 | 30 s |
| Q2 | 150 through 300, inclusive | 2 | 60 s |
| Q3 | 600 through 1,000, inclusive | 2 | 120 s |

The canonical unseeded local plan uses the six range endpoints. The official schedule derives two distinct increasing inputs per group using inward jitter of up to 15% from a hidden cohort seed. Local endpoint results do not predict the hidden inputs.

The pinned whole-job memory policy is 4096 MiB and remains provisional in upstream documentation. The local comparison command does not enforce the official container memory limit. See [measurement and limits](../../docs/methodology.md).

`cases.json` records these groups for inspection. The pinned canonical evaluator resolves and validates the full comparison plan; this manifest does not replace its configuration.

## Dependencies

Lean 4.33.1 and the pinned Mathlib 4.33.1 dependency closure rooted at `Mathlib.NumberTheory.PrimeCounting`. Only modules admitted by the problem's dependency lock are available. Use the setup command below to prepare the fixed environment.

## Run a comparison

From the benchmark repository root:

```bash
python3 benchmark.py setup --problem primecount
python3 benchmark.py compare --problem primecount --submission /path/to/Submission.lean
```

The default baseline is the bundled [official public example](official/Submission.lean). Select `--baseline starter` to use the untouched starter downloaded from the same pinned revision. Omit `--submission` to measure the baseline alone. Both baselines may exceed performance limits.

This command runs the full canonical local evaluation with one wall-time replay per case. Check both the correctness verdict and full-plan eligibility. An accepted submission can still have failed cases and no computation total.

The diagnostic mode checks selected outputs against an independent Python sieve of Eratosthenes and measures exact-output kernel target replay:

```bash
python3 benchmark.py diagnostic --problem primecount --inputs 0 1 2 10 50
python3 benchmark.py diagnostic --problem primecount --submission /path/to/Submission.lean \
  --inputs 50 100 150 300 600 1000 --metric callgrind --repetitions 3 --timeout 600
```

The default diagnostic inputs are the six endpoints above. Diagnostics do not check the universal correctness theorem; use `compare` for that check.

## Pinned upstream references

- [Problem statement](https://github.com/SAIRcompetition/lean-kernel-challenge/blob/eb5e8850cdec9acf52d615529f9d1d64894e44b9/rules/problems/primecount.md)
- [Locked specification](https://github.com/SAIRcompetition/lean-kernel-challenge/blob/eb5e8850cdec9acf52d615529f9d1d64894e44b9/evaluation/problems/primecount/Spec.lean)
- [Default public example baseline](https://github.com/SAIRcompetition/lean-kernel-challenge/blob/eb5e8850cdec9acf52d615529f9d1d64894e44b9/examples/primecount/Submission.lean)
- [Untouched public starter baseline](https://github.com/SAIRcompetition/lean-kernel-challenge/blob/eb5e8850cdec9acf52d615529f9d1d64894e44b9/problems/primecount/Submission.lean)
- [Canonical group configuration](https://github.com/SAIRcompetition/lean-kernel-challenge/blob/eb5e8850cdec9acf52d615529f9d1d64894e44b9/evaluation/problems/primecount/config.json)
- [Dependency lock](https://github.com/SAIRcompetition/lean-kernel-challenge/blob/eb5e8850cdec9acf52d615529f9d1d64894e44b9/evaluation/problems/primecount/dependency-lock.json)
- [Submission and scoring rules](../../docs/rules.md)
