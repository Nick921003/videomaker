#!/usr/bin/env python3
"""把 videomaker 的影片工作流同步到實驗室 repo（cycu-bridgeai/video-skills）的 nick-dev 分支、nick/ 資料夾。

用法：
  python3 tools/video_skills_sync.py           # 複製＋掃描＋列出這次的變動，不 commit
  python3 tools/video_skills_sync.py --push    # 掃描通過才 commit 並推到 nick-dev

同一專案不同分支，和老師互相取用模組（2026-10-28 與老師確認）。只碰 nick/，老師的檔案一律不動。
nick/ 每次整個重建，videomaker 刪掉的東西這邊也會跟著消失；要放什麼只改下面的 INCLUDE。
掃描擋三種東西：金鑰、本機路徑與帳號、媒體檔與模型權重（老師 repo 的規則：生成的媒體、權重不進 git）。
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REMOTE = "git@github.com:cycu-bridgeai/video-skills.git"
BRANCH = "nick-dev"
FOLDER = "nick"
DEST_REPO = Path(os.environ.get("VIDEO_SKILLS_DIR", Path.home() / "projects" / "video-skills"))

# (videomaker 裡的路徑, nick/ 底下的路徑)；只放影片相關（手帳版、黑板版、F5 旁白），心智圖與工作台不放
INCLUDE = [
	("tts_f5", "tts_f5"),
	("video_engine", "video_engine"),
	("video_engine/out/vscode_printf_chalk", "examples/printf-chalk/film"),
	("docs/experiments/2026-10-22-vscode-printf/video/chalk-story", "examples/printf-chalk/story"),
	("docs/影片製作流程說明.md", "docs/影片製作流程說明.md"),
	("docs/images/影片製作流程.svg", "docs/images/影片製作流程.svg"),
	("docs/參考紀錄.md", "docs/參考紀錄.md"),
	("docs/PLATFORM_FLOW.md", "docs/PLATFORM_FLOW.md"),
	("tools/video_skills/README.md", "README.md"),
	("tools/video_skills/conftest.py", "conftest.py"),
	# 手帳版接工作台素材（素材庫、出處、教學計畫）時會用到；import 檢查抓出來的依賴
	("workbench/__init__.py", "workbench/__init__.py"),
	("workbench/library.py", "workbench/library.py"),
	("workbench/material.py", "workbench/material.py"),
	("workbench/teaching.py", "workbench/teaching.py"),
	("workbench/_runner.py", "workbench/_runner.py"),
	("workbench/artifacts.py", "workbench/artifacts.py"),
	("workbench/usage.py", "workbench/usage.py"),
	("studio/__init__.py", "studio/__init__.py"),
	("studio/teaching_plan.py", "studio/teaching_plan.py"),
	("studio/deck_contracts.py", "studio/deck_contracts.py"),
	("studio/deck_builder.py", "studio/deck_builder.py"),
	("studio/visual_components.py", "studio/visual_components.py"),
	("studio/mindmap.py", "studio/mindmap.py"),
	("studio/pptx_export.py", "studio/pptx_export.py"),
	("studio/key_points.py", "studio/key_points.py"),
	("workbench/key_points.py", "workbench/key_points.py"),
	("workbench/source_document.py", "workbench/source_document.py"),
] + [("tests/" + t, "tests/" + t) for t in (
	"__init__.py",
	"test_board_author.py", "test_board_build.py", "test_board_check.py", "test_board_compile.py", "test_board_compose.py",
	"test_board_narrate.py", "test_board_voice_identity.py",
	"test_tts_f5.py", "test_tts_pick.py", "test_f5_story.py", "test_storyboard.py", "test_sync_film.py", "test_narration_style.py",
	"test_layout.py", "test_render_slides.py", "test_render_video.py", "test_render_explainer.py",
)]

# 路徑任何一段是這些就不帶：產出、課程教材、快取、渲染結果、音檔
SKIP_DIRS = {"out", "materials", "__pycache__", "node_modules", "renders", "qa", "snapshots", "audio", ".git"}
SKIP_EXT = {".mp4", ".mp3", ".wav", ".m4a", ".webm", ".mov", ".safetensors", ".pt", ".pth", ".ckpt", ".pyc", ".tgz", ".zip"}
# paper_* 是另一種影片風格（紙本），目前沒用到，也會拉進 studio 的整套合約
SKIP_NAMES = {".env", "paper_contract.py", "paper_renderer.py", "paper_subtitles.py"}
MAX_BYTES = 5 * 1024 * 1024

SECRET = [re.compile(p) for p in (r"sk-[A-Za-z0-9_-]{20,}", r"AKIA[0-9A-Z]{16}", r"AIza[0-9A-Za-z_-]{35}", r"-----BEGIN [A-Z ]*PRIVATE KEY-----")]
PERSONAL = [re.compile(p) for p in (r"/mnt/[a-z]/", r"pjw92")]
TEXT_EXT = {".py", ".js", ".mjs", ".json", ".md", ".html", ".css", ".txt", ".sh", ".svg", ".srt", ".yml", ".yaml", ".toml", ".ini"}


def skipped(rel):
	"""rel：相對於某個 INCLUDE 來源的路徑。assets/img 是實機截圖：掃描看不到圖裡的字，可能有本機帳號，一律不帶"""
	p = Path(rel)
	return (bool(set(p.parts[:-1]) & SKIP_DIRS) or p.suffix.lower() in SKIP_EXT or p.name in SKIP_NAMES
		or "/".join(p.parts[:2]) == "assets/img")


def scan(text):
	"""回傳 [(種類, 命中字串)]"""
	hits = [("金鑰", m.group()) for r in SECRET for m in r.finditer(text)]
	return hits + [("本機路徑", m.group()) for r in PERSONAL for m in r.finditer(text)]


def plan(root=ROOT):
	"""[(來源檔, nick/ 底下的相對路徑)]，照 INCLUDE 順序；同一目的地以後面的為準"""
	out = {}
	for src, dst in INCLUDE:
		s = root / src
		if s.is_file():
			out[dst] = s
		elif s.is_dir():
			for f in sorted(s.rglob("*")):
				rel = f.relative_to(s)
				if f.is_file() and not skipped(rel):
					out[str(Path(dst) / rel)] = f
		else:
			raise SystemExit(f"INCLUDE 裡的 {src} 不存在")
	return sorted((f, d) for d, f in out.items())


def local_modules(root=ROOT):
	"""專案裡的 Python 模組：{模組名: [路徑]}。同名的都列（board 會把 video_engine 加進 sys.path，import synth 指的是 video_engine/synth.py）"""
	idx = {}
	for f in root.rglob("*.py"):
		rel = f.relative_to(root)
		if rel.parts[0] in {".venv", "prototypes", ".git", "node_modules"} or set(rel.parts) & SKIP_DIRS:
			continue
		names = [rel.stem] if rel.name != "__init__.py" else [rel.parent.name]
		if len(rel.parts) > 1 and rel.name != "__init__.py":
			names.append(".".join(rel.with_suffix("").parts))
		for n in names:
			idx.setdefault(n, []).append(f)
	return idx


def missing_imports(files, root=ROOT):
	"""要搬的 .py 用到、但清單沒帶的專案模組：[(nick/ 路徑, 模組名, 該補的來源檔)]。
	影片相關的東西有改動時，這個檢查讓清單漏掉的依賴不會安靜地搬過去才壞（使用者 2026-10-28 的規則）"""
	import ast
	have = {f.resolve() for f, _ in files}
	idx = local_modules(root)
	out = []
	for f, d in files:
		if f.suffix != ".py":
			continue
		try:
			tree = ast.parse(f.read_text(encoding="utf-8"))
		except SyntaxError:
			continue
		for node in ast.walk(tree):
			mods = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module] if isinstance(node, ast.ImportFrom) and node.module and not node.level else []
			for m in mods:
				parts = m.split(".")
				for k in range(len(parts), 0, -1):
					cand = idx.get(".".join(parts[:k])) or (idx.get(parts[k - 1]) if k == 1 else None)
					if cand:
						if not any(c.resolve() in have for c in cand):
							out.append((d, m, str(cand[0].relative_to(root))))
						break
	return sorted(set(out))


def problems(files):
	"""[(nick/ 路徑, 問題)]：太大、金鑰、本機路徑"""
	bad = []
	for f, d in files:
		if f.stat().st_size > MAX_BYTES:
			bad.append((d, f"檔案太大 {f.stat().st_size // 1024} KB"))
			continue
		if f.suffix.lower() in TEXT_EXT:
			for kind, hit in scan(f.read_text(encoding="utf-8", errors="ignore")):
				bad.append((d, f"{kind}：{hit}"))
	return bad


def git(*args, cwd=DEST_REPO, check=True):
	r = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
	if check and r.returncode:
		raise SystemExit(f"git {' '.join(args)} 失敗：{r.stderr.strip()}")
	return r.stdout.strip()


def prepare_repo():
	if not (DEST_REPO / ".git").exists():
		subprocess.run(["git", "clone", "-q", REMOTE, str(DEST_REPO)], check=True)
	git("fetch", "-q", "origin")
	if git("status", "--porcelain", "--", ".", f":!{FOLDER}"):
		raise SystemExit(f"{DEST_REPO} 在 {FOLDER}/ 以外有未提交的改動，先處理掉（這支腳本不碰老師的檔案）")
	if git("rev-parse", "--verify", "-q", BRANCH, check=False):
		git("checkout", "-q", BRANCH)
	elif git("ls-remote", "--heads", "origin", BRANCH):
		git("checkout", "-q", "-b", BRANCH, f"origin/{BRANCH}")
	else:
		git("checkout", "-q", "-b", BRANCH, "origin/main")
	if git("ls-remote", "--heads", "origin", BRANCH):
		git("pull", "-q", "--ff-only", "origin", BRANCH)


def main():
	ap = argparse.ArgumentParser()
	ap.add_argument("--push", action="store_true", help="掃描通過就 commit 並推到 nick-dev")
	a = ap.parse_args()

	files = plan()
	bad = problems(files) + [(d, f"用到 {m}，清單沒帶 {src}（補進 INCLUDE，或確定不需要就別帶用到它的檔）") for d, m, src in missing_imports(files)]
	if bad:
		print("擋下來了，這些要先在 videomaker 裡處理：")
		for d, why in bad:
			print(f"  {d}：{why}")
		return 1

	prepare_repo()
	dest = DEST_REPO / FOLDER
	shutil.rmtree(dest, ignore_errors=True)
	for f, d in files:
		(dest / d).parent.mkdir(parents=True, exist_ok=True)
		shutil.copy2(f, dest / d)
	head = git("rev-parse", "--short", "HEAD", cwd=ROOT)
	dirty = bool(git("status", "--porcelain", cwd=ROOT))
	json.dump({"source": "videomaker", "commit": head, "uncommitted_changes": dirty, "files": len(files)},
		open(dest / "SYNC.json", "w", encoding="utf-8"), ensure_ascii=False, indent="\t")

	git("add", "-A", FOLDER)
	stat = git("diff", "--cached", "--stat", "--", FOLDER)
	if not stat:
		print("沒有變動，不用推")
		return 0
	print(stat.splitlines()[-1])
	print("\n".join(git("diff", "--cached", "--name-status", "--", FOLDER).splitlines()[:80]))
	if not a.push:
		print(f"\n只整理好、還沒 commit。確認後加 --push。（{DEST_REPO}）")
		return 0
	msg = f"feat(nick): 同步 videomaker {head}{'（含未提交改動）' if dirty else ''}\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
	git("commit", "-q", "-m", msg)
	git("push", "-q", "-u", "origin", BRANCH)
	print(f"已推到 {BRANCH}：{git('rev-parse', '--short', 'HEAD')}")
	return 0


if __name__ == "__main__":
	sys.exit(main())
