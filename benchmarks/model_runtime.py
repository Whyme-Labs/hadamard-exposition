"""Development parity and cost fixtures for the frozen six-arm CPU campaign.

No function downloads inputs or opens quality data. Reference execution imports
Torch only inside the converter worker. ONNX execution checks the reviewed
export receipt's graph identity on every load, then keeps one session resident.
The outer runner owns source locks, resource limits and permission to evaluate
test prefixes. Numerical observations here cannot set campaign readiness.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
import gc
import hashlib
import json
import math
from numbers import Integral
import os
from pathlib import Path
import platform
import resource
import time

import numpy as np
import onnx
from onnx import TensorProto, helper
import onnxruntime as ort

from benchmarks.contract import ContractError, aggregate_nll, assert_disjoint_roles, shifted_nll
from benchmarks.model_export import (
    ARMS, INPUT_NAMES, MODEL_REVISION, OUTPUT_NAMES, SITES, file_sha256, model_inputs,
)
from benchmarks.model_metrics import ARM_IDS, run_timing_worker


_DATA_REVISION = "b08601e04326c79dfdd32d625aee71d232d685c3"
_DATA_CONFIG = "wikitext-2-raw-v1"
_CASES = {"full": 513, "prefill": 512, "cached": 1}
_ACTIVE_SESSION = False


def _new_json(path: Path, content: dict) -> None:
    with Path(path).open("x", encoding="utf8") as stream:
        json.dump(content, stream, indent=2, allow_nan=False)
        stream.write("\n")


def _array_hash(array: np.ndarray) -> str:
    values = np.asarray(array)
    digest = hashlib.sha256()
    # Logits have batch one, so iterating only their leading axis would still
    # copy the complete array. Hash small row chunks in canonical C order.
    if values.ndim == 0:
        digest.update(values.tobytes())
    else:
        rows = values.reshape(-1, values.shape[-1])
        for start in range(0, len(rows), 16):
            digest.update(memoryview(np.ascontiguousarray(rows[start:start + 16])).cast("B"))
    return digest.hexdigest()


def _array_identity(array: np.ndarray) -> dict:
    return {"shape": list(array.shape), "dtype": str(array.dtype),
            "bytes": int(array.nbytes), "array_sha256": _array_hash(array)}


def _checked_outputs(outputs: Sequence[np.ndarray], batch: int, sequence: int,
                     total_sequence: int) -> tuple[np.ndarray, tuple[np.ndarray, ...]]:
    if not isinstance(outputs, (tuple, list)) or len(outputs) != 13:
        raise ContractError("The model must return logits and all twelve cache outputs")
    logits = np.asarray(outputs[0])
    if logits.dtype != np.float32 or logits.shape != (batch, sequence, 50304):
        raise ContractError("Logits must preserve FP32 [batch,sequence,50304] shape")
    if not np.isfinite(logits).all():
        raise ContractError("Model logits must be finite")
    cache = tuple(np.asarray(value) for value in outputs[1:])
    for value in cache:
        if value.dtype != np.float32 or value.shape != (batch, 8, total_sequence, 64):
            raise ContractError("Every present cache must be FP32 [batch,8,total_sequence,64]")
        if not np.isfinite(value).all():
            raise ContractError("Model cache outputs must be finite")
    return logits, cache


def compare_logits(actual: np.ndarray, reference: np.ndarray) -> dict:
    """Full-array FP32 logit control, accumulating squared norms in float64.

    The function accepts [sequence,vocabulary] or batch-preserving arrays. It
    processes bounded chunks, so callers can pass local memory-mapped logits.
    Aggregate NLL control is separate and must use all selected target counts.
    """
    actual, reference = np.asarray(actual), np.asarray(reference)
    if (actual.shape != reference.shape or actual.ndim < 2 or not all(actual.shape)
            or actual.dtype != np.float32 or reference.dtype != np.float32):
        raise ContractError("Parity needs nonempty, same-shaped FP32 logit arrays")
    a_rows, b_rows = actual.reshape(-1, actual.shape[-1]), reference.reshape(-1, reference.shape[-1])
    squared_errors, squared_references, maximum = [], [], 0.0
    for start in range(0, len(a_rows), 16):
        a = a_rows[start:start + 16].astype(np.float64)
        b = b_rows[start:start + 16].astype(np.float64)
        if not np.isfinite(a).all() or not np.isfinite(b).all():
            raise ContractError("Parity logits must be finite")
        difference = a - b
        squared_errors.append(float(np.sum(difference * difference)))
        squared_references.append(float(np.sum(b * b)))
        maximum = max(maximum, float(np.max(np.abs(difference))))
    denominator = math.sqrt(math.fsum(squared_references))
    numerator = math.sqrt(math.fsum(squared_errors))
    relative = numerator / denominator if denominator else (0.0 if numerator == 0 else None)
    passed = relative is not None and relative <= 1e-5 and maximum <= 1e-3
    return {"relative_frobenius_error": relative, "max_absolute_error": maximum,
            "relative_frobenius_max": 1e-5, "absolute_logit_error_max": 1e-3,
            "passed": passed, "shape": list(actual.shape)}


def _development_record(record: Mapping) -> tuple[dict, np.ndarray]:
    if not isinstance(record, Mapping):
        raise ContractError("A selected development record is required")
    required = {"role": "development", "split": "validation", "dataset_repo": "Salesforce/wikitext",
                "dataset_revision": _DATA_REVISION, "dataset_config": _DATA_CONFIG}
    if any(record.get(key) != value for key, value in required.items()):
        raise ContractError("Development execution accepts only the frozen validation role")
    row = record.get("start_row")
    if type(row) is not int or row < 0:
        raise ContractError("Development article start_row must be nonnegative")
    identity = f"{_DATA_REVISION}/{_DATA_CONFIG}/validation/{row}"
    if record.get("article_id") != identity:
        raise ContractError("Development article identity does not bind its source row")
    try:
        supplied = record["token_ids"]
        if not isinstance(supplied, (list, tuple)) or any(
                isinstance(value, (bool, np.bool_)) or not isinstance(value, Integral) for value in supplied):
            raise ValueError("Token IDs must be integer values, not booleans")
        values = np.asarray(supplied)
        feed = model_inputs(values)
    except (KeyError, TypeError, ValueError) as error:
        raise ContractError("Development token IDs violate the model input contract") from error
    tokens = feed["input_ids"]
    if tokens.shape != (1, 513):
        raise ContractError("Development must preserve the frozen 513-token prefix")
    digest = hashlib.sha256(tokens.astype("<u4").tobytes()).hexdigest()
    if record.get("token_sha256") != digest:
        raise ContractError("Development token bytes differ from their selected identity")
    text_digest = record.get("text_sha256")
    if not isinstance(text_digest, str) or len(text_digest) != 64 or any(c not in "0123456789abcdef" for c in text_digest):
        raise ContractError("The complete development article needs a SHA256 identity")
    public = {**required, "article_id": identity, "start_row": row,
              "text_sha256": text_digest, "token_sha256": digest, "prefix_tokens": 513}
    return public, tokens


def _development_records(records: Sequence[Mapping]) -> list[tuple[dict, np.ndarray]]:
    if not isinstance(records, Sequence) or len(records) != 2:
        raise ContractError("Both frozen development articles are required")
    values = [_development_record(record) for record in records]
    assert_disjoint_roles({"development": [public for public, _ in values]})
    if values[0][0]["start_row"] >= values[1][0]["start_row"]:
        raise ContractError("Development articles must remain in source row order")
    return values


def development_cost_fixture(record: Mapping) -> dict:
    """Cyclically extend one fixed development prefix for cost/cache-shape only.

    This is an artificial continuation, not additional source article text and
    not a quality endpoint. No extra tokenization, fitting or data access occurs.
    """
    public, source = _development_record(record)
    tokens = source[0, np.arange(640) % 513].tolist()
    return {"schema_version": "hadamard-development-cost-fixture.v1",
            "purpose": "synthetic_continuation_for_cost_and_cache_shape_only",
            "source_article": public,
            "mapping": {"rule": "source_index_equals_output_index_mod_513",
                        "original_indices_inclusive": [0, 512], "repeated_indices_inclusive": [0, 126]},
            "token_ids": tokens, "tokens": 640,
            "token_sha256": hashlib.sha256(np.asarray(tokens, dtype="<u4").tobytes()).hexdigest()}


def _validated_cost_fixture(fixture: Mapping) -> tuple[dict, list[int]]:
    if not isinstance(fixture, Mapping) or not isinstance(fixture.get("source_article"), Mapping):
        raise ContractError("A source-bound development cost fixture is required")
    tokens = fixture.get("token_ids")
    if not isinstance(tokens, list) or len(tokens) != 640:
        raise ContractError("The development cost fixture must contain exactly 640 tokens")
    expected = development_cost_fixture({**fixture["source_article"], "token_ids": tokens[:513]})
    if dict(fixture) != expected:
        raise ContractError("The cost fixture differs from the fixed cyclic development mapping")
    return {key: value for key, value in expected.items() if key != "token_ids"}, tokens


def _runtime_versions() -> dict:
    observed = {"python": platform.python_version(), "numpy": np.__version__,
                "onnx": onnx.__version__, "onnxruntime": ort.__version__}
    expected = {"python": "3.12.14", "numpy": "2.3.5", "onnx": "1.19.1", "onnxruntime": "1.23.2"}
    if observed != expected:
        raise ContractError(f"Runtime versions differ from the frozen contract: {observed}")
    return observed


def _graph_audit(graph_path: Path, receipt: Mapping) -> dict:
    """Bind the converter's full surgery audit to every loaded graph's bytes."""
    if not isinstance(receipt, Mapping) or receipt.get("arm") not in ARMS:
        raise ContractError("A reviewed export arm receipt is required")
    if (graph_path.name != receipt.get("path") or not graph_path.is_file()
            or graph_path.stat().st_size != receipt.get("bytes")
            or file_sha256(graph_path) != receipt.get("sha256")):
        raise ContractError("Graph bytes or filename differ from the reviewed export receipt")
    graph = onnx.load(graph_path, load_external_data=False)
    if any(tensor.external_data or tensor.data_location == TensorProto.EXTERNAL for tensor in graph.graph.initializer):
        raise ContractError("The frozen export must be a standalone graph")
    onnx.checker.check_model(graph)
    arm = receipt["arm"]
    rotated, group = ARMS[arm]
    opsets = {item.domain: item.version for item in graph.opset_import}
    expected_opsets = {"": 18, **({"com.microsoft": 1} if group else {})}
    if graph.ir_version != 10 or opsets != expected_opsets:
        raise ContractError("Graph IR/opsets differ from the frozen implementation")
    if ([value.name for value in graph.graph.input] != list(INPUT_NAMES)
            or [value.name for value in graph.graph.output] != list(OUTPUT_NAMES)):
        raise ContractError("The graph must retain every ordered token/logit/cache IO")
    for index, value in enumerate(graph.graph.input):
        tensor = value.type.tensor_type
        dimensions = tensor.shape.dim
        if index == 0:
            valid = tensor.elem_type == TensorProto.INT64 and len(dimensions) == 2
            dynamic_axes = (0, 1)
        else:
            valid = (tensor.elem_type == TensorProto.FLOAT and len(dimensions) == 4
                     and dimensions[1].dim_value == 8 and dimensions[3].dim_value == 64)
            dynamic_axes = (0, 2)
        if not valid or any(not dimensions[axis].dim_param for axis in dynamic_axes):
            raise ContractError("Model inputs must preserve the frozen dynamic dimensions and precision")
    for index, value in enumerate(graph.graph.output):
        tensor = value.type.tensor_type
        dimensions = tensor.shape.dim
        if index == 0:
            valid = tensor.elem_type == TensorProto.FLOAT and len(dimensions) == 3 and dimensions[2].dim_value == 50304
            dynamic_axes = (0, 1)
        else:
            valid = (tensor.elem_type == TensorProto.FLOAT and len(dimensions) == 4
                     and dimensions[1].dim_value == 8 and dimensions[3].dim_value == 64)
            dynamic_axes = (0, 2)
        if not valid or any(not dimensions[axis].dim_param for axis in dynamic_axes):
            raise ContractError("Model outputs must preserve the frozen dynamic dimensions and precision")
    initializers = [{"name": value.name, "dtype": TensorProto.DataType.Name(value.data_type),
                     "shape": list(value.dims), "sha256": hashlib.sha256(value.SerializeToString()).hexdigest()}
                    for value in graph.graph.initializer]
    if initializers != receipt.get("initializers"):
        raise ContractError("An initializer differs from its reviewed exported identity")
    nodes = {node.name: node for node in graph.graph.node}
    sites = receipt.get("sites")
    if not isinstance(sites, list) or [site.get("site") for site in sites] != list(SITES):
        raise ContractError("The export receipt must identify the six frozen projection sites")
    quantized = [node for node in graph.graph.node if node.op_type == "MatMulNBits"]
    if len(quantized) != (6 if group else 0):
        raise ContractError("Unexpected count of quantized model projections")
    for site in sites:
        node = nodes.get(site.get("matmul_node"))
        if node is None:
            raise ContractError("A reviewed projection node is missing")
        if group:
            attributes = {attribute.name: helper.get_attribute_value(attribute) for attribute in node.attribute}
            if (node.domain != "com.microsoft" or node.op_type != "MatMulNBits" or len(node.input) != 3
                    or attributes != {"K": 2048, "N": 512, "bits": 4, "block_size": group, "accuracy_level": 1}):
                raise ContractError("A grouped projection changed its precision, grouping or zero-point contract")
        elif node.domain or node.op_type != "MatMul":
            raise ContractError("A full-precision projection changed its operator")
    online_add = sum(node.op_type == "Add" and node.name.startswith("hadamard_layer") for node in nodes.values())
    online_sub = sum(node.op_type == "Sub" and node.name.startswith("hadamard_layer") for node in nodes.values())
    if (online_add, online_sub) != ((66, 66) if rotated else (0, 0)):
        raise ContractError("The graph omitted or changed the eleven-stage online transforms")
    evidence = {"arm": arm, "graph_sha256": receipt["sha256"], "serialized_model_bytes": receipt["bytes"],
                "initializer_identities_verified": len(initializers), "matmul_nbits_nodes": len(quantized),
                "online_add_nodes": online_add, "online_sub_nodes": online_sub,
                "full_surgery_audit": "bound_to_reviewed_export_receipt_by_graph_and_initializer_hashes",
                "dynamic_io_and_operator_attributes": "passed"}
    del graph
    gc.collect()
    return evidence


class CheckedSession:
    """One receipt-checked CPU session, with native logs retained for its lifetime."""

    def __init__(self, graph_path: Path, log_dir: Path, arm_receipt: Mapping, profile: bool):
        global _ACTIVE_SESSION
        if _ACTIVE_SESSION:
            raise ContractError("Only one checked model session may be active in a process")
        _ACTIVE_SESSION = True
        self._runtime = None
        self._previous_stderr = None
        self._log = None
        self._closed = False
        self._owns_directory = False
        self._profile = profile
        self._call_count = 0
        self._directory = Path(log_dir)
        self.evidence = {"status": "failed"}
        started = time.perf_counter()
        try:
            self._directory.mkdir(parents=True, exist_ok=False)
            self._owns_directory = True
            versions = _runtime_versions()
            audit = _graph_audit(Path(graph_path), arm_receipt)
            audit_seconds = time.perf_counter() - started
            self.evidence.update(audit)
            self.evidence.update({"runtime_versions": versions, "audit_seconds": audit_seconds,
                                  "profile_enabled": profile, "threads": 1,
                                  "graph_optimizations": "disabled", "execution_mode": "sequential"})
            self._log = (self._directory / "ort.log").open("xb")
            self._previous_stderr = os.dup(2)
            os.dup2(self._log.fileno(), 2)
            options = ort.SessionOptions()
            options.intra_op_num_threads = options.inter_op_num_threads = 1
            options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
            options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_DISABLE_ALL
            options.log_severity_level = 1
            options.enable_profiling = profile
            options.profile_file_prefix = str(self._directory / "ort")
            load_started = time.perf_counter()
            self._runtime = ort.InferenceSession(str(graph_path), sess_options=options, providers=["CPUExecutionProvider"])
            self.evidence["session_load_seconds"] = time.perf_counter() - load_started
            if self._runtime.get_providers() != ["CPUExecutionProvider"]:
                raise ContractError("The model session must use only CPUExecutionProvider")
            if ([value.name for value in self._runtime.get_inputs()] != list(INPUT_NAMES)
                    or [value.name for value in self._runtime.get_outputs()] != list(OUTPUT_NAMES)):
                raise ContractError("The runtime session dropped or reordered model IO")
            if file_sha256(Path(graph_path)) != arm_receipt["sha256"]:
                raise ContractError("Graph bytes changed during session loading")
            self.evidence.update({"status": "loaded", "session_providers": self._runtime.get_providers(),
                                  "load_wall_seconds": time.perf_counter() - started})
        except Exception as error:
            self.evidence["error"] = {"type": type(error).__name__, "message": str(error)}
            self.close(require_execution=False)
            raise

    def __enter__(self):
        return self

    def __exit__(self, error_type, error, traceback):
        if error is not None:
            self.evidence.update({"status": "failed", "error": {"type": type(error).__name__, "message": str(error)}})
        try:
            self.close(require_execution=error is None)
        except Exception as close_error:
            if error is None:
                raise
            self.evidence["closing_error"] = str(close_error)
        return False

    def step(self, tokens: np.ndarray, cache: Sequence[np.ndarray] | None = None) -> tuple[np.ndarray, tuple]:
        if self._closed or self._runtime is None:
            raise ContractError("The checked model session is not open")
        feed = model_inputs(tokens, cache)
        batch, sequence = feed["input_ids"].shape
        total = feed[INPUT_NAMES[1]].shape[2] + sequence
        outputs = self._runtime.run(list(OUTPUT_NAMES), feed)
        self._call_count += 1
        return _checked_outputs(outputs, batch, sequence, total)

    def close(self, *, require_execution: bool = True) -> None:
        global _ACTIVE_SESSION
        if self._closed:
            return
        self._closed = True
        failure = None
        try:
            if self._runtime is not None and self._profile:
                generated = Path(self._runtime.end_profiling())
                target = self._directory / "ort.profile.json"
                if target.exists():
                    raise ContractError("Refusing to replace a prior profile")
                generated.rename(target)
                events = json.loads(target.read_text())
                nodes = [event for event in events if event.get("cat") == "Node" and event.get("args", {}).get("provider")]
                providers = sorted({event["args"]["provider"] for event in nodes})
                operators = Counter(event["args"].get("op_name", "unknown") for event in nodes)
                expected = self.evidence["matmul_nbits_nodes"] * self._call_count
                self.evidence.update({"observed_providers": providers,
                                      "operator_execution_counts": dict(sorted(operators.items())),
                                      "expected_matmul_nbits_executions": expected,
                                      "profile": {"path": target.name, "sha256": file_sha256(target), "bytes": target.stat().st_size}})
                if require_execution and (not self._call_count or providers != ["CPUExecutionProvider"]
                                          or operators["MatMulNBits"] != expected):
                    raise ContractError("The profile did not establish every requested CPU operator execution")
            elif require_execution and not self._call_count:
                raise ContractError("The checked model session made no complete calls")
            self.evidence.update({"complete_forward_calls": self._call_count,
                                  "internal_mlas_path": "not established by operator/provider profiling"})
        except Exception as error:
            failure = error
            self.evidence["error"] = {"type": type(error).__name__, "message": str(error)}
        finally:
            self._runtime = None
            gc.collect()
            if self._previous_stderr is not None:
                os.dup2(self._previous_stderr, 2)
                os.close(self._previous_stderr)
                self._previous_stderr = None
            if self._log is not None:
                self._log.close()
                log_path = self._directory / "ort.log"
                self.evidence["runtime_log"] = {"path": log_path.name, "sha256": file_sha256(log_path),
                                                 "bytes": log_path.stat().st_size}
                self.evidence["unpacked_fallback_message_present"] = "unpacked compute mode" in log_path.read_text(errors="replace")
            if self.evidence.get("status") == "loaded":
                self.evidence["status"] = "passed" if failure is None else "failed"
            _ACTIVE_SESSION = False
            if self._owns_directory and not (self._directory / "session.json").exists():
                _new_json(self._directory / "session.json", self.evidence)
        if failure is not None:
            raise failure


def create_session(graph_path: Path, log_dir: Path, *, arm_receipt: Mapping,
                   profile: bool = False) -> CheckedSession:
    """Create one managed CPU session; always close it or use it in a with block."""
    if type(profile) is not bool:
        raise ContractError("profile must be a boolean")
    return CheckedSession(Path(graph_path), Path(log_dir), arm_receipt, profile)


def step_from_session(session: CheckedSession):
    """Expose the common step(tokens, cache) interface for timing and quality."""
    if not isinstance(session, CheckedSession):
        raise ContractError("A receipt-checked model session is required")
    return session.step


def _saved_logits(directory: Path, case: Mapping) -> np.ndarray:
    artifact = case.get("logits_file")
    if not isinstance(artifact, Mapping) or not isinstance(artifact.get("path"), str):
        raise ContractError("A retained local reference logit artifact is required")
    relative = Path(artifact["path"])
    if relative.is_absolute() or len(relative.parts) != 1 or relative.name in (".", ".."):
        raise ContractError("Reference logits must stay in their retained directory")
    path = directory / relative
    if not path.is_file() or path.stat().st_size != artifact.get("bytes") or file_sha256(path) != artifact.get("sha256"):
        raise ContractError("Reference logit artifact bytes differ from their receipt")
    values = np.load(path, mmap_mode="r", allow_pickle=False)
    if values.dtype != np.float32 or list(values.shape) != case["logits"]["shape"]:
        raise ContractError("Reference logit array shape or dtype differs from its receipt")
    return values


def _observe_development(step, public: dict, tokens: np.ndarray, directory: Path, index: int,
                         *, save_logits: bool, comparison: tuple[Path, dict] | None = None) -> dict:
    observation = {"article": public, "cases": {}}
    cache, full_logits = None, None
    for case, sequence in _CASES.items():
        inputs = tokens if case == "full" else (tokens[:, :512] if case == "prefill" else tokens[:, 512:513])
        before = time.perf_counter()
        logits, present = step(inputs, cache if case == "cached" else None)
        elapsed = time.perf_counter() - before
        logits, present = _checked_outputs((logits, *present), 1, sequence, 513 if case != "prefill" else 512)
        if case == "full":
            observation["nll"] = {"article_id": public["article_id"], **shifted_nll(logits[0], tokens[0].tolist())}
            observation["full_forward_and_nll_seconds"] = time.perf_counter() - before
        result = {"logits": _array_identity(logits), "forward_seconds": elapsed,
                  "cache": [_array_identity(value) for value in present]}
        if save_logits:
            path = directory / f"article{index}.{case}.npy"
            with path.open("xb") as stream:
                np.save(stream, logits, allow_pickle=False)
            result["logits_file"] = {"path": path.name, "sha256": file_sha256(path), "bytes": path.stat().st_size}
        if comparison is not None:
            reference_dir, reference = comparison
            expected = _saved_logits(reference_dir, reference["cases"][case])
            result["reference_comparison"] = compare_logits(logits, expected)
            del expected
        if case == "full":
            full_logits = logits
        elif case == "prefill":
            result["full_vs_cached_path"] = compare_logits(logits, full_logits[:, :512])
        else:
            result["full_vs_cached_path"] = compare_logits(logits, full_logits[:, 512:513])
        observation["cases"][case] = result
        cache = present if case == "prefill" else None
        del present
    observation["cache_path_passed"] = all(observation["cases"][case]["full_vs_cached_path"]["passed"]
                                            for case in ("prefill", "cached"))
    return observation


def run_reference_development(model_dir: Path, selected_records: Sequence[Mapping], output_dir: Path) -> dict:
    """Create local full-model reference logits in the isolated converter worker."""
    from benchmarks.model_export import load_reference, reference_forward

    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=False)
    receipt = {"schema_version": "hadamard-reference-development.v1", "status": "failed",
               "model_revision": MODEL_REVISION, "campaign_ready": False,
               "scope": "Two fixed development prefixes; no quality test evaluation", "records": []}
    started, failure = time.perf_counter(), None
    model = None
    try:
        records = _development_records(selected_records)
        model = load_reference(Path(model_dir))
        receipt["model_load_seconds"] = time.perf_counter() - started
        for index, (public, tokens) in enumerate(records):
            receipt["records"].append(_observe_development(
                lambda ids, cache: reference_forward(model, ids, cache), public, tokens,
                directory, index, save_logits=True))
        receipt["aggregate_nll"] = aggregate_nll([record["nll"] for record in receipt["records"]])
        if not all(record["cache_path_passed"] for record in receipt["records"]):
            raise ContractError("The reference's full and cached paths fail development parity")
        receipt["status"] = "passed"
    except Exception as error:
        failure = error
        receipt["error"] = {"type": type(error).__name__, "message": str(error)}
    finally:
        del model
        gc.collect()
        receipt["elapsed_seconds"] = time.perf_counter() - started
        _new_json(directory / "reference.json", receipt)
    if failure is not None:
        raise ContractError(f"Reference development failed; retained receipt: {directory / 'reference.json'}") from failure
    return receipt


def run_onnx_development(export_dir: Path, export_receipt: Mapping,
                         selected_records: Sequence[Mapping], reference_dir: Path,
                         output_dir: Path) -> dict:
    """Check all six graphs sequentially on development data, without cost runs."""
    directory, export_dir, reference_dir = Path(output_dir), Path(export_dir), Path(reference_dir)
    directory.mkdir(parents=True, exist_ok=False)
    receipt = {"schema_version": "hadamard-onnx-development.v1", "status": "failed",
               "model_revision": MODEL_REVISION, "campaign_ready": False,
               "scope": "Development parity only; fresh-worker cost qualification is separate", "arms": {}}
    started, failure = time.perf_counter(), None
    try:
        records = _development_records(selected_records)
        if (not isinstance(export_receipt, Mapping) or export_receipt.get("model_revision") != MODEL_REVISION
                or [arm.get("arm") for arm in export_receipt.get("arms", [])] != list(ARM_IDS)):
            raise ContractError("The reviewed export must include exactly the six ordered frozen arms")
        if json.loads((export_dir / "export.json").read_text()) != export_receipt:
            raise ContractError("The supplied export receipt differs from the retained file")
        reference = json.loads((reference_dir / "reference.json").read_text())
        if (reference.get("status") != "passed" or reference.get("model_revision") != MODEL_REVISION
                or [record.get("article") for record in reference.get("records", [])] != [public for public, _ in records]):
            raise ContractError("Reference evidence does not match the frozen development selection")
        receipt.update({"export_receipt_sha256": file_sha256(export_dir / "export.json"),
                        "reference_receipt_sha256": file_sha256(reference_dir / "reference.json")})
        for arm in export_receipt["arms"]:
            arm_started = time.perf_counter()
            arm_id = arm["arm"]
            arm_dir = directory / arm_id
            observed = {"graph_sha256": arm["sha256"], "records": []}
            receipt["arms"][arm_id] = observed
            with create_session(export_dir / arm["path"], arm_dir, arm_receipt=arm, profile=True) as session:
                for index, (public, tokens) in enumerate(records):
                    comparison = None
                    if arm_id == "fp32_original":
                        comparison = reference_dir, reference["records"][index]
                    elif arm_id == "fp32_rotated":
                        comparison = directory / "fp32_original", receipt["arms"]["fp32_original"]["records"][index]
                    observed["records"].append(_observe_development(
                        session.step, public, tokens, arm_dir, index,
                        save_logits=arm_id == "fp32_original", comparison=comparison))
            observed["runtime"] = session.evidence
            observed["aggregate_nll"] = aggregate_nll([record["nll"] for record in observed["records"]])
            observed["cache_path_passed"] = all(record["cache_path_passed"] for record in observed["records"])
            if arm_id in ("fp32_original", "fp32_rotated"):
                baseline = reference if arm_id == "fp32_original" else receipt["arms"]["fp32_original"]
                observed["aggregate_nll_delta"] = observed["aggregate_nll"]["mean_nll"] - baseline["aggregate_nll"]["mean_nll"]
                observed["float_control_passed"] = (
                    abs(observed["aggregate_nll_delta"]) <= 1e-5 and all(
                        case["reference_comparison"]["passed"] for record in observed["records"] for case in record["cases"].values()))
            observed["parity_wall_seconds"] = time.perf_counter() - arm_started
        gates = {"every_arm_cache_path": all(arm["cache_path_passed"] for arm in receipt["arms"].values()),
                 "original_vs_transformers": receipt["arms"]["fp32_original"]["float_control_passed"],
                 "rotated_vs_original": receipt["arms"]["fp32_rotated"]["float_control_passed"]}
        receipt["gates"] = gates
        if not all(gates.values()):
            raise ContractError("Full-model development parity failed")
        receipt["status"] = "passed"
    except Exception as error:
        failure = error
        receipt["error"] = {"type": type(error).__name__, "message": str(error)}
    finally:
        receipt["elapsed_seconds"] = time.perf_counter() - started
        _new_json(directory / "export-parity.json", receipt)
    if failure is not None:
        raise ContractError(f"ONNX development failed; retained receipt: {directory / 'export-parity.json'}") from failure
    return receipt


def current_rss_bytes() -> int:
    """Read this worker's current resident memory from its own procfs identity."""
    for line in Path("/proc/self/status").read_text().splitlines():
        if line.startswith("VmRSS:"):
            fields = line.split()
            if len(fields) != 3 or fields[2] != "kB" or not fields[1].isdigit() or int(fields[1]) <= 0:
                break
            return int(fields[1]) * 1024
    raise ContractError("The worker's OS resident-memory observation is unavailable")


