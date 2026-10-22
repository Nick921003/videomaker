# 來源：G 槽 論文研究/Analyses/TTS/F5-TTS/finetune_teacher/tw_text_normalizer.py（2026-10-22 複製，sha1 421a5b21e145）
# 隨套件帶走，不依賴 G 槽；研究端更新時要手動同步。
import re
import json
from pathlib import Path

DIGITS_ZH = '零一二三四五六七八九'
UNITS_SMALL = ['', '十', '百', '千']
UNITS_BIG = ['', '萬', '億', '兆', '京']

def _int_to_zh(n: int) -> str:
    if n == 0:
        return "零"

    s = str(n)
    res, groups = [], []
    while s:
        groups.append(int(s[-4:]))
        s = s[:-4]

    if len(groups) > len(UNITS_BIG):
        raise ValueError("數字太大，超出目前中文單位支援範圍")

    for g_idx in range(len(groups) - 1, -1, -1):
        g = groups[g_idx]
        if g == 0:
            if res and res[-1] != "零":
                res.append("零")
            continue

        g_str = f"{g:04d}" if g_idx < len(groups) - 1 else str(g)
        zero_flag = False
        for i, ch in enumerate(g_str):
            d = int(ch)
            pos = len(g_str) - 1 - i
            if d == 0:
                zero_flag = True
            else:
                if zero_flag and res and res[-1] != "零":
                    res.append("零")
                elif zero_flag and not res and g_idx < len(groups) - 1:
                    res.append("零")
                zero_flag = False
                res.append(DIGITS_ZH[d] + UNITS_SMALL[pos])

        res.append(UNITS_BIG[g_idx])

    out = "".join(res).rstrip("零")
    if out.startswith("一十"):
        out = out[1:]
    if out.startswith("二百"):
        out = "兩百" + out[2:]
    if out.startswith("二千"):
        out = "兩千" + out[2:]
    return out or "零"


def num_to_trad_zh(num_str: str) -> str:
    num_str = num_str.strip()
    neg = "負" if num_str.startswith("-") else ""
    if neg:
        num_str = num_str[1:]

    num_str = re.sub(r"\.0+$", "", num_str)
    if "." in num_str:
        int_part, dec_part = num_str.split(".", 1)
        int_zh = _int_to_zh(int(int_part)) if int_part else "零"
        dec_zh = "".join(DIGITS_ZH[int(c)] for c in dec_part if c.isdigit())
        return f"{neg}{int_zh}點{dec_zh}"

    return f"{neg}{_int_to_zh(int(num_str))}"


UNIT_MAP = {'mV': '毫伏特', 'kV': '千伏特', 'V': '伏特', 'mA': '毫安培', 'uA': '微安培', 'μA': '微安培', 'A': '安培', 'mW': '毫瓦', 'kW': '千瓦', 'W': '瓦', 'kΩ': '千歐姆', 'MΩ': '百萬歐姆', 'Ω': '歐姆', 'ohm': '歐姆', 'kHz': '千赫茲', 'MHz': '百萬赫茲', 'GHz': '吉赫茲', 'Hz': '赫茲', 'ms': '毫秒', 's': '秒', '°C': '攝氏度', '℃': '攝氏度'}
WORDS_MAP = {'ASCII': '阿斯基', 'I/O': 'I O', 'printf': 'print F', 'scanf': 'scan F', 'sizeof': 'size of'}
ACRONYMS = ['CPU', 'GPU', 'RAM', 'ROM', 'USB', 'API', 'LED', 'IDE', 'OS', 'PC', 'AI', 'IO', 'PWM', 'ADC', 'DAC', 'IC', 'PCB', 'URL', 'HTML', 'IP']
OPERATORS = {'&&': '，而且同時滿足 ', '||': '，或者是 ', '<=': '小於等於', '>=': '大於等於', '==': '等於', '!=': '不等於', '<<': '左移', '>>': '右移', '->': '箭頭', '++': ' 加加 ', '--': ' 減減 ', '+=': '加等於', '-=': '減等於', '*=': '乘等於', '/=': '除等於', '%lf': '百分比 L F', '%d': '百分比 D', '%f': '百分比 F', '%c': '百分比 C', '%s': '百分比 S', '≤': '小於等於', '≥': '大於等於', '≠': '不等於', '&': ' and ', '|': '一豎', '!': ' not ', '<': '小於', '>': '大於', '=': '等於', '*': '乘以', '/': '除以', '%': '取餘數', '+': '加'}
NUM = '-?\\d+(?:\\.\\d+)?'
CJK = '\\u4e00-\\u9fff'

