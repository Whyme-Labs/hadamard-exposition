"""Numerical and data contracts for the bounded W4A32 benchmark design."""

from __future__ import annotations

import hashlib
import math
from numbers import Integral, Real
import re
from typing import Mapping, Sequence

import numpy as np


class ContractError(ValueError):
    """An input or receipt does not satisfy the frozen benchmark contract."""


def _positive_int(value, name: str) -> int:
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, Integral) or value < 1:
        raise ContractError(f"{name} must be a positive integer")
    return int(value)


def quantize_weights(weights: np.ndarray, group_size: int) -> tuple[np.ndarray, np.ndarray]:
    """Return signed codes and FP32 scales for rows [output, input]."""
    a = np.asarray(weights)
    if a.dtype != np.float32 or a.ndim != 2 or not all(a.shape):
        raise ContractError("weights must be a nonempty FP32 [output, input] matrix")
    group_size = _positive_int(group_size, "group_size")
    if group_size not in (16, 32) or a.shape[1] % group_size:
        raise ContractError("group size must be 16 or 32 and divide the input width")
    if not np.isfinite(a).all():
        raise ContractError("weights must be finite")
    groups = a.reshape(a.shape[0], -1, group_size)
    maxima = np.max(np.abs(groups), axis=-1)
    with np.errstate(under="ignore"):
        scales = maxima / np.float32(7)
    scales = np.where(maxima == 0, np.float32(1), scales).astype(np.float32)
    if not np.isfinite(scales).all() or np.any(scales <= 0):
        raise ContractError("a nonzero group has no finite positive FP32 maxabs/7 scale")
    codes = np.clip(np.rint(groups / scales[..., None]), -7, 7).astype(np.int8)
    return codes.reshape(a.shape), scales


def pack_codes(codes: np.ndarray) -> np.ndarray:
    """Encode q+8, with the earlier input coordinate in the low nibble."""
    q = np.asarray(codes)
    if q.ndim != 2 or not all(q.shape) or q.shape[1] % 2 or q.dtype.kind not in "iu":
        raise ContractError("codes must be a nonempty integer matrix with even input width")
    if np.any(q < -7) or np.any(q > 7):
        raise ContractError("only signed codes -7 through +7 are allowed")
    encoded = (q.astype(np.int16) + 8).astype(np.uint8)
    return encoded[:, 0::2] | (encoded[:, 1::2] << np.uint8(4))


def unpack_codes(packed: np.ndarray, last_dimension: int) -> np.ndarray:
    """Decode the exact no-padding representation used by this design."""
    a = np.asarray(packed)
    width = _positive_int(last_dimension, "last_dimension")
    if a.dtype != np.uint8 or a.ndim != 2 or not all(a.shape) or width != 2 * a.shape[1]:
        raise ContractError("packed bytes and the declared input width disagree")
    encoded = np.empty((a.shape[0], width), dtype=np.uint8)
    encoded[:, 0::2] = a & np.uint8(15)
    encoded[:, 1::2] = a >> np.uint8(4)
    if np.any(encoded == 0):
        raise ContractError("nibble zero represents reserved code -8")
    return (encoded.astype(np.int16) - 8).astype(np.int8)


def payload_counts(input_width: int, output_width: int, group_size: int, layers: int) -> dict:
    """Count nominal code, scale and bias payload only, not file or process memory."""
    k, n, count = [_positive_int(v, name) for v, name in (
        (input_width, "input_width"), (output_width, "output_width"), (layers, "layers"))]
    group_size = _positive_int(group_size, "group_size")
    if group_size not in (16, 32) or k % group_size:
        raise ContractError("group size must be 16 or 32 and divide input_width")
    weights = k * n * count
    scales = weights // group_size
    return {"weight_count": weights, "scale_count": scales,
            "packed_code_bytes": weights // 2, "scale_bytes": scales * 4,
            "bias_bytes": n * count * 4}


_ARTICLE_HEADING = re.compile(r"^= [^=].* =$")


