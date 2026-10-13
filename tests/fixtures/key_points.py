"""人工撰寫的合格重點清單；只當測試基準，不冒充模型輸出。"""
from copy import deepcopy
import hashlib

from studio.teaching_plan import source_excerpts
from tests.fixtures.teaching_quality import MATERIAL


GOAL_1 = '能用 for 與 while 寫出正確的重複動作，知道兩者各適合什麼場合，'
GOAL_2 = '並且避開初學者最常踩的兩個坑：差一錯誤與無窮迴圈。'
CONCEPT = '迴圈說穿了只有三件事：從哪裡開始、什麼時候繼續、每一輪怎麼變。'
DIRECTION = '中間那個是「繼續的條件」不是「結束的條件」，這個方向很多人會想反。'
FOR = 'for 把這三件事寫在同一行，一眼就看得完，適合次數已經知道的情況。'
WHILE = 'while 把三件事拆開來寫，適合次數事先不知道的情況，'
EDGE = '因為題目要從一加到五，五本身要算進去，所以條件寫成小於等於。'
SOURCE_OF_OFF_BY_ONE = '同一個符號在兩種情境下不一樣，這正是差一錯誤最常見的來源。'
PITFALL = '用 while 的時候忘記在主體裡更新條件變數，條件就永遠成立，程式停不下來。'


def sample_key_points(structure='material'):
	inferred = structure == 'inferred'
	return {
		'contract_version': '1.0',
		'content_version': hashlib.sha256(MATERIAL.encode('utf-8')).hexdigest(),
		'title': 'C 語言迴圈基礎',
		'structure': structure,
		'status': 'needs_review' if inferred else 'ready',
		'objectives': [
			{'id': 'o1', 'text': '用 for 與 while 寫出正確的重複動作，並知道各適合什麼場合', 'inferred': inferred, 'sources': [GOAL_1]},
			{'id': 'o2', 'text': '避開差一錯誤與無窮迴圈兩個常見的坑', 'inferred': inferred, 'sources': [GOAL_2]},
		],
		'points': [
			{'id': 'three_parts', 'title': '迴圈三要素', 'question': 'for 後面括號裡為什麼用分號隔成三段？',
				'type': 'concept', 'objectives': ['o1'],
				'explanation': '括號裡三段各管一件事：從哪裡開始、什麼時候繼續、每一輪怎麼變。中間那段是「繼續的條件」，成立才會再跑一輪，不是「結束的條件」。',
				'example': {'kind': 'code', 'content': 'for (int i = 1; i <= n; i++) {\n    sum += i;\n}', 'language': 'c'},
				'misconceptions': [{'wrong': '把中間的條件當成迴圈結束的條件', 'why': '條件成立時迴圈會繼續，不成立才離開', 'correct': '把中間那段讀成「還要不要再跑一輪」'}],
				'parent_id': None, 'sources': [CONCEPT, DIRECTION]},
			{'id': 'choose', 'title': 'for 與 while', 'question': '同樣是重複，什麼時候該改用 while 而不是 for？',
				'type': 'compare', 'objectives': ['o1'],
				'explanation': 'for 把三件事寫在同一行，適合次數已經知道的情況；while 把三件事拆開寫，適合等到某件事發生才停，例如讀到檔案結束或使用者輸入零。',
				'example': None, 'misconceptions': [], 'parent_id': 'three_parts', 'sources': [FOR, WHILE]},
			{'id': 'boundary', 'title': '差一錯誤', 'question': '一加到五時，條件為什麼寫 i <= 5 而不是 i < 5？',
				'type': 'mistake', 'objectives': ['o2'],
				'explanation': '因為五本身要算進去。若改成走訪長度為五的陣列，索引是零到四，就要用小於。同一個符號在兩種情境下不一樣，這是差一錯誤最常見的來源。',
				'example': None,
				'misconceptions': [{'wrong': '不管什麼情況都寫小於等於', 'why': '陣列索引從零開始，長度五只到四', 'correct': '先確認範圍的終點有沒有包含，再選符號'}],
				'parent_id': None, 'sources': [EDGE, SOURCE_OF_OFF_BY_ONE]},
			{'id': 'infinite', 'title': '無窮迴圈', 'question': '程式跑起來停不下來、游標一直閃，是哪裡漏了？',
				'type': 'mistake', 'objectives': ['o2'],
				'explanation': '多半是用 while 時忘了在主體裡更新條件變數，條件永遠成立。for 把更新寫在括號裡，比較不容易漏。',
				'example': None,
				'misconceptions': [{'wrong': 'while 主體裡沒有改變條件用到的變數', 'why': '條件每次判斷結果都一樣，永遠成立', 'correct': '在主體裡更新條件變數，讓它朝結束前進'}],
				'parent_id': None, 'sources': [PITFALL]},
		],
	}


def by_excerpt_ids(output):
	"""把原文引用換成片段 id，模擬模型只回傳代號。"""
	excerpts = source_excerpts(MATERIAL)
	def ref(quote):
		normalized = ' '.join(quote.split())
		return next(item['id'] for item in excerpts if normalized in ' '.join(item['text'].split()))
	for objective in output['objectives']:
		objective['sources'] = [ref(quote) for quote in objective['sources']]
	for point in output['points']:
		point['sources'] = [ref(quote) for quote in point['sources']]
	return output


def model_output():
	"""模型會回傳的形狀：來源是片段代號；沒有版本、結構、狀態欄位；無上層用空字串，無例子用 kind=none。"""
	value = deepcopy(sample_key_points())
	for objective in value['objectives']:
		objective.pop('inferred')
	for point in value['points']:
		point['parent_id'] = point['parent_id'] or ''
		point['example'] = point['example'] or {'kind': 'none', 'content': '', 'language': ''}
	return by_excerpt_ids({'title': value['title'], 'objectives': value['objectives'], 'points': value['points']})
