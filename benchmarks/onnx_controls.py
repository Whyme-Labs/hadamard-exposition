"""Synthetic conformance controls for the proposed ORT W4A32 model adapter.

The runtime graphs use packed MatMulNBits weights and Add/Sub Hadamard
butterflies. Dense float64 matrices exist only in independent references.
Nothing in this module loads a pretrained model or measures performance.
"""

from __future__ import annotations

from collections import Counter
from contextlib import contextmanager
from hashlib import sha256
import math
import os
from pathlib import Path
import json

import numpy as np
import onnx
from onnx import TensorProto, helper, numpy_helper
import onnxruntime as ort


FIXTURE_SEED = 20261017
RELATIVE_TOLERANCE = 1e-5
ABSOLUTE_TOLERANCE = 1e-3


def _group_size(group_size: int) -> None:
    if type(group_size) is not int or group_size not in (16, 32):
        raise ValueError("The frozen controls support group sizes 16 and 32.")


def pack_weights(weight: np.ndarray, group_size: int) -> tuple[np.ndarray, np.ndarray]:
    """Pack output-by-input weights with maxabs/7 scales and zero padding.

    Return uint8 [N, ceil(K/g), g/2] bytes and float32 [N, ceil(K/g)]
    scales. Signed codes -7..7 are stored as q+8, low nibble first.
    Entirely zero groups use scale 1. Padding is the zero code 8.
    """
    _group_size(group_size)
    weight = np.asarray(weight)
    if weight.ndim != 2 or min(weight.shape) < 1 or weight.dtype != np.float32:
        raise ValueError("Weights must be a nonempty float32 [N,K] matrix.")
    if not np.isfinite(weight).all():
        raise ValueError("Weights must be finite.")
    n, k = weight.shape
    groups = (k + group_size - 1) // group_size
    padded = np.zeros((n, groups * group_size), dtype=np.float32)
    padded[:, :k] = weight
    blocks = padded.reshape(n, groups, group_size)
    maximum = np.max(np.abs(blocks), axis=-1)
    scales = np.where(maximum == 0, np.float32(1), maximum / np.float32(7))
    if not np.isfinite(scales).all() or np.any(scales <= 0):
        raise ValueError("A nonzero group scale underflowed or is invalid.")
    signed = np.clip(np.rint(blocks / scales[..., None]), -7, 7).astype(np.int8)
    encoded = (signed.astype(np.int16) + 8).astype(np.uint8)
    packed = encoded[..., 0::2] | (encoded[..., 1::2] << 4)
    return packed, scales.astype(np.float32)


def unpack_weights(packed: np.ndarray, scales: np.ndarray, input_features: int) -> np.ndarray:
    """Validate and independently decode stored nibbles into float64 weights."""
    packed, scales = np.asarray(packed), np.asarray(scales)
    if packed.dtype != np.uint8 or packed.ndim != 3 or min(packed.shape) < 1:
        raise ValueError("Packed weights must be nonempty uint8 [N,groups,g/2].")
    n, groups, half_group = packed.shape
    group = half_group * 2
    _group_size(group)
    if type(input_features) is not int or input_features < 1:
        raise ValueError("Input feature count must be a positive integer.")
    if groups != (input_features + group - 1) // group:
        raise ValueError("Packed group count disagrees with the input width.")
    if scales.dtype != np.float32 or scales.shape != (n, groups):
        raise ValueError("Scale shape or dtype is invalid.")
    if not np.isfinite(scales).all() or np.any(scales <= 0):
        raise ValueError("Scales must be finite and positive.")
    decoded = np.empty((n, groups * group), dtype=np.int8)
    # Scalar decoding intentionally avoids the vectorized packer's layout code.
    for output in range(n):
        for block in range(groups):
            for byte_index, byte in enumerate(packed[output, block]):
                for nibble, shift in enumerate((0, 4)):
                    code = (int(byte) >> shift) & 15
                    if code == 0:
                        raise ValueError("The unused signed -8 code is present.")
                    feature = block * group + byte_index * 2 + nibble
                    if feature >= input_features and code != 8:
                        raise ValueError("A padding nibble does not encode zero.")
                    decoded[output, feature] = code - 8
    expanded = np.repeat(scales.astype(np.float64), group, axis=1)
    return (decoded * expanded)[:, :input_features]


