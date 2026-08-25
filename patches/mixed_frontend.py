"""訓練端的中英混合文字前端。

原本 prepare_datasets/1-get-text.py 直接呼叫 clean_text(text, "zh")，
中文前端會把拉丁字母整段吃掉（Windows -> 秒），造成音訊與音素不對齊。
推論端 TTS_infer_pack/TextPreprocessor.get_phones_and_bert() 則會先用
LangSegmenter 切中英再逐段 g2p。本模組把推論端的切分邏輯抽出來共用，
讓訓練與推論對齊。

對齊目標為推論參數 text_lang="zh"（即 TextPreprocessor 的 else 分支）。
"""

import re

import torch

from text.LangSegmenter import LangSegmenter
from text.cleaner import clean_text


def split_like_inference(text, language):
	"""複製 TextPreprocessor.get_phones_and_bert() 中 text_lang="zh" 的切分。

	回傳 [(lang, text), ...]，串接後與輸入無損相等（僅收斂連續空白）。
	"""
	text = re.sub(r" {2,}", " ", text)
	langlist = []
	textlist = []
	for tmp in LangSegmenter.getTexts(text):
		if langlist:
			# 相鄰同類（都是英文，或都不是英文）併回上一段
			if (tmp["lang"] == "en" and langlist[-1] == "en") or (
				tmp["lang"] != "en" and langlist[-1] != "en"
			):
				textlist[-1] += tmp["text"]
				continue
		if tmp["lang"] == "en":
			langlist.append("en")
		else:
			# 中日韓漢字無法區分，以資料集標註的語言為準
			langlist.append(language)
		textlist.append(tmp["text"])
	return list(zip(langlist, textlist))


def clean_text_mixed(text, language, version):
	"""逐段 g2p 後串接。

	word2ph 只在整句都是同一種中文時有意義；含英文時回傳 None，
	此時 BERT 必須由 get_phones_and_bert_train() 逐段組出來。
	"""
	text = text.replace("%", "-").replace("￥", ",")
	segments = split_like_inference(text, language)

	phones = []
	norm_parts = []
	word2ph_parts = []
	all_same_lang = True
	for lang, seg in segments:
		seg_phones, seg_word2ph, seg_norm = clean_text(seg, lang, version)
		phones += seg_phones
		norm_parts.append(seg_norm)
		if seg_word2ph is None:
			all_same_lang = False
		else:
			word2ph_parts += seg_word2ph

	word2ph = word2ph_parts if all_same_lang and len(segments) == 1 else None
	return phones, word2ph, "".join(norm_parts)


def get_phones_and_bert_train(text, language, version, bert_fn, dtype=torch.float32):
	"""訓練用：回傳 (phones, bert_feature, norm_text)。

	bert_fn(norm_text, word2ph) 由呼叫端提供（1-get-text.py 內的 get_bert_feature）。
	非中文段落給零向量，與推論端 TextPreprocessor.get_bert_inf() 行為一致。
	"""
	text = text.replace("%", "-").replace("￥", ",")
	segments = split_like_inference(text, language)

	phones_list = []
	bert_list = []
	norm_list = []
	for lang, seg in segments:
		seg_phones, seg_word2ph, seg_norm = clean_text(seg, lang, version)
		if lang.replace("all_", "") == "zh":
			feat = bert_fn(seg_norm, seg_word2ph)
		else:
			feat = torch.zeros((1024, len(seg_phones)), dtype=dtype)
		phones_list.append(seg_phones)
		bert_list.append(feat.to(dtype))
		norm_list.append(seg_norm)

	phones = sum(phones_list, [])
	bert = torch.cat(bert_list, dim=1)
	assert bert.shape[-1] == len(phones), (bert.shape, len(phones))
	return phones, bert, "".join(norm_list)
