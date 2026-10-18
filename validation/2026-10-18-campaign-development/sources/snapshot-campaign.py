"""Retain original campaign receipts and exact diagnostic slices without rerunning a model."""

import argparse
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import stat
import tarfile

import numpy as np


def digest(path):
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def write_json(path, value):
    with path.open("x") as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")


def refuse(error):
    raise error


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--input", type=Path, required=True)
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
source = args.input.resolve(strict=True)
output = args.output.resolve()
if source == output or source in output.parents or output in source.parents:
    raise ValueError("Source and new evidence directory must be disjoint")
output.mkdir(parents=True, exist_ok=False)
files = []
for parent, directories, names in os.walk(source, followlinks=False, onerror=refuse):
    if any((Path(parent) / name).is_symlink() for name in directories):
        raise ValueError("Symlink directories are not archival evidence")
    for name in names:
        path = Path(parent) / name
        if not stat.S_ISREG(path.lstat().st_mode):
            raise ValueError("Every observed file must be a regular file")
        files.append(path)

inventory = {
    "schema_version": "hadamard-campaign-attempt-archive.v2",
    "original_directory": str(args.input),
    "snapshot_source_sha256": digest(Path(__file__)),
    "members": [], "omissions": [], "separate_copies": {},
    "model_calls": 0,
    "note": "Original receipts are byte copies. Derived full-last slices are separate and explicitly bound to their original full arrays. Omitted files remain unchanged in the source directory.",
}
archive_path = output / "raw-evidence.tar.gz"
with archive_path.open("xb") as raw:
    with gzip.GzipFile(fileobj=raw, mode="wb", filename="", mtime=0) as zipped:
        with tarfile.open(fileobj=zipped, mode="w", format=tarfile.PAX_FORMAT) as archive:
            for path in sorted(files):
                name = path.relative_to(source).as_posix()
                entry = {"path": name, "bytes": path.stat().st_size, "sha256": digest(path)}
                reason = None
                if name.startswith(("artifacts/model/", "artifacts/dataset/")):
                    reason = "Pinned public input. Its acquisition receipt and immutable byte identity are retained."
                elif name.startswith("export/") and path.suffix == ".onnx":
                    reason = "Large generated graph. Complete export receipt, graph hash and initializer audit are retained."
                elif name.startswith("export/.") and ".onnx." in path.name:
                    reason = "Unreferenced export-adjacent file observed during archival after the model worker ended. Origin and cleanup are unestablished; this file is not one of the six receipt-bound graphs."
                elif name.startswith("reference/.") and ".npy." in path.name:
                    reason = "Unreferenced logit-adjacent file observed during archival after the model worker ended. Origin and cleanup are unestablished; this file is not a receipt-bound reference array."
                elif name.startswith("reference/") and name.endswith((".full.npy", ".prefill.npy")):
                    reason = "Large development logit array. The reference receipt and full file identity are retained; exact last-position full slices are separately preserved for the failed cached comparison."
                elif name in ("selection/tokens.quality.json", "selection/tokens.timing.json"):
                    reason = "Selected nondevelopment tokens. Role identities and token hashes are retained in selection.json; no model quality or timing evaluation ran."
                if reason:
                    inventory["omissions"].append({**entry, "reason": reason})
                    continue
                if entry["bytes"] > 4 * 1024 * 1024:
                    raise ValueError(f"Unexpected large receipt requires explicit classification: {name}")
                data = path.read_bytes()
                if hashlib.sha256(data).hexdigest() != entry["sha256"]:
                    raise ValueError(f"Source changed while archiving {name}")
                info = tarfile.TarInfo(name)
                info.size, info.mode, info.mtime = len(data), 0o644, 0
                archive.addfile(info, io.BytesIO(data))
                inventory["members"].append(entry)

for name, original in {
    "campaign.json": "campaign.json", "preflight.json": "preflight.json",
    "acquisition.json": "artifacts/acquisition.json",
    "reference.json": "reference/reference.json",
}.items():
    data = (source / original).read_bytes()
    with (output / name).open("xb") as stream:
        stream.write(data)
    entry = next(item for item in inventory["members"] if item["path"] == original)
    if hashlib.sha256(data).hexdigest() != entry["sha256"]:
        raise ValueError("Standalone receipt differs from archived original")
    inventory["separate_copies"][name] = entry

slices, derivations = {}, []
for article_index in (0, 1):
    for case in ("full", "cached"):
        name = f"reference/article{article_index}.{case}.npy"
        original = source / name
        entry = next(item for item in inventory["members"] + inventory["omissions"] if item["path"] == name)
        if digest(original) != entry["sha256"]:
            raise ValueError("Logit source changed before slicing")
        array = np.load(original, mmap_mode="r", allow_pickle=False)
        expected = (1, 513 if case == "full" else 1, 50304)
        if array.dtype != np.dtype("float32") or array.shape != expected:
            raise ValueError("Diagnostic source has an unexpected shape or dtype")
        value = np.array(array[:, 512:513, :] if case == "full" else array, copy=True)
        key = f"article{article_index}_{case}"
        slices[key] = value
        derivations.append({"key": key, "source": entry,
            "operation": "array[:,512:513,:]" if case == "full" else "array[:]",
            "shape": list(value.shape), "dtype": value.dtype.str,
            "array_c_order_sha256": hashlib.sha256(value.tobytes(order="C")).hexdigest()})
        del array
with (output / "cache-comparison-slices.npz").open("xb") as stream:
    np.savez_compressed(stream, **slices)
with np.load(output / "cache-comparison-slices.npz", allow_pickle=False) as retained:
    if set(retained.files) != set(slices) or any(not np.array_equal(retained[key], value) for key, value in slices.items()):
        raise ValueError("Retained diagnostic slices differ from their source slices")
write_json(output / "slice-derivation.json", {"schema_version": "hadamard-development-logit-slices.v1",
    "npz_sha256": digest(output / "cache-comparison-slices.npz"),
    "npz_bytes": (output / "cache-comparison-slices.npz").stat().st_size,
    "numpy_version": np.__version__, "model_calls": 0, "arrays": derivations})

with tarfile.open(archive_path) as archive:
    members = archive.getmembers()
    if [item.name for item in members] != [item["path"] for item in inventory["members"]]:
        raise ValueError("Archive member set differs from inventory")
    for member, entry in zip(members, inventory["members"]):
        data = archive.extractfile(member).read()
        if not member.isfile() or len(data) != entry["bytes"] or hashlib.sha256(data).hexdigest() != entry["sha256"]:
            raise ValueError("Archive readback differs from the source inventory")
inventory["archive"] = {"path": archive_path.name, "bytes": archive_path.stat().st_size,
    "sha256": digest(archive_path), "member_count": len(inventory["members"]),
    "uncompressed_member_bytes": sum(item["bytes"] for item in inventory["members"])}
write_json(output / "inventory.json", inventory)
print(json.dumps({"archive": inventory["archive"], "omitted_files": len(inventory["omissions"]),
    "diagnostic_slice_bytes": (output / "cache-comparison-slices.npz").stat().st_size}))
