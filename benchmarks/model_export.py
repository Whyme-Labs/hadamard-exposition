"""Pinned Pythia export and the six prespecified ONNX interventions.

The converter traces the unmodified Transformers eager model once.  Every arm
then changes only the six MLP output projection sites in that same graph.  The
functions here never download inputs, select evaluation text, or run a campaign.
The caller owns acquisition provenance, resource limits, and full-model parity.

Graph IO is ``input_ids`` followed by twelve flat FP32 key/value cache tensors.
The outputs are ``logits`` followed by the twelve corresponding present tensors.
An empty cache is represented by shape [batch, 8, 0, 64], not by omitted inputs.
"""

from __future__ import annotations

from collections import Counter
from copy import deepcopy
from hashlib import sha256
import argparse
import gc
import json
import math
from pathlib import Path
from typing import Sequence

import numpy as np
import onnx
from onnx import TensorProto, helper, numpy_helper

try:
    from .contract import pack_codes, quantize_weights, unpack_codes
    from .onnx_controls import GraphBuilder, pack_weights
except ImportError:
    from contract import pack_codes, quantize_weights, unpack_codes
    from onnx_controls import GraphBuilder, pack_weights


MODEL_REVISION = "301b2c9bdf4d6da917d8f02d3c48aac481a60d06"
SITES = tuple(f"gpt_neox.layers.{index}.mlp.dense_4h_to_h" for index in range(6))
ARMS = {
    "fp32_original": (False, None),
    "fp32_rotated": (True, None),
    "w4a32_g32_original": (False, 32),
    "w4a32_g32_rotated": (True, 32),
    "w4a32_g16_original": (False, 16),
    "w4a32_g16_rotated": (True, 16),
}
INPUT_NAMES = ("input_ids",) + tuple(
    f"past_{kind}_{index}" for index in range(6) for kind in ("key", "value"))
OUTPUT_NAMES = ("logits",) + tuple(
    f"present_{kind}_{index}" for index in range(6) for kind in ("key", "value"))
PRODUCTION_CONFIG = {
    "hidden_size": 512, "intermediate_size": 2048, "num_hidden_layers": 6,
    "num_attention_heads": 8, "vocab_size": 50304, "max_position_embeddings": 2048,
    "hidden_act": "gelu", "use_parallel_residual": True, "rotary_pct": .25,
    "rotary_emb_base": 10000, "rope_scaling": None, "layer_norm_eps": 1e-5,
    "attention_bias": True, "attention_dropout": 0.0, "hidden_dropout": 0.0,
    "tie_word_embeddings": False, "use_cache": True,
}


def file_sha256(path: Path) -> str:
    digest = sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fixed_signs(layer_index: int, width: int = 2048) -> np.ndarray:
    if type(layer_index) is not int or not 0 <= layer_index < 6:
        raise ValueError("The model has exactly six fixed layer seeds.")
    if type(width) is not int or width < 1 or width & (width - 1):
        raise ValueError("Rotation width must be a positive power of two.")
    return np.random.Generator(np.random.PCG64(20261017 + layer_index)).choice(
        [-1, 1], size=width).astype(np.int8)


def rotated_weight(weight: np.ndarray, signs: np.ndarray) -> np.ndarray:
    """Compute W D H/sqrt(K) in float64, then round to FP32 exactly once.

The offline butterfly avoids a large dense Q. Independent tests compare it with
an explicitly constructed Sylvester matrix, including the sign orientation.
"""
    weight, signs = np.asarray(weight), np.asarray(signs)
    if weight.dtype != np.float32 or weight.ndim != 2 or not all(weight.shape):
        raise ValueError("Stored weights must be a nonempty FP32 [output,input] matrix.")
    k = weight.shape[1]
    if signs.shape != (k,) or k & (k - 1) or not np.isin(signs, (-1, 1)).all():
        raise ValueError("Signs must match a power-of-two input width.")
    if not np.isfinite(weight).all():
        raise ValueError("Stored weights must be finite.")
    result = weight.astype(np.float64) * signs.astype(np.float64)
    for stage in range(k.bit_length() - 1):
        half = 1 << stage
        blocks = result.reshape(weight.shape[0], -1, 2, half)
        left, right = blocks[:, :, 0].copy(), blocks[:, :, 1].copy()
        blocks[:, :, 0], blocks[:, :, 1] = left + right, left - right
    result *= 1 / math.sqrt(k)
    return result.astype(np.float32)


