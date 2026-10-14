"""固定 C 教材的人工驗證基準；不呼叫模型，不修改正式素材庫。"""
from pathlib import Path
import json
import shutil
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from tests.fixtures.teaching_quality import MATERIAL, sample_plan
from studio.teaching_plan import canonical_plan
from workbench.library import Library
from workbench import run_slides, run_mindmap


def main():
	preview = Path('/tmp/videomaker-shared-components-preview-20261012/units')
	library = Library(preview)
	uid, _ = library.create_unit(MATERIAL, 'C 迴圈：流程與概念層次（人工驗證基準）')
	directory = library.unit_dir(uid)
	plan = sample_plan();plan['contract_version'] = '1.1'
	labels = ['程式走讀', '迴圈三要素', '累加例子', 'for 與 while', '有效範圍', '無窮迴圈', '閱讀檢查']
	for unit, label in zip(plan['units'], labels):
		unit.update(concept_label=label, parent_id='root', relation='主題', relation_quote=unit['source_quotes'][0])
	walk_quote = '走讀時分四步：宣告變數並把累加器歸零、寫出迴圈的三個部分、\n在主體裡累加、最後印出結果。'
	plan['units'][0].update(title='把程式分成四部分，逐步核對結果', question='程式走讀要先看哪幾部分？',
		explanation='這是閱讀程式的四個部分；主體會依條件重複累加，離開迴圈後才印出結果。',
		source_quotes=[walk_quote, plan['units'][2]['source_quotes'][0]], relation_quote=walk_quote,
		visual={'type':'pipeline','stages':[
			{'id':'declare','label':'宣告與歸零','note':'先宣告 n 與 sum，把累加器 sum 設成 0。'},
			{'id':'loop','label':'辨認迴圈三部分','note':'找到起始、繼續條件，以及每輪更新。'},
			{'id':'body','label':'走讀主體','note':'每一輪將當下的 i 加進 sum，按條件重複執行。'},
			{'id':'print','label':'印出結果','note':'離開迴圈後才印出結果；一加到五得到 15。'}]},
		details=[{'kind':'usage','text':'先找歸零，再核對迴圈、主體與輸出；這是閱讀順序，並非只執行一次的控制流程。','source_quote':walk_quote}],
		selection_reason='沿用 Board pipeline 階段資料展示走讀順序；實際重複由下一頁狀態走讀解釋。')
	plan['units'][2].update(parent_id='problem', relation='實際走讀', relation_quote=walk_quote)
	plan['units'][3].update(parent_id='three_parts', relation='寫法比較', relation_quote='for 把這三件事寫在同一行，一眼就看得完，適合次數已經知道的情況。\nwhile 把三件事拆開來寫，適合次數事先不知道的情況，')
	plan['units'][4].update(parent_id='three_parts', relation='條件邊界', relation_quote=plan['units'][4]['source_quotes'][0])
	plan['units'][5].update(parent_id='three_parts', relation='更新遺漏', relation_quote=plan['units'][5]['source_quotes'][0])
	plan = canonical_plan(plan, MATERIAL)
	calls = []
	def fixed_plan(*_):
		calls.append('人工基準，不是模型呼叫')
		return plan, {}
	# 清除本次隔離範例的舊快取，使重製能驗證同批共用一次規劃。
	for name in ('teaching_plan.json','teaching_plan.source.json'):
		(directory/name).unlink(missing_ok=True)
	for runner in (run_slides, run_mindmap):
		if runner.main([str(directory),'--quality','professional'], fixed_plan):
			raise RuntimeError('隔離產物生成失敗')
	assert len(calls) == 1, '兩種產物必須共用相同規劃'
	evidence = Path(__file__).resolve().parent
	for name in ('teaching_plan.json','material.md','slides','mindmap'):
		path = directory/name
		if path.is_dir(): shutil.copytree(path,evidence/name,dirs_exist_ok=True)
		else: shutil.copy2(path,evidence/name)
	# 固定分析規劃只是讓正式網站顯示成品，不觸發分析或模型。
	shutil.copy2(evidence/'analysis.json',directory/'plan.json')
	print(json.dumps({'unit':uid,'preview_root':str(preview),'fixture_calls':len(calls),'paid_calls':0},ensure_ascii=False))


if __name__ == '__main__': main()
