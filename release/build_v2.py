#!/usr/bin/env python3
"""Build and validate a history-free v2 candidate locally; never publish it."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parent.parent
SCIENCE_PARENT = '12f0463020cfb6e81f9ce2178386668f9b60c27f'
SOURCES = (
    'audit_study.py', 'browser_check.py', 'build_article.py', 'build_pdf.py',
    'conjecture-companion.md', 'counterexample_family.py', 'exact_checks.py',
    'lab.html', 'lab.js', 'protocol-v2.json', 'study.py', 'style.css',
    'test_audit.py', 'test_exact.py', 'test_family.py', 'test_study.py',
    'verify_lab.cjs', 'verify_study.py', 'all_hadamard_checks.py',
    'all-hadamard-addendum.md', 'test_all_hadamard.py', 'build_addendum.py',
)
TEMPLATES = ('README.md', 'SUBMISSION.md', 'CITATION.cff', 'LICENSE.md', 'LICENSE-CC-BY-4.0.md')
FROZEN = {
    'strengthening/study.py': 'cb1648df4390190125b98951cbf24436a3becb4c',
    'strengthening/exact_checks.py': 'c13d30296b49c3f2671d95ebaa47633e7fdabd3a',
    'strengthening/protocol-v2.json': 'a8a267972de0d6ab73429761b219a20eaca472ef',
    'strengthening/counterexample_family.py': '915dfa0f6c867bd619fafe9be1ce9aa43361d995',
    'strengthening/conjecture-companion.md': 'd639876925ccef10fe547a4032cba527b9bbf85e',
    'requirements-v2.txt': 'd59d856f1cc6c05962ca6bd4f14dd3315acd207c',
}
THREADS = {name: '1' for name in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'VECLIB_MAXIMUM_THREADS')}


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def blob_sha(data: bytes) -> str:
    return hashlib.sha1(f'blob {len(data)}\0'.encode() + data).hexdigest()


def safe_read(root: Path, name: str) -> bytes:
    path = PurePosixPath(name)
    if str(path) != name or path.is_absolute() or any(p in ('.', '..') for p in path.parts):
        raise ValueError('unsafe source path')
    current = root
    for part in path.parts:
        current = current / part
        if current.is_symlink():
            raise ValueError('symlink source rejected: ' + name)
    if not current.is_file():
        raise ValueError('regular source file required: ' + name)
    return current.read_bytes()


def reserve_output(destination: Path) -> None:
    if os.path.lexists(destination):
        raise FileExistsError('Refusing to overwrite release output: ' + str(destination))
    destination.mkdir(parents=True, exist_ok=False)


def inventory(root: Path) -> dict[str, str]:
    result = {}
    for path in sorted(root.rglob('*')):
        if path.is_symlink():
            raise ValueError('symlink in payload')
        if path.is_file():
            result[path.relative_to(root).as_posix()] = sha(path.read_bytes())
    return result


def verify_inventory(root: Path, expected: dict[str, str]) -> None:
    if inventory(root) != expected:
        raise ValueError('payload inventory or byte identity changed')


def write_archive(payload: Path, destination: Path) -> None:
    with zipfile.ZipFile(destination, mode='x', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name in inventory(payload):
            info = zipfile.ZipInfo('hadamard-exposition-v2/' + name, date_time=(2026, 10, 21, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, safe_read(payload, name), compresslevel=9)


def write_json(path: Path, value) -> None:
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    temporary.replace(path)


def build(destination: Path, source_root: Path = ROOT) -> dict:
    source_root = source_root.resolve()
    mapping = {f'strengthening/{name}': f'strengthening/{name}' for name in SOURCES}
    mapping.update({f'release/v2/{name}': name for name in TEMPLATES})
    mapping.update({'requirements-v2.txt': 'requirements-v2.txt', 'release/templates/LICENSE-MIT.txt': 'LICENSE-MIT.txt'})
    source_bytes = {name: safe_read(source_root, name) for name in mapping}
    for name, expected in FROZEN.items():
        if blob_sha(source_bytes[name]) != expected:
            raise ValueError('frozen scientific input changed: ' + name)
    reserve_output(destination)
    payload = destination / 'payload'; payload.mkdir()
    logs = destination / 'logs'; logs.mkdir()
    receipt = {'schema': 'hadamard-v2-release-acceptance.v1', 'status': 'running',
               'started_utc': datetime.now(timezone.utc).isoformat(), 'research_parent_commit': SCIENCE_PARENT,
               'builder_sha256': sha(Path(__file__).read_bytes()),
               'source_files': {name: {'sha256': sha(data), 'git_blob_sha1': blob_sha(data)} for name, data in source_bytes.items()},
               'execution_surface': 'assistant_local', 'publication_performed': False, 'phases': []}
    receipt_path = destination / 'acceptance.json'
    write_json(receipt_path, receipt)

    def run(name: str, command: list[str], seconds: int = 60) -> str:
        record = {'name': name, 'command': command, 'timeout_seconds': seconds, 'status': 'running'}
        receipt['phases'].append(record); write_json(receipt_path, receipt)
        result = subprocess.run(command, cwd=payload, env={**os.environ, **THREADS, 'PYTHONDONTWRITEBYTECODE': '1'},
                                capture_output=True, text=True, timeout=seconds)
        (logs/f'{name}.stdout.log').write_text(result.stdout)
        (logs/f'{name}.stderr.log').write_text(result.stderr)
        record.update(exit_code=result.returncode, status='passed' if result.returncode == 0 else 'failed')
        write_json(receipt_path, receipt)
        result.check_returncode()
        return result.stdout

    try:
        for name, target in mapping.items():
            path = payload/target; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(source_bytes[name])
        verification = payload/'verification'; verification.mkdir()
        run('unit-tests', [sys.executable, '-m', 'unittest', 'discover', '-s', 'strengthening', '-p', 'test_*.py', '-v'])
        shutil.copyfile(logs/'unit-tests.stderr.log', verification/'unit-tests.txt')
        run('study', [sys.executable, 'strengthening/study.py', '--output', 'run-v2'], 180)
        (verification/'legacy-audit.json').write_text(run('legacy-audit', [sys.executable, 'strengthening/verify_study.py', 'run-v2']))
        (verification/'audit.json').write_text(run('complete-audit', [sys.executable, 'strengthening/audit_study.py', 'run-v2']))
        witnesses = run('exact-family', [sys.executable, 'strengthening/counterexample_family.py'])
        (payload/'family-checks.json').write_text(witnesses)
        (payload/'family-linear-checks.json').write_text(witnesses)
        run('article', [sys.executable, 'strengthening/build_article.py'])
        (verification/'calculator.json').write_text(run('calculator', ['node', 'strengthening/verify_lab.cjs', 'exposition-v2.html']))
        run('browser', [sys.executable, 'strengthening/browser_check.py'])
        shutil.copyfile(payload/'browser-verification.json', verification/'browser.json')
        (payload/'browser-verification.json').unlink()
        # Screenshots are review evidence outside the public payload, not extra private files.
        shutil.move(str(payload/'review-screenshots'), str(destination/'review-screenshots'))
        run('pdf', [sys.executable, 'strengthening/build_pdf.py'])
        (payload/'all-hadamard-checks.json').write_text(run('all-Hadamard', [sys.executable, 'strengthening/all_hadamard_checks.py']))
        run('addendum', [sys.executable, 'strengthening/build_addendum.py'])
        write_json(payload/'PUBLICATION.json', {'version': '2-submission-candidate', 'public_repository': None,
                   'public_commit': None, 'stable_public_material_url': None, 'first_public_observed_utc': None,
                   'official_submission_record': None, 'committee_selection': None,
                   'note': 'Preparation and local validation are not public publication or prize acceptance.'})
        for name, data in source_bytes.items():
            if safe_read(source_root, name) != data or safe_read(payload, mapping[name]) != data:
                raise ValueError('source or copied payload changed during validation')
        before_manifest = inventory(payload)
        write_json(payload/'MANIFEST.json', {'schema': 'hadamard-v2-public-payload.v1',
                   'research_parent_commit': SCIENCE_PARENT, 'files_sha256': before_manifest,
                   'scope': 'Byte identities only. The new run is same-protocol v2 reproduction, not a new independent sample.',
                   'timestamp_policy': 'ZIP entry dates are fixed for deterministic packaging, not publication evidence.'})
        checksummed = inventory(payload)
        (payload/'SHA256SUMS').write_text(''.join(f'{value}  {name}\n' for name, value in checksummed.items()))
        final_inventory = inventory(payload)
        archive = destination/'hadamard-exposition-v2.zip'
        write_archive(payload, archive)
        extracted = destination/'extracted'
        with zipfile.ZipFile(archive) as zipped:
            zipped.extractall(extracted)
        verify_inventory(extracted/'hadamard-exposition-v2', final_inventory)
        verify_inventory(payload, final_inventory)
        receipt.update(status='passed', payload_files=len(final_inventory), archive_sha256=sha(archive.read_bytes()),
                       archive_bytes=archive.stat().st_size, payload_sha256=final_inventory,
                       archive_extraction_verified=True,
                       note='Numerical, source, calculator and layout checks passed locally. Visual review is recorded separately. No network or public publication action occurred.')
    except Exception as error:
        receipt.update(status='failed', error={'type': type(error).__name__, 'message': str(error)})
        # A partial or unverified archive must never be confused with an accepted release.
        archive = destination/'hadamard-exposition-v2.zip'
        if archive.exists(): archive.rename(destination/'unaccepted-partial.zip')
        raise
    finally:
        receipt['finished_utc'] = datetime.now(timezone.utc).isoformat()
        write_json(receipt_path, receipt)
    return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = build(args.output.absolute())
    print(json.dumps({k: result[k] for k in ('status', 'payload_files', 'archive_sha256', 'archive_bytes')}, indent=2))
