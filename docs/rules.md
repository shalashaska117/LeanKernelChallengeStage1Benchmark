# Submission and comparison rules

This repository provides community benchmarks for the pinned Stage 1 challenge. The [upstream rules](https://github.com/SAIRcompetition/lean-kernel-challenge/blob/eb5e8850cdec9acf52d615529f9d1d64894e44b9/rules/overview.md#rules) define competition eligibility. These notes explain the requirements that affect local comparisons; they do not submit a file to the competition.

## Required submission

Provide a single human-readable `Submission.lean` file, at most 1 MiB (1,048,576 bytes). Put `impl`, `impl_correct`, and supporting declarations in `namespace Submission`. Keep the exact types and theorem statement required by the selected problem:

```text
impl : Nat → Output
impl_correct : ∀ n, impl n = spec n
```

`Output` is `Int` for `mertens` and `polydisc`, and `Nat` for the other six problems. Each problem guide names its exact specification. The implementation must terminate and reduce in the Lean kernel to the required output literal.

The correctness theorem covers every `n : Nat`. For packed inputs it covers every instance produced by the fixed decoder and generator, including zero and scales outside the timing groups. Passing a finite test set cannot establish this theorem.

## Fixed environment and proof restrictions

Keep `Spec.lean`, the toolchain, package configuration, and dependency locks unchanged. Lean is pinned to 4.33.1. The three Mathlib tasks (`fib`, `mertens`, and `primecount`) use only their locked Mathlib 4.33.1 import closures. An import that happens to work in a larger local project may be unavailable to the evaluator.

Upstream prohibits `partial`, `unsafe`, `sorry`, `admit`, `native_decide`, unapproved axioms, compressed data, and bytecode. The admitted proof axioms are `propext`, `Quot.sound`, and `Classical.choice`. A different algorithm, proof structure, or representation is allowed if it satisfies the fixed interface and rules.

See the pinned [submission requirements](https://github.com/SAIRcompetition/lean-kernel-challenge/blob/eb5e8850cdec9acf52d615529f9d1d64894e44b9/rules/problems/README.md#submission), [evaluation rules](https://github.com/SAIRcompetition/lean-kernel-challenge/blob/eb5e8850cdec9acf52d615529f9d1d64894e44b9/rules/evaluation.md), and the per-problem dependency locks linked from the [benchmark guides](../benchmarks/).

## What a baseline means

`--baseline example` selects the official public example bundled in `benchmarks/<number>-<problem>/official/Submission.lean`. These files are unchanged copies of upstream `examples/<problem>/Submission.lean`. `--baseline starter` selects the untouched participant starter downloaded from upstream `problems/<problem>/Submission.lean`. The example is the default.

Both baselines come from the repository revision recorded in the benchmark's upstream pin. They are reference entries supplied by the challenge repository. They are not a claim about the best current solution, a leaderboard entry, or the exact submission running on the hosted service. Upstream states that examples and starters may exceed performance limits.

The eight official examples are included under [Apache-2.0](../third_party/lean-kernel-challenge/LICENSE). Their upstream paths, bundled paths, and SHA-256 hashes are recorded in [baselines.lock.json](../baselines.lock.json); the wrapper checks the selected source before each run. The specification, evaluator, dependencies, and optional starter are downloaded during setup.

## Completion and scoring

The canonical evaluator first checks the interface, universal proof, and permitted axioms. An `accepted` verdict means that gate passed. A timeout, failed computation case, or incomplete correctness replay can still leave an accepted entry without a complete total.

For the pinned official policy, each successful case has three positive instruction counts. Its measurement is their median. The computation total is the sum of every planned case's median, and lower totals rank first. Equal totals tie. Every planned case and required verification must complete before a total exists.

Correctness replay is reported separately and does not contribute to ranking. There are no case weights, cross-problem totals, or partial-plan rankings under this policy. Missing measurements remain absent; they must never be presented as zero cost.

The benchmark's `compare` command uses the canonical full unseeded local plan and one wall-time replay per case. Its totals are local wall-time totals, not official instruction scores. The diagnostic command measures selected exact-output replays without checking the universal theorem. Read [methodology](methodology.md) before comparing its results.

## Keeping a comparison reproducible

Use the same upstream revision, specification, dependency closure, input plan, tool versions, metric, limits, and machine for both entries. Preserve raw samples and failure outcomes. Do not divide totals when either run is incomplete, or combine measurements from different metrics or cohorts.

Report whether the baseline was the example or starter. A useful shared report identifies the source file by hash and records the environment, without requiring the source file itself. Review generated logs and result paths before sharing them: evaluator diagnostics can contain excerpts from the supplied source.

Competition policy and hosted infrastructure can change. This repository's results describe its pinned revision. Check the [current official repository](https://github.com/SAIRcompetition/lean-kernel-challenge) before a formal competition submission.
