"""Probe access to the timer's hardware instruction event without running Lean.

The probe opens a disabled event and closes it immediately. It never enables the
counter, changes permissions, or runs a submission. A successful open establishes
event access; the timer must still enable, read and validate each measurement.
"""

from __future__ import annotations

import ctypes
import errno
import json
import os
from pathlib import Path
import platform
import sys


PARANOID_PATH = Path("/proc/sys/kernel/perf_event_paranoid")
EVENT_SOURCES_PATH = Path("/sys/bus/event_source/devices")
# Linux's native 64-bit syscall ABIs; no fallback number is used.
SYSCALL_NUMBERS = {"x86_64": 298, "aarch64": 241}
PERF_TYPE_HARDWARE = 0
PERF_COUNT_HW_INSTRUCTIONS = 1
PERF_ATTR_DISABLED = 1 << 0
PERF_ATTR_EXCLUDE_HV = 1 << 6


class _PerfEventAttr(ctypes.Structure):
    # PERF_ATTR_SIZE_VER0 (64 bytes) contains every field used by this event.
    # Later ABI extensions are zero, just as in the timer's zeroed structure.
    # Layout: include/uapi/linux/perf_event.h in the Linux source tree.
    _fields_ = [
        ("type", ctypes.c_uint32),
        ("size", ctypes.c_uint32),
        ("config", ctypes.c_uint64),
        ("sample_period", ctypes.c_uint64),
        ("sample_type", ctypes.c_uint64),
        ("read_format", ctypes.c_uint64),
        ("attribute_flags", ctypes.c_uint64),
        ("wakeup_events", ctypes.c_uint32),
        ("bp_type", ctypes.c_uint32),
        ("config1", ctypes.c_uint64),
    ]


def _read_paranoid() -> int | None:
    try:
        return int(PARANOID_PATH.read_text(encoding="ascii").strip())
    except (OSError, UnicodeError, ValueError):
        return None


def _event_sources() -> tuple[list[str], str | None]:
    try:
        return sorted(path.name for path in EVENT_SOURCES_PATH.iterdir() if path.is_dir()), None
    except OSError as error:
        return [], str(error)


def _failure(result: dict, number: int, detail: str | None = None) -> dict:
    result["errno"] = number
    result["errno_name"] = errno.errorcode.get(number, "UNKNOWN")
    reason = detail or os.strerror(number)
    if number in (errno.EACCES, errno.EPERM):
        result["status"] = "permission-denied"
        result["detail"] = (
            f"perf_event_open denied access: {reason}. This does not establish whether hardware "
            "counters are available. An administrator can repeat the source-free probe with perf access."
        )
    elif number in (errno.ENOENT, errno.ENODEV, errno.EOPNOTSUPP, errno.ENOSYS, errno.EINVAL):
        result["status"] = "unavailable"
        result["detail"] = (
            f"The requested hardware instruction event is unavailable to this process: {reason}. "
            "Check kernel PMU support and, for a virtual machine, host exposure of hardware counters."
        )
    else:
        result["status"] = "error"
        result["detail"] = f"The hardware instruction event probe failed: {reason}."
    return result


def probe_pmu() -> dict:
    """Return event access, syscall outcome and readable procfs/sysfs evidence."""
    machine = platform.machine().lower()
    result = {
        "available": False,
        "status": "unsupported",
        "detail": "",
        "errno": None,
        "errno_name": None,
        "architecture": machine,
        "syscall_number": None,
        "perf_event_paranoid": None,
        "event_sources": [],
        "event_sources_error": None,
        "standard_x86_cpu_sources_visible": None,
        "event": {
            "type": PERF_TYPE_HARDWARE,
            "config": PERF_COUNT_HW_INSTRUCTIONS,
            "disabled": True,
            "exclude_user": False,
            "exclude_kernel": False,
            "exclude_hv": True,
            "pid": 0,
            "cpu": -1,
            "group_fd": -1,
            "flags": 0,
        },
        "scope": "calling thread, any CPU, user and kernel instructions; excludes hypervisor",
        "probe": "open a disabled event, then close it without enabling it",
    }
    if platform.system() != "Linux":
        result["detail"] = "The PMU probe requires Linux. On Windows, run it inside WSL."
        return result
    result["perf_event_paranoid"] = _read_paranoid()
    result["event_sources"], result["event_sources_error"] = _event_sources()
    if machine == "x86_64" and result["event_sources_error"] is None:
        result["standard_x86_cpu_sources_visible"] = bool(
            {"cpu", "cpu_core", "cpu_atom"}.intersection(result["event_sources"])
        )
    if machine not in SYSCALL_NUMBERS or ctypes.sizeof(ctypes.c_void_p) != 8 or sys.byteorder != "little":
        result["detail"] = (
            "No syscall ABI is configured for this process. Supported ABIs are 64-bit "
            "little-endian Linux x86_64 and aarch64; no syscall was attempted."
        )
        return result
    number = SYSCALL_NUMBERS[machine]
    result["syscall_number"] = number
    attr = _PerfEventAttr()
    attr.type = PERF_TYPE_HARDWARE
    attr.size = ctypes.sizeof(attr)
    attr.config = PERF_COUNT_HW_INSTRUCTIONS
    attr.attribute_flags = PERF_ATTR_DISABLED | PERF_ATTR_EXCLUDE_HV
    try:
        library = ctypes.CDLL(None, use_errno=True)
        syscall = library.syscall
        syscall.restype = ctypes.c_long
        ctypes.set_errno(0)
        descriptor = syscall(
            ctypes.c_long(number), ctypes.byref(attr), ctypes.c_long(0),
            ctypes.c_long(-1), ctypes.c_long(-1), ctypes.c_ulong(0),
        )
        error_number = ctypes.get_errno()
    except (AttributeError, OSError) as error:
        result["status"] = "error"
        result["detail"] = f"Cannot call perf_event_open through the C library: {error}."
        return result
    if descriptor < 0:
        return _failure(result, error_number)
    try:
        os.close(descriptor)
    except OSError as error:
        return _failure(result, error.errno or errno.EIO, f"closing the probe event failed: {error}")
    result.update(
        available=True,
        status="available",
        detail="The requested hardware instruction event opened successfully and was closed without being enabled.",
    )
    return result


def main() -> int:
    result = probe_pmu()
    print(json.dumps(result, indent=2))
    return 0 if result["available"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
