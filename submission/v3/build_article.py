"""Render the v3 article to standalone HTML. Requires Pandoc.

Reuses the v2 style sheet and exact calculator without modifying them.
"""
from pathlib import Path
import argparse
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parent
REPO = next(p for p in ROOT.parents if (p/'submission'/'v2').is_dir())
V2 = REPO/'submission'/'v2'/'strengthening'
MARKER = '## A fresh-seed study with competing transforms'

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output', type=Path, default=ROOT/'build'/'hadamard-conjecture-v3.html')
output = parser.parse_args().output
text = (ROOT/'hadamard-conjecture.md').read_text()
if text.count(MARKER) != 1:
    raise ValueError('Expected exactly one calculator insertion point')
lab = (V2/'lab.html').read_text() + '\n<script id="family-calculator">\n' + (V2/'lab.js').read_text() + '\n</script>\n\n'
text = text.replace(MARKER, lab + MARKER)
output.parent.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix='hadamard-v3-render-') as tmp:
    source = Path(tmp)/'article.md'
    source.write_text(text)
    subprocess.run(['pandoc', str(source), '--standalone', '--mathml', '--embed-resources',
                    '--toc', '--toc-depth=2', '--css', str(V2/'style.css'),
                    '--metadata', 'pagetitle=What the Hadamard conjecture promises',
                    '-o', str(output)], check=True, timeout=30)
print(output)
