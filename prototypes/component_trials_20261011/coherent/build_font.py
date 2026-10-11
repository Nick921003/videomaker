"""Save a separate subset so the existing six candidates keep their fonts."""
import hashlib
import json
from pathlib import Path
from fontTools import subset
from fontTools.ttLib import TTFont

HERE = Path(__file__).resolve().parent
source = Path('/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc')
text = ''.join(p.read_text() for p in HERE.iterdir() if p.suffix in ('.json', '.mjs', '.html'))
text += ''.join(chr(i) for i in range(32, 127))
font = TTFont(source, fontNumber=3, recalcTimestamp=False)
missing = sorted({c for c in text if not c.isspace() and ord(c) not in font.getBestCmap()})
assert not missing, missing
options = subset.Options()
options.flavor = 'woff'
options.recalc_timestamp = False
subsetter = subset.Subsetter(options=options)
subsetter.populate(text=text)
subsetter.subset(font)
font.flavor = 'woff'
font.save(HERE / 'teaching.woff')
(HERE / 'font.json').write_text(json.dumps({'source':str(source),'font_index':3,'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'subset_sha256':hashlib.sha256((HERE/'teaching.woff').read_bytes()).hexdigest(),'cmap':sorted(font.getBestCmap()),'license':'../vendor/Noto-CJK-copyright.txt'}, indent=2)+'\n')
print('Saved teaching.woff; source glyphs verified')
