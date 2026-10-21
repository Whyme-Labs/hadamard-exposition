#!/usr/bin/env python3
"""Read-only, bounded publication audit. Never print matched secret values.

This is an indicator scan, not a guarantee that a repository has no secrets or
that third-party material may be relicensed. Review every finding and gap.
"""
from __future__ import annotations
import argparse
from collections import Counter
from datetime import datetime, timezone
import gzip
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import tarfile
import urllib.error
import urllib.parse
import urllib.request
import zipfile

REPOSITORY = 'Whyme-Labs/hadamard-exposition'
MAX_FILE = 64 * 1024 * 1024
MAX_TOTAL = 512 * 1024 * 1024
MAX_MEMBERS = 30000
PATTERNS = {
    'private_key': rb'-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----\s+[A-Za-z0-9+/=]{32,}',
    'github_token': rb'\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{50,})\b',
    'aws_access_key': rb'\b(?:AKIA|ASIA)[A-Z0-9]{16}\b',
    'huggingface_token': rb'\bhf_[A-Za-z0-9]{30,}\b',
    'api_secret': rb'\bsk-(?:proj-|ant-)?[A-Za-z0-9_-]{32,}\b',
    'credential_assignment': rb'''(?i)\b(?:password|passwd|api_key|access_token|client_secret)\s*[=:]\s*["'][A-Za-z0-9+/_.=-]{12,}["']''',
    'authenticated_url': rb'https?://[^\s/<>"\x27]{1,80}:[^\s/@<>"\x27]{4,100}@',
    'url_capability': rb'(?i)[?&](?:token|access_token|signature|sig)=[A-Za-z0-9%_+/-]{20,}',
    'personal_email': rb'(?i)\b[A-Z0-9._%+-]+@(?:gmail|hotmail|outlook|protonmail|yahoo)\.com\b',
    'home_path': rb'/(?:home|Users)/[A-Za-z0-9_.-]+(?:/|\b)',
}
RULES = {name: re.compile(pattern) for name, pattern in PATTERNS.items()}
PUBLICATION_SUFFIXES = ('.whl', '.onnx', '.safetensors', '.bin', '.pt', '.pth')


class Audit:
    def __init__(self):
        self.counts = Counter()
        self.findings = []
        self.gaps = []
        self.archives = []
        self.redistribution = []
        self.expanded = 0

    def gap(self, location, reason):
        self.gaps.append({'location': location, 'reason': reason})

    def scan(self, data: bytes, location: str, depth: int = 0):
        self.expanded += len(data)
        if len(data) > MAX_FILE or self.expanded > MAX_TOTAL:
            self.gap(location, 'byte limit reached')
            return
        self.counts['objects_or_members'] += 1
        self.counts['bytes_inspected'] += len(data)
        for name, rule in RULES.items():
            matches = list(rule.finditer(data))
            if matches:
                # Deliberately no matched text, token digest, or surrounding lines.
                lines = sorted({data.count(b'\n', 0, m.start()) + 1 for m in matches})
                self.findings.append({'location': location, 'rule': name, 'count': len(matches), 'lines': lines[:20]})
        if location.lower().endswith(PUBLICATION_SUFFIXES):
            self.redistribution.append({'location': location, 'bytes': len(data), 'note': 'Review third-party origin and redistribution terms; no blanket relicensing.'})
        if data.startswith(b'version https://git-lfs.github.com/spec/v1'):
            self.gap(location, 'Git LFS pointer; referenced object not inspected')
        is_zip = data.startswith((b'PK\x03\x04', b'PK\x05\x06', b'PK\x07\x08'))
        is_gzip = data.startswith(b'\x1f\x8b')
        is_tar = len(data) >= 262 and data[257:262] == b'ustar'
        if not (is_zip or is_gzip or is_tar):
            return
        if depth >= 6:
            self.gap(location, 'archive recursion limit reached')
            return
        self.counts['archives'] += 1
        entry = {'location': location, 'members': 0, 'unpacked_bytes': 0, 'sample_names': []}
        self.archives.append(entry)
        def member(name, size, reader, regular=True):
            entry['members'] += 1
            if self.counts['archive_members'] >= MAX_MEMBERS:
                raise ValueError('archive member limit reached')
            self.counts['archive_members'] += 1
            p = PurePosixPath(name)
            if p.is_absolute() or '..' in p.parts or '\\' in name or not regular:
                self.gap(location + '!' + name, 'unsafe archive path or nonregular member')
                return
            if len(entry['sample_names']) < 12:
                entry['sample_names'].append(name)
            if size > MAX_FILE or size + self.expanded > MAX_TOTAL:
                self.gap(location + '!' + name, 'archive member size limit')
                return
            content = reader.read(MAX_FILE + 1)
            entry['unpacked_bytes'] += len(content)
            self.scan(content, location + '!' + name, depth + 1)
        try:
            if is_zip:
                with zipfile.ZipFile(io.BytesIO(data)) as z:
                    for info in z.infolist():
                        if info.is_dir():
                            continue
                        if info.flag_bits & 1:
                            self.gap(location + '!' + info.filename, 'encrypted archive member')
                            continue
                        mode = info.external_attr >> 16
                        with z.open(info) as stream:
                            member(info.filename, info.file_size, stream, (mode & 0o170000) != 0o120000)
            elif is_tar:
                with tarfile.open(fileobj=io.BytesIO(data), mode='r:') as t:
                    for info in t:
                        if info.isdir():
                            continue
                        if not info.isfile():
                            self.gap(location + '!' + info.name, 'nonregular tar member')
                            continue
                        with t.extractfile(info) as stream:
                            member(info.name, info.size, stream)
            else:
                with gzip.GzipFile(fileobj=io.BytesIO(data)) as z:
                    content = z.read(MAX_FILE + 1)
                    entry['members'] = 1
                    entry['unpacked_bytes'] = len(content)
                    self.scan(content, location + '!gunzip', depth + 1)
        except (ValueError, OSError, EOFError, RuntimeError, zipfile.BadZipFile, tarfile.TarError):
            self.gap(location, 'archive could not be completely inspected')

    def report(self):
        return {'counts': dict(self.counts), 'findings': self.findings, 'gaps': self.gaps,
                'archives': self.archives, 'redistribution_review': self.redistribution,
                'automated_status': 'review_required' if self.findings else 'incomplete' if self.gaps else 'no_indicators_found',
                'publication_authorized_by_scanner': False}


