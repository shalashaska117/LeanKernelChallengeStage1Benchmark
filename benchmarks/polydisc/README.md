# Polynomial discriminant (`polydisc`)

Return the exact signed discriminant of the monic degree-24 integer polynomial selected by `n`. Its coefficient list is `[1, a1, ..., a24]`, ordered from highest to lowest degree.

## Interface

Declarations belong in `namespace Submission`:

```text
impl : Nat → Int
impl_correct : ∀ n, impl n = discSpec n
```

The theorem must cover every natural-number input, including inputs outside the benchmark groups. Import the fixed `Spec` and preserve the exact theorem statement. All inputs are Lean function arguments; no standard-input protocol is involved.

## Input and output

The entire `n` selects a width band and initializes the generator. It is not a packed dimension/seed pair. All 24 non-leading coefficients are nonzero. The maximum coefficient widths are 15 bits for `n < 2^26`, 36 bits for `2^26 <= n < 2^36`, 205 bits for `2^36 <= n < 2^46`, 1001 bits for `2^46 <= n < 2^56`, and 3484 bits thereafter.

The fixed generator uses an MMIX linear congruential sequence modulo `2^64`, with multiplier `6364136223846793005`, increment `1442695040888963407`, and initial state `(A * (n + 1) + C) mod 2^64`. The specification's `coefficientWidth` and `polyOf` fix each coefficient's width, bit extraction, and signed value. A width is an upper bound on the coefficient's representation; it is not a promise of that magnitude.

For degree 24, the discriminant equals `resultant(P, P')` because `24*23/2 = 276` is even. The answer can still be negative. Preserve the sign and every digit. The universal theorem covers all five width bands, including the two bands absent from the performance groups.

Input `0` selects a degree-24 polynomial in the 15-bit band. The pinned problem statement includes its full coefficient list and exact signed answer.

## Naive specification cost

Normal subresultant PRS; reduced Bareiss fallback.

This is the site's qualitative description of the naive specification. It names the naive specification's evaluation method; it does not establish a formal complexity bound or a measured runtime for either baseline.

## Public performance groups

| Group | Input selection | Cases | Target replay limit per repetition |
| --- | --- | ---: | ---: |
| D1 | 262,144 through 33,554,432, inclusive | 2 | 30 s |
| D3 | 137,438,953,472 through 35,184,372,088,832, inclusive | 2 | 60 s |
| D5 | 144,115,188,075,855,872 through 9,223,372,036,854,775,808, inclusive | 2 | 120 s |

The official schedule samples two distinct integers uniformly from each range. The canonical evaluator derives the local unseeded inputs. D1, D3, and D5 cover maximum widths of 15, 205, and 3484 bits; the group names intentionally skip D2 and D4.

The pinned whole-job memory policy is 4096 MiB and remains provisional in upstream documentation. The local comparison command does not enforce the official container memory limit. See [measurement and limits](../../docs/methodology.md).

`cases.json` records these groups for inspection. The pinned canonical evaluator resolves and validates the full comparison plan; this manifest does not replace its configuration.

## Dependencies

Core Lean 4.33.1, without Mathlib. Keep the fixed specification and package files unchanged. The benchmark setup still builds the shared evaluator tools.

## Run a comparison

From the benchmark repository root:

```bash
python3 benchmark.py setup --problem polydisc
python3 benchmark.py compare --problem polydisc --submission /path/to/Submission.lean
```

The default baseline is the public upstream example. Select `--baseline starter` to use the untouched upstream starter. Omit `--submission` to measure the baseline alone. Baselines are downloaded from the pinned upstream revision and may exceed performance limits.

This command runs the full canonical local evaluation with one wall-time replay per case. Check both the correctness verdict and full-plan eligibility. An accepted submission can still have failed cases and no computation total.

The optional diagnostic command currently supports `fib`, `partition`, and `mertens`. Use `compare` for this problem.

## Pinned upstream references

- [Problem statement](https://github.com/SAIRcompetition/lean-kernel-challenge/blob/eb5e8850cdec9acf52d615529f9d1d64894e44b9/rules/problems/polydisc.md)
- [Locked specification](https://github.com/SAIRcompetition/lean-kernel-challenge/blob/eb5e8850cdec9acf52d615529f9d1d64894e44b9/evaluation/problems/polydisc/Spec.lean)
- [Default public example baseline](https://github.com/SAIRcompetition/lean-kernel-challenge/blob/eb5e8850cdec9acf52d615529f9d1d64894e44b9/examples/polydisc/Submission.lean)
- [Untouched public starter baseline](https://github.com/SAIRcompetition/lean-kernel-challenge/blob/eb5e8850cdec9acf52d615529f9d1d64894e44b9/problems/polydisc/Submission.lean)
- [Canonical group configuration](https://github.com/SAIRcompetition/lean-kernel-challenge/blob/eb5e8850cdec9acf52d615529f9d1d64894e44b9/evaluation/problems/polydisc/config.json)
- [Submission and scoring rules](../../docs/rules.md)
