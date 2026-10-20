#!/usr/bin/env python3
"""Build a history-free exposition bundle; publish nothing and preserve frozen bytes."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
from html.parser import HTMLParser
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from urllib.parse import unquote, urlsplit

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
META = ('README.md', 'index.html', 'SUBMISSION.md', 'LICENSE.md',
        'LICENSE-MIT.txt', 'LICENSE-CC-BY-4.0.md', 'CITATION.cff', '.nojekyll')
RESERVED = {'MANIFEST.json', 'SHA256SUMS'}
THREAD_ENV = {k: '1' for k in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS')}


class ReleaseError(ValueError):
    """A release boundary failed. No publication may follow."""


def safe_path(name: str) -> str:
    if not isinstance(name, str) or not re.fullmatch(r'[A-Za-z0-9._/-]+', name):
        raise ReleaseError('Invalid release path')
    path = PurePosixPath(name)
    if not path.parts or path.is_absolute() or path.as_posix() != name or any(p.casefold() in ('.', '..', '.git') for p in path.parts):
        raise ReleaseError(f'Unsafe release path: {name!r}')
    return name


def blob_id(data: bytes) -> str:
    return hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def json_bytes(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + '\n').encode()


def git(repo: Path, *args: str) -> bytes:
    result = subprocess.run(['git', '-C', str(repo), *args], capture_output=True, timeout=30)
    if result.returncode:
        raise ReleaseError(f'Git read failed: {args[0]}')
    return result.stdout


def collect(repo: Path, spec: dict) -> dict[str, bytes]:
    """Read only allowlisted regular blobs at a full, frozen commit identity."""
    ref = spec.get('source_commit', '')
    if not re.fullmatch(r'[0-9a-f]{40}', ref):
        raise ReleaseError('Source must be a full commit SHA, not a mutable ref')
    paths = spec.get('files')
    if not isinstance(paths, dict) or not paths:
        raise ReleaseError('An explicit nonempty allowlist is required')
    for name, expected in paths.items():
        safe_path(name)
        if name in RESERVED or not re.fullmatch(r'[0-9a-f]{40}', expected):
            raise ReleaseError('Invalid artifact identity')
    if len({p.casefold() for p in paths}) != len(paths):
        raise ReleaseError('Case-insensitive path collision')
    if git(repo, 'rev-parse', '--verify', ref + '^{commit}').decode().strip() != ref:
        raise ReleaseError('Source does not resolve to the exact commit')
    tree = {}
    for item in git(repo, 'ls-tree', '-rz', '--full-tree', ref).split(b'\0'):
        if item:
            info, name = item.split(b'\t', 1)
            mode, kind, oid = info.decode().split()
            tree[name.decode()] = mode, kind, oid
    files = {}
    for name, expected in sorted(paths.items()):
        if tree.get(name) != ('100644', 'blob', expected):
            raise ReleaseError(f'Missing, changed, or non-regular frozen input: {name}')
        data = git(repo, 'cat-file', 'blob', expected)
        if blob_id(data) != expected:
            raise ReleaseError(f'Frozen byte identity mismatch: {name}')
        files[name] = data
    return files


def scan(files: dict[str, bytes]) -> None:
    """Bounded high-confidence credential scan of payload bytes, never private history."""
    rules = {
        'private-key-header': rb'-----BEGIN (?:[A-Z0-9]+ )*PRIVATE KEY-----',
        'github-token': rb'\bgh[pousr]_[A-Za-z0-9]{36,}\b',
        'github-fine-grained-token': rb'\bgithub_pat_[A-Za-z0-9_]{60,}\b',
        'openai-project-token': rb'\bsk-proj-[A-Za-z0-9_-]{40,}\b',
    }
    findings = [(name, rule) for name, data in files.items()
                for rule, pattern in rules.items() if re.search(pattern, data)]
    if findings:
        raise ReleaseError('Credential indicators found, values withheld: ' + repr(findings))


class Links(HTMLParser):
    def __init__(self):
        super().__init__(); self.targets = []
    def handle_starttag(self, tag, attrs):
        for key, value in attrs:
            if key in ('href', 'src') and value:
                self.targets.append(value)


def check_links(files: dict[str, bytes]) -> None:
    for name, data in files.items():
        if not name.endswith(('.md', '.html')):
            continue
        text = data.decode('utf-8')
        if name.endswith('.html'):
            parser = Links(); parser.feed(text); targets = parser.targets
        else:
            targets = re.findall(r'\[[^\]]*\]\(([^\s)]+)\)', text)
        for target in targets:
            parsed = urlsplit(target)
            if parsed.scheme or parsed.netloc or not parsed.path:
                continue
            relative = unquote(parsed.path)
            path = PurePosixPath(name).parent / relative
            parts = []
            for part in path.parts:
                if part == '..':
                    if not parts: raise ReleaseError(f'Link escapes bundle in {name}')
                    parts.pop()
                elif part != '.': parts.append(part)
            resolved = '/'.join(parts)
            if resolved not in files:
                raise ReleaseError(f'Unbundled local link in {name}: {target}')


def checksums(files: dict[str, bytes]) -> bytes:
    return ''.join(f'{sha256(data)}  {name}\n' for name, data in sorted(files.items())).encode()


def seal(files: dict[str, bytes], ref: str) -> dict[str, bytes]:
    if RESERVED & files.keys(): raise ReleaseError('Reserved metadata path collision')
    result = dict(files)
    result['MANIFEST.json'] = json_bytes({
        'schema': 'hadamard-public-bundle.v1', 'scientific_source_commit': ref,
        'publication_status': 'not_recorded', 'public_publication_utc': None,
        'note': 'A preparation date or Git commit date is not public-priority evidence.',
        'files': {name: {'bytes': len(data), 'sha256': sha256(data), 'git_blob_sha1': blob_id(data)}
                  for name, data in sorted(files.items())},
    })
    result['SHA256SUMS'] = checksums(result)
    return result


def verify(files: dict[str, bytes]) -> dict:
    try:
        manifest = json.loads(files['MANIFEST.json'])
        if manifest.get('schema') != 'hadamard-public-bundle.v1': raise ReleaseError('Unknown manifest schema')
        if len({p.casefold() for p in files}) != len(files): raise ReleaseError('Case-insensitive path collision')
        records = manifest['files']
        if not isinstance(records, dict) or not records: raise ReleaseError('Empty manifest')
        if set(files) != set(records) | RESERVED: raise ReleaseError('Bundle inventory mismatch')
        for name, identity in records.items():
            safe_path(name)
            data = files[name]
            actual = {'bytes': len(data), 'sha256': sha256(data), 'git_blob_sha1': blob_id(data)}
            if actual != identity: raise ReleaseError(f'Bundle byte identity mismatch: {name}')
        if files['SHA256SUMS'] != checksums({k: v for k, v in files.items() if k != 'SHA256SUMS'}):
            raise ReleaseError('SHA256SUMS mismatch')
    except (KeyError, TypeError, json.JSONDecodeError) as error:
        raise ReleaseError('Malformed or missing bundle manifest') from error
    scan(files)
    check_links(files)
    return manifest


def write_zip(path: Path, files: dict[str, bytes]) -> None:
    """Stored ZIP avoids compressor-version variability; metadata is fixed."""
    with zipfile.ZipFile(path, 'x', compression=zipfile.ZIP_STORED) as archive:
        for name, data in sorted(files.items()):
            safe_path(name)
            info = zipfile.ZipInfo('hadamard-exposition-v1/' + name, (2026, 10, 20, 0, 0, 0))
            info.create_system = 3; info.external_attr = 0o100644 << 16
            archive.writestr(info, data)


def require_new_output(output: Path) -> None:
    if output.exists() or output.is_symlink():
        raise ReleaseError('Output already exists; use a new directory to preserve prior evidence')


def write_files(root: Path, files: dict[str, bytes]) -> None:
    for name, data in files.items():
        safe_path(name)
        dest = root / name; dest.parent.mkdir(parents=True, exist_ok=True)
        with dest.open('xb') as stream: stream.write(data)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'build' / 'public-release-v1')
    args = parser.parse_args()
    output = args.output.absolute()
    created_output = False
    try:
        require_new_output(output)
        spec = json.loads((HERE / 'spec.json').read_text())
        head = git(ROOT, 'rev-parse', 'HEAD').decode().strip()
        bound = ['release/build_bundle.py', 'release/spec.json'] + ['release/templates/' + p for p in META]
        source_hashes = {}
        for path in bound:
            current = ROOT / path
            if current.is_symlink() or current.read_bytes() != git(ROOT, 'show', head + ':' + path):
                raise ReleaseError(f'Release tooling differs from committed source: {path}')
            source_hashes[path] = sha256(current.read_bytes())
        files = collect(ROOT, spec)
        for name in META:
            if name in files: raise ReleaseError('Template replaces frozen scientific input')
            files[name] = (HERE / 'templates' / name).read_bytes()
        files = seal(files, spec['source_commit'])
        verify(files)
        output.mkdir(parents=True)
        created_output = True
        report = {'schema': 'hadamard-release-build.v1', 'status': 'running',
                  'tool_commit': head, 'tool_source_sha256': source_hashes,
                  'scientific_source_commit': spec['source_commit'], 'publication_performed': False,
                  'started_utc': datetime.now(timezone.utc).isoformat(),
                  'frozen_files_verified': len(spec['files']), 'payload_file_count': len(files)}
        (output / 'build-report.json').write_bytes(json_bytes(report))
        with tempfile.TemporaryDirectory(prefix='hadamard-release-check-') as temp:
            check = Path(temp); write_files(check, files)
            result = subprocess.run([sys.executable, 'scripts/validate.py', '--reproduce'], cwd=check,
                                    env={**os.environ, **THREAD_ENV}, capture_output=True, timeout=300)
            (output / 'validation.stdout.log').write_bytes(result.stdout)
            (output / 'validation.stderr.log').write_bytes(result.stderr)
            receipt = check / 'build' / 'validation.json'
            if receipt.exists(): shutil.copyfile(receipt, output / 'validation.json')
            if result.returncode != 0 or not receipt.exists():
                raise ReleaseError('Isolated scientific reproduction failed; no release archive created')
            observed = json.loads(receipt.read_text())
            if observed.get('status') != 'passed' or not observed.get('reproduce_requested'):
                raise ReleaseError('Scientific reproduction receipt did not pass')
            if any((check / name).read_bytes() != data for name, data in files.items()):
                raise ReleaseError('Reproduction changed a release input')
        write_files(output / 'payload', files)
        archive = output / 'hadamard-exposition-v1.zip'
        write_zip(archive, files)
        with zipfile.ZipFile(archive) as check_zip:
            readback = {name.removeprefix('hadamard-exposition-v1/'): check_zip.read(name) for name in check_zip.namelist()}
        if readback != files: raise ReleaseError('ZIP readback differs from verified payload')
        verify(readback)
        report.update(status='passed', finished_utc=datetime.now(timezone.utc).isoformat(),
                      archive_sha256=sha256(archive.read_bytes()), archive_bytes=archive.stat().st_size,
                      manifest_sha256=sha256(files['MANIFEST.json']),
                      validation_receipt_sha256=sha256((output / 'validation.json').read_bytes()),
                      local_links_complete=True, bounded_credential_scan='no_indicators',
                      history_exported=False, original_inputs_unchanged=True)
        (output / 'build-report.json').write_bytes(json_bytes(report))
        print(json.dumps(report, indent=2))
        return 0
    except (OSError, subprocess.SubprocessError, ReleaseError, json.JSONDecodeError) as error:
        if created_output and (output / 'build-report.json').is_file():
            report = json.loads((output / 'build-report.json').read_text())
            report.update(status='failed', error=str(error), publication_performed=False)
            (output / 'build-report.json').write_bytes(json_bytes(report))
        print(f'Release blocked: {error}', file=sys.stderr)
        return 1


if __name__ == '__main__': raise SystemExit(main())