def parse_articles(rows: Sequence[str], split: str) -> list[dict]:
    """Parse first-level WikiText headings, preserving row order and text."""
    if split not in {"train", "validation", "test"}:
        raise ContractError("split must be train, validation or test")
    articles: list[dict] = []
    title = None
    start_row = None
    content: list[str] = []

    def finish() -> None:
        if title is not None:
            text = "\n".join(content)
            articles.append({"article_id": f"{split}:{start_row}", "split": split,
                             "start_row": start_row, "title": title,
                             "text": text, "text_sha256": hashlib.sha256(text.encode()).hexdigest()})

    for row_index, row in enumerate(rows):
        if not isinstance(row, str):
            raise ContractError("WikiText rows must be strings")
        heading = _ARTICLE_HEADING.fullmatch(row.strip())
        if heading:
            finish()
            title, content, start_row = row.strip()[2:-2].strip(), [row], row_index
            if not title:
                raise ContractError("an article heading must have a title")
        elif title is not None:
            content.append(row)
    finish()
    return articles


def _token_ids(values: Sequence[int]) -> list[int]:
    try:
        tokens = list(values)
    except TypeError as error:
        raise ContractError("token IDs must be a sequence") from error
    if any(isinstance(v, (bool, np.bool_)) or not isinstance(v, Integral) or v < 0 for v in tokens):
        raise ContractError("token IDs must be nonnegative integers, not booleans")
    return [int(v) for v in tokens]


def select_article_prefixes(articles: Sequence[dict], tokenized: Mapping[str, Sequence[int]],
                            count: int = 32, length: int = 513) -> list[dict]:
    """Select first eligible articles from supplied tokenizer output, with no fitting."""
    count, length = _positive_int(count, "count"), _positive_int(length, "length")
    selected = []
    seen = set()
    for article in articles:
        identity = article.get("article_id")
        if not isinstance(identity, str) or not identity or identity in seen:
            raise ContractError("articles need unique nonempty IDs")
        seen.add(identity)
        if identity not in tokenized:
            raise ContractError(f"missing tokenizer output for {identity}")
        tokens = _token_ids(tokenized[identity])
        if tokens and max(tokens) > np.iinfo(np.uint32).max:
            raise ContractError("token IDs must fit the declared little-endian uint32 identity")
        if len(tokens) >= length:
            prefix = tokens[:length]
            selected.append({"article_id": identity, "split": article["split"],
                             "start_row": article["start_row"],
                             "text_sha256": article["text_sha256"], "token_ids": prefix,
                             "token_sha256": hashlib.sha256(np.asarray(prefix, dtype="<u4").tobytes()).hexdigest()})
            if len(selected) == count:
                return selected
    raise ContractError(f"need {count} articles with at least {length} token IDs; found {len(selected)}")


def assert_disjoint_roles(roles: Mapping[str, Sequence[dict]]) -> None:
    """Reject repeated selected article identities or exact text, not pretraining overlap."""
    if not roles:
        raise ContractError("at least one nonempty data role is required")
    identities, texts = {}, {}
    for role, records in roles.items():
        if not isinstance(role, str) or not role or not records:
            raise ContractError("data roles must have a name and selected records")
        for record in records:
            identity, digest = record.get("article_id"), record.get("text_sha256")
            if not isinstance(identity, str) or not identity or not isinstance(digest, str) or not re.fullmatch(r"[a-f0-9]{64}", digest):
                raise ContractError("selected records need an article ID and a SHA256 text identity")
            if identity in identities or digest in texts:
                raise ContractError(f"repeated article identity or exact text in role {role}")
            identities[identity], texts[digest] = role, role


def aggregate_nll(records: Sequence[dict]) -> dict:
    """Aggregate loss totals with their target counts, never means of article means."""
    if not records:
        raise ContractError("at least one NLL record is required")
    totals, target_count = [], 0
    for record in records:
        loss, count = record.get("nll_sum"), record.get("target_count")
        if isinstance(loss, bool) or not isinstance(loss, Real) or not math.isfinite(loss) or loss < 0:
            raise ContractError("NLL sums must be finite and nonnegative")
        target_count += _positive_int(count, "target_count")
        totals.append(float(loss))
    try:
        loss = math.fsum(totals)
    except OverflowError as error:
        raise ContractError("aggregate NLL must be finite") from error
    if not math.isfinite(loss):
        raise ContractError("aggregate NLL must be finite")
    return {"nll_sum": loss, "target_count": target_count, "mean_nll": loss / target_count}


