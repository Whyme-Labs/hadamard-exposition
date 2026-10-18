"""Frozen v1 campaign statistics and fixed-work timing, with no data acquisition.

The summaries accept already measured records. They do not authorize test access
or establish full-model parity, graph identity, hardware or resource qualification.
All six arms remain visible when the primary endpoints fail.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
import math
from numbers import Integral, Real
import time
from typing import Any

import numpy as np

from benchmarks.contract import ContractError, aggregate_nll


ARM_IDS = (
    "fp32_original", "fp32_rotated", "w4a32_g32_original",
    "w4a32_g32_rotated", "w4a32_g16_original", "w4a32_g16_rotated",
)
WORKLOADS = {"short": (128, 32), "primary": (512, 128)}
BOOTSTRAP_DRAWS = 10_000
QUALITY_SEED = 20261018
ORDER_SEED = 20261019
TIMING_SEED = 20261020
_TIMES = ("prefill_seconds", "decode_seconds", "request_seconds")


def _integer(value: Any, name: str, minimum: int = 1) -> int:
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, Integral) or value < minimum:
        raise ContractError(f"{name} must be an integer >= {minimum}")
    return int(value)


def _positive(value: Any, name: str) -> float:
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, Real) or not math.isfinite(value) or value <= 0:
        raise ContractError(f"{name} must be finite and positive")
    return float(value)


def _records(values: Sequence[Mapping], name: str) -> list[Mapping]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence) or not values:
        raise ContractError(f"{name} must be a nonempty sequence of records")
    if any(not isinstance(record, Mapping) for record in values):
        raise ContractError(f"{name} must contain mappings")
    return list(values)


def _losses(values: Sequence[Mapping], name: str) -> tuple[list[str], np.ndarray, np.ndarray, dict]:
    records = _records(values, name)
    ids = [record.get("article_id") for record in records]
    if any(not isinstance(identity, str) or not identity for identity in ids) or len(set(ids)) != len(ids):
        raise ContractError(f"{name} needs unique, nonempty article IDs")
    aggregate = aggregate_nll(records)
    return (ids, np.asarray([record["nll_sum"] for record in records], dtype=np.float64),
            np.asarray([record["target_count"] for record in records], dtype=np.float64), aggregate)


def _indices(count: int, seed: int) -> np.ndarray:
    # One array is shared by all arms and metrics within the relevant summary.
    return np.random.Generator(np.random.PCG64(seed)).integers(0, count, size=(BOOTSTRAP_DRAWS, count))


def _interval(point: float, draws: np.ndarray) -> dict:
    if not math.isfinite(point) or not np.isfinite(draws).all():
        raise ContractError("bootstrap estimates must remain finite")
    lower, upper = np.percentile(draws, [2.5, 97.5], method="linear")
    return {"point_estimate": float(point), "lower_95": float(lower), "upper_95": float(upper)}


def _bootstrap_metadata(seed: int, unit: str) -> dict:
    return {"draws": BOOTSTRAP_DRAWS, "seed": seed, "generator": "NumPy PCG64",
            "unit": unit, "shared_indices": True, "percentiles": [2.5, 97.5],
            "quantile_method": "linear"}


def _loss_interval(treatment: tuple, baseline: tuple, indices: np.ndarray) -> dict:
    t_ids, t_loss, t_count, t_total = treatment
    b_ids, b_loss, b_count, b_total = baseline
    if t_ids != b_ids or not np.array_equal(t_count, b_count):
        raise ContractError("paired loss records need the same ordered articles and target counts")
    with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
        t_mean = t_loss[indices].sum(axis=1) / t_count[indices].sum(axis=1)
        b_mean = b_loss[indices].sum(axis=1) / b_count[indices].sum(axis=1)
    result = _interval(t_total["mean_nll"] - b_total["mean_nll"], t_mean - b_mean)
    result["per_article"] = [
        {"article_id": identity, "target_count": int(count),
         "mean_nll_difference": float(t / count - b / count)}
        for identity, t, b, count in zip(t_ids, t_loss, b_loss, t_count, strict=True)
    ]
    return result


def paired_nll_bootstrap(treatment: Sequence[Mapping], baseline: Sequence[Mapping]) -> dict:
    """Paired whole-article loss difference; unequal article lengths stay weighted.

    Both sequences must have the same article order and target counts. This
    generic helper also accepts small conformance fixtures; the campaign summary
    below enforces the frozen 32 articles with 512 targets each.
    """
    t_values, b_values = _losses(treatment, "treatment"), _losses(baseline, "baseline")
    result = _loss_interval(t_values, b_values, _indices(len(t_values[0]), QUALITY_SEED))
    result["bootstrap"] = _bootstrap_metadata(QUALITY_SEED, "whole_article_prefix")
    return result


def summarize_quality(records_by_arm: Mapping[str, Sequence[Mapping]]) -> dict:
    """Report six fixed quality arms and primary gates without claiming parity.

    Full-model logit controls remain a separate prerequisite. The FP32 aggregate
    NLL gate included here cannot substitute for those controls.
    """
    if not isinstance(records_by_arm, Mapping) or set(records_by_arm) != set(ARM_IDS):
        raise ContractError("quality records must contain exactly the six frozen arms")
    values = {arm: _losses(records_by_arm[arm], arm) for arm in ARM_IDS}
    reference = values["fp32_original"]
    for arm, (ids, _, counts, _) in values.items():
        if len(ids) != 32 or ids != reference[0] or not np.all(counts == 512):
            raise ContractError(f"{arm} must preserve all 32 ordered articles with 512 targets each")
    indices = _indices(32, QUALITY_SEED)
    comparisons = {}
    for name, treatment, baseline, role in (
        ("fp32_rotated_minus_original", "fp32_rotated", "fp32_original", "invariance_control"),
        ("g32_rotated_minus_original", "w4a32_g32_rotated", "w4a32_g32_original", "primary"),
        ("g32_rotated_minus_fp32", "w4a32_g32_rotated", "fp32_original", "primary"),
        ("g16_rotated_minus_original", "w4a32_g16_rotated", "w4a32_g16_original", "sensitivity"),
        ("g16_rotated_minus_fp32", "w4a32_g16_rotated", "fp32_original", "sensitivity"),
    ):
        comparisons[name] = {"treatment": treatment, "baseline": baseline, "role": role,
                             **_loss_interval(values[treatment], values[baseline], indices)}
    arms = {}
    for arm, (_, _, _, aggregate) in values.items():
        # Extremely large finite loss may exceed the representable exponential.
        try:
            perplexity = math.exp(aggregate["mean_nll"])
        except OverflowError:
            perplexity = None
        arms[arm] = {**aggregate, "articles": 32, "perplexity": perplexity,
                     "perplexity_overflow": perplexity is None}
    gates = {
        "primary_quality_improvement": comparisons["g32_rotated_minus_original"]["upper_95"] < 0,
        "primary_fp32_margin": comparisons["g32_rotated_minus_fp32"]["upper_95"] <= math.log(1.01),
        "fp32_aggregate_nll_control": abs(comparisons["fp32_rotated_minus_original"]["point_estimate"]) <= 1e-5,
    }
    return {"arms": arms, "comparisons": comparisons, "primary_gates": gates,
            "primary_gates_passed": all(gates.values()), "sensitivity_promoted": False,
            "bootstrap": _bootstrap_metadata(QUALITY_SEED, "whole_article_prefix"),
            "scope": "Selected article-prefix endpoints only; full-model logit parity and campaign readiness are external prerequisites."}


def timing_schedule() -> list[dict]:
    """The fixed 20-block order; callers must launch one fresh worker per arm."""
    generator = np.random.Generator(np.random.PCG64(ORDER_SEED))
    return [{"block_index": index, "article_index": index % 4,
             "arms": generator.permutation(ARM_IDS).tolist()} for index in range(20)]


def _timing_vector(values: Sequence[Real], name: str) -> np.ndarray:
    if isinstance(values, (str, bytes)):
        raise ContractError(f"{name} must be a nonempty sequence of times")
    try:
        result = np.asarray([_positive(value, name) for value in values], dtype=np.float64)
    except TypeError as error:
        raise ContractError(f"{name} must be a nonempty sequence of times") from error
    if not len(result):
        raise ContractError(f"{name} must be a nonempty sequence of times")
    return result


def _timing_interval(treatment: np.ndarray, baseline: np.ndarray, indices: np.ndarray) -> dict:
    if treatment.shape != baseline.shape:
        raise ContractError("timing comparisons must have the same paired block count")
    with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
        # Each resample has the same number of paired blocks, so the mean
        # denominators cancel. Averaging individual time ratios is different.
        ratios = treatment[indices].sum(axis=1) / baseline[indices].sum(axis=1)
    try:
        point = math.fsum(treatment) / math.fsum(baseline)
    except OverflowError as error:
        raise ContractError("aggregate timing must remain finite") from error
    return _interval(point, ratios)


def paired_timing_bootstrap(treatment: Sequence[Real], baseline: Sequence[Real]) -> dict:
    """Ratio of mean times with shared, whole paired-block resampling."""
    t_values, b_values = _timing_vector(treatment, "treatment"), _timing_vector(baseline, "baseline")
    result = _timing_interval(t_values, b_values, _indices(len(t_values), TIMING_SEED))
    result["bootstrap"] = _bootstrap_metadata(TIMING_SEED, "paired_timing_block")
    return result


def _rates(prefill: float, decode: float, workload: str) -> dict:
    prompt_tokens, decode_steps = WORKLOADS[workload]
    return {"prefill_tokens_per_second": prompt_tokens / prefill,
            "decode_tokens_per_second": decode_steps / decode,
            "decode_seconds_per_token": decode / decode_steps}


def summarize_timing(records_by_arm: Mapping[str, Sequence[Mapping]]) -> dict:
    """Report all 20 blocks, both workloads and the prescribed group-32 gates.

    Each record has block_index, article_index, peak_rss_bytes and a workloads
    mapping. Each workload needs the three forward-time metrics and steady RSS.
    Session identity, execution order and graph hashes are checked by the runner.
    """
    if not isinstance(records_by_arm, Mapping) or set(records_by_arm) != set(ARM_IDS):
        raise ContractError("timing records must contain exactly the six frozen arms")
    values, peaks, arms = {}, {}, {}
    for arm in ARM_IDS:
        records = _records(records_by_arm[arm], arm)
        if len(records) != 20:
            raise ContractError(f"{arm} needs all 20 timing blocks")
        values[arm] = {workload: {metric: [] for metric in _TIMES} for workload in WORKLOADS}
        steady = {workload: [] for workload in WORKLOADS}
        arm_peaks = []
        for block_index, record in enumerate(records):
            if (_integer(record.get("block_index"), "block_index", 0) != block_index
                    or _integer(record.get("article_index"), "article_index", 0) != block_index % 4):
                raise ContractError(f"{arm} needs ordered blocks 0..19 and article index block modulo four")
            peak = _integer(record.get("peak_rss_bytes"), "peak_rss_bytes")
            arm_peaks.append(peak)
            workloads = record.get("workloads")
            if not isinstance(workloads, Mapping) or set(workloads) != set(WORKLOADS):
                raise ContractError("every timing worker must retain both short and primary workloads")
            for workload in WORKLOADS:
                measured = workloads[workload]
                if not isinstance(measured, Mapping):
                    raise ContractError("workload metrics must be a mapping")
                times = {metric: _positive(measured.get(metric), metric) for metric in _TIMES}
                if not math.isclose(times["request_seconds"], times["prefill_seconds"] + times["decode_seconds"],
                                    rel_tol=1e-12, abs_tol=1e-12):
                    raise ContractError("request time must equal complete prefill plus cached-call times")
                rss = _integer(measured.get("steady_rss_bytes"), "steady_rss_bytes")
                if rss > peak:
                    raise ContractError("worker high-water RSS cannot be less than observed steady RSS")
                steady[workload].append(rss)
                for metric, seconds in times.items():
                    values[arm][workload][metric].append(seconds)
        peaks[arm] = max(arm_peaks)
        arms[arm] = {"blocks": 20, "maximum_peak_rss_bytes": peaks[arm], "workloads": {}}
        for workload in WORKLOADS:
            vectors = {metric: _timing_vector(samples, metric) for metric, samples in values[arm][workload].items()}
            values[arm][workload] = vectors
            means = {metric: math.fsum(samples) / 20 for metric, samples in vectors.items()}
            arms[arm]["workloads"][workload] = {
                **means, **_rates(means["prefill_seconds"], means["decode_seconds"], workload),
                "mean_steady_rss_bytes": math.fsum(steady[workload]) / 20,
                "maximum_steady_rss_bytes": max(steady[workload]),
            }
    indices = _indices(20, TIMING_SEED)
    comparisons = {}
    for name, treatment, baseline, role in (
        ("fp32", "fp32_rotated", "fp32_original", "invariance_control"),
        ("g32", "w4a32_g32_rotated", "w4a32_g32_original", "primary"),
        ("g16", "w4a32_g16_rotated", "w4a32_g16_original", "sensitivity"),
    ):
        comparisons[name] = {
            "treatment": treatment, "baseline": baseline, "role": role,
            "maximum_peak_rss_ratio": peaks[treatment] / peaks[baseline],
            "workloads": {workload: {
                metric: _timing_interval(values[treatment][workload][metric], values[baseline][workload][metric], indices)
                for metric in _TIMES} for workload in WORKLOADS},
        }
    primary = comparisons["g32"]
    gates = {f"primary_{metric}_overhead": primary["workloads"]["primary"][metric]["upper_95"] <= 1.05
             for metric in _TIMES}
    gates["maximum_peak_rss_overhead"] = primary["maximum_peak_rss_ratio"] <= 1.05
    return {"arms": arms, "comparisons": comparisons, "primary_gates": gates,
            "primary_gates_passed": all(gates.values()), "sensitivity_promoted": False,
            "bootstrap": _bootstrap_metadata(TIMING_SEED, "paired_timing_block"),
            "aggregation": "ratio_of_mean_treatment_time_to_mean_baseline_time",
            "scope": "Forward-call and observed worker-memory endpoints; runner resource and artifact checks remain external prerequisites."}


def _elapsed(start: Real, stop: Real) -> float:
    if any(isinstance(value, (bool, np.bool_)) or not isinstance(value, Real) or not math.isfinite(value)
           for value in (start, stop)):
        raise ContractError("the monotonic clock must return finite numbers")
    return _positive(stop - start, "elapsed seconds")


def run_request(step: Callable, token_ids: Sequence[int], workload: str,
                *, clock: Callable[[], float] = time.perf_counter) -> dict:
    """Run one fresh-cache request with fixed continuation and complete-call times.

    ``step(input_ids, cache)`` receives int64 [1, sequence] IDs and returns
    ``(logits, next_cache)``. Its entire call, including the ONNX session.run and
    online transforms, lies inside the timer. The adapter must return all graph
    outputs and use the supplied cache; no model generation/EOS logic is used.
    Token preparation and Python result inspection are outside forward latency.
    """
    if workload not in WORKLOADS:
        raise ContractError("workload must be short or primary")
    try:
        tokens = list(token_ids)
    except TypeError as error:
        raise ContractError("token IDs must be a sequence") from error
    if len(tokens) != 640:
        raise ContractError("timing requires the frozen 640-token prefix")
    tokens = [_integer(value, "token ID", 0) for value in tokens]
    if max(tokens) > np.iinfo(np.int64).max:
        raise ContractError("token IDs must fit int64 graph inputs")
    ids = np.asarray(tokens, dtype=np.int64)[None, :]
    ids.setflags(write=False)
    prompt_tokens, decode_steps = WORKLOADS[workload]
    wall_start = clock()

    def forward(current_ids: np.ndarray, cache: Any) -> tuple[Any, float]:
        started = clock()
        result = step(current_ids, cache)
        elapsed = _elapsed(started, clock())
        if not isinstance(result, tuple) or len(result) != 2 or result[1] is None:
            raise ContractError("each complete model step must return (logits, next_cache)")
        return result[1], elapsed

    cache, prefill = forward(ids[:, :prompt_tokens], None)
    decode_times = []
    for index in range(prompt_tokens, prompt_tokens + decode_steps):
        cache, elapsed = forward(ids[:, index:index + 1], cache)
        decode_times.append(elapsed)
    wall = _elapsed(wall_start, clock())
    decode = math.fsum(decode_times)
    return {"prefill_seconds": prefill, "decode_seconds": decode,
            "request_seconds": math.fsum([prefill, decode]),
            "request_wall_seconds": wall, "prompt_tokens": prompt_tokens,
            "decode_steps": decode_steps, **_rates(prefill, decode, workload)}


def run_timing_worker(step: Callable, token_ids: Sequence[int], rss_reader: Callable[[], int],
                      *, clock: Callable[[], float] = time.perf_counter) -> dict:
    """Run short then primary, each with one warmup and one measured request.

    Call this once in each newly loaded arm worker. The runner records session
    load time separately, obtains the worker's OS peak RSS and enforces limits.
    Wall fields include warmups and RSS observation for feasibility accounting;
    the endpoint time fields contain only complete measured forward calls.
    """
    worker_start = clock()
    workloads = {}
    for workload in WORKLOADS:
        workload_start = clock()
        warmup = run_request(step, token_ids, workload, clock=clock)
        steady = _integer(rss_reader(), "steady_rss_bytes")
        measured = run_request(step, token_ids, workload, clock=clock)
        workloads[workload] = {
            **measured, "steady_rss_bytes": steady,
            "warmup_request_seconds": warmup["request_seconds"],
            "warmup_request_wall_seconds": warmup["request_wall_seconds"],
            "workload_wall_seconds": _elapsed(workload_start, clock()),
        }
    return {"workloads": workloads, "timing_worker_wall_seconds": _elapsed(worker_start, clock())}
