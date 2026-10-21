"""Inspect the generated standalone article using a local browser."""
from pathlib import Path
import json
from playwright.sync_api import sync_playwright

root=Path(__file__).resolve().parent.parent
shots=root/'review-screenshots'; shots.mkdir(exist_ok=True)
report={'scope':'Local Chromium rendering and interactive state checks, not learner or committee review.','viewports':[]}
with sync_playwright() as p:
    browser=p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
    report['browser_version']=browser.version
    for name,width,height in [('desktop',1440,1000),('mobile',390,844)]:
        page=browser.new_page(viewport={'width':width,'height':height})
        errors=[]; page.on('pageerror',lambda e:errors.append(str(e)))
        page.set_content((root/'exposition-v2.html').read_text(),wait_until='load')
        page.screenshot(path=str(shots/f'{name}-opening.png'))
        page.locator('.lab').scroll_into_view_if_needed()
        page.screenshot(path=str(shots/f'{name}-calculator.png'))
        assert page.locator('#family-fraction').inner_text()=='11/3332'
        page.select_option('#family-n','1024'); page.select_option('#family-signs','7')
        assert page.locator('#family-fraction').inner_text()=='11/3332'
        page.select_option('#family-bits','5')
        assert page.locator('#family-fraction').inner_text()=='8/17025'
        overflow=page.evaluate('document.documentElement.scrollWidth > window.innerWidth')
        outside=page.evaluate("""() => [...document.querySelectorAll('body *')].filter(e => {
          const r=e.getBoundingClientRect(); return r.width>0 && (r.left < -1 || r.right>innerWidth+1) &&
          !e.closest('math,pre,table,nav'); }).slice(0,10).map(e=>({tag:e.tagName,text:e.textContent.slice(0,80)}))""")
        report['viewports'].append({'name':name,'width':width,'height':height,'horizontal_document_overflow':overflow,'page_errors':errors,'outside_viewport':outside,'mathml_equations':page.locator('math').count(),'interactive_change_checks':True})
        if errors or overflow or outside: raise ValueError(report['viewports'][-1])
        page.close()
    browser.close()
report['status']='passed'
(root/'browser-verification.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
