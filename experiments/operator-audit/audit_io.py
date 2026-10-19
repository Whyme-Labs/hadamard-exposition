"""Bound, read-only inputs for the preregistered operator audit.

The public loaders enforce the pinned checkpoint and historical trace
identities. The pure parsers also support synthetic fixture tests. Importing
this module performs no file access, tensor loading or numerical evaluation.
"""

import hashlib
import io
import json
import math
from pathlib import Path, PurePosixPath
import stat
import struct
import tarfile
import zipfile

CHECKPOINT_BYTES = 166029852
CHECKPOINT_SHA256 = "ebfa4e2f18696ebd83716a0d39fe2c025f2ff8483f72a83ca59c475692fc9d15"
TRACE_DIRECTORY = "validation/2026-10-18-campaign-development/reference-trace-v2"
TRACE_ARCHIVE_SHA256 = "67d20a6e24f477fcf5e789aa8af6259f07f06ffd83bc407084e24b747e0f683a"
TRACE_INVENTORY_SHA256 = "09c0be5d13fe13ab29124d401122b2b8e7b2fcff47f2409a9b7da73aa55abd07"
TRACE_WORKER_SHA256 = "0a3f346cc8fc3904167cd9bf4d8331e31591117ec30d2e11dfcc57866887965c"
BENCHMARK_SOURCE_MAP_SHA256 = "1dd75e9af0736795e4d83c26f866d15d9f7a3fe55003e399ddbd36951ab2d69e"
QKV = "gpt_neox.layers.0.attention.query_key_value"
MLP = "gpt_neox.layers.0.mlp.dense_h_to_4h"
SELECTED_SHAPES = {
    QKV + ".weight": (1536, 512), QKV + ".bias": (1536,),
    MLP + ".weight": (2048, 512), MLP + ".bias": (2048,),
}
MAX_HEADER_BYTES = 1024 * 1024
DTYPE_BYTES = {
    "BOOL": 1, "U8": 1, "I8": 1, "U16": 2, "I16": 2,
    "U32": 4, "I32": 4, "U64": 8, "I64": 8,
    "F16": 2, "BF16": 2, "F32": 4, "F64": 8,
}
ARTICLE_RECORDS = tuple({
    "article_id": f"b08601e04326c79dfdd32d625aee71d232d685c3/wikitext-2-raw-v1/validation/{row}",
    "dataset_config": "wikitext-2-raw-v1", "dataset_repo": "Salesforce/wikitext",
    "dataset_revision": "b08601e04326c79dfdd32d625aee71d232d685c3",
    "prefix_tokens": 513, "role": "development", "split": "validation", "start_row": row,
    "text_sha256": text_hash, "token_sha256": token_hash,
} for row, text_hash, token_hash in (
    (1, "37288f2bbde25e2405c4e0f40c1c54eaa8ac3d3106e170c8c6ea061d17abb891",
     "0a9f94df5f5de2b581d82281907b01af4aeac86f95055e3684aa42ee643185f4"),
    (47, "4b60812433749e0cdb1b886da6c319d3011fb9e2333f2a7d8158fb9acff02f0e",
     "4bb3be20531fe494946704c1ebdf36fbeffbc73be4861e91bfd76b87c66aa43d"),
))


def sha256_file(path):
    """Hash a regular file in bounded chunks; reject a changing file."""
    path = Path(path)
    before = path.lstat()
    if not stat.S_ISREG(before.st_mode):
        raise ValueError(f"a regular file is required: {path}")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    after = path.lstat()
    fields = ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns")
    if any(getattr(before, field) != getattr(after, field) for field in fields):
        raise ValueError(f"file changed while hashing: {path}")
    return digest.hexdigest()


