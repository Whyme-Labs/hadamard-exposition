"""Independent refusal and process-monitor tests; no model or network access."""

from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from benchmarks.campaign_guard import (MANIFEST, ROOT, bind_files, directory_bytes,
    new_directory, preflight, run_bounded_task, sha256_file, source_hashes,
    validate_execution_lock, validate_review, verify_bound_files, write_json, _worker_is_exiting)


class GuardTests(unittest.TestCase):
    def setUp(self):
        self.manifest = json.loads(MANIFEST.read_text())
        self.observed = {
            "architecture": "x86_64", "cpu_model": "AMD EPYC 9V74 80-Core Processor",
            "python_version": "3.12.14", "dependency_metadata_versions": {
                "numpy": "2.3.5", "onnx": "1.19.1", "onnxruntime": "1.23.2"},
            "cgroup_memory_max_bytes": 8 * 1024**3,
            "cgroup_memory_current_bytes": 1024**3,
            "cgroup_memory_stat": {"inactive_file": 0, "file_dirty": 0, "file_writeback": 0},
            "host_memory_bytes": {"MemAvailable": 7 * 1024**3},
            "disk_free_bytes": 8 * 1024**3, "cpu_quota_cores": 8,
        }

    def test_exact_host_can_pass_without_claiming_campaign_ready(self):
        result = preflight(self.manifest, self.observed)
        self.assertEqual(result["status"], "passed")
        self.assertFalse(result["campaign_ready"])
        self.assertFalse(result["model_or_dataset_accessed"])

    def test_active_cache_cannot_rescue_failed_memory_gate(self):
        self.observed["cgroup_memory_current_bytes"] = 7 * 1024**3
        self.observed["cgroup_memory_stat"]["active_file"] = 6 * 1024**3
        result = preflight(self.manifest, self.observed)
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["environment"]["memory_availability_estimate"]["estimated_available_bytes"], 1024**3)

    def test_host_cap_dirty_cache_and_missing_counters_fail_closed(self):
        self.observed["host_memory_bytes"]["MemAvailable"] = 5 * 1024**3
        self.assertEqual(preflight(self.manifest, self.observed)["status"], "blocked")
        del self.observed["cgroup_memory_current_bytes"]
        self.observed["cgroup_memory_stat"]["inactive_file"] = 10 * 1024**3
        self.assertEqual(preflight(self.manifest, self.observed)["status"], "blocked")

    def test_cpu_runtime_and_disk_errors_are_all_reported(self):
        self.observed.update(cpu_model="different", disk_free_bytes=1)
        self.observed["dependency_metadata_versions"]["onnxruntime"] = "other"
        result = preflight(self.manifest, self.observed)
        self.assertEqual(len(result["errors"]), 3)

    def test_review_is_bound_to_both_axes_and_exact_source(self):
        sources = {"a.py": "a" * 64}
        review = {"schema_version": "hadamard-model-review.v1", "reviewed_commit": "a" * 40,
                  "reviewed_tree": "b" * 40, "source_sha256": sources,
                  "specification": "passed", "standards": "passed"}
        validate_review(review, sources)
        with self.assertRaises(ValueError):
            validate_review(review, {"a.py": "b" * 64})
        review["standards"] = "pending"
        with self.assertRaises(ValueError):
            validate_review(review, sources)

    def test_atomic_evidence_and_directories_do_not_overwrite(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            write_json(root / "receipt.json", {"old": True})
            with self.assertRaises(FileExistsError):
                write_json(root / "receipt.json", {"new": True})
            self.assertEqual(json.loads((root / "receipt.json").read_text()), {"old": True})
            with self.assertRaises(FileExistsError):
                new_directory(root)

    def test_bound_files_detect_tamper_and_path_escape(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "a").write_text("abc")
            bound = bind_files(root, [root / "a"])
            verify_bound_files(root, bound)
            (root / "a").write_text("abd")
            with self.assertRaises(ValueError):
                verify_bound_files(root, bound)
            with self.assertRaises(ValueError):
                verify_bound_files(root, {"../outside": bound["a"]})

    def test_symlinks_do_not_hide_output_or_replace_evidence(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "a").write_text("abc")
            (root / "alias").symlink_to(root / "a")
            with self.assertRaises(ValueError):
                bind_files(root, [root / "alias"])
            with self.assertRaises(ValueError):
                directory_bytes(root)

    def test_atomic_publication_disappearance_does_not_mask_process_errors(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            pending, published = root / "receipt.pending", root / "receipt.json"
            published.write_bytes(b"12345")
            with patch.object(Path, "rglob", return_value=iter([pending, published])):
                self.assertEqual(directory_bytes(root), 5)
            # Only disappearance is tolerated. Permission/IO errors still make
            # resource accounting unavailable and must reach the monitor.
            with patch.object(Path, "lstat", side_effect=PermissionError("denied")):
                with self.assertRaises(PermissionError):
                    directory_bytes(root)

    def test_execution_lock_rejects_placeholder_receipts(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            sources = {"a.py": "a" * 64}
            review = {"schema_version": "hadamard-model-review.v1", "reviewed_commit": "a" * 40,
                      "reviewed_tree": "b" * 40, "source_sha256": sources,
                      "specification": "passed", "standards": "passed"}
            files = []
            for name in ("preflight.json", "dependencies.json", "preparation.json", "development-proof.json"):
                p = root / name
                value = {"status": "passed", "feasible": True, "quality_test_accessed": False}
                value["checks"] = {key: True for key in ("acquisition", "selection", "export", "reference", "onnx_parity", "source_identity")}
                write_json(p, value)
                files.append(p)
            lock = {"schema_version": "hadamard-model-execution-lock.v1", "campaign_ready": True,
                    "source_sha256": sources, "review": review, "files": bind_files(root, files),
                    "quality_test_accessed": False}
            with self.assertRaises(ValueError):
                validate_execution_lock(lock, root, sources)

    def test_exit_race_requires_matching_pid_start_and_terminal_state(self):
        identity = {"procfs_pid": 123, "start_ticks": 456, "namespace_pid": 7}
        def stat(state, ticks=456):
            return "123 (worker name) " + " ".join([state] + ["0"] * 18 + [str(ticks)])
        with patch.object(Path, "read_text", return_value=stat("Z")):
            self.assertTrue(_worker_is_exiting(identity))
        with patch.object(Path, "read_text", return_value=stat("R")):
            self.assertFalse(_worker_is_exiting(identity))
        with patch.object(Path, "read_text", return_value=stat("Z", 457)):
            with self.assertRaises(ValueError):
                _worker_is_exiting(identity)

    def _worker(self, output: Path, *, delay=0.12, payload=0, status="passed"):
        code = "\n".join([
            "from pathlib import Path", "import json, resource, sys, time",
            "from benchmarks.qualify import _publish_worker_identity",
            "out=Path(sys.argv[1])", "identity=_publish_worker_identity(out)",
            f"(out/'payload').write_bytes(b'x'*{payload})", f"time.sleep({delay!r})",
            f"result={{'status':{status!r},'worker_identity':identity,'peak_worker_rss_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024}}",
            "(out/'worker-result.json').write_text(json.dumps(result))",
        ])
        return [sys.executable, "-c", code, str(output)]

    def test_real_worker_is_identity_bound_and_sampled(self):
        with tempfile.TemporaryDirectory() as temp:
            root, output = Path(temp), Path(temp) / "worker"
            result = run_bounded_task(self._worker(output), output, deadline=time.monotonic()+5,
                                     memory_limit=1024**3, campaign_root=root, cache_limit=1024**2)
            self.assertEqual(result["status"], "passed", result)
            self.assertGreater(result["valid_rss_samples"], 0)
            self.assertGreater(result["sampled_peak_worker_rss_bytes"], 0)
            self.assertEqual(result["worker_identity"], result["worker"]["worker_identity"])

    def test_worker_deadline_retains_failed_observation(self):
        with tempfile.TemporaryDirectory() as temp:
            root, output = Path(temp), Path(temp) / "worker"
            result = run_bounded_task(self._worker(output, delay=3), output, deadline=time.monotonic()+0.3,
                                     memory_limit=1024**3, campaign_root=root, cache_limit=1024**2)
            self.assertEqual(result["status"], "failed")
            self.assertEqual(result["stopped_for"], "phase_or_campaign_deadline")
            self.assertTrue((output / "task-receipt.json").is_file())

    def test_worker_cache_limit_is_observed_during_execution(self):
        with tempfile.TemporaryDirectory() as temp:
            root, output = Path(temp), Path(temp) / "worker"
            result = run_bounded_task(self._worker(output, delay=1, payload=65536), output,
                                     deadline=time.monotonic()+5, memory_limit=1024**3,
                                     campaign_root=root, cache_limit=32768)
            self.assertEqual(result["status"], "failed")
            self.assertEqual(result["stopped_for"], "cache_and_output_budget")


if __name__ == "__main__":
    unittest.main()
