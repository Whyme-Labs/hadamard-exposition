#!/usr/bin/env python3
"""One pinned checkpoint acquisition using the unchanged benchmark downloader."""

import argparse
from dataclasses import asdict
from pathlib import Path
import resource
import sys
import time
from urllib.request import build_opener

sys.dont_write_bytecode = True
from run_audit import (
    ROOT, BODY_LIMIT, CHECKPOINT_BYTES, CHECKPOINT_SHA256, file_identity, numpy_startup_evidence, read_json,
    utc_now, verify_registration, write_json,
)
from benchmarks.qualify import _publish_worker_identity


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--review", type=Path, required=True)
    parser.add_argument("--publication", type=Path, required=True)
    args = parser.parse_args()
    started = time.monotonic()
    result = {"schema_version": "hadamard-operator-checkpoint.v1", "status": "failed",
              "started_utc": utc_now(), "model_calls": 0, "candidate_operator_calls": 0,
              "dependency_received_bytes": 0, "campaign_ready": False, "inputs_unchanged": False,
              "download_body_limit_bytes": BODY_LIMIT, "download_attempts": 0, "file": {}}
    budget = None
    try:
        result["worker_identity"] = _publish_worker_identity(args.output)
        result["registration_before"] = verify_registration(args.review, args.publication)
        # model_acquire imports contract/NumPy, so load it after identity publication.
        from benchmarks.model_acquire import (
            _DownloadBudget, _PinnedRedirectHandler, _download_one, allowed_artifacts,
        )
        result["numpy_import_self_checks"] = numpy_startup_evidence(sys.modules["numpy"])
        budget = _DownloadBudget(BODY_LIMIT)
        specs = [s for s in allowed_artifacts(read_json(ROOT / "benchmarks/model-benchmark-v1.json"))
                 if s.kind == "model" and s.filename == "model.safetensors"]
        if (len(specs) != 1 or specs[0].expected_bytes != CHECKPOINT_BYTES
                or specs[0].expected_sha256 != CHECKPOINT_SHA256):
            raise ValueError("The one pinned checkpoint allowlist differs")
        spec = specs[0]
        result["file"] = asdict(spec)
        write_json(args.output / "start.json", result)
        result["download_attempts"] += 1
        _download_one(spec, args.output, budget, started + 600,
                      build_opener(_PinnedRedirectHandler()).open, result["file"])
        result["checkpoint"] = file_identity(args.output / spec.relative_path)
        if result["checkpoint"] != {"bytes": CHECKPOINT_BYTES, "sha256": CHECKPOINT_SHA256}:
            raise ValueError("The acquired checkpoint identity differs")
        result["registration_after"] = verify_registration(args.review, args.publication)
        if result["registration_after"] != result["registration_before"]:
            raise ValueError("Acquisition source/registration inputs changed")
        result["inputs_unchanged"] = True
        result["status"] = "passed"
    except Exception as error:
        result["error"] = {"type": type(error).__name__,
                           "message": str(error) if isinstance(error, ValueError)
                           else "Checkpoint acquisition failed; signed network URLs are not retained"}
    result.update(downloaded_bytes=budget.used if budget is not None else 0, finished_utc=utc_now(),
                  elapsed_seconds=time.monotonic() - started,
                  peak_worker_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024)
    write_json(args.output / "worker-result.json", result)
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
