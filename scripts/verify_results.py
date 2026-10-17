#!/usr/bin/env python3
"""Independently verify retained Hadamard results, without importing producers."""

from __future__ import annotations

import argparse
import ast
from fractions import Fraction
import hashlib
import json
import math
import os
from pathlib import Path
import re
import statistics

for _variable in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
    os.environ[_variable] = "1"

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
RTOL, ATOL = 2e-12, 2e-14
INVARIANCE_LIMIT = 2e-13
SEEDS = list(range(20))
CASES = ("isotropic_gaussian", "persistent_outlier")
GROUPS = (128, 64, 32, 16)
OUTPUT = "linear_output_relative_squared_error"
DIAGNOSTICS = tuple(f"{metric}_{arm}" for metric in (
    "activation_relative_squared_error", "weight_relative_squared_error",
    "activation_only_output_relative_squared_error", "weight_only_output_relative_squared_error",
    "mean_activation_peak_to_rms",
) for arm in ("original", "rotated"))
REFERENCE_METRICS = tuple(key for key in DIAGNOSTICS if not key.startswith("weight_only_")) + (
    f"{OUTPUT}_original", f"{OUTPUT}_rotated", "full_precision_relative_frobenius_difference",
    "fast_transform_max_absolute_difference", "output_error_ratio_rotated_over_original",
)
SOURCE_PATHS = {
    "group_experiment": "group_experiment.py", "focused_tests": "test_group_experiment.py",
    "reference_experiment": "experiment.py", "reference_results": "results.json",
    "protocol": "docs/experiments/group-size-v1.md",
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    def invalid_constant(value: str) -> None:
        raise ValueError(f"nonfinite JSON constant: {value}")
    def unique_object(pairs: list) -> dict:
        result = {}
        for key, value in pairs:
            require(key not in result, f"duplicate JSON key: {key}")
            result[key] = value
        return result
    return json.loads(path.read_text(), parse_constant=invalid_constant, object_pairs_hook=unique_object)


def number(value, label: str, nonnegative: bool = False) -> float:
    require(type(value) in (int, float) and math.isfinite(value), f"{label}: missing or nonfinite number")
    require(not nonnegative or value >= 0, f"{label}: negative value")
    return float(value)


def compare(actual, expected, label: str = "result") -> int:
    """Compare one deterministic retained structure with frozen numeric tolerances."""
    if isinstance(expected, dict):
        require(isinstance(actual, dict) and actual.keys() == expected.keys(), f"{label}: keys differ")
        return sum(compare(actual[key], value, f"{label}.{key}") for key, value in expected.items())
    if isinstance(expected, list):
        require(isinstance(actual, list) and len(actual) == len(expected), f"{label}: list length differs")
        return sum(compare(a, b, f"{label}[{i}]") for i, (a, b) in enumerate(zip(actual, expected)))
    if type(expected) is float:
        require(math.isclose(number(actual, label), expected, rel_tol=RTOL, abs_tol=ATOL), f"{label}: numeric mismatch")
        return 1
    require(type(actual) is type(expected) and actual == expected, f"{label}: identity or count mismatch")
    return 0


def check_row(row: dict, grouped: bool) -> None:
    require(type(row.get("seed")) is int and row["seed"] in SEEDS, "invalid seed identity")
    metrics = set(REFERENCE_METRICS) | (set(DIAGNOSTICS) if grouped else set())
    for key in metrics - {"output_error_ratio_rotated_over_original"}:
        number(row.get(key), key, nonnegative=True)
    require(row["full_precision_relative_frobenius_difference"] < INVARIANCE_LIMIT, "full-precision invariance limit exceeded")
    require(row["fast_transform_max_absolute_difference"] <= 2e-12, "fast-transform agreement limit exceeded")
    original, rotated = row[f"{OUTPUT}_original"], row[f"{OUTPUT}_rotated"]
    compare(row.get("rotated_output_error_lower"), rotated < original, "rotation-win flag")
    ratio = float(rotated / original) if original else None
    compare(row.get("output_error_ratio_rotated_over_original"), ratio, "per-seed output ratio")
    if grouped:
        compare(row.get("paired_output_error_difference"), float(rotated - original), "paired difference")


def verify_reference(reference: dict, root: Path) -> dict:
    require(reference["script_sha256"] == digest(root / "experiment.py"), "reference source hash differs")
    imported = load(root / "docs/reference-import.json")
    for filename in ("experiment.py", "results.json"):
        entries = [entry for entry in imported["imported_files"] if entry["path"] == filename]
        require(len(entries) == 1, f"reference import identity missing: {filename}")
        require(entries[0]["sha256"] == digest(root / filename), f"imported reference bytes changed: {filename}")
        require(entries[0]["bytes"] == (root / filename).stat().st_size, f"imported reference length changed: {filename}")
    # Read the configuration without executing the reference module. Its sole
    # nonliteral field is the frozen list(range(20)) seed declaration.
    assignments = [node.value for node in ast.parse((root / "experiment.py").read_text()).body
                   if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == "CONFIG" for target in node.targets)]
    require(len(assignments) == 1, "reference CONFIG declaration missing or duplicated")
    require(isinstance(assignments[0], ast.Dict), "reference CONFIG is not a dictionary")
    source_configuration = {}
    for key, value in zip(assignments[0].keys, assignments[0].values):
        name = ast.literal_eval(key)
        if name == "seeds":
            require(ast.dump(value) == ast.dump(ast.parse("list(range(20))", mode="eval").body), "reference seed declaration changed")
            source_configuration[name] = SEEDS
        else:
            source_configuration[name] = ast.literal_eval(value)
    compare(reference["configuration"], source_configuration, "reference configuration")
    records = reference["records"]
    identities = [(row["case"], row["seed"]) for row in records]
    expected_ids = {(case, seed) for case in (*CASES, "quantizer_grid") for seed in SEEDS}
    require(len(identities) == 60 and len(set(identities)) == 60 and set(identities) == expected_ids,
            "reference must retain all 60 unique expected records")
    for row in records:
        check_row(row, grouped=False)
        if row["case"] == "quantizer_grid":
            require(row[f"{OUTPUT}_original"] == 0 and row[f"{OUTPUT}_rotated"] > 0,
                    "reference grid counterexample was lost")
    expected_summary = {}
    for case in (*CASES, "quantizer_grid"):
        rows = [row for row in records if row["case"] == case]
        metrics = {}
        for key in REFERENCE_METRICS:
            values = [row[key] for row in rows if row[key] is not None]
            if values:
                metrics[key] = {"mean": math.fsum(values) / len(values), "median": float(statistics.median(values)),
                                "min": float(min(values)), "max": float(max(values))}
        expected_summary[case] = {"seeds": 20, "rotation_output_wins": sum(row[f"{OUTPUT}_rotated"] < row[f"{OUTPUT}_original"] for row in rows),
                                  "metrics": metrics}
    comparisons = compare(reference["summary"], expected_summary, "reference summary")
    exact = reference["exact_counterexample"]
    require(Fraction(exact["rotated_relative_squared_error_exact"]) == Fraction(11, 3332), "exact rational counterexample differs")
    compare(exact["rotated_relative_squared_error"], float(Fraction(11, 3332)), "counterexample float")
    compare(reference["validation"]["maximum_full_precision_relative_frobenius_difference"],
            float(max(row["full_precision_relative_frobenius_difference"] for row in records)), "reference invariance maximum")
    return {"records": 60, "summary_numeric_comparisons": comparisons, "reference_source_and_import_bytes_match": True}