def model_inputs(tokens: np.ndarray, past: Sequence[np.ndarray] | None = None) -> dict:
    """Validate the full-model IO contract and make an empty cache when needed."""
    tokens = np.asarray(tokens)
    if tokens.ndim == 1:
        tokens = tokens[None, :]
    if tokens.ndim != 2 or not all(tokens.shape) or tokens.dtype.kind not in "iu":
        raise ValueError("Token IDs must be a nonempty integer [batch,sequence] array.")
    if np.any(tokens < 0) or np.any(tokens >= 50304):
        raise ValueError("A token ID is outside the pinned vocabulary.")
    tokens = np.ascontiguousarray(tokens, dtype=np.int64)
    batch, length = tokens.shape
    if past is None:
        past = tuple(np.empty((batch, 8, 0, 64), np.float32) for _ in range(12))
    if len(past) != 12:
        raise ValueError("Exactly one key and one value cache per layer is required.")
    arrays = tuple(np.asarray(value) for value in past)
    past_length = arrays[0].shape[2] if arrays[0].ndim == 4 else -1
    for value in arrays:
        if value.dtype != np.float32 or value.shape != (batch, 8, past_length, 64):
            raise ValueError("Cache tensors must share FP32 [batch,8,past,64] shape.")
        if not np.isfinite(value).all():
            raise ValueError("Cache tensors must be finite.")
    if past_length < 0 or past_length + length > 2048:
        raise ValueError("The request exceeds the pinned 2048-position context.")
    return dict(zip(INPUT_NAMES, (tokens, *arrays)))


def _converter_versions() -> dict:
    import torch
    import transformers

    observed = {"torch": torch.__version__, "transformers": transformers.__version__,
                "numpy": np.__version__, "onnx": onnx.__version__}
    expected = {"torch": "2.5.1+cpu", "transformers": "4.46.3",
                "numpy": "2.3.5", "onnx": "1.19.1"}
    if observed != expected:
        raise ValueError(f"Converter versions differ from the frozen contract: {observed}")
    return observed


def validate_reference_config(config) -> None:
    """Check all inference-affecting dimensions and defaults in the pinned config."""
    differences = {key: {"expected": value, "observed": getattr(config, key, None)}
                   for key, value in PRODUCTION_CONFIG.items() if getattr(config, key, None) != value}
    if differences:
        raise ValueError(f"The model configuration differs from pinned Pythia-70M: {differences}")


def _validate_reference_model(model, *, production: bool) -> None:
    import torch

    if production:
        validate_reference_config(model.config)
    if model.__class__.__name__ != "GPTNeoXForCausalLM" or model.config.num_hidden_layers != 6:
        raise ValueError("The adapter requires the pinned six-layer GPTNeoX architecture.")
    if model.training:
        raise ValueError("Export requires a model already placed in evaluation mode.")
    if model.gpt_neox._attn_implementation != "eager":
        raise ValueError("The reference must use GPTNeoX eager attention.")
    if any(layer.attention.__class__.__name__ != "GPTNeoXAttention"
           for layer in model.gpt_neox.layers):
        raise ValueError("An attention implementation other than pinned eager was selected.")
    if any(parameter.dtype != torch.float32 or parameter.device.type != "cpu"
           for parameter in model.parameters()):
        raise ValueError("Every model parameter must be CPU FP32.")
    for site in SITES:
        linear = model.get_submodule(site)
        if not isinstance(linear, torch.nn.Linear) or tuple(linear.weight.shape) != (
                model.config.hidden_size, model.config.intermediate_size):
            raise ValueError(f"Unexpected parameter orientation or projection at {site}.")


def load_reference(model_dir: Path):
    """Load only the already-acquired local safetensors model in pinned eager FP32."""
    _converter_versions()
    import torch
    from transformers import GPTNeoXForCausalLM

    torch.set_num_threads(1)
    if torch.get_num_interop_threads() != 1:
        torch.set_num_interop_threads(1)
    model_dir = Path(model_dir)
    if not (model_dir / "model.safetensors").is_file():
        raise FileNotFoundError("The acquired local safetensors file is required.")
    model = GPTNeoXForCausalLM.from_pretrained(
        str(model_dir), local_files_only=True, trust_remote_code=False,
        use_safetensors=True, torch_dtype=torch.float32,
        attn_implementation="eager", low_cpu_mem_usage=False)
    model.eval()
    model.requires_grad_(False)
    _validate_reference_model(model, production=True)
    return model


