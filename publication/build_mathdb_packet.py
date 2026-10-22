#!/usr/bin/env python3
"""Build the MathDB upload files for v3: the frozen PDF and a reproducible supporting ZIP.

The ZIP holds submission/v3 and submission/v2 at their repository paths, so the
article's commands run from the ZIP root. Entries are sorted with fixed times and
modes, so the same commit always gives the same ZIP bytes.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import zipfile

REPO = Path(__file__).resolve().parent.parent
EDITIONS = ('submission/v3', 'submission/v2')
PDF = 'submission/v3/hadamard-conjecture-v3.pdf'
STAMP = (2026, 10, 22, 0, 0, 0)
ZIP_README = """# Hadamard exposition v3: supporting files

This archive accompanies the PDF "What the Hadamard conjecture promises", version 3.
Run the commands in the article's "Reproduce and inspect" section from this directory.

- submission/v3: the frozen v3 edition (manuscript, PDF, HTML, checks, checksums).
- submission/v2: the unchanged v2 evidence used by Part III (study data, audit, checkers).

Each edition has its own SHA256SUMS. Text and data: CC BY 4.0. Code: MIT.
"""


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=REPO/'build'/'mathdb-v3')
    out = parser.parse_args().output
    if out.exists():
        raise SystemExit(f'Refusing to overwrite {out}')
    tracked = subprocess.run(['git', '-C', str(REPO), 'ls-files', '-z', *EDITIONS],
                             check=True, capture_output=True).stdout.decode().split('\0')
    names = sorted(n for n in tracked if n)
    for edition in EDITIONS:
        subprocess.run(['sha256sum', '-c', '--quiet', 'SHA256SUMS'], cwd=REPO/edition, check=True)
    out.mkdir(parents=True)
    archive = out/'hadamard-exposition-v3-supporting-files.zip'
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        entries = [('README.md', ZIP_README.encode())] + [(n, (REPO/n).read_bytes()) for n in names]
        for name, data in entries:
            info = zipfile.ZipInfo(name, STAMP)
            info.external_attr = 0o644 << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, data)
    shutil.copyfile(REPO/PDF, out/'hadamard-conjecture-v3.pdf')
    commit = subprocess.run(['git', '-C', str(REPO), 'rev-parse', 'HEAD'], check=True,
                            capture_output=True, text=True).stdout.strip()
    receipt = {'source_commit': commit, 'zip_entries': len(entries),
               'files': {p.name: {'bytes': p.stat().st_size, 'sha256': sha(p.read_bytes())}
                         for p in sorted(out.iterdir())}}
    print(json.dumps(receipt, indent=2))


if __name__ == '__main__':
    main()
