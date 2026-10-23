"""Print the rendered v3 HTML to PDF with local Chromium. Requires Playwright."""
from pathlib import Path
import argparse
import shutil
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent
CANDIDATES = ('/usr/bin/chromium', '/opt/pw-browsers/chromium')

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--html', type=Path, default=ROOT/'build'/'hadamard-conjecture-v3.html')
parser.add_argument('--output', type=Path, default=ROOT/'build'/'hadamard-conjecture-v3.pdf')
parser.add_argument('--chromium', default=next((c for c in CANDIDATES if Path(c).exists()), shutil.which('chromium')))
args = parser.parse_args()
with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=args.chromium, headless=True, args=['--no-sandbox'])
    page = browser.new_page()
    page.set_content(args.html.read_text(), wait_until='load')
    page.pdf(path=str(args.output), format='A4', print_background=True, prefer_css_page_size=True,
             display_header_footer=True, header_template='<div></div>',
             footer_template='<div style="width:100%;font:8px sans-serif;color:#555;text-align:center">'
                             'Hadamard exposition · Version 3 · <span class="pageNumber"></span> / '
                             '<span class="totalPages"></span></div>')
    browser.close()
print(args.output)