def reference_forward(model, tokens: np.ndarray,
                      past: Sequence[np.ndarray] | None = None) -> tuple[np.ndarray, tuple]:
    """Run the unmodified reference on caller-supplied development inputs."""
    import torch

    feed = model_inputs(tokens, past)
    tensors = [torch.from_numpy(feed[name]) for name in INPUT_NAMES]
    cache = tuple((tensors[1 + 2 * i], tensors[2 + 2 * i]) for i in range(6))
    with torch.inference_mode():
        output = model(input_ids=tensors[0], past_key_values=cache, use_cache=True,
                       output_attentions=False, output_hidden_states=False, return_dict=True)
    present = output.past_key_values
    if hasattr(present, "to_legacy_cache"):
        present = present.to_legacy_cache()
    arrays = tuple(value.detach().cpu().numpy() for pair in present for value in pair)
    return output.logits.detach().cpu().numpy(), arrays


def export_reference_graph(model, output_path: Path) -> onnx.ModelProto:
    """Trace a nonempty-cache path with all request dimensions kept dynamic.

    The pinned DynamicCache concatenation accepts a zero-length past axis. Trace
    a multi-token request so the causal-mask triangular operation stays present;
    the caller must still prove empty prefill and cached decode parity before test.
    """
    _validate_reference_model(model, production=True)
    return _trace_reference_graph(model, output_path)


def normalize_fp32_scalar_casts(graph: onnx.ModelProto) -> list[dict]:
    """Remove only FP64 scalar storage immediately cast exclusively to FP32.

    Torch 2.5.1 lowers the Python scalar alpha/beta arguments of baddbmm as
    DOUBLE Constant -> Cast(FLOAT), although the attention arithmetic is FP32.
    Store the exact FP32 cast result at those constants and retain every Cast.
    Actual FP64 consumers, exposed graph outputs, non-scalars and nonfinite
    values fail closed. This is applied once to the common original export,
    before generating any arm, and every change is recorded in its receipt.
    """
    consumers = {}
    for node in graph.graph.node:
        for name in node.input:
            consumers.setdefault(name, []).append(node)
    output_names = {value.name for value in graph.graph.output}
    changes = []
    for node in graph.graph.node:
        for attribute in node.attribute:
            if attribute.type != onnx.AttributeProto.TENSOR or attribute.t.data_type != TensorProto.DOUBLE:
                continue
            original = attribute.t
            array = numpy_helper.to_array(original)
            uses = consumers.get(node.output[0], []) if len(node.output) == 1 else []
            fp32_cast_only = bool(uses) and all(
                use.op_type == "Cast" and not use.domain and list(use.input) == list(node.output)
                and {item.name: helper.get_attribute_value(item) for item in use.attribute} == {"to": TensorProto.FLOAT}
                for use in uses)
            if (node.op_type != "Constant" or node.domain or attribute.name != "value" or array.shape != ()
                    or not np.isfinite(array).all() or not fp32_cast_only
                    or any(name in output_names for name in node.output)):
                raise ValueError(f"FP64 content is not an exclusively FP32-cast scalar: {node.name}")
            with np.errstate(over="ignore", under="ignore"):
                converted = array.astype(np.float32)
            if not np.isfinite(converted).all():
                raise ValueError(f"FP64 scalar has no finite FP32 cast result: {node.name}")
            serialized = original.SerializeToString()
            changes.append({"node": node.name, "original_dtype": "DOUBLE", "stored_dtype": "FLOAT",
                            "original_value": float(array), "stored_value": float(converted),
                            "original_tensor_proto_hex": serialized.hex(),
                            "original_tensor_sha256": sha256(serialized).hexdigest(),
                            "stored_float32_hex": converted.tobytes().hex(),
                            "unchanged_cast_consumers": [use.name for use in uses],
                            "reason": "Scalar storage normalization; all numerical consumers already used Cast(FLOAT)."})
            original.CopyFrom(numpy_helper.from_array(converted, original.name))
    return changes


