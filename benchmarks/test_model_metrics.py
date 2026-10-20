"""Independent small fixtures for campaign statistics and workload semantics."""

from __future__ import annotations

import copy
import math
import unittest

import numpy as np

from benchmarks.contract import ContractError
from benchmarks.model_metrics import (
    ARM_IDS,
    paired_nll_bootstrap,
    paired_timing_bootstrap,
    run_request,
    run_timing_worker,
    summarize_quality,
    summarize_timing,
    timing_schedule,
)


def loss_records(losses, counts):
    return [{"article_id": f"article:{index}", "nll_sum": loss, "target_count": count}
            for index, (loss, count) in enumerate(zip(losses, counts, strict=True))]


def linear_percentile(values, percentile):
    ordered = sorted(values)
    position = (len(ordered) - 1) * percentile / 100
    lower = math.floor(position)
    upper = math.ceil(position)
    return ordered[lower] + (position - lower) * (ordered[upper] - ordered[lower])


class BootstrapTests(unittest.TestCase):
    def test_article_bootstrap_reweights_unequal_lengths_on_each_draw(self):
        result = paired_nll_bootstrap(loss_records([1, 90], [1, 9]), loss_records([2, 45], [1, 9]))
        self.assertAlmostEqual(result["point_estimate"], 4.4)
        # A two-article draw has only three possible effects: -1, 4.4 and 5.
        self.assertEqual([result["lower_95"], result["upper_95"]], [-1, 5])
        self.assertEqual([record["mean_nll_difference"] for record in result["per_article"]], [-1, 5])
        self.assertNotAlmostEqual(result["point_estimate"], (-1 + 5) / 2)

    def test_time_bootstrap_uses_ratio_of_means_not_mean_of_ratios(self):
        result = paired_timing_bootstrap([2, 9], [1, 9])
        self.assertAlmostEqual(result["point_estimate"], 1.1)
        self.assertEqual([result["lower_95"], result["upper_95"]], [1, 2])
        self.assertNotAlmostEqual(result["point_estimate"], (2 + 1) / 2)

    def test_prescribed_random_streams_match_independent_scalar_oracles(self):
        treatment = [0.13, 1.93, 3.17, 2.31, 5.29, 7.81, 0.87]
        baseline = [0.97, 1.11, 4.03, 1.87, 3.43, 8.19, 1.23]
        counts = [1, 3, 7, 11, 2, 5, 13]
        quality = paired_nll_bootstrap(loss_records(treatment, counts), loss_records(baseline, counts))
        timing = paired_timing_bootstrap(treatment, baseline)
        for result, seed, is_quality in ((quality, 20261018, True), (timing, 20261020, False)):
            generator = np.random.Generator(np.random.PCG64(seed))
            draws = []
            # This oracle does not call the vectorized implementation or NumPy
            # quantiles: it forms each ratio from independently summed records.
            for _ in range(10_000):
                sample = generator.choice(len(counts), size=len(counts), replace=True)
                t = math.fsum(treatment[index] for index in sample)
                b = math.fsum(baseline[index] for index in sample)
                denominator = sum(counts[index] for index in sample)
                draws.append(t / denominator - b / denominator if is_quality else t / b)
            self.assertAlmostEqual(result["lower_95"], linear_percentile(draws, 2.5), places=14)
            self.assertAlmostEqual(result["upper_95"], linear_percentile(draws, 97.5), places=14)
            self.assertEqual(result["bootstrap"]["draws"], 10_000)
            self.assertEqual(result["bootstrap"]["seed"], seed)
            self.assertTrue(result["bootstrap"]["shared_indices"])

    def test_pairing_counts_and_finite_inputs_fail_closed(self):
        baseline = loss_records([1, 3], [1, 3])
        bad_cases = [baseline[::-1], loss_records([1, 3], [1, 2]),
                     loss_records([1, float("nan")], [1, 3]),
                     [baseline[0], baseline[0]]]
        for treatment in bad_cases:
            with self.subTest(treatment=treatment), self.assertRaises(ContractError):
                paired_nll_bootstrap(treatment, baseline)
        for treatment, reference in (([1], [1, 2]), ([0, 1], [1, 2]),
                                     ([True, 1], [1, 2]), ([1, math.inf], [1, 2]), ([], [])):
            with self.subTest(treatment=treatment), self.assertRaises(ContractError):
                paired_timing_bootstrap(treatment, reference)


