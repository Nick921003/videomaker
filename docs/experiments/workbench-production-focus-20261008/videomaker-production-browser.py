from pathlib import Path
import json
from playwright.sync_api import sync_playwright, expect
base='http://127.0.0.1:8765/web/index.html'
out=Path('/tmp/videomaker-production-focus');out.mkdir(exist_ok=True)
results=[];errors=[]
with sync_playwright() as p:
 b=p.chromium.launch()
 for width,height in [(1440,900),(1350,700),(1024,768),(768,900),(375,900),(375,560)]:
  page=b.new_page(viewport={'width':width,'height':height})
  page.on('pageerror',lambda e:errors.append(str(e)))
  page.on('console',lambda m:errors.append(m.text) if m.type=='error' else None)
  # API.MOCK makes all generation local simulation; guard any real write too.
  page.route('**/api/v1/**',lambda route: route.abort() if route.request.method!='GET' else route.continue_())
  page.goto(base+'?mock=1#/make/3?unit=ff9e559208c9',wait_until='networkidle')
  expect(page.get_by_role('heading',name='這次要生成哪些？',exact=True)).to_be_visible()
  if width>760:
   left=page.locator('.generate-left').bounding_box();right=page.locator('.generate-live').bounding_box()
   assert left['x']+left['width']<=right['x']
  assert page.locator('.generate-live .generate-queue').count()==1
  assert page.locator('video').count()==0
  page.screenshot(path=str(out/f'generate-open-{width}-{height}.png'))
  for cb in page.locator('.generate-choice input:not([disabled])').all(): cb.uncheck()
  page.locator('.generate-choice input[value="q5"]').check()
  page.get_by_role('button',name='收合選擇',exact=True).click()
  expect(page.locator('.generate-actions').get_by_role('button',name='開始生成',exact=True)).to_be_visible()
  page.get_by_role('button',name='開始生成',exact=True).click()
  expect(page.locator('.make-generate')).to_have_attribute('data-selection','collapsed')
  expect(page.get_by_role('button',name='展開選擇',exact=True)).to_be_visible()
  expect(page.locator('.generate-diagram')).to_be_visible()
  page.locator('.generate-live').scroll_into_view_if_needed()
  page.screenshot(path=str(out/f'generate-collapsed-{width}-{height}.png'))
  page.get_by_role('button',name='展開選擇',exact=True).click()
  expect(page.locator('.generate-left')).to_be_visible()
  assert not page.evaluate('document.documentElement.scrollWidth>innerWidth+1')
  # New page reload resets mock state so q5 is known to be unmade.
  page.goto(base+'?mock=1#/make/4?unit=ff9e559208c9',wait_until='networkidle')
  expect(page.locator('video')).to_be_visible()
  assert page.locator('[data-product-id]').count()==5
  page.locator('[data-product-id="q3"]').click()
  expect(page.locator('[data-product-id="q3"]')).to_have_attribute('aria-pressed','true')
  assert page.get_by_role('button',name='下一點',exact=True).count()==0
  page.locator('.product-viewer').scroll_into_view_if_needed()
  page.screenshot(path=str(out/f'products-{width}-{height}.png'))
  page.locator('[data-product-id="q5"]').click()
  expect(page.get_by_role('button',name='去選要生成的 →',exact=True)).to_be_visible()
  assert page.locator('video').count()==0
  page.get_by_role('tab',name='簡報',exact=True).click()
  jump=page.get_by_role('combobox',name='選擇投影片')
  expect(jump).to_be_visible();jump.select_option('6')
  expect(page.locator('.deck-counter')).to_have_text('7 / 7')
  page.locator('.deck-viewport').focus();page.keyboard.press('ArrowLeft')
  expect(page.locator('.deck-counter')).to_have_text('6 / 7')
  with page.expect_download() as info: page.get_by_role('link',name='下載 PPTX',exact=True).click()
  assert info.value.failure() is None
  assert not page.evaluate('document.documentElement.scrollWidth>innerWidth+1')
  results.append({'width':width,'height':height,'generate_collapse':True,'direct_product_and_slide':True,'paid_calls':0})
  page.close()
 b.close()
assert not errors,errors
(out/'browser-report.json').write_text(json.dumps({'checks':results,'errors':errors,'mode':'mock fixture generation and media; no paid API'},ensure_ascii=False,indent=2))
print(json.dumps(results))