def _trace_reference_graph(model, output_path: Path) -> onnx.ModelProto:
    """Shared tracer, also exercised by a small generated six-layer GPTNeoX test.

    Production callers enter through export_reference_graph and its complete
    pinned-model guard. This private primitive lets the generated test exercise
    exactly the same cache handling and exporter without allocating Pythia-70M.
    """
    _converter_versions()
    import torch

    _validate_reference_model(model, production=False)
    output_path = Path(output_path)
    if output_path.exists():
        raise FileExistsError("Existing graph artifacts must be preserved.")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    class FlatCacheModel(torch.nn.Module):
        def __init__(self, wrapped):
            super().__init__()
            self.model = wrapped

        def forward(self, input_ids, *flat_past):
            cache = tuple((flat_past[2 * i], flat_past[2 * i + 1]) for i in range(6))
            result = self.model(input_ids=input_ids, past_key_values=cache, use_cache=True,
                                output_attentions=False, output_hidden_states=False,
                                return_dict=False)
            return (result[0], *(value for pair in result[1] for value in pair))

    wrapper = FlatCacheModel(model).eval()
    dummy_tokens = torch.tensor([[1, 2, 3]], dtype=torch.int64)
    heads = model.config.num_attention_heads
    head_width = model.config.hidden_size // heads
    dummy_cache = tuple(torch.zeros((1, heads, 2, head_width), dtype=torch.float32) for _ in range(12))
    dynamic_axes = {"input_ids": {0: "batch", 1: "sequence"},
                    "logits": {0: "batch", 1: "sequence"}}
    dynamic_axes.update({name: {0: "batch", 2: "past_sequence"} for name in INPUT_NAMES[1:]})
    dynamic_axes.update({name: {0: "batch", 2: "total_sequence"} for name in OUTPUT_NAMES[1:]})
    with torch.inference_mode():
        torch.onnx.export(
            wrapper, (dummy_tokens, *dummy_cache), str(output_path), export_params=True,
            input_names=list(INPUT_NAMES), output_names=list(OUTPUT_NAMES),
            dynamic_axes=dynamic_axes, opset_version=18, do_constant_folding=False,
            keep_initializers_as_inputs=False, dynamo=False,
            training=torch.onnx.TrainingMode.EVAL)
    graph = onnx.load(output_path)
    graph.ir_version = 10
    normalization = normalize_fp32_scalar_casts(graph)
    if normalization:
        metadata = graph.metadata_props.add()
        metadata.key = "hadamard.fp32_scalar_normalizations.v1"
        metadata.value = json.dumps(normalization, sort_keys=True)
    onnx.checker.check_model(graph)
    onnx.save_model(graph, output_path)
    if [value.name for value in graph.graph.input] != list(INPUT_NAMES):
        raise ValueError("Export did not preserve all thirteen dynamic model inputs.")
    if [value.name for value in graph.graph.output] != list(OUTPUT_NAMES):
        raise ValueError("Export did not preserve logits and every cache output.")
    for value in (*graph.graph.input, *graph.graph.output):
        tensor = value.type.tensor_type
        expected_type = TensorProto.INT64 if value.name == "input_ids" else TensorProto.FLOAT
        if tensor.elem_type != expected_type:
            raise ValueError(f"Unexpected graph IO precision for {value.name}.")
        for axis, label in dynamic_axes[value.name].items():
            if tensor.shape.dim[axis].dim_param != label:
                raise ValueError(f"The exporter froze a dynamic dimension of {value.name}.")
    return graph


def _maps(graph: onnx.ModelProto) -> tuple[dict, dict, dict, dict]:
    nodes, initializers, producers, consumers = {}, {}, {}, {}
    for node in graph.graph.node:
        if not node.name or node.name in nodes:
            raise ValueError("Every graph node needs a unique nonempty name.")
        nodes[node.name] = node
        for name in node.output:
            if name in producers:
                raise ValueError("Graph outputs have multiple producers.")
            producers[name] = node
        for name in node.input:
            consumers.setdefault(name, []).append(node)
    for value in graph.graph.initializer:
        if value.name in initializers:
            raise ValueError("Graph initializers need unique names.")
        initializers[value.name] = value
    return nodes, initializers, producers, consumers


