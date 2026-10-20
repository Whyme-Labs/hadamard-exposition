"""Generated graph/cache controls and development-only runtime boundary tests."""

from __future__ import annotations

import copy
import hashlib
import json
import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import onnx
from onnx import TensorProto, helper, numpy_helper

from benchmarks.contract import ContractError
from benchmarks.model_export import INPUT_NAMES, OUTPUT_NAMES, SITES, file_sha256
from benchmarks.model_runtime import (
    _checked_outputs, _saved_logits, _validated_cost_fixture,
    compare_logits, create_session, current_rss_bytes, development_cost_fixture,
    run_development_cost, run_reference_development, step_from_session,
)


def development_record(row=1):
    tokens = list(range(513))
    revision = "b08601e04326c79dfdd32d625aee71d232d685c3"
    config = "wikitext-2-raw-v1"
    return {"role": "development", "split": "validation", "dataset_repo": "Salesforce/wikitext",
            "dataset_revision": revision, "dataset_config": config, "start_row": row,
            "article_id": f"{revision}/{config}/validation/{row}", "token_ids": tokens,
            "token_sha256": hashlib.sha256(np.asarray(tokens, dtype="<u4").tobytes()).hexdigest(),
            "text_sha256": hashlib.sha256(f"generated fixture {row}".encode()).hexdigest()}


def write_cache_fixture(path: Path) -> dict:
    """Thirteen-IO generated graph with six real-width projections and a cache.

    This is not a language model. Sparse FP32 matrices preserve a token's value
    exactly through six projection sites; cache outputs append token+cache_index.
    That makes the expected logits and every key/value cache hand-computable.
    """
    nodes, tensors = [], []

    def constant(name, array):
        tensors.append(numpy_helper.from_array(np.asarray(array), name))
        return name

    def operation(op, inputs, name, **attributes):
        nodes.append(helper.make_node(op, inputs, [name], name=name, **attributes))
        return name

    zero = constant("index_zero", np.array([0], np.int64))
    one = constant("index_one", np.array([1], np.int64))
    last_axis = constant("last_axis", np.array([2], np.int64))
    cache_axes = constant("cache_axes", np.array([1, 3], np.int64))
    head_count = constant("head_count", np.array([8], np.int64))
    head_width = constant("head_width", np.array([64], np.int64))
    input_width = constant("input_width", np.array([2048], np.int64))
    vocabulary = constant("vocabulary", np.array([50304], np.int64))
    shape = operation("Shape", ["input_ids"], "token_shape")
    batch = operation("Gather", [shape, zero], "batch_size", axis=0)
    sequence = operation("Gather", [shape, one], "sequence_size", axis=0)
    projection_shape = operation("Concat", [batch, sequence, input_width], "projection_shape", axis=0)
    logit_shape = operation("Concat", [batch, sequence, vocabulary], "logit_shape", axis=0)
    cache_shape = operation("Concat", [batch, head_count, sequence, head_width], "cache_shape", axis=0)
    floated = operation("Cast", ["input_ids"], "float_tokens", to=TensorProto.FLOAT)
    value = operation("Unsqueeze", [floated, last_axis], "token_column")
    sites = []
    for index, site in enumerate(SITES):
        activation = operation("Expand", [value, projection_shape], f"activation_{index}")
        weight = np.zeros((512, 2048), np.float32)
        weight[0, 0] = 1
        name = constant(site + ".weight", weight)
        transposed = operation("Transpose", [name], f"transpose_{index}", perm=[1, 0])
        product = operation("MatMul", [activation, transposed], f"projection_{index}")
        value = operation("ReduceSum", [product, last_axis], f"sum_{index}", keepdims=1)
        sites.append({"site": site, "matmul_node": product, "weight_shape": [512, 2048]})
    operation("Expand", [value, logit_shape], "logits")
    cache_tokens = operation("Unsqueeze", [floated, cache_axes], "cache_token_column")
    cache_values = operation("Expand", [cache_tokens, cache_shape], "cache_values")
    for index, (past, present) in enumerate(zip(INPUT_NAMES[1:], OUTPUT_NAMES[1:], strict=True)):
        offset = constant(f"cache_offset_{index}", np.array(index, np.float32))
        new_values = operation("Add", [cache_values, offset], f"new_cache_{index}")
        operation("Concat", [past, new_values], present, axis=2)
    inputs = [helper.make_tensor_value_info("input_ids", TensorProto.INT64, ["batch", "sequence"])]
    inputs.extend(helper.make_tensor_value_info(name, TensorProto.FLOAT, ["batch", 8, "past_sequence", 64])
                  for name in INPUT_NAMES[1:])
    outputs = [helper.make_tensor_value_info("logits", TensorProto.FLOAT, ["batch", "sequence", 50304])]
    outputs.extend(helper.make_tensor_value_info(name, TensorProto.FLOAT, ["batch", 8, "total_sequence", 64])
                   for name in OUTPUT_NAMES[1:])
    model = helper.make_model(helper.make_graph(nodes, "generated_cache_fixture", inputs, outputs, tensors),
                              ir_version=10, opset_imports=[helper.make_opsetid("", 18)])
    onnx.checker.check_model(model)
    onnx.save(model, path)
    return {"arm": "fp32_original", "path": path.name, "bytes": path.stat().st_size,
            "sha256": file_sha256(path), "sites": sites,
            "initializers": [{"name": tensor.name, "dtype": TensorProto.DataType.Name(tensor.data_type),
                              "shape": list(tensor.dims), "sha256": hashlib.sha256(tensor.SerializeToString()).hexdigest()}
                             for tensor in model.graph.initializer]}


