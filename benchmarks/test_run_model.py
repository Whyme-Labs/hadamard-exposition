"""Offline orchestration fixtures: no pretrained model, data or launch approval.

The complete-flow fixture substitutes declared child outcomes. It verifies
ordering, refusal and retained decisions; it cannot establish model parity.
"""

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

from benchmarks import run_model as runner
from benchmarks.campaign_guard import bind_files, preflight, source_hashes, validate_execution_lock, write_json
from benchmarks.model_metrics import ARM_IDS, timing_schedule


def supported_host():
    return {"architecture": "x86_64", "cpu_model": "AMD EPYC 9V74 80-Core Processor",
        "python_version": "3.12.14", "dependency_metadata_versions": {
            "numpy": "2.3.5", "onnx": "1.19.1", "onnxruntime": "1.23.2"},
        "cgroup_memory_max_bytes": 8 * 1024**3, "cgroup_memory_current_bytes": 1024**3,
        "cgroup_memory_stat": {"inactive_file": 0, "file_dirty": 0, "file_writeback": 0},
        "host_memory_bytes": {"MemAvailable": 7 * 1024**3}, "disk_free_bytes": 8 * 1024**3,
        "cpu_quota_cores": 8}


def synthetic_loss(index, mean=4.0):
    return {"article_id": f"synthetic:{index}", "nll_sum": mean * 512,
            "target_count": 512, "mean_nll": mean}


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.manifest = json.loads(runner.MANIFEST.read_text())

    def test_failed_host_retains_receipts_without_reading_inputs_or_starting_child(self):
        observed = supported_host()
        observed["cgroup_memory_current_bytes"] = 7 * 1024**3
        blocked = preflight(self.manifest, observed)
        with patch.object(runner, "preflight", return_value=blocked), \
                patch.object(runner, "_copy_new") as copy, patch.object(runner, "run_bounded_task") as child:
            result = runner.run_campaign(self.root / "blocked", None, None, None, None)
        self.assertEqual(result["status"], "blocked")
        self.assertFalse(result["campaign_ready"])
        self.assertFalse(result["quality_test_accessed"])
        self.assertFalse(result["model_or_dataset_accessed"])
        copy.assert_not_called()
        child.assert_not_called()
        self.assertEqual(result["tasks"], [])
        self.assertTrue((self.root / "blocked/preflight.json").is_file())
        self.assertTrue((self.root / "blocked/campaign.json").is_file())

    def test_quality_loader_rejects_missing_or_invalid_lock_before_reading_tokens(self):
        with patch.object(runner, "_read", side_effect=AssertionError("No input may be read")):
            with self.assertRaises(runner.CampaignBlocked):
                runner.load_tokens(self.root, "quality")
            with self.assertRaises(ValueError):
                runner.load_tokens(self.root, "quality", execution_lock={"campaign_ready": True})

    def test_review_commit_must_contain_actual_current_file_bytes(self):
        sources = {"a.py": hashlib.sha256(b"current").hexdigest()}
        review = {"schema_version": "hadamard-model-review.v1", "reviewed_commit": "a" * 40,
                  "reviewed_tree": "b" * 40, "source_sha256": sources,
                  "specification": "passed", "standards": "passed"}
        with patch.object(runner.subprocess, "check_output", side_effect=["b" * 40, b"older"]):
            with self.assertRaisesRegex(ValueError, "does not contain"):
                runner.verify_review_commit(review, sources)

    def test_failed_fp32_pair_retains_losses_and_the_negative_logit_control(self):
        class Session:
            def __init__(self, arm):
                self.arm, self.evidence = arm, {"status": "passed"}

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def step(self, tokens, cache):
                logits = np.zeros((1, 2, 3), dtype=np.float32)
                if self.arm == "fp32_rotated":
                    logits += 1
                return logits, ()

        def session(path, logdir, *, arm_receipt, **kwargs):
            return Session(arm_receipt["arm"])

        with patch.object(runner, "_arm", side_effect=lambda root, arm: {"arm": arm, "path": arm + ".onnx"}), \
                patch("benchmarks.model_runtime.create_session", side_effect=session):
            with self.assertRaisesRegex(runner.CampaignBlocked, "rotation control failed"):
                runner._quality_pair(self.root, self.root, {"article_id": "synthetic:0", "token_ids": [0, 1]})
        retained = json.loads((self.root / "fp32-pair.json").read_text())
        self.assertEqual(retained["status"], "failed")
        self.assertEqual(set(retained["losses"]), {"fp32_original", "fp32_rotated"})
        self.assertFalse(retained["logit_control"]["passed"])

    def _projection_inputs(self, cost=1.0):
        parity = {"status": "passed", "arms": {arm: {"parity_wall_seconds": 0.5} for arm in ARM_IDS}}
        tasks = {arm: {"status": "passed", "elapsed_seconds": cost,
            "worker": {"status": "passed", "result": {"status": "passed", "arm": arm,
                                                      "worker_wall_seconds": cost * 0.9}}} for arm in ARM_IDS}
        return parity, tasks

    def test_projection_reserves_preparation_and_counts_complete_workers(self):
        parity, tasks = self._projection_inputs()
        result = runner.development_projection(parity, tasks, 20, self.manifest)
        self.assertTrue(result["feasible"])
        self.assertEqual(result["quality_graph_loads"], 68)
        self.assertEqual(result["quality_child_workers"], 36)
        self.assertAlmostEqual(result["timing_seconds_upper"], 150)
        self.assertAlmostEqual(result["quality_seconds_upper"], 124.5)
        self.assertAlmostEqual(result["projected_campaign_seconds"], 874.5)
        self.assertFalse(result["quality_test_accessed"])

    def test_projection_cannot_reuse_failed_or_incomplete_observations(self):
        parity, tasks = self._projection_inputs()
        for change in (lambda p, t: t.pop(ARM_IDS[-1]),
                       lambda p, t: t[ARM_IDS[0]].update(status="failed"),
                       lambda p, t: t[ARM_IDS[0]].update(elapsed_seconds=float("nan")),
                       lambda p, t: p["arms"][ARM_IDS[0]].update(parity_wall_seconds=0)):
            p, t = deepcopy(parity), deepcopy(tasks)
            change(p, t)
            with self.assertRaises(ValueError):
                runner.development_projection(p, t, 20, self.manifest)

    def test_projection_rejects_excessive_cost_before_any_quality_call(self):
        parity, tasks = self._projection_inputs(cost=5)
        result = runner.development_projection(parity, tasks, 20, self.manifest)
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["timing_seconds_upper"], 750)
        self.assertFalse(result["feasible"])

    def _stub_campaign(self, *, parity_passed=True, cost=0.01):
        """Explicitly fictional child records exercise the orchestration only."""
        sources, calls = source_hashes(), []
        review = {"schema_version": "hadamard-model-review.v1", "reviewed_commit": "a" * 40,
                  "reviewed_tree": "b" * 40, "source_sha256": sources,
                  "specification": "passed", "standards": "passed"}
        review_path = self.root / "fictional-review.json"
        write_json(review_path, review)
        campaign = self.root / "fictional-campaign"
        counts = {name: {"tensors": 1, "elements": 1, "bytes": 4}
                  for name in ("parameters", "buffers", "state_dict")}
        counts["note"] = "Synthetic count fixture, not an exported model"

        def child(command, output, **kwargs):
            config = json.loads(Path(command[command.index("--config") + 1]).read_text())
            kind = config["kind"]
            calls.append(config)
            output.mkdir(parents=True)

            def artifact(path, value):
                target = campaign / path
                target.parent.mkdir(parents=True, exist_ok=True)
                write_json(target, value)

            if kind == "dependencies":
                result = {"status": "passed", "python_prefix": f"/fixture/{config['environment']}"}
            elif kind == "acquisition":
                result = {"status": "complete"}
                artifact("artifacts/acquisition.json", result)
            elif kind == "selection":
                result = {"status": "complete", "role_disjointness": "passed", "quality_evaluation_started": False}
                artifact("selection/selection.json", result)
                for role in ("development", "timing", "quality"):
                    artifact(f"selection/tokens.{role}.json", {"fixture_only": True, "role": role})
            elif kind == "export":
                result = {"schema_version": "hadamard-model-export.v1", "counts": counts,
                    "arms": [{"arm": arm, "bytes": 4, "packed_code_bytes": 0, "scale_bytes": 0} for arm in ARM_IDS]}
                artifact("export/export.json", result)
            elif kind == "reference":
                result = {"status": "passed"}
                artifact("reference/reference.json", result)
            elif kind == "onnx_parity":
                result = {"status": "passed" if parity_passed else "failed",
                    "gates": {key: parity_passed for key in (
                        "every_arm_cache_path", "original_vs_transformers", "rotated_vs_original")},
                    "arms": {arm: {"parity_wall_seconds": 0.01} for arm in ARM_IDS}}
                artifact("parity/export-parity.json", result)
            elif kind == "development_cost":
                result = {"status": "passed", "arm": config["arm"], "worker_wall_seconds": cost * 0.9}
            elif kind == "quality_pair":
                index = config["article_index"]
                result = {"status": "passed", "article_id": f"synthetic:{index}",
                    "logit_control": {"passed": True},
                    "losses": {arm: synthetic_loss(index) for arm in ARM_IDS[:2]}}
            elif kind == "quality_quantized":
                # Group32 is worse after rotation. An excellent group16 result
                # must remain visible without replacing that negative primary.
                mean = {ARM_IDS[2]: 4.1, ARM_IDS[3]: 4.2, ARM_IDS[4]: 4.05, ARM_IDS[5]: 3.9}[config["arm"]]
                result = {"arm": config["arm"], "losses": [synthetic_loss(index, mean) for index in range(32)]}
            elif kind == "timing":
                block = config["block_index"]
                result = {"arm": config["arm"], "block_index": block, "article_index": block % 4,
                    "peak_rss_bytes": 100, "workloads": {workload: {
                        "prefill_seconds": 1, "decode_seconds": 2, "request_seconds": 3, "steady_rss_bytes": 80}
                        for workload in ("short", "primary")}}
            else:
                raise AssertionError(f"Unspecified fixture task: {kind}")
            identity = {"namespace_pid": len(calls), "procfs_pid": len(calls), "start_ticks": len(calls)}
            worker = {"status": "passed", "worker_identity": identity, "result": result,
                "source_sha256_before": sources, "source_sha256_after": sources,
                "inputs_unchanged": True, "peak_worker_rss_bytes": 100}
            task = {"status": "passed", "stopped_for": None, "worker_identity": identity,
                "valid_rss_samples": 2, "sampled_peak_worker_rss_bytes": 100,
                "max_observed_cache_and_output_bytes": 4096,
                "elapsed_seconds": cost if kind == "development_cost" else 0.01, "worker": worker}
            write_json(output / "task-receipt.json", task)
            return task

        host = preflight(self.manifest, supported_host())
        with patch.object(runner, "preflight", return_value=host), \
                patch.object(runner, "verify_review_commit"), patch.object(runner, "run_bounded_task", side_effect=child):
            result = runner.run_campaign(campaign, Path(sys.executable), Path(sys.executable),
                runner.ROOT / "benchmarks/model-dependencies-v1.json", review_path)
        return result, calls, campaign

    def test_complete_flow_retains_negative_primary_and_all_prescribed_timing_workers(self):
        result, calls, campaign = self._stub_campaign()
        self.assertEqual(result["status"], "completed", result["errors"])
        self.assertFalse(result["adoption_candidate"])
        self.assertTrue(result["campaign_ready"])
        self.assertEqual(len(calls), 169)
        measured = [call for call in calls if call["kind"] == "timing"]
        expected = [(block["block_index"], arm) for block in timing_schedule() for arm in block["arms"]]
        self.assertEqual([(call["block_index"], call["arm"]) for call in measured], expected)
        quality = json.loads((campaign / "quality.json").read_text())
        self.assertEqual(set(quality["arms"]), set(ARM_IDS))
        self.assertFalse(quality["primary_gates"]["primary_quality_improvement"])
        self.assertLess(quality["comparisons"]["g16_rotated_minus_original"]["upper_95"], 0)
        self.assertFalse(quality["sensitivity_promoted"])
        self.assertEqual(len([call for call in calls if call["kind"] == "quality_pair"]), 32)
        self.assertEqual(len([call for call in calls if call["kind"] == "quality_quantized"]), 4)

    def test_failed_development_parity_cannot_launch_cost_or_quality(self):
        result, calls, campaign = self._stub_campaign(parity_passed=False)
        self.assertEqual(result["status"], "blocked")
        self.assertFalse(result["quality_test_accessed"])
        self.assertFalse(result["campaign_ready"])
        self.assertEqual(len(calls), 7)
        self.assertFalse((campaign / "execution-lock.json").exists())
        self.assertEqual(json.loads((campaign / "preparation.json").read_text())["status"], "failed")

    def test_infeasible_single_development_pass_cannot_launch_quality(self):
        result, calls, campaign = self._stub_campaign(cost=5)
        self.assertEqual(result["status"], "blocked")
        self.assertFalse(result["quality_test_accessed"])
        self.assertEqual(len(calls), 13)
        self.assertFalse((campaign / "execution-lock.json").exists())
        self.assertEqual(json.loads((campaign / "development-proof.json").read_text())["timing_seconds_upper"], 750)

    def test_fast_lock_checks_consumed_receipts_while_full_check_covers_unused_profiles(self):
        result, _, campaign = self._stub_campaign()
        self.assertEqual(result["status"], "completed", result["errors"])
        lock = json.loads((campaign / "execution-lock.json").read_text())
        profile = campaign / "parity/unused-profile.json"
        write_json(profile, {"generated_profile_fixture": 1})
        lock["files"].update(bind_files(campaign, [profile]))
        profile.write_text('{"generated_profile_fixture": 2}\n')
        validate_execution_lock(lock, campaign, source_hashes(), verify_all_files=False)
        with self.assertRaisesRegex(ValueError, "Evidence bytes changed"):
            validate_execution_lock(lock, campaign, source_hashes(), verify_all_files=True)
        prerequisite = campaign / "workers/development-cost-fp32_original/task-receipt.json"
        prerequisite.write_text("{}\n")
        with self.assertRaisesRegex(ValueError, "Evidence bytes changed"):
            validate_execution_lock(lock, campaign, source_hashes(), verify_all_files=False)


if __name__ == "__main__":
    unittest.main()
