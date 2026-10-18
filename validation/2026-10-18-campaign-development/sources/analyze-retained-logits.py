"""Describe the two already-retained cached comparisons without any model call."""

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--evidence", type=Path, required=True)
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
source = args.evidence / "cache-comparison-slices.npz"
derivation = json.loads((args.evidence / "slice-derivation.json").read_text())
source_sha = sha(source)
if source_sha != derivation["npz_sha256"]:
    raise ValueError("The retained slice archive differs from its provenance record")
result = {"schema_version": "hadamard-retained-logit-analysis.v1", "model_calls": 0,
    "campaign_ready": False, "gate_repaired": False, "quality_test_accessed": False,
    "source_npz_sha256": source_sha, "analysis_source_sha256": sha(Path(__file__)),
    "maximum_absolute_gate": 0.001,
    "note": "All extra metrics describe the same two saved development outputs; none replaces a frozen acceptance criterion.",
    "articles": []}
with np.load(source, allow_pickle=False) as saved:
    if set(saved.files) != {f"article{i}_{case}" for i in (0, 1) for case in ("full", "cached")}:
        raise ValueError("Exactly the two original full-last and cached arrays are required")
    for item in derivation["arrays"]:
        array = saved[item["key"]]
        if (list(array.shape) != item["shape"] or array.dtype.str != item["dtype"]
                or hashlib.sha256(array.tobytes(order="C")).hexdigest() != item["array_c_order_sha256"]):
            raise ValueError("An array differs from its original-slice identity")
    for index in (0, 1):
        full32, cached32 = saved[f"article{index}_full"].reshape(-1), saved[f"article{index}_cached"].reshape(-1)
        if (full32.dtype != np.float32 or cached32.dtype != np.float32
                or full32.size != 50304 or cached32.size != 50304
                or not np.isfinite(full32).all() or not np.isfinite(cached32).all()
                or np.any(full32 <= 0) or np.any(cached32 <= 0)):
            raise ValueError("The observed finite positive FP32 logit domain differs")
        full, cached = full32.astype(np.float64), cached32.astype(np.float64)
        delta = cached - full
        absolute = np.abs(delta)
        ids = np.arange(full.size)
        full_order, cached_order = np.lexsort((ids, -full)), np.lexsort((ids, -cached))
        ulps = np.abs(cached32.view(np.uint32).astype(np.int64) - full32.view(np.uint32).astype(np.int64))
        maximum = float(absolute.max())
        maxima = np.flatnonzero(absolute == maximum)
        result["articles"].append({"article_index": index, "logit_count": int(full.size),
            "above_absolute_gate": int(np.count_nonzero(absolute > 0.001)),
            "exactly_equal": int(np.count_nonzero(delta == 0)),
            "maximum_absolute_error": maximum, "median_absolute_error": float(np.median(absolute)),
            "relative_frobenius_error": float(np.linalg.norm(delta) / np.linalg.norm(full)),
            "full_minimum": float(full.min()), "full_maximum": float(full.max()),
            "full_mean": float(full.mean()), "full_standard_deviation": float(full.std()),
            "maximum_ulp_distance": int(ulps.max()),
            "best_uniform_shift_maximum_error": float((delta.max() - delta.min()) / 2),
            "mean_centered_maximum_error": float(np.max(np.abs(delta - delta.mean()))),
            "full_top_token": int(full_order[0]), "cached_top_token": int(cached_order[0]),
            "same_top_20_order": bool(np.array_equal(full_order[:20], cached_order[:20])),
            "maximum_error_tokens": [{"token_id": int(i), "full": float(full[i]),
                "cached": float(cached[i]), "signed_error": float(delta[i]), "ulp_distance": int(ulps[i])}
                for i in maxima]})
if sha(source) != source_sha:
    raise ValueError("Retained slices changed during analysis")
with args.output.open("x", encoding="utf-8") as stream:
    json.dump(result, stream, indent=2, sort_keys=True, allow_nan=False)
    stream.write("\n")
print(json.dumps({"articles": result["articles"], "model_calls": 0}))
