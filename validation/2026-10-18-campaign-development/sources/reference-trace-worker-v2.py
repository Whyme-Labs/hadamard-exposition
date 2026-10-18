#!/usr/bin/env python3
"""Trace six unchanged development forwards using reconstructed local inputs.

Original receipts, cached arrays and final-position slices are restored evidence.
Model files are reacquired inputs. Full and prefill logits from the first run
are unavailable, so their recorded whole-array identities are the comparison.
This is a failure-localization diagnostic, not a campaign or a timing result.
The parent must use campaign_guard.run_bounded_task with the reviewed limits.
No model call is made when this file is imported.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import resource
import sys
import time
import traceback


sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

# Both imports are standard-library-only, including their transitive imports.
from benchmarks.campaign_guard import (
    THREADS, bind_files, directory_bytes, sha256_file, source_hashes,
    utc_now, validate_review, verify_bound_files, write_json,
)
from benchmarks.qualify import _publish_worker_identity


SOURCE_MAP_SHA256 = "1dd75e9af0736795e4d83c26f866d15d9f7a3fe55003e399ddbd36951ab2d69e"
MODEL_REVISION = "301b2c9bdf4d6da917d8f02d3c48aac481a60d06"
MODEL_SHA256 = "ebfa4e2f18696ebd83716a0d39fe2c025f2ff8483f72a83ca59c475692fc9d15"
OUTPUT_LIMIT = 64 * 1024 * 1024
ARRAY_LIMIT = 32 * 1024 * 1024
CASES = (("full", 513), ("prefill", 512), ("cached", 1))
ORIGINAL_RECEIPTS = {
    "campaign.json": "96136cf823ca00d82c28d080b0c7ff38726717cd2764cca20dacd914ff07b781",
    "review.json": "4acb4165f6594d95d0d9b8713d17cb0da81d556060703c528e3d8862a0053a8a",
    "artifacts/acquisition.json": "982613be2e25d233f9b06c6ab6d7063b58e94dacbbc9a76ca1047cfd4b4e7175",
    "selection/selection.json": "5506c8882fb3f5772d628bdf7f1b69d2a7175d217b49f9609bed32272c4c4c78",
    "selection/tokens.development.json": "cc11f24b75693260cd1bfb9716139056f7094a2f452063962e6d2af0e4a81eb5",
    "reference/reference.json": "7693dcacf075b7975880d3e77f4219c29401390488dc386f6a9e947c0b9e4aed",
}
RETAINED_SLICE_FILES = {
    "reference/slice-derivation.json": "7d8188d744de8e676b62ac3f4f17dd42ae82e0823f16d5ecc54e21ee662501b9",
    "reference/cache-comparison-slices.npz": "6972d7416056a53c840b1bf62ce139a34f27325a8ad611fc6f3aac6e4cef6a6f",
}
DEVELOPMENT_IDENTITIES = (
    (1, "37288f2bbde25e2405c4e0f40c1c54eaa8ac3d3106e170c8c6ea061d17abb891",
     "0a9f94df5f5de2b581d82281907b01af4aeac86f95055e3684aa42ee643185f4"),
    (47, "4b60812433749e0cdb1b886da6c319d3011fb9e2333f2a7d8158fb9acff02f0e",
     "4bb3be20531fe494946704c1ebdf36fbeffbc73be4861e91bfd76b87c66aa43d"),
)


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def helper_hashes():
    directory = Path(__file__).parent
    return {name: sha256_file(directory / name) for name in
            ("reference-trace-worker-v2.py", "reference-trace-invocation-v2.md")}


def verify_inputs(campaign, sources):
    """Verify restored evidence and explicitly reacquired local model inputs."""
    canonical = json.dumps(sources, sort_keys=True, separators=(",", ":")).encode()
    if len(sources) != 30 or hashlib.sha256(canonical).hexdigest() != SOURCE_MAP_SHA256:
        raise ValueError("The thirty frozen benchmark source identities changed")
    expected_evidence = {**ORIGINAL_RECEIPTS, **RETAINED_SLICE_FILES}
    bound = bind_files(campaign, [campaign / name for name in expected_evidence])
    if any(bound[name]["sha256"] != digest for name, digest in expected_evidence.items()):
        raise ValueError("Restored evidence differs from the retained second campaign attempt")
    original = read_json(campaign / "campaign.json")
    if (original["source_sha256_before"] != sources
            or original["source_sha256_after"] != sources
            or original["status"] != "blocked"
            or original["quality_test_accessed"] is not False):
        raise ValueError("The original failed campaign or source binding differs")
    validate_review(read_json(campaign / "review.json"), sources)
    acquisition = read_json(campaign / "artifacts/acquisition.json")
    selection = read_json(campaign / "selection/selection.json")
    reference = read_json(campaign / "reference/reference.json")
    prefixes = read_json(campaign / "selection/tokens.development.json")
    if (acquisition["status"] != "complete" or selection["status"] != "complete"
            or selection["acquisition_sha256"] != ORIGINAL_RECEIPTS["artifacts/acquisition.json"]
            or reference["status"] != "failed" or reference["model_revision"] != MODEL_REVISION
            or reference["error"]["message"] != "The reference's full and cached paths fail development parity"
            or prefixes["schema_version"] != "hadamard-model-token-prefixes.v1"
            or prefixes["role"] != "development" or len(prefixes["records"]) != 2
            or len(reference["records"]) != 2):
        raise ValueError("The original acquisition, selection or reference failure differs")
    selected_file = selection["local_token_files"]["development"]
    if (selected_file["path"] != "tokens.development.json"
            or selected_file["sha256"] != bound["selection/tokens.development.json"]["sha256"]
            or selected_file["bytes"] != bound["selection/tokens.development.json"]["bytes"]):
        raise ValueError("The selected development token file identity differs")
    model_files = [item for item in acquisition["files"] if item["kind"] == "model"]
    expected_names = {"config.json", "model.safetensors", "tokenizer.json",
                      "tokenizer_config.json", "special_tokens_map.json"}
    model_dir = campaign / "artifacts/model"
    if {path.name for path in model_dir.iterdir()} != expected_names:
        raise ValueError("The model directory contains an unexpected or missing file")
    model_bound = {"artifacts/" + item["path"]: {"bytes": item["bytes"], "sha256": item["sha256"]}
                   for item in model_files}
    if (set(model_bound) != {"artifacts/model/" + name for name in expected_names}
            or any(item["revision"] != MODEL_REVISION or item["status"] != "complete" for item in model_files)
            or model_bound["artifacts/model/model.safetensors"]["sha256"] != MODEL_SHA256):
        raise ValueError("The original pinned model identities differ")
    verify_bound_files(campaign, model_bound)
    for index, (row, text_hash, token_hash) in enumerate(DEVELOPMENT_IDENTITIES):
        record = prefixes["records"][index]
        public = {key: value for key, value in record.items() if key != "token_ids"}
        if (public != selection["roles"]["development"][index]
                or (record["start_row"], record["text_sha256"], record["token_sha256"])
                != (row, text_hash, token_hash)):
            raise ValueError("A development article or prefix differs from the original selection")
        for case, _ in CASES:
            saved = reference["records"][index]["cases"][case]["logits_file"]
            if saved["path"] != f"article{index}.{case}.npy":
                raise ValueError("An original logit path differs from the fixed six cases")
            if case == "cached":
                bound["reference/" + saved["path"]] = {"bytes": saved["bytes"], "sha256": saved["sha256"]}
            elif (campaign / "reference" / saved["path"]).exists() or (campaign / "reference" / saved["path"]).is_symlink():
                raise ValueError("A recreated full or prefill NPY cannot stand in for unavailable original evidence")
    verify_bound_files(campaign, bound)
    reconstruction_path = campaign / "reconstruction.json"
    reconstruction_bound = bind_files(campaign, [reconstruction_path])
    reconstruction = read_json(reconstruction_path)
    if (reconstruction.get("schema_version") != "hadamard-reference-diagnostic-inputs.v2"
            or reconstruction.get("status") != "complete"
            or reconstruction.get("original_campaign_directory") != "build/model-campaign-development-002"
            or reconstruction.get("original_campaign_sha256") != ORIGINAL_RECEIPTS["campaign.json"]
            or reconstruction.get("full_prefill_logits_available") is not False
            or type(reconstruction.get("model_calls")) is not int or reconstruction["model_calls"] != 0
            or reconstruction.get("quality_test_accessed") is not False
            or reconstruction.get("copied_original_evidence") != bound
            or reconstruction.get("reacquired_model_files") != model_bound):
        raise ValueError("Reconstruction provenance must distinguish copied evidence from reacquired model inputs")
    bound.update(model_bound)
    bound.update(reconstruction_bound)
    verify_bound_files(campaign, bound)
    return bound, prefixes["records"], reference, reconstruction


def load_retained_comparisons(campaign, reference, receipt):
    """Read original cached arrays and preserved slices without a model call."""
    import numpy as np
    from benchmarks.model_runtime import _array_identity, compare_logits

    derivation = read_json(campaign / "reference/slice-derivation.json")
    expected_keys = [f"article{index}_{case}" for index in range(2) for case in ("full", "cached")]
    if (derivation.get("schema_version") != "hadamard-development-logit-slices.v1"
            or derivation.get("model_calls") != 0
            or derivation.get("npz_sha256") != RETAINED_SLICE_FILES["reference/cache-comparison-slices.npz"]
            or derivation.get("npz_bytes") != (campaign / "reference/cache-comparison-slices.npz").stat().st_size
            or [item["key"] for item in derivation["arrays"]] != expected_keys):
        raise ValueError("The recorded original slice derivation differs")
    retained = {}
    with np.load(campaign / "reference/cache-comparison-slices.npz", allow_pickle=False) as archive:
        if len(archive.files) != 4 or set(archive.files) != set(expected_keys):
            raise ValueError("The retained NPZ must contain exactly the four original comparison arrays")
        for entry in derivation["arrays"]:
            key = entry["key"]
            article, case = key.split("_")
            index = int(article.removeprefix("article"))
            original_case = reference["records"][index]["cases"][case]
            saved = original_case["logits_file"]
            if ({name: entry["source"][name] for name in ("bytes", "sha256")} !=
                    {name: saved[name] for name in ("bytes", "sha256")}
                    or entry["source"]["path"] != "reference/" + saved["path"]
                    or entry["operation"] != ("array[:,512:513,:]" if case == "full" else "array[:]")
                    or entry["shape"] != [1, 1, 50304] or entry["dtype"] != "<f4"):
                raise ValueError("A retained slice is not bound to the corresponding original logit source")
            array = archive[key]
            expected = {"shape": entry["shape"], "dtype": "float32", "bytes": 201216,
                        "array_sha256": entry["array_c_order_sha256"]}
            if _array_identity(array) != expected:
                raise ValueError("The retained slice data differs from its original recorded identity")
            retained[key] = array.copy()
    receipt["retained_input_checks"] = []
    for index in range(2):
        original = reference["records"][index]["cases"]["cached"]
        mapped = np.load(campaign / "reference" / original["logits_file"]["path"],
                         mmap_mode="r", allow_pickle=False)
        try:
            if _array_identity(mapped) != original["logits"]:
                raise ValueError("An original cached NPY has a different array data identity")
            cached_copy = difference(retained[f"article{index}_cached"], mapped)
            if not cached_copy["array_equal"] or not cached_copy["data_identity_equal"]:
                raise ValueError("The retained cached slice differs from its original complete NPY")
        finally:
            mapped._mmap.close()
        control = compare_logits(retained[f"article{index}_cached"], retained[f"article{index}_full"])
        if control != original["full_vs_cached_path"]:
            raise ValueError("The preserved comparison arrays do not reproduce the recorded original control")
        receipt["retained_input_checks"].append(
            {"article_index": index, "cached_npz_vs_original_npy": cached_copy,
             "preserved_full_last_vs_cached_control": control})
    return retained


def compare_recorded_logits(logits, original_case):
    """Compare the full data identity without inventing unavailable error metrics."""
    from benchmarks.model_runtime import _array_identity

    identity = _array_identity(logits)
    return {"actual": identity, "expected": original_case["logits"],
            "data_identity_equal": identity == original_case["logits"],
            "comparison_basis": "Original recorded whole-array shape, dtype, byte count and SHA256",
            "direct_full_array_comparison_available": False,
            "array_equal": None, "differing_elements": None,
            "max_absolute_error": None, "relative_frobenius_error": None,
            "unavailable_reason": "The original full or prefill NPY was not retained and is unavailable",
            "original_npy_file_identity": original_case["logits_file"],
            "original_npy_file_identity_reverified": False}


def difference(actual, expected):
    """Summarize exact equality and numerical error using bounded FP64 chunks."""
    import numpy as np
    from benchmarks.model_runtime import _array_identity

    actual, expected = np.asarray(actual), np.asarray(expected)
    result = {"actual": _array_identity(actual), "expected": _array_identity(expected),
              "array_equal": bool(np.array_equal(actual, expected)),
              "data_identity_equal": False}
    result["data_identity_equal"] = result["actual"] == result["expected"]
    if actual.shape != expected.shape or actual.dtype != expected.dtype:
        result["comparable"] = False
        return result
    a, b = actual.reshape(-1), expected.reshape(-1)
    errors, norms, count, maximum, maximum_index = [], [], 0, 0.0, 0
    for offset in range(0, a.size, 65536):
        left = a[offset:offset + 65536].astype(np.float64)
        right = b[offset:offset + 65536].astype(np.float64)
        if not np.isfinite(left).all() or not np.isfinite(right).all():
            raise ValueError("A diagnostic tensor contains nonfinite values")
        delta = left - right
        absolute = np.abs(delta)
        index = int(np.argmax(absolute))
        if float(absolute[index]) > maximum:
            maximum, maximum_index = float(absolute[index]), offset + index
        count += int(np.count_nonzero(delta))
        errors.append(float(np.sum(delta * delta)))
        norms.append(float(np.sum(right * right)))
    numerator, denominator = math.sqrt(math.fsum(errors)), math.sqrt(math.fsum(norms))
    result.update({"comparable": True, "differing_elements": count,
                   "max_absolute_error": maximum,
                   "relative_frobenius_error": numerator / denominator if denominator else
                   (0.0 if numerator == 0 else None),
                   "max_error_index": [int(value) for value in np.unravel_index(maximum_index, actual.shape)],
                   "actual_at_max_error": float(a[maximum_index]),
                   "expected_at_max_error": float(b[maximum_index])})
    return result


class LastTokenTrace:
    """Copy last-token values without returning replacements from any hook."""

    def __init__(self, model):
        self.model = model
        self.handles = []
        self.total_array_bytes = 0
        self.arrays, self.events, self.attention_arguments = {}, [], {}
        self.module_kinds = {}
        self.tokenwise = {"gpt_neox.embed_in", "gpt_neox.final_layer_norm", "embed_out"}
        names = ["gpt_neox.embed_in", "gpt_neox.rotary_emb"]
        for layer in range(6):
            block = f"gpt_neox.layers.{layer}"
            leaves = ("input_layernorm", "attention.query_key_value", "attention.dense",
                      "post_attention_layernorm", "mlp.dense_h_to_4h", "mlp.act", "mlp.dense_4h_to_h")
            names.extend([block, block + ".attention", block + ".mlp",
                          *(block + "." + name for name in leaves)])
            self.tokenwise.update(block + "." + name for name in leaves)
        names.extend(["gpt_neox.final_layer_norm", "embed_out"])
        for name in names:
            module = model.get_submodule(name)
            self.module_kinds[name] = type(module).__name__
            self.handles.append(module.register_forward_pre_hook(self._pre(name), with_kwargs=True))
            self.handles.append(module.register_forward_hook(self._post(name), with_kwargs=True))

    def begin(self):
        self.arrays, self.events, self.attention_arguments = {}, [], {}

    def capture(self, label, tensor, *, layout="token"):
        import torch

        if label in self.arrays or not isinstance(tensor, torch.Tensor) or tensor.device.type != "cpu":
            raise ValueError("A hook tensor is missing, duplicated or outside the CPU reference")
        original_shape = list(tensor.shape)
        if layout == "token" and tensor.ndim == 3:
            selected = tensor[:, -1:, :]
        elif layout == "ids" and tensor.ndim == 2:
            selected = tensor[:, -1:]
        elif layout == "position" and tensor.ndim == 1:
            selected = tensor[-1:]
        elif layout == "mask" and tensor.ndim == 4:
            selected = tensor[:, :, -1:, :]
        else:
            raise ValueError(f"Unexpected hook tensor layout: {label}, {original_shape}")
        array = selected.detach().cpu().numpy().copy()
        self.total_array_bytes += array.nbytes
        if self.total_array_bytes > ARRAY_LIMIT:
            raise ValueError("Last-token diagnostic arrays exceeded the 32 MiB internal ceiling")
        self.arrays[label] = array
        self.events.append({"label": label, "original_shape": original_shape,
                            "retained_shape": list(array.shape), "dtype": str(array.dtype)})

    def _pre(self, name):
        def observe(module, args, kwargs):
            hidden = args[0] if args else kwargs["hidden_states"]
            self.capture(name + ":input", hidden,
                         layout="ids" if name == "gpt_neox.embed_in" else "token")
            if name.endswith(".attention"):
                metadata = {key: kwargs.get(key) for key in ("use_cache", "output_attentions")}
                metadata["layer_past_class"] = type(kwargs.get("layer_past")).__name__
                for key, layout in (("position_ids", "ids"), ("cache_position", "position"),
                                    ("attention_mask", "mask")):
                    value = kwargs.get(key)
                    metadata[key + "_is_none"] = value is None
                    if value is not None:
                        self.capture(name + ":" + key, value, layout=layout)
                for key in ("head_mask", "padding_mask"):
                    if kwargs.get(key) is not None:
                        raise ValueError("The unmodified reference unexpectedly supplied an auxiliary mask")
                    metadata[key + "_is_none"] = True
                positions = kwargs.get("position_embeddings")
                metadata["position_embeddings_is_none"] = positions is None
                if positions is not None:
                    for label, value in zip(("cos", "sin"), positions, strict=True):
                        self.capture(name + ":" + label, value)
                self.attention_arguments[name] = metadata
            elif name == "gpt_neox.rotary_emb":
                self.capture(name + ":position_ids", args[1], layout="ids")
            return None
        return observe

    def _post(self, name):
        def observe(module, args, kwargs, output):
            if name == "gpt_neox.rotary_emb":
                for label, value in zip(("cos", "sin"), output, strict=True):
                    self.capture(name + ":" + label, value)
            else:
                tensor = output[0] if isinstance(output, tuple) else output
                self.capture(name + ":output", tensor)
            return None
        return observe

    def save(self, output, index, case):
        import numpy as np

        path = output / f"article{index}.{case}.trace.npz"
        with path.open("xb") as stream:
            np.savez(stream, **self.arrays)
        return {"path": path.name, "bytes": path.stat().st_size, "sha256": sha256_file(path),
                "events": self.events, "attention_arguments": self.attention_arguments}

    def remove(self):
        for handle in self.handles:
            handle.remove()


def backend_observation(model):
    import numpy as np
    import onnx
    import onnxruntime
    import torch
    import transformers

    return {"python": sys.version, "executable": sys.executable,
            "versions": {"numpy": np.__version__, "onnx": onnx.__version__,
                         "onnxruntime": onnxruntime.__version__, "torch": torch.__version__,
                         "transformers": transformers.__version__},
            "torch_threads": torch.get_num_threads(), "torch_interop_threads": torch.get_num_interop_threads(),
            "float32_matmul_precision": torch.get_float32_matmul_precision(),
            "mkldnn_enabled": torch.backends.mkldnn.enabled,
            "deterministic_algorithms_enabled": torch.are_deterministic_algorithms_enabled(),
            "attention_implementation": model.gpt_neox._attn_implementation,
            "model_training": model.training,
            "torch_build_config": torch.__config__.show(),
            "torch_parallel_info": torch.__config__.parallel_info()}


def replay(campaign, output, records, reference, receipt):
    import numpy as np
    from benchmarks.model_export import load_reference, reference_forward
    from benchmarks.model_runtime import _array_identity, _checked_outputs, _development_records, compare_logits

    selected = _development_records(records)
    if [public for public, _ in selected] != [item["article"] for item in reference["records"]]:
        raise ValueError("Validated development article identities differ from the failed reference")
    retained = load_retained_comparisons(campaign, reference, receipt)
    model = load_reference(campaign / "artifacts/model")
    receipt["backend_before"] = backend_observation(model)
    if receipt["backend_before"]["torch_threads"] != 1 or receipt["backend_before"]["torch_interop_threads"] != 1:
        raise ValueError("The reference must retain one intra-op and one inter-op CPU thread")
    collector = LastTokenTrace(model)
    receipt["hooked_modules"] = collector.module_kinds
    receipt["tokenwise_modules"] = sorted(collector.tokenwise)
    try:
        for index, (public, tokens) in enumerate(selected):
            observation = {"article": public, "cases": {}}
            receipt["records"].append(observation)
            full_prefix_cache, prefill_snapshot, feed_cache, full_last = None, None, None, None
            traces = {}
            for case, length in CASES:
                collector.begin()
                case_result = {"completed": False}
                observation["cases"][case] = case_result
                inputs = tokens if case == "full" else (tokens[:, :512] if case == "prefill" else tokens[:, 512:513])
                receipt["forward_calls_attempted"] += 1
                receipt["model_calls"] += 1
                start = time.monotonic()
                try:
                    logits, present = reference_forward(model, inputs, feed_cache if case == "cached" else None)
                    receipt["forward_calls_completed"] += 1
                    logits, present = _checked_outputs((logits, *present), 1, length, 512 if case == "prefill" else 513)
                finally:
                    case_result["forward_with_hooks_seconds"] = time.monotonic() - start
                    case_result["trace"] = collector.save(output, index, case)
                    traces[case] = collector.arrays
                original_case = reference["records"][index]["cases"][case]
                if case == "cached":
                    mapped = np.load(campaign / "reference" / original_case["logits_file"]["path"],
                                     mmap_mode="r", allow_pickle=False)
                    try:
                        comparison = difference(logits, mapped)
                    finally:
                        mapped._mmap.close()
                    comparison.update({"comparison_basis": "Direct comparison with the complete restored original cached NPY",
                                       "direct_full_array_comparison_available": True,
                                       "unavailable_reason": None,
                                       "original_npy_file_identity": original_case["logits_file"],
                                       "original_npy_file_identity_reverified": True})
                    case_result["original_logits_comparison"] = comparison
                    case_result["retained_cached_copy_comparison"] = difference(logits, retained[f"article{index}_cached"])
                else:
                    case_result["original_logits_comparison"] = compare_recorded_logits(logits, original_case)
                    if case == "full":
                        case_result["retained_last_position_comparison"] = difference(logits[:, 512:513, :],
                                                                                      retained[f"article{index}_full"])
                case_result["cache_identities"] = [_array_identity(value) for value in present]
                case_result["original_cache_identities_equal"] = case_result["cache_identities"] == original_case["cache"]
                if case == "full":
                    full_last = logits[:, -1:].copy()
                    full_prefix_cache = tuple(value[:, :, :512, :].copy() for value in present)
                elif case == "prefill":
                    prefill_snapshot = tuple(value.copy() for value in present)
                    feed_cache = present
                    case_result["full_prefix_vs_prefill_cache"] = [
                        {"layer": number // 2, "kind": "key" if number % 2 == 0 else "value",
                         "comparison": difference(value, full_prefix_cache[number])}
                        for number, value in enumerate(present)]
                else:
                    case_result["cached_prefix_vs_prefill_cache"] = [
                        {"layer": number // 2, "kind": "key" if number % 2 == 0 else "value",
                         "comparison": difference(value[:, :, :512, :], prefill_snapshot[number]),
                         "prefill_input_unchanged": bool(np.array_equal(feed_cache[number], prefill_snapshot[number]))}
                        for number, value in enumerate(present)]
                    case_result["frozen_full_vs_cached_logits"] = compare_logits(logits, full_last)
                case_result["completed"] = True
                del logits, present
            if list(traces["full"]) != list(traces["cached"]):
                raise ValueError("Full and cached hooks did not visit the same ordered events")
            comparisons = [{"label": label, **difference(traces["cached"][label], traces["full"][label])}
                           for label in traces["full"]]
            observation["full_last_vs_cached_events"] = comparisons
            observation["first_differing_event"] = next(
                (item for item in comparisons if not item["array_equal"]), None)
            by_label = {item["label"]: item for item in comparisons}
            observation["first_tokenwise_equal_input_different_output"] = next(
                (item for item in comparisons if item["label"].endswith(":output")
                 and item["label"][:-7] in collector.tokenwise and not item["array_equal"]
                 and by_label[item["label"][:-7] + ":input"]["data_identity_equal"]), None)
        receipt["backend_after"] = backend_observation(model)
        receipt["backend_unchanged"] = receipt["backend_before"] == receipt["backend_after"]
        receipt["total_retained_array_bytes"] = int(collector.total_array_bytes)
    finally:
        collector.remove()
    cases = [item for article in receipt["records"] for item in article["cases"].values()]
    receipt["all_recorded_logit_data_identities_match"] = all(
        item["original_logits_comparison"]["data_identity_equal"] for item in cases)
    direct_comparisons = [
        comparison for article in receipt["records"] for comparison in (
            article["cases"]["full"]["retained_last_position_comparison"],
            article["cases"]["cached"]["original_logits_comparison"],
            article["cases"]["cached"]["retained_cached_copy_comparison"])]
    receipt["all_available_original_arrays_equal"] = all(
        item["array_equal"] and item["data_identity_equal"] for item in direct_comparisons)
    receipt["all_original_cache_identities_equal"] = all(item["original_cache_identities_equal"] for item in cases)
    receipt["original_reference_failure_reproduced"] = (
        len(cases) == 6 and receipt["all_recorded_logit_data_identities_match"]
        and receipt["all_available_original_arrays_equal"] and receipt["all_original_cache_identities_equal"]
        and all(article["cases"]["cached"]["frozen_full_vs_cached_logits"]["passed"] is False
                for article in receipt["records"]))
    receipt["collection_completed"] = True
    if not receipt["original_reference_failure_reproduced"] or not receipt["backend_unchanged"]:
        raise ValueError("Recorded output identities or retained arrays do not reproduce the original reference failure")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--diagnostic-inputs", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    campaign, output = arguments.diagnostic_inputs.absolute(), arguments.output.absolute()
    if (campaign.resolve() != campaign or output.resolve() != output
            or not campaign.is_relative_to(ROOT / "build") or not output.is_relative_to(ROOT / "build")
            or output.is_relative_to(campaign) or campaign.is_relative_to(output)
            or campaign.is_relative_to(ROOT / "build/model-campaign-development-002")):
        raise ValueError("Use a separate reconstructed input directory and fresh output under build, outside the old campaign")
    if not output.is_dir() or any(path.name not in {"stdout.log", "stderr.log"} for path in output.iterdir()):
        raise ValueError("The parent must supply a fresh task directory containing only its logs")
    started = time.monotonic()
    identity = _publish_worker_identity(output)
    receipt = {"schema_version": "hadamard-reference-trace.v2", "status": "failed",
               "worker_identity": identity, "started_utc": utc_now(),
               "diagnostic_inputs": str(campaign), "campaign_ready": False,
               "original_campaign_directory": "build/model-campaign-development-002",
               "full_prefill_original_arrays_available": False,
               "reproduction_basis": {
                   "all_six_logits": "Match the recorded original whole-array shape, dtype, byte count and canonical SHA256",
                   "cached_logits": "Also compare every value with the restored original cached NPY and its retained NPZ copy",
                   "full_last_logits": "Also compare every value at position 512 with the originally retained full-last slice",
                   "cache_tensors": "Match all original recorded cache array identities",
                   "unavailable_metrics": "Original full/prefill NPYs are unavailable; direct equality and numerical error against those complete arrays remain null",
               },
               "quality_test_accessed": False, "timing_tokens_accessed": False,
               "acquisition_invoked": False, "quantized_model_calls": 0,
               "model_calls": 0, "forward_calls_attempted": 0, "forward_calls_completed": 0,
               "collection_completed": False, "original_reference_failure_reproduced": False,
               "scope": "Six unchanged development forwards from reacquired model files and copied original evidence",
               "timing_scope": "Diagnostic elapsed time includes hooks and is not inference timing evidence",
               "records": [], "errors": []}
    bound = {}
    try:
        receipt["helper_sha256_before"] = sha256_file(Path(__file__))
        receipt["diagnostic_helper_sha256_before"] = helper_hashes()
        receipt["source_sha256_before"] = source_hashes()
        expected_environment = {**THREADS, "CUDA_VISIBLE_DEVICES": "", "HF_HUB_OFFLINE": "1",
                                "HF_HUB_DISABLE_TELEMETRY": "1", "TRANSFORMERS_OFFLINE": "1"}
        receipt["thread_and_offline_environment"] = {key: os.environ.get(key) for key in expected_environment}
        if receipt["thread_and_offline_environment"] != expected_environment:
            raise ValueError("The parent must retain the frozen single-thread, CPU and offline environment")
        bound, records, reference, reconstruction = verify_inputs(campaign, receipt["source_sha256_before"])
        receipt["reconstruction"] = reconstruction
        receipt["used_input_files"] = bound
        write_json(output / "start.json", receipt)
        # First numerical imports occur inside replay, after publication and all file bindings.
        replay(campaign, output, records, reference, receipt)
        if receipt["forward_calls_attempted"] != 6 or receipt["forward_calls_completed"] != 6:
            raise ValueError("The diagnostic must perform exactly the six prescribed forwards")
        receipt["status"] = "passed"
    except Exception as error:
        receipt["errors"].append({"stage": "diagnostic", "type": type(error).__name__, "message": str(error)})
        traceback.print_exc()
    finally:
        for name, operation in (
            ("source_sha256_after", source_hashes),
            ("helper_sha256_after", lambda: sha256_file(Path(__file__))),
            ("diagnostic_helper_sha256_after", helper_hashes),
            ("used_inputs_unchanged", lambda: verify_bound_files(campaign, bound) is None if bound else False),
            ("output_bytes_before_final_receipt", lambda: directory_bytes(output)),
        ):
            try:
                receipt[name] = operation()
            except Exception as error:
                receipt[name] = None
                receipt["errors"].append({"stage": name, "type": type(error).__name__, "message": str(error)})
        receipt["inputs_unchanged"] = (receipt.get("used_inputs_unchanged") is True
                                        and receipt.get("source_sha256_before") == receipt.get("source_sha256_after")
                                        and receipt.get("helper_sha256_before") == receipt.get("helper_sha256_after")
                                        and receipt.get("diagnostic_helper_sha256_before") == receipt.get("diagnostic_helper_sha256_after"))
        if not receipt["inputs_unchanged"]:
            receipt["errors"].append({"stage": "final_identity", "type": "ValueError", "message": "A required identity was changed or could not be verified"})
        if receipt.get("output_bytes_before_final_receipt") is None or receipt["output_bytes_before_final_receipt"] > OUTPUT_LIMIT - 8 * 1024 * 1024:
            receipt["errors"].append({"stage": "output_budget", "type": "ValueError", "message": "Insufficient space inside the 64 MiB diagnostic output budget"})
        if receipt["errors"]:
            receipt["status"] = "failed"
            receipt["original_reference_failure_reproduced"] = False
        receipt["finished_utc"] = utc_now()
        receipt["elapsed_seconds"] = time.monotonic() - started
        receipt["peak_worker_rss_bytes"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
        write_json(output / "worker-result.json", receipt)
    return 0 if receipt["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())

