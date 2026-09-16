"""Exercise PMU diagnosis with fake syscalls and temporary procfs/sysfs data."""

import ctypes
from contextlib import ExitStack
import errno
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from lkc_bench import pmu


class PmuProbeTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.contexts = ExitStack()
        # Restore os.close before TemporaryDirectory performs Linux fd cleanup.
        self.addCleanup(self.contexts.close)
        root = Path(directory.name)
        self.paranoid = root / "perf_event_paranoid"
        self.paranoid.write_text("2\n", encoding="ascii")
        self.sources = root / "devices"
        self.sources.mkdir()
        for name in ("software", "cpu", "breakpoint"):
            (self.sources / name).mkdir()
        (self.sources / "ordinary-file").write_text("ignored", encoding="ascii")
        self.library = Mock()
        self.library.syscall.return_value = 17
        self.close = Mock()
        for target, value in (("PARANOID_PATH", self.paranoid), ("EVENT_SOURCES_PATH", self.sources)):
            self.contexts.enter_context(patch.object(pmu, target, value))
        self.contexts.enter_context(patch.object(pmu.platform, "system", return_value="Linux"))
        self.contexts.enter_context(patch.object(pmu.platform, "machine", return_value="x86_64"))
        self.load = self.contexts.enter_context(patch.object(pmu.ctypes, "CDLL", return_value=self.library))
        self.contexts.enter_context(patch.object(pmu.os, "close", self.close))

    def failure(self, number):
        def syscall(*args):
            ctypes.set_errno(number)
            return -1
        self.library.syscall.side_effect = syscall

    def test_exact_timer_event_and_close(self):
        captured = {}
        def syscall(number, pointer, pid, cpu, group, flags):
            attr = ctypes.cast(pointer, ctypes.POINTER(pmu._PerfEventAttr)).contents
            captured.update(number=number.value, pid=pid.value, cpu=cpu.value,
                            group=group.value, flags=flags.value,
                            attr=ctypes.string_at(pointer, ctypes.sizeof(attr)))
            return 17
        self.library.syscall.side_effect = syscall
        result = pmu.probe_pmu()
        self.assertTrue(result["available"])
        self.assertEqual(result["status"], "available")
        self.assertEqual(result["perf_event_paranoid"], 2)
        self.assertEqual(result["event_sources"], ["breakpoint", "cpu", "software"])
        self.assertTrue(result["standard_x86_cpu_sources_visible"])
        self.assertEqual({key: captured[key] for key in ("number", "pid", "cpu", "group", "flags")},
                         {"number": 298, "pid": 0, "cpu": -1, "group": -1, "flags": 0})
        attr = pmu._PerfEventAttr.from_buffer_copy(captured["attr"])
        self.assertEqual(attr.type, 0)
        self.assertEqual(attr.config, 1)
        self.assertEqual(attr.size, 64)
        self.assertEqual(attr.attribute_flags, (1 << 0) | (1 << 6))
        self.assertEqual(attr.sample_period, 0)
        self.assertEqual(attr.sample_type, 0)
        self.assertEqual(attr.read_format, 0)
        self.assertEqual(attr.config1, 0)
        self.close.assert_called_once_with(17)
        self.load.assert_called_once_with(None, use_errno=True)

    def test_zero_descriptor_is_closed(self):
        self.library.syscall.return_value = 0
        self.assertTrue(pmu.probe_pmu()["available"])
        self.close.assert_called_once_with(0)

    def test_permission_denial_does_not_claim_hardware_is_missing(self):
        for number in (errno.EPERM, errno.EACCES):
            with self.subTest(number=number):
                self.failure(number)
                result = pmu.probe_pmu()
                self.assertFalse(result["available"])
                self.assertEqual(result["status"], "permission-denied")
                self.assertEqual(result["errno"], number)
                self.assertIn("does not establish", result["detail"])
        self.close.assert_not_called()

    def test_unavailable_event_is_distinct(self):
        self.failure(errno.ENOENT)
        result = pmu.probe_pmu()
        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(result["errno_name"], "ENOENT")
        self.assertTrue(result["standard_x86_cpu_sources_visible"])
        self.close.assert_not_called()

    def test_resource_failure_is_not_hardware_diagnosis(self):
        self.failure(errno.EMFILE)
        result = pmu.probe_pmu()
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["errno"], errno.EMFILE)

    def test_missing_cpu_source_does_not_override_syscall_success(self):
        (self.sources / "cpu").rmdir()
        result = pmu.probe_pmu()
        self.assertTrue(result["available"])
        self.assertFalse(result["standard_x86_cpu_sources_visible"])

    def test_missing_procfs_or_sysfs_does_not_block_probe(self):
        self.paranoid.unlink()
        with patch.object(pmu, "EVENT_SOURCES_PATH", self.sources / "missing"):
            result = pmu.probe_pmu()
        self.assertTrue(result["available"])
        self.assertIsNone(result["perf_event_paranoid"])
        self.assertEqual(result["event_sources"], [])
        self.assertIsNotNone(result["event_sources_error"])
        self.assertIsNone(result["standard_x86_cpu_sources_visible"])

    def test_aarch64_uses_its_own_syscall_number(self):
        with patch.object(pmu.platform, "machine", return_value="aarch64"):
            result = pmu.probe_pmu()
        self.assertTrue(result["available"])
        self.assertEqual(self.library.syscall.call_args.args[0].value, 241)
        self.assertIsNone(result["standard_x86_cpu_sources_visible"])

    def test_unknown_abi_never_calls_syscall(self):
        with patch.object(pmu.platform, "machine", return_value="riscv64"):
            result = pmu.probe_pmu()
        self.assertEqual(result["status"], "unsupported")
        self.assertIsNone(result["syscall_number"])
        self.load.assert_not_called()

    def test_non_linux_never_calls_syscall(self):
        with patch.object(pmu.platform, "system", return_value="Windows"):
            result = pmu.probe_pmu()
        self.assertEqual(result["status"], "unsupported")
        self.load.assert_not_called()

    def test_32_bit_process_never_calls_syscall(self):
        with patch.object(pmu.ctypes, "sizeof", return_value=4):
            result = pmu.probe_pmu()
        self.assertEqual(result["status"], "unsupported")
        self.load.assert_not_called()

    def test_close_failure_is_reported(self):
        self.close.side_effect = OSError(errno.EIO, "close failed")
        result = pmu.probe_pmu()
        self.assertFalse(result["available"])
        self.assertEqual(result["status"], "error")
        self.close.assert_called_once_with(17)


if __name__ == "__main__":
    unittest.main()