def quality_fixture():
    means = {"fp32_original": 4.0, "fp32_rotated": 4.0,
             "w4a32_g32_original": 4.04, "w4a32_g32_rotated": 4.005,
             "w4a32_g16_original": 4.02, "w4a32_g16_rotated": 4.002}
    return {arm: loss_records([mean * 512] * 32, [512] * 32) for arm, mean in means.items()}


def timing_fixture():
    records = {}
    for arm in ARM_IDS:
        ratio = 1.02 if arm == "w4a32_g32_rotated" else 1.0
        records[arm] = []
        for block in range(20):
            workloads = {}
            for workload, duration in (("short", 1.0), ("primary", 4.0)):
                prefill = duration * (block + 1) * ratio
                decode = 2 * duration * (block + 1) * ratio
                workloads[workload] = {"prefill_seconds": prefill, "decode_seconds": decode,
                                       "request_seconds": prefill + decode, "steady_rss_bytes": 80}
            records[arm].append({"block_index": block, "article_index": block % 4,
                                 "peak_rss_bytes": 100, "workloads": workloads})
    return records


class CampaignSummaryTests(unittest.TestCase):
    def test_quality_reports_all_arms_and_requires_both_primary_endpoints(self):
        records = quality_fixture()
        result = summarize_quality(records)
        self.assertEqual(list(result["arms"]), list(ARM_IDS))
        self.assertEqual(result["arms"]["fp32_original"]["target_count"], 16_384)
        self.assertAlmostEqual(result["arms"]["fp32_original"]["perplexity"], math.exp(4))
        self.assertTrue(result["primary_gates_passed"])
        records["w4a32_g32_rotated"] = loss_records([4.06 * 512] * 32, [512] * 32)
        failed = summarize_quality(records)
        self.assertFalse(failed["primary_gates_passed"])
        self.assertFalse(failed["primary_gates"]["primary_quality_improvement"])
        self.assertFalse(failed["primary_gates"]["primary_fp32_margin"])
        self.assertLess(failed["comparisons"]["g16_rotated_minus_original"]["upper_95"], 0)
        self.assertFalse(failed["sensitivity_promoted"])

    def test_strict_improvement_and_fp32_control_cannot_be_bypassed(self):
        records = quality_fixture()
        records["w4a32_g32_rotated"] = copy.deepcopy(records["w4a32_g32_original"])
        self.assertFalse(summarize_quality(records)["primary_gates"]["primary_quality_improvement"])
        records = quality_fixture()
        records["fp32_rotated"] = loss_records([4.001 * 512] * 32, [512] * 32)
        result = summarize_quality(records)
        self.assertFalse(result["primary_gates"]["fp32_aggregate_nll_control"])
        self.assertFalse(result["primary_gates_passed"])

    def test_quality_rejects_missing_reordered_or_shortened_campaign_records(self):
        for mutate in (lambda records: records.pop("w4a32_g16_rotated"),
                       lambda records: records["fp32_rotated"].reverse(),
                       lambda records: records["fp32_rotated"].pop(),
                       lambda records: records["fp32_rotated"][0].update(target_count=511)):
            records = quality_fixture()
            mutate(records)
            with self.assertRaises(ContractError):
                summarize_quality(records)

    def test_timing_uses_paired_blocks_and_ratio_of_maximum_worker_memory(self):
        records = timing_fixture()
        records["w4a32_g32_original"][0]["peak_rss_bytes"] = 1000
        records["w4a32_g32_rotated"][19]["peak_rss_bytes"] = 1040
        result = summarize_timing(records)
        primary = result["comparisons"]["g32"]
        self.assertAlmostEqual(primary["maximum_peak_rss_ratio"], 1.04)
        for workload in ("short", "primary"):
            self.assertAlmostEqual(primary["workloads"][workload]["request_seconds"]["point_estimate"], 1.02)
        self.assertTrue(result["primary_gates_passed"])
        self.assertEqual(list(result["arms"]), list(ARM_IDS))
        self.assertAlmostEqual(result["arms"]["fp32_original"]["workloads"]["primary"]["decode_tokens_per_second"], 128 / 84)
        records["w4a32_g32_rotated"][19]["peak_rss_bytes"] = 1060
        failed = summarize_timing(records)
        self.assertFalse(failed["primary_gates"]["maximum_peak_rss_overhead"])
        self.assertFalse(failed["primary_gates_passed"])
        self.assertFalse(failed["sensitivity_promoted"])

    def test_timing_rejects_missing_mispaired_inconsistent_or_impossible_records(self):
        for mutate in (lambda records: records["fp32_original"].pop(),
                       lambda records: records["fp32_original"][1].update(article_index=0),
                       lambda records: records["fp32_original"][0]["workloads"].pop("short"),
                       lambda records: records["fp32_original"][0]["workloads"]["short"].update(request_seconds=7),
                       lambda records: records["fp32_original"][0].update(peak_rss_bytes=79)):
            records = timing_fixture()
            mutate(records)
            with self.assertRaises(ContractError):
                summarize_timing(records)