def shifted_nll(logits: np.ndarray, token_ids: Sequence[int],
                attention_mask: Sequence[int] | None = None) -> dict:
    """Score next-token targets once, excluding masked targets and masked predictors."""
    scores = np.asarray(logits, dtype=np.float64)
    ids = _token_ids(token_ids)
    if scores.ndim != 2 or scores.shape[0] != len(ids) or len(ids) < 2 or not scores.shape[1]:
        raise ContractError("logits must be [sequence, vocabulary] with at least two token IDs")
    if not np.isfinite(scores).all() or max(ids) >= scores.shape[1]:
        raise ContractError("logits must be finite and token IDs must fit the vocabulary")
    mask = np.ones(len(ids), dtype=np.bool_)
    if attention_mask is not None:
        raw_mask = np.asarray(attention_mask)
        if raw_mask.shape != (len(ids),) or not np.isin(raw_mask, [0, 1]).all():
            raise ContractError("attention mask must contain one zero or one per input token")
        mask = raw_mask.astype(np.bool_)
    valid = mask[:-1] & mask[1:]
    count = int(valid.sum())
    if not count:
        raise ContractError("at least one valid shifted target is required")
    rows, targets = scores[:-1][valid], np.asarray(ids[1:])[valid]
    with np.errstate(over="ignore", invalid="ignore"):
        normalized = rows - np.max(rows, axis=1, keepdims=True)
        losses = np.log(np.sum(np.exp(normalized), axis=1)) - normalized[np.arange(count), targets]
    return aggregate_nll([{"nll_sum": float(np.sum(losses)), "target_count": count}])


def _expect(actual, expected, name: str) -> None:
    if type(actual) is not type(expected) or actual != expected:
        raise ContractError(f"{name} must equal {expected!r}")


def _fields(actual: dict, expected: dict, name: str) -> None:
    if not isinstance(actual, dict):
        raise ContractError(f"{name} must be an object")
    for key, value in expected.items():
        if isinstance(value, dict):
            _fields(actual.get(key), value, f"{name}.{key}")
        else:
            _expect(actual.get(key), value, f"{name}.{key}")


