"""Focused contract checks using generated arrays and text only."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import unittest

import numpy as np

from benchmarks.contract import (
    ContractError,
    aggregate_nll,
    assert_disjoint_roles,
    pack_codes,
    parse_articles,
    payload_counts,
    quantize_weights,
    select_article_prefixes,
    shifted_nll,
    unpack_codes,
    validate_manifest,
)


class PackingTests(unittest.TestCase):
    def test_nibble_order_and_every_supported_code(self):
        codes = np.array([[-7, -1, 0, 7], [1, 2, 3, 4]], dtype=np.int8)
        packed = pack_codes(codes)
        np.testing.assert_array_equal(packed, [[0x71, 0xF8], [0xA9, 0xCB]])
        np.testing.assert_array_equal(unpack_codes(packed, 4), codes)
        all_codes = np.array([list(range(-7, 8)) + [0]], dtype=np.int8)
        np.testing.assert_array_equal(unpack_codes(pack_codes(all_codes), 16), all_codes)

    def test_invalid_codes_and_reserved_nibble_are_rejected(self):
        for codes in (np.array([[-8, 0]], dtype=np.int8), np.array([[8, 0]]),
                      np.array([[0.0, 1.0]]), np.array([[1]], dtype=np.int8)):
            with self.subTest(codes=codes.tolist()), self.assertRaises(ContractError):
                pack_codes(codes)
        with self.assertRaises(ContractError):
            unpack_codes(np.array([[0x08]], dtype=np.uint8), 2)
        with self.assertRaises(ContractError):
            unpack_codes(np.array([[0x88]], dtype=np.uint8), 4)

    def test_group_scales_rounding_and_zero_groups(self):
        weights = np.zeros((2, 64), dtype=np.float32)
        weights[0, :7] = [7, 0.5, 1.5, 2.5, -0.5, -1.5, -2.5]
        weights[0, 32:35] = [14, 3, -3]
        codes, scales = quantize_weights(weights, 32)
        np.testing.assert_array_equal(scales, [[1, 2], [1, 1]])
        np.testing.assert_array_equal(codes[0, :7], [7, 0, 2, 2, 0, -2, -2])
        np.testing.assert_array_equal(codes[0, 32:35], [7, 2, -2])
        self.assertEqual(codes.dtype, np.int8)
        self.assertEqual(scales.dtype, np.float32)

    def test_quantizer_rejects_wrong_precision_nonfinite_and_partial_groups(self):
        for weights, group in ((np.zeros((2, 32), dtype=np.float64), 32),
                               (np.full((2, 32), np.nan, dtype=np.float32), 32),
                               (np.zeros((2, 33), dtype=np.float32), 32),
                               (np.zeros((2, 32), dtype=np.float32), 8)):
            with self.subTest(group=group, dtype=str(weights.dtype)), self.assertRaises(ContractError):
                quantize_weights(weights, group)

    def test_payload_includes_fp32_scales_and_bias(self):
        g32 = payload_counts(2048, 512, 32, 6)
        g16 = payload_counts(2048, 512, 16, 6)
        self.assertEqual(g32["packed_code_bytes"], 3_145_728)
        self.assertEqual(g32["scale_count"], 196_608)
        self.assertEqual(g32["scale_bytes"], 786_432)
        self.assertEqual(g32["bias_bytes"], 12_288)
        self.assertEqual(g16["packed_code_bytes"], g32["packed_code_bytes"])
        self.assertEqual(g16["scale_bytes"], 2 * g32["scale_bytes"])


class DatasetTests(unittest.TestCase):
    def articles(self, split="test"):
        return parse_articles([
            "preamble", " = First = ", "First text", " == Detail == ", "detail",
            " = Short = ", "short", " = Third = ", "Third text",
        ], split)

    def test_heading_parser_and_prefix_selection(self):
        articles = self.articles()
        self.assertEqual([a["title"] for a in articles], ["First", "Short", "Third"])
        self.assertIn(" == Detail == ", articles[0]["text"])
        tokens = {articles[0]["article_id"]: list(range(520)),
                  articles[1]["article_id"]: [1, 2],
                  articles[2]["article_id"]: list(range(1000, 1513))}
        selected = select_article_prefixes(articles, tokens, count=2)
        self.assertEqual([a["article_id"] for a in selected], [articles[0]["article_id"], articles[2]["article_id"]])
        self.assertEqual([len(a["token_ids"]) for a in selected], [513, 513])
        self.assertEqual(selected[0]["token_ids"][-1], 512)
        self.assertEqual(selected[0]["article_id"], "test:1")
        self.assertEqual(selected[1]["start_row"], 7)
        self.assertEqual(selected[0]["token_sha256"], hashlib.sha256(np.arange(513, dtype="<u4").tobytes()).hexdigest())

    def test_insufficient_or_malformed_tokens_fail_instead_of_shrinking(self):
        articles = self.articles()
        with self.assertRaises(ContractError):
            select_article_prefixes(articles, {a["article_id"]: [1] for a in articles})
        bad = {a["article_id"]: [1] * 513 for a in articles}
        bad[articles[0]["article_id"]][100] = True
        with self.assertRaises(ContractError):
            select_article_prefixes(articles, bad, count=1)

    def test_roles_reject_duplicate_ids_or_text_even_across_split_names(self):
        train, test = self.articles("train"), self.articles("test")
        with self.assertRaises(ContractError):
            assert_disjoint_roles({"timing": train, "quality": test})
        changed = copy.deepcopy(test)
        for item in changed:
            item["text_sha256"] = "a" * 64
        with self.assertRaises(ContractError):
            assert_disjoint_roles({"quality": changed})
        clean = parse_articles([" = Unique = ", "new content"], "validation")
        assert_disjoint_roles({"timing": train, "implementation": clean})


class MetricTests(unittest.TestCase):
    def test_shifted_targets_and_mask_have_hand_computable_loss(self):
        logits = np.log(np.array([[0.75, 0.25], [0.2, 0.8], [0.5, 0.5]]))
        result = shifted_nll(logits, [0, 1, 0])
        self.assertEqual(result["target_count"], 2)
        self.assertAlmostEqual(result["nll_sum"], -np.log(0.25) - np.log(0.2))
        masked = shifted_nll(logits, [0, 1, 0], [1, 1, 0])
        self.assertEqual(masked["target_count"], 1)
        self.assertAlmostEqual(masked["nll_sum"], -np.log(0.25))

    def test_aggregation_weights_tokens_not_records(self):
        result = aggregate_nll([{"nll_sum": 2.0, "target_count": 1},
                                {"nll_sum": 6.0, "target_count": 3}])
        self.assertEqual(result, {"nll_sum": 8.0, "target_count": 4, "mean_nll": 2.0})
        uneven = aggregate_nll([{"nll_sum": 1.0, "target_count": 1},
                                {"nll_sum": 9.0, "target_count": 3}])
        self.assertEqual(uneven["mean_nll"], 2.5)

    def test_nonfinite_invalid_targets_and_zero_target_metrics_fail(self):
        for record in ({"nll_sum": float("nan"), "target_count": 1},
                       {"nll_sum": float("inf"), "target_count": 1},
                       {"nll_sum": -1, "target_count": 1},
                       {"nll_sum": 1, "target_count": 0},
                       {"nll_sum": 1, "target_count": True}):
            with self.subTest(record=record), self.assertRaises(ContractError):
                aggregate_nll([record])
        for logits, ids, mask in (([[0, np.inf], [0, 0]], [0, 1], None),
                                   ([[0, 0], [0, 0]], [0, 2], None),
                                   ([[0, 0], [0, 0]], [0, 1], [0, 0])):
            with self.assertRaises(ContractError):
                shifted_nll(np.asarray(logits), ids, mask)


class ManifestTests(unittest.TestCase):
    def setUp(self):
        self.manifest = json.loads(Path(__file__).with_name("model-benchmark-v1.json").read_text())

    def test_frozen_design_is_valid_and_cannot_launch_campaign(self):
        result = validate_manifest(self.manifest)
        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["arm_count"], 6)
        self.assertFalse(result["campaign_ready"])

    def test_mutable_or_mismatched_artifact_identities_are_rejected(self):
        for target in ("model", "dataset"):
            broken = copy.deepcopy(self.manifest)
            broken[target]["revision"] = "main"
            with self.subTest(target=target), self.assertRaises(ContractError):
                validate_manifest(broken)
        self.manifest["model"]["tokenizer"]["revision"] = "a" * 40
        with self.assertRaises(ContractError):
            validate_manifest(self.manifest)
        self.manifest["model"]["revision"] = "a" * 40
        with self.assertRaises(ContractError):
            validate_manifest(self.manifest)

    def test_wrong_dataset_file_cannot_reuse_v1_identity(self):
        self.manifest["dataset"]["files"]["test"] = "wikitext-2-raw-v1/train-00000-of-00001.parquet"
        with self.assertRaises(ContractError):
            validate_manifest(self.manifest)

    def test_mixed_quantization_precision_and_scale_groups_are_rejected(self):
        changes = [("runtime", "activation_dtype", "float16"), ("runtime", "accuracy_level", 4),
                   ("quantizer", "scale_dtype", "float16"), ("quantizer", "activation_quantization", True)]
        for section, key, value in changes:
            broken = copy.deepcopy(self.manifest)
            broken[section][key] = value
            with self.subTest(section=section, key=key), self.assertRaises(ContractError):
                validate_manifest(broken)
        self.manifest["arms"][3]["group_size"] = 16
        with self.assertRaises(ContractError):
            validate_manifest(self.manifest)

    def test_overlapping_roles_fitting_and_unshifted_loss_are_rejected(self):
        for mutate in (lambda m: m["dataset"]["roles"]["quality"].update(split="train"),
                       lambda m: m["dataset"]["calibration"].update(fitted_examples=128),
                       lambda m: m["quality"].update(target_shift=0)):
            broken = copy.deepcopy(self.manifest)
            mutate(broken)
            with self.assertRaises(ContractError):
                validate_manifest(broken)

    def test_unbounded_or_inconsistent_resource_claims_are_rejected(self):
        for key, value in (("campaign_seconds", 3600), ("timing_seconds", 0),
                           ("threads_per_worker", 8), ("gpu_hours", 1),
                           ("paid_service_budget_usd", True), ("process_memory_bytes", float("inf"))):
            broken = copy.deepcopy(self.manifest)
            broken["budgets"][key] = value
            with self.subTest(key=key), self.assertRaises(ContractError):
                validate_manifest(broken)

    def test_nonfinite_threshold_and_campaign_readiness_claim_are_rejected(self):
        self.manifest["quality"]["acceptance"]["rotated_minus_fp32_upper_95_lte"] = float("nan")
        with self.assertRaises(ContractError):
            validate_manifest(self.manifest)
        self.setUp()
        self.manifest["readiness"]["current_milestone_can_launch_campaign"] = True
        with self.assertRaises(ContractError):
            validate_manifest(self.manifest)


if __name__ == "__main__":
    unittest.main()
