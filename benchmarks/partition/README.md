# Integer partitions (`partition`)

Count the partitions of `n` into positive integers, allowing repeated parts and ignoring order. The empty sum is the single partition of zero.

## Interface

Declarations belong in `namespace Submission`:

```text
impl : Nat → Nat
impl_correct : ∀ n, impl n = partitionSpec n
```

The theorem must cover every natural-number input, including inputs outside the benchmark groups. Import the fixed `Spec` and preserve the exact theorem statement. All inputs are Lean function arguments; no standard-input protocol is involved.

## Input and output

The locked `partitionSpec n` is `partAux n n`. Here `partAux k n` counts partitions with parts at most `k`: it is 1 at `(0, 0)`, 0 at `(0, n + 1)`, and for a positive maximum part it sums over each possible multiplicity of that part. Return the exact count without a modulus. The argument `n` is used directly.

`impl 0 = 1`, `impl 4 = 5`, `impl 5 = 7`, and `impl 10 = 42`.

## Naive specification cost

Approximately p(n) · n, where p(n) is the partition count.

This is the site's qualitative description of the naive specification. It describes the naive specification; it does not establish a formal complexity bound or a measured runtime for either baseline.

## Public performance groups

| Group | Input selection | Cases | Target replay limit per repetition |
| --- | --- | ---: | ---: |
| P1 | 14 through 18, inclusive | 2 | 30 s |
| P2 | 22 through 26, inclusive | 2 | 60 s |
| P3 | 32 through 36, inclusive | 2 | 120 s |

The canonical unseeded local plan uses the six range endpoints. The official schedule derives two distinct increasing inputs per group using inward jitter of up to 15% from a hidden cohort seed. Local endpoint results do not predict the hidden inputs.

The pinned whole-job memory policy is 4096 MiB and remains provisional in upstream documentation. The local comparison command does not enforce the official container memory limit. See [measurement and limits](../../docs/methodology.md).

`cases.json` records these groups for inspection. The pinned canonical evaluator resolves and validates the full comparison plan; this manifest does not replace its configuration.

## Dependencies

Core Lean 4.33.1, without Mathlib. Keep the fixed specification and package files unchanged. The benchmark setup still builds the shared evaluator tools.

## Run a comparison

From the benchmark repository root:

```bash
python3 benchmark.py setup --problem partition
python3 benchmark.py compare --problem partition --submission /path/to/Submission.lean
```

The default baseline is the public upstream example. Select `--baseline starter` to use the untouched upstream starter. Omit `--submission` to measure the baseline alone. Baselines are downloaded from the pinned upstream revision and may exceed performance limits.

This command runs the full canonical local evaluation with one wall-time replay per case. Check both the correctness verdict and full-plan eligibility. An accepted submission can still have failed cases and no computation total.

## Optional diagnostic

For a short check of the diagnostic setup:

```bash
python3 benchmark.py diagnostic --problem partition --submission /path/to/Submission.lean --inputs 0 1 10 --metric wall-time
```

To measure the default six inputs:

```bash
python3 benchmark.py diagnostic --problem partition --submission /path/to/Submission.lean --metric wall-time --repetitions 3
```

Default inputs: `14, 18, 22, 26, 32, 36`. Change them with `--inputs`. These exact-output diagnostics do not verify the universal correctness theorem. They provide local measurements under the separate [diagnostic methodology](../../docs/methodology.md#diagnostic-runs).

## Pinned upstream references

- [Problem statement](https://github.com/SAIRcompetition/lean-kernel-challenge/blob/eb5e8850cdec9acf52d615529f9d1d64894e44b9/rules/problems/partition.md)
- [Locked specification](https://github.com/SAIRcompetition/lean-kernel-challenge/blob/eb5e8850cdec9acf52d615529f9d1d64894e44b9/evaluation/problems/partition/Spec.lean)
- [Default public example baseline](https://github.com/SAIRcompetition/lean-kernel-challenge/blob/eb5e8850cdec9acf52d615529f9d1d64894e44b9/examples/partition/Submission.lean)
- [Untouched public starter baseline](https://github.com/SAIRcompetition/lean-kernel-challenge/blob/eb5e8850cdec9acf52d615529f9d1d64894e44b9/problems/partition/Submission.lean)
- [Canonical group configuration](https://github.com/SAIRcompetition/lean-kernel-challenge/blob/eb5e8850cdec9acf52d615529f9d1d64894e44b9/evaluation/problems/partition/config.json)
- [Submission and scoring rules](../../docs/rules.md)
