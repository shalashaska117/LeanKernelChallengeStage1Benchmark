# Hardware instruction counters

PMU diagnostics need both a usable hardware instruction counter and permission to open it. A permission error can hide a missing hardware counter, so check the two conditions separately.

## Run the probe

From the repository root, run:

```bash
python3 -m lkc_bench.pmu
```

This command uses only Python's standard library. It opens the same event requested by the pinned timer, keeps it disabled, then closes it. It does not load a submission, compile Lean, or change system settings. Exit status is 0 when the event opens and 1 otherwise.

The JSON includes the syscall result, error number, `perf_event_paranoid`, and visible event sources under `/sys/bus/event_source/devices`. The probe supports 64-bit little-endian Linux `x86_64` and `aarch64`. Other ABIs return `unsupported` without attempting a guessed syscall.

For a prepared problem, `python3 benchmark.py doctor --problem partition --metric pmu` includes the same check and exits 1 when PMU access is unavailable. A PMU diagnostic checks access before creating its output directory or compiling a submission; a failed check exits 2 without starting a run. If the check passes but a later timer replay fails, the diagnostic retains its partial run and exits 1. Failed cases have no median or total.

The event is `PERF_TYPE_HARDWARE` / `PERF_COUNT_HW_INSTRUCTIONS`, attached to the calling thread on any CPU. It includes user and kernel instructions and excludes hypervisor execution. Its configuration uses the original 64-byte `perf_event_attr` ABI, which contains all the fields needed here. See the Linux [event ABI](https://github.com/torvalds/linux/blob/master/include/uapi/linux/perf_event.h).

## Read the outcome

| Status | Meaning | Next step |
| --- | --- | --- |
| `available` | The requested disabled event opened successfully | Run a small PMU diagnostic to check actual counting |
| `permission-denied` | The kernel rejected access with `EACCES` or `EPERM` | Review perf access with the machine's administrator |
| `unavailable` | The kernel could not provide the requested event | Check kernel PMU support and hardware-counter exposure |
| `unsupported` | This probe has no supported syscall ABI for the process | Use a supported Linux environment or another metric |
| `error` | Another failure occurred, such as a file-descriptor limit | Inspect the reported error before changing permissions |

A successful open is an access check, not a measured instruction sample. The timer must still enable and read the event successfully. The benchmark rejects missing or nonpositive instruction counts.

On x86, missing `cpu`, `cpu_core`, and `cpu_atom` event sources suggest that the guest or kernel has no registered CPU PMU. This is diagnostic evidence, not a substitute for the syscall result. A container can also hide sysfs, and ARM PMUs use other names. An installed `perf` command or a visible software event source alone does not establish hardware-counter availability.

## Separate access policy from hardware support

Linux's documented `perf_event_paranoid` policy permits per-process user and kernel monitoring at level 1. Level 2 and above restrict unprivileged monitoring to user space, which excludes the timer's requested kernel scope. Capabilities and other host policies also affect access; the setting alone cannot predict the syscall result. For controlled monitoring access, the kernel documentation prefers `CAP_PERFMON` over the broader `CAP_SYS_ADMIN`. Ask the administrator to choose a narrowly scoped policy for the benchmark environment. See [Linux perf access control](https://docs.kernel.org/admin-guide/perf-security.html).

The timer opens its own event. Granting a capability only to the separate `perf` executable does not grant access to the timer process.

After a permission denial, an administrator can repeat the standalone probe with authorized perf access. That probe does not accept a submission argument. If access is allowed and the event still fails with an unavailable-event error, investigate hardware exposure or the PMU driver. Running the Lean benchmark as root is not a troubleshooting step.

## WSL and virtual machines

WSL can expose hardware counters on supported hosts. Microsoft's release notes describe enabling this support when the hardware permits it and document a `hardwarePerformanceCounters=false` opt-out. They do not promise support for every CPU, guest kernel, or virtualization configuration. See the [WSL hardware-counter announcement](https://github.com/microsoft/WSL/discussions/7701).

WSL 2.7.14 enables the virtual PMU only when the host reports support. Explicitly requesting hardware counters does not bypass that host check. See the [WSL VM configuration code](https://github.com/microsoft/WSL/blob/2.7.14/src/windows/service/exe/WslCoreVm.cpp#L1406).

For an unavailable counter, check the Windows or hypervisor configuration and whether the guest kernel supports the exposed CPU PMU. The administrator can inspect guest kernel messages for PMU initialization failures. Installing a userspace `perf` package or relaxing perf permissions does not add a missing hardware-counter driver.

Use `--metric callgrind` for instrumented user-space instruction diagnostics or `--metric wall-time` for elapsed kernel replay time when PMU access is unavailable. Preserve the metric name in comparisons: these measurements are different from PMU instruction counts. See [methodology](methodology.md).
