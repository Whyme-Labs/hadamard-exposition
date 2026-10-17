#!/usr/bin/env python3
"""Paired synthetic experiment for the Hadamard and quantization exposition.

This is an error simulation in float64, not an integer inference benchmark.
No model, corpus, GPU, network, or external service is used.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import sys
from fractions import Fraction

os.environ.setdefault("MPLCONFIGDIR", "/tmp/hadamard-exposition-matplotlib")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")

import numpy as np

CONFIG = {
    "schema_version": 1,
    "experiment": "hadamard_quantization_synthetic_v1",
    "seeds": list(range(20)),
    "rotation_seed_offset": 100000,
    "tokens_per_seed": 512,
    "input_features": 128,
    "output_features": 64,
    "bits": 4,
    "outlier_channel_multiplier": 32.0,
    "arithmetic": "float64 simulation",
    "quantizer": "per-vector maxabs, symmetric integers -7 through +7, round-to-nearest ties-to-even",
    "activation_scale_axis": "one scale per row, over input features",
    "weight_scale_axis": "one scale per output column, over input features",
    "rotation": "Q = D H / sqrt(n), D diagonal with independent Rademacher signs, H Sylvester",
    "cases": ["isotropic_gaussian", "persistent_outlier", "quantizer_grid"],
    "primary_metric": "linear_output_relative_squared_error",
    "aggregation": "arithmetic mean over 20 seed-level relative squared errors",
    "scope": "synthetic linear layers; no language model quality, throughput, latency or memory measurements",
}

LABELS = {
    "isotropic_gaussian": "Gaussian",
    "persistent_outlier": "Persistent outlier",
    "quantizer_grid": "Quantizer grid",
}


def hadamard(n: int) -> np.ndarray:
    """Construct an unnormalized Sylvester matrix with exact integer entries."""
    if n < 1 or n & (n - 1):
        raise ValueError("n must be a positive power of two")
    h = np.ones((1, 1), dtype=np.int64)
    while h.shape[0] < n:
        h = np.block([[h, h], [h, -h]])
    return h


def fwht_rows(x: np.ndarray) -> np.ndarray:
    """Normalized Walsh-Hadamard transform along the last dimension."""
    z = np.array(x, dtype=np.float64, copy=True)
    n = z.shape[-1]
    if n < 1 or n & (n - 1):
        raise ValueError("last dimension must be a positive power of two")
    stride = 1
    while stride < n:
        blocks = z.reshape(*z.shape[:-1], -1, 2 * stride)
        left = blocks[..., :stride].copy()
        right = blocks[..., stride:].copy()
        blocks[..., :stride] = left + right
        blocks[..., stride:] = left - right
        stride *= 2
    return z / np.sqrt(n)


def quantize(a: np.ndarray, axis: int, bits: int = 4) -> np.ndarray:
    """Return dequantized floats. Scales are derived identically in both arms."""
    if bits < 2:
        raise ValueError("bits must be at least 2")
    maximum = (1 << (bits - 1)) - 1
    absmax = np.max(np.abs(a), axis=axis, keepdims=True)
    scale = np.where(absmax == 0, 1.0, absmax / maximum)
    code = np.clip(np.rint(a / scale), -maximum, maximum)
    return code * scale


def relative_squared_error(actual: np.ndarray, expected: np.ndarray) -> float:
    denominator = float(np.sum(expected * expected))
    if denominator == 0:
        raise ValueError("relative error is undefined for a zero reference")
    return float(np.sum((actual - expected) ** 2) / denominator)


def peak_to_rms(x: np.ndarray) -> float:
    return float(np.mean(np.max(np.abs(x), axis=1) / np.sqrt(np.mean(x * x, axis=1))))


def matrices(seed: int, case: str) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    n, tokens, outputs = [CONFIG[k] for k in ["input_features", "tokens_per_seed", "output_features"]]
    rng = np.random.Generator(np.random.PCG64(seed))
    x = rng.standard_normal((tokens, n))
    w = rng.standard_normal((n, outputs)) / np.sqrt(n)
    if case == "persistent_outlier":
        x[:, 0] *= CONFIG["outlier_channel_multiplier"]
    elif case == "quantizer_grid":
        # Integer data with an explicit maximum of 7 in every scale group.
        # The baseline is exactly representable by this quantizer.
        grid = np.random.Generator(np.random.PCG64(seed + 200000))
        x = grid.integers(-7, 8, size=(tokens, n)).astype(np.float64)
        w = grid.integers(-7, 8, size=(n, outputs)).astype(np.float64)
        x[:, 0] = 7.0
        w[0, :] = 7.0
    elif case != "isotropic_gaussian":
        raise ValueError(f"unknown case {case}")
    rotation_rng = np.random.Generator(np.random.PCG64(seed + CONFIG["rotation_seed_offset"]))
    signs = rotation_rng.choice(np.array([-1.0, 1.0]), size=n)
    q = signs[:, None] * hadamard(n).astype(np.float64) / np.sqrt(n)
    return x, w, q, signs


def run_seed(seed: int, case: str) -> dict:
    x, w, q, signs = matrices(seed, case)
    y = x @ w
    xr, wr = x @ q, q.T @ w
    xhat, what = quantize(x, 1), quantize(w, 0)
    xrhat, wrhat = quantize(xr, 1), quantize(wr, 0)
    original_error = relative_squared_error(xhat @ what, y)
    rotated_error = relative_squared_error(xrhat @ wrhat, y)
    invariance = np.sqrt(relative_squared_error(xr @ wr, y))
    fast_difference = float(np.max(np.abs(fwht_rows(x * signs) - xr)))
    if invariance > 2e-13:
        raise AssertionError(f"change-of-basis failed: {invariance}")
    if fast_difference > 2e-12:
        raise AssertionError(f"fast transform differs: {fast_difference}")
    if not np.allclose(xr @ q.T, x, rtol=2e-13, atol=2e-12):
        raise AssertionError("round-trip failed")
    if case == "quantizer_grid":
        if not np.array_equal(xhat, x) or not np.array_equal(what, w):
            raise AssertionError("grid baseline must be exactly representable")
        if original_error != 0.0 or rotated_error <= 0.0:
            raise AssertionError("grid case must be a strict counterexample")
    return {
        "case": case,
        "seed": seed,
        "activation_relative_squared_error_original": relative_squared_error(xhat, x),
        "activation_relative_squared_error_rotated": relative_squared_error(xrhat @ q.T, x),
        "weight_relative_squared_error_original": relative_squared_error(what, w),
        "weight_relative_squared_error_rotated": relative_squared_error(q @ wrhat, w),
        "activation_only_output_relative_squared_error_original": relative_squared_error(xhat @ w, y),
        "activation_only_output_relative_squared_error_rotated": relative_squared_error(xrhat @ wr, y),
        "linear_output_relative_squared_error_original": original_error,
        "linear_output_relative_squared_error_rotated": rotated_error,
        "mean_activation_peak_to_rms_original": peak_to_rms(x),
        "mean_activation_peak_to_rms_rotated": peak_to_rms(xr),
        "full_precision_relative_frobenius_difference": float(invariance),
        "fast_transform_max_absolute_difference": fast_difference,
        "output_error_ratio_rotated_over_original": rotated_error / original_error if original_error else None,
        "rotated_output_error_lower": rotated_error < original_error,
    }


def summarize(records: list[dict]) -> dict:
    summary = {}
    for case in CONFIG["cases"]:
        rows = [r for r in records if r["case"] == case]
        metrics = {}
        for key in rows[0]:
            if key in {"case", "seed", "rotated_output_error_lower"}:
                continue
            values = [r[key] for r in rows if r[key] is not None]
            if values:
                metrics[key] = {
                    "mean": float(np.mean(values)),
                    "median": float(np.median(values)),
                    "min": float(np.min(values)),
                    "max": float(np.max(values)),
                }
        summary[case] = {
            "seeds": len(rows),
            "rotation_output_wins": sum(r["rotated_output_error_lower"] for r in rows),
            "metrics": metrics,
        }
    return summary


def exact_counterexample() -> dict:
    """Independent rational arithmetic: a smaller peak can still mean more error."""
    x = [Fraction(v) for v in [7, 1, 1, 0]]
    h = [[1, 1, 1, 1], [1, -1, 1, -1], [1, 1, -1, -1], [1, -1, -1, 1]]
    z = [sum(x[i] * h[i][j] for i in range(4)) / 2 for j in range(4)]
    scale = max(abs(v) for v in z) / 7
    zhat = [round(v / scale) * scale for v in z]
    numerator = sum((a - b) ** 2 for a, b in zip(zhat, z))
    denominator = sum(v * v for v in x)
    relative_error = numerator / denominator
    assert relative_error == Fraction(11, 3332)
    assert max(abs(v) for v in z) < max(abs(v) for v in x)
    return {"original": [str(v) for v in x], "rotated": [str(v) for v in z],
            "dequantized_rotated": [str(v) for v in zhat],
            "original_relative_squared_error": 0,
            "rotated_relative_squared_error_exact": str(relative_error),
            "rotated_relative_squared_error": float(relative_error),
            "peak_original": 7, "peak_rotated": 4.5}


def export_plots(result: dict, output: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.ticker import PercentFormatter

    plt.rcParams.update({
        "font.family": "DejaVu Sans", "font.size": 11,
        "axes.spines.top": False, "axes.spines.right": False,
        "axes.edgecolor": "#798393", "text.color": "#1c2a3a",
        "axes.labelcolor": "#1c2a3a", "xtick.color": "#1c2a3a",
        "ytick.color": "#1c2a3a", "figure.facecolor": "white",
        "savefig.facecolor": "white", "svg.hashsalt": "hadamard-exposition-v1",
    })
    colors = {"original": "#7c8999", "rotated": "#285bc2"}
    fig, axes = plt.subplots(1, 2, figsize=(12.6, 5.4), layout="constrained")
    for ax, metric, heading in zip(
        axes,
        ["activation_relative_squared_error", "linear_output_relative_squared_error"],
        ["Activation reconstruction error", "Linear output error, both operands quantized"],
    ):
        for side, offset, label in [("original", -.18, "Original basis"), ("rotated", .18, "Hadamard basis")]:
            means = [result["summary"][c]["metrics"][f"{metric}_{side}"]["mean"] for c in CONFIG["cases"]]
            ax.bar(np.arange(3) + offset, means, width=.32, color=colors[side], label=label, zorder=2)
            for i, case in enumerate(CONFIG["cases"]):
                values = [r[f"{metric}_{side}"] for r in result["records"] if r["case"] == case]
                jitter = np.linspace(-.08, .08, len(values))
                ax.scatter(i + offset + jitter, values, color="#1c2a3a", alpha=.35,
                           marker="o" if side == "original" else "x", s=10, linewidths=.6, zorder=3)
            for i, value in enumerate(means):
                ax.annotate(f"{100 * value:.2f}%", (i + offset, value), xytext=(0, 7),
                            textcoords="offset points", ha="center", va="bottom", fontsize=10)
        ax.set_xticks(range(3), [LABELS[c] for c in CONFIG["cases"]])
        ax.yaxis.set_major_formatter(PercentFormatter(1, decimals=0))
        ax.set_ylim(bottom=0)
        ax.set_ylim(top=ax.get_ylim()[1] * 1.15)
        ax.set_title(heading, loc="left", fontsize=12, pad=15, weight="bold")
        ax.grid(axis="y", color="#e2e6ec", linewidth=.7, zorder=0)
        ax.set_ylabel("Squared error / reference squared norm")
    axes[0].legend(loc="upper right", frameon=False, fontsize=10)
    fig.suptitle("The same rotation helps, has little effect, or hurts", x=.02, ha="left", fontsize=17, weight="bold")
    fig.supxlabel("Synthetic data. Twenty paired seeds per case. Bars are means; marks show every seed.\nFour-bit symmetric maxabs quantization, simulated in float64. No model accuracy or speed is measured.", fontsize=10)
    for extension in ["png", "svg"]:
        fig.savefig(output / f"quantization-results.{extension}", dpi=180, metadata={"Creator": "experiment.py"})
    plt.close(fig)

    x, _, q, _ = matrices(0, "persistent_outlier")
    before, after = x[0], x[0] @ q
    fig, axes = plt.subplots(2, 1, figsize=(12, 5.6), sharex=True, sharey=True, layout="constrained")
    for ax, data, color, title in zip(axes, [before, after], [colors["original"], colors["rotated"]],
                                    ["Original coordinates", "After randomized Hadamard transform"]):
        ax.bar(np.arange(len(data)), data, color=color, width=.8)
        ax.axhline(0, color="#798393", linewidth=.6)
        ax.set_title(title, loc="left", fontsize=12, weight="bold")
        ax.set_ylabel("Coordinate value")
        ax.set_xlim(-1, len(data))
        ax.grid(axis="y", color="#e2e6ec", linewidth=.7)
    axes[1].set_xlabel("Coordinate index")
    fig.suptitle("A change of coordinates preserves energy", x=.02, ha="left", fontsize=17, weight="bold")
    fig.supxlabel("Seed 0, first vector of the persistent outlier case. Both panels use the same vertical scale.\nThis fixed example is illustrative; the full paired experiment includes all 20 seeds.", fontsize=10)
    for extension in ["png", "svg"]:
        fig.savefig(output / f"coordinate-example.{extension}", dpi=180, metadata={"Creator": "experiment.py"})
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--no-plots", action="store_true", help="only NumPy is required")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    h = hadamard(CONFIG["input_features"])
    exact_orthogonality = np.array_equal(h @ h.T, CONFIG["input_features"] * np.eye(CONFIG["input_features"], dtype=np.int64))
    if not exact_orthogonality:
        raise AssertionError("integer Hadamard identity failed")
    if not np.array_equal(quantize(np.zeros((2, 3)), 1), np.zeros((2, 3))):
        raise AssertionError("zero quantizer group failed")
    records = [run_seed(seed, case) for case in CONFIG["cases"] for seed in CONFIG["seeds"]]
    result = {
        "configuration": CONFIG,
        "environment": {"python": platform.python_version(), "numpy": np.__version__, "platform": platform.platform()},
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "validation": {"integer_hadamard_identity": exact_orthogonality,
                       "zero_scale_group": True,
                       "grid_exact_and_rotation_worse_all_seeds": True,
                       "full_precision_invariance_all_seeds": True,
                       "dense_and_fast_transform_agree_all_seeds": True,
                       "maximum_full_precision_relative_frobenius_difference": max(r["full_precision_relative_frobenius_difference"] for r in records)},
        "summary": summarize(records),
        "exact_counterexample": exact_counterexample(),
        "records": records,
    }
    (args.output / "results.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    if not args.no_plots:
        export_plots(result, args.output)
    for case, values in result["summary"].items():
        m = values["metrics"]
        print(f"{case}: output {100*m['linear_output_relative_squared_error_original']['mean']:.6f}% -> {100*m['linear_output_relative_squared_error_rotated']['mean']:.6f}%; rotation wins {values['rotation_output_wins']}/{values['seeds']}")
    print(f"Full-precision maximum relative difference: {result['validation']['maximum_full_precision_relative_frobenius_difference']:.3e}")


if __name__ == "__main__":
    main()
