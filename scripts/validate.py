#!/usr/bin/env python3
"""Validate retained results and the bundled calculator, optionally reproducing the sweep."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

THREAD_ENV = {key: "1" for key in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS", "VECLIB_MAXIMUM_THREADS")}
os.environ.update(THREAD_ENV)

from verify_results import ROOT, compare_reproduction, digest, load, verify_retained

INPUTS = (
    "experiment.py", "results.json", "group_experiment.py", "test_group_experiment.py", "group-results.json",
    "scripts/verify_results.py", "scripts/validate.py", "test_verify_results.py", "scripts/build_article.py",
    "docs/experiments/group-size-v1.md", "docs/reference-import.json", "requirements.txt",
    "article.md", "exposition.html", "calculator.html", "verify-calculator.cjs", "calculator-verification.json",
)


def source_hashes() -> dict:
    return {name: digest(ROOT / name) if (ROOT / name).is_file() else None for name in INPUTS}


def write_receipt(path: Path, receipt: dict) -> None:
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(receipt, indent=2, allow_nan=False) + "\n")
    os.replace(temporary, path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reproduce", action="store_true", help="rerun the group sweep in a fresh directory with a 180-second deadline")
    args = parser.parse_args()
    build = ROOT / "build"
    build.mkdir(exist_ok=True)
    path = build / "validation.json"
    if path.exists():
        history = build / "validation-history"
        history.mkdir(exist_ok=True)
        previous = path.read_bytes()
        saved = history / f"{hashlib.sha256(previous).hexdigest()}.json"
        if not saved.exists():
            saved.write_bytes(previous)
    started = time.perf_counter()
    receipt = {
        "schema": "hadamard-validation.v1", "status": "running",
        "started_utc": datetime.now(timezone.utc).isoformat(), "reproduce_requested": args.reproduce,
        "source_sha256": source_hashes(), "thread_environment": THREAD_ENV,
        "validation_python": sys.version, "phases": [],
    }
    write_receipt(path, receipt)

    def phase(name: str, action) -> None:
        record = {"name": name, "status": "running"}
        receipt["phases"].append(record)
        write_receipt(path, receipt)
        phase_start = time.perf_counter()
        try:
            record["result"] = action(record)
            record["status"] = "passed"
        except Exception as error:
            record.update(status="failed", error={"type": type(error).__name__, "message": str(error)})
        finally:
            record["wall_seconds"] = time.perf_counter() - phase_start
            write_receipt(path, receipt)
            print(f"{name}: {record['status']}", flush=True)

    def command(record: dict, argv: list[str], timeout: int) -> subprocess.CompletedProcess:
        record["command"] = argv
        record["deadline_seconds"] = timeout
        environment = {**os.environ, **THREAD_ENV}
        try:
            result = subprocess.run(argv, cwd=ROOT, env=environment, capture_output=True, text=True, timeout=timeout)
        except subprocess.TimeoutExpired as error:
            record.update(timed_out=True, stdout=(error.stdout or b"").decode() if isinstance(error.stdout, bytes) else error.stdout,
                          stderr=(error.stderr or b"").decode() if isinstance(error.stderr, bytes) else error.stderr)
            raise
        record.update(exit_code=result.returncode, timed_out=False, stdout=result.stdout, stderr=result.stderr)
        result.check_returncode()
        return result

    phase("focused_unit_tests", lambda record: {
        "completed": command(record, [sys.executable, "-m", "unittest", "discover", "-s", ".", "-p", "test_*.py", "-v"], 60).returncode == 0,
    })
    phase("retained_results", lambda record: verify_retained())

    def calculator(record: dict) -> dict:
        node = shutil.which("node")
        if node is None:
            raise RuntimeError("Node is required to execute the actual bundled calculator.")
        result = command(record, [node, str(ROOT / "verify-calculator.cjs"), str(ROOT / "exposition.html")], 30)
        observed = json.loads(result.stdout)
        for field in ("actual_bundled_javascript_executed", "update_events_checked", "exact_counterexample_matches_rational_result", "all_assets_embedded"):
            if observed.get(field) is not True:
                raise ValueError(f"calculator check missing: {field}")
        if digest(ROOT / "calculator-verification.json") != receipt["source_sha256"]["calculator-verification.json"]:
            raise ValueError("Validation changed the retained calculator receipt.")
        return observed

    phase("bundled_calculator", calculator)

    if args.reproduce:
        def reproduce(record: dict) -> dict:
            directory = Path(tempfile.mkdtemp(prefix="reproduction-", dir=build))
            record["output_directory"] = str(directory.relative_to(ROOT))
            command(record, [sys.executable, str(ROOT / "group_experiment.py"), "--no-plots", "--output", str(directory)], 180)
            reproduced_path = directory / "group-results.json"
            record["reproduced_results_sha256"] = digest(reproduced_path)
            independent = verify_retained(group_path=reproduced_path)
            retained, reproduced = load(ROOT / "group-results.json"), load(reproduced_path)
            matched = compare_reproduction(retained, reproduced)
            return {"independent_verification": independent, "deterministic_comparison": matched,
                    "retained_environment": retained["environment"], "reproduced_environment": reproduced["environment"],
                    "reproduced_timing": reproduced["timing"]}
        phase("group_reproduction", reproduce)
    else:
        receipt["phases"].append({"name": "group_reproduction", "status": "not_requested"})

    def unchanged(record: dict) -> dict:
        current = source_hashes()
        differences = [name for name, expected in receipt["source_sha256"].items() if current[name] != expected]
        record["final_source_sha256"] = current
        if differences:
            raise ValueError("Validation inputs changed during execution: " + ", ".join(differences))
        missing = [name for name, value in current.items() if value is None]
        if missing:
            raise ValueError("Validation inputs are missing: " + ", ".join(missing))
        return {"all_source_and_retained_result_bytes_unchanged": True}

    phase("inputs_unchanged", unchanged)
    receipt["status"] = "failed" if any(item["status"] == "failed" for item in receipt["phases"]) else "passed"
    receipt["finished_utc"] = datetime.now(timezone.utc).isoformat()
    receipt["wall_seconds"] = time.perf_counter() - started
    write_receipt(path, receipt)
    print(f"Validation {receipt['status']}: {path}")
    return 0 if receipt["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