def run_development_cost(graph_path: Path, arm_receipt: Mapping,
                         synthetic640fixture: Mapping, log_dir: Path) -> dict:
    """Run one fresh-worker cost fixture; the parent must launch a fresh process.

    Session audit/loading, both warmups, RSS observations and both measured
    workloads are included in worker_wall_seconds. This development observation
    is for feasibility only and cannot replace the 20-block timing endpoint.
    """
    directory = Path(log_dir)
    if directory.exists():
        raise FileExistsError("Development cost output already exists; preserve the prior attempt")
    started = time.perf_counter()
    public, tokens = _validated_cost_fixture(synthetic640fixture)
    receipt = {"schema_version": "hadamard-development-cost.v1", "status": "failed",
               "arm": arm_receipt["arm"], "fixture": public, "campaign_ready": False,
               "scope": "One synthetic development cost fixture; no test or timing endpoint claim"}
    failure, session = None, None
    try:
        with create_session(graph_path, log_dir, arm_receipt=arm_receipt, profile=False) as session:
            receipt.update(run_timing_worker(session.step, tokens, current_rss_bytes))
        receipt["runtime"] = session.evidence
        receipt["status"] = "passed"
    except Exception as error:
        failure = error
        receipt["error"] = {"type": type(error).__name__, "message": str(error)}
        if session is not None:
            receipt["runtime"] = session.evidence
    finally:
        receipt["worker_wall_seconds"] = time.perf_counter() - started
        receipt["peak_rss_bytes"] = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss) * 1024
        if directory.is_dir() and not (directory / "development-cost.json").exists():
            _new_json(directory / "development-cost.json", receipt)
    if failure is not None:
        raise ContractError(f"Development cost observation failed; retained logs: {log_dir}") from failure
    return receipt
