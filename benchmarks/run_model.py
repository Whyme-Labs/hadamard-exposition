#!/usr/bin/env python3
"""Run the frozen Pythia campaign only after its concrete launch gates pass."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import resource
import shutil
import subprocess
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from benchmarks.campaign_guard import (MANIFEST, bind_files, directory_bytes,
    new_directory, preflight, run_bounded_task, sha256_file, source_hashes,
    utc_now, validate_execution_lock, validate_review, verify_bound_files, write_json)
from benchmarks.qualify import _publish_worker_identity


class CampaignBlocked(RuntimeError):
    """A retained prerequisite prevents model or quality execution."""


def _read(path: Path) -> dict:
    return json.loads(Path(path).read_text())


def _copy_new(source: Path, target: Path) -> None:
    source = Path(source)
    if source.is_symlink() or not source.is_file():
        raise ValueError("A regular, non-symlink input receipt is required")
    with source.open("rb") as src, target.open("xb") as dst:
        shutil.copyfileobj(src, dst)
    if sha256_file(source) != sha256_file(target):
        raise ValueError("Input receipt changed while it was copied")


def verify_review_commit(review: dict, sources: dict) -> None:
    """Verify that the named reviewed Git object contains these exact sources."""
    validate_review(review, sources)
    commit = review["reviewed_commit"]
    tree = subprocess.check_output(["git", "rev-parse", commit + "^{tree}"], cwd=ROOT, text=True).strip()
    if tree != review["reviewed_tree"]:
        raise ValueError("The reviewed commit/tree pair does not match Git")
    for path, expected in sources.items():
        content = subprocess.check_output(["git", "show", f"{commit}:{path}"], cwd=ROOT)
        if hashlib.sha256(content).hexdigest() != expected:
            raise ValueError(f"The reviewed Git commit does not contain current source: {path}")


def load_tokens(campaign: Path, role: str, *, execution_lock: dict | None = None) -> list[dict]:
    """Check selected input bytes; quality tokens require a qualified lock first."""
    if role not in {"development", "timing", "quality"}:
        raise ValueError("Unknown data role")
    if role == "quality":
        if execution_lock is None:
            raise CampaignBlocked("Quality tokens cannot reach a model before execution qualification")
        validate_execution_lock(execution_lock, campaign, source_hashes(), verify_all_files=False)
    selection = _read(campaign / "selection/selection.json")
    if selection.get("status") != "complete" or selection.get("role_disjointness") != "passed":
        raise ValueError("The complete disjoint role selection is required")
    artifact = selection["local_token_files"][role]
    relative = "selection/" + artifact["path"]
    verify_bound_files(campaign, {relative: {"bytes": artifact["bytes"], "sha256": artifact["sha256"]}})
    content = _read(campaign / relative)
    if content.get("schema_version") != "hadamard-model-token-prefixes.v1" or content.get("role") != role:
        raise ValueError("Local token role differs from its selection receipt")
    records = content["records"]
    public = [{key: value for key, value in record.items() if key != "token_ids"} for record in records]
    if public != selection["roles"][role]:
        raise ValueError("Local token identities differ from the public selection")
    import numpy as np
    from benchmarks.contract import assert_disjoint_roles

    assert_disjoint_roles(selection["roles"])
    config = _read(MANIFEST)["dataset"]["roles"][role]
    if len(records) != config["articles"]:
        raise ValueError("The role has an incorrect article count")
    for record in records:
        tokens = record["token_ids"]
        if (record.get("role") != role or record.get("split") != config["split"]
                or len(tokens) != config["tokens_per_article"]
                or any(type(token) is not int or not 0 <= token < 50304 for token in tokens)):
            raise ValueError("The token prefix differs from the frozen role/vocabulary")
        if hashlib.sha256(np.asarray(tokens, dtype="<u4").tobytes()).hexdigest() != record["token_sha256"]:
            raise ValueError("The token-prefix content hash is invalid")
    return records


def _environment_probe(campaign: Path, name: str) -> dict:
    import importlib.metadata
    import numpy as np
    import onnx
    import onnxruntime as ort
    from onnx import TensorProto, helper, numpy_helper
    from benchmarks.dependency_lock import validate_environment

    locked = _read(campaign / "dependency-lock.json")
    if locked.get("manifest_sha256") != sha256_file(MANIFEST) or name not in {"converter", "runtime"}:
        raise ValueError("Dependency lock does not match this manifest/environment")
    result = validate_environment(locked["environments"][name])
    x = np.arange(6, dtype=np.float32).reshape(2, 3)
    w = np.arange(6, dtype=np.float32).reshape(3, 2)
    graph = helper.make_model(helper.make_graph(
        [helper.make_node("MatMul", ["x", "w"], ["y"])], "ABI",
        [helper.make_tensor_value_info("x", TensorProto.FLOAT, [2, 3])],
        [helper.make_tensor_value_info("y", TensorProto.FLOAT, [2, 2])],
        [numpy_helper.from_array(w, "w")]), opset_imports=[helper.make_opsetid("", 18)], ir_version=10)
    options = ort.SessionOptions()
    options.intra_op_num_threads = options.inter_op_num_threads = 1
    options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_DISABLE_ALL
    options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
    session = ort.InferenceSession(graph.SerializeToString(), options, providers=["CPUExecutionProvider"])
    np.testing.assert_array_equal(session.run(None, {"x": x})[0], x @ w)
    if name == "converter":
        import torch
        import transformers
        import datasets
        import tokenizers
        import safetensors
        import pyarrow as pa
        import pyarrow.parquet as pq

        torch.set_num_threads(1)
        torch.set_num_interop_threads(1)
        np.testing.assert_array_equal((torch.from_numpy(x) @ torch.from_numpy(w)).numpy(), x @ w)
        shared = torch.from_numpy(x)
        shared[0, 0] = 99
        if x[0, 0] != 99:
            raise ValueError("The Torch/NumPy sharing probe failed")
        sink = pa.BufferOutputStream()
        pq.write_table(pa.table({"text": ["one", "two"]}), sink)
        if pq.read_table(pa.BufferReader(sink.getvalue())).column("text").to_pylist() != ["one", "two"]:
            raise ValueError("The Arrow/Parquet ABI probe failed")
    result.update({"environment": name, "numpy_onnx_abi": "passed",
                   "torch_arrow_import_abi": "passed" if name == "converter" else "not applicable",
                   "python_executable": sys.executable, "python_prefix": sys.prefix,
                   "model_or_dataset_accessed": False})
    return result


def _arm(campaign: Path, arm_id: str) -> dict:
    matches = [item for item in _read(campaign / "export/export.json")["arms"] if item["arm"] == arm_id]
    if len(matches) != 1:
        raise ValueError("An exact exported arm is required")
    return matches[0]


def _quality_pair(campaign: Path, task_output: Path, record: dict) -> dict:
    """Compare one FP32 article in memory, avoiding a3.08GiB logit cache."""
    import numpy as np
    from benchmarks.contract import shifted_nll
    from benchmarks.model_runtime import compare_logits, create_session

    tokens = np.asarray(record["token_ids"], dtype=np.int64)[None, :]
    receipt = {"status": "failed", "article_id": record["article_id"],
               "losses": {}, "runtime": {}}
    baseline = None
    try:
        for arm_id in ("fp32_original", "fp32_rotated"):
            arm = _arm(campaign, arm_id)
            with create_session(campaign / "export" / arm["path"], task_output / arm_id,
                                arm_receipt=arm, profile=False) as session:
                logits, cache = session.step(tokens, None)
                del cache
                receipt["losses"][arm_id] = {"article_id": record["article_id"],
                                            **shifted_nll(logits[0], record["token_ids"])}
            receipt["runtime"][arm_id] = session.evidence
            if arm_id == "fp32_original":
                baseline = logits
            else:
                receipt["logit_control"] = compare_logits(logits, baseline)
                if not receipt["logit_control"]["passed"]:
                    raise CampaignBlocked("The quality FP32 rotation control failed")
        receipt["status"] = "passed"
    except Exception as error:
        receipt["error"] = {"type": type(error).__name__, "message": str(error)}
        raise
    finally:
        write_json(task_output / "fp32-pair.json", receipt)
    return receipt


def _quality_quantized(campaign: Path, task_output: Path, records: list[dict], arm_id: str) -> dict:
    import numpy as np
    from benchmarks.contract import shifted_nll
    from benchmarks.model_runtime import create_session

    arm = _arm(campaign, arm_id)
    if arm_id not in {"w4a32_g32_original", "w4a32_g32_rotated", "w4a32_g16_original", "w4a32_g16_rotated"}:
        raise ValueError("This task accepts only a frozen quantized arm")
    losses = []
    with create_session(campaign / "export" / arm["path"], task_output / "session",
                        arm_receipt=arm, profile=False) as session:
        for index, record in enumerate(records):
            logits, cache = session.step(np.asarray(record["token_ids"], dtype=np.int64)[None, :], None)
            loss = {"article_id": record["article_id"], **shifted_nll(logits[0], record["token_ids"])}
            losses.append(loss)
            write_json(task_output / f"article-{index:02d}.json", loss)
            del logits, cache
    return {"arm": arm_id, "losses": losses, "runtime": session.evidence}


def execute_task(config: dict, task_output: Path) -> dict:
    """Called only in an isolated, observed child process."""
    campaign = Path(config["campaign_root"])
    manifest = _read(MANIFEST)
    if config.get("source_sha256") != source_hashes():
        raise CampaignBlocked("Worker sources differ from the parent's frozen inputs")
    kind = config["kind"]
    if kind == "dependencies":
        return _environment_probe(campaign, config["environment"])
    if kind == "acquisition":
        from benchmarks.model_acquire import acquire
        return acquire(manifest, campaign / "artifacts", deadline_monotonic=config["deadline"])
    if kind == "selection":
        from benchmarks.model_acquire import select_roles
        return select_roles(manifest, campaign / "artifacts", campaign / "selection", deadline_monotonic=config["deadline"])
    if kind == "export":
        from benchmarks.model_acquire import verify_acquisition
        from benchmarks.model_export import export_all
        verify_acquisition(manifest, campaign / "artifacts")
        return export_all(campaign / "artifacts/model", campaign / "export")
    if kind in {"reference", "onnx_parity", "development_cost"}:
        from benchmarks.model_runtime import (development_cost_fixture, run_development_cost,
            run_onnx_development, run_reference_development)
        records = load_tokens(campaign, "development")
        if kind == "reference":
            return run_reference_development(campaign / "artifacts/model", records, campaign / "reference")
        if kind == "onnx_parity":
            return run_onnx_development(campaign / "export", _read(campaign / "export/export.json"),
                                       records, campaign / "reference", campaign / "parity")
        arm = _arm(campaign, config["arm"])
        return run_development_cost(campaign / "export" / arm["path"], arm,
                                    development_cost_fixture(records[0]), task_output / "cost")
    if kind in {"quality_pair", "quality_quantized", "timing"}:
        lock_path = campaign / "execution-lock.json"
        if sha256_file(lock_path) != config["execution_lock_sha256"]:
            raise CampaignBlocked("Execution lock changed before a measurement worker")
        lock = _read(lock_path)
        if kind.startswith("quality"):
            records = load_tokens(campaign, "quality", execution_lock=lock)
            if kind == "quality_pair":
                return _quality_pair(campaign, task_output, records[config["article_index"]])
            return _quality_quantized(campaign, task_output, records, config["arm"])
        from benchmarks.model_metrics import run_timing_worker, timing_schedule
        from benchmarks.model_runtime import create_session, current_rss_bytes

        validate_execution_lock(lock, campaign, source_hashes(), verify_all_files=False)
        block = timing_schedule()[config["block_index"]]
        records = load_tokens(campaign, "timing")
        arm = _arm(campaign, config["arm"])
        with create_session(campaign / "export" / arm["path"], task_output / "session",
                            arm_receipt=arm, profile=False) as session:
            measured = run_timing_worker(session.step, records[block["article_index"]]["token_ids"], current_rss_bytes)
        measured.update({"block_index": config["block_index"], "article_index": block["article_index"],
                         "arm": config["arm"], "runtime": session.evidence,
                         "peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024})
        return measured
    raise ValueError("Unknown worker task")


def worker(config_path: Path, output: Path) -> int:
    started = time.monotonic()
    identity = _publish_worker_identity(output)
    before = source_hashes()
    receipt = {"status": "failed", "worker_identity": identity, "source_sha256_before": before}
    try:
        receipt["result"] = execute_task(_read(config_path), output)
        receipt["status"] = "passed"
    except Exception as error:
        receipt["error"] = {"type": type(error).__name__, "message": str(error)}
        traceback.print_exc()
    receipt["source_sha256_after"] = source_hashes()
    receipt["inputs_unchanged"] = before == receipt["source_sha256_after"]
    if not receipt["inputs_unchanged"]:
        receipt["status"] = "failed"
    receipt["elapsed_seconds"] = time.monotonic() - started
    receipt["peak_worker_rss_bytes"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
    write_json(output / "worker-result.json", receipt)
    return 0 if receipt["status"] == "passed" else 1


def record_preflight(output: Path) -> dict:
    output = new_directory(output)
    before = source_hashes()
    receipt = preflight(_read(MANIFEST), disk_path=output)
    receipt.update({"source_sha256_before": before, "source_sha256_after": source_hashes()})
    receipt["inputs_unchanged"] = receipt["source_sha256_before"] == receipt["source_sha256_after"]
    if not receipt["inputs_unchanged"]:
        receipt["status"] = "blocked"
        receipt["errors"].append("Sources changed during the preflight")
    write_json(output / "preflight.json", receipt)
    return receipt


def development_projection(parity: dict, cost_tasks: dict, preparation_elapsed: float,
                           manifest: dict) -> dict:
    """A fixed, conservative estimate, calculated before any quality model call."""
    arms = [arm["id"] for arm in manifest["arms"]]
    if parity.get("status") != "passed" or set(parity.get("arms", {})) != set(arms) or set(cost_tasks) != set(arms):
        raise ValueError("The projection requires parity and a fresh cost worker for all six arms")

    def seconds(value):
        if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value) or value <= 0:
            raise ValueError("Observed preparation times must be finite and positive")
        return float(value)

    seconds(preparation_elapsed)
    parity_wall = sum(seconds(parity["arms"][arm]["parity_wall_seconds"]) for arm in arms)
    costs, startup = [], []
    for arm in arms:
        task = cost_tasks[arm]
        if task.get("status") != "passed" or task.get("worker", {}).get("status") != "passed":
            raise ValueError("A failed cost worker cannot qualify the campaign")
        observed = task["worker"]["result"]
        if observed.get("status") != "passed" or observed.get("arm") != arm:
            raise ValueError("Development cost observation has the wrong arm or status")
        elapsed = seconds(task["elapsed_seconds"])
        inner = seconds(observed["worker_wall_seconds"])
        if inner > elapsed:
            raise ValueError("Worker cost time exceeds the complete observed child lifetime")
        costs.append(elapsed)
        startup.append(elapsed - inner)
    margin = 1.25
    # Each arm's parity observation includes two full-prefix calls plus its
    # prefill/cache calls, comparisons, load, validation and profile closure.
    # Multiplying that entire six-arm amount by32 deliberately overcounts the
    # quality work. The real quality plan has68 graph loads and36 fresh workers.
    quality = margin * (32 * parity_wall + 36 * max(startup))
    timing = margin * 20 * sum(costs)
    budget = manifest["budgets"]
    total = budget["acquisition_and_export_seconds"] + quality + timing
    gates = {"preparation": preparation_elapsed <= budget["acquisition_and_export_seconds"],
             "quality": quality <= budget["quality_seconds"],
             "timing": timing <= budget["timing_seconds"],
             "campaign": total <= budget["campaign_seconds"]}
    return {"schema_version": "hadamard-model-development-proof.v1",
            "status": "passed" if all(gates.values()) else "blocked", "feasible": all(gates.values()),
            "quality_test_accessed": False, "quality_seconds_upper": quality,
            "timing_seconds_upper": timing, "acquisition_export_seconds": preparation_elapsed,
            "projected_campaign_seconds": total, "gates": gates,
            "margin_multiplier": margin, "observed_parity_wall_seconds_sum": parity_wall,
            "observed_cost_child_elapsed_seconds_sum": sum(costs),
            "maximum_observed_child_startup_and_closure_overhead_seconds": max(startup),
            "quality_graph_loads": 68, "quality_child_workers": 36, "timing_child_workers": 120,
            "preparation_seconds_reserved_in_total": budget["acquisition_and_export_seconds"],
            "quality_formula": "1.25*(32*sum(six parity wall times)+36*max(child elapsed-cost wall time))",
            "timing_formula": "1.25*20*sum(six fresh cost child elapsed times)",
            "limitation": "A development estimate, not a guaranteed bound; live phase, RSS and disk guards remain mandatory."}


def _preparation_checks(tasks: dict, sources: dict) -> dict:
    """Require actual task outputs before publishing preparation as complete."""
    result = {name: task["worker"]["result"] for name, task in tasks.items()}
    export = result["export"]
    arms = [arm["id"] for arm in _read(MANIFEST)["arms"]]
    counts = export.get("counts", {})
    counted = {"parameters", "buffers", "state_dict"}.issubset(counts)
    for name in ("parameters", "buffers", "state_dict"):
        values = counts.get(name, {})
        counted = counted and all(type(values.get(key)) is int and values[key] >= 0
                                  for key in ("tensors", "elements", "bytes"))
        if name != "buffers":
            counted = counted and all(values.get(key, 0) > 0 for key in ("tensors", "elements", "bytes"))
    checks = {"acquisition": result["acquisition"].get("status") == "complete",
              "selection": result["selection"].get("status") == "complete"
                  and result["selection"].get("role_disjointness") == "passed"
                  and result["selection"].get("quality_evaluation_started") is False,
              "export": export.get("schema_version") == "hadamard-model-export.v1" and counted
                  and [arm.get("arm") for arm in export.get("arms", [])] == arms,
              "reference": result["reference"].get("status") == "passed",
              "onnx_parity": result["onnx_parity"].get("status") == "passed"
                  and set(result["onnx_parity"].get("gates", {})) == {
                      "every_arm_cache_path", "original_vs_transformers", "rotated_vs_original"}
                  and all(value is True for value in result["onnx_parity"].get("gates", {}).values()),
              "source_identity": source_hashes() == sources}
    return checks


def _quality_phase(launch, check_budget, output: Path, lock_sha256: str, arm_ids: list[str]) -> dict:
    from benchmarks.model_metrics import summarize_quality

    losses = {arm: [] for arm in arm_ids}
    controls, tasks = [], []
    for index in range(32):
        task = launch(f"quality-pair-{index:02d}", "quality_pair", "runtime",
                      article_index=index, execution_lock_sha256=lock_sha256)
        pair = task["worker"]["result"]
        tasks.append(task["receipt_path"])
        controls.append({"article_id": pair["article_id"], **pair["logit_control"]})
        for arm, loss in pair["losses"].items():
            losses[arm].append(loss)
    for arm in arm_ids[2:]:
        task = launch(f"quality-{arm}", "quality_quantized", "runtime", arm=arm,
                      execution_lock_sha256=lock_sha256)
        tasks.append(task["receipt_path"])
        losses[arm] = task["worker"]["result"]["losses"]
    summary = summarize_quality(losses)
    summary.update({"schema_version": "hadamard-model-quality.v1", "status": "completed",
                    "fp32_logit_controls": controls,
                    "float_controls_passed": all(control["passed"] for control in controls)
                        and summary["primary_gates"]["fp32_aggregate_nll_control"],
                    "tasks": tasks, "records": losses})
    write_json(output / "quality.json", summary)
    check_budget()
    if not summary["float_controls_passed"]:
        raise CampaignBlocked("The full quality FP32 controls failed; retained all observed losses")
    return summary


def _timing_phase(launch, check_budget, output: Path, lock_sha256: str, arm_ids: list[str]) -> dict:
    from benchmarks.model_metrics import summarize_timing, timing_schedule

    records = {arm: [] for arm in arm_ids}
    schedule, tasks = timing_schedule(), []
    write_json(output / "timing-schedule.json", schedule)
    for block in schedule:
        for arm in block["arms"]:
            task = launch(f"timing-{block['block_index']:02d}-{arm}", "timing", "runtime",
                          arm=arm, block_index=block["block_index"], execution_lock_sha256=lock_sha256)
            tasks.append(task["receipt_path"])
            record = task["worker"]["result"]
            if (record["arm"] != arm or record["block_index"] != block["block_index"]
                    or record["article_index"] != block["article_index"]):
                raise ValueError("Timing worker differs from its prescribed paired block")
            # Both process measurements are retained. The endpoint is the OS
            # high-water mark, which includes the complete isolated worker.
            if record["peak_rss_bytes"] > task["worker"]["peak_worker_rss_bytes"]:
                raise ValueError("Timing RSS observation exceeds the worker's final OS high-water mark")
            record["peak_rss_bytes"] = task["worker"]["peak_worker_rss_bytes"]
            record["sampled_peak_rss_bytes"] = task["sampled_peak_worker_rss_bytes"]
            records[arm].append(record)
    summary = summarize_timing(records)
    summary.update({"schema_version": "hadamard-model-timing.v1", "status": "completed",
                    "schedule": schedule, "tasks": tasks, "records": records})
    write_json(output / "timing.json", summary)
    check_budget()
    return summary


def run_campaign(output: Path, converter_python: Path | None, runtime_python: Path | None,
                 dependency_lock: Path | None, review_path: Path | None) -> dict:
    """Complete the frozen campaign or retain the first concrete blocking gate."""
    output = new_directory(output)
    started = time.monotonic()
    manifest, sources = _read(MANIFEST), source_hashes()
    budgets = manifest["budgets"]
    deadline = started + budgets["campaign_seconds"]
    phase_started, phase_deadline, phase = started, started + budgets["acquisition_and_export_seconds"], "preparation"
    receipt = {"schema_version": "hadamard-model-campaign.v1", "campaign_id": manifest["campaign_id"],
               "started_utc": utc_now(), "status": "blocked", "campaign_ready": False,
               "quality_test_accessed": False, "model_or_dataset_accessed": False,
               "source_sha256_before": sources, "phase_elapsed_seconds": {}, "tasks": [], "errors": []}
    build = ROOT / "build"
    build.mkdir(exist_ok=True)
    lock_file = build / "model-campaign.process-lock"
    if lock_file.is_symlink():
        raise ValueError("The campaign process lock must not be a symlink")
    process_lock = lock_file.open("a+")

    def check_budget():
        if source_hashes() != sources:
            raise CampaignBlocked("Sources changed during the campaign")
        if time.monotonic() >= min(deadline, phase_deadline):
            raise CampaignBlocked(f"The {phase} phase or outer campaign deadline expired")
        if directory_bytes(output) > budgets["cache_and_output_bytes"]:
            raise CampaignBlocked("Campaign cache/output exceeds the frozen 4 GiB limit")

    def launch(name, kind, interpreter_name, **arguments):
        check_budget()
        config = {"kind": kind, "campaign_root": str(output), "source_sha256": sources,
                  "deadline": min(deadline, phase_deadline), **arguments}
        config_path, task_output = output / "tasks" / f"{name}.json", output / "workers" / name
        write_json(config_path, config)
        command = [str(interpreters[interpreter_name]), str(ROOT / "benchmarks/run_model.py"), "worker",
                   "--config", str(config_path), "--output", str(task_output)]
        task = run_bounded_task(command, task_output, deadline=min(deadline, phase_deadline),
            memory_limit=budgets["process_memory_bytes"], campaign_root=output,
            cache_limit=budgets["cache_and_output_bytes"], env={
                "HF_HOME": str(output / "library-cache"),
                "TRANSFORMERS_CACHE": str(output / "library-cache"),
                "MPLCONFIGDIR": str(output / "plot-cache")})
        relative = (task_output / "task-receipt.json").relative_to(output).as_posix()
        receipt["tasks"].append({"name": name, "kind": kind, "phase": phase,
                                 "status": task["status"], "receipt_path": relative})
        if task["status"] != "passed":
            raise CampaignBlocked(f"Worker {name} failed; retained {relative}")
        task["receipt_path"] = relative
        check_budget()
        return task

    try:
        try:
            fcntl.flock(process_lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise CampaignBlocked("Another campaign owns this repository's model-worker lock") from error
        host = preflight(manifest, disk_path=output)
        write_json(output / "preflight.json", host)
        if host["status"] != "passed":
            receipt["errors"].extend(host["errors"])
            raise CampaignBlocked("The frozen host preflight failed before acquisition or model loading")
        from benchmarks.contract import validate_manifest
        validate_manifest(manifest)
        if any(value is None for value in (converter_python, runtime_python, dependency_lock, review_path)):
            raise CampaignBlocked("Both isolated interpreters, the reviewed dependency lock and source review are required")
        interpreters = {"converter": Path(converter_python).absolute(), "runtime": Path(runtime_python).absolute()}
        if any(not path.is_file() or not os.access(path, os.X_OK) for path in interpreters.values()):
            raise CampaignBlocked("An isolated interpreter is missing or not executable")
        if sha256_file(dependency_lock) != sources.get("benchmarks/model-dependencies-v1.json"):
            raise CampaignBlocked("Use the exact complete wheel lock included in the reviewed source")
        review = _read(review_path)
        verify_review_commit(review, sources)
        _copy_new(review_path, output / "review.json")
        _copy_new(dependency_lock, output / "dependency-lock.json")
        (output / "tasks").mkdir()
        (output / "workers").mkdir()
        dependency_tasks = {name: launch(f"dependencies-{name}", "dependencies", name, environment=name)
                            for name in ("converter", "runtime")}
        prefixes = {task["worker"]["result"]["python_prefix"] for task in dependency_tasks.values()}
        if len(prefixes) != 2:
            raise CampaignBlocked("Converter and runtime must use separate verified environments")
        write_json(output / "dependencies.json", {"schema_version": "hadamard-model-dependencies.v1",
            "status": "passed", "lock_file": "dependency-lock.json",
            "lock_sha256": sha256_file(output / "dependency-lock.json"),
            "tasks": {name: task["receipt_path"] for name, task in dependency_tasks.items()}})
        preparation = {}
        for kind, environment in (("acquisition", "converter"), ("selection", "converter"),
                                  ("export", "converter"), ("reference", "converter"), ("onnx_parity", "runtime")):
            if kind == "acquisition":
                receipt["model_or_dataset_accessed"] = True
            preparation[kind] = launch(kind, kind, environment)
        checks = _preparation_checks(preparation, sources)
        preparation_receipt = {"schema_version": "hadamard-model-preparation.v1",
            "status": "passed" if all(checks.values()) else "failed", "checks": checks,
            "tasks": {name: task["receipt_path"] for name, task in preparation.items()},
            "parameter_buffer_counts": preparation["export"]["worker"]["result"].get("counts")}
        write_json(output / "preparation.json", preparation_receipt)
        if not all(checks.values()):
            raise CampaignBlocked("Preparation did not establish every required model/data/parity check")
        arm_ids = [arm["id"] for arm in manifest["arms"]]
        cost_tasks = {arm: launch(f"development-cost-{arm}", "development_cost", "runtime", arm=arm) for arm in arm_ids}
        launch_host = preflight(manifest, disk_path=output)
        write_json(output / "launch-preflight.json", launch_host)
        if launch_host["status"] != "passed":
            raise CampaignBlocked("The reobserved host failed its pre-test launch gate")
        verify_review_commit(review, sources)
        # Bind the complete immutable preparation before estimating its elapsed
        # time. Final receipt/lock writes also remain inside the live600s guard.
        files = bind_files(output, sorted(path for path in output.rglob("*") if path.is_file()))
        proof = development_projection(preparation["onnx_parity"]["worker"]["result"],
                                       cost_tasks, time.monotonic() - started, manifest)
        proof["tasks"] = {arm: task["receipt_path"] for arm, task in cost_tasks.items()}
        write_json(output / "development-proof.json", proof)
        if not proof["feasible"]:
            raise CampaignBlocked("The single development observation cannot fit the frozen campaign budgets")
        files.update(bind_files(output, [output / "development-proof.json"]))
        execution_lock = {"schema_version": "hadamard-model-execution-lock.v1", "campaign_ready": True,
            "source_sha256": sources, "review": review, "files": files,
            "quality_test_accessed": False, "created_utc": utc_now(),
            "hardware_policy": "The observed architecture/CPU and conservative memory gate remain frozen."}
        validate_execution_lock(execution_lock, output, sources)
        write_json(output / "execution-lock.json", execution_lock)
        lock_sha256 = sha256_file(output / "execution-lock.json")
        check_budget()
        receipt["phase_elapsed_seconds"][phase] = time.monotonic() - phase_started
        receipt["campaign_ready"] = True
        receipt["execution_lock_sha256"] = lock_sha256

        phase, phase_started = "quality", time.monotonic()
        phase_deadline = min(deadline, phase_started + budgets["quality_seconds"])
        receipt["quality_test_accessed"] = True
        quality = _quality_phase(launch, check_budget, output, lock_sha256, arm_ids)
        receipt["phase_elapsed_seconds"][phase] = time.monotonic() - phase_started

        phase, phase_started = "timing", time.monotonic()
        phase_deadline = min(deadline, phase_started + budgets["timing_seconds"])
        validate_execution_lock(execution_lock, output, sources)
        timing = _timing_phase(launch, check_budget, output, lock_sha256, arm_ids)
        receipt["serialized_model_bytes"] = {arm["arm"]: arm["bytes"]
            for arm in preparation["export"]["worker"]["result"]["arms"]}
        receipt["packed_payload_bytes"] = {arm["arm"]: {
            "packed_code_bytes": arm["packed_code_bytes"], "scale_bytes": arm["scale_bytes"]}
            for arm in preparation["export"]["worker"]["result"]["arms"]}
        receipt["primary_gates"] = {**quality["primary_gates"], **timing["primary_gates"],
                                   "full_quality_float_controls": quality["float_controls_passed"]}
        receipt["adoption_candidate"] = all(receipt["primary_gates"].values())
        receipt["decision_scope"] = "This selected Pythia W4A32 treatment only; production validation is still required."
        check_budget()
        receipt["phase_elapsed_seconds"][phase] = time.monotonic() - phase_started
        receipt["status"] = "completed"
    except Exception as error:
        receipt["status"] = "blocked" if isinstance(error, CampaignBlocked) else "failed"
        receipt["errors"].append(str(error))
        receipt["error_type"] = type(error).__name__
        receipt["blocked_phase"] = phase
        receipt["phase_elapsed_seconds"][phase] = time.monotonic() - phase_started
    finally:
        receipt["finished_utc"] = utc_now()
        receipt["elapsed_seconds"] = time.monotonic() - started
        receipt["source_sha256_after"] = source_hashes()
        receipt["inputs_unchanged"] = sources == receipt["source_sha256_after"]
        receipt["retained_cache_and_output_bytes_before_final_receipt"] = directory_bytes(output)
        if not receipt["inputs_unchanged"]:
            receipt["status"] = "failed"
            receipt["errors"].append("Source identity changed before final receipt publication")
        if receipt["status"] == "completed" and time.monotonic() >= min(deadline, phase_deadline):
            receipt["status"] = "failed"
            receipt["errors"].append("The final summary exceeded a phase or outer deadline")
        final_size = len((json.dumps(receipt, indent=2, sort_keys=True, allow_nan=False) + "\n").encode())
        if receipt["retained_cache_and_output_bytes_before_final_receipt"] + final_size > budgets["cache_and_output_bytes"]:
            receipt["status"] = "failed"
            receipt["errors"].append("The retained final evidence exceeded the cache/output budget")
        if receipt["status"] != "completed":
            receipt["adoption_candidate"] = False
        write_json(output / "campaign.json", receipt)
        fcntl.flock(process_lock.fileno(), fcntl.LOCK_UN)
        process_lock.close()
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("preflight", "run", "worker"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--config", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--converter-python", type=Path)
    parser.add_argument("--runtime-python", type=Path)
    parser.add_argument("--dependency-lock", type=Path)
    parser.add_argument("--review", type=Path)
    args = parser.parse_args()
    if args.command == "worker":
        return worker(args.config, args.output)
    if args.command == "preflight":
        receipt = record_preflight(args.output)
    else:
        receipt = run_campaign(args.output, args.converter_python, args.runtime_python,
                               args.dependency_lock, args.review)
    print(json.dumps({"status": receipt["status"], "campaign_ready": receipt.get("campaign_ready", False),
                      "receipt_directory": str(args.output), "errors": receipt.get("errors", [])}))
    return 0 if receipt["status"] in {"passed", "completed"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
