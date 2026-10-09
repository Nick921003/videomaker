import io, json
from pathlib import Path
from playwright.sync_api import sync_playwright

base=Path('/tmp/videomaker-step2-browser-inputs')
files=['lesson.csv','lesson.docx','lesson.xlsx']
report=[]
with sync_playwright() as p:
 browser=p.chromium.launch(headless=True)
 for width,height in [(1350,700),(375,900)]:
  page=browser.new_page(viewport={'width':width,'height':height})
  errors=[]; rejected=[]
  page.on('pageerror', lambda error: errors.append(str(error)))
  def route(req):
   if req.request.method != 'GET' and '/api/v1/uploads' not in req.request.url:
    rejected.append(req.request.url); req.abort(); return
   if req.request.method != 'GET' and '/normalize' in req.request.url:
    rejected.append(req.request.url); req.abort(); return
   req.continue_()
  page.route('**/*',route)
  for name in [*files,'lesson.png']:
   page.goto('http://127.0.0.1:8765/web/index.html#/make/1')
   page.locator('input[type=file]').set_input_files(str(base/name))
   page.get_by_role('button',name='確認整理',exact=False).wait_for()
   assert page.locator('.upload-preview').is_visible()
   assert name in page.locator('.upload-preview').inner_text()
   assert not rejected,rejected
   assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
   report.append({'viewport':[width,height],'file':name,'preview':True,'paid_requests':len(rejected),'errors':list(errors)})
  page.screenshot(path=f'docs/experiments/workbench-step2-evidence-20261008/source-{width}.png',full_page=True)
  assert not errors,errors
  page.close()
 browser.close()
Path('docs/experiments/workbench-step2-evidence-20261008/browser-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
print(json.dumps(report,ensure_ascii=False))
