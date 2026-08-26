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

FIG_MAX_W = 1560
FIG_ROW_H = 104
FIG_GAP = 26
FIG_CAPTION_H = 46


# 文字不貼卡片邊：BULLET_MAX_W 比內容卡內寬窄 110px，左右各 55px。
# 這個內距一直存在，只是以前藏在 fit_font 的寬度上限裡沒有名字
CARD_PAD_X = (CONTENT_BOX[2] - CONTENT_BOX[0] - BULLET_MAX_W) // 2


def bullet_metrics(n):
	"""依條數決定行距與字級，跟 code_metrics 同一個形狀。

	7 條起 (n-1)*120+48 就超過內容卡的 740px 高。prompt 規則 4 只給 2–4 條、
	實測語料最多 3 條，但 schema 沒設上限——沒有這個函式的話，降級回 stack
	之後照樣爆版，只是換個地方爆"""
	avail = CONTENT_BOX[3] - CONTENT_BOX[1] - 48
	step = min(BULLET_STEP, avail // (n - 1)) if n > 1 else BULLET_STEP
	return step, max(16, min(BULLET_SIZE, round(step * BULLET_SIZE / BULLET_STEP)))


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


def fig_height(el):
	"""先算高度，才能把整塊內容垂直置中。從 render_slides.py 搬過來——這是純算式，不碰 PIL"""
	cap = FIG_CAPTION_H if el.get("caption") else 0
	if el["kind"] == "compare":
		n = max(len(el.get("left", {}).get("items", [])),
			len(el.get("right", {}).get("items", [])))
		return 64 + n * 74 + cap
	return FIG_ROW_H + cap


def _stack(slide, index):
	"""現況版位原樣搬進區域框架。之後更花俏的版型判斷容量不夠時，
	降級也是呼叫這個函式，所以獨立出來而不是塞在 regions_for 裡"""
	els = slide["elements"]
	has_code = any(e["type"] == "code" for e in els)
	# 條列計數不分 hidden：base 與 full 必須算出同一份版位，
	# 不然浮現動畫裁出來的框跟已經畫好的底圖對不齊
	n_bullets = sum(1 for e in els if e["type"] in ("bullet", "callout"))
	figs = [e for e in els if e["type"] == "figure"]

	# 這裡刻意用固定的 BULLET_STEP，不用 bullet_metrics。
	# render_slide 的繪製迴圈這一步也是以 BULLET_STEP 遞增，兩邊必須算同一個值，
	# 否則 7 條以上就分歧（738 vs 768）。自適應行距由後續 Task 在兩處同時換上
	bullets_h = (n_bullets - 1) * BULLET_STEP + 48 if n_bullets else 0
	figs_h = sum(fig_height(f) + 40 for f in figs)
	block_h = bullets_h + figs_h
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


def regions_for(slide, index):
	"""這一頁的哪塊區域給誰。index 是頁次（0 起算），供之後需要鏡像的版型使用。

	title／subtitle 不在回傳值裡——它們永遠畫在 HEADER_BOX，
	那是換頁交叉淡化時唯一不動的錨點。
	目前只有 stack 一種版型；之後版型選擇邏輯會插在這裡，
	容量算不下時降級也回頭呼叫 _stack
	"""
	return _stack(slide, index)
