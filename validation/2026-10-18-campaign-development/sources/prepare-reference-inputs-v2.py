"""Reacquire pinned bytes and copy retained evidence for the reviewed trace.

This does not recreate omitted logits, parse datasets or call a model.
New acquisition provenance remains separate from copied original receipts.
"""

import argparse
import fcntl
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tarfile
import time
import traceback

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from benchmarks.campaign_guard import (MANIFEST, bind_files, directory_bytes,
    new_directory, run_bounded_task, sha256_file, source_hashes, utc_now,
    verify_bound_files, write_json)
from benchmarks.qualify import _environment, _memory_preflight
from benchmarks.run_model import verify_review_commit
from benchmarks.model_acquire import verify_acquisition

EVIDENCE = ROOT / "validation/2026-10-18-campaign-development"
RETAINED = EVIDENCE / "campaign-attempt-2"
INPUTS = ROOT / "build/reference-diagnostic-inputs-001"
DEPENDENCIES = ROOT / "build/diagnostic-environment-recovery-001/qualification.json"
VENVS = ROOT / "build/diagnostic-environments-001"
SOURCES = ("diagnostic-plan-v2.md", "sources/reference-trace-worker-v2.py",
    "sources/run-reference-trace-v2.py", "sources/prepare-reference-inputs-v2.py",
    "sources/release-recovered-cache-v2.py")
RECOVERY_ROOT = ROOT / "validation/2026-10-18-environment-recovery/sources"
RECOVERY_SOURCES = ("run-recovery.py", "pip-worker.py", "pip_meter.py", "full-suite-worker.py")
ORIGINAL_SHA = "96136cf823ca00d82c28d080b0c7ff38726717cd2764cca20dacd914ff07b781"
ARCHIVE_SHA = "320ab8f6dbcb36b4cc962de25b193f9cbfee88345fae37beb1ea9453f373031e"
COPIED_MEMBERS = ("campaign.json", "review.json", "artifacts/acquisition.json",
    "selection/selection.json", "selection/tokens.development.json",
    "reference/reference.json", "reference/article0.cached.npy", "reference/article1.cached.npy")
SECONDS, RSS_BYTES, OUTPUT_BYTES = 600, 1024**3, 4 * 1024**3


