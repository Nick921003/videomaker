"""固定教學資料；人工基準，不冒充模型生成成果。"""
from pathlib import Path


MATERIAL = Path(__file__).resolve().parents[2].joinpath('video_engine/materials/c_loop.md').read_text()


def sample_plan():
	import hashlib
	quotes = {
		'hook': '要把一到一百加起來，用手寫一百行加法沒有人受得了。',
		'concept': '迴圈說穿了只有三件事：從哪裡開始、什麼時候繼續、每一輪怎麼變。',
		'for': 'for 把這三件事寫在同一行，一眼就看得完，適合次數已經知道的情況。',
		'while': 'while 把三件事拆開來寫，適合次數事先不知道的情況，\n例如一直讀到檔案結束、或是等使用者輸入零才停。',
		'code': 'int n = 5, sum = 0;\n    for (int i = 1; i <= n; i++) {\n        sum += i;\n    }',
		'edge': '因為題目要從一加到五，五本身要算進去，所以條件寫成小於等於。',
		'array': '但如果今天是走訪一個長度為五的陣列，索引是從零開始、到四結束，\n那裡就要用小於而不是小於等於。',
		'pitfall': '用 while 的時候忘記在主體裡更新條件變數，條件就永遠成立，程式停不下來。',
	}
	def unit(id, role, title, question, explanation, visual, keys, details):
		return {'id': id, 'role': role, 'title': title, 'question': question,
			'explanation': explanation, 'source_quotes': [quotes[key] for key in keys],
			'visual': visual, 'details': [{'kind': kind, 'text': text, 'source_quote': quotes[key]}
				for kind, text, key in details], 'selection_reason': {
				'concept': '將三種責任分開，幫助辨認各自作用。', 'walkthrough': '同步顯示執行位置、變數和結果。',
				'compare': '兩種情境並排，讓差異直接可見。', 'steps': '先後順序是理解的關鍵。',
				'bullets': '整理已解釋過的重點供回顧。'}[visual['type']]}
	units = [
		unit('problem','hook','一百次加法，怎樣少寫又算對？','重複的工作一定要重複寫嗎？',
			'迴圈讓同一個動作反覆執行。接下來要決定從哪裡開始、何時繼續，以及每次如何前進。',
			{'type':'steps','items':['找出要重複的動作','決定開始與繼續條件','確認每輪更新與最後結果']},['hook','concept'],
			[('example','把一到一百加起來：重複的是加法，不必手寫一百行。','hook')]),
		unit('three_parts','concept','開始、繼續、更新，各管一件事','中間的條件是繼續還是停止？',
			'條件成立就繼續執行；不成立才離開。更新讓下一輪有機會接近結束。',
			{'type':'concept','center':'迴圈的三種責任','items':[{'title':'開始','text':'設定第一輪的起點。'},{'title':'繼續條件','text':'成立才進入下一輪。'},{'title':'更新','text':'改變狀態，準備再判斷。'}]},['concept'],
			[('meaning','三個部分分別決定起點、能否繼續，以及每輪的變化。','concept'),('usage','讀迴圈時先找到這三個部分，避免把繼續條件看成停止條件。','concept')]),
		unit('trace','example','跟著程式，看到累加值怎麼變','一加到五，sum 是怎樣得到十五？',
			'累加器先歸零；每輪把當下的 i 加進 sum，再更新 i。用狀態走讀核對每一步。',
			{'type':'walkthrough','language':'C','lines':['int n = 5, sum = 0;','for (int i = 1; i <= n; i++) {','    sum += i;','}','printf("%d", sum);'],
			 'states':[{'label':f'第{i}輪','line':3,'vars':[{'name':'i','value':str(i)},{'name':'sum','value':str(i*(i+1)//2)}],
				'output':'尚未印出','explanation':f'{i*(i-1)//2} + {i} = {i*(i+1)//2}，接著更新 i。'} for i in range(1,6)] +
				[{'label':'離開迴圈','line':5,'vars':[{'name':'i','value':'條件不成立'},{'name':'sum','value':'15'}],'output':'15','explanation':'五已經加進去；離開迴圈後才印出結果。'}]},['code','edge'],
			[('example','第一輪：sum 從 0 加上 1，變成 1；第二輪再加 2，變成 3。','code'),('usage','每一步同時對照程式行、i 和 sum，確認有沒有少跑一輪。','code')]),
		unit('choose','concept','已知次數用 for，未知次數看 while','怎麼選擇 for 或 while？',
			'兩者都要照顧開始、條件與更新。選擇依情境：次數已知，或需要等某個事件發生。',
			{'type':'compare','left':{'title':'for：次數已知','items':['三個部分集中在同一行','例如一加到五']},'right':{'title':'while：次數未知','items':['三個部分分開安排','例如等輸入零才停止']}},['for','while','code'],
			[('usage','次數已知優先考慮 for；等使用者輸入零等未知次數的情境可用 while。','while')]),
		unit('boundary','pitfall','五要不要算進去？先看情境','小於與小於等於，哪一個才對？',
			'先判斷有效範圍，再選符號。加到五要包含五；長度五的陣列只有索引零到四。',
			{'type':'compare','left':{'title':'一加到五','items':['有效值：1、2、3、4、5','條件包含五：i <= 5']},'right':{'title':'長度五的陣列','items':['有效索引：0、1、2、3、4','條件排除五：i < 5']}},['edge','array'],
			[('pitfall','不能只背一個符號：總和範圍與陣列索引的終點不同。','array'),('example','一加到五要包含五；陣列長度五時，索引五已經超出範圍。','edge')]),
		unit('termination','pitfall','狀態不更新，迴圈就可能停不下來','條件一直成立時，什麼會改變它？',
			'while 的更新寫在主體裡，容易漏掉。若條件變數不變，下一次判斷還是成立。',
			{'type':'steps','items':['檢查條件使用的變數','找到主體裡的更新','確認更新後能讓條件不成立']},['pitfall'],
			[('pitfall','忘記更新條件變數，會讓 while 的條件永遠成立。','pitfall')]),
		unit('recap','summary','先找三要素，再驗範圍與終止','你能解釋每一輪為什麼會繼續嗎？',
			'用相同的檢查順序閱讀 for 與 while；核對邊界，再確認狀態朝結束前進。',
			{'type':'bullets','items':['起點在哪裡？','條件成立代表什麼？','每輪哪個值會改變？','最後一個值該不該包含？']},['concept','edge','pitfall'],
			[('meaning','開始、繼續條件與更新共同決定重複執行。','concept')]),
	]
	return {'contract_version':'1.0','title':'C 迴圈：看懂每一輪','content_version':hashlib.sha256(MATERIAL.encode()).hexdigest(),
		'style':'professional','mindmap_layout':'progressive','units':units}