def scale_counts(group: int) -> dict:
    activation, weight = 512 * (128 // group), 64 * (128 // group)
    return {"activation_per_arm": activation, "weight_per_arm": weight, "total_per_arm": activation + weight}


def resampling() -> tuple[np.ndarray, np.ndarray, str]:
    indices = np.random.Generator(np.random.PCG64(20261017)).integers(0, 20, size=(10000, 20), dtype=np.int64)
    header = json.dumps({"shape": [10000, 20], "dtype": indices.dtype.str}, sort_keys=True).encode()
    identity = hashlib.sha256(header + b"\n" + indices.tobytes(order="C")).hexdigest()
    # Count each whole seed's multiplicity. This differs from the producer's
    # direct row-indexing calculation and preserves the pairing of every metric.
    weights = np.zeros((10000, 20), dtype=np.float64)
    np.add.at(weights, (np.arange(10000)[:, None], indices), 1)
    return indices, weights, identity


def interval(values: np.ndarray) -> list[float]:
    ordered = np.sort(values)
    require(len(ordered) == 10000 and np.isfinite(ordered).all(), "invalid bootstrap draw observations")
    bounds = []
    for probability in (0.025, 0.975):
        position = probability * (len(ordered) - 1)
        low = math.floor(position)
        fraction = position - low
        bounds.append(float(ordered[low] * (1 - fraction) + ordered[min(low + 1, len(ordered) - 1)] * fraction))
    return bounds


def expected_summary(rows: list[dict], weights: np.ndarray, index_digest: str) -> dict:
    ordered = sorted(rows, key=lambda row: row["seed"])
    keys = (f"{OUTPUT}_original", f"{OUTPUT}_rotated", *DIAGNOSTICS)
    columns = np.asarray([[row[key] for key in keys] for row in ordered], dtype=np.float64)
    draws = weights @ columns / 20
    original = [row[keys[0]] for row in ordered]
    rotated = [row[keys[1]] for row in ordered]
    original_mean, rotated_mean = math.fsum(original) / 20, math.fsum(rotated) / 20
    require(original_mean > 0 and np.all(draws[:, 0] > 0), "undefined grouped reduction denominator")
    differences = [b - a for a, b in zip(original, rotated)]
    paired_mean = math.fsum(differences) / 20
    paired_draws = draws[:, 1] - draws[:, 0]
    case, group = ordered[0]["case"], ordered[0]["group_size"]
    return {
        "case": case, "group_size": group, "endpoint_role": "primary" if (case, group) == ("persistent_outlier", 32) else "sensitivity",
        "seed_count": 20, "seed_order": SEEDS, "matched_scale_counts": scale_counts(group), "bootstrap_indices_sha256": index_digest,
        "output": {
            "original_mean": original_mean, "rotated_mean": rotated_mean,
            "paired_difference_mean": paired_mean, "paired_difference_percentage_points": 100 * paired_mean,
            "relative_reduction_in_mean_error": 1 - rotated_mean / original_mean,
            "rotation_win_count": sum(b < a for a, b in zip(original, rotated)),
            "bootstrap_95": {"original_mean": interval(draws[:, 0]), "rotated_mean": interval(draws[:, 1]),
                "paired_difference_mean": interval(paired_draws), "paired_difference_percentage_points": interval(100 * paired_draws),
                "relative_reduction_in_mean_error": interval(1 - draws[:, 1] / draws[:, 0])},
            "bootstrap_reduction_defined_draw_count": 10000,
        },
        "diagnostics": {key: {"mean": math.fsum(row[key] for row in ordered) / 20,
            "min": float(min(row[key] for row in ordered)), "max": float(max(row[key] for row in ordered)),
            "bootstrap_95": interval(draws[:, index + 2])} for index, key in enumerate(DIAGNOSTICS)},
    }


def verify_group(group: dict, reference: dict, root: Path) -> dict:
    require(group.get("schema_version") == 1 and group.get("status") == "complete" and group.get("phase") == "complete",
            "group receipt is incomplete or failed")
    require("failure" not in group and "active_cell" not in group, "group receipt retains an unresolved failure")
    compare(group["provenance"]["sha256"], {name: digest(root / path) for name, path in SOURCE_PATHS.items()}, "source/protocol/reference identities")
    compare(group["provenance"]["protocol_path"], SOURCE_PATHS["protocol"], "protocol path")
    compare(group["provenance"]["protocol_issue"], "https://github.com/Whyme-Labs/hadamard-exposition/issues/1", "protocol issue")
    configuration = group["configuration"]
    expected_configuration = {"experiment": "hadamard_quantization_group_size_v1", "cases": list(CASES), "seeds": SEEDS,
        "group_sizes": list(GROUPS), "bits": 4, "tokens_per_seed": 512, "input_features": 128, "output_features": 64,
        "outlier_channel_multiplier": 32.0, "rotation_seed_offset": 100000, "configured_process_deadline_seconds": 180,
        "rotation": "unchanged full-width Q = D H / sqrt(128), shared across cases and group sizes",
        "activation_group_axis": "contiguous input features within each row",
        "weight_group_axis": "contiguous input features down each output column",
        "quantizer": "reference maxabs rule, codes -7 through +7, round-to-nearest ties-to-even; zero groups use scale 1",
        "scope": "float64 synthetic error simulation; previously inspected seeds; no model, network, GPU, memory compression, latency or throughput measurement",
        "primary_endpoint": {"case": "persistent_outlier", "group_size": 32, "metric": "paired difference in relative squared output error, rotated minus original"},
        "bootstrap": {"draws": 10000, "seed": 20261017, "generator": "NumPy PCG64", "unit": "whole seed record",
                      "shared_indices_across_settings": True, "interval": "descriptive 2.5th and 97.5th percentiles", "quantile_method": "linear"},
        "scale_counts_per_setting": {str(size): scale_counts(size) for size in GROUPS}}
    compare(configuration, expected_configuration, "configuration")
    compare(group["provenance"]["configuration_sha256"], hashlib.sha256(json.dumps(configuration, sort_keys=True).encode()).hexdigest(), "configuration hash")
    for variable in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS"):
        require(group["environment"]["thread_environment"][variable] == "1", f"{variable} was not one")
    for pool in group["environment"]["threadpools"] or []:
        require(pool.get("user_api") != "blas" or pool["num_threads"] == 1, "retained BLAS pool was not one thread")
    for key, value in group["timing"].items():
        if key.endswith("seconds"):
            number(value, f"timing.{key}", nonnegative=True)
    require(group["timing"]["total_run_wall_seconds"] <= 180, "retained computation exceeded its process deadline")
    outer_fields = {"outer_process_wall_seconds", "outer_timeout_seconds", "outer_process_exit_code"}
    if outer_fields & group["timing"].keys():
        require(outer_fields <= group["timing"].keys(), "incomplete outer-process observations")
        compare(group["timing"]["outer_process_exit_code"], 0, "outer-process exit code")
        require(group["timing"]["outer_timeout_seconds"] == 180 and group["timing"]["outer_process_wall_seconds"] <= 180,
                "outer process exceeded its frozen deadline")
    rows = group["records"]
    identities = [(row["case"], row["seed"], row["group_size"]) for row in rows]
    expected_ids = {(case, seed, size) for case in CASES for seed in SEEDS for size in GROUPS}
    require(len(identities) == 160 and len(set(identities)) == 160 and set(identities) == expected_ids,
            "group results must retain all 160 unique expected cells")
    reference_rows = {(row["case"], row["seed"]): row for row in reference["records"]}
    numeric_count, boolean_count, maximum_difference = 0, 0, 0.0
    for row in rows:
        check_row(row, grouped=True)
        require(type(row["group_size"]) is int, "invalid group identity")
        counts = scale_counts(row["group_size"])
        compare(row["scale_counts"], {f"{kind}_{arm}": counts[f"{kind}_per_arm"] for kind in ("activation", "weight", "total")
                                     for arm in ("original", "rotated")}, "matched scale counts")
        require(row["data_sha256"].keys() == {"activation", "weight", "rotation"}, "missing data identity")
        require(all(isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) for value in row["data_sha256"].values()), "invalid data digest")
        if row["group_size"] == 128:
            baseline = reference_rows[(row["case"], row["seed"])]
            for key, value in baseline.items():
                compare(row[key], value, f"g128 reference {row['case']} seed {row['seed']} {key}")
                if type(value) in (int, float) and key != "seed":
                    numeric_count += 1
                    maximum_difference = max(maximum_difference, abs(row[key] - value))
                if type(value) is bool:
                    boolean_count += 1
    for case in CASES:
        for seed in SEEDS:
            selected = [row for row in rows if row["case"] == case and row["seed"] == seed]
            require(len({json.dumps(row["data_sha256"], sort_keys=True) for row in selected}) == 1, "data or rotation differs across group sizes")
    for seed in SEEDS:
        selected = [row for row in rows if row["seed"] == seed]
        for key in ("rotation", "weight"):
            require(len({row["data_sha256"][key] for row in selected}) == 1, f"{key} differs across cases")
    indices, weights, index_digest = resampling()
    compare(group["bootstrap_resampling"], {"shape": [10000, 20], "indices_sha256": index_digest,
            "first_three_draws": indices[:3].tolist(), "seed_order": SEEDS}, "shared whole-seed resampling")
    summaries = {(summary["case"], summary["group_size"]): summary for summary in group["summaries"]}
    require(len(group["summaries"]) == 8 and set(summaries) == {(case, size) for case in CASES for size in GROUPS}, "missing or duplicate setting summaries")
    summary_comparisons = 0
    for identity, summary in summaries.items():
        selected = [row for row in rows if (row["case"], row["group_size"]) == identity]
        summary_comparisons += compare(summary, expected_summary(selected, weights, index_digest), f"summary {identity}")
    expected_validation = {"complete_unique_paired_cells": 160, "matched_scale_counts": True, "finite_metrics": True,
        "full_width_data_and_rotation_reused": True,
        "maximum_full_precision_relative_frobenius_difference": float(max(row["full_precision_relative_frobenius_difference"] for row in rows)),
        "g128_reference": {"passed": True, "numeric_comparisons": numeric_count, "boolean_comparisons": boolean_count,
                           "rtol": RTOL, "atol": ATOL, "maximum_absolute_metric_difference": float(maximum_difference)},
        "source_reference_and_protocol_unchanged_during_run": True, "shared_whole_seed_bootstrap_indices": True}
    compare(group["validation"], expected_validation, "producer validation observations")
    return {"paired_cells": 160, "settings": 8, "g128_numeric_comparisons": numeric_count,
            "summary_numeric_comparisons": summary_comparisons, "bootstrap_draws_per_setting": 10000,
            "bootstrap_indices_sha256": index_digest, "rtol": RTOL, "atol": ATOL,
            "method": "independent arithmetic seed means, bootstrap seed multiplicities, and linear order-statistic interpolation"}


def verify_retained(root: Path = ROOT, group_path: Path | None = None) -> dict:
    reference = load(root / "results.json")
    group = load(group_path or root / "group-results.json")
    return {"status": "passed", "reference": verify_reference(reference, root), "group": verify_group(group, reference, root)}


def compare_reproduction(retained: dict, reproduced: dict) -> dict:
    variable = {"started_utc", "finished_utc", "environment", "timing"}
    count = compare({key: value for key, value in reproduced.items() if key not in variable},
                    {key: value for key, value in retained.items() if key not in variable}, "reproduction")
    return {"status": "passed", "numeric_comparisons": count, "rtol": RTOL, "atol": ATOL,
            "runtime_metadata_not_compared_for_equality": sorted(variable)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--group-results", type=Path)
    args = parser.parse_args()
    print(json.dumps(verify_retained(group_path=args.group_results), indent=2, allow_nan=False))
