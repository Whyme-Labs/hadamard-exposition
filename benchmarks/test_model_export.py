"""Generated-input tests of full-graph surgery, without pretrained model access."""

from copy import deepcopy
from hashlib import sha256
import json
import math
from pathlib import Path
import resource
import sys
import time
from types import SimpleNamespace
import unittest

import numpy as np
import onnx
from onnx import TensorProto, helper, numpy_helper
import onnxruntime as ort

from model_export import (ARMS, INPUT_NAMES, PRODUCTION_CONFIG, SITES, audit_graph_pair,
                          fixed_signs, locate_sites, model_inputs, rewrite_arm,
                          rotated_weight, validate_reference_config,
                          normalize_fp32_scalar_casts)
from onnx_controls import GraphBuilder, dense_rotation, reference_weights


def fixture_graph() -> tuple[onnx.ModelProto, list[dict]]:
    """A six-layer residual fixture with named, explicitly transposed parameters."""
    rng = np.random.Generator(np.random.PCG64(73))
    builder = GraphBuilder()
    value, layers = "input", []
    for index, site in enumerate(SITES):
        weight = rng.normal(0, .04, (32, 32)).astype(np.float32)
        bias = rng.normal(0, .07, 32).astype(np.float32)
        # Unequal group ranges detect an accidentally shared row-wide scale.
        weight[:, 16:] *= np.float32(5)
        layers.append({"weight": weight, "bias": bias})
        prefix = f"/model/gpt_neox/layers.{index}/mlp/"
        activated = builder.gelu(value, prefix + "act/gelu")
        weight_name = builder.constant("model." + site + ".weight", weight)
        bias_name = builder.constant("model." + site + ".bias", bias)
        transpose = builder.operation("Transpose", [weight_name], prefix + "down_transposed", perm=[1, 0])
        product = builder.operation("MatMul", [activated, transpose], prefix + "down_product")
        biased = builder.operation("Add", [product, bias_name], prefix + "down_biased")
        value = builder.operation("Add", [value, biased], prefix + "residual")
    builder.operation("Identity", [value], "output")
    graph = helper.make_graph(builder.nodes, "rank3_six_projection_fixture",
                              [helper.make_tensor_value_info("input", TensorProto.FLOAT, ["B", "S", 32])],
                              [helper.make_tensor_value_info("output", TensorProto.FLOAT, ["B", "S", 32])],
                              initializer=builder.initializers)
    model = helper.make_model(graph, ir_version=10,
                              opset_imports=[helper.make_opsetid("", 18)])
    onnx.checker.check_model(model)
    return model, layers


def scalar_network(inputs: np.ndarray, layers: list[dict], rotated: bool, group: int | None) -> np.ndarray:
    """Independent float64 GELU, dense Sylvester and scalar quantization oracle."""
    value = inputs.astype(np.float64)
    for index, layer in enumerate(layers):
        erf = np.array([math.erf(float(x) / math.sqrt(2)) for x in value.flat]).reshape(value.shape)
        activated = .5 * value * (1 + erf)
        weight = layer["weight"]
        if rotated:
            q = dense_rotation(fixed_signs(index, 32))
            activated = activated @ q
            weight = (weight.astype(np.float64) @ q).astype(np.float32)
        weight = reference_weights(weight, group) if group else weight.astype(np.float64)
        value = value + activated @ weight.T + layer["bias"]
    return value


def session(model: onnx.ModelProto):
    options = ort.SessionOptions()
    options.intra_op_num_threads = options.inter_op_num_threads = 1
    options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
    options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_DISABLE_ALL
    return ort.InferenceSession(model.SerializeToString(), sess_options=options,
                                providers=["CPUExecutionProvider"])