def locate_sites(graph: onnx.ModelProto, *, input_features: int = 2048,
                 output_features: int = 512) -> list[dict]:
    """Identify sites by named model weights and their exclusive transpose use."""
    _, initializers, producers, consumers = _maps(graph)
    result = []
    for index, site in enumerate(SITES):
        matches = [name for name in initializers
                   if name in (site + ".weight", "model." + site + ".weight")]
        if len(matches) != 1:
            raise ValueError(f"Expected one named parameter for {site}.")
        weight_name = matches[0]
        tensor = initializers[weight_name]
        if tensor.data_type != TensorProto.FLOAT or list(tensor.dims) != [output_features, input_features]:
            raise ValueError(f"The stored weight shape or precision differs at {site}.")
        uses = consumers.get(weight_name, [])
        if len(uses) != 1 or uses[0].op_type != "Transpose":
            raise ValueError(f"The named weight needs one exclusive transpose at {site}.")
        transpose = uses[0]
        attributes = {item.name: helper.get_attribute_value(item) for item in transpose.attribute}
        if attributes != {"perm": [1, 0]} or len(transpose.output) != 1:
            raise ValueError(f"Unexpected weight orientation at {site}.")
        products = consumers.get(transpose.output[0], [])
        if len(products) != 1 or products[0].op_type != "MatMul":
            raise ValueError(f"The transposed weight needs one exclusive MatMul at {site}.")
        product = products[0]
        if len(product.input) != 2 or product.input[1] != transpose.output[0]:
            raise ValueError(f"The selected weight is not the right MatMul operand at {site}.")
        activation = product.input[0]
        producer = producers.get(activation)
        scope = f"/gpt_neox/layers.{index}/mlp/act/"
        if producer is None or producer.op_type != "Mul" or scope not in producer.name:
            raise ValueError(f"The selected projection is not immediately after its GELU at {site}.")
        result.append({"site": site, "index": index, "weight": weight_name,
                       "transpose": transpose.name, "matmul": product.name,
                       "activation": activation, "product": product.output[0]})
    return result


def _rotation_graph(activation: str, index: int, width: int) -> tuple[GraphBuilder, str]:
    builder = GraphBuilder()
    prefix = f"hadamard_layer{index}"
    original_shape = builder.operation("Shape", [activation], prefix + "_original_shape")
    rotated = builder.hadamard(activation, fixed_signs(index, width), prefix)
    restored = builder.operation("Reshape", [rotated, original_shape], prefix + "_restored")
    return builder, restored


def _packed_evidence(weight: np.ndarray, group: int) -> tuple[np.ndarray, np.ndarray, dict]:
    packed, scales = pack_weights(weight, group)
    # A separately implemented contract quantizer and nibble decoder audit every
    # coefficient, not just a graph attribute or a nominal payload formula.
    codes, expected_scales = quantize_weights(weight, group)
    encoded = pack_codes(codes).reshape(packed.shape)
    decoded = unpack_codes(packed.reshape(weight.shape[0], -1), weight.shape[1])
    if not (np.array_equal(codes, decoded) and np.array_equal(encoded, packed)
            and np.array_equal(scales, expected_scales)):
        raise ValueError("The packed model weight disagrees with independent contract helpers.")
    return packed, scales, {
        "packed_shape": list(packed.shape), "scales_shape": list(scales.shape),
        "packed_code_bytes": packed.nbytes, "scale_bytes": scales.nbytes,
        "packed_sha256": sha256(packed.tobytes()).hexdigest(),
        "scales_sha256": sha256(scales.tobytes()).hexdigest(),
        "all_codes_and_scales_verified": True,
    }


