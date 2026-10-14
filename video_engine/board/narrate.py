#!/usr/bin/env python3
"""scene.json → 配音 master.wav＋timing.json（每句實測起訖）＋timing.identity.json。

用法：.venv/bin/python video_engine/board/narrate.py <scene.json> <輸出目錄> [--speed 0.95] [--tts sovits|gemini]

每句唸 `spoken`（沒有就唸 `say`），以文字＋聲音配置身份快取：插句或移序沿用音檔。
需要 GPT-SoVITS 服務（.env 的 TTS_API_URL）。合成與驗收重試沿用 synth.py。
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys

import numpy as np
from scipy.io import wavfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)

import gemini_tts
import synth
from asr_check import CHECK_VERSION
from compile import BEAT_GAP, LEAD_IN, SCENE_GAP, file_digest, speech_digest, speech_flags

# 「G C C」這種空白隔開的字母，或 GCC、PATH 這類全大寫縮寫
SPELLED = re.compile(r"(?<![A-Za-z])(?:[A-Za-z] ){1,}[A-Za-z](?![A-Za-z])|(?<![A-Za-z])[A-Z]{2,6}(?![A-Za-z])")
# 中文句中夾英文單字，王老師模型會唸糊並連帶吃掉後面的字（2026-10-04 實測：path 之後的「這份」漏念）
ENGLISH = re.compile(r"[A-Za-z]+")
ENGLISH_OK = {"Windows"}  # 實測唸得清楚的才列入
ASR_PYTHON = os.environ.get("ASR_PYTHON", os.path.expanduser("~/projects/GPT-SoVITS/.venv/bin/python"))
MAX_ROUNDS = 3


def speech_problems(text):
	if SPELLED.search(text):
		return f"逐字母縮寫 {SPELLED.findall(text)}"
	words = [w for w in ENGLISH.findall(text) if w not in ENGLISH_OK]
	return f"夾英文單字 {words}" if words else None


def voice_key(speed):
	"""快取鑰匙含聲音條件：換參考音訊、參考文字、服務或模型，舊音檔就不能沿用。"""
	with open(synth.REF_AUDIO, "rb") as f:
		ref = hashlib.sha1(f.read()).hexdigest()[:12]
	return f"{speed}|{ref}|{synth.REF_TEXT}|{synth.API_URL}|{os.environ.get('TTS_VOICE_ID', '')}"


def audio_signature(wav):
	try:
		rate, data = wavfile.read(wav)
	except (OSError, ValueError, EOFError) as error:
		raise ValueError("快取音檔 WAV 格式無效") from error
	if rate <= 0 or data.ndim != 1 or len(data) == 0:
		raise ValueError("快取音檔必須是有效的單聲道 WAV")
	return {"audio_sha256": file_digest(wav), "wav_format": {
		"sample_rate": rate, "channels": 1, "dtype": str(data.dtype), "frames": len(data)}}


def verified_cache(hit, proof, text, voice_digest, wav):
	"""只有音檔仍是先前驗收的內容，舊 ASR 才能沿用；無摘要的舊檔須重新辨識。"""
	if hit.get("text") != text:
		raise ValueError("快取旁白文字身份不符")
	expected_speech = speech_digest(text, voice_digest)
	for record in (hit, proof or {}):
		if "voice_digest" in record and record["voice_digest"] != voice_digest:
			raise ValueError("快取聲音身份不符")
		if "speech_digest" in record and record["speech_digest"] != expected_speech:
			raise ValueError("快取實際發音身份不符")
	if proof and proof.get("text") != text:
		raise ValueError("快取與前次 timing 旁白身份不符")
	actual = audio_signature(wav)
	bound = False
	for record in (hit, proof or {}):
		if "audio_sha256" in record:
			if record["audio_sha256"] != actual["audio_sha256"]:
				raise ValueError("快取音檔 digest 不符；請用 --redo 明確重配此句")
			bound = bound or (record.get("text") == text and record.get("voice_digest") == voice_digest
				and record.get("speech_digest") == expected_speech)
		if "wav_format" in record and record["wav_format"] != actual["wav_format"]:
			raise ValueError("快取 WAV 格式與先前紀錄不符")
	return {**hit, **actual, "voice_digest": voice_digest, "speech_digest": expected_speech}, bound


def synth_keep_raw(text, speed, wav, raw_prefix):
	"""synth_one 會裁掉頭尾低電平；裁切前的原始音訊另存，追查句尾漏字時才分得出是模型還是裁切。"""
	raws, orig = [], synth.trim_and_pad

	def capture(data, sr):
		raws.append((sr, data.copy()))
		return orig(data, sr)
	synth.trim_and_pad = capture
	try:
		info, ok = synth.synth_one(text, speed, wav)
	finally:
		synth.trim_and_pad = orig
	for i, (sr, data) in enumerate(raws):
		wavfile.write(f"{raw_prefix}.raw{i}.wav", sr, data)
	return info, ok


def asr_check(jobs, out_dir):
	"""另一個 venv 跑語音辨識（GPU 留給 TTS），回傳 {wav: 結果}。"""
	jobs_path, res_path = os.path.join(out_dir, "asr_jobs.json"), os.path.join(out_dir, "asr_result.json")
	with open(jobs_path, "w", encoding="utf-8") as f:
		json.dump(jobs, f, ensure_ascii=False)
	subprocess.run([ASR_PYTHON, os.path.join(HERE, "asr_check.py"), jobs_path, res_path], check=True,
		env={**os.environ, "CUDA_VISIBLE_DEVICES": ""})
	with open(res_path, encoding="utf-8") as f:
		return {r["wav"]: r for r in json.load(f)}


def main():
	ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
	ap.add_argument("scene")
	ap.add_argument("out_dir")
	ap.add_argument("--speed", type=float, default=0.95)
	ap.add_argument("--allow-spelled", action="store_true", help="確定要唸縮寫或英文單字時才用")
	ap.add_argument("--tts", choices=["sovits", "gemini"], default="gemini", help="gemini＝Gemini TTS（預設，付費，記花費）；sovits＝本機王老師（免費，需要 :9880）")
	ap.add_argument("--tts-model", default="gemini-3.8-flash-tts")
	ap.add_argument("--voice", default="Charon", help="Gemini 內建聲音名稱")
	ap.add_argument("--redo", default="", metavar="3,5", help="只重配指定句號（從 1 起），略過這幾句的快取")
	ap.add_argument("--english", default="auto", metavar="PLAN_JSON|auto|off",
		help="Gemini 專用：英文單字照原文唸（唸 say），只把程式符號（<=、-o、Ctrl+S）依 plan 詞彙表換成中文；auto＝找分鏡旁的 plan.json")
	args = ap.parse_args()
	gemini = args.tts == "gemini"
	if gemini:
		import llm
		llm.load_env()
	with open(args.scene, encoding="utf-8") as f:
		doc = json.load(f)
	audio_dir = os.path.join(args.out_dir, "audio")
	raw_dir = os.path.join(audio_dir, "raw")
	os.makedirs(raw_dir, exist_ok=True)
	report_path = os.path.join(args.out_dir, "narration.json")
	cache = {}
	if os.path.exists(report_path):
		with open(report_path, encoding="utf-8") as f:
			previous = json.load(f)
			cache = {r["digest"]: r for r in [*previous.get("cache", []), *previous["beats"]]}
	proofs = {}
	identity_path = os.path.join(args.out_dir, "timing.identity.json")
	if os.path.exists(identity_path):
		with open(identity_path, encoding="utf-8") as f:
			previous_identity = json.load(f)
			proofs = {r["digest"]: {**r, "voice_digest": previous_identity["voice_digest"]}
				for r in previous_identity["beats"]}

	beats = [(si, b) for si, s in enumerate(doc["scenes"]) for b in s["beats"]]
	sources = [{"scene": si, "i": bi, "say": b["say"], "spoken": b.get("spoken")}
		for si, scene in enumerate(doc["scenes"]) for bi, b in enumerate(scene["beats"])]
	if args.redo and not re.fullmatch(r"[1-9]\d*(?:,[1-9]\d*)*", args.redo):
		ap.error("--redo 必須是從 1 起的句號，例如 3,5")
	redo = {int(value) for value in args.redo.split(",")} if args.redo else set()
	if any(value > len(beats) for value in redo):
		ap.error("--redo 的句號超過講稿句數")
	plan_path = None
	if gemini and args.english != "off":
		plan_path = args.english
		if args.english == "auto":
			here = os.path.dirname(os.path.abspath(args.scene))
			plan_path = next((p for p in (os.path.join(here, "plan.json"), os.path.join(os.path.dirname(here), "plan.json")) if os.path.exists(p)), None)
			if plan_path is None:
				print("找不到 plan.json，程式符號沒有唸法可換，改唸 spoken（中文說法）", flush=True)
	symbols = None
	if plan_path:
		with open(plan_path, encoding="utf-8") as f:
			symbols = [g for g in json.load(f).get("glossary", []) if re.search(r"[^A-Za-z0-9\s/]", g.get("term", ""))]
		symbols.sort(key=lambda g: -len(g["term"]))
		for _, b in beats:
			text = b["say"]
			for g in symbols:
				for term in re.split(r"\s*/\s*", g["term"]):
					text = text.replace(term, g["say_as"])
			b["spoken"] = text
	bad = [f"{p}：{b.get('spoken') or b['say']}" for _, b in beats if (p := speech_problems(b.get("spoken") or b["say"]))]
	if bad and not args.allow_spelled and not gemini:
		# 王老師語料沒有逐字母縮寫、英文單字也極少（見 memory gptsovits-ar-failure-modes）
		raise SystemExit("講稿請改中文說法（畫面可保留英文，旁白寫在 spoken）：\n  " + "\n  ".join(bad))

	key = f"gemini|{gemini_tts.AUDIO_FORMAT}|{args.tts_model}|{args.voice}|{args.speed}|{hashlib.sha1(gemini_tts.prompt_for('', args.speed).encode()).hexdigest()[:8]}" if gemini else voice_key(args.speed)
	voice_digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
	usage_path, spent, calls = os.path.join(args.out_dir, "tts_usage.jsonl"), 0.0, 0
	records, meta, todo, unchecked = [None] * len(beats), {}, [], []
	identities, aliases = {}, {}
	redo_digests = {hashlib.sha1(f"{b.get('spoken') or b['say']}|{key}".encode("utf-8")).hexdigest()[:12]
		for k, (_, b) in enumerate(beats) if k + 1 in redo}
	for k, (si, b) in enumerate(beats):
		text = b.get("spoken") or b["say"]
		digest = hashlib.sha1(f"{text}|{key}".encode("utf-8")).hexdigest()[:12]
		wav = os.path.join(audio_dir, f"{digest}.wav")
		meta[k] = (si, text, digest, wav)
		if digest in identities:
			aliases[k] = identities[digest]
			continue
		identities[digest] = k
		hit = cache.get(digest)
		# 舊檔按句序命名，移序仍從報告所指的檔案遷移；保留原檔與 ASR 紀錄。
		if hit and not os.path.exists(wav) and digest not in redo_digests:
			legacy_name = hit.get("wav", "")
			legacy = os.path.join(audio_dir, legacy_name)
			if re.fullmatch(rf"\d+_{digest}\.wav", legacy_name) and os.path.isfile(legacy):
				shutil.copyfile(legacy, wav)
		if hit and os.path.exists(wav) and digest not in redo_digests:
			record, bound = verified_cache(hit, proofs.get(digest), text, voice_digest, wav)
			records[k] = {**record, "scene": si, "wav": os.path.basename(wav)}
			print(f"[{k + 1}/{len(beats)}] 快取 {text}")
			if not bound:
				print(f"[{k + 1}/{len(beats)}] legacy 快取缺少音檔摘要，重新 ASR 驗收")
			if not bound or not hit.get("asr") or not hit["asr"].get("ok") or hit["asr"].get("version") != CHECK_VERSION:
				unchecked.append(k)
		else:
			todo.append(k)

	# 合成 → 內容檢查 → 沒過的換個隨機種子重合成（服務端每次預設隨機 seed），最多 MAX_ROUNDS 次
	rnd = 0
	while True:
		failed = []
		if unchecked:
			results = asr_check([{"wav": meta[k][3], "text": meta[k][1]} for k in unchecked], args.out_dir)
			for k in unchecked:
				r = results[meta[k][3]]
				records[k]["asr"] = {key2: r[key2] for key2 in ("ok", "problems", "missing", "heard")}
				records[k]["asr"]["version"] = r.get("version", CHECK_VERSION)
				if not r["ok"]:
					failed.append(k)
					print(f"  內容檢查未過（{'、'.join(r['problems'])}，疑似漏「{'、'.join(r['missing'])}」）：{meta[k][1]}")
		todo = sorted(set(todo) | set(failed))
		if not todo or rnd >= MAX_ROUNDS:
			break
		rnd += 1
		for k in todo:
			si, text, digest, wav = meta[k]
			print(f"[{k + 1}/{len(beats)}] 合成（第 {rnd} 輪）{text}", flush=True)
			if gemini:
				info, ok, usage = gemini_tts.synth_gemini(text, wav, args.tts_model, args.voice, args.speed)
				spent, calls = spent + usage["usd"], calls + 1
				with open(usage_path, "a", encoding="utf-8") as f:
					f.write(json.dumps({"beat": k, "round": rnd, **usage}, ensure_ascii=False) + "\n")
			else:
				info, ok = synth_keep_raw(text, args.speed, wav, os.path.join(raw_dir, f"{k:02d}_{digest}.r{rnd}"))
			records[k] = {"digest": digest, "text": text, "ok": ok, **info, "scene": si, "wav": os.path.basename(wav), "round": rnd,
				**audio_signature(wav), "voice_digest": voice_digest, "speech_digest": speech_digest(text, voice_digest)}
		unchecked, todo = todo, []
	for k, primary in aliases.items():
		records[k] = {**records[primary], "scene": meta[k][0]}
	records = [{**r, "ok": r["ok"] and r.get("asr", {}).get("ok", False)} for r in records]
	for k, rec in enumerate(records):
		if rec.get("asr", {}).get("missing"):
			print(f"@warn tts_missing 第 {k + 1} 句", flush=True)
		if "重複念" in rec.get("asr", {}).get("problems", []):
			print(f"@warn tts_repeat 第 {k + 1} 句", flush=True)

	# 接成一條：開頭留白、句間停頓、換場多停一點，跟 compile.py 估時的節奏一致
	pieces, timing, t, sr, prev_scene = [], [], 0.0, None, 0
	for k, rec in enumerate(records):
		if file_digest(os.path.join(audio_dir, rec["wav"])) != rec["audio_sha256"]:
			raise ValueError("音檔在 ASR 驗收後改變，拒絕建立 timing 身份")
		rate, data = wavfile.read(os.path.join(audio_dir, rec["wav"]))
		if sr is None:
			sr = rate
			pieces.append(np.zeros(int(sr * LEAD_IN), dtype=data.dtype))
			t = LEAD_IN
		elif rate != sr:
			raise SystemExit(f"取樣率不一致：{rec['wav']} {rate} ≠ {sr}")
		else:
			gap = BEAT_GAP + (SCENE_GAP if rec["scene"] != prev_scene else 0)
			pieces.append(np.zeros(int(sr * gap), dtype=data.dtype))
			t += int(sr * gap) / sr
		dur = len(data) / sr
		# synth 在每句前後各墊了靜音，起訖點取實際開口與收尾
		timing.append({"t0": round(t + synth.PAD_START, 3), "t1": round(t + dur - synth.PAD_END, 3)})
		pieces.append(data)
		t += dur
		prev_scene = rec["scene"]
	master = os.path.join(args.out_dir, "master.wav")
	wavfile.write(master, sr, np.concatenate(pieces))
	with open(os.path.join(args.out_dir, "timing.json"), "w", encoding="utf-8") as f:
		json.dump(timing, f, ensure_ascii=False)
	identity = {"version": 1, "voice_digest": voice_digest, "symbols": symbols,
		"master": {"wav": "master.wav", "audio_sha256": file_digest(master)},
		"beats": [{**source, **span, **speech_flags(rec), "text": rec["text"], "digest": rec["digest"],
			"speech_digest": speech_digest(rec["text"], voice_digest),
			"wav": "audio/" + rec["wav"], "audio_sha256": rec["audio_sha256"], "wav_format": rec["wav_format"]}
			for source, span, rec in zip(sources, timing, records)]}
	with open(identity_path, "w", encoding="utf-8") as f:
		json.dump(identity, f, ensure_ascii=False, indent="\t")
	cache.update({r["digest"]: r for r in records})
	with open(report_path, "w", encoding="utf-8") as f:
		json.dump({"speed": args.speed, "tts": args.tts, "tts_usd_this_run": round(spent, 6), "total": round(t, 3),
			"beats": records, "cache": [cache[digest] for digest in sorted(cache)]}, f, ensure_ascii=False, indent="\t")
	bad = [r for r in records if not r["ok"]]
	print(f"{master}：{t:.2f}s，{len(records)} 句，{len(bad)} 句未過驗收（音量或內容）")
	for r in bad:
		print(f"  未過：{r['text']}　{r.get('asr', {}).get('problems', '')}")
	if gemini:
		total_usd = 0.0
		if os.path.exists(usage_path):
			with open(usage_path, encoding="utf-8") as f:
				total_usd = sum(json.loads(line)["usd"] for line in f if line.strip())
		print(f"Gemini 配音（{args.tts_model}／{args.voice}）：本次 {calls} 次呼叫 US${spent:.4f}，這個資料夾累計 US${total_usd:.4f}")


if __name__ == "__main__":
	main()
