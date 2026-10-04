import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "video_engine", "board"))

import check as BK


def box(owner, role, x, y, w, h, **kw):
	return {"owner": owner, "role": role, "x": x, "y": y, "w": w, "h": h, "alpha": 1, **kw}


def frame(*boxes):
	owners = {b["owner"] for b in boxes}
	return {"errors": [], "moving": False, "camera": {"settled": True, "z": 1}, "scale": 1, "scene": 0,
		"boxes": list(boxes), "alpha": {o: 1 for o in owners}, "members": sorted(owners)}


OBJ = {"src", "mid", "exe", "list", "out"}
SRC = box("src", "text", 700, 200, 500, 60, value="hello.c")
MID = box("mid", "text", 760, 330, 400, 60, value="GCC＝編譯器")
EXE = box("exe", "text", 650, 460, 600, 60, value="hello.exe")


class TestMarks(unittest.TestCase):
	def test_箭頭穿過第三個物件的字要退件(self):
		arrow = box("mark", "stroke", 950, 276, 1, 168, pts=[[950, 276], [950, 444]], skip=[SRC, EXE], kind="箭頭", target="src→exe")
		problems = BK.check_frame(frame(SRC, MID, EXE, arrow), OBJ, ["s1"])
		self.assertTrue(any("穿過" in p and "mid" in p for p in problems), problems)

	def test_繞道的箭頭與兩端本身不算穿過(self):
		arrow = box("mark", "stroke", 1250, 230, 70, 260, pts=[[1212, 230], [1320, 230], [1320, 490], [1262, 490]], skip=[SRC, EXE], kind="箭頭", target="src→exe")
		self.assertEqual(BK.check_frame(frame(SRC, MID, EXE, arrow), OBJ, ["s1"]), [])

	def test_圈壓到相鄰列的框要退件(self):
		r0 = box("list", "panel", 600, 300, 600, 74)
		r1 = box("list", "panel", 600, 388, 600, 74)
		ring = box("mark", "stroke", 578, 282, 644, 110, pts=[[900, 282], [1222, 337], [900, 392], [578, 337], [900, 282]], skip=[r0], kind="圈", target="list:r0")
		problems = BK.check_frame(frame(r0, r1, ring), OBJ, ["s1"])
		self.assertTrue(any("穿過" in p and "圈" in p for p in problems), problems)

	def test_鄰行的字只是貼到目標框邊仍要檢查(self):
		line1 = box("out", "text", 600, 300, 500, 52, value="gcc --version")
		line2 = box("out", "text", 600, 353, 500, 44, value="gcc 13.2.0")
		target = {"x": 580, "y": 350, "w": 800, "h": 50}
		ring = box("mark", "stroke", 570, 330, 820, 90, pts=[[980, 330], [1390, 375], [980, 420], [570, 375], [980, 330]], skip=[target], kind="圈", target="out:line2")
		problems = BK.check_frame(frame(line1, line2, ring), OBJ, ["s1"])
		self.assertTrue(any("gcc --version" in p for p in problems), problems)
		self.assertFalse(any("13.2.0" in p for p in problems), problems)

	def test_標記座標無效要回報而不是崩潰(self):
		ring = box("mark", "stroke", 0, 0, 0, 0, pts=[[None, None], [None, None]], skip=[], kind="圈", target="mid")
		problems = BK.check_frame(frame(MID, ring), OBJ, ["s1"])
		self.assertTrue(any("座標無效" in p for p in problems), problems)

	def test_鏡頭推近時標註檢查照跑(self):
		arrow = box("mark", "stroke", 950, 276, 1, 168, pts=[[950, 276], [950, 444]], skip=[SRC, EXE], kind="箭頭", target="src→exe")
		f = frame(SRC, MID, EXE, arrow)
		f["camera"]["z"] = 1.5
		self.assertTrue(any("穿過" in p for p in BK.check_frame(f, OBJ, ["s1"])))

	def test_物件超出鏡頭要退件(self):
		far = box("mid", "text", 1800, 300, 400, 60, value="超出去的字")
		problems = BK.check_frame(frame(far), OBJ, ["s1"])
		self.assertTrue(any("超出鏡頭視窗" in p for p in problems), problems)

	def test_斜線穿過框角也抓得到(self):
		line = box("mark", "stroke", 600, 175, 320, 320, pts=[[600, 495], [920, 175]], skip=[], kind="箭頭", target="x→y")
		problems = BK.check_frame(frame(MID, line), OBJ, ["s1"])
		self.assertTrue(any("穿過" in p and "mid" in p for p in problems), problems)

	def test_標註文字蓋到物件的字要退件(self):
		label = box("mark", "mark-label", 900, 340, 120, 37, value="gcc 編譯")
		problems = BK.check_frame(frame(SRC, MID, EXE, label), OBJ, ["s1"])
		self.assertTrue(any("標註文字" in p and "mid" in p for p in problems), problems)

	def test_標註文字放在空白處不退件(self):
		label = box("mark", "mark-label", 1340, 340, 120, 37, value="gcc 編譯")
		self.assertEqual(BK.check_frame(frame(SRC, MID, EXE, label), OBJ, ["s1"]), [])

	def test_同一物件的小標蓋到內文要退件(self):
		cap = box("out", "label", 320, 500, 200, 37, value="這一站在做的事")
		body = box("out", "text", 340, 510, 600, 100, value="④ 連結")
		problems = BK.check_frame(frame(cap, body), OBJ, ["s1"])
		self.assertTrue(any("互疊" in p for p in problems), problems)


if __name__ == "__main__":
	unittest.main()