def audit_graph_pair(base: onnx.ModelProto, changed: onnx.ModelProto, arm_id: str,
                     *, input_features: int = 2048, output_features: int = 512) -> dict:
    """Fail if any unrelated node, tensor, graph input or graph output changed."""
    rotated, group = ARMS[arm_id]
    base_opsets = {item.domain: item.version for item in base.opset_import}
    expected_opsets = {"": 18, **({"com.microsoft": 1} if group else {})}
    if base_opsets != {"": 18} or base.ir_version != 10:
        raise ValueError("The base graph must use exactly standard opset 18 and IR 10.")
    if {item.domain: item.version for item in changed.opset_import} != expected_opsets or changed.ir_version != 10:
        raise ValueError("The changed graph violates the frozen operator-domain versions.")
    sites = locate_sites(base, input_features=input_features, output_features=output_features)
    old_nodes, old_initializers, _, _ = _maps(base)
    new_nodes, new_initializers, _, _ = _maps(changed)
    removed_nodes = {site["transpose"] for site in sites} if group else set()
    altered_nodes = {site["matmul"] for site in sites} if rotated or group else set()
    altered_initializers = {site["weight"] for site in sites} if rotated or group else set()
    for name, value in old_nodes.items():
        if name in removed_nodes:
            if name in new_nodes:
                raise ValueError("A quantized projection retained its dense weight transpose.")
        elif name not in altered_nodes and (name not in new_nodes or value != new_nodes[name]):
            raise ValueError(f"Unrelated node changed: {name}")
    for name, value in old_initializers.items():
        if name not in altered_initializers and (name not in new_initializers or value != new_initializers[name]):
            raise ValueError(f"Unrelated initializer changed: {name}")
    if list(base.graph.input) != list(changed.graph.input) or list(base.graph.output) != list(changed.graph.output):
        raise ValueError("Graph IO changed between matched arms.")

    expected_added_nodes, expected_added_initializers = {}, {}
    evidence = []
    for site in sites:
        value = numpy_helper.to_array(old_initializers[site["weight"]])
        signs = fixed_signs(site["index"], input_features)
        activation = site["activation"]
        item = {"site": site["site"], "matmul_node": site["matmul"],
                "weight_shape": list(value.shape), "basis": "rotated" if rotated else "original",
                "bias_unchanged": True, "activation_dtype": "float32"}
        if rotated:
            builder, activation = _rotation_graph(activation, site["index"], input_features)
            expected_added_nodes.update({node.name: node for node in builder.nodes})
            expected_added_initializers.update({tensor.name: tensor for tensor in builder.initializers})
            value = rotated_weight(value, signs)
            item["signs_sha256"] = sha256(signs.tobytes()).hexdigest()
            item["butterfly_stages"] = input_features.bit_length() - 1
            item["shape_restored_before_projection"] = True
        expected_product = deepcopy(old_nodes[site["matmul"]])
        if group:
            if site["weight"] in new_initializers:
                raise ValueError("A quantized projection retained its dense FP32 weight.")
            packed, scales, packing = _packed_evidence(value, group)
            packed_name, scale_name = site["weight"] + ".packed", site["weight"] + ".scales"
            expected_added_initializers[packed_name] = numpy_helper.from_array(packed, packed_name)
            expected_added_initializers[scale_name] = numpy_helper.from_array(scales, scale_name)
            expected_product = helper.make_node(
                "MatMulNBits", [activation, packed_name, scale_name], [site["product"]],
                name=site["matmul"], domain="com.microsoft", K=input_features, N=output_features,
                bits=4, block_size=group, accuracy_level=1)
            item.update({"operator": "com.microsoft.MatMulNBits", "group_size": group,
                         "attributes": {"K": input_features, "N": output_features, "bits": 4,
                                        "block_size": group, "accuracy_level": 1}, **packing})
        else:
            expected_weight = numpy_helper.from_array(np.ascontiguousarray(value), site["weight"])
            if new_initializers.get(site["weight"]) != expected_weight:
                raise ValueError(f"The FP32 projection weight differs from its fixed basis at {site['site']}.")
            item.update({"operator": "MatMul", "group_size": None,
                         "weight_bytes": value.nbytes, "weight_sha256": sha256(value.tobytes()).hexdigest()})
            expected_product.input[0] = activation
        if new_nodes.get(site["matmul"]) != expected_product:
            raise ValueError(f"Unexpected projection operation at {site['site']}.")
        evidence.append(item)

    if set(new_nodes) != (set(old_nodes) - removed_nodes) | set(expected_added_nodes):
        raise ValueError("Unexpected nodes were added or removed outside the six sites.")
    expected_names = (set(old_initializers) - (altered_initializers if group else set())) | set(expected_added_initializers)
    if set(new_initializers) != expected_names:
        raise ValueError("Unexpected initializers were added or removed outside the six sites.")
    for name, value in expected_added_nodes.items():
        if new_nodes.get(name) != value:
            raise ValueError(f"Online butterfly operation differs: {name}")
    for name, value in expected_added_initializers.items():
        if new_initializers.get(name) != value:
            raise ValueError(f"Online constant or packed tensor differs: {name}")
    allowed_float = {TensorProto.FLOAT}
    floating_types = {TensorProto.FLOAT, TensorProto.DOUBLE, TensorProto.FLOAT16, TensorProto.BFLOAT16}
    for tensor in changed.graph.initializer:
        if tensor.data_type in floating_types - allowed_float:
            raise ValueError("A model initializer changed the FP32 precision contract.")
    for value in (*changed.graph.input, *changed.graph.output, *changed.graph.value_info):
        if value.type.tensor_type.elem_type in floating_types - allowed_float:
            raise ValueError("A graph tensor declaration violates the FP32 precision contract.")
    for node in changed.graph.node:
        for attribute in node.attribute:
            if attribute.type == onnx.AttributeProto.TENSOR and attribute.t.data_type in floating_types - allowed_float:
                raise ValueError("A tensor-valued node constant violates the FP32 contract.")
            if node.op_type == "Cast" and attribute.name == "to" and attribute.i in floating_types - allowed_float:
                raise ValueError("A graph cast violates the FP32 precision contract.")
    expected_count = 6 if group else 0
    observed_count = sum(node.op_type == "MatMulNBits" for node in changed.graph.node)
    if observed_count != expected_count:
        raise ValueError("The graph does not contain exactly the intended quantized sites.")
    return {"arm": arm_id, "sites": evidence,
            "unchanged_other_nodes": len(old_nodes) - len(removed_nodes | altered_nodes),
            "unchanged_other_initializers": len(old_initializers) - len(altered_initializers),
            "io_unchanged": True, "floating_initializers_and_constants": "float32",
            "matmul_nbits_nodes": observed_count,
            "packed_code_bytes": sum(item.get("packed_code_bytes", 0) for item in evidence),
            "scale_bytes": sum(item.get("scale_bytes", 0) for item in evidence),
            "rotation_sign_constant_bytes": 6 * input_features * 4 if rotated else 0,
            "online_add_nodes": 6 * (input_features.bit_length() - 1) if rotated else 0,
            "online_sub_nodes": 6 * (input_features.bit_length() - 1) if rotated else 0}


