"""Restore exact environments or run the complete unchanged offline suite.

This fresh effort follows an execution-service reset. It preserves the original
generated-input limits and credits the earlier observed dependency bytes against
the combined 1 GiB receive allowance. It never launches a pretrained campaign.
"""
import argparse
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import time
import venv

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("phase", choices=("dependencies", "suite"))
parser.add_argument("--repo", type=Path, required=True)
parser.add_argument("--output", type=Path, required=True)
parser.add_argument("--venvs", type=Path)
parser.add_argument("--dependency-effort", type=Path)
parser.add_argument("--prior-https-bytes", type=int, default=0)
args = parser.parse_args()
ROOT = args.repo.resolve()
HELPERS = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from benchmarks.campaign_guard import (MANIFEST, THREADS, directory_bytes, new_directory,
    run_bounded_task, sha256_file, source_hashes, utc_now, write_json)
from benchmarks.qualify import _check_environment, _environment, _memory_preflight
from benchmarks.run_model import record_preflight, verify_review_commit

MEMORY = 1024**3
OUTPUT_LIMIT = 4 * 1024**3
LOCK_SHA256 = "f4b045d55bb3de7d8673c2a1e89ee15ec3dcd398097df381d3faa0761c67878b"
REVIEW = ROOT / "validation/2026-10-17-model-campaign/review.json"
HELPER_NAMES = ("run-recovery.py", "pip-worker.py", "pip_meter.py", "full-suite-worker.py")


def helper_hashes():
    return {name: sha256_file(HELPERS / name) for name in HELPER_NAMES}


def footprint(path):
    result = {"regular_file_bytes": 0, "regular_files": 0, "symlinks": []}

    def refuse(error):
        raise error

    for parent, directories, files in os.walk(path, followlinks=False, onerror=refuse):
        for name in [*directories, *files]:
            item = Path(parent) / name
            metadata = item.lstat()
            if stat.S_ISLNK(metadata.st_mode):
                result["symlinks"].append({"path": item.relative_to(path).as_posix(),
                                           "target": os.readlink(item)})
            elif stat.S_ISREG(metadata.st_mode):
                result["regular_file_bytes"] += metadata.st_size
                result["regular_files"] += 1
            elif not stat.S_ISDIR(metadata.st_mode):
                raise ValueError("A special file prevents complete footprint accounting")
    result["symlinks"].sort(key=lambda item: item["path"])
    return result


def worker_environment(output, temporary):
    paths = {"TMPDIR": temporary, "MPLCONFIGDIR": output / "mpl-cache",
             "HF_HOME": output / "hf-cache", "TRANSFORMERS_CACHE": output / "transformers-cache"}
    for path in paths.values():
        path.mkdir(parents=True, exist_ok=False)
    return {**THREADS, **{name: str(path) for name, path in paths.items()},
            "PYTHONPATH": str(ROOT), "TOKENIZERS_PARALLELISM": "false",
            "PYTHONDONTWRITEBYTECODE": "1"}


started = time.monotonic()
output = new_directory(args.output)
duration = 600 if args.phase == "dependencies" else 180
deadline = started + duration
before, helper_before = source_hashes(), helper_hashes()
manifest = json.loads(MANIFEST.read_text())
receipt = {"schema_version": "hadamard-environment-recovery.v2", "phase": args.phase,
    "status": "failed", "started_utc": utc_now(), "start_monotonic": started,
    "deadline_monotonic": deadline, "deadline_seconds": duration,
    "memory_limit_bytes": MEMORY, "retained_output_limit_bytes": OUTPUT_LIMIT,
    "source_sha256_before": before, "helper_sha256_before": helper_before,
    "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
    "source_tree": subprocess.check_output(["git", "rev-parse", "HEAD^{tree}"], cwd=ROOT, text=True).strip(),
    "model_calls": 0, "model_data_download_bytes": 0, "campaign_ready": False, "tasks": {}}
if args.phase == "dependencies":
    receipt.update({"https_receive_byte_limit": 1024**3,
        "prior_observed_https_bytes": args.prior_https_bytes,
        "known_effort_https_bytes": 0, "effort_https_received_bytes": 0,
        "combined_https_received_bytes": args.prior_https_bytes, "https_accounting_complete": True})
write_json(output / "effort-start.json", receipt)

