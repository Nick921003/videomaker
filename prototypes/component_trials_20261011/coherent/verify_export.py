"""Inspect real browser frames, geometry, UI, and optionally export the demo."""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import subprocess
import time
from playwright.sync_api import sync_playwright
from presentation_checks import check_presentation

HERE = Path(__file__).resolve().parent
OUT = HERE / 'out'
BASE = 'http://127.0.0.1:8940/prototypes/component_trials_20261011/coherent/'


def stamp(t):
	ms = round(t * 1000)
	h, ms = divmod(ms, 3600000)
	m, ms = divmod(ms, 60000)
	s, ms = divmod(ms, 1000)
	return f'{h:02}:{m:02}:{s:02},{ms:03}'


def check_frame(state, regions, cmap):
	check_presentation(state)
	for b in state['texts']:
		assert b['region'] in regions, b
		x, y, w, h = regions[b['region']]
		assert b['x'] >= x-2 and b['y'] >= y-2 and b['x']+b['w'] <= x+w+2 and b['y']+b['h'] <= y+h+2, (state['time'], b)
		assert all(ord(c) in cmap for c in b['text'] if not c.isspace()), b['text']
		if b['region'] == 'captions': assert b['font_px'] >= 42
	# The two possible outgoing condition branches must never animate together.
	if state['activeEdge'] == 'no':
		assert state['execution']['i'] == 6 and state['execution']['sum'] == 15
	if state['execution']['step'] == 'exit': assert state['activeEdge'] is None
	if state['scene']=='trace' and state['execution']['step'] in ('body','update','return'):
		assert any(b['text'].startswith(f'第 {state["execution"]["bodies"]} 輪') for b in state['texts']), state


def difference(page, a, b):
	if a == b: return {'pixels':0, 'max_delta':0}
	return page.evaluate('''async ([a,b])=>{
		const decode=async s=>{const i=new Image();i.src='data:image/png;base64,'+s;await i.decode();const c=document.createElement('canvas');c.width=i.width;c.height=i.height;const g=c.getContext('2d');g.drawImage(i,0,0);return g.getImageData(0,0,c.width,c.height).data;};
		const x=await decode(a),y=await decode(b);let pixels=0,max=0;for(let k=0;k<x.length;k+=4){let d=0;for(let j=0;j<4;j++)d=Math.max(d,Math.abs(x[k+j]-y[k+j]));if(d)pixels++;max=Math.max(max,d);}return{pixels,max_delta:max};
	}''', [base64.b64encode(a).decode(), base64.b64encode(b).decode()])


def load(browser, url, errors):
	page = browser.new_page(viewport={'width':1920,'height':1080})
	page.on('pageerror',lambda error:errors.append(str(error)))
	page.goto(url)
	page.wait_for_function('window.__ready || window.__failed')
	assert not page.evaluate('window.__failed || null')
	return page


