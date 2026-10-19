#!/usr/bin/env python3
"""Audit saved affine vectors and execute exactly eight FP64 candidates."""

from __future__ import annotations

import argparse
from contextlib import redirect_stdout
from fractions import Fraction
import hashlib
import io
import json
import math
import os
from pathlib import Path
import resource
import sys
import time
import traceback

sys.dont_write_bytecode = True
from run_audit import (
    ROOT, CASE_IDS, CHECKPOINT_RELATIVE, classify_candidate, file_identity, numpy_startup_evidence,
    utc_now, validate_preparation, verify_registration, write_json,
)
from audit_io import QKV, MLP, load_checkpoint, load_trace_cases
from affine_exact import (
    absolute_error_numerator, f32_bits_to_scaled_int, iter_exact_affine_rows,
    round_accumulator_to_f32_bits, ulp_distance,
)
from benchmarks.campaign_guard import THREADS
from benchmarks.qualify import _publish_worker_identity


def reject_network(event, args):
    if event.startswith("socket."):
        raise RuntimeError("The arithmetic worker permits no network operations")


def array_identity(array):
    return {"shape": list(array.shape), "dtype": array.dtype.str, "bytes": int(array.nbytes),
            "strides": list(array.strides), "c_contiguous": bool(array.flags.c_contiguous),
            "f_contiguous": bool(array.flags.f_contiguous),
            "c_order_sha256": hashlib.sha256(array.tobytes(order="C")).hexdigest()}


def require_binary_formats(np):
    expected = {"float32": (32, 23, 8, -126, 128), "float64": (64, 52, 11, -1022, 1024)}
    result = {}
    for name, values in expected.items():
        info = np.finfo(getattr(np, name))
        actual = tuple(int(getattr(info, key)) for key in ("bits", "nmant", "iexp", "minexp", "maxexp"))
        if actual != values:
            raise ValueError("The runtime floating representation differs from binary32/binary64")
        result[name] = dict(zip(("bits", "nmant", "iexp", "minexp", "maxexp"), actual, strict=True))
    if sys.byteorder != "little":
        raise ValueError("This x86_64 bit audit requires the recorded little-endian runtime")
    return result


def backend_observation(np):
    import threadpoolctl

    pools = threadpoolctl.threadpool_info()
    blas = [item for item in pools if item.get("user_api") == "blas"]
    if not blas or any(item.get("num_threads") != 1 for item in pools):
        raise ValueError("An observable BLAS pool and one thread per reported pool are required")
    if any(os.environ.get(name) != "1" for name in THREADS):
        raise ValueError("A prescribed thread environment differs")
    stream = io.StringIO()
    with redirect_stdout(stream):
        np.show_runtime()
    return {"numpy_version": np.__version__, "threadpoolctl_version": threadpoolctl.__version__,
            "numpy_import_source": file_identity(Path(np.__file__)),
            "thread_environment": {name: os.environ.get(name) for name in THREADS},
            "threadpools": pools, "numpy_build_config": np.show_config(mode="dicts"),
            "numpy_runtime_text": stream.getvalue(), "binary_formats": require_binary_formats(np)}


def fp32_metrics(bits, sums, targets):
    errors = [absolute_error_numerator(int(value), total) for value, total in zip(bits, sums, strict=True)]
    steps = [ulp_distance(int(value), int(target)) for value, target in zip(bits, targets, strict=True)]
    absolute_index = max(range(len(errors)), key=errors.__getitem__)
    step_index = max(range(len(steps)), key=steps.__getitem__)
    return {"bit_mismatches": sum(int(value) != int(target) for value, target in zip(bits, targets, strict=True)),
            "exact_matches": sum(error == 0 for error in errors),
            "max_absolute_error": math.ldexp(float(errors[absolute_index]), -298),
            "max_absolute_error_numerator_hex": hex(errors[absolute_index]),
            "error_scale_exponent": -298, "max_absolute_error_index": absolute_index,
            "max_representable_steps": steps[step_index], "max_representable_steps_index": step_index,
            "at_max_absolute_error": {"observed_bits_hex": f"{int(bits[absolute_index]):08x}",
                                      "exact_rounded_bits_hex": f"{int(targets[absolute_index]):08x}"}}


def fp64_metrics(values, sums):
    # Rational comparison is independent of the candidate reduction and cast.
    errors = [abs(Fraction.from_float(float(value)) - Fraction(total, 1 << 298))
              for value, total in zip(values, sums, strict=True)]
    index = max(range(len(errors)), key=errors.__getitem__)
    maximum = errors[index]
    return {"max_absolute_error": float(maximum), "max_absolute_error_index": index,
            "exact_max_error_numerator": str(maximum.numerator),
            "exact_max_error_denominator": str(maximum.denominator),
            "exact_matches": sum(value == 0 for value in errors)}


