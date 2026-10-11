"""共同固定 fixture 的語意適配與反向控制；不產生模型內容或配音。"""
import copy
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "video_engine/board"))
from tests.fixtures.teaching_quality import sample_plan
from compile import compile_scene, load_catalog
from build import build
from teaching_adapter import adapt_units


def main():
	plan = sample_plan()
	plan["units"] = [u for u in plan["units"] if u["visual"]["type"] in ("walkthrough","steps")]
	scene, sources = adapt_units(plan)
	trace = next(s for s in scene["scenes"] if s["id"] == "trace")
	assert trace["beats"][-1]["do"][-1]["text"] == "15"
	assert trace["beats"][-1]["do"][0]["line"] == 5
	assert len(sources) == 3
	assert [s["source_quotes"] for s in sources] == [u["source_quotes"] for u in plan["units"]]
	tl = compile_scene(scene, None, load_catalog())
	assert not tl["gaps"] and not tl["warnings"]
	out = HERE / "out"
	(out / "shared-fixture.scene.json").write_text(json.dumps(scene,ensure_ascii=False,indent="\t")+'\n')
	(out / "shared-fixture.sources.json").write_text(json.dumps(sources,ensure_ascii=False,indent="\t")+'\n')
	build(tl,str(out / "shared-fixture-player"))
	bad = copy.deepcopy(plan)
	bad["units"][1]["visual"]["states"][0]["line"] = 999
	try:
		adapt_units(bad)
	except ValueError:
		line_rejected = True
	else:
		raise AssertionError("無效行號未拒絕")
	try:
		adapt_units(sample_plan())
	except ValueError as exc:
		assert "尚未驗收" in str(exc)
		unsupported_rejected = True
	else:
		raise AssertionError("未驗收類型被靜默接受")
	result={"units":[u['id'] for u in plan['units']],"final_output":"15","last_focus_line":5,"source_quotes_preserved":True,"invalid_line_rejected":line_rejected,"unsupported_component_rejected":unsupported_rejected,"audio":"none; silent fixed fixture, timing estimated by compiler","duration_estimated":tl['duration']}
	(out / "shared-fixture-verification.json").write_text(json.dumps(result,ensure_ascii=False,indent="\t")+'\n')
	print(json.dumps(result,ensure_ascii=False))


if __name__ == "__main__":
	main()