def normalize_tw_teaching_text(text: str, auto_zh_lead: bool = True) -> str:
    s = text.strip()
    s = re.sub(r"拿\s*(?=1\.)", "拿，", s)

    # 1. 避免「兩個一豎 ||」重複轉譯
    s = s.replace("兩個一豎 ||", "兩個一豎 or ")

    # 2. 特殊單字替換
    for w, say in WORDS_MAP.items():
        s = re.sub(
            rf"(?<![A-Za-z_]){re.escape(w)}(?![A-Za-z_])",
            f" {say} ", s, flags=re.I
        )

    # 3. 百分比與物理電學單位
    s = re.sub(
        rf"({NUM})\s*%(?![A-Za-z])",
        lambda m: "百分之" + num_to_trad_zh(m.group(1)), s
    )
    units = "|".join(sorted(map(re.escape, UNIT_MAP), key=len, reverse=True))
    s = re.sub(
        rf"(?<![A-Za-z_\d])({NUM})\s*({units})(?![A-Za-z])",
        lambda m: num_to_trad_zh(m.group(1)) + UNIT_MAP[m.group(2)], s
    )

    # 4. 程式運算符號替換
    pat = "|".join(sorted(map(re.escape, OPERATORS), key=len, reverse=True))
    s = re.sub(pat, lambda m: f" {OPERATORS[m.group(0)]} ", s)
    s = re.sub(r"(?<=\s)-(?=\s)", "減", s)

    # 5. 剩餘獨立阿拉伯數字
    s = re.sub(
        rf"(?<![A-Za-z_\d])({NUM})(?![A-Za-z_\d])",
        lambda m: num_to_trad_zh(m.group(1)), s
    )

    # 6. 常見縮寫拆成單一大寫字母
    for a in sorted(ACRONYMS, key=len, reverse=True):
        s = re.sub(
            rf"(?<![A-Za-z_]){re.escape(a)}(?![A-Za-z_])",
            lambda m: " " + " ".join(a.upper()) + " ",
            s, flags=re.I
        )

    # 7. 兩個字母以上的英文單詞轉全小寫
    s = re.sub(
        r"(?<![A-Za-z_])[A-Za-z]{2,}(?![A-Za-z_])",
        lambda m: m.group(0).lower(), s
    )

    # 8. 單一英文字母變數轉大寫
    s = re.sub(
        r"(?<![A-Za-z_\d])([a-z])(?![A-Za-z_\d])",
        lambda m: m.group(1).upper(), s
    )

    # 9. 增加語音換氣邊界
    s = re.sub(r"加加\s*跟\s*加加", "加加，跟加加", s)

    # 10. 清理多餘空白與標點
    s = re.sub(r"\s+", " ", s)
    s = re.sub(rf"(?<=[{CJK}])\s+(?=[{CJK}])", "", s)
    s = re.sub(rf"(?<=[{CJK}])(?=[A-Za-z])", " ", s)
    s = re.sub(rf"(?<=[A-Za-z])(?=[{CJK}])", " ", s)
    s = re.sub(r"\s+(?=[，。、；：？！,.;:?!）)])", "", s)
    s = re.sub(r"(?<=[，。、；：？！（(])\s+", "", s)
    s = re.sub(r"，+(?=[，。；：？！,.;:?!])", "", s)

    # 修正：補上第三個參數 s
    s = re.sub(r"^，+", "", s).strip()

    # 11. 若以英文開頭，自動加上中文領頭
    if auto_zh_lead and re.match(r"^[A-Za-z]", s):
        s = "我們看，" + s

    return s


def compute_target_duration_and_speed(
    norm_text: str,
    ref_sec: float,
    ref_text: str,
    zh_char_sec: float = 0.19,
    en_syl_sec: float = 0.29,
    en_letter_sec: float = 0.35,
    cs_pause_sec: float = 0.12,
    comma_sec: float = 0.22,
    final_lengthening_sec: float = 0.45,
):
    zh_count = len(re.findall(f"[{CJK}]", norm_text))
    en_sec = 0.0

    for w in re.findall(r"[A-Za-z]+", norm_text):
        if len(w) == 1:
            en_sec += 0.42 if w.upper() in ("W", "X") else en_letter_sec
        else:
            lw = w.lower()
            g = len(re.findall(r"[aeiouy]+", lw))
            if g > 1 and re.search(r"[^aeiouy]e$", lw) and not re.search(r"[^aeiouy]le$", lw):
                g -= 1
            en_sec += max(1, g) * en_syl_sec

    cs_switches = len(re.findall(
        rf"[{CJK}]\s+[A-Za-z]|[A-Za-z]\s+[{CJK}]", norm_text
    ))
    body = norm_text.rstrip("。！？.!? ")
    pauses = (
        len(re.findall(r"[，、；：,;:]", body)) * comma_sec
        + len(re.findall(r"[。！？!?]", body)) * 0.30
    )
    target_sec = (
        zh_count * zh_char_sec + en_sec + cs_switches * cs_pause_sec
        + pauses + final_lengthening_sec
    )

    ref_bytes = len(ref_text.encode("utf-8"))
    if ref_bytes == 0:
        raise ValueError("ref_text 不可為空字串，否則無法計算相對速度")

    gen_bytes = len(norm_text.encode("utf-8"))
    f5_default_sec = ref_sec * (gen_bytes / ref_bytes)
    dynamic_speed = f5_default_sec / max(1.0, target_sec)
    dynamic_speed = max(0.70, min(1.30, round(dynamic_speed, 2)))
    return target_sec, dynamic_speed
