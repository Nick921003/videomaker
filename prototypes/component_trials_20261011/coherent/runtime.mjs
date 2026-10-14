import {stateAt} from './model.mjs';
const $=id=>document.getElementById(id), params=new URLSearchParams(location.search);
const make=(tag,cls,parent,text)=>{const n=document.createElement(tag);n.className=cls;if(text!==undefined)n.textContent=text;parent.appendChild(n);return n;};
const svgMake=(tag,attrs,parent)=>{const n=document.createElementNS('http://www.w3.org/2000/svg',tag);for(const[k,v]of Object.entries(attrs))n.setAttribute(k,v);parent.appendChild(n);return n;};
const script=src=>new Promise((resolve,reject)=>{const s=make('script','',document.head);s.src=src;s.onload=resolve;s.onerror=()=>reject(Error(src));});
const setVars=vars=>{for(const[k,v]of Object.entries(vars))$('frame').style.setProperty('--'+k,v);};
try {
	const [lesson,theme]=await Promise.all([fetch('lesson.json').then(r=>r.json()),fetch('../../../video_engine/themes/coherent_demo.json').then(r=>r.json())]);
	for(const family of ['Teaching TC','PuHui-Medium','PuHui-Bold','RobotoCondensed','CMU-rm','CMU-it','NotoSerifSC']) {
		const face=new FontFace(family,'url(teaching.woff)');await face.load();document.fonts.add(face);
	}
	await document.fonts.ready;
	for(const lib of ['util','motion','typo','paint','chart','diagram'])await script('../vendor/huashu/scripts/engine/lib/'+lib+'.js');
	await script('../vendor/lanshu/explainer/core/core.js');await script('../vendor/lanshu/explainer/kits/v7-drafting/kit.js');
	U.setStage(1920,1080);
	const codeRows=lesson.code.map(s=>{const r=make('div','code-row',$('lines'));make('span','',r,s);return r;});
	const cards=lesson.concepts.map((c,i)=>{const r=make('div','concept-card',$('concept'));r.style.top=(65+i*175)+'px';make('div','number',r,String(i+1).padStart(2,'0'));const txt=make('div','',r);make('h2','',txt,c.title);make('code','',txt,c.code);make('div','note',r,c.note);return r;});
	const svg=$('flow'), eng=$('engineering');
	const geometry={init:[390,58,360,65],check:[390,191,320,100],body:[390,332,340,76],update:[390,472,340,76],exit:[790,191,240,76]};
	const nodes={};for(const[id,[x,y,w,h]]of Object.entries(geometry)){const n=make('div','node-label'+(id==='check'?' condition':''),eng,lesson.flow[id]);Object.assign(n.style,{left:(x-w/2)+'px',top:(y-h/2)+'px',width:w+'px',height:h+'px'});nodes[id]=n;}
	const edgeDefs={init:{d:'M 390 91 L 390 141',a:.9,b:1.8},yes:{d:'M 390 241 L 390 294',a:9,b:9.55},body:{d:'M 390 370 L 390 434',a:9.65,b:10.2},back:{d:'M 220 472 L 110 472 L 110 191 L 230 191',a:10.3,b:11.1},no:{d:'M 550 191 L 670 191',a:21,b:21.6}};
	const edges={};for(const[id,o]of Object.entries(edgeDefs)){edges[id]=Kit.leader(svg,{...o,width:4});edges[id].el.classList.toggle('exit-edge',id==='no');}
	const tips={};for(const[id,points]of [['init','382,130 390,141 398,130'],['yes','382,283 390,294 398,283'],['body','382,423 390,434 398,423'],['back','219,183 230,191 219,199'],['no','659,183 670,191 659,199']])tips[id]=svgMake('polyline',{points,fill:'none',stroke:theme.technical.line,'stroke-width':3},svg);
	const marker=svgMake('circle',{r:8,fill:theme.technical.current},svg);
	const flowLabels={};for(const[id,x,y,text]of [['yes',418,254,'成立'],['no',570,132,'不成立'],['back',22,305,'回到\n條件']]){const n=make('div','flow-tag',eng,text);Object.assign(n.style,{left:x+'px',top:y+'px',whiteSpace:'pre-line'});flowLabels[id]=n;}
	const notes=lesson.concepts.map((c,i)=>{const n=make('div','paper-note',$('paper-notes'));n.style.top=(80+i*135)+'px';make('span','key',n,c.title);make('span','value',n,c.code);make('span','hint',n,c.note);make('div','paper-corner',n);return n;});
	const canvases=[$('chart'),$('formula')], boxes=[];
	for(const canvas of canvases){const ctx=canvas.getContext('2d');const fill=ctx.fillText.bind(ctx);ctx.fillText=(text,x,y,...rest)=>{const m=ctx.measureText(text),tr=ctx.getTransform();const dx=ctx.textAlign==='center'?-m.width/2:ctx.textAlign==='right'?-m.width:0;const p=tr.transformPoint({x:x+dx,y:y-m.actualBoundingBoxAscent});if(ctx.globalAlpha>=.15)boxes.push({text:String(text),x:p.x+820,y:p.y+260,w:m.width*tr.a,h:(m.actualBoundingBoxAscent+m.actualBoundingBoxDescent)*tr.d,alpha:ctx.globalAlpha,region:'visual',font_px:parseFloat(ctx.font.match(/[\d.]+px/)?.[0]||'0')});return fill(text,x,y,...rest);};}
	const p=(t,a,d)=>Math.max(0,Math.min(1,(t-a)/d));
	const vars={bg:theme.canvas.bg,grid:theme.canvas.grid,paper:theme.card.fill,edge:theme.card.edge,ink:theme.text.title,muted:theme.text.muted,accent:theme.text.accent,current:theme.semantic.current,condition:theme.semantic.condition,result:theme.semantic.result,'tech-bg':theme.technical.bg,'tech-surface':theme.technical.surface,'tech-ink':theme.technical.text,'tech-muted':theme.technical.muted,'tech-line':theme.technical.line,'tech-grid':theme.technical.grid,'tech-current':theme.technical.current,'tech-condition':theme.technical.condition,flat:theme.flat.bg,fold:theme.flat.fold,crease:theme.flat.crease,shadow:theme.effects.shadow};
	let mode=params.get('mode')==='switching'?'switching':'coherent';
	const drawChart=(t,state)=>{
		const ctx=$('chart').getContext('2d');ctx.clearRect(0,0,990,607);
		const F={x:100,y:150,w:780,h:300}, y=CH.lin(0,6,450,150),elapsed=t-31;
		CH.grid(ctx,F,[0,2,4,6],y,p(elapsed,0,.8),{col:theme.flat.grid,zeroCol:theme.text.title,font:'28px "Teaching TC"',labelCol:theme.text.muted,side:'right',labelDy:-6});
		const series=[{x:320,v:state.execution.bodies},{x:655,v:state.execution.checks}];
		for(let j=0;j<2;j++)CH.bars(ctx,[series[j]],y,135,p(elapsed,1+j*1.2,1.1),{lag:0,col:j?theme.semantic.condition:theme.semantic.current,labelCol:theme.text.title,font:'44px "Teaching TC"',fmt:v=>String(Math.round(v))});
		CH.xLabels(ctx,[{x:320,label:'主體 sum += i'},{x:655,label:'條件 i <= 5'}],508,p(elapsed,.6,.5),{font:'30px "Teaching TC"',col:theme.text.title});
		ctx.save();ctx.globalAlpha=p(elapsed,4,.6);ctx.fillStyle=theme.semantic.condition;ctx.font='29px "Teaching TC"';ctx.textAlign='center';ctx.fillText('多一次判斷，才能確認離開。',495,564);ctx.restore();
	};
	// 沿用 t1 的符號匹配規則，以共用字型／配色適配，沒有整頁來源皮膚。
	const drawFormula=t=>{
		const ctx=$('formula').getContext('2d');ctx.clearRect(0,0,990,607);ctx.font='48px "Teaching TC"';
		const old=['sum','=','1','+','2','+','3','+','4','+','5'],newer=['sum','=','15'],size=48;
		const layout=tokens=>{let total=0;const out=tokens.map(s=>{const w=ctx.measureText(s).width+16,r={s,x:total,w};total+=w;return r;});return out.map(r=>({...r,x:r.x+495-total/2}));};
		const a=layout(old),b=layout(newer),q=MO.smooth(p(t,44,1.4));
		const token=(s,x,alpha,offset=0)=>{if(alpha<=0)return;ctx.save();ctx.globalAlpha=alpha;DG.math(ctx,[{s,font:'Teaching TC',zh:true,col:s==='sum'?theme.semantic.result:theme.text.title,gap:0}],x,547+offset,size,{align:'left',p:1});ctx.restore();};
		if(t<44){const write=p(t,41,.9);a.forEach((r,i)=>token(r.s,r.x,p(write,i/a.length,.15)));}
		else{const used=new Set(),move=p(q,.35,.65);b.forEach(n=>{const j=a.findIndex((r,i)=>r.s===n.s&&!used.has(i));if(j>=0){used.add(j);token(n.s,a[j].x+(n.x-a[j].x)*move,1);}else token(n.s,n.x,p(q,.8,.2));});a.forEach((r,i)=>{if(!used.has(i))token(r.s,r.x,1-p(q,0,.3));});}
	};
	const measure=()=>{
		const result=[...boxes], fr=$('frame').getBoundingClientRect(),scale=fr.width/1920;
		const walk=document.createTreeWalker($('frame'),NodeFilter.SHOW_TEXT);let n;
		while((n=walk.nextNode())){if(!n.textContent.trim())continue;let opacity=1;for(let e=n.parentElement;e&&e!==$('frame').parentElement;e=e.parentElement){const s=getComputedStyle(e);if(s.display==='none'||s.visibility==='hidden'){opacity=0;break;}opacity*=Number(s.opacity);}if(opacity<.15)continue;const range=document.createRange();range.selectNodeContents(n);for(const r of range.getClientRects())if(r.width&&r.height)result.push({text:n.textContent,x:(r.x-fr.x)/scale,y:(r.y-fr.y)/scale,w:r.width/scale,h:r.height/scale,alpha:opacity,region:n.parentElement.closest('[data-region]')?.dataset.region,font_px:parseFloat(getComputedStyle(n.parentElement).fontSize)});}
		return result;
	};
	window.renderFrame=time=>{
		const state=stateAt(time,lesson),t=state.time, e=state.execution;boxes.length=0;
		setVars(vars);
		if(mode==='switching'&&['flow','trace'].includes(state.scene))setVars({bg:theme.technical.bg,grid:theme.technical.grid,paper:theme.technical.surface,ink:theme.technical.text,muted:theme.technical.muted,edge:theme.technical.line,current:theme.technical.current,condition:theme.technical.condition,result:theme.technical.result});
		if(mode==='switching'&&state.scene==='chart')setVars({bg:theme.comparison.bg,grid:theme.comparison.bg,paper:theme.comparison.bg,ink:theme.comparison.ink,edge:theme.comparison.line});
		$('title').textContent=state.chapter.title;$('chapter').textContent=state.chapter.label;$('captions').textContent=state.subtitle;
		$('i-value').textContent=e.i;$('sum-value').textContent=e.sum;
		const stepNames={ready:'先看三件事',init:'初始化',check:e.next==='exit'?'條件不成立':'檢查條件',body:'累加',update:'更新 i',return:'回到條件',exit:'離開迴圈'};$('step').textContent=t<16?'先看三件事':stepNames[e.step];
		const active=t<16?-1:e.step==='init'?0:['check','update','return'].includes(e.step)?1:e.step==='body'?2:-1;codeRows.forEach((r,i)=>r.style.setProperty('--active',i===active?.12:0));
		const concept=t<8,flow=t>=8&&t<31,chart=t>=31&&t<39,recap=t>=39;
		$('concept').style.display=concept?'block':'none';$('engineering').style.display=flow?'block':'none';$('quantity').style.display=chart?'block':'none';$('recap').style.display=recap?'block':'none';
		$('engineering').style.opacity=MO.smooth(p(t,8,.7));
		cards.forEach((c,i)=>{const q=MO.smooth(p(t,.3+i*1.75,.65));c.style.opacity=q;c.style.transform='translateY('+18*(1-q)+'px)';});
		for(const[id,node]of Object.entries(nodes)){const order=['init','check','body','update','exit'].indexOf(id);node.style.opacity=p(t,id==='exit'?29:8+order*.85,.6);node.classList.toggle('active',t>=16&&e.step===id);}
		const flowPresentation={labels:{},edges:[]};
		for(const[id,edge]of Object.entries(edges)){edge.render(t-8);const draw=1-Number(edge.el.style.strokeDashoffset)/edge.len;const tip=draw>=.999?1:0;tips[id].style.opacity=tip;flowPresentation.edges.push({id,draw_progress:draw,tip_alpha:tip});}
		for(const[id,at]of [['yes',17],['back',18.3],['no',29]]){const q=p(t,at,.25);flowLabels[id].style.opacity=q;flowPresentation.labels[id]=q;}
		let currentEdge=null,span=.65,begin=e.at;
		if(t>=16&&t<29.65){if(e.step==='init'){currentEdge='init';span=1;}else if(e.step==='check')currentEdge=e.next==='exit'?'no':'yes';else if(e.step==='body')currentEdge='body';else{currentEdge='back';span=1.1;if(e.step==='return')begin=e.at-.55;}}
		for(const[id,edge]of Object.entries(edges))edge.el.classList.toggle('active-edge',id===currentEdge);
		marker.style.display=currentEdge?'block':'none';if(currentEdge){const xy=edges[currentEdge].point(MO.smooth(p(t,begin,span)));marker.setAttribute('cx',xy.x);marker.setAttribute('cy',xy.y);marker.setAttribute('fill',currentEdge==='no'?theme.technical.condition:theme.technical.current);}
		$('flow-note').textContent=t<9.5?'先設定 i = 1，並把 sum 歸零。':t<16?'每一輪開始前，都要先檢查條件。':e.step==='exit'?'i = 6 → 不成立 → 離開；sum = 15':e.next==='exit'?'第 6 次條件判斷 · i = 6，不成立':`第 ${state.executionRound} 輪 · ${e.step==='body'?'主體累加完成':e.step==='update'||e.step==='return'?'更新後，返回條件':stepNames[e.step]}`;
		if(chart)drawChart(t,state);else $('chart').getContext('2d').clearRect(0,0,990,607);
		if(recap)drawFormula(t);else $('formula').getContext('2d').clearRect(0,0,990,607);
		notes.forEach((n,i)=>{const q=MO.smooth(p(t,39.3+i*.45,.7));n.style.opacity=q;const peel=Math.sin(Math.PI*p(t,39.3+i*.45,1.3));n.style.setProperty('--corner',(12+40*peel)+'px');n.querySelector('.value').style.opacity=p(t,39.6+i*.45,.5);});
		$('takeaway').textContent=t<8?'觀念用筆記整理。':t<31?'流程用工程圖理解；數值與程式保持在同一頁。':t<39?'這是程式執行次數的推導，動畫速度不代表 CPU 執行時間。':'起點 → 繼續條件 → 主體 → 更新 → 回到條件；不成立才離開。';
		window.__time=t;
		return{...state,mode,texts:measure(),activeEdge:currentEdge,flowPresentation,theme:'coherent_demo',sources:['Kit.leader','CH.grid','CH.bars','DG.math']};
	};
	window.setMode=value=>{mode=value==='switching'?'switching':'coherent';return window.renderFrame(window.__time||0);};
	const fit=()=>{$('frame').style.transform=params.has('export')?'none':'scale('+Math.min(innerWidth/1920,innerHeight/1080)+')';};fit();addEventListener('resize',fit);
	window.__regions={header:[110,45,1700,166],code:[110,260,660,440],numbers:[110,722,660,145],visual:[820,260,990,607],takeaway:[110,883,1700,40],captions:[110,942,1700,95]};
	window.__lesson=lesson;window.renderFrame(0);window.__ready=true;
}catch(error){window.__failed=String(error.stack||error);console.error(error);}