class BasisTests(unittest.TestCase):
    def test_offline_transform_matches_dense_signed_basis(self):
        weight = np.random.default_rng(44).normal(size=(9, 32)).astype(np.float32)
        signs = fixed_signs(4, 32)
        dense = (weight.astype(np.float64) @ dense_rotation(signs)).astype(np.float32)
        actual = rotated_weight(weight, signs)
        np.testing.assert_array_equal(actual, dense)
        inverse = (weight.astype(np.float64) @ dense_rotation(signs).T).astype(np.float32)
        self.assertGreater(float(np.linalg.norm(actual - inverse)), 1)

    def test_layer_sign_seeds_are_exact_and_distinct(self):
        observed = []
        for index in range(6):
            expected = np.random.Generator(np.random.PCG64(20261017 + index)).choice([-1, 1], 2048)
            values = fixed_signs(index)
            np.testing.assert_array_equal(values, expected)
            self.assertEqual(values.dtype, np.int8)
            observed.append(values.tobytes())
        self.assertEqual(len(set(observed)), 6)

    def test_invalid_rotation_inputs_fail(self):
        with self.assertRaises(ValueError):
            fixed_signs(6)
        with self.assertRaises(ValueError):
            fixed_signs(0, 30)
        with self.assertRaises(ValueError):
            rotated_weight(np.ones((2, 32), np.float64), fixed_signs(0, 32))
        with self.assertRaises(ValueError):
            rotated_weight(np.full((2, 32), np.nan, np.float32), fixed_signs(0, 32))


class ExportScalarTests(unittest.TestCase):
    @staticmethod
    def graph(value=.3535533905932738):
        constant = helper.make_node("Constant", [], ["coefficient"], name="python_scalar",
                                    value=numpy_helper.from_array(np.asarray(value, np.float64)))
        nodes = [constant,
                 helper.make_node("Cast", ["coefficient"], ["scale"], name="scale_cast", to=TensorProto.FLOAT),
                 helper.make_node("Cast", ["coefficient"], ["offset"], name="offset_cast", to=TensorProto.FLOAT),
                 helper.make_node("Mul", ["input", "scale"], ["scaled"], name="multiply"),
                 helper.make_node("Add", ["scaled", "offset"], ["output"], name="offset")]
        graph = helper.make_graph(nodes, "lowered_python_scalar",
                                  [helper.make_tensor_value_info("input", TensorProto.FLOAT, [3])],
                                  [helper.make_tensor_value_info("output", TensorProto.FLOAT, [3])])
        return helper.make_model(graph, ir_version=10, opset_imports=[helper.make_opsetid("", 18)])

    def test_scalar_lowering_normalization_is_exactly_equal_in_real_ort(self):
        for value in (1.0, .3535533905932738):
            with self.subTest(value=value):
                graph = self.graph(value)
                inputs = np.array([-31.25, .0003125, 19.00007], np.float32)
                original = session(graph).run(["output"], {"input": inputs})[0]
                original_casts = [deepcopy(node) for node in graph.graph.node if node.op_type == "Cast"]
                evidence = normalize_fp32_scalar_casts(graph)
                converted = session(graph).run(["output"], {"input": inputs})[0]
                np.testing.assert_array_equal(converted, original)
                self.assertEqual(len(evidence), 1)
                self.assertEqual(evidence[0]["stored_value"], float(np.float32(value)))
                self.assertEqual(original_casts, [node for node in graph.graph.node if node.op_type == "Cast"])
                self.assertEqual(normalize_fp32_scalar_casts(graph), [])

    def test_real_double_consumers_non_scalar_and_nonfinite_values_fail(self):
        mixed = self.graph()
        next(node for node in mixed.graph.node if node.name == "offset_cast").attribute[0].i = TensorProto.DOUBLE
        exposed = self.graph()
        exposed.graph.output.append(helper.make_tensor_value_info("coefficient", TensorProto.DOUBLE, []))
        for candidate in (mixed, exposed, self.graph([1.0]), self.graph(float("nan")),
                          self.graph(float("inf")), self.graph(np.finfo(np.float64).max)):
            with self.assertRaises(ValueError):
                normalize_fp32_scalar_casts(candidate)