def rewrite_arm(base: onnx.ModelProto, arm_id: str, *, input_features: int = 2048,
                output_features: int = 512) -> tuple[onnx.ModelProto, dict]:
    """Build one matched arm; alternate dimensions exist only for generated tests."""
    if arm_id not in ARMS:
        raise ValueError("Unknown benchmark arm.")
    rotated, group = ARMS[arm_id]
    sites = locate_sites(base, input_features=input_features, output_features=output_features)
    changed = deepcopy(base)
    nodes, initializers, _, _ = _maps(changed)
    additions, remove_nodes, remove_initializers = {}, set(), set()
    for site in sites:
        product = nodes[site["matmul"]]
        value = numpy_helper.to_array(initializers[site["weight"]])
        activation = site["activation"]
        if rotated:
            builder, activation = _rotation_graph(activation, site["index"], input_features)
            additions[site["matmul"]] = builder.nodes
            changed.graph.initializer.extend(builder.initializers)
            value = rotated_weight(value, fixed_signs(site["index"], input_features))
        if group:
            packed, scales = pack_weights(value, group)
            packed_name, scale_name = site["weight"] + ".packed", site["weight"] + ".scales"
            changed.graph.initializer.extend([numpy_helper.from_array(packed, packed_name),
                                              numpy_helper.from_array(scales, scale_name)])
            remove_nodes.add(site["transpose"])
            remove_initializers.add(site["weight"])
            replacement = helper.make_node(
                "MatMulNBits", [activation, packed_name, scale_name], [site["product"]],
                name=site["matmul"], domain="com.microsoft", K=input_features, N=output_features,
                bits=4, block_size=group, accuracy_level=1)
            product.CopyFrom(replacement)
        else:
            initializers[site["weight"]].CopyFrom(
                numpy_helper.from_array(np.ascontiguousarray(value), site["weight"]))
            product.input[0] = activation
    ordered = []
    for node in changed.graph.node:
        if node.name in remove_nodes:
            continue
        ordered.extend(additions.get(node.name, []))
        ordered.append(node)
    del changed.graph.node[:]
    changed.graph.node.extend(ordered)
    kept = [tensor for tensor in changed.graph.initializer if tensor.name not in remove_initializers]
    del changed.graph.initializer[:]
    changed.graph.initializer.extend(kept)
    if group and not any(item.domain == "com.microsoft" for item in changed.opset_import):
        changed.opset_import.append(helper.make_opsetid("com.microsoft", 1))
    changed.ir_version = 10
    onnx.checker.check_model(changed)
    evidence = audit_graph_pair(base, changed, arm_id, input_features=input_features,
                                output_features=output_features)
    return changed, evidence


