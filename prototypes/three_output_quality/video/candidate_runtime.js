'use strict';
(async () => {
	const cv = document.getElementById('c'), c = cv.getContext('2d');
	const params = new URLSearchParams(location.search), grammar = params.get('grammar') || 'y3_whiteboard';
	if (params.has('export')) document.body.classList.add('export');
	await document.fonts.ready;
	await Promise.all(['PuHui-Black', 'PuHui-Heavy', 'PuHui-Bold', 'LXGWWenKai-500'].map(f => document.fonts.load(`40px "${f}"`, '繁體起點最後值')));
	U.setStage(1920, 1080);
	const FPS = 24, duration = 13.42;
	const cues = grammar === 'y3_whiteboard' ? [
		{kind:'title',at:.55,text:'迴圈邊界'},
		{kind:'point',at:7.58,text:'起點是幾？'},
		{kind:'point',at:7.58,text:'最後值要不要算？'},
	] : [
		{kind:'title',at:.55,text:'＜ 或 ≤？',sub:'常常多一或少一？'},
		{kind:'point',at:7.58,text:'起點 × 最後值',sub:'起點是幾？最後一個值要算嗎？'},
	];
	const ctx = {W:1920,H:1080,FPS,u:1,dur:duration,portrait:false,alpha:false,data:{palette:[['#F4EFE6','#111111'],['#14213D','#FFD23F']]},theme:{},safe:{top:80,bottom:210,left:90,right:90},IMG:{},cues,of:(...k)=>cues.filter(q=>k.includes(q.kind)),lt:(t,at)=>CLIP.lt(t,at,FPS)};
	CLIPS[grammar].init(ctx);
	const texts = [];
	const original = c.fillText.bind(c);
	c.fillText = (text,x,y,...rest) => {
		const m = c.measureText(text), tr = c.getTransform();
		const dx = c.textAlign === 'center' ? -m.width/2 : c.textAlign === 'right' ? -m.width : 0;
		const corners = [[x+dx,y-m.actualBoundingBoxAscent],[x+dx+m.width,y-m.actualBoundingBoxAscent],[x+dx,y+m.actualBoundingBoxDescent],[x+dx+m.width,y+m.actualBoundingBoxDescent]].map(([px,py])=>tr.transformPoint({x:px,y:py}));
		const xs=corners.map(p=>p.x),ys=corners.map(p=>p.y);
		texts.push({text:String(text),x:Math.min(...xs),y:Math.min(...ys),w:Math.max(...xs)-Math.min(...xs),h:Math.max(...ys)-Math.min(...ys),font:c.font,font_px:parseFloat(c.font)*Math.hypot(tr.a,tr.b),alpha:c.globalAlpha});
		return original(text,x,y,...rest);
	};
	const subtitles = [
		{t0:.55,t1:6.83,text:'寫迴圈時答案常常多一或少一，\n到底什麼時候該寫小於，什麼時候寫小於等於？'},
		{t0:7.58,t1:13.02,text:'這正是最常見的差一錯誤。\n關鍵在於：起點是幾、最後一格要不要算進去。'},
	];
	window.renderFrame = t => {
		texts.length = 0;
		c.setTransform(1,0,0,1,0,0);c.clearRect(0,0,1920,1080);
		CLIPS[grammar].draw(c,t,ctx);
		// 字幕帶由 wrapper 量測，元件內容保留各自 safe 契約。
		c.fillStyle = '#F4EFE6';c.fillRect(0,870,1920,210);
		const sub = subtitles.find(s=>s.t0<=t&&t<=s.t1);
		c.fillStyle = '#111111';c.textAlign='center';c.textBaseline='alphabetic';c.font='42px "Noto Sans CJK TC"';
		if (sub) sub.text.split('\n').forEach((s,i)=>c.fillText(s,960,940+i*60));
		c.font='24px "Noto Sans CJK TC"';c.fillText('外部元件固定 fixture · 保存配音 · 實測句界，非詞級同步',960,1050);
		return {grammar,t,texts:[...texts]};
	};
	window.__total=duration;window.__ready=true;window.renderFrame(0);
	const scrub = document.getElementById('scrub'), audio = document.getElementById('audio');
	scrub.oninput=()=>{audio.currentTime=+scrub.value;window.renderFrame(+scrub.value);document.getElementById('time').textContent=(+scrub.value).toFixed(2)};
	document.getElementById('play').onclick=()=>audio.paused?audio.play():audio.pause();
	const tick=()=>{if(!audio.paused){scrub.value=audio.currentTime;window.renderFrame(audio.currentTime);document.getElementById('time').textContent=audio.currentTime.toFixed(2)}requestAnimationFrame(tick)};
	tick();
})().catch(e=>{window.__failed=String(e.stack||e)});
