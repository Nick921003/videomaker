#!/usr/bin/env python3
"""投影片幾何：這一頁的哪塊區域給誰。

刻意是純函式——不 import PIL、不碰檔案、不畫任何東西。
所以版型選擇、容量計算與降級邏輯都能不產圖就測。
繪製與量測留在 render_slides.py。
"""

W, H = 1920, 1080

HEADER_BOX = (80, 60, 1840, 200)
CONTENT_BOX = (80, 240, 1840, 980)
CODE_BOX = (130, 280, 1790, 940)

TITLE_Y, SUB_Y = 80, 148
BULLET_Y0, BULLET_STEP = 310, 120
BULLET_SIZE = 38
CENTER_X = W // 2
BULLET_MAX_W = 1650
CODE_X, CODE_Y0, CODE_STEP = 170, 310, 42
CODE_SIZE = 28

FIG_ROW_H = 104
FIG_GAP = 26
FIG_CAPTION_H = 46


# 文字不貼卡片邊：BULLET_MAX_W 比內容卡內寬窄 110px，左右各 55px。
# 這個內距一直存在，只是以前藏在 fit_font 的寬度上限裡沒有名字
CARD_PAD_X = (CONTENT_BOX[2] - CONTENT_BOX[0] - BULLET_MAX_W) // 2

COL_GAP = 60
COL_PAD = 40
SPLIT_MAX_BULLETS = 6      # 半欄高 660，(6-1)*120+48 = 648 剛好放得下
STAGE_TEXT_RATIO = 0.4     # stage 文字帶最高占內容卡四成，其餘整片寬度留給 compare


