#!/usr/bin/env python3
"""Gate and observe the separately reviewed operator arithmetic experiment."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path
import re
import shutil
import sys
import time
import traceback

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from benchmarks.campaign_guard import (
    new_directory, run_bounded_task, sha256_file, source_hashes, utc_now, write_json,
)
from benchmarks.qualify import _environment, _memory_preflight
from audit_io import strict_json


BASE_COMMIT = "e26702bdd16242abbfe7dd34cdcf7529327f527a"
BENCHMARK_MAP_SHA256 = "1dd75e9af0736795e4d83c26f866d15d9f7a3fe55003e399ddbd36951ab2d69e"
PROTOCOL = "docs/experiments/operator-arithmetic-v1.md"
SOURCES_NOTE = "docs/research/operator-arithmetic-sources.md"
HOST_RECORD = "experiments/operator-audit/host-v1.json"
HOST_OBSERVATION = "validation/2026-10-19-operator-arithmetic/pre-registration-host-check-001.json"
DEPENDENCY_LEDGER = "validation/2026-10-18-campaign-development/diagnostic-environment-recovery/qualification.json"
DEPENDENCY_BYTES = 1_072_634_485
DEPENDENCY_LIMIT = 1_073_741_824
CHECKPOINT_BYTES = 166_029_852
CHECKPOINT_SHA256 = "ebfa4e2f18696ebd83716a0d39fe2c025f2ff8483f72a83ca59c475692fc9d15"
CHECKPOINT_RELATIVE = "worker/model/model.safetensors"
BODY_LIMIT = 200 * 1024 * 1024
MEMORY_LIMIT = 1024 ** 3
AUDIT_OUTPUT_LIMIT = 64 * 1024 * 1024
CASE_IDS = ("article0_qkv", "article0_mlp", "article1_qkv", "article1_mlp")
NUMPY_IMPORT_SOURCE = {"bytes": 25919,
                      "sha256": "93924ac4b793328947dfd9eb9355e54eccdfd26a92c8dd52188aed2e52c7eb38"}


def canonical_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode()).hexdigest()


def read_json(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError("Expected an existing regular evidence file")
    return strict_json(path.read_bytes())


def file_identity(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError("An evidence input is missing or a symlink")
    return {"bytes": path.stat().st_size, "sha256": sha256_file(path)}


def numpy_startup_evidence(np):
    identity = file_identity(Path(np.__file__))
    if np.__version__ != "2.3.5" or identity != NUMPY_IMPORT_SOURCE:
        raise ValueError("The installed NumPy import source differs from the audited startup code")
    return {"source": identity,
            "source_derived_calls_per_import": {"fp32_dot_length2": 1, "fp64_matmul_20x20": 1},
            "scope": "Normal NumPy startup controls on synthetic arrays; excluded from checkpoint/trace candidate counters",
            "calls_individually_instrumented": False}


def source_snapshot():
    benchmark = source_hashes()
    if len(benchmark) != 30 or canonical_hash(benchmark) != BENCHMARK_MAP_SHA256:
        raise ValueError("The thirty frozen benchmark source files changed")
    paths = sorted(Path(__file__).parent.glob("*.py"))
    paths += [ROOT / PROTOCOL, ROOT / SOURCES_NOTE, ROOT / HOST_RECORD, ROOT / HOST_OBSERVATION]
    operator = {p.relative_to(ROOT).as_posix(): sha256_file(p) for p in paths}
    return {"operator_source_sha256": operator, "benchmark_source_sha256": benchmark}


def verify_registration(review_path, publication_path):
    sources = source_snapshot()
    source_digest = canonical_hash(sources)
    review, publication = read_json(review_path), read_json(publication_path)
    if (review.get("schema_version") != "hadamard-operator-review.v1"
            or review.get("base_commit") != BASE_COMMIT
            or review.get("sources") != sources
            or review.get("source_map_sha256") != source_digest):
        raise ValueError("Current operator/protocol sources differ from the prospective review")
    reviewers = []
    for axis in ("specification", "standards"):
        item = review.get(axis, {})
        report = ROOT / item.get("report_path", "")
        if (item.get("status") != "passed" or item.get("source_map_sha256") != source_digest
                or not isinstance(item.get("reviewer"), str) or not item["reviewer"]
                or not report.resolve().is_relative_to(ROOT)
                or file_identity(report)["sha256"] != item.get("report_sha256")):
            raise ValueError("Both independently bound prospective review axes must pass")
        reviewers.append(item["reviewer"])
    if reviewers[0] == reviewers[1]:
        raise ValueError("The two review axes require distinct reviewers")
    if (publication.get("schema_version") != "hadamard-operator-publication.v1"
            or publication.get("review_sha256") != sha256_file(review_path)
            or publication.get("source_map_sha256") != source_digest
            or not re.fullmatch(r"[0-9a-f]{40}", str(publication.get("preregistration_commit", "")))
            or not re.fullmatch(r"[0-9a-f]{40}", str(publication.get("preregistration_tree", "")))
            or publication.get("published_before_acquisition_and_evaluation") is not True):
        raise ValueError("A matching published preregistration receipt is required")
    return {"sources": sources, "source_map_sha256": source_digest,
            "review": file_identity(review_path), "publication": file_identity(publication_path),
            "preregistration_commit": publication["preregistration_commit"],
            "preregistration_tree": publication["preregistration_tree"]}


def host_preflight(output):
    """Qualify this existing NumPy runtime, never the missing campaign stack."""
    observed = _environment()
    disk = shutil.disk_usage(output)
    observed.update(disk_free_bytes=disk.free, disk_total_bytes=disk.total,
                    disk_observation_path=str(output))
    host = read_json(ROOT / HOST_RECORD)
    errors = []
    if (host.get("schema_version") != "hadamard-operator-host.v1"
            or host.get("campaign_ready") is not False
            or host.get("source_observation") != {"path": HOST_OBSERVATION,
                                                   **file_identity(ROOT / HOST_OBSERVATION)}):
        errors.append("The separate operator host qualification record differs")
    for name in ("architecture", "cpu_model"):
        if observed.get(name) != host["hardware"][name]:
            errors.append(f"{name} differs from the separately qualified operator host")
    if observed.get("python_version") != "3.12.14":
        errors.append("Python 3.12.14 is required")
    versions = dict(observed["dependency_metadata_versions"])
    for name, expected in (("numpy", "2.3.5"), ("threadpoolctl", "3.6.0")):
        try:
            actual = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            actual = None
        versions[name] = actual
        if actual != expected:
            errors.append(f"The existing {name} version differs from {expected}")
    observed["operator_dependency_metadata_versions"] = versions
    try:
        _memory_preflight(observed, 6 * 1024 ** 3)
    except ValueError:
        errors.append("The unchanged conservative 6 GiB memory preflight did not pass")
    if disk.free < 4 * 1024 ** 3:
        errors.append("At least 4 GiB free disk is required")
    quota = observed.get("cpu_quota_cores")
    if quota is not None and quota < 1:
        errors.append("At least one CPU core of quota is required")
    ledger = read_json(ROOT / DEPENDENCY_LEDGER)
    if ledger.get("combined_https_received_bytes") != DEPENDENCY_BYTES:
        errors.append("The previous dependency transfer ledger differs")
    return {"schema_version": "hadamard-operator-preflight.v1", "observed_utc": utc_now(),
            "status": "passed" if not errors else "blocked", "errors": errors,
            "environment": observed, "campaign_ready": False,
            "operator_host_qualification": {"path": HOST_RECORD, **file_identity(ROOT / HOST_RECORD)},
            "scope": "Existing NumPy operator-audit runtime only; ONNX/Torch campaign stack is not qualified",
            "dependency_ledger": {"source": DEPENDENCY_LEDGER,
                                  **file_identity(ROOT / DEPENDENCY_LEDGER),
                                  "carried_received_bytes": DEPENDENCY_BYTES,
                                  "new_received_bytes": 0, "limit_bytes": DEPENDENCY_LIMIT,
                                  "remaining_bytes": DEPENDENCY_LIMIT - DEPENDENCY_BYTES}}


def validate_preparation(directory, registration):
    directory = Path(directory).resolve()
    phase = read_json(directory / "phase-result.json")
    receipt = read_json(directory / "worker/worker-result.json")
    expected = {"bytes": CHECKPOINT_BYTES, "sha256": CHECKPOINT_SHA256}
    if (phase.get("phase") != "prepare" or phase.get("status") != "passed"
            or phase.get("registration_before") != registration
            or phase.get("registration_after") != registration
            or phase.get("inputs_unchanged") is not True
            or receipt.get("status") != "passed"
            or receipt.get("dependency_received_bytes") != 0
            or receipt.get("model_calls") != 0 or receipt.get("candidate_operator_calls") != 0
            or receipt.get("downloaded_bytes") != CHECKPOINT_BYTES
            or receipt.get("checkpoint") != expected
            or file_identity(directory / CHECKPOINT_RELATIVE) != expected):
        raise ValueError("The single pinned checkpoint preparation is incomplete or changed")
    bound = {name: file_identity(directory / name) for name in
             ("phase-result.json", "worker/worker-result.json", CHECKPOINT_RELATIVE)}
    return bound


def classify_candidate(case_results):
    """A complete experiment can pass execution while rejecting the candidate."""
    if [c.get("id") for c in case_results] != list(CASE_IDS):
        raise ValueError("Exactly the four prespecified cases in order are required")
    checked = misses = 0
    for case, width in zip(case_results, (1536, 2048, 1536, 2048), strict=True):
        candidates = case.get("candidate", [])
        if [c.get("rows") for c in candidates] != [1, 513]:
            raise ValueError("Both fixed candidate row counts are required once per case")
        for candidate in candidates:
            count = candidate.get("checked_final_values")
            mismatch = candidate.get("fp32_vs_exact", {}).get("bit_mismatches")
            if (type(count) is not int or count != width or type(mismatch) is not int
                    or not 0 <= mismatch <= count or candidate.get("completed") is not True):
                raise ValueError("Incomplete or malformed candidate evaluation")
            checked += count
            misses += mismatch
    return {"status": "qualified_for_tested_final_positions" if misses == 0 else "rejected",
            "checked_final_values": checked, "bit_mismatches": misses,
            "all_primary_values_match_exact_rounding": misses == 0,
            "general_correct_rounding_guarantee": False, "campaign_ready": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("prepare", "audit", "source-map"))
    parser.add_argument("--review", type=Path)
    parser.add_argument("--publication", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--preparation", type=Path)
    args = parser.parse_args()
    if args.phase == "source-map":
        sources = source_snapshot()
        print(json.dumps({"sources": sources, "source_map_sha256": canonical_hash(sources)},
                         sort_keys=True, indent=2))
        return 0
    if not all((args.review, args.publication, args.output)):
        parser.error("--review, --publication and --output are required")
    if args.phase == "audit" and args.preparation is None:
        parser.error("--preparation is required for audit")
    output = new_directory(args.output)
    started = time.monotonic()
    limit = 600 if args.phase == "prepare" else 120
    result = {"schema_version": "hadamard-operator-phase.v1", "phase": args.phase,
              "status": "failed", "started_utc": utc_now(), "campaign_ready": False,
              "wall_limit_seconds": limit, "worker_rss_limit_bytes": MEMORY_LIMIT,
              "inputs_unchanged": False, "task": None}
    try:
        registration = verify_registration(args.review, args.publication)
        result["registration_before"] = registration
        claim = args.publication.resolve().parent / f"{args.phase}-claim.json"
        write_json(claim, {"phase": args.phase, "output": str(output), "started_utc": utc_now(),
                           "registration": registration})
        write_json(output / "start.json", {**result, "claim": file_identity(claim)})
        preflight = host_preflight(output)
        write_json(output / "preflight.json", preflight)
        if preflight["status"] != "passed":
            raise ValueError("Operator preflight blocked; no worker launched")
        prep_before = None
        if args.phase == "audit":
            prep_before = validate_preparation(args.preparation, registration)
            result["preparation_files_before"] = prep_before
        script = "acquire_checkpoint.py" if args.phase == "prepare" else "audit_worker.py"
        command = [sys.executable, "-B", str(Path(__file__).parent / script),
                   "--output", str(output / "worker"), "--review", str(args.review.resolve()),
                   "--publication", str(args.publication.resolve())]
        if args.preparation is not None:
            command += ["--preparation", str(args.preparation.resolve())]
        result["task"] = run_bounded_task(
            command, output / "worker", deadline=started + limit, memory_limit=MEMORY_LIMIT,
            campaign_root=output, cache_limit=4 * 1024 ** 3 if args.phase == "prepare" else AUDIT_OUTPUT_LIMIT,
        )
        result["registration_after"] = verify_registration(args.review, args.publication)
        if result["registration_after"] != registration:
            raise ValueError("Registration/source inputs changed during the phase")
        if prep_before is not None:
            result["preparation_files_after"] = validate_preparation(args.preparation, registration)
            if result["preparation_files_after"] != prep_before:
                raise ValueError("Preparation inputs changed during the numerical phase")
        result["inputs_unchanged"] = True
        task = result["task"]
        if (task["status"] != "passed" or task["worker"].get("inputs_unchanged") is not True
                or task["worker"].get("registration_before") != registration
                or task["worker"].get("registration_after") != registration):
            raise ValueError("The identity-bound worker did not complete validly")
        result["status"] = "passed"
    except Exception as error:
        result["error"] = {"type": type(error).__name__, "message": str(error)}
        traceback.print_exc()
    result.update(finished_utc=utc_now(), elapsed_seconds=time.monotonic() - started)
    write_json(output / "phase-result.json", result)
    print(json.dumps({"phase": args.phase, "status": result["status"],
                      "elapsed_seconds": result["elapsed_seconds"], "output": str(output)}))
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
