#!/usr/bin/env python3
"""動態時序常數：唯一來源。

渲染器要照它畫、編譯器要照它檢查時序衝突。兩邊各寫一份，改了一邊忘了另一邊，
lint 就會拿錯的基準去檢查對的畫面。每個數值為什麼是這個值，見 docs/MOTION_SPEC.md。
"""

HL_WIPE_MS = 380        # 螢光筆刷過
DIM_IN_MS = 420         # 程式碼區域壓暗淡入
UL_WIPE_MS = 330        # 馬克筆底線畫出
TRANS_MS = 420          # 換頁交叉淡化
CAMERA_MS = 600         # 鏡頭推近
EXIT_RATIO = 0.7        # 退場時長 = 進場的 70%

SCAN_MS = 520           # 掃描線行程
SCAN_DELAY_MS = 450     # 掃描線要等換頁淡化走完才起掃

STAGGER_MS = 60         # 依序進場的間隔
STAGGER_BUDGET_MS = 400 # 一組錯開的總預算
REVEAL_MS_SMALL = 260   # 條列項
REVEAL_MS_CARD = 320    # 卡片、示意圖方塊
REVEAL_MS_HERO = 420    # 標題、整張圖

MIN_GAP_MS = 80         # 兩個動態起點的最小間距，再近就讀成同時發生


def enter_ms(eff):
	"""效果的進場時長。lint 要用它反推退場窗，渲染器要用它算進度"""
	if eff["type"] == "laser":
		return UL_WIPE_MS
	if eff.get("style") == "code":
		return DIM_IN_MS
	return HL_WIPE_MS


def exit_ms(in_ms):
	return in_ms * EXIT_RATIO