class WorkloadTests(unittest.TestCase):
    def test_frozen_schedule_is_reproducible_and_preserves_every_arm(self):
        schedule = timing_schedule()
        self.assertEqual(schedule, timing_schedule())
        self.assertEqual([block["article_index"] for block in schedule], [0, 1, 2, 3] * 5)
        self.assertEqual([block["block_index"] for block in schedule], list(range(20)))
        self.assertEqual(schedule[0]["arms"], ["w4a32_g16_original", "w4a32_g32_original",
                                             "w4a32_g32_rotated", "fp32_original", "fp32_rotated", "w4a32_g16_rotated"])
        self.assertEqual(schedule[1]["arms"], ["fp32_rotated", "w4a32_g16_rotated", "fp32_original",
                                             "w4a32_g32_rotated", "w4a32_g32_original", "w4a32_g16_original"])
        for block in schedule:
            self.assertEqual(set(block["arms"]), set(ARM_IDS))

    def test_four_fresh_requests_fixed_tokens_complete_call_boundary_and_rss_order(self):
        now, events, previous_cache = [0.0], [], [None]

        def clock():
            return now[0]

        def step(ids, cache):
            self.assertEqual(ids.dtype, np.int64)
            self.assertEqual(ids.shape[0], 1)
            self.assertFalse(ids.flags.writeable)
            if cache is not None:
                self.assertIs(cache, previous_cache[0])
                self.assertEqual(ids.shape[1], 1)
            events.append(("forward", ids[0].tolist(), cache is None))
            # The full callable has simulated preparation, graph execution and
            # output preparation cost; all must stay inside its forward timer.
            now[0] += 2 if cache is None else 0.25
            next_cache = object()
            previous_cache[0] = next_cache
            return np.zeros((1, 1, 2), dtype=np.float32), next_cache

        def rss():
            events.append(("rss", len(events)))
            now[0] += 0.5
            return 4096

        result = run_timing_worker(step, list(range(640)), rss, clock=clock)
        resets = [(index, event) for index, event in enumerate(events) if event[0] == "forward" and event[2]]
        self.assertEqual([len(event[1]) for _, event in resets], [128, 128, 512, 512])
        self.assertEqual(len([event for event in events if event[0] == "forward"]), 324)
        self.assertEqual([index for index, event in enumerate(events) if event[0] == "rss"], [33, 196])
        for request_index, (event_index, event) in enumerate(resets):
            prompt, decode = (128, 32) if request_index < 2 else (512, 128)
            self.assertEqual(event[1], list(range(prompt)))
            subsequent = events[event_index + 1:event_index + 1 + decode]
            self.assertEqual([entry[1][0] for entry in subsequent], list(range(prompt, prompt + decode)))
        for workload, decode, wall in (("short", 32, 20.5), ("primary", 128, 68.5)):
            measured = result["workloads"][workload]
            self.assertEqual(measured["prefill_seconds"], 2)
            self.assertEqual(measured["decode_seconds"], decode * 0.25)
            self.assertEqual(measured["request_seconds"], 2 + decode * 0.25)
            self.assertEqual(measured["workload_wall_seconds"], wall)
            self.assertEqual(measured["steady_rss_bytes"], 4096)
        self.assertEqual(result["timing_worker_wall_seconds"], 89)

    def test_malformed_inputs_missing_cache_or_nonmonotonic_clock_are_rejected(self):
        with self.assertRaises(ContractError):
            run_request(lambda *_: (None, object()), range(639), "primary")
        invalid = [0] * 640
        invalid[0] = True
        with self.assertRaises(ContractError):
            run_request(lambda *_: (None, object()), invalid, "primary")
        with self.assertRaises(ContractError):
            run_request(lambda *_: (None, None), range(640), "primary")
        times = iter([10.0, 10.0, 9.0])
        with self.assertRaises(ContractError):
            run_request(lambda *_: (None, object()), range(640), "short", clock=lambda: next(times))


if __name__ == "__main__":
    unittest.main()
