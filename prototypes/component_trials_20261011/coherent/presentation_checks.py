"""Check measured text collisions and causal flow reveal on actual frames."""
def check_presentation(state):
	texts=state['texts']
	for i,a in enumerate(texts):
		for b in texts[i+1:]:
			if a['region']!=b['region']: continue
			w=min(a['x']+a['w'],b['x']+b['w'])-max(a['x'],b['x'])
			h=min(a['y']+a['h'],b['y']+b['h'])-max(a['y'],b['y'])
			assert w<=1 or h<=1, (state['time'],'text collision',a,b)
	if state['scene'] in ('flow','trace'):
		for text,at in [('成立',17),('不成立',29),('回到\n條件',18.3)]:
			if state['time']<at:
				assert not any(b['text']==text for b in texts), (state['time'],'premature flow label',text)
		if state['time']<29:
			assert not any(b['text']=='離開迴圈' and b['region']=='visual' for b in texts), (state['time'],'premature exit node')
		flow=state.get('flowPresentation')
		assert flow is not None, 'missing actual flow reveal measurements'
		for edge in flow['edges']:
			if edge['tip_alpha']>=.15:
				assert edge['draw_progress']>=.99, (state['time'],'arrow tip before path',edge)
		if state['time']<17: assert flow['labels']['yes']<.15
		if state['time']<18.3: assert flow['labels']['back']<.15
		if state['time']<29: assert flow['labels']['no']<.15
