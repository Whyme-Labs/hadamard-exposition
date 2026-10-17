"""Memory accounting and identity-bound RSS monitoring regression cases."""

import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from benchmarks.qualify import (_load_worker_identity, _memory_preflight,
                                _publish_worker_identity, _require_rss_observations,
                                _run_bounded, _sample_worker_rss)


GIB = 1024**3


class MemoryPreflightTests(unittest.TestCase):
    def observation(self, limit=8 * GIB, current=8 * GIB - GIB // 4, *,
                    inactive=2 * GIB, dirty=0, writeback=0, host=9 * GIB):
        return {"cgroup_memory_max_bytes": limit, "cgroup_memory_current_bytes": current,
                "cgroup_memory_stat": {"inactive_file": inactive, "file_dirty": dirty,
                                       "file_writeback": writeback, "active_file": 6 * GIB,
                                       "slab_reclaimable": 4 * GIB},
                "host_memory_bytes": {"MemAvailable": host} if host is not None else {}}

    def test_clean_inactive_cache_supplies_conservative_headroom(self):
        observed = self.observation(limit=8589934592, current=8335228928,
                                    inactive=1505341440, dirty=2007040, writeback=0)
        _memory_preflight(observed, GIB)
        estimate = observed["memory_availability_estimate"]
        self.assertEqual(estimate["cgroup_headroom_bytes"], 254705664)
        self.assertEqual(estimate["reclaimable_inactive_file_bytes"], 1503334400)
        self.assertEqual(estimate["estimated_available_bytes"], 1758040064)
        self.assertTrue(estimate["inactive_file_accounting_complete"])

    def test_dirty_and_writeback_bytes_do_not_receive_cache_credit(self):
        observed = self.observation(inactive=GIB, dirty=GIB // 2, writeback=GIB // 2)
        with self.assertRaises(ValueError):
            _memory_preflight(observed, GIB)
        estimate = observed["memory_availability_estimate"]
        self.assertEqual(estimate["reclaimable_inactive_file_bytes"], 0)
        self.assertEqual(estimate["estimated_available_bytes"], GIB // 4)
        # Neither large active-file nor slab fields may make this pass.
        self.assertGreater(observed["cgroup_memory_stat"]["active_file"], GIB)

    def test_host_memavailable_caps_the_estimate(self):
        observed = self.observation(host=GIB // 2)
        with self.assertRaises(ValueError):
            _memory_preflight(observed, GIB)
        self.assertEqual(observed["memory_availability_estimate"]["estimated_available_bytes"], GIB // 2)

    def test_genuinely_insufficient_or_missing_stats_fail_closed(self):
        insufficient = self.observation(inactive=GIB // 4)
        with self.assertRaises(ValueError):
            _memory_preflight(insufficient, GIB)
        for missing in ("inactive_file", "file_dirty", "file_writeback"):
            observed = self.observation()
            del observed["cgroup_memory_stat"][missing]
            with self.subTest(missing=missing), self.assertRaises(ValueError):
                _memory_preflight(observed, GIB)
            estimate = observed["memory_availability_estimate"]
            self.assertFalse(estimate["inactive_file_accounting_complete"])
            self.assertEqual(estimate["reclaimable_inactive_file_bytes"], 0)

    def test_plain_headroom_can_pass_without_cache_or_host_accounting(self):
        observed = self.observation(current=6 * GIB, host=None)
        observed["cgroup_memory_stat"] = {}
        _memory_preflight(observed, GIB)
        self.assertEqual(observed["memory_availability_estimate"]["estimated_available_bytes"], 2 * GIB)

    def test_negative_headroom_and_overdrawn_cache_credit_are_clamped(self):
        observed = self.observation(current=9 * GIB, inactive=GIB // 4, dirty=GIB // 2)
        with self.assertRaises(ValueError):
            _memory_preflight(observed, GIB)
        self.assertEqual(observed["memory_availability_estimate"]["estimated_available_bytes"], 0)
        observed["cgroup_memory_max_bytes"] = None
        with self.assertRaises(ValueError):
            _memory_preflight(observed, GIB)
        self.assertIsNone(observed["memory_availability_estimate"]["estimated_available_bytes"])


class WorkerIdentityTests(unittest.TestCase):
    def test_real_procfs_identity_produces_a_positive_rss_sample(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            identity = _publish_worker_identity(output)
            self.assertEqual(identity, _load_worker_identity(output / "worker-identity.json", os.getpid()))
            rss = _sample_worker_rss(identity)
            self.assertGreater(rss, 0)
            _require_rss_observations(identity, 1, rss)

    def test_namespace_pid_and_real_procfs_start_time_mismatches_fail(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            identity = _publish_worker_identity(output)
            with self.assertRaisesRegex(ValueError, "spawned namespace PID"):
                _load_worker_identity(output / "worker-identity.json", os.getpid() + 1)
            with self.assertRaisesRegex(ValueError, "PID/start time"):
                _sample_worker_rss({**identity, "start_ticks": identity["start_ticks"] + 1})
            with patch("benchmarks.qualify._proc_stat_identity",
                       return_value=(identity["procfs_pid"] + 1, identity["start_ticks"])):
                with self.assertRaisesRegex(ValueError, "PID/start time"):
                    _sample_worker_rss(identity)

    def test_missing_identity_or_no_positive_samples_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            with self.assertRaises(FileNotFoundError):
                _load_worker_identity(output / "worker-identity.json", os.getpid())
            identity = _publish_worker_identity(output)
            for bound, samples, peak in ((None, 1, 1024), (identity, 0, 1024), (identity, 1, 0)):
                with self.subTest(identity=bound, samples=samples, peak=peak), self.assertRaises(ValueError):
                    _require_rss_observations(bound, samples, peak)

    def test_zero_exit_without_observed_rss_is_resource_unqualified(self):
        with tempfile.TemporaryDirectory() as directory, patch("benchmarks.qualify.subprocess.Popen") as spawn:
            spawn.return_value.pid = os.getpid()
            spawn.return_value.poll.return_value = 0
            spawn.return_value.wait.return_value = 0
            evidence = _run_bounded(Path(directory), time.monotonic() + 5, GIB)
            self.assertEqual(evidence["returncode"], 0)
            self.assertEqual(evidence["stopped_for"], "worker_rss_monitor")
            self.assertEqual(evidence["valid_rss_samples"], 0)
            self.assertIsNotNone(evidence["rss_monitor_error"])


if __name__ == "__main__":
    unittest.main()