def verify_ui(browser):
	report=[]
	for width in [375,768,1440]:
		page=browser.new_page(viewport={'width':width,'height':1000})
		errors=[]
		page.on('pageerror',lambda e:errors.append(str(e)))
		pending_fonts=[]
		if width==375: page.route('**/teaching.woff',lambda r:pending_fonts.append(r))
		page.goto(BASE+'index.html',wait_until='domcontentloaded')
		if width==375:
			page.wait_for_timeout(200)
			assert page.locator('#coherent').is_disabled() and page.locator('#seek').is_disabled()
			page.locator('#switching').evaluate('(b)=>b.click()')
			for route in pending_fonts: route.fulfill(body=(HERE/'teaching.woff').read_bytes(),content_type='font/woff')
			page.unroute('**/teaching.woff')
		page.wait_for_function('!document.getElementById("play").disabled')
		assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
		page.locator('#chapters button').nth(2).click()
		assert page.locator('#clock').inner_text() == '16.0 / 48 秒'
		page.locator('#switching').click()
		assert page.frame_locator('#preview').locator('#frame').evaluate('()=>window.__time') == 16
		assert page.frame_locator('#preview').locator('#frame').evaluate('()=>getComputedStyle(document.getElementById("frame")).getPropertyValue("--bg").trim()') == '#19323B'
		page.locator('#coherent').click()
		page.locator('#play').click()
		page.wait_for_timeout(500)
		page.locator('#play').click()
		paused=page.frame_locator('#preview').locator('#frame').evaluate('()=>window.__time')
		page.wait_for_timeout(150)
		assert page.frame_locator('#preview').locator('#frame').evaluate('()=>window.__time') == paused
		page.locator('#seek').focus();page.locator('#seek').press('End')
		assert page.frame_locator('#preview').locator('#captions').inner_text().startswith('一加到五')
		page.locator('#restart').click();page.wait_for_timeout(150);page.locator('#play').click()
		assert page.frame_locator('#preview').locator('#frame').evaluate('()=>window.__time') < 1
		if (OUT/'coherent.mp4').exists():
			pending_video=[]
			if width==375: page.route('**/out/coherent.mp4',lambda r:r.continue_() if r.request.method=='HEAD' else pending_video.append(r))
			page.locator('#mp4').click()
			if width==375:
				page.wait_for_timeout(100)
				page.locator('#coherent').click()
				for route in pending_video: route.fulfill(body=(OUT/'coherent.mp4').read_bytes(),content_type='video/mp4')
				page.unroute('**/out/coherent.mp4')
				page.wait_for_function('document.getElementById("video").readyState >= 2')
				assert page.locator('#preview').is_visible() and not page.locator('#video').is_visible()
				page.locator('#mp4').click()
			page.wait_for_function('document.getElementById("video").readyState >= 2 && document.getElementById("video").style.display === "block"')
			page.locator('#seek').evaluate('(e)=>{e.value=33;e.dispatchEvent(new Event("input",{bubbles:true}));}')
			page.wait_for_function('Math.abs(document.getElementById("video").currentTime - 33) < .05')
			page.locator('#play').click();page.wait_for_timeout(300);page.locator('#play').click()
			assert page.locator('#video').evaluate('(v)=>v.currentTime') > 33
			page.locator('#coherent').click()
		page.screenshot(path=str(OUT/f'review-{width}.png'))
		assert not errors, errors
		report.append({'width':width,'play_pause_seek_replay':True,'mode_preserves_time':True,'mp4':(OUT/'coherent.mp4').exists(),'page_errors':errors})
		page.close()
	return report


