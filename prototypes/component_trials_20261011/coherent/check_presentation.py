"""Run the reported layout/timing regressions in the real browser."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright
from presentation_checks import check_presentation

HERE=Path(__file__).resolve().parent
URL='http://127.0.0.1:8940/prototypes/component_trials_20261011/coherent/stage.html?export'
errors=[]
with sync_playwright() as p:
	browser=p.chromium.launch()
	page=browser.new_page(viewport={'width':1920,'height':1080})
	page.on('pageerror',lambda e:errors.append(str(e)))
	page.goto(URL);page.wait_for_function('window.__ready || window.__failed')
	assert not page.evaluate('window.__failed || null')
	failures=[]
	for t in [8.4,17,17.65,18.3,18.85,29,29.65,44.4,44.7]:
		state=page.evaluate('t=>renderFrame(t)',t)
		try: check_presentation(state)
		except AssertionError as e: failures.append(str(e))
	assert not failures, '\n'.join(failures)
	for k in range(1152):check_presentation(page.evaluate('t=>renderFrame(t)',k/24))
	page.evaluate('()=>renderFrame(8.4)');page.locator('#frame').screenshot(path=str(HERE/'out/fixed-8.4.png'))
	page.evaluate('()=>renderFrame(29.3)');page.locator('#frame').screenshot(path=str(HERE/'out/fixed-29.3.png'))
	assert not errors,errors
	browser.close()
print('PASS: reported frames + all 1152 frames, text collisions and causal flow reveal')
