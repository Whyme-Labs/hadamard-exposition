#!/usr/bin/env python3
"""Freeze the committed v3 draft into submission/v3. Never overwrites.

Requires a clean Git tree, Pandoc, Node.js, Playwright and Chromium.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import platform
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
V2 = REPO/'submission'/'v2'
OUT = REPO/'submission'/'v3'
COPIED = ['hadamard-conjecture.md', 'known_orders.py', 'test_v3.py', 'build_article.py', 'build_pdf.py', 'REVIEW.md']
EDITION = ['README.md', 'SUBMISSION.md', 'CITATION.cff', 'LICENSE.md', 'PUBLICATION.json', 'requirements-v3.txt']
FROM_V2 = ['LICENSE-CC-BY-4.0.md', 'LICENSE-MIT.txt']
HTML, PDF = 'hadamard-conjecture-v3.html', 'hadamard-conjecture-v3.pdf'


def run(argv, **kw) -> str:
    return subprocess.run(argv, check=True, capture_output=True, text=True, **kw).stdout


def git(*args) -> str:
    return run(['git', '-C', str(REPO), *args]).strip()


def main() -> None:
    if git('status', '--porcelain'):
        sys.exit('Commit the draft first: the edition must come from a clean, committed tree')
    if OUT.exists():
        sys.exit(f'Refusing to overwrite {OUT}')
    commit = git('rev-parse', 'HEAD')
    sources = {name: f'exposition-v3/{name}' for name in COPIED}
    sources.update({name: f'exposition-v3/edition/{name}' for name in EDITION})
    sources.update({name: f'submission/v2/{name}' for name in FROM_V2})
    blobs = {name: git('rev-parse', f'{commit}:{path}') for name, path in sources.items()}

    OUT.mkdir(parents=True)
    (OUT/'verification').mkdir()
    for name, path in sources.items():
        shutil.copyfile(REPO/path, OUT/name)
    run([sys.executable, str(OUT/'build_article.py'), '--output', str(OUT/HTML)])
    run([sys.executable, str(OUT/'build_pdf.py'), '--html', str(OUT/HTML), '--output', str(OUT/PDF)])

    report = run([sys.executable, str(OUT/'known_orders.py'), '--limit', '1000'])
    (OUT/'verification'/'known-orders-1000.json').write_text(report)
    tests = subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', str(OUT), '-p', 'test_*.py', '-v'],
                           capture_output=True, text=True, cwd=REPO)
    (OUT/'verification'/'unit-tests.txt').write_text(tests.stderr)
    if tests.returncode:
        sys.exit('Unit tests failed; see verification/unit-tests.txt')
    calculator = run(['node', str(V2/'strengthening'/'verify_lab.cjs'), str(OUT/HTML)])
    (OUT/'verification'/'calculator.json').write_text(calculator)

    for cache in list(OUT.rglob('__pycache__')):
        shutil.rmtree(cache)
    versions = {
        'python': platform.python_version(),
        'numpy': run([sys.executable, '-c', 'import numpy; print(numpy.__version__)']).strip(),
        'pandoc': run(['pandoc', '--version']).splitlines()[0],
        'node': run(['node', '--version']).strip(),
    }
    manifest = {
        'schema': 'hadamard-v3-source-edition.v1',
        'source_commit': commit,
        'copied_git_blobs': blobs,
        'copied_from': sources,
        'generated': {HTML: 'build_article.py', PDF: 'build_pdf.py',
                      'verification/known-orders-1000.json': 'known_orders.py --limit 1000',
                      'verification/unit-tests.txt': 'unittest discover',
                      'verification/calculator.json': 'submission/v2/strengthening/verify_lab.cjs'},
        'build_environment': versions,
        'evidence_dependency': 'Part III cites submission/v2, unchanged and covered by its own SHA256SUMS.',
        'scope': 'Frozen v3 source edition with rendered HTML and PDF. Not a public publication record.',
    }
    (OUT/'SOURCE-MANIFEST.json').write_text(json.dumps(manifest, indent=2) + '\n')
    lines = []
    for path in sorted(p for p in OUT.rglob('*') if p.is_file()):
        rel = path.relative_to(OUT).as_posix()
        lines.append(f'{hashlib.sha256(path.read_bytes()).hexdigest()}  {rel}')
    (OUT/'SHA256SUMS').write_text('\n'.join(lines) + '\n')
    print(json.dumps({'output': str(OUT), 'source_commit': commit, 'files': len(lines) + 1}, indent=2))


if __name__ == '__main__':
    main()