class NumericAndSelectionTests(unittest.TestCase):
    def test_full_array_norm_matches_scalar_reference_and_both_limits_apply(self):
        reference = np.array([[[1, 2, 3], [-4, 5, 6]]], np.float32)
        actual = reference.copy()
        actual[0, 1, 2] += np.float32(1e-6)
        expected_error = math.sqrt(math.fsum((float(a) - float(b)) ** 2 for a, b in zip(actual.flat, reference.flat)))
        expected_norm = math.sqrt(math.fsum(float(value) ** 2 for value in reference.flat))
        result = compare_logits(actual, reference)
        self.assertAlmostEqual(result["relative_frobenius_error"], expected_error / expected_norm, places=15)
        self.assertTrue(result["passed"])
        high = np.full((2, 3), 1000, np.float32)
        self.assertFalse(compare_logits(high + np.float32(.002), high)["passed"])
        small = np.full((2, 3), 1e-4, np.float32)
        self.assertFalse(compare_logits(small + np.float32(1e-6), small)["passed"])

    def test_zero_reference_shape_precision_and_nonfinite_controls(self):
        zero = np.zeros((2, 3), np.float32)
        self.assertTrue(compare_logits(zero, zero)["passed"])
        result = compare_logits(zero + np.float32(1e-7), zero)
        self.assertIsNone(result["relative_frobenius_error"])
        self.assertFalse(result["passed"])
        for values in (np.zeros((3, 2), np.float32), zero.astype(np.float64), np.full((2, 3), np.nan, np.float32)):
            with self.assertRaises(ContractError):
                compare_logits(values, zero)

    def test_cyclic_cost_fixture_preserves_selected_identity_and_exact_mapping(self):
        source = development_record()
        before = copy.deepcopy(source)
        fixture = development_cost_fixture(source)
        self.assertEqual(source, before)
        self.assertEqual(fixture["token_ids"], list(range(513)) + list(range(127)))
        self.assertEqual(fixture["tokens"], 640)
        self.assertEqual(fixture["source_article"]["token_sha256"], source["token_sha256"])
        public, tokens = _validated_cost_fixture(fixture)
        self.assertNotIn("token_ids", public)
        self.assertEqual(len(tokens), 640)
        broken = copy.deepcopy(fixture)
        broken["token_ids"][600] += 1
        with self.assertRaises(ContractError):
            _validated_cost_fixture(broken)

    def test_wrong_role_changed_tokens_and_mixed_boolean_tokens_are_rejected(self):
        for mutate in (lambda record: record.update(role="quality", split="test"),
                       lambda record: record["token_ids"].pop(),
                       lambda record: record["token_ids"].__setitem__(1, 2),
                       lambda record: record["token_ids"].__setitem__(1, True)):
            record = development_record()
            mutate(record)
            with self.assertRaises(ContractError):
                development_cost_fixture(record)

    def test_full_output_boundary_rejects_missing_stale_and_nonfinite_cache(self):
        logits = np.zeros((1, 2, 50304), np.float32)
        cache = [np.zeros((1, 8, 2, 64), np.float32) for _ in range(12)]
        actual, present = _checked_outputs([logits, *cache], 1, 2, 2)
        self.assertIs(actual, logits)
        self.assertEqual(len(present), 12)
        for outputs in ([logits, *cache[:-1]], [logits.astype(np.float64), *cache],
                        [logits, np.zeros((1, 8, 1, 64), np.float32), *cache[1:]],
                        [logits, np.full((1, 8, 2, 64), np.nan, np.float32), *cache[1:]]):
            with self.assertRaises(ContractError):
                _checked_outputs(outputs, 1, 2, 2)

    def test_local_reference_artifact_hash_and_path_are_enforced(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            path = directory / "logits.npy"
            np.save(path, np.arange(6, dtype=np.float32).reshape(1, 2, 3), allow_pickle=False)
            case = {"logits": {"shape": [1, 2, 3]}, "logits_file": {"path": path.name,
                    "bytes": path.stat().st_size, "sha256": file_sha256(path)}}
            mapped = _saved_logits(directory, case)
            self.assertIsInstance(mapped, np.memmap)
            np.testing.assert_array_equal(mapped, np.arange(6).reshape(1, 2, 3))
            del mapped
            bad = copy.deepcopy(case)
            bad["logits_file"]["path"] = "../logits.npy"
            with self.assertRaises(ContractError):
                _saved_logits(directory, bad)
            with path.open("ab") as stream:
                stream.write(b"changed")
            with self.assertRaises(ContractError):
                _saved_logits(directory, case)

    def test_reference_entry_rejects_test_data_before_loading_and_retains_failure(self):
        records = [development_record(1), development_record(7)]
        records[1]["role"] = "quality"
        with tempfile.TemporaryDirectory() as temporary, patch("benchmarks.model_export.load_reference") as load:
            directory = Path(temporary) / "attempt"
            with self.assertRaises(ContractError):
                run_reference_development(Path(temporary) / "absent-model", records, directory)
            load.assert_not_called()
            receipt = json.loads((directory / "reference.json").read_text())
            self.assertEqual(receipt["status"], "failed")
            self.assertEqual(receipt["records"], [])
            self.assertFalse(receipt["campaign_ready"])

    def test_cost_entry_preserves_existing_attempt_without_creating_a_new_receipt(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            (directory / "prior.log").write_text("preserve this attempt\n")
            with patch("benchmarks.model_runtime.create_session") as create:
                with self.assertRaises(FileExistsError):
                    run_development_cost(directory / "absent.onnx", {"arm": "fp32_original"},
                                         development_cost_fixture(development_record()), directory)
                create.assert_not_called()
            self.assertEqual([path.name for path in directory.iterdir()], ["prior.log"])


class RealSessionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory()
        cls.directory = Path(cls.temporary.name)
        cls.graph_path = cls.directory / "fp32_original.onnx"
        cls.receipt = write_cache_fixture(cls.graph_path)

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def test_real_cpu_session_preserves_all_cache_pairs_across_prefill_and_decode(self):
        log_dir = self.directory / "real-session"
        with create_session(self.graph_path, log_dir, arm_receipt=self.receipt, profile=True) as session:
            step = step_from_session(session)
            full, full_cache = step(np.array([[2, 5, 7]], np.int64), None)
            prefill, past = step(np.array([[2, 5]], np.int64), None)
            cached, present = step(np.array([[7]], np.int64), past)
            np.testing.assert_array_equal(full[0, :, 0], [2, 5, 7])
            np.testing.assert_array_equal(prefill, full[:, :2])
            np.testing.assert_array_equal(cached, full[:, 2:])
            for index, (actual, expected) in enumerate(zip(present, full_cache, strict=True)):
                self.assertEqual(actual.shape, (1, 8, 3, 64))
                np.testing.assert_array_equal(actual, expected)
                np.testing.assert_array_equal(actual[0, 0, :, 0], np.array([2, 5, 7]) + index)
        self.assertEqual(session.evidence["status"], "passed")
        self.assertEqual(session.evidence["complete_forward_calls"], 3)
        self.assertEqual(session.evidence["operator_execution_counts"]["MatMul"], 18)
        self.assertEqual(session.evidence["observed_providers"], ["CPUExecutionProvider"])
        self.assertTrue((log_dir / "ort.profile.json").is_file())
        self.assertGreater(current_rss_bytes(), 0)
        with self.assertRaises(ContractError):
            session.step(np.array([[1]], np.int64), None)

    def test_only_one_session_may_be_active_and_existing_logs_stay_unchanged(self):
        log_dir = self.directory / "exclusive-session"
        with create_session(self.graph_path, log_dir, arm_receipt=self.receipt) as session:
            with self.assertRaises(ContractError):
                create_session(self.graph_path, self.directory / "concurrent", arm_receipt=self.receipt)
            session.step(np.array([[1]], np.int64), None)
        before = {path.name: file_sha256(path) for path in log_dir.iterdir()}
        with self.assertRaises(FileExistsError):
            create_session(self.graph_path, log_dir, arm_receipt=self.receipt)
        after = {path.name: file_sha256(path) for path in log_dir.iterdir()}
        self.assertEqual(after, before)
        self.assertFalse((self.directory / "concurrent").exists())

    def test_graph_bytes_and_initializers_are_checked_before_native_session_load(self):
        for label, receipt in (("bad-hash", {**self.receipt, "sha256": "0" * 64}),
                               ("bad-initializers", {**self.receipt, "initializers": []})):
            with patch("benchmarks.model_runtime.ort.InferenceSession") as constructor:
                with self.assertRaises(ContractError):
                    create_session(self.graph_path, self.directory / label, arm_receipt=receipt)
                constructor.assert_not_called()
            retained = json.loads((self.directory / label / "session.json").read_text())
            self.assertEqual(retained["status"], "failed")

    def test_invalid_step_retains_failed_session_and_releases_exclusive_guard(self):
        log_dir = self.directory / "invalid-step"
        with self.assertRaises(ValueError):
            with create_session(self.graph_path, log_dir, arm_receipt=self.receipt) as session:
                session.step(np.array([[50304]], np.int64), None)
        receipt = json.loads((log_dir / "session.json").read_text())
        self.assertEqual(receipt["status"], "failed")
        with create_session(self.graph_path, self.directory / "after-invalid-step", arm_receipt=self.receipt) as recovered:
            recovered.step(np.array([[1]], np.int64), None)


if __name__ == "__main__":
    unittest.main()
