"""Gemini TTS 配音（narrate.py --tts gemini）。

每句一次 API：回傳 24kHz 單聲道 16-bit PCM，裁掉頭尾靜音後墊上與 GPT-SoVITS 相同的前後留白，timing 計算不用改。
台灣口音提示沿用 ChineseExamAssistant 的寫法（AUDIO PROFILE／DIRECTOR'S NOTES／TRANSCRIPT 分段，模型不會把指示唸出來）。
花費依 usage_metadata 計：文字輸入＋音訊輸出 token。
"""
import struct

import numpy as np

import synth

SR = 24000
# 每百萬 token（US$）：文字輸入、音訊輸出。2027-01-01 起兩者都加倍
PRICE = {
	"gemini-3.8-flash-tts": (0.50, 9.00),
	"gemini-3.8-flash-lite-tts": (0.50, 6.00),
	"gemini-3.1-flash-tts-preview": (1.00, 20.00),
}
TAIWAN_ACCENT = (
	"A standard Taiwan Mandarin accent, like the voices used in official TOCFL listening recordings made in Taiwan. "
	"Educated, neutral and locally natural, with Taiwan Mandarin prosody and zh-TW phrasing. "
	"Retroflex initials are present but lightly realized, without heavy erhua or broadcaster-style curling."
)
PROFILE = (
	"A friendly programming teacher from Taiwan explaining to a first-year university student who is stuck. "
	"Warm, patient and clear, like sitting next to the student."
)


# 快取鑰匙的一部分：音訊讀法改過（2026-10-04 修 C2PA 區塊誤讀成雜訊），舊音檔不能沿用
AUDIO_FORMAT = "wav-chunks-v2"


def pcm_from_response(raw):
	"""回傳 (int16 陣列, 取樣率)。Gemini 回的是 WAV，data 區塊後面還接著 C2PA（AI 內容來源憑證）區塊——
	只能依 data 區塊宣告的長度取，不能砍固定 44 位元組就把剩下全當聲音，否則每句結尾多出 0.1 秒雜訊。"""
	if raw[:4] != b"RIFF" or raw[8:12] != b"WAVE":
		return np.frombuffer(raw[: len(raw) // 2 * 2], dtype="<i2").copy(), SR
	sr, pcm, i = SR, b"", 12
	while i + 8 <= len(raw):
		cid, size = raw[i:i + 4], struct.unpack("<I", raw[i + 4:i + 8])[0]
		body = raw[i + 8:i + 8 + size]
		if cid == b"fmt " and len(body) >= 8:
			sr = struct.unpack("<I", body[4:8])[0]
		elif cid == b"data":
			pcm = body
		i += 8 + size + (size & 1)
	return np.frombuffer(pcm[: len(pcm) // 2 * 2], dtype="<i2").copy(), sr


def prompt_for(text, speed):
	# 230 字／分實測太慢（13 句 112 秒，王老師同稿 72 秒）；王老師實測約 380 字／分
	pace = ("Speak at a natural, brisk teaching pace, about 330 Chinese characters per minute. Keep pauses between phrases short."
		if speed < 1 else "Speak at a lively conversational pace, about 380 Chinese characters per minute.")
	return "\n".join([
		"# AUDIO PROFILE", PROFILE, "",
		"# DIRECTOR'S NOTES", TAIWAN_ACCENT, pace,
		"Read the transcript exactly as written. Do not add, skip or repeat any words. Do not read these notes aloud.", "",
		"# TRANSCRIPT", text,
	])


def synth_gemini(text, out_wav, model="gemini-3.8-flash-tts", voice="Charon", speed=0.95):
	"""回傳 (info, ok, usage)。info 與 synth.synth_one 同欄位，narrate.py 可直接沿用。"""
	from google import genai
	from google.genai import types
	from scipy.io import wavfile

	client = genai.Client()
	resp = client.models.generate_content(
		model=model, contents=prompt_for(text, speed),
		config=types.GenerateContentConfig(
			response_modalities=["AUDIO"],
			speech_config=types.SpeechConfig(voice_config=types.VoiceConfig(
				prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=voice)))))
	u = resp.usage_metadata
	usage = {"model": model, "in": u.prompt_token_count or 0, "out": u.candidates_token_count or 0}
	price_in, price_out = PRICE.get(model, PRICE["gemini-3.8-flash-tts"])
	usage["usd"] = round(usage["in"] * price_in / 1e6 + usage["out"] * price_out / 1e6, 6)
	part = resp.candidates[0].content.parts[0] if resp.candidates and resp.candidates[0].content else None
	raw = part.inline_data.data if part is not None and part.inline_data is not None else b""
	data, sr = pcm_from_response(raw)
	if sr != SR:
		return {"total": 0.0, "voiced": 0.0, "problem": f"取樣率 {sr} 不是 {SR}"}, False, usage
	if not len(data):
		return {"total": 0.0, "voiced": 0.0, "problem": "Gemini 沒有回傳音訊"}, False, usage
	# 峰值壓到 0.9：Gemini 音量偏大，偶爾頂到滿格會破音
	peak0 = float(np.abs(data.astype(np.int32)).max()) or 1.0
	data = (data.astype(np.float32) * min(1.0, 0.9 * 32767 / peak0)).astype(np.int16)
	data = synth.trim_and_pad(data, SR)
	wavfile.write(out_wav, SR, data)
	total = len(data) / SR
	peak = float(np.abs(data).max()) / 32768.0
	ok = total > synth.PAD_START + synth.PAD_END + 0.3 and peak > 0.05
	return {"total": round(total, 3), "voiced": round(total - synth.PAD_START - synth.PAD_END, 3), "peak": round(peak, 3)}, ok, usage
