# Contributing

Changes should help another participant run and understand a benchmark. Keep each problem's guide and `cases.json` beside its benchmark configuration. Describe the input policy, expected result checks, limits, measurement boundary, and differences from official scoring.

The eight official public examples are bundled unchanged in `benchmarks/<problem>/official/Submission.lean`. Do not include participant source, generated Lean targets, profiles, local result archives, or solution development notes. New baseline references need a public source, a pinned revision and SHA-256 hash, and the upstream license. Keep the upstream and bundled paths in `baselines.lock.json` consistent with the source files.

Before proposing a change:

```bash
python3 -m unittest discover -s tests -v
python3 benchmark.py list
python3 scripts/check_release.py
```

For a runner change, also exercise the affected mode on small public-baseline inputs and report the command and outcome. Test failure handling when a change affects timeouts, missing measurements, or comparison eligibility. Never replace failed samples with zero.

Run the release check after staging the intended files as well. It checks the tracked publication file list. Keep output under the ignored `results/` directory. Review the actual diff; a file filter cannot identify every private detail in prose.

Changes to `upstream.lock.json` should update the rule summaries and problem manifests together. Recheck the evaluator contract, bundled official examples, baseline hashes, and third-party license at the new revision. The release check permits only the eight official Lean files with their exact pinned content. A toolchain or metric change starts a new comparison set.

Write documentation in English. A change description should state what changed, how it was checked, and any limit on the result.
