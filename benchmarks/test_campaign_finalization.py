"""Standard-library regressions for retained failures and campaign lock cleanup.

Every fixture stops at the host gate or injects a failure there. The real
``run_campaign``, JSON publication, and local advisory lock are exercised, but
no dependency worker, model, dataset, quality input, or numerical package is
needed. These cases do not qualify a host for the frozen model campaign.
"""

from copy import deepcopy
import fcntl
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from benchmarks import run_model as runner


SOURCE_OBSERVATION = "source_sha256_after"
DISK_OBSERVATION = "retained_cache_and_output_bytes_before_final_receipt"


class CampaignFinalizationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.output = self.root / "attempt"
        self.lock_path = self.root / "build/model-campaign.process-lock"
        self.lock_handles = []
        self.real_open = Path.open
        self.real_flock = fcntl.flock
        self.real_directory_bytes = runner.directory_bytes
        self.real_write_json = runner.write_json
        self.addCleanup(self._close_any_remaining_handles)

        # These are explicit control-flow fixtures, not measured host/source
        # evidence. The bounded test wrapper separately binds the actual code.
        self.sources = {"benchmarks/run_model.py": "f" * 64}
        self.host = {
            "schema_version": "hadamard-model-preflight.v1",
            "status": "blocked",
            "campaign_ready": False,
            "model_or_dataset_accessed": False,
            "errors": ["Fixture host has insufficient conservative memory"],
        }
        self.original_blocking_errors = self.host["errors"] + [
            "The frozen host preflight failed before acquisition or model loading"
        ]
        self.enterContext(patch.object(runner, "ROOT", self.root))
        self.hashes = self.enterContext(
            patch.object(runner, "source_hashes", return_value=self.sources)
        )
        self.host_probe = self.enterContext(
            patch.object(runner, "preflight", return_value=self.host)
        )
        self.child = self.enterContext(patch.object(
            runner, "run_bounded_task",
            side_effect=AssertionError("A finalization fixture must not start a child"),
        ))
        self.copy_input = self.enterContext(patch.object(
            runner, "_copy_new",
            side_effect=AssertionError("A finalization fixture must not copy campaign inputs"),
        ))

        def observe_open(path, *args, **kwargs):
            stream = self.real_open(path, *args, **kwargs)
            if path == self.lock_path:
                # Keep a strong reference: garbage collection must not make a
                # missing explicit close look like successful lock cleanup.
                self.lock_handles.append(stream)
            return stream

        self.enterContext(patch.object(Path, "open", observe_open))

    def tearDown(self):
        self.child.assert_not_called()
        self.copy_input.assert_not_called()

    def _close_any_remaining_handles(self):
        for stream in self.lock_handles:
            if not stream.closed:
                stream.close()

    def _run(self):
        return runner.run_campaign(self.output, None, None, None, None)

    def _retained(self):
        return json.loads((self.output / "campaign.json").read_text())

    def _assert_no_campaign_access(self, receipt):
        self.assertFalse(receipt["campaign_ready"])
        self.assertFalse(receipt["quality_test_accessed"])
        self.assertFalse(receipt["model_or_dataset_accessed"])
        self.assertFalse(receipt["adoption_candidate"])
        self.assertEqual(receipt["tasks"], [])

    def _assert_original_host_failure(self, receipt):
        self.assertEqual(receipt["error_type"], "CampaignBlocked")
        self.assertEqual(
            receipt["errors"][:len(self.original_blocking_errors)],
            self.original_blocking_errors,
        )

    def _assert_lock_released(self):
        self.assertEqual(len(self.lock_handles), 1)
        self.assertTrue(self.lock_handles[0].closed, "The owned lock handle was not closed")
        # A separate open file description really must acquire the same lock.
        # Bypass the observation wrapper so it records only the runner's handle.
        with self.real_open(self.lock_path, "a+") as contender:
            self.real_flock(contender.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.real_flock(contender.fileno(), fcntl.LOCK_UN)

    def test_blocked_preflight_retains_receipt_and_releases_real_lock(self):
        result = self._run()

        self.assertEqual(result["status"], "blocked")
        self._assert_original_host_failure(result)
        self._assert_no_campaign_access(result)
        self.assertEqual(result[SOURCE_OBSERVATION], self.sources)
        self.assertTrue(result["inputs_unchanged"])
        self.assertEqual(result.get("finalization_errors", []), [])
        self.assertEqual(
            result[DISK_OBSERVATION],
            (self.output / "preflight.json").stat().st_size,
        )
        self.assertEqual(self._retained(), result)
        self._assert_lock_released()

    def test_repeated_accounting_failure_preserves_original_error_and_receipt(self):
        def fail_during_preflight(manifest, *, disk_path):
            # Exercise the guard's real refusal, first inside the campaign
            # body and again when the final evidence size is observed.
            (disk_path / "forbidden-link").symlink_to(disk_path / "missing-target")
            runner.directory_bytes(disk_path)
            raise AssertionError("Symlink accounting unexpectedly succeeded")

        self.host_probe.side_effect = fail_during_preflight
        with patch.object(runner, "directory_bytes", wraps=self.real_directory_bytes) as accounting:
            result = self._run()

        message = "Campaign output must not contain symlinks"
        self.assertEqual(accounting.call_count, 2)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["error_type"], "ValueError")
        self.assertEqual(result["errors"][0], message)
        self.assertIsNone(result[DISK_OBSERVATION])
        self.assertEqual(result[SOURCE_OBSERVATION], self.sources)
        self.assertTrue(result["inputs_unchanged"])
        self.assertEqual(result["finalization_errors"], [{
            "observation": DISK_OBSERVATION,
            "error_type": "ValueError",
            "message": message,
        }])
        self._assert_no_campaign_access(result)
        self.assertEqual(self._retained(), result)
        self.assertFalse((self.output / "preflight.json").exists())
        self._assert_lock_released()

    def test_final_source_failure_keeps_disk_observation_and_original_host_error(self):
        message = "Fixture source became unreadable"
        self.hashes.side_effect = [self.sources, OSError(message)]
        with patch.object(runner, "directory_bytes", wraps=self.real_directory_bytes) as accounting:
            result = self._run()

        self.assertEqual(result["status"], "failed")
        self._assert_original_host_failure(result)
        self.assertIsNone(result[SOURCE_OBSERVATION])
        self.assertIsNone(result["inputs_unchanged"])
        accounting.assert_called_once_with(self.output)
        self.assertEqual(
            result[DISK_OBSERVATION],
            (self.output / "preflight.json").stat().st_size,
        )
        self.assertEqual(result["finalization_errors"], [{
            "observation": SOURCE_OBSERVATION,
            "error_type": "OSError",
            "message": message,
        }])
        self._assert_no_campaign_access(result)
        self.assertEqual(self._retained(), result)
        self._assert_lock_released()

    def test_final_disk_failure_keeps_source_observation_and_original_host_error(self):
        message = "Fixture final directory accounting was denied"
        with patch.object(runner, "directory_bytes", side_effect=PermissionError(message)) as accounting:
            result = self._run()

        self.assertEqual(result["status"], "failed")
        self._assert_original_host_failure(result)
        self.assertEqual(result[SOURCE_OBSERVATION], self.sources)
        self.assertTrue(result["inputs_unchanged"])
        accounting.assert_called_once_with(self.output)
        self.assertIsNone(result[DISK_OBSERVATION])
        self.assertEqual(result["finalization_errors"], [{
            "observation": DISK_OBSERVATION,
            "error_type": "PermissionError",
            "message": message,
        }])
        self._assert_no_campaign_access(result)
        self.assertEqual(self._retained(), result)
        self._assert_lock_released()

    def test_both_final_observation_failures_are_retained_independently(self):
        source_message = "Fixture final source read failed"
        disk_message = "Fixture final directory read failed"
        self.hashes.side_effect = [self.sources, OSError(source_message)]
        with patch.object(runner, "directory_bytes", side_effect=PermissionError(disk_message)):
            result = self._run()

        self.assertEqual(result["status"], "failed")
        self._assert_original_host_failure(result)
        self.assertIsNone(result[SOURCE_OBSERVATION])
        self.assertIsNone(result["inputs_unchanged"])
        self.assertIsNone(result[DISK_OBSERVATION])
        self.assertEqual(result["finalization_errors"], [
            {"observation": SOURCE_OBSERVATION, "error_type": "OSError", "message": source_message},
            {"observation": DISK_OBSERVATION, "error_type": "PermissionError", "message": disk_message},
        ])
        self._assert_no_campaign_access(result)
        self.assertEqual(self._retained(), result)
        self._assert_lock_released()

    def test_final_receipt_publication_failure_still_releases_real_lock(self):
        attempted = []

        def fail_final_publication(path, value):
            if path == self.output / "campaign.json":
                attempted.append(deepcopy(value))
                raise PermissionError("Fixture final receipt publication was denied")
            return self.real_write_json(path, value)

        with patch.object(runner, "write_json", side_effect=fail_final_publication):
            with self.assertRaisesRegex(PermissionError, "final receipt publication was denied"):
                self._run()

        self.assertEqual(len(attempted), 1)
        self._assert_original_host_failure(attempted[0])
        self._assert_no_campaign_access(attempted[0])
        self.assertTrue((self.output / "preflight.json").is_file())
        self.assertFalse((self.output / "campaign.json").exists())
        self._assert_lock_released()

    def test_unlock_failure_still_closes_handle_and_releases_kernel_lock(self):
        def fail_explicit_unlock(descriptor, operation):
            if operation == fcntl.LOCK_UN:
                raise OSError("Fixture explicit unlock failed")
            return self.real_flock(descriptor, operation)

        with patch.object(runner.fcntl, "flock", side_effect=fail_explicit_unlock) as lock_call:
            with self.assertRaisesRegex(OSError, "explicit unlock failed"):
                self._run()

        self.assertEqual([call.args[1] for call in lock_call.call_args_list], [
            fcntl.LOCK_EX | fcntl.LOCK_NB, fcntl.LOCK_UN,
        ])
        retained = self._retained()
        self.assertEqual(retained["status"], "blocked")
        self._assert_original_host_failure(retained)
        self._assert_no_campaign_access(retained)
        self._assert_lock_released()


if __name__ == "__main__":
    unittest.main()