def bullet_metrics(n):
	"""依條數決定行距與字級，跟 code_metrics 同一個形狀。

	7 條起 (n-1)*120+48 就超過內容卡的 740px 高。prompt 規則 4 只給 2–4 條、
	實測語料最多 3 條，但 schema 沒設上限——沒有這個函式的話，降級回 stack
	之後照樣爆版，只是換個地方爆"""
	avail = CONTENT_BOX[3] - CONTENT_BOX[1] - 48
	step = min(BULLET_STEP, avail // (n - 1)) if n > 1 else BULLET_STEP
	return step, max(16, min(BULLET_SIZE, round(step * BULLET_SIZE / BULLET_STEP)))


def count_bullets(slide):
	"""條列計數不分 hidden：base 與 full 兩張圖必須算出同一份版位，
	不然浮現動畫裁出來的框跟已經畫好的底圖對不齊。_stack、regions_for 的
	split 分支、render_slides 的繪製迴圈三處都要吃同一顆函式，才不會有人
	改了計數規則卻只改到其中一兩處"""
	return sum(1 for e in slide["elements"] if e["type"] in ("bullet", "callout"))


def rect(x0, y0, x1, y1):
	"""(x0,y0,x1,y1) → 跟 layout.json 的框同一種形狀，免得兩種座標慣例混用"""
	return {"x": x0, "y": y0, "w": x1 - x0, "h": y1 - y0}


def code_metrics(n):
	"""依行數決定行距與字級，保證 n 行一定關得進 CODE_BOX。

	prompt 允許 8–16 行，但固定 42px 行距在 15 行就剛好貼齊底線、16 行溢出 42px——
	差一行就爆版。15 行以內回傳原本的 42／28，既有教材的輸出逐像素不變
	"""
	step = min(CODE_STEP, (CODE_BOX[3] - CODE_Y0) // max(1, n))
	return step, max(12, min(CODE_SIZE, round(step * CODE_SIZE / CODE_STEP)))


def code_top(n, step=None):
	"""程式碼整塊在 CODE_BOX 內垂直置中的起始 y。

	舊版固定從 CODE_Y0 開始，10 行的話下方留 210px 死白。
	step 可選傳入：呼叫端（render_slide）多半已經先呼叫過 code_metrics(n) 拿字級，
	讓它把算好的 step 遞進來，這裡就不用同一個 n 再算一次 code_metrics
	"""
	if step is None:
		step, _ = code_metrics(n)
	return CODE_BOX[1] + max(0, (CODE_BOX[3] - CODE_BOX[1] - n * step) // 2)


def fig_vertical(el, width):
	"""boxes／steps 橫排要多寬、放不下就改直排的判準。draw_figure 跟 fig_height
	都要問同一題，答案搬來這裡兩邊才會一致——不然一個判橫排、一個算直排的高度，
	量出來的框跟實際畫的對不上"""
	# 直排是「窄欄」的作法（spec 3.1）：拿到整幅寬度時一律橫排，放不下就縮格寬——
	# 那是改直排之前一直在用的作法，5 項 steps 就是靠它畫出來的。
	# 少了這一條的話，_stack 拿滿版寬也會翻直排（760px 比整張卡片還高），
	# 合法輸入會一路降級到 raise
	if width >= CONTENT_BOX[2] - CONTENT_BOX[0]:
		return False
	n = max(1, len(el.get("items", [])))
	gap = FIG_GAP + (34 if el["kind"] == "steps" else 0)
	return 360 * n + gap * (n - 1) > width


def fig_height(el, width):
	"""先算高度，才能把整塊內容垂直置中，多圖時也靠它知道游標該往下挪多少。
	width 是這個 figure 實際拿到的畫布寬——boxes／steps 直排時比橫排高得多，
	沒有寬度就量不出真正會畫出來的高度"""
	cap = FIG_CAPTION_H if el.get("caption") else 0
	if el["kind"] == "compare":
		n = max(len(el.get("left", {}).get("items", [])),
			len(el.get("right", {}).get("items", [])))
		return 64 + n * 74 + cap
	n = max(1, len(el.get("items", [])))
	if fig_vertical(el, width):
		gap = FIG_GAP + (34 if el["kind"] == "steps" else 0)
		return FIG_ROW_H * n + gap * (n - 1) + cap
	return FIG_ROW_H + cap


LAYOUT_MODES = ("auto", "split", "center", "random")


def _roll(seed, slide_id):
	"""FNV-1a：純算術的確定性混合，不用 random 也不用 hashlib——
	layout.py 必須維持零 import。Python 內建的 hash 函式不能用：
	它對字串每個行程都不一樣（PYTHONHASHSEED），輸出會不可重現"""
	h = 2166136261 ^ (seed & 0xFFFFFFFF)
	for ch in slide_id:
		h = ((h ^ ord(ch)) * 16777619) & 0xFFFFFFFF
	return h


def pick_variant(slide, mode="auto", seed=0):
	"""版型由內容組成推導，不由教材指定，也不隨機。

	一堂課的序列固定是 compare → boxes → code → steps，四種內容配四種幾何，
	同一堂課內自然就不重複——不需要靠頁次輪替製造變化。
	image 與多張圖一律退回 stack：前者是寫死座標貼上去的、不吃區域，
	後者在只切出一塊圖區的版型裡會整個疊在一起。

	mode 參數支援四種選擇模式：
	- auto（預設）：現況，依內容組成推導
	- split：只要有單張圖就左右分欄（compare 也走分欄）
	- center：一律 stack 置中單欄
	- random：單張圖從 split / stage / stack 依種子抽樣，其餘結構維持原樣
	程式碼頁在任何模式下皆維持 code。
	"""
	if mode not in LAYOUT_MODES:
		raise ValueError(f"未知的版面模式：{mode!r}（支援：{', '.join(LAYOUT_MODES)}）")
	els = slide["elements"]
	if any(e["type"] == "code" for e in els):
		return "code"
	if mode == "center":
		return "stack"
	if any(e["type"] == "image" for e in els):
		return "stack"
	figs = [e for e in els if e["type"] == "figure"]
	if len(figs) != 1:
		return "stack"
	if mode == "split":
		return "split"
	if mode == "random":
		candidates = ("split", "stage", "stack")
		return candidates[_roll(seed, slide["id"]) % len(candidates)]
	return "stage" if figs[0]["kind"] == "compare" else "split"


def _stack(slide, index):
	"""現況版位原樣搬進區域框架。之後更花俏的版型判斷容量不夠時，
	降級也是呼叫這個函式，所以獨立出來而不是塞在 regions_for 裡"""
	els = slide["elements"]
	has_code = any(e["type"] == "code" for e in els)
	n_bullets = count_bullets(slide)
	figs = [e for e in els if e["type"] == "figure"]

	# 兩邊都要用 bullet_metrics 的自適應行距：render_slide 的繪製迴圈這一步
	# 這個 Task 起也改用同一個函式算 step，兩邊才會算出同一個值，
	# 只改一邊的話 7 條以上就分歧（738 vs 768）
	step, _ = bullet_metrics(n_bullets)
	bullets_h = (n_bullets - 1) * step + 48 if n_bullets else 0
	# 圖區永遠給滿版寬（CONTENT_BOX 內寬），跟下面 "figure" 那格算出來的區域一致
	figs_h = sum(fig_height(f, CONTENT_BOX[2] - CONTENT_BOX[0]) + 40 for f in figs)
	block_h = bullets_h + figs_h
	# stack 是最後一級版型，沒有更低可退：放不下就 raise，不要讓置中算式
	# 算出負的 top（曾經量到 -62，條列整條跑出畫布上緣，見 review I1）
	if block_h > CONTENT_BOX[3] - CONTENT_BOX[1]:
		raise ValueError(
			f"{slide['id']} 版位放不下：需要 {block_h}px，"
			f"CONTENT_BOX 只有 {CONTENT_BOX[3] - CONTENT_BOX[1]}px 可用"
		)
	top = (CONTENT_BOX[1] + (CONTENT_BOX[3] - CONTENT_BOX[1] - block_h) // 2
		if block_h else BULLET_Y0)

	return {
		"variant": "stack",
		# 左右各留 CARD_PAD_X，寬度才精確等於 BULLET_MAX_W。
		# 直接用 CONTENT_BOX 的內寬會是 1760，比舊的上限寬 110px，文字會貼到卡片邊
		"text": rect(CONTENT_BOX[0] + CARD_PAD_X, top,
			CONTENT_BOX[2] - CARD_PAD_X, top + bullets_h),
		"text_align": "center",
		"figure": rect(CONTENT_BOX[0], top + bullets_h + (40 if bullets_h else 0),
			CONTENT_BOX[2], CONTENT_BOX[3]) if figs else None,
		"code": rect(*CODE_BOX) if has_code else None,
	}


def _stage(slide, index):
	"""compare 圖走 stage 的唯一理由是它需要寬度：文字條列收窄成頂部一條帶狀區
	（至多內容卡四成高），圖拿下方剩餘部分的整片寬度，左右各留 COL_PAD——
	比 split 的半欄寬得多"""
	x0, y0, x1, y1 = CONTENT_BOX
	n_bullets = count_bullets(slide)
	step, _ = bullet_metrics(n_bullets)
	bullets_h = (n_bullets - 1) * step + 48 if n_bullets else 0
	cap = int((y1 - y0) * STAGE_TEXT_RATIO)
	if bullets_h > cap:
		# 條列塞不進封頂的帶狀區：render_slide 的繪製迴圈是線性遞增、不看
		# text_h 這個封頂，硬塞只會畫穿進 figure 區域。跟 split 超過
		# SPLIT_MAX_BULLETS 同一招，整頁降級回 _stack——它沒有封頂，
		# 繪製迴圈跟區域算式天生同源，不會有這種落差
		return _stack(slide, index)
	text_h = bullets_h
	# 跟 _stack 同款：文字帶與圖區之間留 40px 呼吸空間，沒文字就不留
	fig_top = y0 + text_h + (40 if text_h else 0)
	fig = next(e for e in slide["elements"] if e["type"] == "figure")
	if fig_height(fig, x1 - x0 - 2 * COL_PAD) > y1 - fig_top:
		# 文字帶沒超封頂，但圖本身放不進剩下的區域（見 review I2：只守條列不守圖）。
		# 走 _stack 不是為了買空間——條列沒被 40% 上限壓到時兩者容量相同——
		# 而是把「放不下」的終結權集中在 _stack 那一個 raise，不要散成兩處
		return _stack(slide, index)
	return {
		"variant": "stage",
		"text": rect(x0 + CARD_PAD_X, y0, x1 - CARD_PAD_X, y0 + text_h),
		"text_align": "center",      # 文字帶橫跨整幅，靠左對齊會很怪
		"figure": rect(x0 + COL_PAD, fig_top, x1 - COL_PAD, y1),
		"code": None,
	}


def regions_for(slide, index, mode="auto", seed=0):
	"""這一頁的哪塊區域給誰。index 是頁次（0 起算），split 用它決定文字放左還是放右。

	title／subtitle 不在回傳值裡——它們永遠畫在 HEADER_BOX，
	那是換頁交叉淡化時唯一不動的錨點。
	版型由 pick_variant 依內容組成與模式決定：split、stage 各有自己的幾何切法，
	容量算不下時都降級回 _stack；code 的區域跟 _stack 完全一樣（CODE_BOX 外框
	本來就不動，程式碼整塊的垂直置中另外交給 code_top，不影響這裡切出來的區域），
	只是把 variant 標籤覆蓋成 "code" 才對得上 pick_variant
	"""
	variant = pick_variant(slide, mode=mode, seed=seed)

	if variant == "split":
		n_bullets = count_bullets(slide)

		x0, y0, x1, y1 = CONTENT_BOX
		col_w = (x1 - x0 - 2 * COL_PAD - COL_GAP) // 2
		col_h = y1 - y0 - 2 * COL_PAD
		left = rect(x0 + COL_PAD, y0 + COL_PAD, x0 + COL_PAD + col_w, y1 - COL_PAD)
		right = rect(x0 + COL_PAD + col_w + COL_GAP, y0 + COL_PAD, x1 - COL_PAD, y1 - COL_PAD)
		fig = next(e for e in slide["elements"] if e["type"] == "figure")
		if n_bullets > SPLIT_MAX_BULLETS or fig_height(fig, col_w) > col_h:
			# 半欄放不下（條列太多，或圖本身太高）就退回整幅——_stack 給滿版寬
			# 天生放得下，見 review C1（5 項 steps 直排需要 760px，半欄只有 660px）
			return _stack(slide, index)
		text_left = index % 2 == 0           # 偶數頁文字在左，同課同 kind 的兩頁才不會長一樣
		return {
			"variant": "split",
			"text": left if text_left else right,
			"text_align": "left",
			"figure": right if text_left else left,
			"code": None,
		}

	if variant == "stage":
		return _stage(slide, index)

	r = _stack(slide, index)
	if variant == "code":
		r["variant"] = "code"
	return r
