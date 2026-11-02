#!/usr/bin/env python3
"""黑板頁版面閘：開片子的 index.html，等字型載完，讀黑板通用轉接收集的 window.__boardProblems。

用法（要有 Playwright 的 Python，例：~/.local/share/pipx/venvs/webwright/bin/python）：
  board_check.py <影片專案>

放不下、黑板還不會畫的動作只會讓畫面安靜地少一塊，所以要開頁面讀出來。
__boardProblems 不存在代表轉接根本沒掛上（不是 starter 開的片、或腳本沒載到），一樣算失敗，不能當成沒問題。
"""
import os
import sys

READ = """() => ({
	problems: window.__boardProblems === undefined ? null : window.__boardProblems,
	boards: ((window.STORY || {}).boards || []).length,
	adapter: !!window.ChalkBoard,
})"""


def main(project):
	from playwright.sync_api import sync_playwright
	index = os.path.join(os.path.abspath(project), "index.html")
	if not os.path.exists(index):
		print("黑板頁版面閘：找不到 " + index)
		return 1
	errors = []
	with sync_playwright() as p:
		b = p.chromium.launch()
		page = b.new_page(viewport={"width": 1920, "height": 1080})
		page.on("pageerror", lambda e: errors.append(str(e)))
		page.goto("file://" + index, wait_until="load")
		page.evaluate("document.fonts.ready")
		got = page.evaluate(READ)
		b.close()
	bad = list(errors)
	if got["problems"] is None:
		bad.append("window.__boardProblems 不存在：黑板通用轉接沒有掛上")
	else:
		bad += [str(m) for m in got["problems"]]
	if got["boards"] and not got["adapter"]:
		bad.append("story 有 %d 頁黑板頁，但 lib/kit/board.chalk.js 沒載到" % got["boards"])
	print("黑板頁版面閘：%d 頁黑板頁，%s" % (got["boards"], "%d 個問題" % len(bad) if bad else "全部放得下"))
	for m in bad:
		print("  " + m)
	return 1 if bad else 0


if __name__ == "__main__":
	if len(sys.argv) != 2:
		sys.exit(__doc__)
	sys.exit(main(sys.argv[1]))
