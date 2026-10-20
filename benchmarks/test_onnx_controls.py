"""Focused format and graph tests; the full retained sweep runs in qualify.py."""

from pathlib import Path
import tempfile
import unittest

import numpy as np

from benchmarks.onnx_controls import (
    GraphBuilder, build_mlp_graph, dense_rotation, error_metrics, execute_graph,
    mlp_fixture, mlp_reference, pack_weights, reference_weights, run_controls, unpack_weights,
)


class PackingTests(unittest.TestCase):
    def test_all_signed_codes_and_low_nibble_order(self):
        weight = np.array([list(range(-7, 8)) + [0]], dtype=np.float32)
        packed, scales = pack_weights(weight, 16)
        self.assertEqual(packed[0, 0, 0], 0x21)
        self.assertEqual(packed[0, 0, -1], 0x8F)
        np.testing.assert_array_equal(scales, [[1]])
        np.testing.assert_array_equal(unpack_weights(packed, scales, 16), weight)

    def test_halfway_values_use_ties_to_even(self):
        weight = np.array([[-7, -2.5, -1.5, -.5, 0, .5, 1.5, 2.5, 7] + [0] * 7], dtype=np.float32)
        packed, scales = pack_weights(weight, 16)
        expected = [[-7, -2, -2, 0, 0, 0, 2, 2, 7] + [0] * 7]
        np.testing.assert_array_equal(unpack_weights(packed, scales, 16), expected)

    def test_zero_groups_and_partial_padding(self):
        weight = np.zeros((2, 35), dtype=np.float32)
        weight[1, -1] = 7
        packed, scales = pack_weights(weight, 16)
        self.assertEqual(packed.shape, (2, 3, 8))
        self.assertEqual(packed.nbytes, 48)
        self.assertEqual(scales.nbytes, 24)
        np.testing.assert_array_equal(scales, np.ones((2, 3), np.float32))
        np.testing.assert_array_equal(unpack_weights(packed, scales, 35), weight)
        packed[0, -1, -1] = 0x89
        with self.assertRaisesRegex(ValueError, "padding"):
            unpack_weights(packed, scales, 35)

    def test_unused_code_and_scale_shape_rejected(self):
        packed, scales = pack_weights(np.ones((2, 16), np.float32), 16)
        with self.assertRaisesRegex(ValueError, "Scale shape"):
            unpack_weights(packed, scales.T, 16)
        packed[0, 0, 0] = 0x80
        with self.assertRaisesRegex(ValueError, "unused"):
            unpack_weights(packed, scales, 16)

    def test_nonfinite_weights_and_underflow_rejected(self):
        weight = np.zeros((1, 16), dtype=np.float32)
        weight[0, 0] = np.inf
        with self.assertRaisesRegex(ValueError, "finite"):
            pack_weights(weight, 16)
        weight[0, 0] = np.nextafter(np.float32(0), np.float32(1))
        with self.assertRaisesRegex(ValueError, "underflowed"):
            pack_weights(weight, 16)

    def test_unequal_group_scales_match_independent_oracle(self):
        weight = np.arange(64, dtype=np.float32).reshape(2, 32) / 7
        weight[:, 16:] *= 100
        packed, scales = pack_weights(weight, 16)
        self.assertTrue(np.all(scales[:, 1] > scales[:, 0]))
        np.testing.assert_array_equal(unpack_weights(packed, scales, 32), reference_weights(weight, 16))


class GraphTests(unittest.TestCase):
    def test_real_cpu_butterfly_and_packed_projection(self):
        rng = np.random.default_rng(71)
        weight = rng.normal(size=(4, 32)).astype(np.float32)
        bias = rng.normal(size=4).astype(np.float32)
        inputs = rng.normal(size=(2, 32)).astype(np.float32)
        signs = rng.choice([-1, 1], size=32).astype(np.int8)
        rotation = dense_rotation(signs)
        rotated_weight = (weight.astype(np.float64) @ rotation).astype(np.float32)
        builder = GraphBuilder()
        rotated = builder.hadamard("input", signs, "rotation")
        result = builder.linear(rotated, rotated_weight, bias, "linear", 16)
        model = builder.model(32, 4, result)
        self.assertFalse(any(node.op_type == "MatMul" for node in model.graph.node))
        reference = inputs.astype(np.float64) @ rotation @ reference_weights(rotated_weight, 16).T + bias
        with tempfile.TemporaryDirectory() as temp:
            actual, evidence = execute_graph(model, inputs, Path(temp), "small")
            self.assertTrue(error_metrics(actual, reference)["passed"])
            self.assertEqual(evidence["operator_execution_counts"]["MatMulNBits"], 1)
            with self.assertRaises(FileExistsError):
                execute_graph(model, inputs, Path(temp), "small")

    def test_zero_reference_uses_absolute_and_relative_conformance(self):
        self.assertTrue(error_metrics(np.zeros((1, 2)), np.zeros((1, 2)))["passed"])
        self.assertFalse(error_metrics(np.ones((1, 2)), np.zeros((1, 2)))["passed"])

    def test_two_block_network_catches_invalid_rotation_placement(self):
        fixture = mlp_fixture()
        original = mlp_reference(fixture, "original")
        with tempfile.TemporaryDirectory() as temp:
            for placement in ("post_gelu", "before_gelu", "wrong_inverse"):
                model = build_mlp_graph(fixture, placement)
                actual, _ = execute_graph(model, fixture["input"], Path(temp), placement)
                self.assertTrue(error_metrics(actual, mlp_reference(fixture, placement))["passed"])
                self.assertEqual(error_metrics(actual, original)["passed"], placement == "post_gelu")

    def test_control_runner_preserves_previous_artifacts(self):
        with tempfile.TemporaryDirectory() as temp:
            prior = Path(temp) / "prior_failure.txt"
            prior.write_text("keep this failed observation")
            with self.assertRaises(FileExistsError):
                run_controls(Path(temp))
            self.assertEqual(prior.read_text(), "keep this failed observation")


if __name__ == "__main__":
    unittest.main()
