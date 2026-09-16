# Contributing

Changes should help another participant run and understand a benchmark. Keep each problem's guide and `cases.json` beside its benchmark configuration. Describe the input policy, expected result checks, limits, measurement boundary, and differences from official scoring.

Do not include submission source, generated Lean targets, profiles, local result archives, or solution development notes. Baselines are fetched from a pinned public upstream revision at runtime. New baseline references need a public source and a reproducible revision or content hash.

Before proposing a change:

```bash
python3 -m unittest discover -s tests -v
python3 benchmark.py list
python3 scripts/check_release.py
```

For a runner change, also exercise the affected mode on small public-baseline inputs and report the command and outcome. Test failure handling when a change affects timeouts, missing measurements, or comparison eligibility. Never replace failed samples with zero.

Run the release check after staging the intended files as well. It checks the tracked publication file list. Keep output under the ignored `results/` directory. Review the actual diff; a file filter cannot identify every private detail in prose.

Changes to `upstream.lock.json` should update the rule summaries and problem manifests together. Recheck the evaluator contract and baselines at the new revision. A toolchain or metric change starts a new comparison set.

Write documentation in English. A change description should state what changed, how it was checked, and any limit on the result.
