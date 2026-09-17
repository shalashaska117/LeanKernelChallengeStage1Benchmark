# Reading a benchmark report

Every invocation uses a fresh output directory. Existing reports are not overwritten, including when `--output` is given. Results and generated source are local artifacts ignored by Git.

## Reproduction record

`run.json` records the mode, problem, selected options, UTC start time, pinned upstream revision, Python and Lean versions, operating system, architecture, and SHA-256 hashes of the built tools. The benchmark report also identifies each source by SHA-256. Keep these records together when comparing runs.

The bundled official public example is the default baseline. Its source is linked from the [problem overview](../README.md#problems), and its hash is recorded in [baselines.lock.json](../baselines.lock.json). Selecting `--baseline starter` changes that reference and must be recorded with the result. A comparison against either reference says nothing about the current fastest entry on the website.

Read integer inputs without rounding. Some polynomial discriminant inputs exceed JavaScript's safe integer range; use an integer-preserving JSON parser. Diagnostic expected outputs are decimal strings so large Fibonacci values retain every digit.

## Full public comparisons

Read `summary.md` first, then `summary.json` for structured data. Raw baseline and candidate verdicts and worker logs retain the evaluator's detailed diagnostics.

The evaluator has separate outcomes for submission acceptance, correctness replay, and each computation case. Acceptance checks the submission interface and proof. A complete computation total requires all planned cases and the required verification to finish successfully. A failure, timeout, or unattempted case leaves its measurement absent.

The pinned evaluator's `accepted` and `eligible` fields do not certify compliance with the current ban on precomputed answers or with the competition's purpose. Review the source against the [current computation policy](rules.md#computation-and-precomputed-answers) separately. The website's `SUBMITTED` label confirms submission, not approval. An abbreviated upload hash only permits a prefix comparison; retain full hashes when verifying file identity.

The wrapper compares complete runs only when their problem, case identities, metric, and evaluation cohort agree. It never adds missing values as zero. Correctness replay is reported separately and is not included in the computation total.

## Detailed diagnostics

`diagnostic.json` contains the requested inputs, baseline and candidate source hashes, preparation status, per-step logs, export hashes, individual replay samples, medians, and comparison ratios. `diagnostic.md` provides a shorter table.

The diagnostic target checks that `Submission.impl n` reduces to an independently calculated exact output. It does not check the statement or completeness of `Submission.impl_correct`. A successful diagnostic run needs a separate full evaluator run before it can support a claim about submission acceptance.

The default inputs are six published group endpoints for Fibonacci, partitions, Mertens and prime counting, or all 15 unseeded local packed cases for matrix permanent. Permanent reports include the dimension and seed alongside each input. Custom `--inputs` can test boundaries or small examples. They do not replace an official seeded plan. Diagnostic totals, where shown, refer only to the requested inputs.

## Ratios

For a matching successful case:

```text
ratio = baseline measurement / candidate measurement
```

A ratio of `2` means the candidate used half the measured wall time or instruction count on that input. A ratio below `1` favors the baseline. An instruction ratio is not a wall-time speedup. Do not average case ratios and call the result the total speedup; compare compatible complete totals when those are available.

Different metrics cannot be compared numerically. Binary versions, proof-target encoding, repetitions, and machine conditions also matter. Wall time changes with load and frequency scaling. Callgrind measures simulated user-space instruction execution and has substantial overhead. Hardware counters depend on the host and permissions.

## Sharing results

The summaries are designed to omit the original source path and source content. Review them before sharing. Raw evaluator verdicts, compiler logs, profiles, and generated targets may contain paths, declaration names, or source excerpts from the file being tested. Run both sides on the same machine and retain the records needed to reproduce a comparison.
