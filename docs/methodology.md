# Benchmark methodology

Two commands answer different questions. `compare` runs the upstream correctness and replay pipeline on its complete local plan. `diagnostic` checks chosen inputs to help investigate performance. A successful diagnostic does not establish the universal correctness theorem.

## Canonical local comparison

`python3 benchmark.py compare` evaluates the selected upstream baseline and an optional supplied `Submission.lean` with the pinned canonical local evaluator. Only that submission file is passed as contestant input. The fixed evaluation package supplies the specification and dependencies.

The upstream pipeline:

1. Validates the file, checks the required interface and universal proof with the comparator, and audits the exported axioms.
2. Replays the verified correctness closure.
3. Obtains each case's exact reference output from the evaluator's independent reference answers.
4. Builds and exports an exact-output equality against the frozen compiled implementation. It checks that the exported case is bound to the verified implementation, input, and target, then audits its axioms.
5. Replays each target declaration and records its outcome and measurement.

Case preparation and replay use an equality proof whose kernel check must reduce the implementation to the exact output literal. Preparation does not re-elaborate contestant source for each input. See the pinned [evaluation process](https://github.com/SAIRcompetition/lean-kernel-challenge/blob/eb5e8850cdec9acf52d615529f9d1d64894e44b9/rules/evaluation.md#evaluation-process).

The local entrypoint uses one wall-time replay per case and the full deterministic unseeded plan. It does not use the hidden competition seed. The fixed configuration has six cases for each problem except `permanent`, which has fifteen.

The measured computation interval is the target declaration's kernel replay. Process startup, export parsing, and dependency preload are outside that interval. Exact output-literal checking remains inside it. The correctness measurement covers replay of the full verified closure and is reported separately.

## Diagnostic runs

`python3 benchmark.py diagnostic` currently supports `fib`, `partition`, and `mertens`. By default it uses the six public range endpoints listed in each problem's `cases.json`. The `--inputs` option selects an explicit custom set.

Diagnostic runs check selected exact-output cases and audit the exported axioms. They do not run the canonical universal-proof comparator or establish full-plan eligibility. A case can succeed even when the submitted `impl_correct` declaration would fail canonical verification. Use `compare` for that check.

The diagnostic runner uses the pinned kernel timer's target-declaration replay. Compilation, export, axiom audits, export parsing, and dependency preload are outside the measured replay interval. It records the timer's measurement contract and target identity. These measurements remain diagnostic results because the runner omits the canonical universal-proof and submission-eligibility checks and uses its own selected inputs.

| Diagnostic metric | Interpretation | Requirement |
| --- | --- | --- |
| `wall-time` | The timer's target-replay `wall_ns`, in nanoseconds | Linux or WSL with the prepared Lean environment |
| `callgrind` | Valgrind's `Ir` instructions collected around the replay function | Linux and Valgrind |
| `pmu` | The kernel timer's hardware instruction count | Linux and accessible hardware counters |

Callgrind collection is toggled around `l_Lean_Environment_replay___boxed`, and the runner checks that the profile records exactly one call. It counts instrumented user-space instructions. The timer's wall duration under Callgrind includes instrumentation overhead; do not interpret it as normal execution time.

PMU mode requests the pinned timer's `--count-instructions` measurement. The counter follows the calling thread on any CPU, includes user and operating-system kernel instructions, and excludes hypervisor execution. Its enabled interval also includes the timer's wrapper overhead. It is therefore a different measurement from Callgrind's `Ir`.

Callgrind counts and PMU counts come from different mechanisms and are separate metrics. Compare entries using the same metric, inputs, repetition count, and resource settings. Hardware counter availability depends on the host; many virtual machines and WSL installations do not expose usable PMU counters.

`--repetitions` controls the number of diagnostic replays. The runner reports a case median only when every requested repetition completes. A failed repetition stops the remaining repetitions for that case; later inputs are still attempted. Earlier successful samples remain in the result, with no case median. A diagnostic total exists only when all requested cases complete.

Reports retain the raw timer record for each successful sample, process metadata, and log hashes. Per-case ratios require complete measurements for both entries at the same input. These details make it possible to inspect variation and preparation failures without treating missing samples as zero.

`--timeout` bounds each whole compile, export, audit, or replay process, including any preparation outside the measured window. `--memory-mb` supplies Lean's compilation memory setting and a process-tree RSS watchdog sampled every 100 ms. RSS polling can miss short spikes and count shared pages more than once. These controls do not reproduce the official cgroup memory policy or provide a sandbox. A timeout has no instruction count.

## Public groups and hidden cases

The problem manifests are readable descriptions of the pinned public group policies. The canonical evaluator resolves the actual full plan and validates it. Read its recorded plan to identify exact local inputs.

For `fib`, `partition`, `mertens`, and `primecount`, the unseeded plan uses range endpoints. Official evaluation derives distinct ordered inputs using seed-dependent inward jitter. For `permanent`, `ca-rule110`, and `sha256`, input high bits hold the dimension or step count and the low 32 bits hold the instance seed. `polydisc` uses the complete natural number to choose a width band and initialize its generator.

Official cohorts seal a hidden seed commitment and the resolved schedule. A local unseeded case set is public development data and cannot reproduce those hidden cases. Different schedules require separate comparisons.

## Reading results

Keep the correctness verdict, correctness replay outcome, per-case outcomes, and full-plan eligibility separate. Inspect `replay_report.eligible` and `replay_report.computation_total` in the canonical result. `accepted` alone is insufficient.

Canonical outcomes include `accepted`, `rejected`, `retry`, and `error`. A retry or infrastructure error is not evidence that one implementation is slower. Within a run, failed or unattempted cases remain visible. The evaluator continues to later cases after ordinary case failures where possible.

A total speedup is `baseline_total / candidate_total`, and is meaningful only when both complete the same plan under the same measurement contract and cohort. Per-case ratios need matching cases and successful positive measurements on both sides. Ratios greater than one mean the candidate used less of the selected metric. Show incomplete cases alongside successful comparisons.

Wall-time samples vary with system load, CPU frequency, scheduling, and cache state. Run comparisons on a quiet machine, preserve individual samples, and repeat experiments when a small difference matters. Repeating the canonical command produces additional independent runs; each individual canonical local run still has one replay per case.

## Limits

The upstream official stage limits are:

| Stage | Pinned official limit |
| --- | --- |
| Universal correctness comparator | 600 s |
| Correctness axiom audit | 60 s |
| Correctness replay | 300 s per repetition |
| Case build and export | 600 s shared per case |
| Case binding and axiom audits | 300 s shared per case |
| Target replay | 30, 60, or 120 s per repetition, according to group |

For the canonical local command, `--timeout` defaults to 120 seconds. It replaces each correctness-replay budget, each shared case-build/export budget, and generic timing/value-evaluation budgets. A target replay receives the smaller of this value and its group limit. Comparator and audit limits remain unchanged. The option is not a whole-run deadline; independent case budgets can make a full comparison take much longer.

The outer replay watchdog includes process preparation even though that work is excluded from the reported replay interval. A watchdog timeout alone therefore does not identify time spent exclusively in the target declaration.

Local comparison is unsandboxed and does not enforce the official container's memory, CPU, process, or network restrictions. Run submissions you trust. The benchmark does not claim that local resource flags create a security boundary.

## Official environment at the pinned revision

The upstream documentation specifies Lean 4.33.1; Mathlib is pinned to 4.33.1 for the three Mathlib tasks. Comparator revision is `3927ad383f208ae977c340a91c48ac9b497d2097` with the upstream emit-export patch, and lean4export revision is `15f6055e299ad5b89345e533cc2192f4cc00f659`.

The documented official environment is a Linux PMU host with cgroup v2 and Landlock, running an Ubuntu 24.04 container with two CPUs and a 512-process limit. The whole-job memory cap is 8192 MiB for `permanent`, and provisionally 4096 MiB for each other task, with no additional swap. Submission files are read-only, networking is disabled, and execution is non-root.

Official timing uses three replays, the `kernel-replay-v2` measurement contract, `full-closure-replay-v1` for correctness, and `target-declaration-replay-v1` for computation. The timer's PMU counter measures user and kernel instructions within the replay interval, excluding hypervisor execution. Official PMU counts are not elapsed wall time or Callgrind counts.

Canonical Linux replay memory is a process RSS high-water mark sampled over replay, including preloaded dependencies. It is not memory allocated only by the target declaration. On platforms without the Linux memory measurement, the value is unavailable.

The pinned upstream documentation does not publish the official CPU model and says production-host validation remains pending. Matching the software and nominal limits alone does not establish equivalence to a hosted result. See [environment](https://github.com/SAIRcompetition/lean-kernel-challenge/blob/eb5e8850cdec9acf52d615529f9d1d64894e44b9/rules/evaluation.md#environment), [local evaluation](https://github.com/SAIRcompetition/lean-kernel-challenge/blob/eb5e8850cdec9acf52d615529f9d1d64894e44b9/evaluation/README.md), and [deployment](https://github.com/SAIRcompetition/lean-kernel-challenge/blob/eb5e8850cdec9acf52d615529f9d1d64894e44b9/evaluation/maintainers.md).
