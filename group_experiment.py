#!/usr/bin/env python3
"""Frozen group-size sensitivity study, using the unchanged reference primitives.

Run with one BLAS thread and an outer 180-second process deadline. A normal run
refuses to overwrite a prior receipt. --plot-only redraws retained results.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
from importlib import metadata
import json
import os
from pathlib import Path
import platform
import time

import experiment as reference
import numpy as np

ROOT = Path(__file__).resolve().parent
CASES = ("isotropic_gaussian", "persistent_outlier")
GROUP_SIZES = (128, 64, 32, 16)
SEEDS = tuple(range(20))
BOOTSTRAP_DRAWS = 10000
BOOTSTRAP_SEED = 20261017
REFERENCE_RTOL = 2e-12
REFERENCE_ATOL = 2e-14
INVARIANCE_LIMIT = 2e-13
PROTOCOL = ROOT / "docs/experiments/group-size-v1.md"
SOURCE_PATHS = {
    "group_experiment": ROOT / "group_experiment.py",
    "focused_tests": ROOT / "test_group_experiment.py",
    "reference_experiment": ROOT / "experiment.py",
    "reference_results": ROOT / "results.json",
    "protocol": PROTOCOL,
}
OUTPUT_KEYS = (
    "linear_output_relative_squared_error_original",
    "linear_output_relative_squared_error_rotated",
)
DIAGNOSTIC_KEYS = tuple(
    f"{metric}_{basis}"
    for metric in (
        "activation_relative_squared_error",
        "weight_relative_squared_error",
        "activation_only_output_relative_squared_error",
        "weight_only_output_relative_squared_error",
        "mean_activation_peak_to_rms",
    )
    for basis in ("original", "rotated")
)


@dataclass(frozen=True)
class GroupQuantization:
    values: np.ndarray
    scales: np.ndarray


def quantize_groups(a: np.ndarray, group_size: int, feature_axis: int, bits: int = 4) -> GroupQuantization:
    """Group contiguous features, then call the original scalar quantizer.

    X uses feature_axis=1, W uses feature_axis=0. The returned scales have
    shape [non-feature coordinate, contiguous feature group].
    """
    values = np.asarray(a, dtype=np.float64)
    if values.ndim != 2 or feature_axis not in (0, 1):
        raise ValueError("expected a matrix and feature_axis 0 or 1")
    if isinstance(group_size, bool) or not isinstance(group_size, int) or group_size <= 0:
        raise ValueError("group_size must be a positive integer")
    if not isinstance(bits, int) or isinstance(bits, bool) or bits < 2:
        raise ValueError("bits must be an integer of at least two")
    if values.size == 0 or not np.isfinite(values).all():
        raise ValueError("values must be nonempty and finite")
    moved = np.moveaxis(values, feature_axis, -1)
    if moved.shape[-1] % group_size:
        raise ValueError("feature count must be divisible by group_size")
    grouped = moved.reshape(moved.shape[0], moved.shape[1] // group_size, group_size)
    rounded = reference.quantize(grouped, axis=-1, bits=bits)
    maximum_code = (1 << (bits - 1)) - 1
    maxima = np.max(np.abs(grouped), axis=-1)
    scales = np.where(maxima == 0, 1.0, maxima / maximum_code)
    reconstructed = np.moveaxis(rounded.reshape(moved.shape), -1, feature_axis)
    return GroupQuantization(reconstructed, scales)


def expected_scale_counts(group_size: int) -> dict[str, int]:
    groups = reference.CONFIG["input_features"] // group_size
    activation = reference.CONFIG["tokens_per_seed"] * groups
    weight = reference.CONFIG["output_features"] * groups
    return {"activation_per_arm": activation, "weight_per_arm": weight, "total_per_arm": activation + weight}


def array_sha256(a: np.ndarray) -> str:
    canonical = np.ascontiguousarray(a)
    header = json.dumps({"shape": list(a.shape), "dtype": a.dtype.str}, sort_keys=True).encode()
    return hashlib.sha256(header + b"\n" + canonical.tobytes()).hexdigest()


def source_hashes() -> dict[str, str]:
    return {name: hashlib.sha256(path.read_bytes()).hexdigest() for name, path in SOURCE_PATHS.items()}


def prepare_seed(seed: int, case: str) -> dict:
    x, w, q, signs = reference.matrices(seed, case)
    y, xr, wr = x @ w, x @ q, q.T @ w
    invariance = float(np.sqrt(reference.relative_squared_error(xr @ wr, y)))
    if not np.isfinite(invariance) or invariance >= INVARIANCE_LIMIT:
        raise ValueError(f"full-precision invariance failed for {case}, seed {seed}: {invariance}")
    return {
        "x": x, "w": w, "q": q, "y": y, "xr": xr, "wr": wr,
        "invariance": invariance,
        "fast_difference": float(np.max(np.abs(reference.fwht_rows(x * signs) - xr))),
        "peak_original": reference.peak_to_rms(x),
        "peak_rotated": reference.peak_to_rms(xr),
        "data_hashes": {"activation": array_sha256(x), "weight": array_sha256(w), "rotation": array_sha256(q)},
    }


def run_cell(prepared: dict, seed: int, case: str, group_size: int) -> dict:
    x, w, q, y, xr, wr = [prepared[k] for k in ("x", "w", "q", "y", "xr", "wr")]
    xq = quantize_groups(x, group_size, feature_axis=1)
    wq = quantize_groups(w, group_size, feature_axis=0)
    xrq = quantize_groups(xr, group_size, feature_axis=1)
    wrq = quantize_groups(wr, group_size, feature_axis=0)
    error = reference.relative_squared_error
    original_output = error(xq.values @ wq.values, y)
    rotated_output = error(xrq.values @ wrq.values, y)
    result = {
        "case": case, "seed": seed, "group_size": group_size,
        "data_sha256": prepared["data_hashes"],
        "scale_counts": {
            "activation_original": int(xq.scales.size), "activation_rotated": int(xrq.scales.size),
            "weight_original": int(wq.scales.size), "weight_rotated": int(wrq.scales.size),
            "total_original": int(xq.scales.size + wq.scales.size),
            "total_rotated": int(xrq.scales.size + wrq.scales.size),
        },
        "activation_relative_squared_error_original": error(xq.values, x),
        "activation_relative_squared_error_rotated": error(xrq.values @ q.T, x),
        "weight_relative_squared_error_original": error(wq.values, w),
        "weight_relative_squared_error_rotated": error(q @ wrq.values, w),
        "activation_only_output_relative_squared_error_original": error(xq.values @ w, y),
        "activation_only_output_relative_squared_error_rotated": error(xrq.values @ wr, y),
        "weight_only_output_relative_squared_error_original": error(x @ wq.values, y),
        "weight_only_output_relative_squared_error_rotated": error(xr @ wrq.values, y),
        OUTPUT_KEYS[0]: original_output,
        OUTPUT_KEYS[1]: rotated_output,
        "paired_output_error_difference": rotated_output - original_output,
        "mean_activation_peak_to_rms_original": prepared["peak_original"],
        "mean_activation_peak_to_rms_rotated": prepared["peak_rotated"],
        "full_precision_relative_frobenius_difference": prepared["invariance"],
        "fast_transform_max_absolute_difference": prepared["fast_difference"],
        "output_error_ratio_rotated_over_original": rotated_output / original_output if original_output else None,
        "rotated_output_error_lower": rotated_output < original_output,
    }
    if any(not np.isfinite(value) for value in result.values() if isinstance(value, float)):
        raise ValueError(f"nonfinite metric for {case}, seed {seed}, group {group_size}")
    return result


def bootstrap_indices(seed_count: int, draws: int = BOOTSTRAP_DRAWS, random_seed: int = BOOTSTRAP_SEED) -> np.ndarray:
    if seed_count <= 0 or draws <= 0:
        raise ValueError("seed_count and draws must be positive")
    rng = np.random.Generator(np.random.PCG64(random_seed))
    return rng.integers(0, seed_count, size=(draws, seed_count), dtype=np.int64)


def percentile_interval(values: np.ndarray) -> list[float]:
    if values.size == 0 or not np.isfinite(values).all():
        raise ValueError("percentile input must be nonempty and finite")
    return [float(x) for x in np.quantile(values, [0.025, 0.975], method="linear")]


def summarize_setting(rows: list[dict], indices: np.ndarray, seed_order: tuple[int, ...]) -> dict:
    """Resample whole paired rows, keeping seed order fixed across settings."""
    if not rows or len(seed_order) != len(set(seed_order)):
        raise ValueError("rows and unique expected seed identities are required")
    by_seed = {r["seed"]: r for r in rows}
    if len(by_seed) != len(rows) or set(by_seed) != set(seed_order):
        raise ValueError("seed identities are duplicated, missing, or unexpected")
    if len({(r["case"], r["group_size"]) for r in rows}) != 1:
        raise ValueError("a summary must contain one case and group size")
    if indices.ndim != 2 or indices.shape[0] == 0 or indices.shape[1] != len(seed_order):
        raise ValueError("bootstrap draws must contain exactly one position per seed")
    if not np.issubdtype(indices.dtype, np.integer) or np.any(indices < 0) or np.any(indices >= len(seed_order)):
        raise ValueError("bootstrap positions must be valid integer seed indices")
    ordered = [by_seed[s] for s in seed_order]
    original = np.array([r[OUTPUT_KEYS[0]] for r in ordered], dtype=np.float64)
    rotated = np.array([r[OUTPUT_KEYS[1]] for r in ordered], dtype=np.float64)
    if not np.isfinite(original).all() or not np.isfinite(rotated).all() or np.any(original < 0) or np.any(rotated < 0):
        raise ValueError("output errors must be finite and nonnegative")
    original_mean, rotated_mean = float(np.mean(original)), float(np.mean(rotated))
    paired_difference = rotated - original
    boot_original, boot_rotated = original[indices].mean(axis=1), rotated[indices].mean(axis=1)
    boot_difference = paired_difference[indices].mean(axis=1)
    valid_reduction = boot_original > 0
    reduction_draws = 1.0 - boot_rotated[valid_reduction] / boot_original[valid_reduction]
    # Do not silently drop undefined draws to manufacture a ratio interval.
    reduction_interval = percentile_interval(reduction_draws) if valid_reduction.all() else None
    intervals = {
        "original_mean": percentile_interval(boot_original),
        "rotated_mean": percentile_interval(boot_rotated),
        "paired_difference_mean": percentile_interval(boot_difference),
        "paired_difference_percentage_points": percentile_interval(100 * boot_difference),
        "relative_reduction_in_mean_error": reduction_interval,
    }
    diagnostics = {}
    for key in DIAGNOSTIC_KEYS:
        if all(key in r for r in ordered):
            values = np.array([r[key] for r in ordered], dtype=np.float64)
            diagnostics[key] = {"mean": float(np.mean(values)), "min": float(np.min(values)),
                                "max": float(np.max(values)), "bootstrap_95": percentile_interval(values[indices].mean(axis=1))}
    case, group = ordered[0]["case"], ordered[0]["group_size"]
    return {
        "case": case, "group_size": group,
        "endpoint_role": "primary" if case == "persistent_outlier" and group == 32 else "sensitivity",
        "seed_count": len(ordered), "seed_order": list(seed_order),
        "matched_scale_counts": expected_scale_counts(group),
        "bootstrap_indices_sha256": array_sha256(indices),
        "output": {
            "original_mean": original_mean, "rotated_mean": rotated_mean,
            "paired_difference_mean": float(np.mean(paired_difference)),
            "paired_difference_percentage_points": float(100 * np.mean(paired_difference)),
            "relative_reduction_in_mean_error": 1.0 - rotated_mean / original_mean if original_mean else None,
            "rotation_win_count": int(np.sum(rotated < original)),
            "bootstrap_95": intervals,
            "bootstrap_reduction_defined_draw_count": int(np.sum(valid_reduction)),
        },
        "diagnostics": diagnostics,
    }


def validate_sweep(records: list[dict], retained: dict) -> dict:
    expected = {(case, seed, group) for case in CASES for seed in SEEDS for group in GROUP_SIZES}
    identities = [(r["case"], r["seed"], r["group_size"]) for r in records]
    if len(identities) != len(set(identities)) or set(identities) != expected:
        raise ValueError("sweep must contain all 160 unique expected paired cells")
    relevant = [r for r in retained["records"] if r["case"] in CASES]
    retained_ids = [(r["case"], r["seed"]) for r in relevant]
    expected_reference = {(case, seed) for case in CASES for seed in SEEDS}
    if len(retained_ids) != len(set(retained_ids)) or set(retained_ids) != expected_reference:
        raise ValueError("retained reference identities are duplicated, missing, or unexpected")
    retained_by_id = {(r["case"], r["seed"]): r for r in relevant}
    count = 0
    max_abs_difference = 0.0
    boolean_count = 0
    for row in records:
        expected_counts = expected_scale_counts(row["group_size"])
        for basis in ("original", "rotated"):
            for kind in ("activation", "weight", "total"):
                if row["scale_counts"][f"{kind}_{basis}"] != expected_counts[f"{kind}_per_arm"]:
                    raise ValueError("scale count mismatch")
        if row["full_precision_relative_frobenius_difference"] >= INVARIANCE_LIMIT:
            raise ValueError("change-of-basis tolerance exceeded")
        for value in row.values():
            if isinstance(value, float) and not np.isfinite(value):
                raise ValueError("nonfinite sweep metric")
        if row["group_size"] != 128:
            continue
        baseline = retained_by_id[(row["case"], row["seed"])]
        for key, value in baseline.items():
            if key in ("case", "seed"):
                if row[key] != value:
                    raise ValueError("reference identity mismatch")
            elif isinstance(value, bool):
                boolean_count += 1
                if row[key] != value:
                    raise ValueError(f"reference boolean mismatch: {key}")
            elif isinstance(value, (float, int)):
                count += 1
                max_abs_difference = max(max_abs_difference, abs(row[key] - value))
                if not np.isclose(row[key], value, rtol=REFERENCE_RTOL, atol=REFERENCE_ATOL):
                    raise ValueError(f"g128 reference mismatch: {row['case']}, seed {row['seed']}, {key}")
            elif value is None and row[key] is not None:
                raise ValueError(f"reference null mismatch: {key}")
    for case in CASES:
        for seed in SEEDS:
            rows = [r for r in records if r["case"] == case and r["seed"] == seed]
            if len({json.dumps(r["data_sha256"], sort_keys=True) for r in rows}) != 1:
                raise ValueError("data or rotation changed across group sizes")
    for seed in SEEDS:
        rows = [r for r in records if r["seed"] == seed]
        if len({r["data_sha256"]["rotation"] for r in rows}) != 1 or len({r["data_sha256"]["weight"] for r in rows}) != 1:
            raise ValueError("reference weights or rotations changed across cases")
    return {
        "complete_unique_paired_cells": len(records),
        "matched_scale_counts": True, "finite_metrics": True,
        "full_width_data_and_rotation_reused": True,
        "maximum_full_precision_relative_frobenius_difference": max(r["full_precision_relative_frobenius_difference"] for r in records),
        "g128_reference": {"passed": True, "numeric_comparisons": count, "boolean_comparisons": boolean_count,
                           "rtol": REFERENCE_RTOL, "atol": REFERENCE_ATOL,
                           "maximum_absolute_metric_difference": max_abs_difference},
    }


def export_plot(report: dict, output: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.ticker import PercentFormatter
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 11,
                         "axes.spines.top": False, "axes.spines.right": False,
                         "axes.edgecolor": "#798393", "text.color": "#1c2a3a",
                         "axes.labelcolor": "#1c2a3a", "xtick.color": "#1c2a3a", "ytick.color": "#1c2a3a",
                         "figure.facecolor": "white", "savefig.facecolor": "white", "svg.hashsalt": "hadamard-group-size-v1"})
    settings = {(r["case"], r["group_size"]): r for r in report["summaries"]}
    fig, axes = plt.subplots(1, 2, figsize=(12.8, 6.5), sharey=True, layout="constrained")
    x = np.arange(len(GROUP_SIZES))
    max_high = max(setting["output"]["bootstrap_95"][key][1] for setting in settings.values() for key in ("original_mean", "rotated_mean"))
    for ax, case in zip(axes, CASES):
        if case == "persistent_outlier":
            ax.axvspan(1.8, 2.2, color="#eff3f9", zorder=0)
            ax.text(2, max_high * 1.12, "Primary endpoint\ngroup 32", ha="center", va="top", fontsize=10, color="#596a7c")
        for key, label, color, marker, linestyle in [
            ("original_mean", "Original basis", "#7c8999", "o", "--"),
            ("rotated_mean", "Full-width Hadamard basis", "#285bc2", "s", "-"),
        ]:
            means = np.array([settings[(case, group)]["output"][key] for group in GROUP_SIZES])
            bounds = np.array([settings[(case, group)]["output"]["bootstrap_95"][key] for group in GROUP_SIZES])
            ax.errorbar(x, means, yerr=np.vstack((means - bounds[:, 0], bounds[:, 1] - means)),
                        label=label, color=color, marker=marker, linestyle=linestyle, linewidth=1.7,
                        markersize=6, capsize=4, markerfacecolor="white" if key == "original_mean" else color, zorder=3)
            for position, value in zip(x, means):
                ax.annotate(f"{100 * value:.3f}%", (position, value), xytext=(0, 13 if key == "original_mean" else -21),
                            textcoords="offset points", ha="center", fontsize=9.5, color=color)
        ax.set_title("Gaussian control" if case == "isotropic_gaussian" else "Persistent activation outlier", loc="left", weight="bold", fontsize=13, pad=15)
        ax.set_xticks(x, [f"{group} features\n{expected_scale_counts(group)['total_per_arm']:,} scales" for group in GROUP_SIZES])
        ax.set_xlim(-.25, 3.25)
        ax.set_ylim(0, max_high * 1.2)
        ax.yaxis.set_major_formatter(PercentFormatter(1, decimals=0))
        ax.grid(axis="y", color="#e2e6ec", linewidth=.7, zorder=0)
        ax.tick_params(axis="x", pad=8)
    axes[0].set_ylabel("Squared output error / reference squared norm")
    axes[0].legend(loc="upper left", frameon=False, fontsize=10)
    fig.suptitle("Quantization group size changes the comparison", x=.015, ha="left", fontsize=18, weight="bold")
    fig.supxlabel("Means over 20 paired seeds. Error bars are descriptive 95% whole-seed bootstrap intervals.\nTick labels show total activation and weight scales per arm for one 512-row layer evaluation.\nFull-width transform stays fixed. These are previously inspected synthetic seeds, not a model or hardware benchmark.", fontsize=10)
    for extension in ("png", "svg"):
        fig.savefig(output / f"group-size-results.{extension}", dpi=180, metadata={"Creator": "group_experiment.py"})
    plt.close(fig)


def save_receipt(report: dict, path: Path) -> None:
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    os.replace(temporary, path)


def environment() -> dict:
    thread_environment = {key: os.environ.get(key) for key in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS", "VECLIB_MAXIMUM_THREADS")}
    try:
        from threadpoolctl import threadpool_info
        pools = threadpool_info()
    except ImportError:
        pools = None
    return {"python": platform.python_version(), "numpy": np.__version__, "matplotlib": metadata.version("matplotlib"),
            "platform": platform.platform(), "thread_environment": thread_environment, "threadpools": pools}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT)
    parser.add_argument("--no-plots", action="store_true", help="retain numerical results without exporting figures")
    parser.add_argument("--plot-only", action="store_true", help="render existing group-results.json without recomputing a sweep")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    receipt = args.output / "group-results.json"
    if args.plot_only:
        report = json.loads(receipt.read_text())
        if report["status"] != "complete":
            raise ValueError("only a complete retained sweep can be plotted")
        export_plot(report, args.output)
        return
    if receipt.exists():
        raise FileExistsError("retain the existing group-results.json; use a fresh output directory for a new attempt")
    started = time.perf_counter()
    hashes = source_hashes()
    configuration = {
        "experiment": "hadamard_quantization_group_size_v1", "cases": list(CASES), "seeds": list(SEEDS),
        "group_sizes": list(GROUP_SIZES), "bits": 4,
        "tokens_per_seed": 512, "input_features": 128, "output_features": 64,
        "outlier_channel_multiplier": 32.0, "rotation_seed_offset": 100000,
        "rotation": "unchanged full-width Q = D H / sqrt(128), shared across cases and group sizes",
        "activation_group_axis": "contiguous input features within each row",
        "weight_group_axis": "contiguous input features down each output column",
        "quantizer": "reference maxabs rule, codes -7 through +7, round-to-nearest ties-to-even; zero groups use scale 1",
        "primary_endpoint": {"case": "persistent_outlier", "group_size": 32, "metric": "paired difference in relative squared output error, rotated minus original"},
        "bootstrap": {"draws": BOOTSTRAP_DRAWS, "seed": BOOTSTRAP_SEED, "generator": "NumPy PCG64",
                      "unit": "whole seed record", "shared_indices_across_settings": True,
                      "interval": "descriptive 2.5th and 97.5th percentiles", "quantile_method": "linear"},
        "scale_counts_per_setting": {str(group): expected_scale_counts(group) for group in GROUP_SIZES},
        "configured_process_deadline_seconds": 180,
        "scope": "float64 synthetic error simulation; previously inspected seeds; no model, network, GPU, memory compression, latency or throughput measurement",
    }
    report = {"schema_version": 1, "status": "running", "started_utc": datetime.now(timezone.utc).isoformat(),
              "configuration": configuration, "provenance": {"sha256": hashes, "protocol_path": str(PROTOCOL.relative_to(ROOT)),
                "protocol_issue": "https://github.com/Whyme-Labs/hadamard-exposition/issues/1",
                "configuration_sha256": hashlib.sha256(json.dumps(configuration, sort_keys=True).encode()).hexdigest()},
              "records": [], "summaries": [], "timing": {"definition": "main start through computation, checks and plotting; excludes module imports and final JSON write"}}
    save_receipt(report, receipt)
    try:
        report["phase"] = "preflight"
        report["environment"] = environment()
        env = report["environment"]
        if env["thread_environment"]["OPENBLAS_NUM_THREADS"] != "1" or env["thread_environment"]["OMP_NUM_THREADS"] != "1":
            raise ValueError("run with OPENBLAS_NUM_THREADS=1 and OMP_NUM_THREADS=1")
        if env["threadpools"] is not None and any(p["num_threads"] != 1 for p in env["threadpools"] if p.get("user_api") == "blas"):
            raise ValueError("a loaded BLAS pool has more than one thread")
        for key in ("tokens_per_seed", "input_features", "output_features", "bits", "rotation_seed_offset", "outlier_channel_multiplier"):
            if reference.CONFIG[key] != configuration[key]:
                raise ValueError(f"reference configuration changed: {key}")
        retained = json.loads((ROOT / "results.json").read_text())
        if retained["script_sha256"] != hashes["reference_experiment"]:
            raise ValueError("reference script differs from its retained receipt")
        report["phase"] = "sweep"
        compute_started = time.perf_counter()
        for case in CASES:
            for seed in SEEDS:
                prepared = prepare_seed(seed, case)
                for group_size in GROUP_SIZES:
                    report["active_cell"] = {"case": case, "seed": seed, "group_size": group_size}
                    report["records"].append(run_cell(prepared, seed, case, group_size))
                save_receipt(report, receipt)
        report["timing"]["sweep_seconds"] = time.perf_counter() - compute_started
        report["phase"] = "validation"
        report["validation"] = validate_sweep(report["records"], retained)
        report["phase"] = "bootstrap"
        bootstrap_started = time.perf_counter()
        indices = bootstrap_indices(len(SEEDS))
        report["bootstrap_resampling"] = {"shape": list(indices.shape), "indices_sha256": array_sha256(indices),
                                            "first_three_draws": indices[:3].tolist(), "seed_order": list(SEEDS)}
        for case in CASES:
            for group in GROUP_SIZES:
                rows = [r for r in report["records"] if r["case"] == case and r["group_size"] == group]
                report["summaries"].append(summarize_setting(rows, indices, SEEDS))
        if len({s["bootstrap_indices_sha256"] for s in report["summaries"]}) != 1:
            raise ValueError("resampling indices differ across settings")
        report["timing"]["bootstrap_seconds"] = time.perf_counter() - bootstrap_started
        report["phase"] = "plotting"
        plotting_started = time.perf_counter()
        if not args.no_plots:
            export_plot(report, args.output)
        report["timing"]["figures_generated"] = not args.no_plots
        report["timing"]["plotting_seconds"] = time.perf_counter() - plotting_started
        if source_hashes() != hashes:
            raise ValueError("source, reference or protocol changed during the run")
        report["validation"]["source_reference_and_protocol_unchanged_during_run"] = True
        report["validation"]["shared_whole_seed_bootstrap_indices"] = True
        report["status"] = "complete"
        report.pop("active_cell", None)
        report["phase"] = "complete"
    except (Exception, KeyboardInterrupt) as error:
        report["status"] = "failed"
        report["failure"] = {"type": type(error).__name__, "message": str(error)}
        raise
    finally:
        report["finished_utc"] = datetime.now(timezone.utc).isoformat()
        report["timing"]["total_run_wall_seconds"] = time.perf_counter() - started
        save_receipt(report, receipt)
    for setting in report["summaries"]:
        out = setting["output"]
        print(f"{setting['case']} g={setting['group_size']}: {100*out['original_mean']:.6f}% -> {100*out['rotated_mean']:.6f}%; paired delta {out['paired_difference_percentage_points']:.6f} pp; wins {out['rotation_win_count']}/20")
    print(f"Complete: {len(report['records'])} paired cells; {report['timing']['total_run_wall_seconds']:.3f} seconds")


if __name__ == "__main__":
    main()
