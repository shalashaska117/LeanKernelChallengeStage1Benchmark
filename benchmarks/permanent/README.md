# Seeded matrix permanent (`permanent`)

Compute the permanent of the square 0/1 matrix chosen by a dimension and seed. It counts selections of one nonzero entry per row with no repeated column.

## Interface

Declarations belong in `namespace Submission`:

```text
impl : Nat → Nat
impl_correct : ∀ n, impl n = permanentSpecN n
```

The theorem must cover every natural-number input, including inputs outside the benchmark groups. Import the fixed `Spec` and preserve the exact theorem statement. All inputs are Lean function arguments; no standard-input protocol is involved.

## Input and output

Decode `dimension = n >> 32` and `seed = n & 0xffffffff`. Pack with `(dimension << 32) | seed`, where `0 <= seed < 2^32`. For dimensions at least 3, each row has exactly three ones: its diagonal entry and two distinct seeded off-diagonal entries. The fixed `genPermanentMatrix` defines the mixing constants and column selection. Below dimension 3 the matrix is all ones. Different seeds may generate the same matrix. The input selects this matrix family; it does not encode an arbitrary matrix.

For any seed, dimensions 0, 1, and 2 return 1, 1, and 2. At dimension 3 the result is 6. Packed input `17179869186` is dimension 4, seed 2, and returns 8.

## Naive specification cost

Exponential in dimension (pruned DFS).

This is the site's qualitative description of the naive specification. It describes the naive specification; it does not establish a formal complexity bound or a measured runtime for either baseline.

## Public performance groups

| Group | Input selection | Cases | Target replay limit per repetition |
| --- | --- | ---: | ---: |
| R1 | 6 by 6 matrices; distinct 32-bit seeds | 5 | 30 s |
| R2 | 12 by 12 matrices; distinct 32-bit seeds | 5 | 60 s |
| R3 | 16 by 16 matrices; distinct 32-bit seeds | 5 | 120 s |

The official schedule selects distinct 32-bit seeds within each group. The canonical evaluator derives a deterministic schedule for local unseeded runs. Obtain the exact local packed inputs from the result's performance plan; group scales alone do not identify a case.

The pinned whole-job memory policy is 8192 MiB. The local comparison command does not enforce the official container memory limit. See [measurement and limits](../../docs/methodology.md).

`cases.json` records these groups for inspection. The pinned canonical evaluator resolves and validates the full comparison plan; this manifest does not replace its configuration.

## Dependencies

Core Lean 4.33.1, without Mathlib. Keep the fixed specification and package files unchanged. The benchmark setup still builds the shared evaluator tools.

## Run a comparison

From the benchmark repository root:

```bash
python3 benchmark.py setup --problem permanent
python3 benchmark.py compare --problem permanent --submission /path/to/Submission.lean
```

The default baseline is the public upstream example. Select `--baseline starter` to use the untouched upstream starter. Omit `--submission` to measure the baseline alone. Baselines are downloaded from the pinned upstream revision and may exceed performance limits.

This command runs the full canonical local evaluation with one wall-time replay per case. Check both the correctness verdict and full-plan eligibility. An accepted submission can still have failed cases and no computation total.

The optional diagnostic command currently supports `fib`, `partition`, and `mertens`. Use `compare` for this problem.

## Pinned upstream references

- [Problem statement](https://github.com/SAIRcompetition/lean-kernel-challenge/blob/eb5e8850cdec9acf52d615529f9d1d64894e44b9/rules/problems/permanent.md)
- [Locked specification](https://github.com/SAIRcompetition/lean-kernel-challenge/blob/eb5e8850cdec9acf52d615529f9d1d64894e44b9/evaluation/problems/permanent/Spec.lean)
- [Default public example baseline](https://github.com/SAIRcompetition/lean-kernel-challenge/blob/eb5e8850cdec9acf52d615529f9d1d64894e44b9/examples/permanent/Submission.lean)
- [Untouched public starter baseline](https://github.com/SAIRcompetition/lean-kernel-challenge/blob/eb5e8850cdec9acf52d615529f9d1d64894e44b9/problems/permanent/Submission.lean)
- [Canonical group configuration](https://github.com/SAIRcompetition/lean-kernel-challenge/blob/eb5e8850cdec9acf52d615529f9d1d64894e44b9/evaluation/problems/permanent/config.json)
- [Submission and scoring rules](../../docs/rules.md)