def main():
	parser=argparse.ArgumentParser();parser.add_argument('--export',action='store_true');args=parser.parse_args()
	OUT.mkdir(exist_ok=True)
	lesson=json.loads((HERE/'lesson.json').read_text())
	font=json.loads((HERE/'font.json').read_text());cmap=set(font['cmap'])
	assert hashlib.sha256((HERE/'teaching.woff').read_bytes()).hexdigest()==font['subset_sha256']
	manifest=json.loads((HERE.parent/'vendor/sources.json').read_text())
	for source in manifest: assert hashlib.sha256((HERE.parent/source['local']).read_bytes()).hexdigest()==source['sha256']
	end=0
	for a,b,text in lesson['subtitles']:
		assert a==end and a<b<=48 and len(text)/(b-a)<=10
		end=b
	assert end==48
	started=time.time();errors=[];seek_report=[]
	with sync_playwright() as p:
		browser=p.chromium.launch()
		page=load(browser,BASE+'stage.html?export',errors)
		regions=page.evaluate('window.__regions');frame=page.locator('#frame')
		times=[0,4,8,8.7,12,16,17.5,17.65,18.3,23,28,29,29.3,29.65,30.5,31,34,38,39,39.7,40.2,44,44.7,47.95]
		baseline={};states={}
		for t in times:
			cold=load(browser,BASE+'stage.html?export',errors)
			states[t]=cold.evaluate('t=>renderFrame(t)',t);check_frame(states[t],regions,cmap)
			baseline[t]=cold.locator('#frame').screenshot();cold.close()
		for mode in ['coherent','switching','coherent']:
			page.evaluate('m=>setMode(m)',mode)
			for t in [*times,*reversed(times)]:
				state=page.evaluate('t=>renderFrame(t)',t);check_frame(state,regions,cmap)
				assert state['execution']==states[t]['execution'] and state['subtitle']==states[t]['subtitle']
				if mode=='coherent':
					assert state==states[t], (t,'state mismatch')
					actual=frame.screenshot();diff=difference(page,actual,baseline[t])
					if diff['pixels']>250 or diff['max_delta']>24:
						(OUT/'seek-actual.png').write_bytes(actual);(OUT/'seek-expected.png').write_bytes(baseline[t])
					assert diff['pixels']<=250 and diff['max_delta']<=24,(t,diff)
					seek_report.append({'time':t,**diff})
		for t in [4,12,23,29.3,34,40.2,47.95]:
			page.evaluate('t=>renderFrame(t)',t);frame.screenshot(path=str(OUT/f'frame-{t}.png'))
		page.evaluate('()=>setMode("switching")');page.evaluate('()=>renderFrame(23)');frame.screenshot(path=str(OUT/'switching-23.png'));page.evaluate('()=>setMode("coherent")')
		video=OUT/'coherent.mp4';probe=None;frames=48*24
		if args.export:
			encoder=subprocess.Popen(['ffmpeg','-hide_banner','-loglevel','error','-y','-f','image2pipe','-vcodec','png','-r','24','-i','pipe:0','-an','-c:v','libx264','-preset','fast','-crf','18','-pix_fmt','yuv420p','-movflags','+faststart',str(video)],stdin=subprocess.PIPE)
			try:
				for k in range(frames):
					state=page.evaluate('t=>renderFrame(t)',k/24);check_frame(state,regions,cmap)
					encoder.stdin.write(frame.screenshot())
					if (k+1)%192==0: print(f'{k+1}/{frames} frames',flush=True)
			finally: encoder.stdin.close()
			assert encoder.wait()==0
			probe=json.loads(subprocess.run(['ffprobe','-v','error','-count_frames','-show_streams','-show_format','-of','json',str(video)],capture_output=True,text=True,check=True).stdout)
			v=next(s for s in probe['streams'] if s['codec_type']=='video')
			assert [v['width'],v['height']]==[1920,1080] and v['nb_read_frames']==str(frames) and v['r_frame_rate']=='24/1'
			assert len(probe['streams'])==1 and abs(float(probe['format']['duration'])-48)<.01
			subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-xerror','-i',str(video),'-f','null','-'],check=True)
			for t in [4,23,34,40.2,47.95]: subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-ss',str(t),'-i',str(video),'-frames:v','1',str(OUT/f'mp4-{t}.png')],check=True)
			(OUT/'coherent.srt').write_text('\n\n'.join(f'{i}\n{stamp(a)} --> {stamp(b)}\n{text}' for i,(a,b,text) in enumerate(lesson['subtitles'],1))+'\n')
		ui=verify_ui(browser)
		assert not errors,errors
		browser.close()
		result={'revision':2,'exported':args.export,'duration':48,'frames':frames if args.export else None,'cold_forward_reverse_seek':True,'pixel_differences':seek_report,'all_exported_frame_text_bounds_checked':args.export,'all_exported_frame_text_collisions_checked':args.export,'flow_reveal_checked':True,'source_hashes':True,'glyph_coverage':True,'ui':ui,'errors':errors,'seconds':round(time.time()-started,2)}
		(OUT/'report.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
		print(json.dumps({k:v for k,v in result.items() if k!='pixel_differences'},ensure_ascii=False),flush=True)


if __name__=='__main__': main()
