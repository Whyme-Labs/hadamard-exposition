"""Acquire the eight pinned inputs and select article prefixes without model calls.

The caller owns the campaign-wide process, disk and phase limits. This module
also enforces its download-byte ceiling and a supplied monotonic deadline. Each
attempt uses a new directory; failed downloads and their receipts are retained.
Quality-token files are local inputs. Only the campaign's execution gate may
pass them to a model; creating their identities here is not model evaluation.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
from http.client import IncompleteRead
import json
import math
import os
from pathlib import Path
import re
import time
from typing import Callable, Mapping, Sequence
from urllib.parse import urlsplit, urlunsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

try:
    from .contract import (ContractError, assert_disjoint_roles, parse_articles,
                           select_article_prefixes, validate_manifest)
except ImportError:  # Direct execution: python benchmarks/model_acquire.py.
    from contract import (ContractError, assert_disjoint_roles, parse_articles,
                          select_article_prefixes, validate_manifest)


# The four LFS pointer files at the immutable revisions below independently
# publish these sizes and content SHA256 values. Metadata hashes are measured
# on acquisition; its original URL and response Git-blob ETag are retained.
_PUBLISHED_CONTENT = {
    "model.safetensors": (166029852, "ebfa4e2f18696ebd83716a0d39fe2c025f2ff8483f72a83ca59c475692fc9d15"),
    "wikitext-2-raw-v1/train-00000-of-00001.parquet":
        (6357543, "e83889baabc497075506f91975be5fac0d45c5290b6b20582c8cd1e853d0c9f7"),
    "wikitext-2-raw-v1/validation-00000-of-00001.parquet":
        (657209, "204929b7ff9d6184953f867dedb860e40aa69c078fc1e54b3baaa8fb28511c4c"),
    "wikitext-2-raw-v1/test-00000-of-00001.parquet":
        (732610, "5f1bea067869d04849c0f975a2b29c4ff47d867f484f5010ea5e861eab246d91"),
}
_METADATA_SIZES = {"config.json": 567, "tokenizer_config.json": 396,
                   "special_tokens_map.json": 99}
_ROLES = ("development", "timing", "quality")
_CHUNK_BYTES = 1024 * 1024


class AcquisitionError(ContractError):
    """An acquisition or selection failed; its completed receipt is retained."""


@dataclass(frozen=True)
class ArtifactSpec:
    kind: str
    repo: str
    revision: str
    filename: str
    relative_path: str
    url: str
    expected_bytes: int | None
    expected_sha256: str | None
    provenance_url: str


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json_bytes(value: object) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()


def _atomic_new(path: Path, data: bytes) -> None:
    """Publish complete bytes without replacing any existing file or symlink."""
    temporary = path.with_name(path.name + ".writing")
    with temporary.open("xb") as stream:
        os.chmod(temporary, 0o600)
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    os.link(temporary, path)
    temporary.unlink()


def _sha256_file(path: Path) -> str:
    if path.is_symlink() or not path.is_file():
        raise AcquisitionError(f"expected a regular non-symlink artifact: {path.name}")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(_CHUNK_BYTES), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _deadline(deadline_monotonic: float | None) -> float:
    value = time.monotonic() + 600 if deadline_monotonic is None else deadline_monotonic
    if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value):
        raise AcquisitionError("deadline must be a finite monotonic timestamp")
    return float(value)


def _remaining(deadline: float) -> float:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise AcquisitionError("acquisition/selection monotonic deadline exceeded")
    return remaining


def allowed_artifacts(manifest: dict) -> tuple[ArtifactSpec, ...]:
    """Build URLs only from the validated manifest's exact eight-file allowlist."""
    validate_manifest(manifest)
    artifacts = []
    for kind, source in (("model", manifest["model"]), ("dataset", manifest["dataset"])):
        filenames = (source["files"] if kind == "model" else
                     [source["files"][split] for split in ("train", "validation", "test")])
        prefix = "datasets/" if kind == "dataset" else ""
        base = f"https://huggingface.co/{prefix}{source['repo']}"
        for filename in filenames:
            size, digest = _PUBLISHED_CONTENT.get(filename, (_METADATA_SIZES.get(filename), None))
            artifacts.append(ArtifactSpec(
                kind, source["repo"], source["revision"], filename,
                f"{kind}/{filename}", f"{base}/resolve/{source['revision']}/{filename}",
                size, digest,
                f"{base}/{'raw' if digest else 'blob'}/{source['revision']}/{filename}"))
    return tuple(artifacts)


