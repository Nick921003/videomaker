// A的紙張與鏡頭保留；在執行段加入C的程式提示。時間取實際音訊。
const MOVIE=JSON.parse(document.getElementById("movie-data").textContent);
setPlaying(false);
cameras.splice(0,cameras.length,...cameras.filter(c=>c.focus!=="overview"));
const originalWorldScene=worldScene;
worldScene=function(state,cam,paperStyle){
	if(state.scene!=="read_stop"){
		if(state.scene==="comparison"&&state.t<32.1)state={...state,visible:state.visible.filter(id=>id!=="comparison")};
		originalWorldScene(state,cam,paperStyle);return;
	}
	ctx.save();ctx.translate(G.w/2,304);ctx.scale(cam[2],cam[2]);ctx.translate(-cam[0],-cam[1]);
	ctx.drawImage(paper,0,0);ink([[170,540],[160,740],[175,1180],[150,1430],[170,2090]],clamp(state.t/36),C.accent,2,61);
	text(260,1480,"一路讀到終點",31,C.muted);ink([[260,1505],[460,1505]],1,C.accent,3,102);
	const enter=ease((state.t-16.95)/.4),leave=ease((state.t-18.95)/.75),weight=enter*(1-leave);
	const panelAlpha=ease((state.t-17.35)/.2)*(1-ease((state.t-18.65)/.25));
	const x=mix(G.x,700,weight),cw=mix(G.cellW,83,weight),step=mix(G.step,98,weight),y=arrayY(state.t);
	const ox=mix(630,740,weight),ow=mix(480,430,weight);
	if(panelAlpha>.005){ctx.save();ctx.globalAlpha=panelAlpha;ctx.fillStyle=C.code;ctx.fillRect(100,1530,555,330);text(130,1570,"執行到這一行",26,C.codeText);text(130,1685,'printf("%s", name);',30,C.codeText,"left","code_hint",true);text(130,1802,"印出字串",26,C.codeText);ctx.restore()}
	if(state.visible.includes("array")){row(x,y,cw,step,state,weight<.25);text(x,y-88,"同一個 name 陣列",25,C.muted,"left","array_label")}
	if(state.visible.includes("cursor"))pointer(x+state.cursor*step+cw/2,y-45,state,cw);
	if(state.visible.includes("output"))outputBox(ox,1890,ow,105,state);
	for(const e of scans){if(state.t>=e.time+.4&&state.t<e.time+e.duration){const p=ease((state.t-e.time-.4)/(e.duration-.4));const x0=x+e.index*step+cw/2,x1=ox+ow/2-73+e.index*29;text(mix(x0,x1,p),mix(y+65,1950,p),"Alice"[e.index],43,C.accent,"center","scan_flight",true)}}
	if(state.visible.includes("termination_note")){ellipse(x+5*step+cw/2,y+cw*.54,75,86,ease((state.t-26.2)/.8));text(950,y+175,"到這裡就停",31,C.accent,"center","termination_note")}
	ctx.restore();
};
function visualTime(real){
	const a=MOVIE.anchors;real=clamp(real,0,MOVIE.duration);
	for(let i=1;i<a.length;i++)if(real<=a[i].real){const p=(real-a[i-1].real)/(a[i].real-a[i-1].real);return mix(a[i-1].visual,a[i].visual,clamp(p))}
	return 43.999;
}
window.sourceCanvas=canvas;
window.renderMovie=function(real){
	real=clamp(Number(real)||0,0,MOVIE.duration);const vt=Math.min(43.999,visualTime(real));
	const cue=MOVIE.subtitle_cues.find(c=>c.start<=real&&real<c.end);const s=stateAt(vt);s.subtitle=cue?cue.text:"";
	mode="paper";drawTime=vt;drawn=[];pencilMode=true;ctx.setTransform(1,0,0,1,0,0);ctx.clearRect(0,0,G.w,G.h);ctx.fillStyle=C.paper;ctx.fillRect(0,0,G.w,G.h);
	ctx.save();ctx.beginPath();ctx.rect(0,66,G.w,549);ctx.clip();worldScene(s,cameraAt(vt),true);ctx.restore();screenCaption(s);
	ctx.fillStyle=C.paper;ctx.fillRect(0,702,1280,18);
	window.__movieState={...s,real,visual_time:vt,camera:cameraAt(vt),textBoxes:drawn};return window.__movieState;
};
const audio=document.getElementById("narration"),movieSeek=document.getElementById("movie-seek"),moviePlay=document.getElementById("movie-play"),movieClock=document.getElementById("movie-clock");
movieSeek.max=MOVIE.duration;window.renderMovie(0);
function updateMovie(){const t=audio.currentTime;if(!audio.paused){window.renderMovie(t);movieSeek.value=t}movieClock.textContent=`${t.toFixed(1)} / ${MOVIE.duration.toFixed(1)} 秒`;moviePlay.textContent=audio.paused?"播放":"暫停";requestAnimationFrame(updateMovie)}
moviePlay.addEventListener("click",()=>audio.paused?audio.play():audio.pause());movieSeek.addEventListener("input",()=>{audio.currentTime=Number(movieSeek.value);window.renderMovie(audio.currentTime)});requestAnimationFrame(updateMovie);
