#!/usr/bin/env python3
"""Sound bed for a V8 黑板报 film, on the shared lib/sfxlib.py: every event is procedural and lands on the picture.

    bash tools/sfx.sh        # = node lib/kit/chalklog.mjs . && <numpy python> tools/sfx.py  → assets/audio/sfx.wav

The chalk log (assets/audio/chalk-log.json, written by Kit.log() via lib/kit/chalklog.mjs) holds every written
character, long stroke, quick stroke, tick, tap, erasure, camera move and named mark (Kit.mark / api.mark). The story
(lib/story.js) gives the chapter changes, the line starts, the closing line and the recap. Known marks: pop, light,
pullback, recapBox, lessonEnd, thump, bell; any other mark name gets a soft knock. The unvoiced recap is lifted 8 dB.
Nothing is sampled or downloaded; a fixed seed keeps the file identical run to run. Levels sit under the narration.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "lib"))
import sfxlib as sx  # noqa: E402

LOG = json.loads((ROOT / "assets/audio/chalk-log.json").read_text())
STORY = json.loads((ROOT / "lib/story.js").read_text(encoding="utf-8").split("window.STORY = ", 1)[1].strip().rstrip(";"))
DUR = float(STORY["duration"])
MARK = LOG.get("marks", {})
END = STORY.get("end") or None
REC = STORY.get("recap") or None
if REC and not (REC.get("points") and REC["start"] < DUR - 1):
    REC = None

bed = sx.Bed(DUR, seed_value=20261005)
rnd = lambda: float(sx.rng.random())

# 粉筆頁的字幕在開口時寫、講完就擦：寫字和擦字幕都不配聲，板擦聲只留給整頁換頁（使用者 2026-10-26：太吵）。
# 先畫後講，圖都畫在開口前，所以「講話期間寫的字」幾乎都是字幕。
SPOKEN = [(L["start"], L["end"]) for L in STORY["lines"]]
CAP_ERASE = []  # 同頁上一句講完到下一句開口之間的擦除＝擦字幕
for pg in STORY.get("pages", []):
    for a_, b_ in zip(pg, pg[1:]):
        La, Lb = STORY["lines"][a_ - 1], STORY["lines"][b_ - 1]
        CAP_ERASE.append((La["end"], Lb["start"]))
speaking = lambda t: any(a_ <= t <= b_ for a_, b_ in SPOKEN)

# chalk: one scrape per written character (characters landing within 25 ms share one scrape)
last = -1.0
for at in LOG["chars"]:
    if speaking(at):
        continue
    if at - last < 0.025:
        continue
    last = at
    bed.place(sx.chalk(1 + int(rnd() * 3)), at, -34 + (rnd() - 0.5) * 4, (rnd() - 0.5) * 0.6)
for a, b in LOG["lines"]:  # long hand strokes with the stick
    bed.place(sx.chalk_line(b - a), a, -36, (rnd() - 0.5) * 0.4)
for a, b in LOG["quick"]:  # strokes drawn without the stick (frames, borders, rulers): a softer line
    if b - a >= 0.2:
        bed.place(sx.chalk_line(b - a), a, -41, (rnd() - 0.5) * 0.4)
last = -1.0
for at in LOG["ticks"]:  # tallies, hatching, chart points: quick taps
    if at - last < 0.03:
        continue
    last = at
    bed.place(sx.click(0.9), at, -38, -0.2 + (rnd() - 0.5) * 0.3)
for at in LOG["taps"]:  # rings, stamps, the 「待演绎」 tag: a firm tap
    bed.place(sx.click(1.5), at, -30, 0.0)
for a, b in LOG["erases"]:  # the felt eraser
    if any(x <= a <= y for x, y in CAP_ERASE):
        continue
    bed.place(sx.felt(b - a + 0.08), a, -27, 0.1)
# camera moves：不配聲。換頁的咻聲聽起來刺耳（使用者 2026-10-23 回饋）

# the story: the chalk touching down at every line start（換章的敲板聲拿掉，同上）
end_line = END["line"] if END else None
# 每句開口的粉筆輕敲也拿掉：它就是字幕下筆的聲音（使用者 2026-10-26）

# named marks from the page
KNOWN = {"pop", "light", "pullback", "recapBox", "lessonEnd", "thump", "bell", "click", "key"}
# pop／light／thump／bell 這類有音高或敲擊的提示音不配：使用者聽起來像「叮咚」，很刺耳（2026-10-24）
# 電腦畫面：滑鼠點擊一聲輕喀、打字更輕，都壓在旁白底下
for at in MARK.get("click", []):
    bed.place(sx.click(1.0), at, -36, 0.15)
last = -1.0
for at in MARK.get("key", []):
    if at - last < 0.04:
        continue
    last = at
    bed.place(sx.click(0.6), at, -42, 0.1)
for name, times in MARK.items():
    if name not in KNOWN:
        for at in times:
            bed.place(sx.click(1.2), at, -34, 0.1)

# the closing line: a low swell under it; the board steps back near its end
if END:
    bed.place(sx.swell(3.6), END["start"] - 0.3, -30)
# review: the key sentence is underlined / boxed — a tap, a swell and the class bell (the lift applies on top)
for at in MARK.get("recapBox", []):
    bed.place(sx.click(1.5), at + 0.4, -36, -0.2)
    bed.place(sx.swell(2.0), at - 0.6, -38)

print(bed.write(str(ROOT / "assets/audio/sfx.wav"), lift_after=(REC["start"], 8) if REC and not REC.get("say") else None, fade=0.35))
