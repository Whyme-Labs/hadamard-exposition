"""Render this revision without modifying the frozen version-one exposition."""
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parent
text = (ROOT/'conjecture-companion.md').read_text()
marker = '## A fresh-seed test with competing transforms'
if text.count(marker) != 1:
    raise ValueError('Expected exactly one calculator insertion point')
lab = (ROOT/'lab.html').read_text() + '\n<script id="family-calculator">\n' + (ROOT/'lab.js').read_text() + '\n</script>\n\n'
text = text.replace(marker, lab + marker)
with tempfile.TemporaryDirectory(prefix='hadamard-v2-render-') as tmp:
    source = Path(tmp)/'article.md'; source.write_text(text)
    subprocess.run(['pandoc',str(source),'--standalone','--mathml','--embed-resources',
                    '--toc','--toc-depth=2','--css',str(ROOT/'style.css'),
                    '--metadata','pagetitle=What the Hadamard conjecture promises',
                    '-o',str(ROOT.parent/'exposition-v2.html')],check=True,timeout=30)
