'use strict';
(async()=>{
  const trials=await(await fetch('trials.json')).json();
  const $=id=>document.getElementById(id), key='videomaker-component-trials-20261011';
  let choices={};try{choices=JSON.parse(localStorage.getItem(key)||'{}');}catch{}
  let current,mode='animation',ready=false,playing=false,mediaUrl=null;
  const setTime=t=>{$('seek').value=t;$('time').textContent=Number(t).toFixed(1)+' / 15.0 秒';};
  const send=data=>$('player').querySelector('iframe')?.contentWindow.postMessage(data,location.origin);
  const removePoster=()=>$('player').querySelector('.poster')?.remove();
  const setReady=v=>{ready=v;['play','restart','seek'].forEach(id=>$(id).disabled=!v);$('state').textContent=v?'無聲試片，可播放、拖曳和重播。':'正在載入元件…';};
  const updateChoices=()=>{
    for(const card of $('cards').children)card.querySelector('.choice').textContent=choices[card.dataset.id]||'尚未評選';
    for(const button of $('evaluation').querySelectorAll('button'))button.setAttribute('aria-pressed',String(Boolean(button.dataset.choice)&&choices[current.id]===button.dataset.choice));
    $('saved').textContent=choices[current.id]?'此瀏覽器已記錄：'+choices[current.id]:'看過動畫後，再決定是否保留。';
  };
  const load=()=>{
    if(mediaUrl){URL.revokeObjectURL(mediaUrl);mediaUrl=null;}
    setReady(false);playing=false;$('play').textContent='播放';setTime(0);$('player').replaceChildren();
    if(mode==='animation'){
      const frame=document.createElement('iframe');frame.title=current.title;frame.src='sample.html?id='+current.id;$('player').appendChild(frame);
    }else{
      const video=document.createElement('video');video.playsInline=true;video.preload='auto';$('player').appendChild(video);
      video.onloadeddata=()=>setReady(true);video.onerror=()=>{$('state').textContent='無法播放 MP4；可切換動畫預覽。';};
      video.ontimeupdate=()=>setTime(video.currentTime);video.onended=()=>{playing=false;$('play').textContent='播放';};
      // These small local trial clips can be loaded fully. A Blob URL supports
      // seeking even when Python's static server does not serve HTTP ranges.
      fetch('out/'+current.id+'.mp4').then(response=>{if(!response.ok)throw new Error('HTTP '+response.status);return response.blob();}).then(blob=>{
        if(!video.isConnected)return;mediaUrl=URL.createObjectURL(blob);video.src=mediaUrl;
      }).catch(error=>{if(video.isConnected)$('state').textContent='MP4 讀取失敗：'+error.message+'。可切換動畫預覽。';});
    }
    const poster=document.createElement('button');poster.className='poster';poster.setAttribute('aria-label','播放 '+current.style+' 的十五秒樣片');
    const picture=document.createElement('img');picture.src='out/'+current.id+(current.id==='keynote'?'-8.png':'-14.9.png');picture.alt=current.style+' 效果預覽畫面';
    const badge=document.createElement('span');badge.textContent='▶ 播放 15 秒動畫';poster.append(picture,badge);poster.onclick=()=>{if(ready)$('play').click();};$('player').appendChild(poster);
    $('animation').setAttribute('aria-pressed',String(mode==='animation'));$('mp4').setAttribute('aria-pressed',String(mode==='mp4'));
  };
  const select=id=>{
    current=trials.find(t=>t.id===id)||trials[0];history.replaceState(null,'','#'+current.id);
    for(const card of $('cards').children)card.setAttribute('aria-pressed',String(card.dataset.id===current.id));
    $('title').textContent=current.title;$('effect').textContent=current.effect;$('use').textContent='可用情境：'+current.use;
    const source=document.createElement('a');source.target='_blank';source.rel='noopener';
    source.textContent=current.source_id+' · 原始元件來源';
    source.href=current.renderer==='canvas'?'https://github.com/alchaincyf/huashu-art-motion/blob/57d67608ab458f57d9b153b1a2831b921e22498b/scripts/engine/clips/'+current.source_id+'.js':'https://github.com/cclank/lanshu-create-ai-presenter-video/blob/c24720a85d63b1bd494f6447e48a59384733647b/explainer/kits/'+current.source_id+'/kit.js';
    $('source').replaceChildren(source);$('download').href='out/'+current.id+'.mp4';$('subtitles').href='out/'+current.id+'.srt';
    $('timeline').replaceChildren();for(const[start,end,label]of current.rhythm){const node=document.createElement('div');node.className='beat';node.style.flex=String(end-start);node.textContent=label;node.title=start+'–'+end+' 秒';$('timeline').appendChild(node);}
    updateChoices();load();
  };
  for(const trial of trials){const button=document.createElement('button');button.className='card';button.dataset.id=trial.id;const small=document.createElement('small');small.textContent=trial.candidate;const strong=document.createElement('strong');strong.textContent=trial.style;const choice=document.createElement('span');choice.className='choice';button.append(small,strong,choice);button.onclick=()=>select(trial.id);$('cards').appendChild(button);}
  addEventListener('message',e=>{
    if(e.origin!==location.origin||e.source!==$('player').querySelector('iframe')?.contentWindow)return;
    if(e.data.type==='ready')setReady(true);
    // A queued playback tick must not overwrite a newer pause or seek.
    if(e.data.type==='progress'&&playing){setTime(e.data.time);if(!e.data.playing){playing=false;$('play').textContent='播放';}}
  });
  $('play').onclick=()=>{
    if(!ready)return;removePoster();playing=!playing;
    if(mode==='animation'){if(playing&&+$('seek').value>=14.95){send({type:'seek',time:0});setTime(0);}send({type:playing?'play':'pause'});}
    else{const video=$('player').querySelector('video');if(playing){if(video.currentTime>=14.99)video.currentTime=0;video.play();}else video.pause();}
    $('play').textContent=playing?'暫停':'播放';
  };
  const seek=t=>{removePoster();playing=false;$('play').textContent='播放';if(mode==='animation')send({type:'seek',time:t});else{const video=$('player').querySelector('video');video.pause();video.currentTime=t;}setTime(t);};
  $('seek').oninput=()=>seek(+$('seek').value);$('restart').onclick=()=>{seek(0);$('play').click();};
  $('animation').onclick=()=>{mode='animation';load();};$('mp4').onclick=()=>{mode='mp4';load();};
  $('evaluation').onclick=e=>{const button=e.target.closest('[data-choice]');if(!button)return;if(button.dataset.choice)choices[current.id]=button.dataset.choice;else delete choices[current.id];try{localStorage.setItem(key,JSON.stringify(choices));updateChoices();}catch{$('saved').textContent='瀏覽器無法儲存，請匯出評選紀錄。';}};
  $('export-choices').onclick=()=>{const blob=new Blob([JSON.stringify({batch:'20261011',choices},null,2)],{type:'application/json'});const url=URL.createObjectURL(blob),link=document.createElement('a');link.href=url;link.download='component-choices-20261011.json';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
  select(location.hash.slice(1));
})().catch(error=>{document.getElementById('state').textContent='讀取失敗：'+error.message;});
