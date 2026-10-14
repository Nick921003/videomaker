'use strict';
(async () => {
  const params = new URLSearchParams(location.search);
  const trials = await (await fetch('trials.json')).json();
  const trial = trials.find(t => t.id === params.get('id')) || trials[0];
  const frame = document.getElementById('frame'), stage = document.getElementById('stage');
  const canvas = document.getElementById('c'), context = canvas.getContext('2d');
  const captions = document.getElementById('captions');
  const clamp = x => Math.max(0, Math.min(1, x));
  const progress = (t, start, duration) => clamp((t - start) / duration);
  const smooth = x => x * x * (3 - 2 * x);
  const el = (tag, cls, parent, text) => {
    const node = document.createElement(tag); node.className = cls;
    if (text !== undefined) node.textContent = text;
    parent.appendChild(node); return node;
  };
  const load = src => new Promise((resolve, reject) => {
    const script = document.createElement('script'); script.src = src;
    script.onload = resolve; script.onerror = () => reject(new Error('Missing script: ' + src)); document.head.appendChild(script);
  });
  const style = href => new Promise((resolve, reject) => {
    const link = document.createElement('link'); link.rel = 'stylesheet'; link.href = href;
    link.onload = resolve; link.onerror = () => reject(new Error('Missing style: ' + href)); document.head.appendChild(link);
  });
  // These aliases preserve the original grammar font names while using one saved CJK font.
  const aliases = ['PuHui-Medium','PuHui-Bold','PuHui-Black','PuHui-Heavy','RobotoCondensed','Inter','CMU-rm','CMU-it','NotoSerifSC','EB Garamond','Noto Sans SC','Archivo','Archivo Black','Long Cang','Patrick Hand','ZCOOL KuaiLe'];
  for (const alias of ['Noto Sans CJK TC', ...aliases]) {
    const face = new FontFace(alias, 'url(vendor/teaching-subset.woff)');
    await face.load(); document.fonts.add(face);
  }
  await document.fonts.ready;
  let render;
  let canvasText = [];
  if (trial.renderer === 'canvas') {
    canvas.style.display = 'block'; stage.style.display = 'none';
    window.CLIPS = {};
    window.CLIP = {lt:(t,at,fps)=>t-at+1/fps,p:(t,at,d,fps)=>clamp((t-at+1/fps)/d),fit:(iw,ih,x,y,w,h)=>{const s=Math.min(w/iw,h/ih);return{x:x+(w-iw*s)/2,y:y+(h-ih*s)/2,w:iw*s,h:ih*s,s};},sub:(r,b)=>({x:b.x+r[0]*b.w,y:b.y+r[1]*b.h,w:r[2]*b.w,h:r[3]*b.h})};
    for (const lib of ['util','motion','typo','paint','ui','chart','diagram']) await load('vendor/huashu/scripts/engine/lib/' + lib + '.js');
    await load('vendor/huashu/scripts/engine/clips/' + trial.source_id + '.js');
    U.setStage(1920, 1080);
    const ctx = {W:1920,H:1080,FPS:24,u:1,dur:15,portrait:false,alpha:false,IMG:{},data:trial.payload,theme:{},safe:{top:60,bottom:180,left:70,right:70},box:{x:70,y:60,w:1780,h:840},cues:trial.cues,
      of:(...k)=>trial.cues.filter(q=>k.includes(q.kind)),lt:(t,at)=>CLIP.lt(t,at,24),p:(t,at,d)=>CLIP.p(t,at,d,24)};
    const grammar = CLIPS[trial.source_id]; grammar.init(ctx);
    // Track Canvas text, including text painted into card textures and later transformed by drawImage.
    const records = new WeakMap(); const proto = CanvasRenderingContext2D.prototype;
    const nativeClear = proto.clearRect, nativeReset = proto.reset, nativeFill = proto.fillText, nativeStroke = proto.strokeText, nativeImage = proto.drawImage;
    // The source resets offscreen textures with reset() and canvas.width/height.
    // Reset the measurement ledger too; it must describe this frame only.
    proto.reset=function(...a){records.set(this.canvas,[]);return nativeReset.apply(this,a);};
    for(const dimension of ['width','height']){
      const descriptor=Object.getOwnPropertyDescriptor(HTMLCanvasElement.prototype,dimension);
      Object.defineProperty(HTMLCanvasElement.prototype,dimension,{...descriptor,set(value){records.set(this,[]);descriptor.set.call(this,value);}});
    }
    const transformBox = (b, m) => {
      const points=[[b.x,b.y],[b.x+b.w,b.y],[b.x,b.y+b.h],[b.x+b.w,b.y+b.h]].map(([x,y])=>m.transformPoint({x,y}));
      const xs=points.map(p=>p.x),ys=points.map(p=>p.y);
      return{...b,x:Math.min(...xs),y:Math.min(...ys),w:Math.max(...xs)-Math.min(...xs),h:Math.max(...ys)-Math.min(...ys)};
    };
    const record = (c, text, x, y) => {
      const m=c.measureText(text), fs=parseFloat(c.font.match(/([\d.]+)px/)?.[1]||'0');
      const dx=c.textAlign==='center'?-m.width/2:c.textAlign==='right'||c.textAlign==='end'?-m.width:0;
      let top=y-m.actualBoundingBoxAscent;
      if(c.textBaseline==='top') top=y;
      else if(c.textBaseline==='middle') top=y-(m.actualBoundingBoxAscent+m.actualBoundingBoxDescent)/2;
      const b=transformBox({text:String(text),x:x+dx,y:top,w:m.width,h:m.actualBoundingBoxAscent+m.actualBoundingBoxDescent,font_px:fs,alpha:c.globalAlpha},c.getTransform());
      b.font_px*=Math.hypot(c.getTransform().a,c.getTransform().b);
      const list=records.get(c.canvas)||[];list.push(b);records.set(c.canvas,list);
    };
    proto.clearRect=function(...a){records.set(this.canvas,[]);return nativeClear.apply(this,a);};
    proto.fillText=function(text,x,y,...a){record(this,text,x,y);return nativeFill.call(this,text,x,y,...a);};
    proto.strokeText=function(text,x,y,...a){record(this,text,x,y);return nativeStroke.call(this,text,x,y,...a);};
    proto.drawImage=function(image,...a){
      const entries=records.get(image)||[];
      let sx=0,sy=0,sw=image.width,sh=image.height,dx,dy,dw,dh;
      if(a.length===2){[dx,dy]=a;dw=sw;dh=sh;}else if(a.length===4){[dx,dy,dw,dh]=a;}else{[sx,sy,sw,sh,dx,dy,dw,dh]=a;}
      const list=records.get(this.canvas)||[];
      for(const b of entries){
        const x=Math.max(b.x,sx),y=Math.max(b.y,sy),r=Math.min(b.x+b.w,sx+sw),bot=Math.min(b.y+b.h,sy+sh);
        if(r<=x||bot<=y)continue;
        const box=transformBox({...b,x:dx+(x-sx)*dw/sw,y:dy+(y-sy)*dh/sh,w:(r-x)*dw/sw,h:(bot-y)*dh/sh,font_px:b.font_px*Math.abs(dw/sw),alpha:b.alpha*this.globalAlpha},this.getTransform());
        list.push(box);
      }
      records.set(this.canvas,list);return nativeImage.call(this,image,...a);
    };
    render = t => {
      records.set(canvas,[]); context.setTransform(1,0,0,1,0,0); context.clearRect(0,0,1920,1080);
      context.save(); grammar.draw(context,t,ctx); context.restore();
      canvasText=records.get(canvas)||[];
    };
  } else {
    await style('vendor/lanshu/explainer/kits/' + trial.source_id + '/kit.css');
    await load('vendor/lanshu/explainer/core/core.js');
    await load('vendor/lanshu/explainer/kits/' + trial.source_id + '/kit.js');
    const K=Kit;
    if (trial.id === 'chalk') {
      const B=K.board({stage,cols:1,rows:1,panelW:1780,panelH:820,gap:40});
      const P=K.panel('string',0,0); K.camera([[0,B.W/2,B.H/2+84,1,0,0],[15,B.W/2,B.H/2+84,1,0,0]]);
      K.T(P,70,62,68,[['Hello 為什麼需要六格？',.2,1.6,'cw']],{sprite:true});
      K.T(P,70,165,46,[[trial.payload.code,1.6,2.8,'cb']],{sprite:true});
      const chars=[...trial.payload.chars,'NUL']; const ox=130,y=330,w=225,h=150;
      chars.forEach((char,i)=>{
        const t0=i<5?3+i*.65:7.8;
        K.S(P,K.geo.rect(ox+i*w,y,w,h),'m',4,t0,.55,{sprite:true});
        K.T(P,ox+i*w+(i===5?38:80),y+44,i===5?48:64,[[char,t0+.25,t0+.7,i===5?'cy':'cw']],{sprite:true});
        K.T(P,ox+i*w+90,y+h+28,34,[[String(i),t0+.4,t0+.7,'cm']],{sprite:false});
      });
      K.S(P,K.geo.circ(ox+5.5*w,y+h/2,95,95),'y',5,8.65,.65,{sprite:true});
      const wrong=K.T(P,110,655,55,[[trial.payload.wrong,2.6,3.4,'cp']],{sprite:false});
      K.X(P,[wrong],[90,640,600,100],10.5,1.2);
      K.T(P,110,655,55,[[trial.payload.right,12,12.8,'cg']],{sprite:true});
      K.park(13,P,1500,725,'g'); render=t=>K.render(t);
    } else if (trial.id === 'drafting') {
      stage.style.background='#0b0b0c';K.frame(stage);
      const world=el('div','kit-world',stage);Object.assign(world.style,{width:'1920px',height:'1080px'});
      const heading=el('h1','trial-heading',world,trial.title);el('div','trial-assumption',world,trial.payload.assumption);
      const svg=document.createElementNS('http://www.w3.org/2000/svg','svg');svg.setAttribute('class','kit-svg');svg.setAttribute('width','1920');svg.setAttribute('height','1080');Object.assign(svg.style,{position:'absolute',inset:'0',pointerEvents:'none'});world.appendChild(svg);
      const cells=trial.payload.addresses.map((address,i)=>{
        const c=el('div','array-cell',world);c.style.left=(380+i*290)+'px';
        el('div','',c,'a['+i+']');el('small','',c,String(address));return c;
      });
      const wire=K.leader(svg,{d:'M 525 570 L 525 685 L 1105 685 L 1105 570',a:6.5,b:8.8,flow:8.8,width:4});
      const dim=K.dim(svg,{x1:960,y1:335,x2:1250,y2:335,off:-46,text:'4 bytes',tone:'accent'});
      const label=K.label({text:'a[2] → 1008',sub:'1000 + 2 × 4',tone:'accent'});world.appendChild(label.el);Object.assign(label.el.style,{position:'absolute',left:'1220px',top:'680px',fontSize:'42px'});
      const camera=K.camera(world,[[0,960,540,1,0,0],[8,960,540,1,0,0],[12,975,526,1.015,0,0],[15,975,526,1.015,0,0]]);
      render=t=>{camera.render(t);heading.style.opacity=progress(t,.1,.7);cells.forEach((c,i)=>{c.style.opacity=progress(t,2.5+i*.6,.6);c.style.transform='translateY('+((1-smooth(progress(t,2.5+i*.6,.8)))*35)+'px)';c.classList.toggle('active',i===trial.payload.index&&t>=8.7);});wire.render(t);dim.render(t,7.5);label.render(t,10.4);};
    } else if(trial.id==='paper') {
      stage.style.background='#ece2cc'; const heading=el('h1','trial-heading',stage,trial.title);
      const shell=el('div','paper-shell',stage);el('div','paper-type',shell,trial.payload.type+' s');
      const labels=[K.label({text:'name',sub:trial.payload.name,at:1,dIn:1}),K.label({text:'score',sub:String(trial.payload.score),at:3,dIn:1})];
      labels.forEach((l,i)=>{l.el.classList.add('paper-field');stage.appendChild(l.el);l.el.style.left=(i?1080:240)+'px';});
      const note=K.note('[[同一筆資料]]，欄位一起移動。',{at:10.8,dIn:.9});stage.appendChild(note.el);note.el.classList.add('paper-note');Object.assign(note.el.style,{top:'730px',left:'460px',width:'1000px'});
      render=t=>{
        heading.style.opacity=progress(t,.1,.6);shell.style.opacity=progress(t,5.8,.4);shell.style.transform='perspective(1400px) rotateX('+K.fold(t,5.8,1.3,100,1)+'deg)';shell.style.transformOrigin='50% 100%';
        labels.forEach((l,i)=>{l.render(t);const p=smooth(progress(t,7+i*.35,1.5));const start=i?1080:240;const dest=i?1010:360;l.el.style.left=(start+(dest-start)*p)+'px';l.el.style.top=(330+95*p)+'px';});note.render(t);
      };
    }
  }
  const measureDOM=()=>{
    const result=[],fr=frame.getBoundingClientRect(),sc=fr.width/1920;
    const visible=node=>{let opacity=1;for(let e=node;e&&e!==frame.parentElement;e=e.parentElement){const s=getComputedStyle(e);if(s.display==='none'||s.visibility==='hidden')return 0;opacity*=parseFloat(s.opacity);}return opacity;};
    const walker=document.createTreeWalker(frame,NodeFilter.SHOW_TEXT);
    let node;
    while((node=walker.nextNode())){
      if(!node.textContent.trim()||node.parentElement.closest('script,style'))continue;
      const alpha=visible(node.parentElement);if(alpha<.15)continue;
      if(node.parentElement instanceof SVGTextElement){
        // Chromium's Range rectangle for SVG text can retain the previous
        // ancestor camera transform until paint. Use its actual current CTM.
        const parent=node.parentElement,b=parent.getBBox(),m=parent.getCTM();
        const world=parent.ownerSVGElement.parentElement,camera=new DOMMatrix(getComputedStyle(world).transform);
        const points=[[b.x,b.y],[b.x+b.width,b.y],[b.x,b.y+b.height],[b.x+b.width,b.y+b.height]].map(([x,y])=>camera.transformPoint({x:m.a*x+m.c*y+m.e,y:m.b*x+m.d*y+m.f}));
        const xs=points.map(p=>p.x),ys=points.map(p=>p.y);
        result.push({text:node.textContent,x:Math.min(...xs),y:Math.min(...ys),w:Math.max(...xs)-Math.min(...xs),h:Math.max(...ys)-Math.min(...ys),font_px:parseFloat(getComputedStyle(parent).fontSize),alpha,role:'content'});continue;
      }
      const range=document.createRange();range.selectNodeContents(node);
      for(const r of range.getClientRects())if(r.width&&r.height)result.push({text:node.textContent,x:(r.x-fr.x)/sc,y:(r.y-fr.y)/sc,w:r.width/sc,h:r.height/sc,font_px:parseFloat(getComputedStyle(node.parentElement).fontSize),alpha,role:node.parentElement.closest('#captions')?'subtitle':'content'});
    }
    return result;
  };
  const fit=()=>{frame.style.transform=params.has('export')?'none':'scale('+Math.min(innerWidth/1920,innerHeight/1080)+')';};fit();addEventListener('resize',fit);
  window.renderFrame=t=>{
    t=Math.max(0,Math.min((trial.duration*24-1)/24,t));render(t);
    const sub=trial.subtitles.find(s=>s[0]<=t&&t<s[1]);captions.textContent=sub?sub[2]:'';
    window.__time=t;return{id:trial.id,t,subtitle:captions.textContent,texts:[...canvasText,...measureDOM()]};
  };
  let playing=false,anchor=0,origin=0;
  addEventListener('message',e=>{
    if(e.source!==parent||e.origin!==location.origin||!e.data||typeof e.data.type!=='string')return;
    if(e.data.type==='seek'&&Number.isFinite(e.data.time)){playing=false;renderFrame(e.data.time);}
    if(e.data.type==='play'){playing=true;anchor=performance.now();origin=window.__time||0;}
    if(e.data.type==='pause')playing=false;
  });
  const tick=now=>{if(playing){const t=origin+(now-anchor)/1000;renderFrame(Math.min(t,15));if(t>=15)playing=false;parent.postMessage({type:'progress',time:window.__time,playing},location.origin);}requestAnimationFrame(tick);};
  window.__sourceId=trial.source_id;renderFrame(0);window.__ready=true;requestAnimationFrame(tick);
  parent.postMessage({type:'ready',id:trial.id},location.origin);
})().catch(error=>{window.__failed=String(error.stack||error);console.error(error);});