def validate_manifest(manifest: dict) -> dict:
    """Check the concrete six-arm design, without claiming campaign readiness."""
    try:
        _expect(manifest["schema_version"], "hadamard-model-benchmark.v1", "schema_version")
        _expect(manifest["campaign_id"], "pythia70m-mlp-w4a32-v1", "campaign_id")
        model, data, runtime = manifest["model"], manifest["dataset"], manifest["runtime"]
        for name, value in (("model", model["revision"]), ("tokenizer", model["tokenizer"]["revision"]),
                            ("dataset", data["revision"]), ("runtime", runtime["onnxruntime_revision"]),
                            ("transformers", runtime["conversion"]["transformers_revision"]),
                            ("torch", runtime["conversion"]["torch_revision"])):
            if not isinstance(value, str) or not re.fullmatch(r"[a-f0-9]{40}", value):
                raise ContractError(f"{name} needs an immutable 40-character revision")
        _fields(model, {"repo": "EleutherAI/pythia-70m", "revision": "301b2c9bdf4d6da917d8f02d3c48aac481a60d06",
                       "architecture": "GPTNeoXForCausalLM",
                       "hidden_size": 512, "intermediate_size": 2048, "num_hidden_layers": 6,
                       "num_attention_heads": 8, "vocab_size": 50304,
                       "max_position_embeddings": 2048, "weight_orientation": "output_by_input",
                       "trust_remote_code": False, "use_safetensors": True, "load_dtype": "float32",
                       "files": ["config.json", "model.safetensors", "tokenizer.json", "tokenizer_config.json", "special_tokens_map.json"],
                       "tokenizer": {"repo": model["repo"], "revision": model["revision"],
                                     "add_special_tokens": False, "truncation": False}}, "model")
        _expect(model["sites"], [f"gpt_neox.layers.{i}.mlp.dense_4h_to_h" for i in range(6)], "model.sites")
        _fields(data, {"repo": "Salesforce/wikitext", "revision": "b08601e04326c79dfdd32d625aee71d232d685c3",
                      "config": "wikitext-2-raw-v1",
                      "files": {split: f"wikitext-2-raw-v1/{split}-00000-of-00001.parquet" for split in ("train", "validation", "test")},
                      "selection": {"title_regex": _ARTICLE_HEADING.pattern, "include_title": True,
                                    "row_join": "\n", "order": "source_row_order",
                                    "rule": "first_articles_with_enough_tokens", "token_prefix_only": True,
                                    "insufficient_articles": "fail", "identity": "revision/config/split/start_row",
                                    "content_identity": "sha256_of_full_joined_utf8_article",
                                    "token_identity": "sha256_of_little_endian_uint32_token_prefix"},
                      "calibration": {"method": "none", "fitted_examples": 0,
                                      "rotation_search": False, "clipping_search": False},
                      "role_overlap_policy": "reject_shared_ids_or_content_hashes",
                      "training_decontamination_claim": False}, "dataset")
        role_values = {"development": ("validation", 2, 513), "timing": ("train", 4, 640),
                       "quality": ("test", 32, 513)}
        _expect(set(data["roles"]), set(role_values), "dataset.roles")
        for role, (split, articles, tokens) in role_values.items():
            _fields(data["roles"][role], {"split": split, "articles": articles,
                                         "tokens_per_article": tokens}, f"dataset.roles.{role}")
        _fields(runtime, {"python_version": "3.12.14", "numpy_version": "2.3.5",
                          "onnx_version": "1.19.1", "onnxruntime_version": "1.23.2",
                          "onnxruntime_revision": "a83fc4d58cb48eb68890dd689f94f28288cf2278",
                          "provider": "CPUExecutionProvider", "operator": "com.microsoft.MatMulNBits",
                          "accuracy_level": 1, "threads": 1, "inter_op_threads": 1,
                          "graph_optimizations": "disabled", "execution_mode": "sequential",
                          "activation_dtype": "float32", "scale_dtype": "float32", "bias_dtype": "float32",
                          "cache_dtype": "float32", "accumulation_dtype": "float32", "onnx_opset": 18,
                          "onnx_ir_version": 10, "operator_domain_version": 1,
                          "conversion": {"transformers_version": "4.46.3",
                                         "transformers_revision": "052e652d6d53c2b26ffde87e039b723949a53493",
                                         "torch_version": "2.5.1+cpu", "torch_revision": "a8d6afb511a69687bbb2b7e88a3cf67917e1697e",
                                         "datasets_version": "3.1.0", "safetensors_version": "0.4.5",
                                         "huggingface_hub_version": "0.26.2", "tokenizers_version": "0.20.3",
                                         "sympy_version": "1.13.1", "environment": "separate_from_qualification_runtime"}}, "runtime")
        _fields(manifest["quantizer"], {"bits": 4, "codes": {"minimum": -7, "maximum": 7},
                                       "scale_rule": "maxabs/7", "rounding": "nearest_ties_to_even",
                                       "zero_scale": 1, "group_axis": "contiguous_input_features_per_output",
                                       "scale_dtype": "float32", "zero_point": 8, "activation_quantization": False,
                                       "packing": {"format": "unsigned_offset_nibbles", "offset": 8,
                                                   "first_element": "low_nibble", "second_element": "high_nibble",
                                                   "unused_unsigned_code": 0,
                                                   "layout": "[output_features,ceil(input_features/group_size),group_size/2]",
                                                   "padding_signed_code": 0}}, "quantizer")
        _fields(manifest["rotation"], {"kind": "randomized_sylvester", "width": 2048,
                                      "seed_base": 20261017, "seed_rule": "seed_base_plus_layer_index",
                                      "generator": "NumPy PCG64", "placement": "after_gelu_before_mlp_output_projection",
                                      "row_vector_transform": "xQ", "pytorch_weight_transform": "WQ",
                                      "Q": "D H / sqrt(width)", "dense_Q_in_runtime": False,
                                      "runtime_algorithm": "sign_multiply_then_add_subtract_butterfly_then_normalize",
                                      "selection": "none"}, "rotation")
        expected_arms = [
            {"id": "fp32_original", "basis": "original", "weight_dtype": "float32", "group_size": None, "role": "reference"},
            {"id": "fp32_rotated", "basis": "rotated", "weight_dtype": "float32", "group_size": None, "role": "invariance_control"},
        ]
        for group, role in ((32, "primary"), (16, "sensitivity")):
            for basis, side in (("original", "baseline"), ("rotated", "treatment")):
                expected_arms.append({"id": f"w4a32_g{group}_{basis}", "basis": basis,
                                      "weight_dtype": "packed_uint4", "group_size": group, "role": f"{role}_{side}"})
        _expect(manifest["arms"], expected_arms, "arms, including precision and grouping")
        quality = manifest["quality"]
        _fields(quality, {"metric": "next_token_nll_nats", "aggregation": "sum_nll_divided_by_sum_valid_target_tokens",
                          "target_shift": 1, "valid_targets_per_article": 512,
                          "primary_comparison": {"treatment": "w4a32_g32_rotated", "baseline": "w4a32_g32_original",
                                                 "difference": "treatment_minus_baseline"},
                          "bootstrap": {"draws": 10000, "seed": 20261018, "unit": "whole_article_prefix",
                                        "shared_indices": True, "quantile_method": "linear",
                                        "percentiles": [2.5, 97.5], "weighted_ratio_recomputed_per_draw": True},
                          "acceptance": {"primary_difference_upper_95_lt": 0, "relative_perplexity_margin": 1.01,
                                         "sensitivity_selection": False},
                          "float_controls": {"relative_frobenius_max": 1e-5, "absolute_logit_error_max": 0.001,
                                             "absolute_nll_delta_max": 1e-5}}, "quality")
        threshold = quality["acceptance"]["rotated_minus_fp32_upper_95_lte"]
        if not isinstance(threshold, float) or not math.isfinite(threshold) or not math.isclose(threshold, math.log(1.01), abs_tol=1e-15):
            raise ContractError("quality acceptance must use the finite log(1.01) margin")
        timing = manifest["timing"]
        _expect(timing["workloads"], [
            {"id": "short", "batch_size": 1, "prompt_tokens": 128, "decode_steps": 32, "role": "sensitivity"},
            {"id": "primary", "batch_size": 1, "prompt_tokens": 512, "decode_steps": 128, "role": "primary"},
        ], "timing.workloads")
        _fields(timing, {"repeats": 20, "warmups_per_worker_and_workload": 1, "paired_block_seed": 20261019,
                         "order": "independent_arm_permutation_within_each_paired_block",
                         "input_rule": "same_train_article_tokens_and_fixed_teacher_forced_continuation_for_every_arm",
                         "article_schedule": "timing_article_index_equals_block_index_mod_4",
                         "workload_order": ["short", "primary"],
                         "peak_rss_comparison": "maximum_treatment_worker_peak_divided_by_maximum_baseline_worker_peak",
                         "early_eos_stop": False, "cache_reset_per_request": True,
                         "bootstrap": {"draws": 10000, "seed": 20261020, "unit": "paired_timing_block",
                                       "quantile_method": "linear", "ratio": "ratio_of_mean_treatment_time_to_mean_baseline_time"},
                         "acceptance": {"primary_prefill_ratio_upper_95_lte": 1.05, "primary_decode_ratio_upper_95_lte": 1.05,
                                        "primary_request_ratio_upper_95_lte": 1.05, "maximum_peak_rss_ratio_lte": 1.05}}, "timing")
        budgets = {"campaign_seconds": 1800, "acquisition_and_export_seconds": 600,
                   "quality_seconds": 600, "timing_seconds": 600, "process_memory_bytes": 6 * 1024**3,
                   "cache_and_output_bytes": 4 * 1024**3, "model_and_data_download_bytes": 1024**3,
                   "generated_controls_seconds": 180, "generated_controls_memory_bytes": 1024**3,
                   "paid_service_budget_usd": 0, "gpu_hours": 0, "model_workers": 1, "threads_per_worker": 1}
        _fields(manifest["budgets"], budgets, "budgets")
        _fields(manifest["hardware"], {"architecture": "x86_64", "cpu_model": "AMD EPYC 9V74 80-Core Processor",
                                       "target_threads": 1, "gpu_count": 0,
                                       "required_free_memory_bytes": budgets["process_memory_bytes"],
                                       "required_free_disk_bytes": budgets["cache_and_output_bytes"]}, "hardware")
        _expect(manifest["readiness"]["current_milestone_can_launch_campaign"], False, "readiness.current_milestone_can_launch_campaign")
        for name in ("acquisition_receipt", "full_model_adapter", "export_parity", "bounded_development_proof", "execution_lock"):
            path = manifest["readiness"][name]
            if not isinstance(path, str) or path.startswith("/") or ".." in path.split("/") or not path:
                raise ContractError(f"readiness.{name} must be a repository-relative path")
    except (KeyError, TypeError, AttributeError) as error:
        raise ContractError(f"missing or malformed manifest field: {error}") from error
    return {"status": "passed", "campaign_id": manifest["campaign_id"], "arm_count": 6,
            "primary_group_size": 32, "campaign_ready": False,
            "nominal_payload_by_group": {str(g): payload_counts(2048, 512, g, 6) for g in (32, 16)},
            "scope": "Frozen design validation only; artifact acquisition, adapter and campaign evidence remain unqualified."}