def _safe_remote_url(url: str) -> str:
    parsed = urlsplit(url)
    host = (parsed.hostname or "").lower()
    allowed = (host in {"huggingface.co", "hf.co"} or
               host.endswith(".huggingface.co") or host.endswith(".hf.co"))
    if parsed.scheme != "https" or not allowed or parsed.username or parsed.password or parsed.port not in (None, 443):
        raise AcquisitionError("download redirect left the HTTPS Hugging Face host allowlist")
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))


class _PinnedRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, request, response, code, message, headers, newurl):
        _safe_remote_url(newurl)
        return super().redirect_request(request, response, code, message, headers, newurl)


@dataclass
class _DownloadBudget:
    limit: int
    used: int = 0


def _download_one(spec: ArtifactSpec, directory: Path, budget: _DownloadBudget,
                  deadline: float, opener: Callable, record: dict) -> None:
    target = directory / spec.relative_path
    partial = target.with_name(target.name + ".partial")
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() or target.is_symlink() or partial.exists() or partial.is_symlink():
        raise AcquisitionError("refusing to replace an existing or partial artifact")
    digest = hashlib.sha256()
    git_digest = None
    record.update({"bytes": 0, "sha256": digest.hexdigest(), "status": "pending"})
    remaining_bytes = budget.limit - budget.used
    if spec.expected_bytes is not None and spec.expected_bytes > remaining_bytes:
        raise AcquisitionError("published file size exceeds remaining download budget")
    request = Request(spec.url, headers={"Accept-Encoding": "identity",
                                        "User-Agent": "hadamard-exposition-benchmark/1"})
    with opener(request, timeout=min(30, _remaining(deadline))) as response:
        if response.status != 200:
            raise AcquisitionError(f"download requires HTTP 200, received {response.status}")
        record["resolved_url_without_query"] = _safe_remote_url(response.geturl())
        record["resolved_url_sha256"] = hashlib.sha256(response.geturl().encode()).hexdigest()
        raw_length = response.headers.get("Content-Length")
        if raw_length is not None and not re.fullmatch(r"[0-9]+", raw_length):
            raise AcquisitionError("invalid response Content-Length")
        length = int(raw_length) if raw_length is not None else None
        record["response_content_length"] = length
        if length is not None and length > remaining_bytes:
            raise AcquisitionError("response Content-Length exceeds remaining download budget")
        if length is not None and spec.expected_bytes is not None and length != spec.expected_bytes:
            raise AcquisitionError("response Content-Length differs from the pinned published size")
        if response.headers.get("Content-Encoding", "identity").lower() != "identity":
            raise AcquisitionError("compressed transfer representation is not permitted")
        etag = response.headers.get("ETag", "").strip('"')
        record["response_etag"] = etag
        expected = spec.expected_bytes if spec.expected_bytes is not None else length
        if re.fullmatch(r"[a-f0-9]{40}", etag) and expected is not None:
            git_digest = hashlib.sha1(f"blob {expected}\0".encode())
        record["status"] = "partial"
        record["partial_path"] = str(partial.relative_to(directory))
        with partial.open("xb") as stream:
            os.chmod(partial, 0o600)
            while True:
                _remaining(deadline)
                allowance = budget.limit - budget.used
                if allowance <= 0:
                    if length is not None and record["bytes"] == length:
                        break
                    raise AcquisitionError("download body exhausted the byte budget")
                incomplete = None
                try:
                    chunk = response.read(min(_CHUNK_BYTES, allowance))
                except IncompleteRead as error:
                    # HTTPResponse can attach bytes already received to this
                    # exception. Charge and preserve those bytes as well.
                    chunk, incomplete = error.partial, error
                if not chunk:
                    if incomplete is not None:
                        raise AcquisitionError("network response ended in an incomplete body") from incomplete
                    break
                budget.used += len(chunk)
                record["bytes"] += len(chunk)
                digest.update(chunk)
                if git_digest is not None:
                    git_digest.update(chunk)
                record["sha256"] = digest.hexdigest()
                stream.write(chunk)
                if (expected is not None and record["bytes"] > expected) or budget.used > budget.limit:
                    raise AcquisitionError("download body exceeds its declared size or byte budget")
                if incomplete is not None:
                    raise AcquisitionError("network response ended in an incomplete body") from incomplete
            stream.flush()
            os.fsync(stream.fileno())
        _remaining(deadline)
        if not record["bytes"] or (expected is not None and record["bytes"] != expected):
            raise AcquisitionError("empty or truncated download")
        if spec.expected_sha256 is not None and record["sha256"] != spec.expected_sha256:
            raise AcquisitionError("download SHA256 differs from the immutable LFS pointer")
        if git_digest is not None and git_digest.hexdigest() != etag:
            raise AcquisitionError("download bytes differ from the response Git-blob ETag")
        os.link(partial, target)
        partial.unlink()
        record.pop("partial_path")
        record["status"] = "complete"