def identities():
    return ({name: sha256_file(EVIDENCE / name) for name in SOURCES},
            {name: sha256_file(RECOVERY_ROOT / name) for name in RECOVERY_SOURCES})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review", type=Path, required=True)
    args = parser.parse_args()
    args.review = args.review.absolute()
    output = new_directory(INPUTS)
    started = time.monotonic()
    deadline = started + SECONDS
    before = source_hashes()
    helper_before, recovery_before = identities()
    used = {str(p.relative_to(ROOT)): {"bytes": p.stat().st_size, "sha256": sha256_file(p)}
            for p in (args.review, DEPENDENCIES, RETAINED / "raw-evidence.tar.gz",
                      RETAINED / "inventory.json", RETAINED / "cache-comparison-slices.npz",
                      RETAINED / "slice-derivation.json")}
    record = {"schema_version": "hadamard-reference-diagnostic-inputs.v2", "status": "failed",
        "started_utc": utc_now(), "source_sha256_before": before,
        "diagnostic_sha256_before": helper_before, "recovery_helper_sha256_before": recovery_before,
        "used_input_files_before": used, "deadline_seconds": SECONDS,
        "worker_rss_limit_bytes": RSS_BYTES, "output_limit_bytes": OUTPUT_BYTES,
        "original_campaign_directory": "build/model-campaign-development-002",
        "original_campaign_sha256": ORIGINAL_SHA, "full_prefill_logits_available": False,
        "model_calls": 0, "quality_test_accessed": False, "quality_model_calls": 0,
        "dataset_parsed": False, "dataset_artifact_bodies_acquired": False,
        "campaign_ready": False, "errors": [], "copied_original_evidence": {},
        "reacquired_model_files": {}, "new_acquisition_downloaded_bytes": None}
    write_json(output / "reconstruction-start.json", record)

    def check_limits():
        if time.monotonic() >= deadline or directory_bytes(output) > OUTPUT_BYTES - 65536:
            raise ValueError("Input recovery exceeded the fixed time/output allowance")

    try:
        with (ROOT / "build/model-campaign.process-lock").open("a+b") as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            review = json.loads(args.review.read_text())
            if (review.get("schema_version") != "hadamard-reference-diagnostic-review.v2"
                    or review.get("specification") != "passed" or review.get("standards") != "passed"
                    or review.get("diagnostic_source_sha256") != helper_before
                    or review.get("recovery_helper_sha256") != recovery_before
                    or review.get("benchmark_source_sha256") != before
                    or review.get("original_campaign_sha256") != ORIGINAL_SHA):
                raise ValueError("Both prospective reviews must bind the exact sources and original run")
            verify_review_commit(json.loads((ROOT / "validation/2026-10-17-model-campaign/review.json").read_text()), before)
            dependency = json.loads(DEPENDENCIES.read_text())
            if (dependency.get("phase") != "dependencies" or dependency.get("status") != "passed"
                    or dependency.get("inputs_unchanged") is not True
                    or dependency.get("source_sha256_before") != before
                    or dependency.get("source_sha256_after") != before
                    or dependency.get("helper_sha256_before") != recovery_before
                    or dependency.get("helper_sha256_after") != recovery_before
                    or dependency.get("https_accounting_complete") is not True
                    or dependency.get("prior_observed_https_bytes") != 715089677
                    or type(dependency.get("combined_https_received_bytes")) is not int
                    or dependency["combined_https_received_bytes"] > 1024**3
                    or dependency.get("venvs_root") != str(VENVS)
                    or any(dependency.get("tasks", {}).get(name, {}).get("status") != "passed"
                           for name in ("install-converter", "install-runtime", "abi-converter", "abi-runtime"))):
                raise ValueError("Fresh exact environment restoration with complete carried byte accounting is required")
            manifest = json.loads(MANIFEST.read_text())
            host = _environment()
            try:
                _memory_preflight(host, RSS_BYTES)
                if (any(host[key] != manifest["hardware"][key] for key in ("architecture", "cpu_model"))
                        or host["python_version"] != manifest["runtime"]["python_version"]
                        or host["disk_free_bytes"] < OUTPUT_BYTES):
                    raise ValueError("Acquisition requires the frozen host and 4 GiB free disk")
            finally:
                write_json(output / "acquisition-host.json", host)
            archive_path = RETAINED / "raw-evidence.tar.gz"
            if sha256_file(archive_path) != ARCHIVE_SHA:
                raise ValueError("Original evidence archive changed")
            inventory = json.loads((RETAINED / "inventory.json").read_text())
            expected = {item["path"]: {"bytes": item["bytes"], "sha256": item["sha256"]}
                        for item in inventory["members"]}
            with tarfile.open(archive_path, "r:gz") as archive:
                members = archive.getmembers()
                if len(members) != 49 or len({m.name for m in members}) != 49 or set(expected) != {m.name for m in members}:
                    raise ValueError("Original archive member set differs")
                for member in members:
                    if not member.isfile() or member.size != expected[member.name]["bytes"]:
                        raise ValueError("Original archive has a changed member or special file")
                    content = archive.extractfile(member).read()
                    if hashlib.sha256(content).hexdigest() != expected[member.name]["sha256"]:
                        raise ValueError("Original archive member identity differs")
                    if member.name in COPIED_MEMBERS:
                        target = output / member.name
                        target.parent.mkdir(parents=True, exist_ok=True)
                        with target.open("xb") as stream:
                            stream.write(content)
                        record["copied_original_evidence"][member.name] = expected[member.name]
                    check_limits()
            for filename in ("cache-comparison-slices.npz", "slice-derivation.json"):
                target = output / "reference" / filename
                with (RETAINED / filename).open("rb") as source, target.open("xb") as destination:
                    shutil.copyfileobj(source, destination, length=1024 * 1024)
                record["copied_original_evidence"]["reference/" + filename] = {
                    "bytes": target.stat().st_size, "sha256": sha256_file(target)}
            if sha256_file(output / "campaign.json") != ORIGINAL_SHA:
                raise ValueError("Copied campaign identity differs")
            new_acquisition = new_directory(output / "new-acquisition")
            config = new_acquisition / "config.json"
            write_json(config, {"kind": "acquisition", "campaign_root": str(new_acquisition),
                                "source_sha256": before, "deadline": deadline})
            command = [str(VENVS / "runtime/bin/python"), str(ROOT / "benchmarks/run_model.py"),
                       "worker", "--config", str(config), "--output", str(new_acquisition / "worker")]
            record["acquisition_attempted"] = True
            record["dataset_artifact_bodies_acquired"] = None
            temporary = new_directory(new_acquisition / "temporary")
            task = run_bounded_task(command, new_acquisition / "worker", deadline=deadline,
                memory_limit=RSS_BYTES, campaign_root=output, cache_limit=OUTPUT_BYTES,
                env={"TMPDIR": str(temporary), "HF_HOME": str(new_acquisition / "library-cache"),
                     "HF_HUB_CACHE": str(new_acquisition / "library-cache/hub"),
                     "TRANSFORMERS_CACHE": str(new_acquisition / "library-cache/transformers"),
                     "MPLCONFIGDIR": str(new_acquisition / "plot-cache")})
            record["acquisition_task_status"] = task["status"]
            record["acquisition_task_sha256"] = sha256_file(new_acquisition / "worker/task-receipt.json")
            if task["status"] != "passed":
                raise ValueError("Bounded acquisition failed; no retry or fallback is allowed")
            acquired = verify_acquisition(manifest, new_acquisition / "artifacts")
            record["new_acquisition_sha256"] = sha256_file(new_acquisition / "artifacts/acquisition.json")
            record["new_acquisition_downloaded_bytes"] = acquired["downloaded_bytes"]
            record["dataset_artifact_bodies_acquired"] = True
            original = json.loads((output / "artifacts/acquisition.json").read_text())
            fields = ("path", "kind", "repo", "revision", "filename", "url", "bytes", "sha256")
            if (len(acquired["files"]) != 8 or len(original["files"]) != 8
                    or any(any(fresh[key] != prior[key] for key in fields)
                           for fresh, prior in zip(acquired["files"], original["files"], strict=True))):
                raise ValueError("Reacquired eight-file identities differ from the retained original acquisition")
            original_models = {item["path"]: item for item in original["files"] if item["kind"] == "model"}
            for item in acquired["files"]:
                if item["kind"] != "model":
                    continue
                prior = original_models[item["path"]]
                if any(item[key] != prior[key] for key in ("path", "bytes", "sha256", "repo", "revision", "filename")):
                    raise ValueError("Reacquired model bytes differ from the original pinned model")
                target = output / "artifacts" / item["path"]
                target.parent.mkdir(parents=True, exist_ok=True)
                with (new_acquisition / "artifacts" / item["path"]).open("rb") as source, target.open("xb") as destination:
                    shutil.copyfileobj(source, destination, length=1024 * 1024)
                record["reacquired_model_files"]["artifacts/" + item["path"]] = {
                    "bytes": item["bytes"], "sha256": item["sha256"]}
                check_limits()
            verify_bound_files(output, record["copied_original_evidence"] | record["reacquired_model_files"])
            if len(record["copied_original_evidence"]) != 10 or len(record["reacquired_model_files"]) != 5:
                raise ValueError("Reconstruction requires exactly ten evidence files and five model files")
            record["status"] = "complete"
    except Exception as error:
        record["errors"].append({"type": type(error).__name__, "message": str(error)})
        traceback.print_exc()
    finally:
        record["inputs_unchanged"] = False
        try:
            record["source_sha256_after"] = source_hashes()
            record["diagnostic_sha256_after"], record["recovery_helper_sha256_after"] = identities()
            verify_bound_files(ROOT, used)
            record["inputs_unchanged"] = (before == record["source_sha256_after"]
                and helper_before == record["diagnostic_sha256_after"]
                and recovery_before == record["recovery_helper_sha256_after"])
            record["output_bytes_before_final_receipt"] = directory_bytes(output)
            check_limits()
        except Exception as error:
            record["errors"].append({"type": type(error).__name__, "message": "Final verification: " + str(error)})
        record["elapsed_seconds"] = time.monotonic() - started
        if record["errors"] or not record["inputs_unchanged"] or record["elapsed_seconds"] >= SECONDS:
            record["status"] = "failed"
        record["finished_utc"] = utc_now()
        if len(json.dumps(record, indent=2, sort_keys=True).encode()) + 1 > 65536:
            raise ValueError("Final reconstruction receipt exceeds reserved 64 KiB")
        write_json(output / "reconstruction.json", record)
    print(json.dumps({key: record[key] for key in ("status", "elapsed_seconds", "model_calls", "errors")}))
    return 0 if record["status"] == "complete" else 1


if __name__ == "__main__":
    raise SystemExit(main())
