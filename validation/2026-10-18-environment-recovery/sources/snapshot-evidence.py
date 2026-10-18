"""Archive original recovery receipts before further review or interpretation."""
import argparse
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import stat
import tarfile

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--repo", type=Path, required=True)
parser.add_argument("--input", type=Path, required=True)
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
root, evidence, output = args.repo.resolve(), args.input.resolve(), args.output.resolve()
output.mkdir(parents=True, exist_ok=False)
excluded = {"pip-cache", "pip-temporary", "mpl-cache", "hf-cache", "transformers-cache"}
files, omissions = [], []


def sha(data):
    return hashlib.sha256(data).hexdigest()


def refuse(error):
    raise error


for parent, directories, names in os.walk(evidence, followlinks=False, onerror=refuse):
    for name in list(directories):
        path = Path(parent) / name
        if name in excluded:
            directories.remove(name)
            omissions.append({"path": path.relative_to(root).as_posix(),
                "reason": "Regenerable installation or runtime cache, no original receipt or log omitted."})
        elif path.is_symlink():
            raise ValueError("Retained evidence must not contain symlink directories")
    for name in names:
        path = Path(parent) / name
        if not stat.S_ISREG(path.lstat().st_mode):
            raise ValueError("Retained evidence must consist of regular files")
        files.append(path)

inventory = {"schema_version": "hadamard-recovery-archive.v2", "members": [],
    "source_root": evidence.relative_to(root).as_posix(), "omissions": omissions,
    "wheel_bodies_included": False, "virtual_environments_included": False,
    "temporary_negative_test_fixtures_included": False,
    "snapshot_script_sha256": sha(Path(__file__).read_bytes()), "separate_copies": {}}
archive_path = output / "raw-evidence.tar.gz"
with archive_path.open("xb") as raw:
    with gzip.GzipFile(fileobj=raw, mode="wb", filename="", mtime=0) as zipped:
        with tarfile.open(fileobj=zipped, mode="w", format=tarfile.PAX_FORMAT) as archive:
            for path in sorted(files):
                data = path.read_bytes()
                name = path.relative_to(evidence).as_posix()
                info = tarfile.TarInfo(name)
                info.size, info.mode, info.mtime = len(data), 0o644, 0
                archive.addfile(info, io.BytesIO(data))
                inventory["members"].append({"archive_path": name, "original_path": path.relative_to(root).as_posix(),
                                               "bytes": len(data), "sha256": sha(data)})
for name, path in (("qualification.json", evidence / "qualification.json"),
                   ("campaign-preflight.json", evidence / "campaign-preflight/preflight.json")):
    if path.is_file():
        data = path.read_bytes()
        with (output / name).open("xb") as stream:
            stream.write(data)
        inventory["separate_copies"][name] = {"original_path": path.relative_to(root).as_posix(),
                                               "bytes": len(data), "sha256": sha(data)}
inventory["archive"] = {"path": archive_path.name, "bytes": archive_path.stat().st_size,
    "sha256": sha(archive_path.read_bytes()), "member_count": len(files),
    "uncompressed_member_bytes": sum(item["bytes"] for item in inventory["members"])}
with tarfile.open(archive_path) as archive:
    for item in inventory["members"]:
        if sha(archive.extractfile(item["archive_path"]).read()) != item["sha256"]:
            raise ValueError("Archive readback differs from the source inventory")
with (output / "inventory.json").open("x") as stream:
    json.dump(inventory, stream, indent=2, sort_keys=True)
    stream.write("\n")
print(json.dumps(inventory["archive"]))