def acquire(manifest: dict, output_dir: Path | str, *,
            deadline_monotonic: float | None = None, opener: Callable | None = None) -> dict:
    """Download exact pinned inputs, retaining one immutable success/failure receipt.

    A failure raises AcquisitionError after saving acquisition.json. No retry,
    resume, unpinned fallback, model loading or dataset evaluation occurs here.
    """
    specs = allowed_artifacts(manifest)
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=False)
    deadline = _deadline(deadline_monotonic)
    started = time.monotonic()
    budget = _DownloadBudget(manifest["budgets"]["model_and_data_download_bytes"])
    receipt = {"schema_version": "hadamard-model-acquisition.v1", "status": "failed",
               "campaign_id": manifest["campaign_id"], "started_utc": _utc_now(),
               "manifest_canonical_sha256": hashlib.sha256(_json_bytes(manifest)).hexdigest(),
               "byte_limit": budget.limit, "model_directory": "model", "files": [],
               "trust_remote_code": False, "model_calls": 0, "campaign_ready": False,
               "parameter_buffer_counts": None, "parameter_buffer_audit_required": True}
    if opener is None:
        opener = build_opener(_PinnedRedirectHandler()).open
    failure = None
    try:
        for spec in specs:
            record = {"kind": spec.kind, "repo": spec.repo, "revision": spec.revision,
                      "filename": spec.filename, "path": spec.relative_path, "url": spec.url,
                      "published_bytes": spec.expected_bytes, "published_sha256": spec.expected_sha256,
                      "provenance_url": spec.provenance_url}
            receipt["files"].append(record)
            _download_one(spec, directory, budget, deadline, opener, record)
        receipt["status"] = "complete"
    except Exception as error:
        failure = error
        # A redirect may carry a signed query; retain the error category without
        # publishing transient credentials from arbitrary networking exceptions.
        receipt["error"] = {"type": type(error).__name__,
                            "message": str(error) if isinstance(error, AcquisitionError) else "input acquisition failed"}
    finally:
        receipt.update({"finished_utc": _utc_now(), "elapsed_seconds": time.monotonic() - started,
                        "downloaded_bytes": budget.used})
        _atomic_new(directory / "acquisition.json", _json_bytes(receipt))
    if failure is not None:
        raise AcquisitionError(f"acquisition failed; retained receipt: {directory / 'acquisition.json'}") from failure
    return receipt