def historical_metrics(case, sums, targets):
    full = case["full_output"].view("uint32")
    cached = case["cached_output"].view("uint32")
    f_errors = [absolute_error_numerator(int(value), total) for value, total in zip(full, sums, strict=True)]
    c_errors = [absolute_error_numerator(int(value), total) for value, total in zip(cached, sums, strict=True)]
    gaps = [abs(f32_bits_to_scaled_int(int(f)) - f32_bits_to_scaled_int(int(c)))
            for f, c in zip(full, cached, strict=True)]
    index = max(range(len(gaps)), key=gaps.__getitem__)
    return {"full": fp32_metrics(full, sums, targets), "cached": fp32_metrics(cached, sums, targets),
            "closer_to_exact": {"full": sum(f < c for f, c in zip(f_errors, c_errors, strict=True)),
                                "cached": sum(c < f for f, c in zip(f_errors, c_errors, strict=True)),
                                "ties": sum(c == f for f, c in zip(f_errors, c_errors, strict=True))},
            "full_vs_cached": {"numerically_different_values": sum(g != 0 for g in gaps),
                               "bit_different_values": sum(int(f) != int(c) for f, c in zip(full, cached, strict=True)),
                               "max_absolute_difference": math.ldexp(float(gaps[index]), -149),
                               "max_difference_scaled_integer_hex": hex(gaps[index]),
                               "scale_exponent": -149, "max_difference_index": index}}


def save_npz(np, path, arrays):
    with path.open("xb") as stream:
        np.savez(stream, **arrays)


