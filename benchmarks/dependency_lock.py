"""Turn official-source pip reports into reviewed, hash-addressed wheel locks.

Reports supply provenance; active dependency closure and installed identities
are independently checked here. Import/ABI qualification remains separate from
wheel resolution and never establishes full-model export or campaign readiness.
"""

from __future__ import annotations

import argparse
from email.parser import BytesParser
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import re
import sys
import zipfile
from urllib.parse import unquote, urlsplit

from packaging.requirements import Requirement
from packaging.specifiers import SpecifierSet
from packaging.tags import sys_tags
from packaging.utils import canonicalize_name, parse_wheel_filename
from packaging.version import Version


class DependencyLockError(ValueError):
    """Dependency provenance, closure or installation does not match the lock."""


_OFFICIAL_HOSTS = {"files.pythonhosted.org", "pypi.org", "download.pytorch.org",
                   "download-r2.pytorch.org"}


def _canonical_bytes(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()


def _wheel_identity(url: str, name: str, version: str) -> str:
    parsed = urlsplit(url)
    if (parsed.scheme != "https" or parsed.hostname not in _OFFICIAL_HOSTS or
            parsed.username or parsed.password or parsed.port not in (None, 443) or
            parsed.query or parsed.fragment or any(char.isspace() for char in url)):
        raise DependencyLockError("wheel URL must use an uncredentialed official HTTPS source")
    filename = unquote(parsed.path.rsplit("/", 1)[-1])
    try:
        wheel_name, wheel_version, _, _ = parse_wheel_filename(filename)
    except ValueError as error:
        raise DependencyLockError("only complete binary wheel sources can be locked") from error
    if canonicalize_name(wheel_name) != name or wheel_version != Version(version):
        raise DependencyLockError("wheel filename and distribution metadata disagree")
    return filename


def _verify_wheel_file(path: Path, name: str, version: str) -> dict:
    if path.is_symlink() or not path.is_file():
        raise DependencyLockError("wheel evidence must be a regular local file")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    with zipfile.ZipFile(path) as archive:
        metadata_files = [item for item in archive.infolist()
                          if item.filename.count("/") == 1 and item.filename.endswith(".dist-info/METADATA")]
        if len(metadata_files) != 1 or metadata_files[0].file_size > 2 * 1024**2:
            raise DependencyLockError("wheel evidence has missing or ambiguous package metadata")
        metadata = BytesParser().parsebytes(archive.read(metadata_files[0]))
    if canonicalize_name(metadata["Name"]) != name or metadata["Version"] != version:
        raise DependencyLockError("local wheel content and pip metadata disagree")
    return {"sha256": digest.hexdigest(), "bytes": path.stat().st_size}


def read_exact_pins(path: Path | str, _visited: set[Path] | None = None) -> dict[str, str]:
    """Read the repository's exact-pin requirement files, including local -r."""
    path = Path(path).resolve()
    visited = set() if _visited is None else _visited
    if path in visited:
        raise DependencyLockError("requirements include cycle")
    visited.add(path)
    result = {}
    for raw_line in path.read_text().splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line:
            continue
        if line.startswith("-r "):
            incoming = read_exact_pins(path.parent / line[3:].strip(), visited)
        else:
            requirement = Requirement(line)
            clauses = list(requirement.specifier)
            if (requirement.url or requirement.marker or requirement.extras or len(clauses) != 1 or
                    clauses[0].operator != "==" or "*" in clauses[0].version):
                raise DependencyLockError("source requirements must be unconditional exact version pins")
            incoming = {canonicalize_name(requirement.name): clauses[0].version}
        for name, version in incoming.items():
            if name in result and result[name] != version:
                raise DependencyLockError(f"conflicting requirement pins for {name}")
            result[name] = version
    visited.remove(path)
    return dict(sorted(result.items()))


def validate_dependency_closure(lock: dict) -> dict:
    """Check all active requirements, propagating dependency extras to a fixpoint."""
    packages = lock["packages"]
    indexed = {package["name"]: package for package in packages}
    if len(indexed) != len(packages):
        raise DependencyLockError("duplicate normalized package name")
    marker_environment = dict(lock["python_environment"])
    for field in ("python_full_version", "python_version", "sys_platform", "platform_machine"):
        if not isinstance(marker_environment.get(field), str):
            raise DependencyLockError(f"pip report lacks target environment marker {field}")
    extras = {package["name"]: set(package["requested_extras"]) for package in packages}
    changed, checked = True, set()
    while changed:
        changed = False
        for name, package in indexed.items():
            if package["requires_python"] and not SpecifierSet(package["requires_python"]).contains(
                    marker_environment["python_full_version"], prereleases=True):
                raise DependencyLockError(f"{name} does not support the resolved Python")
            for raw in package["requires_dist"]:
                requirement = Requirement(raw)
                active = requirement.marker is None or any(
                    requirement.marker.evaluate({**marker_environment, "extra": extra})
                    for extra in ({""} | extras[name]))
                if not active:
                    continue
                dependency = canonicalize_name(requirement.name)
                if dependency not in indexed:
                    raise DependencyLockError(f"missing active dependency: {name} requires {raw}")
                resolved = indexed[dependency]
                if not requirement.specifier.contains(resolved["version"], prereleases=True):
                    raise DependencyLockError(f"incompatible dependency: {name} requires {raw}")
                if requirement.url and requirement.url != resolved["url"]:
                    raise DependencyLockError(f"direct dependency URL does not match {dependency}")
                newly_active = set(requirement.extras) - extras[dependency]
                if newly_active:
                    extras[dependency].update(newly_active)
                    changed = True
                checked.add((name, raw))
    return {"status": "passed", "packages": len(packages), "active_requirement_edges": len(checked),
            "activated_extras": {name: sorted(values) for name, values in extras.items() if values}}


def from_pip_report(report: dict, environment: str, required_versions: dict[str, str], *,
                    wheel_files: dict[str, Path] | None = None) -> dict:
    """Bind every resolved package to an official wheel URL, hash and version."""
    if report.get("version") != "1" or not isinstance(report.get("install"), list) or not report["install"]:
        raise DependencyLockError("a nonempty pip installation report version 1 is required")
    if not isinstance(environment, str) or not environment:
        raise DependencyLockError("environment needs a name")
    packages, seen = [], set()
    for item in report["install"]:
        metadata, download = item["metadata"], item["download_info"]
        name, version = canonicalize_name(metadata["name"]), metadata["version"]
        Version(version)
        if name in seen:
            raise DependencyLockError(f"duplicate normalized package name: {name}")
        seen.add(name)
        if item.get("is_yanked") or "vcs_info" in download or "dir_info" in download:
            raise DependencyLockError("yanked, VCS and local-directory distributions are not permitted")
        digest = download.get("archive_info", {}).get("hashes", {}).get("sha256")
        content = None
        if wheel_files is not None and download["url"] in wheel_files:
            content = _verify_wheel_file(Path(wheel_files[download["url"]]), name, version)
            if digest is not None and digest != content["sha256"]:
                raise DependencyLockError("local wheel bytes differ from pip's reported SHA256")
            digest = content["sha256"]
        if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise DependencyLockError(f"{name} needs a complete wheel SHA256")
        filename = _wheel_identity(download["url"], name, version)
        requires = metadata.get("requires_dist", [])
        extras = item.get("requested_extras", [])
        if not isinstance(requires, list) or any(not isinstance(value, str) for value in requires):
            raise DependencyLockError("requires_dist must contain requirement strings")
        if not isinstance(extras, list) or any(not isinstance(value, str) for value in extras):
            raise DependencyLockError("requested extras must be strings")
        packages.append({"name": name, "version": version, "url": download["url"],
                         "filename": filename, "sha256": digest, "requested": bool(item.get("requested")),
                         "requested_extras": sorted(extras), "requires_dist": requires,
                         "requires_python": metadata.get("requires_python", ""),
                         "wheel_content_verified": content is not None,
                         "wheel_bytes": content["bytes"] if content is not None else None,
                         "hash_origin": "verified_local_wheel" if content is not None else "pip_report"})
    packages.sort(key=lambda package: package["name"])
    resolved = {package["name"]: package["version"] for package in packages}
    required = {canonicalize_name(name): version for name, version in required_versions.items()}
    for name, version in required.items():
        if resolved.get(name) != version:
            raise DependencyLockError(f"required frozen version differs: {name}=={version}")
    lock = {"schema_version": "hadamard-python-wheel-lock.v1", "environment_name": environment,
            "pip_version": report.get("pip_version"), "python_environment": report.get("environment", {}),
            "pip_report_canonical_sha256": hashlib.sha256(_canonical_bytes(report)).hexdigest(),
            "required_versions": dict(sorted(required.items())), "packages": packages}
    lock["dependency_closure"] = validate_dependency_closure(lock)
    return lock


def validate_environment(lock: dict, installed_versions: dict[str, str] | None = None) -> dict:
    """Run inside the isolated interpreter to compare the complete installation."""
    observed = {"python_full_version": platform.python_version(),
                "python_version": f"{sys.version_info.major}.{sys.version_info.minor}",
                "sys_platform": sys.platform, "platform_machine": platform.machine(),
                "implementation_name": sys.implementation.name}
    for field, value in observed.items():
        if lock["python_environment"].get(field) != value:
            raise DependencyLockError(f"interpreter environment differs from the wheel lock: {field}")
    compatible_tags = set(sys_tags())
    for package in lock["packages"]:
        _, _, _, tags = parse_wheel_filename(package["filename"])
        if not compatible_tags.intersection(tags):
            raise DependencyLockError(f"wheel tags do not support this interpreter: {package['name']}")
    if installed_versions is None:
        installed_versions = {}
        for distribution in importlib.metadata.distributions():
            name = canonicalize_name(distribution.metadata["Name"])
            if name in installed_versions:
                raise DependencyLockError(f"duplicate installed distribution: {name}")
            installed_versions[name] = distribution.version
    installed = {canonicalize_name(name): version for name, version in installed_versions.items()}
    expected = {package["name"]: package["version"] for package in lock["packages"]}
    if installed != expected:
        missing = sorted(set(expected) - set(installed))
        extra = sorted(set(installed) - set(expected))
        changed = sorted(name for name in set(installed) & set(expected) if installed[name] != expected[name])
        raise DependencyLockError(f"installed versions differ: missing={missing}, extra={extra}, changed={changed}")
    closure = validate_dependency_closure(lock)
    return {"status": "passed", "installed_packages": len(installed), "dependency_closure": closure,
            "python_environment": observed, "wheel_tags_compatible": True}


def write_hash_requirements(lock: dict) -> str:
    """Return pip --require-hashes input for every member of the closed lock."""
    validate_dependency_closure(lock)
    lines = []
    for package in lock["packages"]:
        _wheel_identity(package["url"], package["name"], package["version"])
        if not re.fullmatch(r"[a-f0-9]{64}", package["sha256"]):
            raise DependencyLockError("invalid locked wheel hash")
        lines.append(f"{package['name']} @ {package['url']} --hash=sha256:{package['sha256']}")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--converter-report", type=Path, required=True)
    parser.add_argument("--runtime-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--wheel-files", type=Path,
                        help="JSON mapping official wheel URLs to retained local wheel files")
    arguments = parser.parse_args()
    repo = Path(__file__).resolve().parent.parent
    combined = {"schema_version": "hadamard-model-dependencies.v1", "environments": {},
                "manifest_sha256": hashlib.sha256((repo / "benchmarks/model-benchmark-v1.json").read_bytes()).hexdigest(),
                "campaign_ready": False, "model_calls": 0}
    wheel_files = json.loads(arguments.wheel_files.read_text()) if arguments.wheel_files else None
    for name, report_path, requirement in (
            ("converter", arguments.converter_report, repo / "requirements-model-converter.txt"),
            ("runtime", arguments.runtime_report, repo / "requirements-benchmark.txt")):
        lock = from_pip_report(json.loads(report_path.read_text()), name, read_exact_pins(requirement),
                               wheel_files=wheel_files)
        lock["pip_report_sha256"] = hashlib.sha256(report_path.read_bytes()).hexdigest()
        lock["requirements_sha256"] = hashlib.sha256(requirement.read_bytes()).hexdigest()
        combined["environments"][name] = lock
    with arguments.output.open("xb") as stream:
        stream.write(_canonical_bytes(combined))
    print(json.dumps({"status": "locked", "packages": {name: len(lock["packages"])
                                                        for name, lock in combined["environments"].items()}}))


if __name__ == "__main__":
    main()
