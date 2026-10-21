"""Render the separately versioned all-Hadamard addendum. Optional build tools."""
from pathlib import Path
import subprocess
from playwright.sync_api import sync_playwright

root=Path(__file__).resolve().parent.parent
source=root/'strengthening/all-hadamard-addendum.md'
html=root/'all-hadamard-addendum.html'
subprocess.run(['pandoc',str(source),'--standalone','--mathml','--embed-resources',
                '--css',str(root/'strengthening/style.css'),'-o',str(html)],check=True,timeout=30)
with sync_playwright() as p:
    browser=p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
    page=browser.new_page()
    page.set_content(html.read_text(),wait_until='load')
    page.pdf(path=str(root/'all-hadamard-addendum.pdf'),format='A4',print_background=True,
             prefer_css_page_size=True,display_header_footer=True,header_template='<div></div>',
             footer_template='<div style="width:100%;font:8px sans-serif;text-align:center">Hadamard exposition · All-matrices addendum · <span class="pageNumber"></span> / <span class="totalPages"></span></div>')
    browser.close()