def journal_event(stream, value):
    stream.write(json.dumps(value, sort_keys=True, allow_nan=False) + "\n")
    stream.flush()
    os.fsync(stream.fileno())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--review", type=Path, required=True)
    parser.add_argument("--publication", type=Path, required=True)
    parser.add_argument("--preparation", type=Path, required=True)
    args = parser.parse_args()
    started = time.monotonic()
    counts = {name: 0 for name in ("matrix_attempted", "matrix_completed", "bias_attempted", "bias_completed",
                                  "cast_attempted", "cast_completed", "exact_scalar_outputs", "exact_integer_products")}
    result = {"schema_version": "hadamard-operator-arithmetic.v1", "status": "failed",
              "started_utc": utc_now(), "counts": counts, "cases": [], "inputs_unchanged": False,
              "counts_scope": "Explicit exact audit and checkpoint/trace candidate evaluations; NumPy import controls are separate",
              "fresh_native_fp32_affine_calls": 0, "torch_calls": 0, "model_calls": 0,
              "network_received_bytes": 0, "dependency_received_bytes": 0,
              "quality_test_accessed": False, "timing_tokens_accessed": False, "campaign_ready": False,
              "timing_scope": "Resource-bound execution receipt; not a speed benchmark"}
    vectors = {}
    np = None
    try:
        result["worker_identity"] = _publish_worker_identity(args.output)
        sys.addaudithook(reject_network)
        result["registration_before"] = verify_registration(args.review, args.publication)
        result["preparation_files_before"] = validate_preparation(args.preparation, result["registration_before"])
        write_json(args.output / "start.json", result)
        import numpy as np

        result["numpy_import_self_checks"] = numpy_startup_evidence(np)
        result["backend_before"] = backend_observation(np)
        tensors, parameter_receipt = load_checkpoint(args.preparation / CHECKPOINT_RELATIVE)
        cases, trace_receipt = load_trace_cases(ROOT)
        if [c["id"] for c in cases] != list(CASE_IDS):
            raise ValueError("The bound trace case order differs")
        result["parameter_inputs"] = parameter_receipt
        result["trace_inputs"] = trace_receipt
        for tensor in tensors.values():
            tensor.flags.writeable = False
        for case in cases:
            for name in ("input", "full_output", "cached_output"):
                case[name].flags.writeable = False
        save_npz(np, args.output / "selected-parameters.npz", tensors)
        write_json(args.output / "parameter-derivation.json", parameter_receipt)
        write_json(args.output / "trace-inputs.json", trace_receipt)

        sums_by_case = {case["id"]: [] for case in cases}
        for module in (QKV, MLP):
            selected = [case for case in cases if case["module"] == module]
            inputs = [case["input"].view(np.uint32) for case in selected]
            weight = tensors[module + ".weight"].view(np.uint32)
            bias = tensors[module + ".bias"].view(np.uint32)
            for outputs in iter_exact_affine_rows(inputs, weight, bias):
                for case, total in zip(selected, outputs, strict=True):
                    sums_by_case[case["id"]].append(total)
                    counts["exact_scalar_outputs"] += 1
                    counts["exact_integer_products"] += 512
        if counts["exact_scalar_outputs"] != 7168 or counts["exact_integer_products"] != 3_670_016:
            raise ValueError("The exact arithmetic population differs")
        write_json(args.output / "exact-sums.json", {
            "schema_version": "hadamard-exact-affine-sums.v1", "scale_exponent": -298,
            "case_order": list(CASE_IDS), "rounding": "direct_binary32_nearest_ties_even",
            "sums_signed_hex": {name: [hex(value) for value in totals] for name, totals in sums_by_case.items()},
        })

        with (args.output / "candidate-calls.jsonl").open("x", encoding="utf-8") as journal:
            for case in cases:
                key, module = case["id"], case["module"]
                sums = sums_by_case[key]
                targets = np.array([round_accumulator_to_f32_bits(total) for total in sums], dtype=np.uint32)
                if not np.isfinite(targets.view(np.float32)).all():
                    raise ValueError("The exact final-round target is not finite")
                observed = {"id": key, "article": case["article"], "module": module,
                            "provenance": case["provenance"], "historical": historical_metrics(case, sums, targets),
                            "candidate": []}
                result["cases"].append(observed)
                for name in ("input", "full_output", "cached_output"):
                    vectors[f"{key}_{name}"] = case[name]
                vectors[f"{key}_exact_fp32_bits"] = targets
                w64 = tensors[module + ".weight"].astype(np.float64, order="C", casting="safe")
                b64 = tensors[module + ".bias"].astype(np.float64, order="C", casting="safe")
                for rows in (1, 513):
                    x64 = np.repeat(case["input"].astype(np.float64)[None, :], rows, axis=0)
                    call = {"case": key, "rows": rows, "ordinal": counts["matrix_attempted"] + 1,
                            "input": array_identity(x64), "weight_transpose": array_identity(w64.T),
                            "bias": array_identity(b64), "completed": False}
                    journal_event(journal, {"event": "attempt", "at_utc": utc_now(), **call})
                    counts["matrix_attempted"] += 1
                    product64 = x64 @ w64.T
                    counts["matrix_completed"] += 1
                    counts["bias_attempted"] += 1
                    output64 = product64 + b64
                    counts["bias_completed"] += 1
                    counts["cast_attempted"] += 1
                    output32 = output64.astype(np.float32, order="C", casting="same_kind")
                    counts["cast_completed"] += 1
                    if (product64.dtype != np.float64 or output64.dtype != np.float64
                            or output32.dtype != np.float32
                            or output64.shape != (rows, len(sums))
                            or not np.isfinite(product64).all() or not np.isfinite(output64).all()
                            or not np.isfinite(output32).all()):
                        raise ValueError("A candidate output shape, dtype or finite-value check failed")
                    final64, final32 = output64[-1].copy(), output32[-1].copy()
                    vectors[f"{key}_rows{rows}_fp64"] = final64
                    vectors[f"{key}_rows{rows}_fp32"] = final32
                    call.update(completed=True, checked_final_values=len(sums),
                                full_product64=array_identity(product64),
                                full_output64=array_identity(output64), full_output32=array_identity(output32),
                                retained_final64=array_identity(final64), retained_final32=array_identity(final32),
                                fp64_vs_exact=fp64_metrics(final64, sums),
                                fp32_vs_exact=fp32_metrics(final32.view(np.uint32), sums, targets))
                    observed["candidate"].append(call)
                    journal_event(journal, {"event": "complete", "at_utc": utc_now(), **call})
                    del product64, output64, output32, x64
        if any(counts[name] != 8 for name in counts if name not in ("exact_scalar_outputs", "exact_integer_products")):
            raise ValueError("The eight-evaluation call budget did not complete exactly")
        result["candidate_qualification"] = classify_candidate(result["cases"])
        result["backend_after"] = backend_observation(np)
        if result["backend_after"] != result["backend_before"]:
            raise ValueError("The observed NumPy/BLAS environment changed")
        result["trace_source_files_after"] = {name: file_identity(ROOT / name)
                                               for name in trace_receipt["source_files"]}
        if result["trace_source_files_after"] != trace_receipt["source_files"]:
            raise ValueError("Retained trace/source inputs changed during the audit")
        result["preparation_files_after"] = validate_preparation(args.preparation, result["registration_before"])
        if result["preparation_files_after"] != result["preparation_files_before"]:
            raise ValueError("Checkpoint preparation inputs changed during the audit")
        result["registration_after"] = verify_registration(args.review, args.publication)
        if result["registration_after"] != result["registration_before"]:
            raise ValueError("The reviewed source/protocol inputs changed")
        if any(name == "torch" or name.startswith("torch.") for name in sys.modules):
            raise ValueError("An unexpected Torch import occurred")
        result["inputs_unchanged"] = True
        result["status"] = "passed"
    except Exception as error:
        result["error"] = {"type": type(error).__name__, "message": str(error)}
        traceback.print_exc()
    if np is not None and vectors:
        save_npz(np, args.output / "audited-vectors.npz", vectors)
    result["evidence_files"] = {p.name: file_identity(p) for p in sorted(args.output.iterdir())
                                if p.is_file() and p.name not in ("stdout.log", "stderr.log")}
    result.update(finished_utc=utc_now(), elapsed_seconds=time.monotonic() - started,
                  peak_worker_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024)
    write_json(args.output / "worker-result.json", result)
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
