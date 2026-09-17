# Third-party sources

The benchmark wrapper is independent of the challenge organizers. It includes eight unchanged official public examples from the [Lean Kernel Challenge repository](https://github.com/SAIRcompetition/lean-kernel-challenge/tree/eb5e8850cdec9acf52d615529f9d1d64894e44b9), revision `eb5e8850cdec9acf52d615529f9d1d64894e44b9`, released under Apache-2.0.

The copied files are `benchmarks/<number>-<problem>/official/Submission.lean` for `fib`, `partition`, `mertens`, `primecount`, `permanent`, `ca-rule110`, `sha256`, and `polydisc`. Their originals are `examples/<problem>/Submission.lean` at that revision. [baselines.lock.json](baselines.lock.json) records each upstream path, bundled path, and SHA-256 hash. The upstream license is included at [third_party/lean-kernel-challenge/LICENSE](third_party/lean-kernel-challenge/LICENSE).

Setup also downloads the pinned evaluator, specifications, starters, and dependencies. Downloaded code retains its own license files in `.cache/`. The [MIT license](LICENSE) covers this repository's benchmark tools; it does not replace the license of the official Lean files.

Problem definitions and test-group metadata are summarized from that public revision. Each problem guide links to its source. The [rules guide](docs/rules.md) also records the current computation restrictions checked on September 17, 2026. The organizers' current rules take precedence for competition entries; this policy update does not change the bundled sources or executable pin.