class InputContractTests(unittest.TestCase):
    def test_production_configuration_rejects_dimension_rope_and_norm_drift(self):
        config = SimpleNamespace(**PRODUCTION_CONFIG)
        validate_reference_config(config)
        for key, bad in (("hidden_size", 32), ("num_hidden_layers", 5), ("rotary_pct", .5),
                         ("rotary_emb_base", 50000), ("rope_scaling", {"rope_type": "linear", "factor": 2}),
                         ("layer_norm_eps", 1e-6), ("hidden_act", "gelu_new"),
                         ("tie_word_embeddings", True), ("use_parallel_residual", False)):
            candidate = SimpleNamespace(**{**PRODUCTION_CONFIG, key: bad})
            with self.subTest(field=key), self.assertRaises(ValueError):
                validate_reference_config(candidate)

    def test_empty_and_nonempty_caches_preserve_batch_and_layer_order(self):
        feed = model_inputs(np.array([1, 2, 3], dtype=np.uint32))
        self.assertEqual(tuple(feed), INPUT_NAMES)
        self.assertEqual(feed["input_ids"].shape, (1, 3))
        self.assertEqual(feed["past_key_5"].shape, (1, 8, 0, 64))
        past = tuple(np.full((2, 8, 7, 64), index, np.float32) for index in range(12))
        feed = model_inputs(np.array([[1], [2]], np.int64), past)
        self.assertEqual(feed["past_value_5"][0, 0, 0, 0], 11)

    def test_bad_tokens_cache_lengths_dtypes_and_context_fail(self):
        for tokens in ([], [-1], [50304], [1.0], [[True]]):
            with self.subTest(tokens=tokens), self.assertRaises(ValueError):
                model_inputs(np.asarray(tokens))
        with self.assertRaises(ValueError):
            model_inputs(np.ones(2049, np.int64))
        past = [np.zeros((1, 8, 4, 64), np.float32) for _ in range(12)]
        for bad in (past[:-1], [past[0].astype(np.float64), *past[1:]],
                    [np.zeros((1, 8, 3, 64), np.float32), *past[1:]]):
            with self.assertRaises(ValueError):
                model_inputs(np.array([1]), bad)


class GraphSurgeryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base, cls.layers = fixture_graph()

    def test_all_six_runtime_arms_match_independent_rank3_network(self):
        rng = np.random.default_rng(54)
        # The same graph is reused across batch and sequence shapes, including
        # the one-token shape used in decoding. No dimensions may be flattened
        # into a stale export-time batch or sequence count.
        for arm, (rotated, group) in ARMS.items():
            with self.subTest(arm=arm):
                graph, audit = rewrite_arm(self.base, arm, input_features=32, output_features=32)
                runtime = session(graph)
                self.assertEqual(runtime.get_providers(), ["CPUExecutionProvider"])
                for shape in ((1, 3, 32), (2, 1, 32), (2, 5, 32)):
                    inputs = rng.normal(0, .3, shape).astype(np.float32)
                    result = runtime.run(["output"], {"input": inputs})[0]
                    expected = scalar_network(inputs, self.layers, rotated, group)
                    self.assertEqual(result.shape, shape)
                    np.testing.assert_allclose(result, expected, rtol=2e-5, atol=2e-6)
                self.assertEqual(audit["matmul_nbits_nodes"], 6 if group else 0)
                self.assertTrue(audit["io_unchanged"])
                self.assertEqual(audit["online_add_nodes"], 30 if rotated else 0)
                if group:
                    self.assertEqual(audit["packed_code_bytes"], 6 * 32 * 32 // 2)
                    self.assertEqual(audit["scale_bytes"], 6 * 32 * 32 // group * 4)

    def test_fp32_original_is_byte_identical_and_legal_rotation_is_invariant(self):
        unchanged, _ = rewrite_arm(self.base, "fp32_original", input_features=32, output_features=32)
        self.assertEqual(unchanged.SerializeToString(), self.base.SerializeToString())
        rotated, _ = rewrite_arm(self.base, "fp32_rotated", input_features=32, output_features=32)
        inputs = np.random.default_rng(43).normal(size=(2, 4, 32)).astype(np.float32)
        original_output = session(self.base).run(["output"], {"input": inputs})[0]
        rotated_output = session(rotated).run(["output"], {"input": inputs})[0]
        np.testing.assert_allclose(rotated_output, original_output, rtol=2e-5, atol=2e-5)

    def test_scope_audit_rejects_unrelated_weight_node_and_io_mutation(self):
        graph, _ = rewrite_arm(self.base, "w4a32_g32_rotated", input_features=32, output_features=32)
        changed_tensor = deepcopy(graph)
        bias = next(t for t in changed_tensor.graph.initializer if t.name.endswith("dense_4h_to_h.bias"))
        bias.CopyFrom(numpy_helper.from_array(numpy_helper.to_array(bias) + np.float32(1), bias.name))
        changed_node = deepcopy(graph)
        next(n for n in changed_node.graph.node if n.name.endswith("/residual")).op_type = "Sub"
        changed_io = deepcopy(graph)
        changed_io.graph.output[0].type.tensor_type.elem_type = TensorProto.DOUBLE
        for candidate in (changed_tensor, changed_node, changed_io):
            with self.assertRaises(ValueError):
                audit_graph_pair(self.base, candidate, "w4a32_g32_rotated",
                                 input_features=32, output_features=32)

    def test_scope_audit_rejects_wrong_rotation_stage_scale_and_operator_precision(self):
        graph, _ = rewrite_arm(self.base, "w4a32_g32_rotated", input_features=32, output_features=32)
        bad_rotation = deepcopy(graph)
        next(n for n in bad_rotation.graph.node if n.name == "hadamard_layer0_stage0_minus").op_type = "Add"
        bad_scale = deepcopy(graph)
        scale = next(t for t in bad_scale.graph.initializer if t.name.endswith(".weight.scales"))
        scale.CopyFrom(numpy_helper.from_array(numpy_helper.to_array(scale) * np.float32(2), scale.name))
        bad_precision = deepcopy(graph)
        quantized = next(n for n in bad_precision.graph.node if n.op_type == "MatMulNBits")
        next(a for a in quantized.attribute if a.name == "accuracy_level").i = 4
        for candidate in (bad_rotation, bad_scale, bad_precision):
            with self.assertRaises(ValueError):
                audit_graph_pair(self.base, candidate, "w4a32_g32_rotated",
                                 input_features=32, output_features=32)

    def test_scope_audit_rejects_operator_version_drift(self):
        graph, _ = rewrite_arm(self.base, "w4a32_g32_original", input_features=32, output_features=32)
        for index in range(2):
            candidate = deepcopy(graph)
            candidate.opset_import[index].version += 1
            with self.assertRaises(ValueError):
                audit_graph_pair(self.base, candidate, "w4a32_g32_original",
                                 input_features=32, output_features=32)

    def test_ambiguous_parameter_use_wrong_orientation_and_wrong_placement_fail(self):
        shared = deepcopy(self.base)
        shared.graph.node.append(helper.make_node("Identity", ["model." + SITES[0] + ".weight"],
                                                  ["extra_weight_use"], name="extra_weight_use"))
        wrong_transpose = deepcopy(self.base)
        transpose = next(n for n in wrong_transpose.graph.node if n.op_type == "Transpose")
        transpose.attribute[0].ints[:] = [0, 1]
        before_gelu = deepcopy(self.base)
        product = next(n for n in before_gelu.graph.node if n.op_type == "MatMul")
        product.input[0] = "input"
        for candidate in (shared, wrong_transpose, before_gelu):
            with self.assertRaises(ValueError):
                locate_sites(candidate, input_features=32, output_features=32)


def run_pinned_stack_probe(output_dir: Path) -> dict:
    """Explicit small-model probe for the isolated pinned converter environment.

    This command is separate from dependency-light unit discovery. It exercises
    the actual Transformers cache and Torch exporter with a randomly initialized
    6-layer / hidden-32 / intermediate-64 / vocabulary-97 GPTNeoX. The production
    exporter must reject this small configuration. No model or data are fetched.
    """
    import torch
    import transformers
    from transformers import GPTNeoXConfig, GPTNeoXForCausalLM
    from model_export import (_trace_reference_graph, export_reference_graph,
                              file_sha256, OUTPUT_NAMES)
    from onnx_controls import error_metrics

    started = time.monotonic()
    output_dir = Path(output_dir)
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError("Preserve the earlier pinned-stack probe directory.")
    output_dir.mkdir(parents=True, exist_ok=True)
    torch.set_num_threads(1)
    if torch.get_num_interop_threads() != 1:
        torch.set_num_interop_threads(1)
    torch.manual_seed(20261017)
    config = GPTNeoXConfig(num_hidden_layers=6, hidden_size=32, intermediate_size=64,
                          num_attention_heads=4, vocab_size=97, max_position_embeddings=64,
                          hidden_act="gelu", rotary_pct=.25, use_parallel_residual=True,
                          hidden_dropout=0, attention_dropout=0, bos_token_id=0, eos_token_id=0)
    config._attn_implementation = "eager"
    model = GPTNeoXForCausalLM(config).eval().requires_grad_(False)
    guard_rejected = False
    try:
        export_reference_graph(model, output_dir / "must-not-export.onnx")
    except ValueError as exc:
        if "configuration differs" not in str(exc):
            raise
        guard_rejected = True
    if not guard_rejected or (output_dir / "must-not-export.onnx").exists():
        raise AssertionError("The production export entry point accepted a tiny model.")

    base = _trace_reference_graph(model, output_dir / "fp32_original.onnx")
    mapped = locate_sites(base, input_features=64, output_features=32)
    initializers = {tensor.name: tensor for tensor in base.graph.initializer}
    for site in mapped:
        exported = numpy_helper.to_array(initializers[site["weight"]])
        actual = model.get_submodule(site["site"]).weight.detach().numpy()
        np.testing.assert_array_equal(exported, actual)

    def empty_cache(batch):
        return tuple(np.empty((batch, 4, 0, 8), np.float32) for _ in range(12))

    def reference(wrapped, tokens, past):
        cache = tuple((torch.from_numpy(past[2 * i]), torch.from_numpy(past[2 * i + 1]))
                      for i in range(6))
        with torch.inference_mode():
            result = wrapped(input_ids=torch.from_numpy(tokens), past_key_values=cache,
                             use_cache=True, return_dict=True, output_attentions=False,
                             output_hidden_states=False)
        if not isinstance(result.past_key_values, tuple):
            raise AssertionError("Pinned legacy inputs did not produce legacy cache outputs.")
        return [result.logits.numpy(), *(value.numpy() for pair in result.past_key_values for value in pair)]

    def run(runtime, tokens, past):
        feed = dict(zip(INPUT_NAMES, (tokens, *past)))
        return runtime.run(list(OUTPUT_NAMES), feed)

    def compare(actual, expected):
        if len(actual) != 13 or len(expected) != 13:
            raise AssertionError("Logits or cache outputs are missing.")
        metrics = []
        for name, observed, reference_value in zip(OUTPUT_NAMES, actual, expected):
            if observed.dtype != np.float32:
                raise AssertionError(f"Output precision differs for {name}.")
            errors = error_metrics(observed, reference_value)
            if not errors["passed"]:
                raise AssertionError(f"Generated pinned-model mismatch for {name}: {errors}")
            metrics.append({"output": name, "shape": list(observed.shape), **errors})
        return metrics

    rng = np.random.Generator(np.random.PCG64(20261017))
    fixtures = []
    for batch, sequence, past_length in ((1, 1, 0), (1, 7, 0), (2, 3, 0), (2, 2, 5)):
        tokens = rng.integers(1, 97, (batch, sequence), dtype=np.int64)
        past = tuple(rng.normal(index / 100, .03, (batch, 4, past_length, 8)).astype(np.float32)
                     for index in range(12)) if past_length else empty_cache(batch)
        fixtures.append((tokens, past))

    def transformed_reference(rotated, group):
        copied = deepcopy(model)
        for index, site in enumerate(SITES):
            linear = copied.get_submodule(site)
            weight = model.get_submodule(site).weight.detach().numpy().copy()
            if rotated:
                q = dense_rotation(fixed_signs(index, 64))
                weight = (weight.astype(np.float64) @ q).astype(np.float32)
                # Dense float64 multiplication is confined to this independent
                # small reference; exported treatment graphs use FP32 butterflies.
                rotation = torch.from_numpy(q)
                linear.register_forward_pre_hook(
                    lambda _module, inputs, rotation=rotation: ((inputs[0].double() @ rotation).float(),))
            if group:
                weight = reference_weights(weight, group).astype(np.float32)
            with torch.no_grad():
                linear.weight.copy_(torch.from_numpy(weight))
        return copied

    receipt = {
        "schema_version": "hadamard-generated-gptneox-export.v1", "status": "running",
        "scope": "Randomly initialized small GPTNeoX export/cache conformance; no pretrained model or dataset.",
        "full_pythia_parity_established": False,
        "production_config_guard_rejected_small_model": guard_rejected,
        "versions": {"torch": torch.__version__, "transformers": transformers.__version__,
                     "onnx": onnx.__version__, "onnxruntime": ort.__version__, "numpy": np.__version__},
        "dimensions": {"layers": 6, "hidden": 32, "intermediate": 64, "heads": 4,
                       "head_width": 8, "vocabulary": 97, "context": 64},
        "exact_named_parameter_orientation_verified": True, "arms": [],
        "export_scalar_normalizations": next((json.loads(item.value) for item in base.metadata_props
                                               if item.key == "hadamard.fp32_scalar_normalizations.v1"), []),
    }
    for arm_id, (rotated, group) in ARMS.items():
        graph, audit = rewrite_arm(base, arm_id, input_features=64, output_features=32)
        path = output_dir / f"{arm_id}.onnx"
        if arm_id != "fp32_original":
            onnx.save_model(graph, path)
        runtime = session(graph)
        oracle = transformed_reference(rotated, group)
        cases = []
        for tokens, past in fixtures:
            actual = run(runtime, tokens, past)
            expected = reference(oracle, tokens, past)
            metrics = compare(actual, expected)
            for original, present in zip(past, actual[1:]):
                np.testing.assert_array_equal(present[:, :, :original.shape[2], :], original)
            cases.append({"batch": tokens.shape[0], "sequence": tokens.shape[1],
                          "past_sequence": past[0].shape[2], "prior_cache_prefix_exact": True,
                          "metrics": metrics})
        # Compare one complete request with an empty-cache prefill followed by
        # five cached one-token steps. This catches wrong position offsets,
        # stale masks, or a present cache that drops/reorders earlier tokens.
        tokens = rng.integers(1, 97, (1, 10), dtype=np.int64)
        full = run(runtime, tokens, empty_cache(1))
        actual = run(runtime, tokens[:, :5], empty_cache(1))
        expected = reference(oracle, tokens[:, :5], empty_cache(1))
        decode_metrics = [compare(actual, expected)]
        pieces = [actual[0]]
        for index in range(5, 10):
            actual = run(runtime, tokens[:, index:index + 1], tuple(actual[1:]))
            expected = reference(oracle, tokens[:, index:index + 1], tuple(expected[1:]))
            decode_metrics.append(compare(actual, expected))
            pieces.append(actual[0])
        compare([np.concatenate(pieces, axis=1), *actual[1:]], full)
        altered_future = tokens.copy()
        altered_future[:, 7:] = (altered_future[:, 7:] + 1) % 97
        future = run(runtime, altered_future, empty_cache(1))
        np.testing.assert_array_equal(full[0][:, :7, :], future[0][:, :7, :])
        receipt["arms"].append({"arm": arm_id, "graph_sha256": file_sha256(path),
                                "graph_bytes": path.stat().st_size, "audit": audit,
                                "cases": cases, "decode_metrics": decode_metrics,
                                "full_request_vs_cached_request_passed": True,
                                "future_token_change_preserved_prefix_logits": True})
        del runtime, oracle, graph
    receipt["elapsed_seconds"] = time.monotonic() - started
    receipt["worker_peak_rss_bytes"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
    receipt["status"] = "passed"
    receipt["source_hashes"] = {name: sha256((Path(__file__).parent / name).read_bytes()).hexdigest()
                                 for name in ("model_export.py", "test_model_export.py", "contract.py", "onnx_controls.py")}
    if receipt["worker_peak_rss_bytes"] > 1024 ** 3 or receipt["elapsed_seconds"] > 180:
        receipt["status"] = "resource_limit_exceeded"
    (output_dir / "probe.json").write_text(json.dumps(receipt, indent=2) + "\n")
    if receipt["status"] != "passed":
        raise AssertionError("The generated pinned-stack probe exceeded its resource ceiling.")
    return receipt


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--pinned-stack-probe":
        result = run_pinned_stack_probe(Path(sys.argv[2]))
        print(json.dumps({"status": result["status"], "elapsed_seconds": result["elapsed_seconds"],
                          "worker_peak_rss_bytes": result["worker_peak_rss_bytes"],
                          "receipt": str(Path(sys.argv[2]) / "probe.json")}))
    else:
        unittest.main()
