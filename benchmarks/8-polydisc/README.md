# Polynomial discriminant (`polydisc`)

Return the exact signed discriminant of the monic degree-24 integer polynomial selected by `n`. Its coefficient list is `[1, a1, ..., a24]`, ordered from highest to lowest degree.

## Official Lean baseline

[Read the official public `Submission.lean`](official/Submission.lean). This is an unchanged copy of the organizers' pinned example and is the default comparison baseline. Its upstream path and SHA-256 are recorded in [baselines.lock.json](../../baselines.lock.json). It is distributed under [Apache-2.0](../../third_party/lean-kernel-challenge/LICENSE) and imports the fixed specification linked below.

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

This names the specification's evaluation method. It uses a normal subresultant polynomial remainder sequence (PRS), with reduced Bareiss elimination as a fallback. The polynomial degree is fixed at 24; coefficient widths vary across input bands and affect the cost of exact integer arithmetic.

The site's description is qualitative. It is not a formal complexity bound or a measured baseline runtime.

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

The default baseline is the bundled [official public example](official/Submission.lean). Select `--baseline starter` to use the untouched starter downloaded from the same pinned revision. Omit `--submission` to measure the baseline alone. Both baselines may exceed performance limits.

This command runs the full canonical local evaluation with one wall-time replay per case. Check both the correctness verdict and full-plan eligibility. An accepted submission can still have failed cases and no computation total.

## Run diagnostics

Start with a small baseline-only check:

```bash
python3 benchmark.py diagnostic --problem polydisc --inputs 0 1 19337098 \
  --metric wall-time --repetitions 1
```

Omit `--inputs` to use the six inputs from the pinned evaluator's local plan with its empty sampling key:

| Group | Case 0 | Case 1 | Maximum coefficient width |
| --- | ---: | ---: | ---: |
| D1 | 19337098 | 9225987 | 15 bits |
| D3 | 6476047012455 | 10487306645701 | 205 bits |
| D5 | 5042242704654352709 | 4530401864863699852 | 3484 bits |

The sampler uses the entire HMAC-SHA256 digest, rejection sampling and distinct inputs within each group. Case order follows the evaluator's sample order. These inputs are public development cases; hidden evaluation uses a different key.

```bash
python3 benchmark.py diagnostic --problem polydisc \
  --submission /path/to/Submission.lean --metric callgrind \
  --repetitions 3 --timeout 600
```

The independent expected-answer code generates the 25 coefficients and builds the full 47-by-47 Sylvester matrix for `P` and its derivative. Exact integer Bareiss elimination gives the signed discriminant. It needs only Python's standard library. The expected answer is computed before timing; the measured kernel target still checks the implementation against the full output literal.

JSON reports store each signed output as a decimal string. They also record the polynomial degree, width band, actual maximum coefficient bit length and total coefficient bit length. Inputs belonging to the six-case plan have their group and zero-based case index recorded. Markdown shows the input, degree and maximum coefficient width beside the measurements.

The diagnostic command defaults to three replays, a 120-second timeout per tool process and a 4096 MiB memory watchdog. `--preparation-memory-mb` can set a separate allowance for target compilation and export. Source compilation, axiom audits and kernel replay keep `--memory-mb`. Per-process diagnostic timeouts are separate from the canonical group's replay limits; see [methodology](../../docs/methodology.md#diagnostic-runs).

Use `compare` to check the universal theorem and canonical eligibility. Diagnostics check the chosen exact-output targets and exported axioms. A full diagnostic total is available only when every requested case and repetition completes.

## Pinned upstream references

- [Problem statement](https://github.com/SAIRcompetition/lean-kernel-challenge/blob/eb5e8850cdec9acf52d615529f9d1d64894e44b9/rules/problems/polydisc.md)
- [Locked specification](https://github.com/SAIRcompetition/lean-kernel-challenge/blob/eb5e8850cdec9acf52d615529f9d1d64894e44b9/evaluation/problems/polydisc/Spec.lean)
- [Default public example baseline](https://github.com/SAIRcompetition/lean-kernel-challenge/blob/eb5e8850cdec9acf52d615529f9d1d64894e44b9/examples/polydisc/Submission.lean)
- [Untouched public starter baseline](https://github.com/SAIRcompetition/lean-kernel-challenge/blob/eb5e8850cdec9acf52d615529f9d1d64894e44b9/problems/polydisc/Submission.lean)
- [Canonical group configuration](https://github.com/SAIRcompetition/lean-kernel-challenge/blob/eb5e8850cdec9acf52d615529f9d1d64894e44b9/evaluation/problems/polydisc/config.json)
- [Submission and scoring rules](../../docs/rules.md)
