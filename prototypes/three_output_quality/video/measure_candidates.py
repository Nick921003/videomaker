"""量測外部候選所有323幀的可見文字框，尚不量測裝飾路徑。"""
import json
import pathlib
from playwright.sync_api import sync_playwright

HERE = pathlib.Path(__file__).resolve().parent


def main():
	summaries=[]
	with sync_playwright() as p:
		browser=p.chromium.launch()
		page=browser.new_page(viewport={'width':1920,'height':1080})
		for grammar in ['y3_whiteboard','y5_kinetic_type']:
			page.goto((HERE/'candidates.html').as_uri()+'?export&grammar='+grammar)
			page.wait_for_function('window.__ready || window.__failed')
			assert not page.evaluate('window.__failed || null')
			issues=[]
			core_min=sub_min=999
			for k in range(323):
				info=page.evaluate('t=>renderFrame(t)',k/24)
				for text in info['texts']:
					if text['alpha']<.99:
						continue
					if text['x'] < -1 or text['y'] < -1 or text['x']+text['w']>1921 or text['y']+text['h']>1081:
						issues.append({'time':k/24,**text})
					size=float(text['font'].split('px')[0])
					if size==42:
						sub_min=min(sub_min,size)
					elif size>24:
						core_min=min(core_min,text['font_px'])
			report={'grammar':grammar,'samples':323,'visible_text_canvas_overflow':issues,'min_core_font_px':core_min,'subtitle_font_px':sub_min,'instrumentation':'four-corner transformed text AABB; visible text only, illustrative paths are not instrumented'}
			(HERE/'out'/f'{grammar}.geometry.json').write_text(json.dumps(report,ensure_ascii=False,indent='\t')+'\n')
			assert not issues and core_min>=28 and 38<=sub_min<=46, report
			summaries.append({k:v for k,v in report.items() if k!='visible_text_canvas_overflow'}|{'overflow_count':len(issues)})
		browser.close()
	print(json.dumps(summaries,ensure_ascii=False))


if __name__=='__main__':
	main()