def _model_counts(model) -> dict:
    def count(named):
        values = list(named)
        return {"tensors": len(values), "elements": sum(value.numel() for _, value in values),
                "bytes": sum(value.numel() * value.element_size() for _, value in values)}
    return {"parameters": count(model.named_parameters()), "buffers": count(model.named_buffers()),
            "state_dict": count(model.state_dict().items()),
            "note": "Buffers include nonpersistent causal masks; state_dict counts serialized model tensors. "
                    "Parameter counts are independent of inference requires_grad=False."}


def export_all(model_dir: Path, output_dir: Path, *, reference_prefixes=None) -> dict:
    """Export all six graphs from already-acquired inputs; do no quality evaluation.

``reference_prefixes`` is deliberately unused: parity belongs to the caller's
bounded, development-only gate, with its own receipt and process accounting.
"""
    if reference_prefixes is not None:
        raise ValueError("Run reference_forward in the caller's explicit development parity phase.")
    output_dir = Path(output_dir)
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError("Export output must be absent or empty; preserve earlier attempts.")
    output_dir.mkdir(parents=True, exist_ok=True)
    versions = _converter_versions()
    model = load_reference(model_dir)
    counts = _model_counts(model)
    baseline_path = output_dir / "fp32_original.onnx"
    base = export_reference_graph(model, baseline_path)
    del model
    gc.collect()
    receipt = {"schema_version": "hadamard-model-export.v1", "model_revision": MODEL_REVISION,
               "converter_versions": versions, "counts": counts,
               "export_scalar_normalizations": next((json.loads(item.value) for item in base.metadata_props
                                                      if item.key == "hadamard.fp32_scalar_normalizations.v1"), []),
               "input_names": list(INPUT_NAMES), "output_names": list(OUTPUT_NAMES),
               "cache_layout": "FP32 [batch,8,past,64], flat key/value pairs in layer order",
               "dynamic_dimensions": ["batch", "sequence", "past_sequence", "total_sequence"],
               "tracing_fixture": {"batch": 1, "tokens": 3, "past_tokens": 2},
               "full_model_parity": "required separately before test evaluation",
               "serialization": "six standalone graphs; no external weights or dense rotation matrices",
               "signs": [{"layer": index, "seed": 20261017 + index,
                          "sha256": sha256(fixed_signs(index).tobytes()).hexdigest(),
                          "dtype": "int8", "values": fixed_signs(index).tolist()}
                         for index in range(6)], "arms": []}
    for arm_id in ARMS:
        if arm_id == "fp32_original":
            graph = base
            audit = audit_graph_pair(base, base, arm_id)
        else:
            graph, audit = rewrite_arm(base, arm_id)
        path = output_dir / f"{arm_id}.onnx"
        if arm_id != "fp32_original":
            if path.exists():
                raise FileExistsError("Refusing to overwrite an arm graph.")
            onnx.save_model(graph, path)
        audit.update({"path": path.name, "sha256": file_sha256(path), "bytes": path.stat().st_size,
                      "opset_imports": {item.domain: item.version for item in graph.opset_import},
                      "ir_version": graph.ir_version,
                      "node_types": dict(sorted(Counter(node.op_type for node in graph.graph.node).items())),
                      "initializers": [{"name": tensor.name, "dtype": TensorProto.DataType.Name(tensor.data_type),
                                        "shape": list(tensor.dims),
                                        "sha256": sha256(tensor.SerializeToString()).hexdigest()}
                                       for tensor in graph.graph.initializer]})
        receipt["arms"].append(audit)
        del graph
        gc.collect()
    receipt["total_graph_bytes"] = sum(arm["bytes"] for arm in receipt["arms"])
    (output_dir / "export.json").write_text(json.dumps(receipt, indent=2) + "\n")
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    receipt = export_all(args.model_dir, args.output)
    print(json.dumps({"receipt": str(args.output / "export.json"),
                      "arms": len(receipt["arms"]), "total_graph_bytes": receipt["total_graph_bytes"]}))


if __name__ == "__main__":
    main()
