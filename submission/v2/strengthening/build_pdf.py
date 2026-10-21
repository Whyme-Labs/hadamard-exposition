"""Print the generated HTML using local Chromium. Optional publication dependency."""
from pathlib import Path
from playwright.sync_api import sync_playwright

root=Path(__file__).resolve().parent.parent
with sync_playwright() as p:
    browser=p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
    page=browser.new_page()
    page.set_content((root/'exposition-v2.html').read_text(),wait_until='load')
    page.pdf(path=str(root/'exposition-v2.pdf'),format='A4',print_background=True,
             prefer_css_page_size=True,display_header_footer=True,header_template='<div></div>',
             footer_template='<div style="width:100%;font:8px sans-serif;color:#555;text-align:center">Hadamard exposition · Version 2 · <span class="pageNumber"></span> / <span class="totalPages"></span></div>')
    browser.close()
