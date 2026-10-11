const $=id=>document.getElementById(id), frame=$('preview'),video=$('video');
const lesson=await(await fetch('lesson.json')).json(),last=lesson.duration-1/lesson.fps;
let ready=false,playing=false,time=0,anchor=0,start=0,mode='coherent',isVideo=false,blob=null,videoLoad=null,requestVersion=0;
const showClock=()=>{$('seek').value=time;$('clock').textContent=time.toFixed(1)+' / 48 秒';};
const pause=()=>{playing=false;video.pause();$('play').textContent='播放';};
const seek=t=>{pause();time=Math.max(0,Math.min(last,t));if(isVideo)video.currentTime=time;else if(ready)frame.contentWindow.renderFrame(time);showClock();};
const play=()=>{if(time>=last-.02)seek(0);if(isVideo){video.play().catch(e=>{$('status').textContent='影片播放失敗：'+e.message;pause();});}else{anchor=performance.now();start=time;}playing=true;$('play').textContent='暫停';};
const useHTML=newMode=>{requestVersion++;mode=newMode;if(!ready)return;pause();isVideo=false;video.style.display='none';frame.style.display='block';frame.contentWindow.setMode(mode);frame.contentWindow.renderFrame(time);for(const id of ['coherent','switching','mp4'])$(id).setAttribute('aria-pressed',String(id===mode));$('status').textContent=mode==='coherent'?'暖色基底保持一致；工程圖與量化圖表在同一區域切換。':'同內容、同節奏的整頁換色對照。';};
$('coherent').onclick=()=>useHTML('coherent');$('switching').onclick=()=>useHTML('switching');
$('play').onclick=()=>playing?pause():play();$('restart').onclick=()=>{seek(0);play();};$('seek').oninput=e=>seek(Number(e.target.value));
for(const c of lesson.chapters){const b=document.createElement('button');b.textContent=c.label;b.disabled=true;b.onclick=()=>seek(c.at);$('chapters').appendChild(b);}
const tick=now=>{if(playing&&!isVideo){time=Math.min(last,start+(now-anchor)/1000);frame.contentWindow.renderFrame(time);showClock();if(time>=last)pause();}requestAnimationFrame(tick);};requestAnimationFrame(tick);
video.addEventListener('timeupdate',()=>{if(isVideo){time=Math.min(last,video.currentTime);showClock();}});video.addEventListener('ended',()=>{time=last;showClock();pause();});
const loadVideo=()=>videoLoad ||= (async()=>{
	try{const response=await fetch('out/coherent.mp4');if(!response.ok)throw Error('成片尚未匯出');blob=URL.createObjectURL(await response.blob());await new Promise((resolve,reject)=>{video.addEventListener('loadedmetadata',resolve,{once:true});video.addEventListener('error',reject,{once:true});video.src=blob;});}
	catch(error){if(blob)URL.revokeObjectURL(blob);blob=null;videoLoad=null;throw error;}
})();
$('mp4').onclick=async()=>{
	const request=++requestVersion;pause();$('status').textContent='正在載入成片…';
	try{await loadVideo();if(request!==requestVersion)return;
		isVideo=true;frame.style.display='none';video.style.display='block';video.currentTime=time;
		for(const id of ['coherent','switching','mp4'])$(id).setAttribute('aria-pressed',String(id==='mp4'));$('status').textContent='成片：48 秒、1080p、動畫與字幕。';
	}catch(error){if(request===requestVersion)$('status').textContent=error.message||'影片載入失敗。';}
};
addEventListener('beforeunload',()=>{if(blob)URL.revokeObjectURL(blob);});
const wait=()=>{if(frame.contentWindow.__failed){$('status').textContent='動畫載入失敗：'+frame.contentWindow.__failed;return;}if(!frame.contentWindow.__ready){setTimeout(wait,100);return;}ready=true;for(const control of document.querySelectorAll('button,input'))control.disabled=false;useHTML(mode);};wait();
fetch('out/coherent.mp4',{method:'HEAD'}).then(r=>{if(r.ok)$('downloads').style.display='block';});
