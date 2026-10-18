"""Source, evidence and resource gates for the frozen model campaign.

This module uses only the standard library. It can reject an unavailable host
before importing a model runtime, downloading inputs or reading quality tokens.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import signal
import stat
import subprocess
import time

from .qualify import (_environment, _load_worker_identity, _memory_preflight,
                      _proc_stat_identity, _require_rss_observations, _sample_worker_rss)


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "benchmarks/model-benchmark-v1.json"
PROTOCOL = ROOT / "docs/experiments/model-benchmark-v1.md"
THREADS = {name: "1" for name in (
    "OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS")}
HEX256 = re.compile(r"[0-9a-f]{64}\Z")
HEX40 = re.compile(r"[0-9a-f]{40}\Z")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, value: object) -> None:
    """Publish complete JSON without replacing old evidence."""
    path = Path(path)
    pending = path.with_name(path.name + ".pending")
    with pending.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.link(pending, path)
    pending.unlink()


def new_directory(path: Path) -> Path:
    path = Path(path).absolute()
    if path.exists() or path.is_symlink():
        raise FileExistsError("Use a new output directory; earlier observations are retained")
    path.mkdir(parents=True, exist_ok=False)
    return path.resolve()


def source_hashes(root: Path = ROOT) -> dict[str, str]:
    paths = [root / "benchmarks/model-benchmark-v1.json",
             root / "docs/experiments/model-benchmark-v1.md"]
    execution = root / "docs/experiments/model-execution-v1.md"
    if execution.is_file():
        paths.append(execution)
    dependency_lock = root / "benchmarks/model-dependencies-v1.json"
    if dependency_lock.is_file():
        paths.append(dependency_lock)
    paths.extend(sorted((root / "benchmarks/locks").glob("*.txt")))
    paths.extend(sorted(root.glob("requirements*.txt")))
    paths.extend(sorted((root / "benchmarks").rglob("*.py")))
    return {p.relative_to(root).as_posix(): sha256_file(p) for p in paths}


def preflight(manifest: dict, observed: dict | None = None, *, disk_path: Path | None = None) -> dict:
    """Evaluate every host gate, including the unchanged conservative RAM rule."""
    observed = _environment() if observed is None else observed
    if disk_path is not None:
        disk = shutil.disk_usage(disk_path)
        observed.update({"disk_total_bytes": disk.total, "disk_free_bytes": disk.free,
                         "disk_observation_path": str(Path(disk_path).absolute())})
    errors = []
    for key in ("architecture", "cpu_model"):
        if observed.get(key) != manifest["hardware"][key]:
            errors.append(f"{key} differs from the qualified hardware; a new hardware record is required")
    if observed.get("python_version") != manifest["runtime"]["python_version"]:
        errors.append("Python version differs from the frozen runtime")
    for name in ("numpy", "onnx", "onnxruntime"):
        if observed.get("dependency_metadata_versions", {}).get(name) != manifest["runtime"][name + "_version"]:
            errors.append(f"{name} version differs from the frozen runtime")
    try:
        _memory_preflight(observed, manifest["hardware"]["required_free_memory_bytes"])
    except ValueError:
        errors.append("Conservative available memory is below the required 6 GiB or cannot be established")
    disk = observed.get("disk_free_bytes")
    if type(disk) is not int or disk < manifest["hardware"]["required_free_disk_bytes"]:
        errors.append("At least 4 GiB of free disk is required")
    quota = observed.get("cpu_quota_cores")
    if quota is not None and (not isinstance(quota, (int, float)) or quota < 1):
        errors.append("At least one CPU core of quota is required")
    return {"schema_version": "hadamard-model-preflight.v1", "started_utc": utc_now(),
            "status": "passed" if not errors else "blocked", "campaign_ready": False,
            "environment": observed, "errors": errors,
            "model_or_dataset_accessed": False,
            "resource_policy": manifest["budgets"]}


def validate_review(review: dict, sources: dict) -> None:
    if review.get("schema_version") != "hadamard-model-review.v1":
        raise ValueError("A model-adapter review record is required")
    if not HEX40.fullmatch(str(review.get("reviewed_commit", ""))) or not HEX40.fullmatch(str(review.get("reviewed_tree", ""))):
        raise ValueError("The review must identify its Git commit and tree")
    if review.get("source_sha256") != sources:
        raise ValueError("Current source files differ from the independent review")
    if review.get("specification") != "passed" or review.get("standards") != "passed":
        raise ValueError("Both independent review axes must pass")


def _regular_path(root: Path, relative: str) -> Path:
    if not isinstance(relative, str) or Path(relative).is_absolute() or ".." in Path(relative).parts:
        raise ValueError("Evidence paths must stay inside their campaign directory")
    path = root / relative
    if any(parent.is_symlink() for parent in (path, *path.parents) if parent != root.parent):
        raise ValueError("Evidence paths must not traverse symlinks")
    if not path.is_file() or not path.resolve().is_relative_to(root.resolve()):
        raise ValueError("A required evidence file is missing or not regular")
    return path


def bind_files(root: Path, paths: list[Path]) -> dict:
    bound = {}
    for path in paths:
        relative = Path(path).relative_to(root).as_posix()
        if relative in bound:
            raise ValueError("A file was bound more than once")
        checked = _regular_path(root, relative)
        bound[relative] = {"bytes": checked.stat().st_size, "sha256": sha256_file(checked)}
    return bound


def verify_bound_files(root: Path, bound: dict) -> None:
    if not isinstance(bound, dict) or not bound:
        raise ValueError("A nonempty file identity map is required")
    for relative, record in bound.items():
        if not isinstance(record, dict) or not HEX256.fullmatch(str(record.get("sha256", ""))):
            raise ValueError("An evidence hash is invalid")
        path = _regular_path(root, relative)
        if type(record.get("bytes")) is not int or path.stat().st_size != record["bytes"] or sha256_file(path) != record["sha256"]:
            raise ValueError(f"Evidence bytes changed: {relative}")


def directory_bytes(root: Path) -> int:
    total = 0
    for path in Path(root).rglob("*"):
        try:
            observed = path.lstat()
        except FileNotFoundError:
            # Atomic publication can remove a pending name between enumeration
            # and stat. The next/final scan sees its published name. This narrow
            # disk race must never excuse a missing process identity or RSS read.
            continue
        if stat.S_ISLNK(observed.st_mode):
            raise ValueError("Campaign output must not contain symlinks")
        if stat.S_ISREG(observed.st_mode):
            total += observed.st_size
    return total


def _worker_is_exiting(identity: dict) -> bool:
    """Confirm a matching zombie/dead process; never excuse unreadable live RSS."""
    text = (Path("/proc") / str(identity["procfs_pid"]) / "stat").read_text()
    if _proc_stat_identity(text) != (identity["procfs_pid"], identity["start_ticks"]):
        raise ValueError("Exit observation belongs to a different process identity")
    return text.rpartition(")")[2].split()[0] in {"Z", "X", "x"}


def validate_execution_lock(lock: dict, root: Path, sources: dict, *, verify_all_files: bool = True) -> None:
    """Recheck source, all bound bytes and concrete prerequisite receipts."""
    if lock.get("schema_version") != "hadamard-model-execution-lock.v1" or lock.get("campaign_ready") is not True:
        raise ValueError("A qualified execution lock is required before test evaluation")
    if lock.get("source_sha256") != sources:
        raise ValueError("The adapter or frozen design changed after qualification")
    validate_review(lock.get("review", {}), sources)
    files = lock.get("files", {})
    required = {"preflight.json", "launch-preflight.json", "dependencies.json",
                "preparation.json", "development-proof.json"}
    # The parent verifies every bound artifact at the phase boundary. Each
    # worker rechecks the receipts it consumes, all selected token identities,
    # and the used graph at load time. Large unused profile JSON and reference
    # logits do not add an unmeasured hashing pass to all120 timing workers.
    direct_inputs = required | {"review.json", "dependency-lock.json", "export/export.json",
        "selection/selection.json", "selection/tokens.development.json",
        "selection/tokens.timing.json", "selection/tokens.quality.json"}
    if not isinstance(files, dict) or not direct_inputs.issubset(files):
        raise ValueError("The lock omits a launch prerequisite")
    selected = files if verify_all_files else {name: files[name] for name in direct_inputs}
    verify_bound_files(root, selected)
    for name in required:
        receipt = json.loads((root / name).read_text())
        if receipt.get("status") != "passed":
            raise ValueError(f"Launch prerequisite did not pass: {name}")
    manifest = json.loads(MANIFEST.read_text())
    for name in ("preflight.json", "launch-preflight.json"):
        host = json.loads((root / name).read_text())
        if host.get("schema_version") != "hadamard-model-preflight.v1" or not isinstance(host.get("environment"), dict):
            raise ValueError("The preflight must retain concrete environment observations")
        if preflight(manifest, host["environment"])["status"] != "passed":
            raise ValueError("The retained host does not meet the frozen resource gates")
    if json.loads((root / "review.json").read_text()) != lock["review"]:
        raise ValueError("The bound review differs from the execution lock")
    dependencies = json.loads((root / "dependencies.json").read_text())
    if dependencies.get("schema_version") != "hadamard-model-dependencies.v1":
        raise ValueError("A complete resolved dependency observation is required")
    dependency_path = dependencies.get("lock_file")
    if dependency_path not in lock["files"] or lock["files"][dependency_path]["sha256"] != dependencies.get("lock_sha256"):
        raise ValueError("Dependency wheel lock is missing or changed")
    if set(dependencies.get("tasks", {})) != {"converter", "runtime"}:
        raise ValueError("Both isolated environments must have observed import/ABI receipts")
    preparation = json.loads((root / "preparation.json").read_text())
    if set(preparation.get("checks", {})) != {"acquisition", "selection", "export", "reference", "onnx_parity", "source_identity"}:
        raise ValueError("Preparation lacks the complete launch checks")
    if not all(value is True for value in preparation["checks"].values()):
        raise ValueError("A preparation check failed")
    task_names = {"acquisition", "selection", "export", "reference", "onnx_parity"}
    if set(preparation.get("tasks", {})) != task_names:
        raise ValueError("Preparation must bind each observed worker task")
    development = json.loads((root / "development-proof.json").read_text())
    if development.get("feasible") is not True or development.get("quality_test_accessed") is not False:
        raise ValueError("A development-only feasibility proof is required")
    if set(development.get("tasks", {})) != {arm["id"] for arm in manifest["arms"]}:
        raise ValueError("Every arm needs a fresh-worker development cost observation")
    for field, ceiling in (("quality_seconds_upper", "quality_seconds"),
                           ("timing_seconds_upper", "timing_seconds"),
                           ("acquisition_export_seconds", "acquisition_and_export_seconds"),
                           ("projected_campaign_seconds", "campaign_seconds")):
        value = development.get(field)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 < value <= manifest["budgets"][ceiling]:
            raise ValueError("Development projection is missing, invalid or above a frozen budget")
    for relative in [*dependencies["tasks"].values(), *preparation["tasks"].values(), *development["tasks"].values()]:
        if relative not in lock["files"]:
            raise ValueError("A prerequisite task receipt is not bound in the execution lock")
        if not verify_all_files:
            verify_bound_files(root, {relative: files[relative]})
        task = json.loads((root / relative).read_text())
        if (task.get("status") != "passed" or task.get("stopped_for") is not None
                or type(task.get("valid_rss_samples")) is not int or task["valid_rss_samples"] <= 0
                or not task.get("worker_identity")
                or task.get("worker", {}).get("worker_identity") != task["worker_identity"]
                or task.get("worker", {}).get("status") != "passed"
                or task["worker"].get("inputs_unchanged") is not True
                or task["worker"].get("source_sha256_before") != sources
                or task["worker"].get("source_sha256_after") != sources):
            raise ValueError("A prerequisite worker did not pass with valid resource observations")
        for peak in (task.get("sampled_peak_worker_rss_bytes"), task["worker"].get("peak_worker_rss_bytes")):
            if type(peak) is not int or not 0 < peak <= manifest["budgets"]["process_memory_bytes"]:
                raise ValueError("A prerequisite worker exceeded its RSS budget")
        if (type(task.get("max_observed_cache_and_output_bytes")) is not int
                or not 0 <= task["max_observed_cache_and_output_bytes"] <= manifest["budgets"]["cache_and_output_bytes"]):
            raise ValueError("A prerequisite worker exceeded its cache/output budget")
    if lock.get("quality_test_accessed") is not False:
        raise ValueError("The launch lock must precede test evaluation")


def run_bounded_task(command: list[str], output: Path, *, deadline: float,
                     memory_limit: int, campaign_root: Path, cache_limit: int,
                     env: dict | None = None) -> dict:
    """Observe one identity-bound process; stop on the first resource breach."""
    output = new_directory(output)
    started = time.monotonic()
    if started >= deadline:
        raise TimeoutError("The phase deadline expired before starting a worker")
    environment = {**os.environ, **THREADS, "PYTHONHASHSEED": "0",
                   "PYTHONPATH": str(ROOT), "CUDA_VISIBLE_DEVICES": "",
                   "HF_HUB_DISABLE_TELEMETRY": "1", "HF_HUB_OFFLINE": "1",
                   "TRANSFORMERS_OFFLINE": "1"}
    if env:
        environment.update(env)
    identity, identity_hash, peak, samples = None, None, 0, 0
    stopped, error, max_bytes = None, None, 0
    last_disk_check = 0.0
    exit_transition_started, exit_transition_observations = None, 0
    with (output / "stdout.log").open("xb") as stdout, (output / "stderr.log").open("xb") as stderr:
        process = subprocess.Popen(command, cwd=ROOT, env=environment, stdout=stdout,
                                   stderr=stderr, start_new_session=True)
        while process.poll() is None:
            now = time.monotonic()
            try:
                identity_path = output / "worker-identity.json"
                if identity is None and identity_path.is_file():
                    identity = _load_worker_identity(identity_path, process.pid)
                    identity_hash = sha256_file(identity_path)
                if identity is not None:
                    peak = max(peak, _sample_worker_rss(identity))
                    samples += 1
                elif now - started > 5:
                    raise ValueError("Worker did not publish its process identity within five seconds")
                if now - last_disk_check >= 0.25:
                    max_bytes = max(max_bytes, directory_bytes(campaign_root))
                    last_disk_check = now
                if max_bytes > cache_limit:
                    stopped = "cache_and_output_budget"
                if peak > memory_limit:
                    stopped = "worker_rss_budget"
                if now >= deadline:
                    stopped = "phase_or_campaign_deadline"
            except (FileNotFoundError, ProcessLookupError) as exc:
                exited = process.poll() is not None
                try:
                    exiting = identity is not None and samples > 0 and _worker_is_exiting(identity)
                except FileNotFoundError:
                    exiting = exited
                except Exception as identity_error:
                    exiting = False
                    exc = identity_error
                if samples > 0 and (exited or exiting):
                    exit_transition_started = exit_transition_started or now
                    exit_transition_observations += 1
                    if now - exit_transition_started > 1:
                        stopped, error = "resource_monitor", {"type": "TimeoutError", "message": "Exited worker was not reaped within one second"}
                else:
                    stopped, error = "resource_monitor", {"type": type(exc).__name__, "message": str(exc)}
            except Exception as exc:
                stopped, error = "resource_monitor", {"type": type(exc).__name__, "message": str(exc)}
            if now >= deadline:
                stopped = "phase_or_campaign_deadline"
            if stopped:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                break
            time.sleep(min(0.05, max(0, deadline - time.monotonic())))
        returncode = process.wait()
    try:
        _require_rss_observations(identity, samples, peak)
        if sha256_file(output / "worker-identity.json") != identity_hash:
            raise ValueError("Worker identity bytes changed during the observation")
        max_bytes = max(max_bytes, directory_bytes(campaign_root))
        if max_bytes > cache_limit:
            stopped = stopped or "cache_and_output_budget"
        if time.monotonic() >= deadline:
            stopped = stopped or "phase_or_campaign_deadline"
    except Exception as exc:
        stopped, error = stopped or "resource_monitor", {"type": type(exc).__name__, "message": str(exc)}
    worker = None
    worker_path = output / "worker-result.json"
    if worker_path.is_file():
        try:
            worker = json.loads(worker_path.read_text())
            if worker.get("worker_identity") != identity:
                raise ValueError("Worker receipt does not match its observed process")
            if type(worker.get("peak_worker_rss_bytes")) is not int or not 0 < worker["peak_worker_rss_bytes"] <= memory_limit:
                stopped = stopped or "os_peak_worker_rss_budget"
        except Exception as exc:
            stopped, error = stopped or "worker_receipt", {"type": type(exc).__name__, "message": str(exc)}
    passed = returncode == 0 and stopped is None and worker is not None and worker.get("status") == "passed"
    result = {"schema_version": "hadamard-model-task.v1", "status": "passed" if passed else "failed",
              "command": command, "returncode": returncode, "stopped_for": stopped, "monitor_error": error,
              "elapsed_seconds": time.monotonic() - started, "worker_identity": identity,
              "worker_identity_sha256": identity_hash, "sampled_peak_worker_rss_bytes": peak,
              "valid_rss_samples": samples, "rss_sampling_interval_seconds": 0.05,
              "verified_exit_transition_observations": exit_transition_observations,
              "max_observed_cache_and_output_bytes": max_bytes, "memory_limit_bytes": memory_limit,
              "worker_result_sha256": sha256_file(worker_path) if worker_path.is_file() else None,
              "worker": worker, "thread_environment": THREADS,
              "limitation": "Sampling is an observation/termination guard, not an instantaneous kernel allocation cap."}
    write_json(output / "task-receipt.json", result)
    return result