try:
    review = json.loads(REVIEW.read_text())
    verify_review_commit(review, before)
    receipt["review_verification"] = {"status": "passed", "sha256": sha256_file(REVIEW),
        "reviewed_commit": review["reviewed_commit"], "reviewed_tree": review["reviewed_tree"],
        "specification": review["specification"], "standards": review["standards"]}
    host = _environment()
    receipt["host_before"] = host
    try:
        if args.phase == "suite":
            _check_environment(host, manifest)
        else:
            _memory_preflight(host, MEMORY)
            if (any(host[key] != manifest["hardware"][key] for key in ("architecture", "cpu_model"))
                    or host["python_version"] != manifest["runtime"]["python_version"]):
                raise ValueError("The frozen CPU, architecture and Python are required")
        if host["disk_free_bytes"] < OUTPUT_LIMIT:
            raise ValueError("Qualification requires at least 4 GiB free disk")
    finally:
        write_json(output / "host-preflight.json", host)
    locked_path = ROOT / "benchmarks/model-dependencies-v1.json"
    if sha256_file(locked_path) != LOCK_SHA256:
        raise ValueError("The complete published wheel lock changed")
    locked = json.loads(locked_path.read_text())
    receipt["lock_sha256"] = LOCK_SHA256

    if args.phase == "dependencies":
        import pip
        from benchmarks.dependency_lock import write_hash_requirements

        if args.venvs is None or not 0 <= args.prior_https_bytes < 1024**3:
            raise ValueError("A fresh venv root and a valid prior transfer observation are required")
        environments = new_directory(args.venvs)
        if environments.is_relative_to(output) or output.is_relative_to(environments):
            raise ValueError("Venvs must be separate prepared inputs outside the retained evidence tree")
        receipt["venvs_root"] = str(environments)
        receipt["disk_accounting_scope"] = (
            "Sampled disk covers retained evidence, pip cache and pip temporary files. "
            "Prepared venvs are separate; their final logical footprint is observed without following symlinks.")
        with (output / "dependency-lock.json").open("xb") as stream:
            stream.write(locked_path.read_bytes())
        environment = worker_environment(output, output / "pip-temporary")
        runner = Path(pip.__file__).parent / "__pip-runner__.py"
        receipt["installer"] = {"host_pip_version": pip.__version__, "runner": str(runner),
                                "runner_sha256": sha256_file(runner)}
        for name in ("converter", "runtime"):
            if time.monotonic() >= deadline:
                raise TimeoutError("The dependency effort deadline expired")
            requirements = ROOT / f"benchmarks/locks/{name}-requirements.txt"
            if requirements.read_text() != write_hash_requirements(locked["environments"][name]):
                raise ValueError("Installation list differs from the complete wheel lock")
            destination = environments / name
            venv.EnvBuilder(with_pip=False, clear=False, symlinks=True).create(destination)
            python = destination / "bin/python"
            task_output = output / f"install-{name}-1"
            remaining = 1024**3 - args.prior_https_bytes - receipt["known_effort_https_bytes"]
            if remaining <= 0:
                raise ValueError("The combined dependency receive allowance is exhausted")
            command = [str(python), str(HELPERS / "pip-worker.py"), str(task_output),
                str(HELPERS / "pip_meter.py"), str(runner), str(remaining), str(deadline),
                "--isolated", "install", "--no-input", "--disable-pip-version-check", "--no-index",
                "--require-hashes", "--no-deps", "--only-binary=:all:", "--retries", "0",
                "--resume-retries", "0", "--timeout", "15", "--keyring-provider", "disabled",
                "--cache-dir", str(output / "pip-cache"), "--report",
                str(output / f"{name}-install-report.json"), "-r", str(requirements)]
            attempt = {"path": task_output.relative_to(output).as_posix(), "status": "failed", "command": command}
            receipt["tasks"][f"install-{name}"] = attempt
            receipt["https_accounting_complete"] = False
            receipt["effort_https_received_bytes"] = receipt["combined_https_received_bytes"] = None
            try:
                task = run_bounded_task(command, task_output, deadline=deadline,
                    memory_limit=MEMORY, campaign_root=output, cache_limit=OUTPUT_LIMIT, env=environment)
                attempt["status"] = task["status"]
            finally:
                transfer_path = task_output / "transfer.json"
                attempt["transfer_receipt_exists"] = transfer_path.is_file()
                attempt["pip_report_exists"] = (output / f"{name}-install-report.json").is_file()
                try:
                    transfer = json.loads(transfer_path.read_text())
                    received = transfer["https_received_bytes"]
                    if (type(received) is not int or not 0 <= received <= remaining
                            or type(transfer.get("https_read_calls")) is not int or transfer["https_read_calls"] < 0
                            or transfer.get("https_receive_byte_limit") != remaining
                            or transfer.get("deadline_monotonic") != deadline
                            or transfer.get("python_executable") != str(python)
                            or type(transfer.get("exit_code")) is not int
                            or attempt["status"] == "passed" and transfer["exit_code"] != 0):
                        raise ValueError("Transfer receipt differs from its bounded attempt")
                    receipt["known_effort_https_bytes"] += received
                    receipt["effort_https_received_bytes"] = receipt["known_effort_https_bytes"]
                    receipt["combined_https_received_bytes"] = args.prior_https_bytes + receipt["known_effort_https_bytes"]
                    receipt["https_accounting_complete"] = True
                except Exception as error:
                    attempt["transfer_accounting_error"] = {"type": type(error).__name__, "message": str(error)}
            if not receipt["https_accounting_complete"] or task["status"] != "passed":
                raise RuntimeError("The metered install failed or lacks complete byte accounting")
            print(json.dumps({"task": f"install-{name}", "status": "passed",
                              "combined_https_bytes": receipt["combined_https_received_bytes"]}), flush=True)
            host = _environment()
            try:
                _memory_preflight(host, MEMORY)
            finally:
                write_json(output / f"{name}-abi-host.json", host)
            config = output / f"{name}-abi-config.json"
            write_json(config, {"kind": "dependencies", "environment": name,
                                "campaign_root": str(output), "source_sha256": before})
            abi_output = output / f"abi-{name}"
            task = run_bounded_task([str(python), str(ROOT / "benchmarks/run_model.py"), "worker",
                "--config", str(config), "--output", str(abi_output)], abi_output,
                deadline=deadline, memory_limit=MEMORY, campaign_root=output,
                cache_limit=OUTPUT_LIMIT, env=environment)
            receipt["tasks"][f"abi-{name}"] = {"path": abi_output.relative_to(output).as_posix(), "status": task["status"]}
            if task["status"] != "passed":
                raise RuntimeError("The complete installed-closure or generated ABI check failed")
            print(json.dumps({"task": f"abi-{name}", "status": "passed"}), flush=True)
        receipt["prepared_environment_footprints"] = {name: footprint(environments / name) for name in ("converter", "runtime")}
    else:
        from benchmarks.dependency_lock import validate_environment

        if args.dependency_effort is None:
            raise ValueError("The accepted fresh dependency effort is required")
        dependency_path = args.dependency_effort.resolve() / "qualification.json"
        dependency = json.loads(dependency_path.read_text())
        if (dependency["status"] != "passed" or dependency["source_sha256_after"] != before
                or dependency["lock_sha256"] != LOCK_SHA256
                or Path(sys.prefix).resolve() != Path(dependency["venvs_root"]).resolve() / "runtime"):
            raise ValueError("This runtime or source differs from the qualified dependency effort")
        receipt["dependency_qualification"] = {"path": str(dependency_path), "sha256": sha256_file(dependency_path)}
        receipt["runtime_installed_closure"] = validate_environment(locked["environments"]["runtime"])
        fixtures = new_directory(output.with_name(output.name + "-fixtures"))
        environment = worker_environment(output, fixtures / "temporary")
        receipt["fixture_root"] = str(fixtures)
        receipt["disk_accounting_scope"] = (
            "Sampled disk covers retained evidence and scoped caches only. Temporary negative-test fixtures are in "
            "a sibling tree because they deliberately create symlinks. Their transient disk peak is unmeasured. "
            "The generated-suite contract remains 180 seconds and 1 GiB worker RSS. A final footprint is an observation, not a cleanup guarantee.")
        task_output = output / "full-suite"
        task = run_bounded_task([sys.executable, str(HELPERS / "full-suite-worker.py"), str(task_output)],
            task_output, deadline=deadline, memory_limit=MEMORY, campaign_root=output,
            cache_limit=OUTPUT_LIMIT, env=environment)
        receipt["tasks"]["full-suite"] = {"path": "full-suite", "status": task["status"]}
        receipt["fixture_footprint_after"] = footprint(fixtures)
        if task["status"] != "passed":
            raise RuntimeError("The complete current-source suite failed")
        receipt["tests"] = task["worker"]["tests"]
        if receipt["tests"] != {"run": 135, "failures": 0, "errors": 0, "skipped": 0}:
            raise ValueError("The complete 135-test scope did not pass")
        receipt["campaign_preflight"] = record_preflight(output / "campaign-preflight")
    receipt["status"] = "passed"
except Exception as error:
    receipt["error"] = {"type": type(error).__name__, "message": str(error)}
finally:
    receipt["finalization_errors"] = []
    for key, observe in (("source_sha256_after", source_hashes), ("helper_sha256_after", helper_hashes),
                         ("retained_output_bytes_before_final_receipt", lambda: directory_bytes(output))):
        try:
            receipt[key] = observe()
        except Exception as error:
            receipt[key] = None
            receipt["finalization_errors"].append({"observation": key, "type": type(error).__name__, "message": str(error)})
    receipt["inputs_unchanged"] = before == receipt["source_sha256_after"] and helper_before == receipt["helper_sha256_after"]
    receipt["elapsed_seconds"] = time.monotonic() - started
    if not receipt["inputs_unchanged"] or receipt["elapsed_seconds"] >= duration or receipt["finalization_errors"]:
        receipt["status"] = "failed"
    write_json(output / "qualification.json", receipt)
    print(json.dumps({key: receipt[key] for key in ("phase", "status", "elapsed_seconds", "inputs_unchanged", "campaign_ready")}
                     | {"error": receipt.get("error")}), flush=True)
raise SystemExit(0 if receipt["status"] == "passed" else 1)
