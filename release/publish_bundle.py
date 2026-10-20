#!/usr/bin/env python3
"""Publish a verified bundle through authenticated gh; never expose source history."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import urllib.request

from build_bundle import META, RESERVED, ReleaseError, ROOT, blob_id, json_bytes, safe_path, sha256, verify, write_files

DESTINATION = 'Whyme-Labs/hadamard-exposition-public'
PHASES = {'focused_unit_tests', 'retained_results', 'bundled_calculator', 'group_reproduction', 'inputs_unchanged'}


def load_verified(build: Path, spec: dict) -> dict[str, bytes]:
    report = json.loads((build / 'build-report.json').read_text())
    if report.get('status') != 'passed' or report.get('scientific_source_commit') != spec['source_commit']:
        raise ReleaseError('A passing build receipt for the fixed source is required')
    receipt_bytes = (build / 'validation.json').read_bytes()
    if sha256(receipt_bytes) != report['validation_receipt_sha256']:
        raise ReleaseError('Validation receipt identity mismatch')
    receipt = json.loads(receipt_bytes)
    phases = receipt.get('phases', [])
    if (receipt.get('status') != 'passed' or receipt.get('reproduce_requested') is not True
            or len(phases) != len(PHASES)
            or {p.get('name') for p in phases} != PHASES
            or any(p.get('status') != 'passed' for p in phases)):
        raise ReleaseError('Complete real-payload scientific validation is required')
    payload = build / 'payload'
    if payload.is_symlink() or not payload.is_dir(): raise ReleaseError('Invalid payload directory')
    files = {}
    for path in payload.rglob('*'):
        if path.is_symlink(): raise ReleaseError('Payload contains a symlink')
        if path.is_file(): files[safe_path(path.relative_to(payload).as_posix())] = path.read_bytes()
    if set(files) != set(spec['files']) | set(META) | RESERVED:
        raise ReleaseError('Payload differs from the approved public allowlist')
    manifest = verify(files)
    if manifest.get('scientific_source_commit') != spec['source_commit']:
        raise ReleaseError('Payload source identity mismatch')
    if sha256(files['MANIFEST.json']) != report['manifest_sha256']:
        raise ReleaseError('Payload is not the validated manifest')
    for name, expected in spec['files'].items():
        if manifest['files'].get(name, {}).get('git_blob_sha1') != expected:
            raise ReleaseError(f'Frozen scientific artifact missing or changed: {name}')
    archive = build / 'hadamard-exposition-v1.zip'
    if archive.is_symlink() or sha256(archive.read_bytes()) != report['archive_sha256']:
        raise ReleaseError('Archive identity mismatch')
    return files


def run(argv: list[str], cwd: Path | None = None) -> bytes:
    environment = {k: v for k, v in os.environ.items() if not k.startswith('GIT_')}
    if argv[0] == 'git':
        environment.update(GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL=os.devnull)
    elif argv[0] == 'gh':
        environment['GH_HOST'] = 'github.com'
    result = subprocess.run(argv, cwd=cwd, env=environment, capture_output=True, timeout=180)
    if result.returncode:
        # Do not echo command output that may contain authentication material.
        raise ReleaseError(f'{argv[0]} command failed with exit code {result.returncode}')
    return result.stdout


def prepare_root(stage: Path, files: dict[str, bytes]) -> str:
    if stage.exists() or stage.is_symlink(): raise ReleaseError('Use a new, empty publication stage path')
    stage.mkdir(parents=True)
    write_files(stage, files)
    run(['git', 'init', '--template=', '--initial-branch=main'], cwd=stage)
    run(['git', 'config', 'core.hooksPath', str(stage / '.git' / 'disabled-hooks')], cwd=stage)
    run(['git', 'add', '--all'], cwd=stage)
    run(['git', '-c', 'user.name=Wei Meng Soh', '-c', 'user.email=51080539+wms2537@users.noreply.github.com',
         '-c', 'commit.gpgsign=false', 'commit', '-m', 'Publish the fixed JSP-000013 exposition'], cwd=stage)
    identity = run(['git', 'rev-list', '--parents', 'HEAD'], cwd=stage).decode().split()
    if len(identity) != 1: raise ReleaseError('Publication repository must contain exactly one parentless commit')
    tracked = {}
    for item in run(['git', 'ls-tree', '-rz', 'HEAD'], cwd=stage).split(b'\0'):
        if item:
            info, name = item.split(b'\t', 1)
            mode, kind, oid = info.decode().split()
            tracked[name.decode()] = mode, kind, oid
    expected = {name: ('100644', 'blob', blob_id(data)) for name, data in files.items()}
    if tracked != expected:
        raise ReleaseError('Public commit differs from the verified payload bytes or inventory')
    return identity[0]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build', type=Path, default=ROOT / 'build' / 'public-release-v1')
    parser.add_argument('--stage', type=Path, required=True)
    parser.add_argument('--execute', action='store_true', help='create a private mirror, verify it, then make only that mirror public')
    args = parser.parse_args()
    progress = {'schema': 'hadamard-publication.v1', 'destination': DESTINATION,
                'source_visibility_changed': False, 'official_submission_performed': False,
                'public_observation': None, 'steps_completed': []}
    stage = args.stage.absolute()
    record = stage.parent / (stage.name + '-publication.json')
    try:
        files = load_verified(args.build, json.loads((Path(__file__).parent / 'spec.json').read_text()))
        if not args.execute:
            print('Verified. With --execute, create a fresh private mirror, verify its parentless commit, then make ONLY ' + DESTINATION + ' public.')
            return 0
        if record.exists(): raise ReleaseError('Publication record already exists; inspect prior progress before retrying')
        run(['gh', 'auth', 'status'])
        commit = prepare_root(stage, files)
        progress.update(public_commit=commit, manifest_sha256=sha256(files['MANIFEST.json']))
        record.write_bytes(json_bytes(progress))
        # gh refuses an existing repository; never overwrite or convert an unrelated repo.
        run(['gh', 'repo', 'create', DESTINATION, '--private'])
        progress['steps_completed'].append('empty_private_mirror_created'); record.write_bytes(json_bytes(progress))
        run(['git', 'remote', 'add', 'origin', f'https://github.com/{DESTINATION}.git'], cwd=stage)
        run(['git', '-c', 'credential.helper=', '-c', 'credential.helper=!gh auth git-credential',
             'push', '--set-upstream', 'origin', 'main'], cwd=stage)
        progress['steps_completed'].append('private_mirror_created'); record.write_bytes(json_bytes(progress))
        remote = json.loads(run(['gh', 'api', f'repos/{DESTINATION}/commits/{commit}']))
        if remote.get('sha') != commit or remote.get('parents') != []:
            raise ReleaseError('Remote commit is not the verified parentless release')
        private = json.loads(run(['gh', 'repo', 'view', DESTINATION, '--json', 'isPrivate,nameWithOwner']))
        if private != {'isPrivate': True, 'nameWithOwner': DESTINATION}:
            raise ReleaseError('Remote private staging identity mismatch')
        progress['visibility_request_started_utc'] = datetime.now(timezone.utc).isoformat()
        record.write_bytes(json_bytes(progress))
        run(['gh', 'repo', 'edit', DESTINATION, '--visibility', 'public', '--accept-visibility-change-consequences'])
        progress['steps_completed'].append('mirror_made_public'); record.write_bytes(json_bytes(progress))
        url = f'https://api.github.com/repos/{DESTINATION}/commits/{commit}'
        request = urllib.request.Request(url, headers={'Accept': 'application/vnd.github+json', 'User-Agent': 'hadamard-exposition-release'})
        # This observation deliberately sends no Authorization header.
        with urllib.request.urlopen(request, timeout=30) as response:
            observed = json.load(response)
            server_date = response.headers.get('Date')
        if observed.get('sha') != commit or observed.get('parents') != []:
            raise ReleaseError('Anonymous read did not reproduce the public commit')
        progress['public_observation'] = {'observed_at_utc': datetime.now(timezone.utc).isoformat(),
            'github_server_date': server_date, 'anonymous_commit_url': url,
            'scope': 'first anonymous observation in this publication run, not a committee priority decision'}
        progress['stable_material_url'] = f'https://github.com/{DESTINATION}/blob/{commit}/exposition.html'
        record.write_bytes(json_bytes(progress))
        print(json.dumps(progress, indent=2))
        return 0
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        if record.exists() and progress.get('public_commit'):
            progress['error'] = str(error); record.write_bytes(json_bytes(progress))
        print(f'Publication stopped: {error}. Existing remote state is not deleted or rewritten.', file=sys.stderr)
        return 1


if __name__ == '__main__': raise SystemExit(main())