def verify_acquisition(manifest: dict, artifact_dir: Path | str) -> dict:
    """Reject incomplete, changed, extra or unpinned inputs before local loading."""
    directory = Path(artifact_dir)
    receipt_path = directory / "acquisition.json"
    if receipt_path.is_symlink():
        raise AcquisitionError("acquisition receipt cannot be a symlink")
    receipt = json.loads(receipt_path.read_text())
    specs = allowed_artifacts(manifest)
    if (receipt.get("schema_version") != "hadamard-model-acquisition.v1" or
            receipt.get("status") != "complete" or
            receipt.get("manifest_canonical_sha256") != hashlib.sha256(_json_bytes(manifest)).hexdigest()):
        raise AcquisitionError("acquisition receipt is incomplete or belongs to another manifest")
    records = receipt.get("files", [])
    if not isinstance(records, list) or [r.get("path") for r in records] != [s.relative_path for s in specs]:
        raise AcquisitionError("acquisition receipt does not contain the exact ordered allowlist")
    total = 0
    for spec, record in zip(specs, records, strict=True):
        path = directory / spec.relative_path
        if (record.get("status") != "complete" or record.get("url") != spec.url or
                record.get("repo") != spec.repo or record.get("revision") != spec.revision or
                record.get("filename") != spec.filename or record.get("kind") != spec.kind):
            raise AcquisitionError("acquisition provenance does not match a pinned input")
        digest = _sha256_file(path)
        size = path.stat().st_size
        if (digest != record.get("sha256") or size != record.get("bytes") or
                (spec.expected_sha256 is not None and digest != spec.expected_sha256) or
                (spec.expected_bytes is not None and size != spec.expected_bytes)):
            raise AcquisitionError("acquired artifact no longer matches its recorded bytes")
        total += size
    if total != receipt.get("downloaded_bytes") or total > manifest["budgets"]["model_and_data_download_bytes"]:
        raise AcquisitionError("acquisition byte accounting is invalid")
    for kind in ("model", "dataset"):
        actual = {str(path.relative_to(directory)) for path in (directory / kind).rglob("*") if not path.is_dir()}
        if actual != {spec.relative_path for spec in specs if spec.kind == kind}:
            raise AcquisitionError("artifact directory contains unrecorded inputs")
    return receipt


def read_parquet_rows(path: Path) -> list[str]:
    """Read only the pinned text column, preserving Parquet row order."""
    import pyarrow as pa
    import pyarrow.parquet as pq

    parquet = pq.ParquetFile(path, memory_map=False)
    schema = parquet.schema_arrow
    if schema.names != ["text"] or not (pa.types.is_string(schema.field("text").type) or
                                        pa.types.is_large_string(schema.field("text").type)):
        raise AcquisitionError("WikiText Parquet must contain only the string text column")
    return parquet.read(columns=["text"], use_threads=False).column("text").to_pylist()


def select_from_rows(manifest: dict, rows_by_split: Mapping[str, Sequence[str]],
                     tokenizer, *, deadline_monotonic: float | None = None) -> tuple[dict, dict]:
    """Use the frozen first-eligible rule; return private records and public counts."""
    validate_manifest(manifest)
    deadline = _deadline(deadline_monotonic)
    dataset = manifest["dataset"]
    roles, counts = {}, {}
    for role in _ROLES:
        _remaining(deadline)
        config = dataset["roles"][role]
        split, required = config["split"], config["articles"]
        rows = rows_by_split[split]
        articles = parse_articles(rows, split)
        scanned, tokenized, token_counts, eligible = [], {}, {}, 0
        for article in articles:
            _remaining(deadline)
            article["article_id"] = f"{dataset['revision']}/{dataset['config']}/{split}/{article['start_row']}"
            identity = article["article_id"]
            tokens = tokenizer.encode(article["text"], add_special_tokens=False, truncation=False)
            scanned.append(article)
            tokenized[identity] = tokens
            token_counts[identity] = len(tokens)
            if len(tokens) >= config["tokens_per_article"]:
                eligible += 1
            if eligible == required:
                break
        selected = select_article_prefixes(scanned, tokenized, count=required,
                                           length=config["tokens_per_article"])
        for record in selected:
            record.update({"dataset_repo": dataset["repo"], "dataset_revision": dataset["revision"],
                           "dataset_config": dataset["config"], "role": role,
                           "full_article_tokens": token_counts[record["article_id"]],
                           "prefix_tokens": len(record["token_ids"])})
        roles[role] = selected
        counts[role] = {"source_rows": len(rows), "parsed_articles": len(articles),
                        "tokenized_articles": len(scanned), "selected_articles": len(selected)}
    assert_disjoint_roles(roles)
    _remaining(deadline)
    return roles, counts