def git(root, *args):
    return subprocess.check_output(['git', '-C', str(root), *args], timeout=60)


def scan_git(root: Path, audit: Audit):
    if git(root, 'rev-parse', '--is-shallow-repository').strip() != b'false':
        raise ValueError('Full history is required, not a shallow clone')
    refs = git(root, 'show-ref').decode().splitlines()
    objects = git(root, 'rev-list', '--objects', '--all').decode().splitlines()
    identities = {}
    for item in objects:
        oid, _, name = item.partition(' ')
        identities.setdefault(oid, name)
    proc = subprocess.Popen(['git', '-C', str(root), 'cat-file', '--batch'], stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    types = Counter()
    try:
        for oid, path in identities.items():
            proc.stdin.write((oid + '\n').encode()); proc.stdin.flush()
            header = proc.stdout.readline().decode().split()
            if len(header) != 3 or header[1] == 'missing':
                raise ValueError('Missing Git object')
            size = int(header[2]); kind = header[1]; types[kind] += 1
            if size > MAX_FILE:
                audit.gap(oid, 'Git object exceeds scan bound')
                remaining = size + 1
                while remaining:
                    block = proc.stdout.read(min(65536, remaining)); remaining -= len(block)
                    if not block: raise ValueError('Truncated Git object')
                continue
            data = proc.stdout.read(size)
            if len(data) != size or proc.stdout.read(1) != b'\n':
                raise ValueError('Truncated Git object')
            if kind in ('blob', 'commit', 'tag'):
                audit.scan(data, 'git:' + oid + ':' + path)
    finally:
        proc.stdin.close(); proc.stdout.close(); proc.wait(timeout=30)
    if proc.returncode != 0:
        raise ValueError('Git object scan failed')
    modes = git(root, 'ls-tree', '-r', 'HEAD').decode().splitlines()
    for row in modes:
        if row.startswith('160000'):
            audit.gap(row.split('\t', 1)[-1], 'submodule content not scanned')
    return {'head': git(root, 'rev-parse', 'HEAD').decode().strip(), 'refs': refs,
            'unique_objects': len(identities), 'object_types': dict(types),
            'scope': 'All objects reachable from fetched branches, tags and PR-head refs; not unreachable deleted GitHub objects.'}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class GitHubRead:
    def __init__(self, token):
        self.token = token
        self.endpoints = []
        self.opener = urllib.request.build_opener(NoRedirect)

    def get(self, path, raw=False):
        if not path.startswith('/') or '..' in path:
            raise ValueError('Repository-relative endpoint required')
        url = 'https://api.github.com/repos/' + REPOSITORY + path
        request = urllib.request.Request(url, headers={'Authorization': 'Bearer ' + self.token, 'Accept': 'application/vnd.github+json', 'User-Agent': 'Hadamard-publication-audit'})
        try:
            with self.opener.open(request, timeout=45) as r:
                data = r.read(MAX_FILE + 1)
        except urllib.error.HTTPError as error:
            if error.code not in (301, 302, 303, 307, 308) or not raw:
                raise
            destination = error.headers.get('Location', '')
            parsed = urllib.parse.urlparse(destination)
            host = parsed.hostname or ''
            allowed = host.endswith(('.blob.core.windows.net', '.githubusercontent.com', '.actions.githubusercontent.com'))
            if parsed.scheme != 'https' or not allowed or parsed.username or parsed.password:
                raise ValueError('Unapproved artifact redirect')
            # No GitHub authorization header is forwarded to the storage host.
            with self.opener.open(urllib.request.Request(destination), timeout=45) as r:
                data = r.read(MAX_FILE + 1)
        if len(data) > MAX_FILE:
            raise ValueError('API response exceeds bound')
        self.endpoints.append({'path': path, 'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data)})
        return data if raw else json.loads(data)

    def pages(self, path, key=None):
        output = []
        for page in range(1, 101):
            value = self.get(path + ('&' if '?' in path else '?') + 'per_page=100&page=' + str(page))
            items = value[key] if key else value
            if not isinstance(items, list): raise ValueError('List expected')
            output.extend(items)
            if len(items) < 100: return output
        raise ValueError('API pagination bound reached')


def scan_remote(api: GitHubRead, audit: Audit):
    counts = Counter()
    def content(value, location):
        audit.scan(json.dumps(value, sort_keys=True).encode(), location)
    for endpoint, key in [('/issues?state=all', None), ('/issues/comments', None), ('/pulls/comments', None), ('/comments', None), ('/releases', None)]:
        try:
            items = api.pages(endpoint, key); counts[endpoint] = len(items)
            for item in items:
                content(item, 'api:' + endpoint + ':' + str(item.get('id', 'unknown')))
                if endpoint.startswith('/issues?') and 'pull_request' in item:
                    for review in api.pages('/pulls/' + str(item['number']) + '/reviews'):
                        content(review, 'api:review:' + str(review['id']))
                        counts['reviews'] += 1
        except (urllib.error.HTTPError, OSError, ValueError):
            audit.gap(endpoint, 'API collection unavailable or incomplete')
    try:
        runs = api.pages('/actions/runs', 'workflow_runs'); counts['workflow_runs'] = len(runs)
        for run in runs:
            if str(run['id']) == os.environ.get('GITHUB_RUN_ID'):
                counts['current_audit_run_excluded'] += 1
                continue
            if run['status'] != 'completed':
                counts['not_completed_runs'] += 1
                audit.gap('run:' + str(run['id']), 'unfinished run; logs can change after this audit')
                continue
            for attempt in range(1, run.get('run_attempt', 1) + 1):
                endpoint = '/actions/runs/' + str(run['id']) + '/attempts/' + str(attempt)
                try:
                    jobs = api.pages(endpoint + '/jobs', 'jobs')
                    if not any(job.get('steps') for job in jobs):
                        counts['no_step_attempts'] += 1
                        continue
                    audit.scan(api.get(endpoint + '/logs', raw=True), 'run:' + str(run['id']) + ':attempt:' + str(attempt) + '.zip')
                    counts['log_archives_scanned'] += 1
                except (urllib.error.HTTPError, OSError, ValueError):
                    audit.gap(endpoint, 'job or log data unavailable')
        artifacts = api.pages('/actions/artifacts', 'artifacts'); counts['artifacts'] = len(artifacts)
        for item in artifacts:
            if item.get('expired'):
                counts['expired_artifacts'] += 1
                continue
            try:
                audit.scan(api.get('/actions/artifacts/' + str(item['id']) + '/zip', raw=True), 'artifact:' + str(item['id']) + '.zip')
            except (urllib.error.HTTPError, OSError, ValueError):
                audit.gap('artifact:' + str(item['id']), 'artifact data unavailable')
    except (urllib.error.HTTPError, OSError, ValueError):
        audit.gap('actions', 'run or artifact collection incomplete')
    return dict(counts)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repository', type=Path)
    parser.add_argument('--archive', type=Path)
    parser.add_argument('--remote', action='store_true')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists(): raise FileExistsError('Do not overwrite prior audit evidence')
    started = datetime.now(timezone.utc).isoformat()
    audit = Audit(); scopes = {}
    if args.repository: scopes['git'] = scan_git(args.repository, audit)
    if args.archive:
        data = args.archive.read_bytes(); audit.scan(data, args.archive.name)
        scopes['archive'] = {'name': args.archive.name, 'sha256': hashlib.sha256(data).hexdigest()}
    endpoints = []
    if args.remote:
        token = os.environ.get('GH_TOKEN')
        if not token: raise ValueError('Authenticated repository read required')
        api = GitHubRead(token)
        scopes['remote'] = scan_remote(api, audit); endpoints = api.endpoints
    report = {'schema': 'hadamard-publication-audit.v1', 'started_utc': started,
              'finished_utc': datetime.now(timezone.utc).isoformat(),
              'scanner_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'scopes': scopes, **audit.report(), 'api_reads': endpoints,
              'limits': {'per_object_bytes': MAX_FILE, 'expanded_bytes': MAX_TOTAL, 'members': MAX_MEMBERS, 'depth': 6},
              'scope_limits': ['Indicator scan only, not a guarantee of no secrets or personal data.', 'No archive member is extracted or executed.', 'Matched credential values are never included in this report.', 'Redistribution and license review remains a separate decision.', 'No repository visibility, history or artifact mutation occurs.']}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({k: report[k] for k in ('automated_status', 'counts')}, indent=2))


if __name__ == '__main__': main()
