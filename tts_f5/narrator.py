"""F5-TTS 旁白：一段文字進、一個 wav 出。

不認得任何教材格式，權重、參考音、seed 都由呼叫端傳入，可整包搬到別的專案。
做法依 F5 研究交接（給影片製作_F5旁白用法_2026-10-21.md）：文字轉寫＋破音字表、
依音節估語速、固定 seed。一段在長度上限內就整段一次送，讓模型自己處理段內停頓；
句與句分開生成會各自收尾降調，聽起來斷成兩截。超過上限才依句號、再依逗號切。
"""
import hashlib
import json
import os
import re
from pathlib import Path

import numpy as np
import soundfile as sf

from .tw_text_normalizer import normalize_tw_teaching_text, compute_target_duration_and_speed

SR = 24000
# 官方程式把參考音剪到 12 秒內，參考音＋生成音每段合計約 22 秒
SEGMENT_LIMIT = 22.0
CHUNK_GAP = 0.4
MIN_PEAK = 0.15
SIL_FLOOR = 0.015
MAX_GAP_SEC = 1.5
DEFAULT_POLYPHONE = Path(__file__).with_name("polyphone.json")
DEFAULT_PRONUNCIATION = Path(__file__).with_name("pronunciation.json")


def load_polyphone(path=DEFAULT_POLYPHONE):
	return json.load(open(path, encoding="utf-8"))["表"]


def load_pronunciation(path=DEFAULT_PRONUNCIATION):
	return json.load(open(path, encoding="utf-8"))["表"]


def _frames_rms(x):
	n = SR // 50
	frames = x[: len(x) // n * n].reshape(-1, n)
	return np.sqrt((frames ** 2).mean(1)), n


def trim(x):
	"""切頭尾靜音。用逐框 RMS，單點振幅會被雜訊騙"""
	rms, n = _frames_rms(x)
	active = np.where(rms > SIL_FLOOR)[0]
	if len(active) == 0:
		return x
	return x[max(0, active[0] * n - int(SR * 0.03)): min(len(x), (active[-1] + 1) * n + int(SR * 0.03))]


def analyse(x):
	"""回傳 (峰值, 講話秒數, 最長空白)"""
	rms, _ = _frames_rms(x)
	sil = (rms < rms.max() * 0.02) | (rms < SIL_FLOOR)
	longest = run = 0
	for s in sil:
		run = run + 1 if s else 0
		longest = max(longest, run)
	return float(np.abs(x).max()), float((~sil).sum() * 0.02), longest * 0.02


class F5Narrator:
	def __init__(self, ckpt, ref_wav, ref_text, *, seed=5, polyphone=None, pronunciation=None,
			cache_dir=None, device="cuda"):
		self.ckpt, self.ref_wav = Path(ckpt), Path(ref_wav)
		for p in (self.ckpt, self.ref_wav):
			if not p.exists():
				raise FileNotFoundError(p)
		self.seed, self.device = seed, device
		self.polyphone = load_polyphone() if polyphone is None else polyphone
		self.pronunciation = load_pronunciation() if pronunciation is None else pronunciation
		# pypinyin 的詞典是行程全域的；文字沒變、拼音變了，所以快取鍵要含這張表
		from pypinyin import load_phrases_dict
		load_phrases_dict({w: [[p] for p in py.split()] for w, py in self.pronunciation.items()})
		self._pron_tag = hashlib.sha1(json.dumps(self.pronunciation, sort_keys=True).encode("utf-8")).hexdigest()[:8]
		self.ref_sec = sf.info(str(self.ref_wav)).duration
		self.ref_text = self.spoken(ref_text)
		self.cache_dir = Path(cache_dir) if cache_dir else None
		self._tts = None

	def spoken(self, text):
		"""實際送進模型的文字；參考逐字稿也要走同一套"""
		s = normalize_tw_teaching_text(text)
		for k, v in self.polyphone.items():
			s = s.replace(k, v)
		return s

	def estimate(self, text):
		return compute_target_duration_and_speed(self.spoken(text), self.ref_sec, self.ref_text)[0]

	def chunks(self, text):
		"""能整段送就整段；太長才依句號切，句子還太長再依逗號切"""
		budget = SEGMENT_LIMIT - self.ref_sec
		if self.estimate(text) <= budget:
			return [text.strip()]
		out = []
		for sent in re.findall(r"[^。！？!?]+[。！？!?]?", text):
			for part in ([sent] if self.estimate(sent) <= budget else re.findall(r"[^，；,;]+[，；,;]?", sent)):
				if out and self.estimate(out[-1] + part) <= budget:
					out[-1] += part
				else:
					out.append(part)
		return [c.strip() for c in out if c.strip()]

	def _infer(self, spoken, speed, seed):
		if self._tts is None:
			from f5_tts.api import F5TTS
			self._tts = F5TTS(model="F5TTS_v1_Base", ckpt_file=str(self.ckpt), device=self.device)
		w, sr, _ = self._tts.infer(ref_file=str(self.ref_wav), ref_text=self.ref_text,
			gen_text=spoken, seed=seed, speed=speed)
		assert sr == SR, sr
		return np.asarray(w, dtype=np.float32)

	def chunk(self, text, seed=None):
		"""單一片段 → (音訊, 紀錄)。有 cache_dir 時同樣輸入不重算"""
		seed = self.seed if seed is None else seed
		spoken = self.spoken(text)
		_, speed = compute_target_duration_and_speed(spoken, self.ref_sec, self.ref_text)
		tag = f"{spoken}|{speed}|{seed}|{self.ckpt.name}|{self.ref_wav.name}|{self.ref_text}|{self._pron_tag}"
		digest = hashlib.sha1(tag.encode("utf-8")).hexdigest()[:12]
		cached = self.cache_dir / f"{digest}.wav" if self.cache_dir else None
		if cached and cached.exists():
			x, _ = sf.read(str(cached), dtype="float32")
		else:
			x = trim(self._infer(spoken, speed, seed))
			if cached:
				os.makedirs(self.cache_dir, exist_ok=True)
				sf.write(str(cached), x, SR, subtype="PCM_16")
		peak, voiced, gap = analyse(x)
		warnings = []
		if peak < MIN_PEAK:
			warnings.append(f"近乎無聲（峰值 {peak:.2f}）")
		if gap > MAX_GAP_SEC:
			warnings.append(f"中間空白 {gap:.1f}s")
		return x, {"text": text, "spoken": spoken, "seed": seed, "speed": speed, "digest": digest,
			"wav": str(cached) if cached else None, "duration": round(len(x) / SR, 3),
			"voiced": round(voiced, 3), "max_gap": round(gap, 2), "warnings": warnings}

	def speak(self, text, *, seeds=None, pad=(0.15, 0.25)):
		"""一段旁白 → (音訊, 片段紀錄)。seeds 可對個別片段（原文）指定別的 seed"""
		seeds = seeds or {}
		parts, recs = [], []
		for c in self.chunks(text):
			x, rec = self.chunk(c, seeds.get(c))
			parts += [x, np.zeros(int(SR * CHUNK_GAP), np.float32)]
			recs.append(rec)
		audio = np.concatenate([np.zeros(int(SR * pad[0]), np.float32), *parts[:-1],
			np.zeros(int(SR * pad[1]), np.float32)])
		return audio, recs
