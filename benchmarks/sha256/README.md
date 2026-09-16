# Seeded SHA-256 chains (`sha256`)

Apply SHA-256 repeatedly to a seeded 32-byte digest, then encode the final digest as a big-endian natural number.

## Official Lean baseline

[Read the official public `Submission.lean`](official/Submission.lean). This is an unchanged copy of the organizers' pinned example and is the default comparison baseline. Its upstream path and SHA-256 are recorded in [baselines.lock.json](../../baselines.lock.json). It is distributed under [Apache-2.0](../../third_party/lean-kernel-challenge/LICENSE) and imports the fixed specification linked below.

## Interface

Declarations belong in `namespace Submission`:

```text
impl : Nat → Nat
impl_correct : ∀ n, impl n = sha256Spec n
```

The theorem must cover every natural-number input, including inputs outside the benchmark groups. Import the fixed `Spec` and preserve the exact theorem statement. All inputs are Lean function arguments; no standard-input protocol is involved.

## Input and output

Decode `steps = n >> 32` and `seed = n & 0xffffffff`. Starting at the seed, apply `x = (1664525 * x + 1013904223) mod 2^32` eight times. The eight successive states are the initial digest's words, most significant first.

Each chain step hashes those 32 bytes with standard SHA-256 padding and initial state. Hash the binary bytes, not their decimal or hexadecimal text. Seed expansion runs once. Zero steps returns the initial digest. For final words `a` through `h`, return `a*2^224 + b*2^192 + ... + g*2^32 + h`.

Input `4294967297` means one step with seed 1. Its output is `6974916886958575962243026017989799625410957637305596483321224775681667163855`.

## Naive specification cost

Linear in steps, word-per-Nat.

The scale is the decoded chain length. Each step hashes one 32-byte digest, and the naive specification represents each 32-bit word as a Lean `Nat`. The packed input also contains the seed and is not itself the chain length.

The site's description is qualitative. It is not a formal complexity bound or a measured baseline runtime.

## Public performance groups

| Group | Input selection | Cases | Target replay limit per repetition |
| --- | --- | ---: | ---: |
| H1 | 4 steps; distinct 32-bit seeds | 2 | 30 s |
| H2 | 32 steps; distinct 32-bit seeds | 2 | 60 s |
| H3 | 512 steps; distinct 32-bit seeds | 2 | 120 s |

The official schedule selects distinct 32-bit seeds within each group. The canonical evaluator derives a deterministic schedule for local unseeded runs. Obtain the exact local packed inputs from the result's performance plan; group scales alone do not identify a case.

The pinned whole-job memory policy is 4096 MiB and remains provisional in upstream documentation. The local comparison command does not enforce the official container memory limit. See [measurement and limits](../../docs/methodology.md).

`cases.json` records these groups for inspection. The pinned canonical evaluator resolves and validates the full comparison plan; this manifest does not replace its configuration.

## Dependencies

Core Lean 4.33.1, without Mathlib. Keep the fixed specification and package files unchanged. The benchmark setup still builds the shared evaluator tools.

## Run a comparison

From the benchmark repository root:

```bash
python3 benchmark.py setup --problem sha256
python3 benchmark.py compare --problem sha256 --submission /path/to/Submission.lean
```

The default baseline is the bundled [official public example](official/Submission.lean). Select `--baseline starter` to use the untouched starter downloaded from the same pinned revision. Omit `--submission` to measure the baseline alone. Both baselines may exceed performance limits.

This command runs the full canonical local evaluation with one wall-time replay per case. Check both the correctness verdict and full-plan eligibility. An accepted submission can still have failed cases and no computation total.

The optional diagnostic command currently supports `fib`, `partition`, and `mertens`. Use `compare` for this problem.

## Pinned upstream references

- [Problem statement](https://github.com/SAIRcompetition/lean-kernel-challenge/blob/eb5e8850cdec9acf52d615529f9d1d64894e44b9/rules/problems/sha256.md)
- [Locked specification](https://github.com/SAIRcompetition/lean-kernel-challenge/blob/eb5e8850cdec9acf52d615529f9d1d64894e44b9/evaluation/problems/sha256/Spec.lean)
- [Default public example baseline](https://github.com/SAIRcompetition/lean-kernel-challenge/blob/eb5e8850cdec9acf52d615529f9d1d64894e44b9/examples/sha256/Submission.lean)
- [Untouched public starter baseline](https://github.com/SAIRcompetition/lean-kernel-challenge/blob/eb5e8850cdec9acf52d615529f9d1d64894e44b9/problems/sha256/Submission.lean)
- [Canonical group configuration](https://github.com/SAIRcompetition/lean-kernel-challenge/blob/eb5e8850cdec9acf52d615529f9d1d64894e44b9/evaluation/problems/sha256/config.json)
- [Submission and scoring rules](../../docs/rules.md)