def select_roles(manifest: dict, artifact_dir: Path | str, output_dir: Path | str, *,
                 tokenizer=None, row_reader: Callable = read_parquet_rows,
                 deadline_monotonic: float | None = None) -> dict:
    """Write tokenless public identities and separate local token files per role.

    Run this in a dedicated process. It imports the tokenizer only, never a
    model. local_files_only and trust_remote_code=False prohibit remote model
    code and discovery of unrecorded tokenizer assets.
    """
    directory, artifact_dir = Path(output_dir), Path(artifact_dir)
    directory.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    deadline = _deadline(deadline_monotonic)
    receipt = {"schema_version": "hadamard-model-selection.v1", "status": "failed",
               "campaign_id": manifest["campaign_id"], "started_utc": _utc_now(),
               "manifest_canonical_sha256": hashlib.sha256(_json_bytes(manifest)).hexdigest(),
               "model_calls": 0, "calibration_examples": 0, "campaign_ready": False}
    failure = None
    try:
        _remaining(deadline)
        acquisition = verify_acquisition(manifest, artifact_dir)
        _remaining(deadline)
        receipt["acquisition_sha256"] = _sha256_file(artifact_dir / "acquisition.json")
        receipt["inputs"] = [{k: record[k] for k in ("path", "bytes", "sha256", "url")}
                             for record in acquisition["files"]]
        if tokenizer is None:
            from transformers import AutoTokenizer

            tokenizer = AutoTokenizer.from_pretrained(
                str(artifact_dir / "model"), local_files_only=True,
                trust_remote_code=False, use_fast=True)
        receipt["tokenizer_class"] = type(tokenizer).__name__
        receipt["tokenizer_options"] = {"local_files_only": True, "trust_remote_code": False,
                                         "add_special_tokens": False, "truncation": False}
        rows = {}
        for split, filename in manifest["dataset"]["files"].items():
            _remaining(deadline)
            rows[split] = row_reader(artifact_dir / "dataset" / filename)
        roles, counts = select_from_rows(manifest, rows, tokenizer,
                                         deadline_monotonic=deadline)
        receipt["roles"] = {role: [{k: v for k, v in record.items() if k != "token_ids"}
                                    for record in records] for role, records in roles.items()}
        receipt["selection_counts"] = counts
        receipt["local_token_files"] = {}
        for role in _ROLES:
            _remaining(deadline)
            path = directory / f"tokens.{role}.json"
            content = _json_bytes({"schema_version": "hadamard-model-token-prefixes.v1",
                                   "role": role, "records": roles[role]})
            _atomic_new(path, content)
            receipt["local_token_files"][role] = {"path": path.name, "bytes": len(content),
                                                   "sha256": hashlib.sha256(content).hexdigest()}
        _remaining(deadline)
        receipt.update({"status": "complete", "role_disjointness": "passed",
                        "quality_evaluation_started": False})
    except Exception as error:
        failure = error
        receipt["error"] = {"type": type(error).__name__,
                            "message": str(error) if isinstance(error, ContractError) else "input selection failed"}
    finally:
        receipt.update({"finished_utc": _utc_now(), "elapsed_seconds": time.monotonic() - started})
        _atomic_new(directory / "selection.json", _json_bytes(receipt))
    if failure is not None:
        raise AcquisitionError(f"selection failed; retained receipt: {directory / 'selection.json'}") from failure
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("download", "select"))
    parser.add_argument("--manifest", type=Path, default=Path(__file__).with_name("model-benchmark-v1.json"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--artifacts", type=Path)
    parser.add_argument("--seconds", type=float, default=600)
    arguments = parser.parse_args()
    if not math.isfinite(arguments.seconds) or arguments.seconds <= 0 or arguments.seconds > 600:
        parser.error("--seconds must be greater than zero and at most 600")
    manifest = json.loads(arguments.manifest.read_text())
    deadline = time.monotonic() + arguments.seconds
    if arguments.operation == "download":
        receipt = acquire(manifest, arguments.output, deadline_monotonic=deadline)
    else:
        if arguments.artifacts is None:
            parser.error("select requires --artifacts")
        receipt = select_roles(manifest, arguments.artifacts, arguments.output,
                               deadline_monotonic=deadline)
    print(json.dumps({"status": receipt["status"], "output": str(arguments.output),
                      "model_calls": 0, "campaign_ready": False}))


if __name__ == "__main__":
    main()
