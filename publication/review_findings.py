"""Resolve specific audit flags without changing scientific files or visibility.

Verify archive metadata against public PyPI records. Remove only machine-generated
signed-action footers from current PR bodies. Cancel only named zero-step queued
jobs. Historical edit records are not erased. Never exercise a signed link.
"""
from collections import Counter
from datetime import datetime, timezone
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import re
import subprocess
import tarfile
import urllib.parse
import urllib.request
from audit import GitHubRead, REPOSITORY, RULES

ARCHIVES = ('4fa8471dc08aa7cf93724e59a86a89b75a63a6a0',
            'a9eac9bb5e7fc4e5ea5d15ce17c2a2300c65264a',
            '42ba9f23973854df68832a3448270b360d2080cb')
QUEUED_RUNS = (39536825246, 39466379796, 39465140698)
FOOTER = re.compile(r'<!-- codesmith:footer -->.*?<!-- /codesmith:footer -->', re.S)


def clean_footer(body):
    matches = list(FOOTER.finditer(body))
    if len(matches) != 1:
        return body, False
    block = matches[0].group()
    if 'https://backend.blacksmith.sh/track/enable-autofix?' not in block or 'signature=' not in block:
        return body, False
    # Preserve every user-authored byte outside the generated block.
    match = matches[0]
    return body[:match.start()] + body[match.end():], True


def metadata_matches(value, path=''):
    if isinstance(value, str):
        for name in ('personal_email', 'home_path'):
            for match in RULES[name].finditer(value.encode()):
                yield name, path, match.group()
    elif isinstance(value, dict):
        for key, item in value.items():
            yield from metadata_matches(item, path + '.' + key)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from metadata_matches(item, path + '[' + str(index) + ']')


def main():
    token = os.environ['GH_TOKEN']
    api = GitHubRead(token)
    report = {'schema':'hadamard-publication-findings-review.v1',
              'started_utc':datetime.now(timezone.utc).isoformat(),
              'source_commit':os.environ['EXPECTED_SHA'],
              'public_metadata':[], 'footer_removals':[], 'queued_run_actions':[],
              'errors':[], 'public_visibility_changed':False,
              'limitations':['PR edit histories are not erased by current-body edits.',
                             'No signed action URL was requested or exercised.',
                             'No repository history or scientific file was changed.',
                             'This is bounded publication hygiene, not a security certification.']}
    cache = {}
    for oid in ARCHIVES:
        data = subprocess.check_output(['git','cat-file','blob',oid], timeout=30)
        with tarfile.open(fileobj=io.BytesIO(data), mode='r:gz') as archive:
            for member in archive:
                if not member.isfile() or not member.name.endswith('install-report.json'):
                    continue
                payload = json.load(archive.extractfile(member))
                for item in payload['install']:
                    metadata = item['metadata']
                    matches = list(metadata_matches(metadata))
                    if not matches:
                        continue
                    name, version = metadata['name'], metadata['version']
                    key = name, version
                    url = 'https://pypi.org/pypi/' + urllib.parse.quote(name, safe='') + '/' + urllib.parse.quote(version, safe='') + '/json'
                    try:
                        if key not in cache:
                            with urllib.request.urlopen(url, timeout=20) as response:
                                public = response.read(4*1024*1024)
                            cache[key] = json.dumps(json.loads(public)['info'], ensure_ascii=False).encode()
                        public = cache[key]
                        verified = [value in public for _, _, value in matches]
                        report['public_metadata'].append({'archive_blob':oid, 'member':member.name,
                            'package':name, 'version':version, 'source':url,
                            'matching_fields':sorted({path for _, path, _ in matches}),
                            'indicator_count':len(matches), 'publicly_verified_count':sum(verified),
                            'all_indicators_present_in_public_metadata':all(verified),
                            'public_metadata_sha256':hashlib.sha256(public).hexdigest()})
                    except Exception as error:
                        report['errors'].append({'area':'public_metadata','package':name,'version':version,'type':type(error).__name__})
    def write(method, endpoint, payload=None):
        request = urllib.request.Request('https://api.github.com/repos/' + REPOSITORY + endpoint,
            method=method, data=json.dumps(payload).encode() if payload is not None else b'',
            headers={'Authorization':'Bearer '+token,'Content-Type':'application/json','Accept':'application/vnd.github+json'})
        with urllib.request.urlopen(request, timeout=30) as response:
            raw=response.read()
            return json.loads(raw) if raw else None
    for item in api.pages('/issues?state=all'):
        if 'pull_request' not in item:
            continue
        body=item.get('body') or ''
        cleaned, changed = clean_footer(body)
        if not changed:
            continue
        number=item['number']
        write('PATCH', '/pulls/' + str(number), {'body':cleaned})
        observed=api.get('/pulls/'+str(number))['body']
        report['footer_removals'].append({'pull_request':number,
            'prior_body_sha256':hashlib.sha256(body.encode()).hexdigest(),
            'new_body_sha256':hashlib.sha256(observed.encode()).hexdigest(),
            'exact_nonfooter_content_preserved':observed==cleaned,
            'signed_footer_absent_on_readback':not FOOTER.search(observed)})
    for run_id in QUEUED_RUNS:
        run=api.get('/actions/runs/'+str(run_id))
        jobs=api.pages('/actions/runs/'+str(run_id)+'/jobs','jobs')
        eligible = run['status']=='queued' and all(not j.get('steps') and j.get('runner_id',0)==0 for j in jobs)
        record={'run_id':run_id,'observed_status':run['status'],'zero_step_unassigned_jobs':all(not j.get('steps') and j.get('runner_id',0)==0 for j in jobs)}
        if eligible:
            write('POST','/actions/runs/'+str(run_id)+'/cancel')
            record['cancel_requested']=True
        else:
            record['cancel_requested']=False
        report['queued_run_actions'].append(record)
    report['remaining_current_pr_signed_footers'] = [x['number'] for x in api.pages('/issues?state=all')
        if 'pull_request' in x and FOOTER.search(x.get('body') or '') and 'signature=' in (x.get('body') or '')]
    report['finished_utc']=datetime.now(timezone.utc).isoformat()
    report['review_status']='review_required' if report['errors'] or any(not x['all_indicators_present_in_public_metadata'] for x in report['public_metadata']) or report['remaining_current_pr_signed_footers'] else 'reviewed'
    output=Path('build/publication-review'); output.mkdir(parents=True,exist_ok=False)
    (output/'review.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'status':report['review_status'],'metadata_records':len(report['public_metadata']),
        'footers_removed':len(report['footer_removals']),'queued_run_actions':report['queued_run_actions'],
        'error_count':len(report['errors'])},indent=2))


if __name__=='__main__':main()
