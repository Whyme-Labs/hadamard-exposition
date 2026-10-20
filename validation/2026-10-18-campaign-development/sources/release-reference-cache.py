#!/usr/bin/env python3
"""One bounded advisory pass over the retained reference campaign's own files.

File bytes are preserved. A successful syscall does not prove reclamation.
Run the unchanged campaign preflight separately after this command finishes.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import resource
import signal
import stat
import sys
import time


OWNED_ROOTS = ("build/model-campaign-development-002",)
SECONDS = 120
ADDRESS_SPACE_BYTES = 512 * 1024 * 1024
DIRECTORY_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
FILE_FLAGS = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC


def identity(value):
    return {name: getattr(value, "st_" + name) for name in
            ("dev", "ino", "mode", "nlink", "uid", "size", "mtime_ns", "ctime_ns")}


def open_directory(parent_fd, relative):
    descriptor = os.dup(parent_fd)
    try:
        for component in Path(relative).parts:
            if component in (".", "..") or "/" in component:
                raise ValueError("Directory traversal is outside the fixed scope")
            child = os.open(component, DIRECTORY_FLAGS, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = child
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise


def write_new(path, value):
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    repo = arguments.repo.absolute()
    output = arguments.output.absolute()
    if repo.is_symlink() or repo.resolve() != repo:
        raise ValueError("Repository must be a concrete non-symlink path")
    if not output.is_relative_to(repo / "build"):
        raise ValueError("Evidence must be a fresh directory below this repository's build")
    if any(output.is_relative_to(repo / root) for root in OWNED_ROOTS):
        raise ValueError("Evidence cannot be inside an advised tree")
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.parent.resolve() != output.parent:
        raise ValueError("Evidence ancestors cannot be symlinks")
    output.mkdir(exist_ok=False)
    started = time.monotonic()
    deadline = started + SECONDS
    script_sha = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    record = {"schema_version": "hadamard-owned-cache-advice.v1", "status": "failed",
              "started_utc": datetime.now(timezone.utc).isoformat(),
              "scope_roots": list(OWNED_ROOTS), "deadline_seconds": SECONDS,
              "address_space_limit_bytes": ADDRESS_SPACE_BYTES,
              "script_sha256_before": script_sha, "advice": "POSIX_FADV_DONTNEED",
              "advice_offset": 0, "advice_length": 0,
              "data_writes": 0, "deletions": 0, "global_cache_controls": False,
              "reclamation_guaranteed": False, "campaign_ready": False,
              "model_calls": 0, "network_bytes": 0,
              "advised_files": 0, "advised_logical_bytes": 0, "skipped_symlinks": [],
              "metadata_unchanged_after_advice": True, "errors": []}
    write_new(output / "start.json", record)

    def check_deadline(*unused):
        if unused or time.monotonic() >= deadline:
            raise TimeoutError("Owned-cache maintenance exceeded its fixed deadline")

    resource.setrlimit(resource.RLIMIT_AS, (ADDRESS_SPACE_BYTES, ADDRESS_SPACE_BYTES))
    signal.signal(signal.SIGALRM, check_deadline)
    signal.setitimer(signal.ITIMER_REAL, max(0.001, deadline - time.monotonic()))
    repo_fd = os.open(repo, DIRECTORY_FLAGS)
    lock_fd = None
    journal_hash = hashlib.sha256()
    try:
        build_fd = open_directory(repo_fd, "build")
        try:
            lock_fd = os.open("model-campaign.process-lock", os.O_RDWR | os.O_CREAT |
                              os.O_NOFOLLOW | os.O_CLOEXEC, 0o600, dir_fd=build_fd)
        finally:
            os.close(build_fd)
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with (output / "files.jsonl").open("xb") as journal:
            for relative_root in OWNED_ROOTS:
                root_fd = open_directory(repo_fd, relative_root)
                try:
                    def walk_error(error):
                        raise error

                    for directory, names, files, directory_fd in os.fwalk(
                            ".", dir_fd=root_fd, follow_symlinks=False, onerror=walk_error):
                        check_deadline()
                        for name in sorted(names + files):
                            path = (Path(relative_root) / directory / name).as_posix()
                            observed = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
                            if stat.S_ISLNK(observed.st_mode):
                                record["skipped_symlinks"].append(path)
                                continue
                            if stat.S_ISDIR(observed.st_mode):
                                continue
                            if (not stat.S_ISREG(observed.st_mode) or observed.st_nlink != 1
                                    or observed.st_uid != os.getuid()):
                                raise ValueError(f"Unexpected file ownership or type: {path}")
                            entry = {"path": path, "identity_before": identity(observed),
                                     "status": "failed"}
                            descriptor = None
                            try:
                                descriptor = os.open(name, FILE_FLAGS, dir_fd=directory_fd)
                                if identity(os.fstat(descriptor)) != entry["identity_before"]:
                                    raise ValueError("Opened file differs from the observed identity")
                                digest = hashlib.sha256()
                                while chunk := os.read(descriptor, 1024 * 1024):
                                    digest.update(chunk)
                                    check_deadline()
                                entry["sha256_before_advice"] = digest.hexdigest()
                                if identity(os.fstat(descriptor)) != entry["identity_before"]:
                                    raise ValueError("File changed while its content was hashed")
                                check_deadline()
                                os.posix_fadvise(descriptor, 0, 0, os.POSIX_FADV_DONTNEED)
                                entry["identity_after"] = identity(os.fstat(descriptor))
                                if entry["identity_after"] != entry["identity_before"]:
                                    record["metadata_unchanged_after_advice"] = False
                                    raise ValueError("File metadata changed after advisory operation")
                                entry["status"] = "advice_accepted"
                                record["advised_files"] += 1
                                record["advised_logical_bytes"] += observed.st_size
                            except Exception as error:
                                entry["error"] = {"type": type(error).__name__, "message": str(error)}
                                raise
                            finally:
                                if descriptor is not None:
                                    os.close(descriptor)
                                payload = (json.dumps(entry, sort_keys=True, separators=(",", ":")) + "\n").encode()
                                journal.write(payload)
                                journal_hash.update(payload)
                finally:
                    os.close(root_fd)
        check_deadline()
        record["status"] = "completed"
    except Exception as error:
        record["errors"].append({"type": type(error).__name__, "message": str(error)})
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        if lock_fd is not None:
            os.close(lock_fd)
        os.close(repo_fd)
        record["elapsed_seconds"] = time.monotonic() - started
        record["worker_os_peak_rss_bytes"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
        record["files_journal_sha256"] = journal_hash.hexdigest()
        record["script_sha256_after"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
        if record["script_sha256_after"] != script_sha or record["elapsed_seconds"] >= SECONDS:
            record["status"] = "failed"
            record["errors"].append({"type": "FinalizationError", "message": "Source changed or deadline expired"})
        write_new(output / "advice.json", record)
    print(json.dumps({key: record[key] for key in
                     ("status", "advised_files", "advised_logical_bytes", "elapsed_seconds", "errors")}))
    return 0 if record["status"] == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
