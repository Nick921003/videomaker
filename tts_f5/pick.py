"""多 seed 自動挑選：同一句合成好幾版，機器打分挑一版，全部不及格才標成可疑句給人看。

做法依 2026-10-28 調查：best-of-N 用 ASR 錯字率挑（BoN-TTS，arXiv 2607.08256），
但單一 ASR 會被它自己的偏好帶歪，所以用兩種（Whisper＋Paraformer）取平均；
句尾上揚依知覺研究約 2 個半音以上就像問句（Peters & Pfitzinger 2008），
中文有聲調不能套絕對門檻，所以分數只在同一句的候選之間比，門檻放寬到 3 個半音只擋明顯飄的。
不加總分，各指標各排一次名再相加（Borda），單一指標騙不了。
UTMOS 主要是英文訓練，中文只能當參考，先不用。

打分函式只吃 numpy；ASR 與音高套件（faster-whisper、funasr、opencc、praat-parselmouth）
只在 Colab 上裝，用到才 import，不進專案本體依賴。
"""
import re

import numpy as np

from .tw_text_normalizer import num_to_trad_zh

CER_MAX = 0.2
RISE_MAX = 3.0
GAP_MAX = 1.0
ASR_SR = 16000


def norm(s):
	"""比對用：數字轉中文、英文小寫、拿掉標點與空白（"F flush" 和 "fflush" 視為相同）"""
	s = re.sub(r"\d+(?:\.\d+)?", lambda m: num_to_trad_zh(m.group()), s)
	return re.sub(r"[^一-鿿a-z]", "", s.lower())


def tokens(s):
	"""中文轉帶聲調拼音、英文拆字母。比的是念法不是用字：Paraformer 用大陸語料訓練，
	「程式」常聽成「城市」、「裡」寫成「裏」，同音不同字不該算念錯（2026-10-28 VS Code 實驗）"""
	from pypinyin import Style, lazy_pinyin
	out = []
	for run in re.findall(r"[一-鿿]+|[a-z]+", norm(s)):
		out += lazy_pinyin(run, style=Style.TONE3, neutral_tone_with_five=True) if "一" <= run[0] <= "鿿" else list(run)
	return out


def cer(ref, hyp):
	"""讀音錯誤率（拼音／字母序列的編輯距離 ÷ 原稿長度）"""
	a, b = tokens(ref), tokens(hyp)
	if not a:
		return 0.0 if not b else 1.0
	prev = list(range(len(b) + 1))
	for i, ca in enumerate(a, 1):
		cur = [i]
		for j, cb in enumerate(b, 1):
			cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
		prev = cur
	return prev[-1] / len(a)


def rise_st(f0):
	"""最後一段有聲音（≥ 5 格）的音高變化，單位半音；前三分之一中位數 → 後三分之一中位數。f0 裡 0 代表無聲"""
	f0 = np.asarray(f0, dtype=float)
	idx = np.flatnonzero(f0 > 0)
	if len(idx) < 5:
		return 0.0
	# 從尾巴往回找連續有聲段，中間斷 2 格以內當作同一段
	end = start = idx[-1]
	for k in idx[::-1][1:]:
		if start - k > 3:
			break
		start = k
	seg = f0[start:end + 1]
	seg = seg[seg > 0][-30:]
	if len(seg) < 5:
		return 0.0
	n = max(1, len(seg) // 3)
	return float(12 * np.log2(np.median(seg[-n:]) / np.median(seg[:n])))


def choose(cands, question=False):
	"""cands：[{cer, rise, dev, gap}, ...]，第 0 個通常是預設 seed。
	回傳 (選中的索引, 是否可疑)。可疑＝沒有一個過門檻，此時仍從全部候選裡挑最好的"""
	def ok(c):
		return c["cer"] <= CER_MAX and c["gap"] <= GAP_MAX and (question or c["rise"] <= RISE_MAX)
	pool = [i for i, c in enumerate(cands) if ok(c)]
	suspicious = not pool
	pool = pool or list(range(len(cands)))
	keys = ["cer", "dev"] + ([] if question else ["rise"])
	score = {i: 0 for i in pool}
	# 名次＝比它好的候選有幾個；同分同名次，不然排在前面的 seed 白白多拿分
	for k in keys:
		for i in pool:
			score[i] += sum(1 for j in pool if cands[j][k] < cands[i][k])
	return min(pool, key=lambda i: (score[i], i)), suspicious


class Judge:
	"""兩種 ASR＋音高；模型第一次用到才載入（只在 Colab GPU 上用）"""

	def __init__(self, device="cuda"):
		self.device = device
		self._w = self._p = self._cc = None

	def _load(self):
		if self._w is None:
			from faster_whisper import WhisperModel
			from funasr import AutoModel
			from opencc import OpenCC
			self._w = WhisperModel("large-v3", device=self.device, compute_type="float16")
			self._p = AutoModel(model="paraformer-zh", disable_update=True)
			self._cc = OpenCC("s2t")

	def transcribe(self, x, sr):
		self._load()
		y = np.interp(np.arange(0, len(x), sr / ASR_SR), np.arange(len(x)), x).astype(np.float32)
		segs, _ = self._w.transcribe(y, language="zh", beam_size=5)
		w = self._cc.convert("".join(s.text for s in segs))
		p = self._cc.convert(self._p.generate(input=y)[0]["text"])
		return {"whisper": w, "paraformer": p}

	def f0(self, x, sr):
		import parselmouth
		return parselmouth.Sound(x.astype(np.float64), sr).to_pitch(time_step=0.01, pitch_floor=75, pitch_ceiling=500).selected_array["frequency"]

	def score(self, text, x, sr, voiced, gap):
		"""一個候選的分數；dev 由呼叫端在同一句候選之間補上（語速偏離中位數）"""
		hyp = self.transcribe(x, sr)
		return {"cer": float(np.mean([cer(text, h) for h in hyp.values()])), "rise": rise_st(self.f0(x, sr)),
			"rate": voiced / max(1, len(norm(text))), "gap": gap, "asr": hyp}
