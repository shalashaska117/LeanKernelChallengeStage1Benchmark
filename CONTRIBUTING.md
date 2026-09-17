# Contributing

Changes should help another participant run and understand a benchmark. Keep each problem's guide and `cases.json` beside its benchmark configuration. Describe the input policy, expected result checks, limits, measurement boundary, and differences from official scoring.

Follow the [current computation policy](docs/rules.md#computation-and-precomputed-answers). Do not recommend answer precomputation or evaluation manipulation as optimizations. Keep independent expected answers in the test harness separate from candidate computation. Document algorithm constants and tables generated during measured computation accurately; they are not categorically prohibited. An automated acceptance result is not an organizer eligibility ruling.

When competition policy changes ahead of the pinned evaluator, update the policy notes with a dated official source. Keep the executable pin and measurement provenance explicit. A documentation update alone does not require changing the evaluator or baseline hashes.

The eight official public examples are bundled unchanged in `benchmarks/<number>-<problem>/official/Submission.lean`. Keep changes focused on benchmark tools, guides, and these pinned examples. New baseline references need a public source, a pinned revision and SHA-256 hash, and the upstream license. Keep the upstream and bundled paths in `baselines.lock.json` consistent with the source files.

Before proposing a change:

```bash
python3 -m unittest discover -s tests -v
python3 benchmark.py list
python3 scripts/check_release.py
```

For a runner change, also exercise the affected mode on small public-baseline inputs and report the command and outcome. Test failure handling when a change affects timeouts, missing measurements, or comparison eligibility. Never replace failed samples with zero.

Run `python3 scripts/check_release.py --worktree` before staging, then run the default release check after staging the intended files. The default checks the staged publication file list and content. Keep output under the ignored `results/` directory. Review the actual diff; a file filter cannot identify every private detail in prose.

Changes to `upstream.lock.json` should update the rule summaries and problem manifests together. Recheck the evaluator contract, bundled official examples, baseline hashes, and third-party license at the new revision. The release check permits only the eight official Lean files with their exact pinned content. A toolchain or metric change starts a new comparison set.

Write documentation in English. A change description should state what changed, how it was checked, and any limit on the result.

## Publishing benchmark improvements

Update benchmark tools, affected problem guides, and validation notes together. Use `--submission` to test a local Lean file.

Run the tests and worktree release check, then stage the benchmark changes. Run the default release check on the staged blobs and review `git diff --cached`. Commit and push the verified benchmark update to GitHub. The benchmark commands perform local measurements and do not publish files.
