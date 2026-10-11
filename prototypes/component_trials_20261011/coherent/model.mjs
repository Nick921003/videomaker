const round = n => Math.round(n*1000)/1000;
export function buildTrace(lesson) {
	const {start,limit,sum:initial,trace_start:at,cycle} = lesson.example;
	let sum=initial, checks=0, bodies=0;
	const out=[{at:at-1,step:'init',i:start,sum,checks,bodies,next:'check'}];
	for(let i=start;i<=limit;i++) {
		const t=at+(i-start)*cycle;
		checks++;
		out.push({at:round(t),step:'check',i,sum,checks,bodies,next:'body'});
		sum+=i; bodies++;
		out.push({at:round(t+.65),step:'body',i,sum,checks,bodies,next:'update'});
		out.push({at:round(t+1.3),step:'update',i:i+1,sum,checks,bodies,next:'check'});
		out.push({at:round(t+1.85),step:'return',i:i+1,sum,checks,bodies,next:'check'});
	}
	const finish=at+(limit-start+1)*cycle;
	checks++;
	out.push({at:round(finish),step:'check',i:limit+1,sum,checks,bodies,next:'exit'});
	out.push({at:round(finish+.65),step:'exit',i:limit+1,sum,checks,bodies,next:null});
	return out;
}
export function stateAt(time,lesson) {
	if(!Number.isFinite(time)) throw new TypeError('time must be finite');
	const t=Math.max(0,Math.min(lesson.duration-1/lesson.fps,time));
	const chapter=lesson.chapters.filter(c=>c.at<=t).at(-1);
	const trace=buildTrace(lesson);
	const execution=trace.filter(e=>e.at<=t).at(-1)||{at:0,step:'ready',i:lesson.example.start,sum:lesson.example.sum,checks:0,bodies:0,next:'init'};
	const executionRound=execution.step==='check'?execution.checks:Math.max(1,execution.bodies);
	return{time:t,scene:chapter.id,chapter,execution,executionRound,subtitle:lesson.subtitles.find(([a,b])=>a<=t&&t<b)?.[2]||''};
}