def strict_json(payload):
    """Decode UTF-8 JSON, rejecting duplicate keys and nonfinite numbers."""
    def object_pairs(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate JSON key: {key}")
            result[key] = value
        return result

    def reject_constant(value):
        raise ValueError(f"nonstandard JSON constant: {value}")

    def finite_float(value):
        parsed = float(value)
        if not math.isfinite(parsed):
            raise ValueError("JSON number exceeds finite float range")
        return parsed

    if isinstance(payload, bytes):
        payload = payload.decode("utf-8")
    if not isinstance(payload, str):
        raise TypeError("JSON input must be bytes or str")
    return json.loads(payload, object_pairs_hook=object_pairs,
                      parse_constant=reject_constant, parse_float=finite_float)


def _identity(path):
    return {"bytes": Path(path).stat().st_size, "sha256": sha256_file(path)}


def _array_identity(array):
    return {"shape": list(array.shape), "dtype": str(array.dtype), "bytes": int(array.nbytes),
            "array_sha256": hashlib.sha256(array.tobytes(order="C")).hexdigest()}


def parse_selected_safetensors(path, expected_shapes):
    """Validate all header ranges and decode only selected floating tensors.

    Safetensors stores an eight-byte little-endian header length, UTF-8 JSON
    and a contiguous data buffer. All declared tensor intervals must exactly
    cover that buffer without overlap or holes. Selected F16 and BF16 values
    widen exactly to native contiguous F32; F32 values retain their bits.
    """
    import numpy as np

    path = Path(path)
    before = _identity(path)
    if not expected_shapes or any(not isinstance(name, str) for name in expected_shapes):
        raise ValueError("selected tensor names must be a nonempty mapping")
    selected_shapes = {name: tuple(shape) for name, shape in expected_shapes.items()}
    with path.open("rb") as stream:
        prefix = stream.read(8)
        if len(prefix) != 8:
            raise ValueError("truncated Safetensors length prefix")
        header_bytes = struct.unpack("<Q", prefix)[0]
        if not 2 <= header_bytes <= MAX_HEADER_BYTES or header_bytes > before["bytes"] - 8:
            raise ValueError("Safetensors header length is outside bounds")
        raw_header = stream.read(header_bytes)
        if not raw_header.startswith(b"{"):
            raise ValueError("Safetensors header must begin with an opening brace")
        header = strict_json(raw_header)
        if not isinstance(header, dict):
            raise ValueError("Safetensors header must be an object")
        metadata = header.get("__metadata__", {})
        if not isinstance(metadata, dict) or any(not isinstance(k, str) or not isinstance(v, str)
                                                for k, v in metadata.items()):
            raise ValueError("Safetensors metadata must map strings to strings")
        data_start = 8 + header_bytes
        data_bytes = before["bytes"] - data_start
        entries, occupied = {}, []
        for name, entry in header.items():
            if name == "__metadata__":
                continue
            if not isinstance(entry, dict) or set(entry) != {"dtype", "shape", "data_offsets"}:
                raise ValueError(f"invalid tensor metadata: {name}")
            dtype, shape, offsets = entry["dtype"], entry["shape"], entry["data_offsets"]
            if not isinstance(dtype, str) or dtype not in DTYPE_BYTES:
                raise ValueError(f"unsupported stored tensor dtype: {name}")
            if not isinstance(shape, list) or any(type(n) is not int or n < 0 for n in shape):
                raise ValueError(f"invalid tensor shape: {name}")
            if (not isinstance(offsets, list) or len(offsets) != 2
                    or any(type(n) is not int for n in offsets)):
                raise ValueError(f"invalid tensor offsets: {name}")
            start, end = offsets
            if not 0 <= start <= end <= data_bytes or end - start != math.prod(shape) * DTYPE_BYTES[dtype]:
                raise ValueError(f"tensor offsets or byte count mismatch: {name}")
            entries[name] = entry
            occupied.append((start, end))
        cursor = 0
        for start, end in sorted(occupied):
            if start != cursor:
                raise ValueError("tensor intervals overlap or leave a hole")
            cursor = end
        if cursor != data_bytes:
            raise ValueError("tensor intervals do not consume the exact data buffer")
        if not set(selected_shapes) <= entries.keys():
            raise ValueError("selected tensor is absent from the checkpoint")

        tensors, selected = {}, {}
        for name, shape in selected_shapes.items():
            entry = entries[name]
            if tuple(entry["shape"]) != shape:
                raise ValueError(f"selected tensor shape mismatch: {name}")
            dtype = entry["dtype"]
            if dtype not in {"F16", "BF16", "F32"}:
                raise ValueError(f"selected tensor must be F16, BF16 or F32: {name}")
            start, end = entry["data_offsets"]
            stream.seek(data_start + start)
            raw = stream.read(end - start)
            if len(raw) != end - start:
                raise ValueError("selected tensor was truncated while reading")
            if dtype == "BF16":
                words = np.frombuffer(raw, dtype="<u2").astype(np.uint32)
                words <<= np.uint32(16)
                array = words.view(np.float32).reshape(shape)
            else:
                array = np.frombuffer(raw, dtype="<f2" if dtype == "F16" else "<f4").astype(np.float32).reshape(shape)
            array = np.ascontiguousarray(array)
            if not np.isfinite(array).all():
                raise ValueError(f"selected tensor contains a nonfinite value: {name}")
            tensors[name] = array
            selected[name] = {"stored_dtype": dtype, "shape": list(shape), "data_offsets": [start, end],
                              "absolute_file_offsets": [data_start + start, data_start + end],
                              "stored_bytes": len(raw), "stored_sha256": hashlib.sha256(raw).hexdigest(),
                              "derived_fp32": _array_identity(array)}
    after = _identity(path)
    if after != before:
        raise ValueError("checkpoint bytes changed during parsing")
    return tensors, {"file": before, "header_bytes": header_bytes,
                     "header_sha256": hashlib.sha256(raw_header).hexdigest(),
                     "data_start": data_start, "data_bytes": data_bytes,
                     "declared_tensor_count": len(entries), "selected_tensors": selected}


def load_checkpoint(path):
    """Load the four bound tensors only after the entire checkpoint matches."""
    expected = {"bytes": CHECKPOINT_BYTES, "sha256": CHECKPOINT_SHA256}
    if _identity(path) != expected:
        raise ValueError("checkpoint does not match the pinned complete input")
    tensors, receipt = parse_selected_safetensors(path, SELECTED_SHAPES)
    if receipt["file"] != expected:
        raise ValueError("checkpoint identity changed after the binding check")
    receipt["path"] = str(Path(path))
    return tensors, receipt


def _safe_member_name(name):
    path = PurePosixPath(name)
    return bool(name) and not path.is_absolute() and ".." not in path.parts and str(path) == name


def _read_archive_members(path, identities):
    """Read verified regular members into memory without filesystem extraction."""
    expected = {item["path"]: item for item in identities}
    if len(expected) != len(identities) or any(not _safe_member_name(name) for name in expected):
        raise ValueError("duplicate or unsafe archive inventory path")
    if sum(item["bytes"] for item in identities) > 64 * 1024 * 1024:
        raise ValueError("archive inventory exceeds the in-memory byte ceiling")
    result = {}
    with tarfile.open(path, "r:gz") as archive:
        for member in archive:
            if (member.name in result or member.name not in expected or not _safe_member_name(member.name)
                    or member.type not in (tarfile.REGTYPE, tarfile.AREGTYPE) or member.sparse is not None):
                raise ValueError("archive contains a duplicate, unexpected or nonregular member")
            target = expected[member.name]
            if member.size != target["bytes"]:
                raise ValueError("archive member byte count mismatch")
            with archive.extractfile(member) as stream:
                raw = stream.read(member.size + 1)
            if len(raw) != member.size or hashlib.sha256(raw).hexdigest() != target["sha256"]:
                raise ValueError("archive member content identity mismatch")
            result[member.name] = raw
    if result.keys() != expected.keys():
        raise ValueError("archive member set is incomplete")
    return result


def _selected_npz_arrays(raw, trace):
    """Validate NPZ keys against saved events and load four finite F32 arrays."""
    import numpy as np

    if len(raw) != trace["bytes"] or hashlib.sha256(raw).hexdigest() != trace["sha256"]:
        raise ValueError("NPZ file identity differs from its trace receipt")
    events = trace["events"]
    if not isinstance(events, list) or len(events) != 160:
        raise ValueError("a trace must contain exactly 160 events")
    labels = [event["label"] for event in events]
    if len(set(labels)) != len(labels):
        raise ValueError("trace event labels are duplicated")
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        members = archive.infolist()
        if [member.filename for member in members] != [label + ".npy" for label in labels]:
            raise ValueError("NPZ key order differs from the complete event list")
        if any(member.file_size > 1024 * 1024 or member.is_dir() for member in members):
            raise ValueError("NPZ member exceeds the byte ceiling or is a directory")
        if sum(member.file_size for member in members) > 4 * 1024 * 1024:
            raise ValueError("NPZ uncompressed content exceeds the byte ceiling")
    selected = {}
    with np.load(io.BytesIO(raw), allow_pickle=False, max_header_size=16384) as archive:
        for label in (QKV + ":input", QKV + ":output", MLP + ":input", MLP + ":output"):
            array = archive[label]
            if array.dtype != np.dtype(np.float32) or not array.flags.c_contiguous or not np.isfinite(array).all():
                raise ValueError("selected trace arrays must be finite contiguous native FP32")
            selected[label] = array.copy()
    return selected


def _cases_from_payloads(worker, payloads):
    """Build the fixed four cases; exposed to synthetic format-rejection tests."""
    records = worker["records"]
    if not isinstance(records, list) or len(records) != 2:
        raise ValueError("exactly two historical development articles are required")
    result = []
    for article_index, (record, expected_article) in enumerate(zip(records, ARTICLE_RECORDS)):
        if record["article"] != expected_article:
            raise ValueError("development article identity differs from the fixed selection")
        comparisons = record["full_last_vs_cached_events"]
        if len(comparisons) != 160 or len({item["label"] for item in comparisons}) != 160:
            raise ValueError("comparison events are incomplete or duplicated")
        comparison_by_label = {item["label"]: item for item in comparisons}
        arrays, traces = {}, {}
        for mode in ("full", "cached"):
            trace = record["cases"][mode]["trace"]
            if trace["path"] != f"article{article_index}.{mode}.trace.npz":
                raise ValueError("trace path differs from its article and call mode")
            traces[mode] = trace
            arrays[mode] = _selected_npz_arrays(payloads["worker/" + trace["path"]], trace)
        for short, module, width, input_event in (("qkv", QKV, 1536, 15), ("mlp", MLP, 2048, 23)):
            provenance = {"events": {}, "retained_identities": {}, "npz_files": {}}
            for mode, sequence, comparison_key in (("full", 513, "expected"), ("cached", 1, "actual")):
                trace = traces[mode]
                provenance["npz_files"][mode] = {k: trace[k] for k in ("path", "bytes", "sha256")}
                provenance["events"][mode] = []
                provenance["retained_identities"][mode] = {}
                for offset, suffix, features in ((0, ":input", 512), (1, ":output", width)):
                    label = module + suffix
                    event = trace["events"][input_event + offset]
                    expected_event = {"label": label, "dtype": "float32", "original_shape": [1, sequence, features],
                                      "retained_shape": [1, 1, features]}
                    if event != expected_event or arrays[mode][label].shape != (1, 1, features):
                        raise ValueError("selected trace event position, shape or dtype differs")
                    identity = _array_identity(arrays[mode][label])
                    if identity != comparison_by_label[label][comparison_key]:
                        raise ValueError("selected trace array identity differs from the historical comparison")
                    provenance["events"][mode].append({"index": input_event + offset, **event})
                    provenance["retained_identities"][mode][suffix[1:]] = identity
            full_input = arrays["full"][module + ":input"]
            cached_input = arrays["cached"][module + ":input"]
            if full_input.tobytes() != cached_input.tobytes():
                raise ValueError("full and cached selected input bytes differ")
            result.append({"id": f"article{article_index}_{short}", "article": dict(expected_article), "module": module,
                           "input": full_input.reshape(-1).copy(),
                           "full_output": arrays["full"][module + ":output"].reshape(-1).copy(),
                           "cached_output": arrays["cached"][module + ":output"].reshape(-1).copy(),
                           "provenance": provenance})
    return result


def load_trace_cases(repo_root):
    """Verify the pinned archive, historical source maps and four trace cases."""
    root = Path(repo_root).resolve()
    directory = root / TRACE_DIRECTORY
    files = {}

    def bound_file(relative, expected_sha=None, expected_bytes=None):
        path = root / relative
        if not path.resolve().is_relative_to(root):
            raise ValueError("a bound source escapes the repository")
        identity = _identity(path)
        if ((expected_sha is not None and identity["sha256"] != expected_sha)
                or (expected_bytes is not None and identity["bytes"] != expected_bytes)):
            raise ValueError(f"bound source identity mismatch: {relative}")
        files[relative] = identity
        return path

    inventory_path = bound_file(TRACE_DIRECTORY + "/inventory.json", TRACE_INVENTORY_SHA256)
    archive_path = bound_file(TRACE_DIRECTORY + "/raw-evidence.tar.gz", TRACE_ARCHIVE_SHA256, 2216803)
    worker_path = bound_file(TRACE_DIRECTORY + "/worker-result.json", TRACE_WORKER_SHA256, 866754)
    inventory = strict_json(inventory_path.read_bytes())
    worker = strict_json(worker_path.read_bytes())
    if (inventory["schema_version"] != "hadamard-diagnostic-archive.v2" or inventory["kind"] != "trace"
            or inventory["archive"]["member_count"] != 15 or len(inventory["members"]) != 15
            or inventory["archive"]["uncompressed_member_bytes"] != 5977560
            or sum(item["bytes"] for item in inventory["members"]) != 5977560
            or inventory["archive"]["sha256"] != TRACE_ARCHIVE_SHA256 or inventory["archive"]["bytes"] != 2216803):
        raise ValueError("trace archive inventory differs from its fixed scope")
    required_true = ("collection_completed", "inputs_unchanged", "backend_unchanged", "original_reference_failure_reproduced",
                     "all_available_original_arrays_equal", "all_original_cache_identities_equal", "all_recorded_logit_data_identities_match")
    if (worker["schema_version"] != "hadamard-reference-trace.v2" or worker["status"] != "passed"
            or any(worker.get(key) is not True for key in required_true)
            or worker["model_calls"] != 6 or worker["errors"]):
        raise ValueError("historical trace completion and reproduction evidence differs")
    sources = worker["source_sha256_before"]
    canonical = json.dumps(sources, sort_keys=True, separators=(",", ":")).encode()
    if len(sources) != 30 or sources != worker["source_sha256_after"] or hashlib.sha256(canonical).hexdigest() != BENCHMARK_SOURCE_MAP_SHA256:
        raise ValueError("historical benchmark source map differs")
    for relative, expected in sources.items():
        bound_file(relative, expected)
    helpers = worker["diagnostic_helper_sha256_before"]
    if helpers != worker["diagnostic_helper_sha256_after"]:
        raise ValueError("historical diagnostic helper identities differ")
    for name, expected in helpers.items():
        bound_file("validation/2026-10-18-campaign-development/sources/" + name, expected)
    payloads = _read_archive_members(archive_path, inventory["members"])
    for name, expected in inventory["separate_copies"].items():
        path = bound_file(TRACE_DIRECTORY + "/" + name, expected["sha256"], expected["bytes"])
        if path.read_bytes() != payloads[expected["original_path"]]:
            raise ValueError("standalone trace evidence differs from its archived copy")
    cases = _cases_from_payloads(worker, payloads)
    for relative, identity in files.items():
        if _identity(root / relative) != identity:
            raise ValueError("a bound trace source changed during loading")
    return cases, {"source_files": files, "verified_archive_members": inventory["members"],
                   "loaded_npz_paths": [f"worker/article{i}.{mode}.trace.npz" for i in range(2) for mode in ("full", "cached")],
                   "case_ids": [case["id"] for case in cases], "benchmark_source_map_sha256": BENCHMARK_SOURCE_MAP_SHA256}
