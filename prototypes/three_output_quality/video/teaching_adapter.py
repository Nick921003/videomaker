"""共用 teaching_plan units → Board scene 的免費接點。

目前只接已驗證的 walkthrough / steps，其他元件明確報缺口。
時間由 compile_scene 或已核對音訊句界決定；本層不製造時間或像素。
"""
import json
import pathlib
import re
import sys


def adapt_units(plan):
	objects, scenes, source_map = [], [], []
	for unit in plan["units"]:
		uid = unit["id"]
		if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]*", uid):
			raise ValueError("unit id 無法作為 Board 語意 target")
		visual = unit["visual"]
		if visual["type"] == "walkthrough":
			lines, states = visual["lines"], visual["states"]
			if not lines or not states:
				raise ValueError(f"{uid} 沒有走讀資料")
			code_id, vars_id, output_id = f"{uid}_code", f"{uid}_vars", f"{uid}_output"
			first_vars = states[0].get("vars", [])
			names = [v["name"] for v in first_vars]
			if not names or len(names) != len(set(names)):
				raise ValueError(f"{uid} 需具名、唯一的變數")
			objects += [{"id":code_id,"type":"code","lines":lines,"caption":unit["title"]}, {"id":vars_id,"type":"vars","title":"目前變數","vars":[{"id":f"v{i}","name":v["name"],"value":str(v["value"])} for i,v in enumerate(first_vars)]}, {"id":output_id,"type":"output","label":"輸出"}]
			beats = []
			for state in states:
				if not 1 <= state["line"] <= len(lines) or [v["name"] for v in state.get("vars", [])] != names:
					raise ValueError(f"{uid} 行號或變數順序無效")
				acts = [{"act":"highlight","target":code_id,"line":state["line"]}]
				acts += [{"act":"set","target":f"{vars_id}:v{i}","value":str(v["value"]),"with":"prev"} for i,v in enumerate(state["vars"])]
				acts.append({"act":"set","target":output_id,"text":str(state.get("output", "")),"with":"prev"})
				beats.append({"say":state["explanation"],"do":acts})
			scenes.append({"id":uid,"title":unit["title"],"label":unit["role"],"layout":{"stack":[{"row":[code_id,vars_id]},output_id]},"beats":beats})
		elif visual["type"] == "steps":
			steps = visual.get("items", visual.get("steps"))
			if not steps or len(steps) > 4:
				raise ValueError(f"{uid} pipeline 支援 1–4 個具名步驟")
			pid = f"{uid}_pipeline"
			labels = [s if isinstance(s,str) else s["label"] for s in steps]
			objects.append({"id":pid,"type":"pipeline","title":unit["title"],"stages":[{"id":f"s{i}","label":label} for i,label in enumerate(labels)]})
			scenes.append({"id":uid,"title":unit["title"],"label":unit["role"],"layout":{"stack":[pid]},"beats":[{"say":label,"do":[{"act":"step","target":f"{pid}:s{i}"}]} for i,label in enumerate(labels)]})
		else:
			raise ValueError(f"{uid}: 尚未驗收的 video visual {visual['type']}")
		source_map.append({"unit_id":uid,"source_quotes":unit["source_quotes"],"selection_reason":unit["selection_reason"]})
	if not scenes:
		raise ValueError("教學規劃沒有單元")
	return {"version":1,"title":plan.get("title","教學走讀"),"tag":"共用教學規劃","corner_note":"未配音 fixture","objects":objects,"scenes":scenes}, source_map


if __name__ == "__main__":
	plan = json.loads(pathlib.Path(sys.argv[1]).read_text())
	scene, sources = adapt_units(plan)
	pathlib.Path(sys.argv[2]).write_text(json.dumps(scene,ensure_ascii=False,indent="\t")+"\n")
	pathlib.Path(sys.argv[2]+".sources.json").write_text(json.dumps(sources,ensure_ascii=False,indent="\t")+"\n")
