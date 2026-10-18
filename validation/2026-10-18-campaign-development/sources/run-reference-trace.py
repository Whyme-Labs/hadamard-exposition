"""Run the reviewed reference trace after unchanged host and source gates."""

import argparse
import fcntl
import json
from pathlib import Path
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from benchmarks.campaign_guard import (
    MANIFEST, directory_bytes, new_directory, preflight, run_bounded_task,
    sha256_file, source_hashes, utc_now, write_json,
)
from benchmarks.run_model import verify_review_commit


EVIDENCE = ROOT / "validation/2026-10-18-campaign-development"
ORIGINAL = ROOT / "build/model-campaign-development-002"
DIAGNOSTIC_SOURCES = (
    "diagnostic-plan.md", "sources/reference-trace-worker.py",
    "sources/run-reference-trace.py", "sources/release-reference-cache.py",
)
SECONDS = 120
RSS_BYTES = 6 * 1024**3
OUTPUT_BYTES = 64 * 1024**2


def diagnostic_hashes():
    return {name: sha256_file(EVIDENCE / name) for name in DIAGNOSTIC_SOURCES}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--review", type=Path, required=True)
    parser.add_argument("--maintenance", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.absolute()
    if (not output.is_relative_to(ROOT / "build") or output.is_relative_to(ORIGINAL)
            or output.parent.resolve() != output.parent):
        raise ValueError("Use a new concrete output directory under build, outside the original run")
    output = new_directory(output)
    started = time.monotonic()
    before, diagnostic_before = source_hashes(), diagnostic_hashes()
    review_sha = sha256_file(args.review)
    record = {"schema_version": "hadamard-reference-trace-run.v1", "status": "blocked",
        "started_utc": utc_now(), "original_campaign": str(ORIGINAL.relative_to(ROOT)),
        "campaign_ready": False, "control_repaired": False, "quality_test_accessed": False,
        "source_sha256_before": before, "diagnostic_sha256_before": diagnostic_before,
        "review_sha256": review_sha, "deadline_seconds": SECONDS,
        "worker_rss_limit_bytes": RSS_BYTES, "new_output_limit_bytes": OUTPUT_BYTES,
        "model_calls": 0, "errors": []}
    try:
        with (ROOT / "build/model-campaign.process-lock").open("a+b") as process_lock:
            fcntl.flock(process_lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            review = json.loads(args.review.read_text())
            if (review.get("schema_version") != "hadamard-reference-diagnostic-review.v1"
                    or review.get("specification") != "passed" or review.get("standards") != "passed"
                    or review.get("diagnostic_source_sha256") != diagnostic_before
                    or review.get("benchmark_source_sha256") != before):
                raise ValueError("Both diagnostic reviews must bind these exact source bytes")
            verify_review_commit(json.loads((ORIGINAL / "review.json").read_text()), before)
            if sha256_file(ORIGINAL / "campaign.json") != review.get("original_campaign_sha256"):
                raise ValueError("The reviewed original campaign differs")
            maintenance = json.loads(args.maintenance.read_text())
            if (maintenance.get("status") != "completed" or maintenance.get("errors")
                    or maintenance.get("scope_roots") != ["build/model-campaign-development-002"]
                    or maintenance.get("script_sha256_before") != diagnostic_before["sources/release-reference-cache.py"]
                    or maintenance.get("script_sha256_after") != diagnostic_before["sources/release-reference-cache.py"]
                    or maintenance.get("metadata_unchanged_after_advice") is not True
                    or maintenance.get("data_writes") != 0 or maintenance.get("deletions") != 0
                    or sha256_file(args.maintenance.parent / "files.jsonl") != maintenance.get("files_journal_sha256")):
                raise ValueError("The single scoped maintenance pass lacks valid complete evidence")
            record["maintenance_receipt_sha256"] = sha256_file(args.maintenance)
            host = preflight(json.loads(MANIFEST.read_text()), disk_path=output)
            write_json(output / "preflight.json", host)
            if host["status"] != "passed":
                raise ValueError("The unchanged frozen host preflight did not pass")
            command = [str(ROOT / "build/recovered-envs-002/converter/bin/python"),
                str(EVIDENCE / "sources/reference-trace-worker.py"),
                "--original-campaign", str(ORIGINAL), "--output", str(output / "worker")]
            record["model_calls"] = None
            task = run_bounded_task(command, output / "worker", deadline=started + SECONDS,
                memory_limit=RSS_BYTES, campaign_root=output, cache_limit=OUTPUT_BYTES,
                env={"HF_HOME": str(output / "library-cache"),
                     "HF_HUB_CACHE": str(output / "library-cache/hub"),
                     "TRANSFORMERS_CACHE": str(output / "library-cache/transformers")})
            record["task_status"] = task["status"]
            record["task_receipt_sha256"] = sha256_file(output / "worker/task-receipt.json")
            record["model_calls"] = (task.get("worker") or {}).get("model_calls")
            if task["status"] != "passed":
                raise ValueError("The bounded diagnostic worker failed; retain its original task receipt")
            record["status"] = "passed"
    except Exception as error:
        record["errors"].append({"type": type(error).__name__, "message": str(error)})
        traceback.print_exc()
    finally:
        record["inputs_unchanged"] = False
        record["new_output_bytes_before_final_receipt"] = None
        try:
            record["source_sha256_after"] = source_hashes()
            record["diagnostic_sha256_after"] = diagnostic_hashes()
            record["inputs_unchanged"] = (before == record["source_sha256_after"]
                and diagnostic_before == record["diagnostic_sha256_after"]
                and review_sha == sha256_file(args.review))
            record["new_output_bytes_before_final_receipt"] = directory_bytes(output)
        except Exception as error:
            record["errors"].append({"type": type(error).__name__,
                "message": "Final identity/output observation failed: " + str(error)})
        record["elapsed_seconds"] = time.monotonic() - started
        if (not record["inputs_unchanged"] or record["elapsed_seconds"] >= SECONDS
                or record["new_output_bytes_before_final_receipt"] is None
                or record["new_output_bytes_before_final_receipt"] > OUTPUT_BYTES - 64 * 1024):
            record["status"] = "blocked"
            record["errors"].append({"type": "FinalizationError",
                "message": "Source or review changed, or diagnostic time/output allowance exceeded"})
        record["finished_utc"] = utc_now()
        if len(json.dumps(record, indent=2, sort_keys=True).encode()) + 1 > 64 * 1024:
            raise ValueError("Final receipt exceeds its reserved 64 KiB allowance")
        write_json(output / "trace-run.json", record)
    print(json.dumps({key: record[key] for key in
        ("status", "model_calls", "elapsed_seconds", "quality_test_accessed", "errors")}))
    return 0 if record["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