def reference_weights(weight: np.ndarray, group_size: int) -> np.ndarray:
    """Scalar quantizer oracle, independent of nibble packing and unpacking."""
    result = np.empty(weight.shape, dtype=np.float64)
    for output, row in enumerate(weight):
        for start in range(0, len(row), group_size):
            values = row[start : start + group_size]
            maximum = max(abs(float(value)) for value in values)
            scale = np.float32(1 if maximum == 0 else np.float32(maximum) / np.float32(7))
            for offset, value in enumerate(values):
                code = max(-7, min(7, round(float(np.float32(value / scale)))))
                result[output, start + offset] = code * float(scale)
    return result


def dense_rotation(signs: np.ndarray) -> np.ndarray:
    """Independent Sylvester reference; never serialized into runtime graphs."""
    n = len(signs)
    if n < 1 or n & (n - 1) or not np.isin(signs, (-1, 1)).all():
        raise ValueError("Rotation requires power-of-two width and signs +/-1.")
    matrix = np.ones((1, 1), dtype=np.float64)
    while len(matrix) < n:
        matrix = np.block([[matrix, matrix], [matrix, -matrix]])
    return signs[:, None] * matrix / math.sqrt(n)


class GraphBuilder:
    """Small ONNX graph builder for projection and residual-MLP controls."""

    def __init__(self) -> None:
        self.nodes: list = []
        self.initializers: list = []

    def constant(self, name: str, value: np.ndarray) -> str:
        self.initializers.append(numpy_helper.from_array(np.asarray(value), name=name))
        return name

    def operation(self, kind: str, inputs: list[str], output: str, **attributes) -> str:
        self.nodes.append(helper.make_node(kind, inputs, [output], name=output, **attributes))
        return output

    def hadamard(self, value: str, signs: np.ndarray, prefix: str, *, inverse: bool = False) -> str:
        """Apply x D H/sqrt(K), or x H D/sqrt(K) for the inverse control."""
        signs = np.asarray(signs)
        k = signs.size
        if signs.ndim != 1 or k < 1 or k & (k - 1) or not np.isin(signs, (-1, 1)).all():
            raise ValueError("Hadamard input width must be a power of two with signs +/-1.")
        sign_name = self.constant(prefix + "_signs", signs.astype(np.float32))
        if not inverse:
            value = self.operation("Mul", [value, sign_name], prefix + "_signed")
        for stage in range(k.bit_length() - 1):
            half = 1 << stage
            label = f"{prefix}_stage{stage}"
            shape = self.constant(label + "_shape", np.array([-1, k // (2 * half), 2, half], np.int64))
            split = self.constant(label + "_split", np.array([1, 1], np.int64))
            flat = self.constant(label + "_flatshape", np.array([-1, k], np.int64))
            view = self.operation("Reshape", [value, shape], label + "_view")
            left, right = label + "_left", label + "_right"
            self.nodes.append(helper.make_node("Split", [view, split], [left, right], name=label + "_splitop", axis=2))
            plus = self.operation("Add", [left, right], label + "_plus")
            minus = self.operation("Sub", [left, right], label + "_minus")
            joined = self.operation("Concat", [plus, minus], label + "_join", axis=2)
            value = self.operation("Reshape", [joined, flat], label + "_flat")
        scale = self.constant(prefix + "_scale", np.array(1 / math.sqrt(k), np.float32))
        value = self.operation("Mul", [value, scale], prefix + "_normalized")
        return self.operation("Mul", [value, sign_name], prefix + "_inverse_signed") if inverse else value

    def linear(self, value: str, weight: np.ndarray, bias: np.ndarray, prefix: str, group: int | None = None) -> str:
        bias_name = self.constant(prefix + "_bias", bias)
        if group is None:
            weights = self.constant(prefix + "_weight", weight.T.copy())
            product = self.operation("MatMul", [value, weights], prefix + "_product")
            return self.operation("Add", [product, bias_name], prefix + "_output")
        packed, scales = pack_weights(weight, group)
        weights = self.constant(prefix + "_packed", packed)
        scale_name = self.constant(prefix + "_scales", scales)
        return self.operation("MatMulNBits", [value, weights, scale_name, "", "", bias_name],
                              prefix + "_output", domain="com.microsoft", K=weight.shape[1],
                              N=weight.shape[0], bits=4, block_size=group, accuracy_level=1)

    def layer_norm(self, value: str, scale: np.ndarray, bias: np.ndarray, prefix: str) -> str:
        gamma = self.constant(prefix + "_gamma", scale)
        beta = self.constant(prefix + "_beta", bias)
        return self.operation("LayerNormalization", [value, gamma, beta], prefix + "_output", axis=-1, epsilon=1e-5)

    def gelu(self, value: str, prefix: str) -> str:
        root_two = self.constant(prefix + "_sqrt_two", np.array(math.sqrt(2), np.float32))
        half = self.constant(prefix + "_half", np.array(.5, np.float32))
        one = self.constant(prefix + "_one", np.array(1, np.float32))
        normalized = self.operation("Div", [value, root_two], prefix + "_normalized")
        erf = self.operation("Erf", [normalized], prefix + "_erf")
        offset = self.operation("Add", [erf, one], prefix + "_offset")
        product = self.operation("Mul", [value, offset], prefix + "_product")
        return self.operation("Mul", [product, half], prefix + "_output")

    def model(self, input_width: int, output_width: int, value: str) -> onnx.ModelProto:
        self.operation("Identity", [value], "output")
        graph = helper.make_graph(self.nodes, "synthetic_hadamard_conformance",
                                  [helper.make_tensor_value_info("input", TensorProto.FLOAT, [None, input_width])],
                                  [helper.make_tensor_value_info("output", TensorProto.FLOAT, [None, output_width])],
                                  initializer=self.initializers)
        model = helper.make_model(graph, producer_name="hadamard-exposition-controls",
                                  opset_imports=[helper.make_opsetid("", 18), helper.make_opsetid("com.microsoft", 1)],
                                  ir_version=10)
        onnx.checker.check_model(model)
        return model


def error_metrics(actual: np.ndarray, reference: np.ndarray) -> dict:
    if actual.shape != reference.shape or not np.isfinite(actual).all() or not np.isfinite(reference).all():
        raise AssertionError("Output shape or finiteness check failed.")
    difference = actual.astype(np.float64) - reference.astype(np.float64)
    norm = float(np.linalg.norm(reference.astype(np.float64)))
    absolute = float(np.max(np.abs(difference)))
    relative = float(np.linalg.norm(difference) / norm) if norm else (0.0 if absolute == 0 else None)
    passed = relative is not None and relative <= RELATIVE_TOLERANCE and absolute <= ABSOLUTE_TOLERANCE
    return {"relative_frobenius_error": relative, "max_absolute_error": absolute, "passed": passed}


@contextmanager
def _native_log(path: Path):
    """Capture ORT's native stderr in this sequential fixture process."""
    previous = os.dup(2)
    try:
        with path.open("wb") as log:
            os.dup2(log.fileno(), 2)
            yield
    finally:
        os.dup2(previous, 2)
        os.close(previous)


def execute_graph(model: onnx.ModelProto, inputs: np.ndarray, output_dir: Path, name: str) -> tuple[np.ndarray, dict]:
    """Execute a real CPU session and retain graph, native log and profile."""
    graph_path, log_path = output_dir / f"{name}.onnx", output_dir / f"{name}.ort.log"
    profile_path = output_dir / f"{name}.profile.json"
    if any(path.exists() for path in (graph_path, log_path, profile_path)):
        raise FileExistsError(f"Refusing to overwrite control artifacts for {name}.")
    onnx.save_model(model, graph_path)
    options = ort.SessionOptions()
    options.intra_op_num_threads = 1
    options.inter_op_num_threads = 1
    options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
    options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_DISABLE_ALL
    options.enable_profiling = True
    options.profile_file_prefix = str(output_dir / name)
    options.log_severity_level = 1
    with _native_log(log_path):
        session = ort.InferenceSession(str(graph_path), sess_options=options, providers=["CPUExecutionProvider"])
        try:
            result = session.run(["output"], {"input": np.asarray(inputs, dtype=np.float32)})[0]
            providers = session.get_providers()
        finally:
            created_profile = Path(session.end_profiling())
            created_profile.rename(profile_path)
    events = json.loads(profile_path.read_text())
    nodes = [event for event in events if event.get("cat") == "Node" and event.get("args", {}).get("provider")]
    operators = Counter(event["args"].get("op_name", "unknown") for event in nodes)
    observed_providers = sorted({event["args"]["provider"] for event in nodes})
    if providers != ["CPUExecutionProvider"] or observed_providers != ["CPUExecutionProvider"]:
        raise AssertionError("CPU provider execution was not established.")
    expected_quantized = sum(node.op_type == "MatMulNBits" for node in model.graph.node)
    if operators["MatMulNBits"] != expected_quantized:
        raise AssertionError("Profile does not contain every expected MatMulNBits execution.")
    evidence = {"session_providers": providers, "observed_providers": observed_providers,
                "operator_execution_counts": dict(sorted(operators.items())),
                "unpacked_fallback_message_present": "unpacked compute mode" in log_path.read_text(),
                "internal_mlas_path": "not established by operator profiling",
                "graph": graph_path.name, "profile": profile_path.name, "runtime_log": log_path.name}
    return result, evidence


def _packing_evidence(weight: np.ndarray, group: int) -> tuple[np.ndarray, dict]:
    packed, scales = pack_weights(weight, group)
    decoded = unpack_weights(packed, scales, weight.shape[1])
    independent = reference_weights(weight, group)
    if not np.array_equal(decoded, independent):
        raise AssertionError("Serialized weights disagree with the independent scalar quantizer.")
    n, k = weight.shape
    groups = (k + group - 1) // group
    expected_bytes = n * groups * group // 2
    if packed.nbytes != expected_bytes or scales.nbytes != n * groups * 4:
        raise AssertionError("Packed weight or scale byte count is incorrect.")
    return independent, {
        "input_features": k, "output_features": n, "group_size": group,
        "packed_shape": list(packed.shape), "scales_shape": list(scales.shape),
        "weight_code_bytes": packed.nbytes, "scale_bytes": scales.nbytes,
        "payload_bytes": packed.nbytes + scales.nbytes,
        "padding_code_count": n * (groups * group - k),
        "padding_equivalent_bytes": n * (groups * group - k) / 2,
        "packed_sha256": sha256(packed.tobytes()).hexdigest(),
        "scales_sha256": sha256(scales.tobytes()).hexdigest(),
        "decoded_matches_scalar_quantizer": True,
        "scale_dtype": "float32", "code_range": [-7, 7], "stored_zero_code": 8,
    }


def mlp_fixture() -> dict:
    """Deterministic two-block network with synthetic learned norm parameters."""
    rng = np.random.default_rng(FIXTURE_SEED + 1)
    layers = []
    for _ in range(2):
        layers.append({
            "gamma": rng.uniform(.7, 1.3, 16).astype(np.float32),
            "beta": rng.normal(0, .2, 16).astype(np.float32),
            "up_weight": rng.normal(0, .3, (32, 16)).astype(np.float32),
            "up_bias": rng.normal(0, .2, 32).astype(np.float32),
            "down_weight": rng.normal(0, .2, (16, 32)).astype(np.float32),
            "down_bias": rng.normal(0, .2, 16).astype(np.float32),
            "signs": rng.choice([-1, 1], 32).astype(np.int8),
        })
    return {"input": rng.normal(size=(3, 16)).astype(np.float32), "layers": layers,
            "head_weight": rng.normal(0, .2, (11, 16)).astype(np.float32),
            "head_bias": rng.normal(0, .1, 11).astype(np.float32)}


def _placement(placement: str) -> None:
    if placement not in {"original", "post_gelu", "before_gelu", "wrong_inverse"}:
        raise ValueError("Unknown rotation placement.")


def build_mlp_graph(fixture: dict, placement: str, group: int | None = None) -> onnx.ModelProto:
    _placement(placement)
    builder = GraphBuilder()
    state = "input"
    for index, layer in enumerate(fixture["layers"]):
        prefix = f"block{index}"
        value = builder.layer_norm(state, layer["gamma"], layer["beta"], prefix + "_norm")
        value = builder.linear(value, layer["up_weight"], layer["up_bias"], prefix + "_up")
        if placement == "before_gelu":
            value = builder.hadamard(value, layer["signs"], prefix + "_rotation")
        value = builder.gelu(value, prefix + "_gelu")
        if placement in {"post_gelu", "wrong_inverse"}:
            value = builder.hadamard(value, layer["signs"], prefix + "_rotation", inverse=placement == "wrong_inverse")
        weight = layer["down_weight"]
        if placement != "original":
            weight = (weight.astype(np.float64) @ dense_rotation(layer["signs"])).astype(np.float32)
        value = builder.linear(value, weight, layer["down_bias"], prefix + "_down", group)
        state = builder.operation("Add", [state, value], prefix + "_residual")
    logits = builder.linear(state, fixture["head_weight"], fixture["head_bias"], "head")
    return builder.model(16, 11, logits)


def mlp_reference(fixture: dict, placement: str, group: int | None = None) -> np.ndarray:
    """Float64 network reference with scalar quantization and math.erf GELU."""
    _placement(placement)
    state = fixture["input"].astype(np.float64)
    for layer in fixture["layers"]:
        centered = state - state.mean(axis=-1, keepdims=True)
        value = centered / np.sqrt(np.mean(centered * centered, axis=-1, keepdims=True) + 1e-5)
        value = value * layer["gamma"] + layer["beta"]
        value = value @ layer["up_weight"].astype(np.float64).T + layer["up_bias"]
        rotation = dense_rotation(layer["signs"])
        if placement == "before_gelu":
            value = value @ rotation
        erf = np.fromiter((math.erf(float(v) / math.sqrt(2)) for v in value.flat), dtype=np.float64).reshape(value.shape)
        value = .5 * value * (1 + erf)
        if placement == "post_gelu":
            value = value @ rotation
        elif placement == "wrong_inverse":
            value = value @ rotation.T
        weight = layer["down_weight"]
        if placement != "original":
            weight = (weight.astype(np.float64) @ rotation).astype(np.float32)
        weight = reference_weights(weight, group) if group is not None else weight.astype(np.float64)
        state = state + value @ weight.T + layer["down_bias"]
    return state @ fixture["head_weight"].astype(np.float64).T + fixture["head_bias"]


def run_controls(output_dir: Path) -> dict:
    """Run the frozen synthetic controls once, preserving successes and failures.

    The caller supplies an absent or empty artifact directory and applies the
    outer resource deadline. The returned receipt is JSON serializable. Runtime
    profiles identify CPU operator execution, not an internal MLAS kernel path.
    """
    output_dir = Path(output_dir)
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError("Control output directory must be absent or empty.")
    output_dir.mkdir(parents=True, exist_ok=True)
    controls = []

    def check(name, action):
        try:
            evidence = action()
            controls.append({"name": name, "status": "passed", **evidence})
        except Exception as exc:
            controls.append({"name": name, "status": "failed", "error_type": type(exc).__name__, "error": str(exc)})

    def projection_case(name, inputs, weight, bias, group, signs=None, cached=None):
        builder = GraphBuilder()
        value = "input"
        reference_input = inputs.astype(np.float64)
        if signs is not None:
            value = builder.hadamard(value, signs, "rotation")
            reference_input = reference_input @ dense_rotation(signs)
        reference_weight, packing = cached if cached is not None else _packing_evidence(weight, group)
        value = builder.linear(value, weight, bias, "projection", group)
        model = builder.model(weight.shape[1], weight.shape[0], value)
        if any(node.op_type in {"MatMul", "Gemm"} for node in model.graph.node):
            raise AssertionError("The projection graph contains a dense matrix operation.")
        actual, profile = execute_graph(model, inputs, output_dir, name)
        metrics = error_metrics(actual, reference_input @ reference_weight.T + bias)
        if not metrics["passed"]:
            raise AssertionError(f"Projection conformance failed: {metrics}")
        return {"input_shape": list(inputs.shape), "packing": packing, "errors": metrics,
                "runtime": profile, "rotation": signs is not None,
                "butterfly_additions": sum(node.op_type == "Add" for node in model.graph.node),
                "butterfly_subtractions": sum(node.op_type == "Sub" for node in model.graph.node)}

    # One-hot inputs reveal every decoded coefficient, including half-way cases.
    edge_weight = np.zeros((4, 32), dtype=np.float32)
    edge_weight[1] = np.tile(np.array(list(range(-7, 8)) + [0], np.float32), 2)
    edge_weight[2] = np.tile(np.array([-7, -2.5, -1.5, -.5, 0, .5, 1.5, 2.5, 7] + [0] * 7, np.float32), 2)
    edge_weight[3, :16] = np.arange(16, dtype=np.float32) / 20
    edge_weight[3, 16:] = np.arange(16, dtype=np.float32) * 20
    for group in (32, 16):
        name = f"edge_codes_g{group}"
        check(name, lambda group=group, name=name: projection_case(
            name, np.eye(32, dtype=np.float32), edge_weight, np.zeros(4, np.float32), group))
        padding_weight = np.zeros((2, 35), dtype=np.float32)
        padding_weight[0, :16] = np.arange(16, dtype=np.float32)
        padding_weight[1, -3:] = [-7, .5, 7]
        name = f"partial_padding_g{group}"
        check(name, lambda group=group, name=name, weight=padding_weight: projection_case(
            name, np.eye(35, dtype=np.float32), weight, np.zeros(2, np.float32), group))

    # The actual Pythia projection shape, with fixed original and rotated data.
    rng = np.random.default_rng(FIXTURE_SEED)
    weight = (rng.normal(size=(512, 2048)) / math.sqrt(2048)).astype(np.float32)
    inputs = rng.normal(size=(8, 2048)).astype(np.float32)
    inputs[:, 0] *= np.float32(16)
    # This projection's external input is explicitly a post-GELU activation.
    erf = np.fromiter((math.erf(float(v) / math.sqrt(2)) for v in inputs.flat), dtype=np.float64).reshape(inputs.shape)
    inputs = (.5 * inputs.astype(np.float64) * (1 + erf)).astype(np.float32)
    bias = rng.normal(0, .1, 512).astype(np.float32)
    signs = rng.choice([-1, 1], 2048).astype(np.int8)
    rotation = dense_rotation(signs)
    rotated_weight = (weight.astype(np.float64) @ rotation).astype(np.float32)
    del rotation
    for group in (32, 16):
        for basis, basis_weight, basis_signs in (("original", weight, None), ("rotated", rotated_weight, signs)):
            try:
                packed_reference = _packing_evidence(basis_weight, group)
            except Exception as exc:
                controls.append({"name": f"packing_{basis}_g{group}", "status": "failed",
                                 "error_type": type(exc).__name__, "error": str(exc)})
                continue
            for rows in (1, 8):
                name = f"projection_{basis}_g{group}_rows{rows}"
                check(name, lambda group=group, name=name, rows=rows, weight=basis_weight, signs=basis_signs, cache=packed_reference:
                      projection_case(name, inputs[:rows], weight, bias, group, signs, cache))

    fixture = mlp_fixture()
    original_reference = mlp_reference(fixture, "original")
    baseline_output = None

    def mlp_case(name, placement, group):
        nonlocal baseline_output
        model = build_mlp_graph(fixture, placement, group)
        actual, profile = execute_graph(model, fixture["input"], output_dir, name)
        metrics = error_metrics(actual, mlp_reference(fixture, placement, group))
        if not metrics["passed"]:
            raise AssertionError(f"Residual MLP reference conformance failed: {metrics}")
        invariance = error_metrics(actual, original_reference)
        negative = placement in {"before_gelu", "wrong_inverse"}
        if group is None and invariance["passed"] == negative:
            raise AssertionError(f"Unexpected invariance result for {placement}: {invariance}")
        evidence = {"placement": placement, "group_size": group, "reference_errors": metrics,
                    "original_float_errors": invariance, "negative_control": negative, "runtime": profile}
        if placement == "original" and group is None:
            baseline_output = actual
        if placement == "post_gelu" and group is None:
            if baseline_output is None:
                raise AssertionError("The original runtime baseline did not pass.")
            observed = error_metrics(actual, baseline_output)
            if not observed["passed"]:
                raise AssertionError(f"Runtime-to-runtime invariance failed: {observed}")
            evidence["original_runtime_errors"] = observed
        return evidence

    for placement in ("original", "post_gelu", "before_gelu", "wrong_inverse"):
        name = f"residual_mlp_{placement}_float"
        check(name, lambda name=name, placement=placement: mlp_case(name, placement, None))
    for group in (32, 16):
        for placement in ("original", "post_gelu"):
            name = f"residual_mlp_{placement}_g{group}"
            check(name, lambda name=name, placement=placement, group=group: mlp_case(name, placement, group))

    artifacts = [{"path": path.relative_to(output_dir).as_posix(), "bytes": path.stat().st_size,
                  "sha256": sha256(path.read_bytes()).hexdigest()}
                 for path in sorted(output_dir.iterdir()) if path.is_file()]
    return {"schema_version": "hadamard-onnx-controls.v1",
            "status": "passed" if all(control["status"] == "passed" for control in controls) else "failed",
            "fixture_seed": FIXTURE_SEED,
            "runtime": {"onnx": onnx.__version__, "onnxruntime": ort.__version__, "numpy": np.__version__,
                        "requested_provider": "CPUExecutionProvider", "intra_op_threads": 1, "inter_op_threads": 1,
                        "graph_optimizations": "disabled", "input_dtype": "float32", "accuracy_level": 1},
            "tolerances": {"relative_frobenius": RELATIVE_TOLERANCE, "max_absolute": ABSOLUTE_TOLERANCE},
            "claims": ["Synthetic numerical and packed-format conformance only.",
                       "No pretrained-model quality, latency or memory improvement was measured.",
                       "CPU operator profiles do not identify the internal MLAS path; tiled dequantization or fallback may occur."],
            "controls": controls, "artifacts": artifacts}
