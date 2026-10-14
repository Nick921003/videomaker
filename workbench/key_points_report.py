"""重點清單對照表：讓人五分鐘內判斷重點有沒有抓對。"""
from pathlib import Path
import re
import sys

if __package__ in (None, ''):
	sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def render_report(material, key_points):
	headings = [line.lstrip('#').strip() for line in material.splitlines() if re.match(r'^#{1,6}\s', line)]
	lines = [f'# {key_points["title"]}', '',
		f'結構：{key_points["structure"]}　狀態：{key_points["status"]}', '', '## 教材段落標題', '']
	lines += [f'- {heading}' for heading in headings] or ['- （教材沒有標題）']
	lines += ['', '## 學習目標', '']
	lines += [f'- {item["id"]}：{item["text"]}' + ('（推論）' if item['inferred'] else '') for item in key_points['objectives']]
	lines += ['', '## 重點', '', '| # | 重點 | 學生疑問 | 類型 | 對應目標 | 講解字數 |', '| --- | --- | --- | --- | --- | --- |']
	for number, point in enumerate(key_points['points'], 1):
		objectives = '、'.join(point['objectives']) or '補充'
		lines.append(f'| {number} | {point["title"]} | {point["question"]} | {point["type"]} | {objectives} | {len(point["explanation"])} |')
	lines += ['', '## 講解全文', '']
	for point in key_points['points']:
		lines += [f'### {point["title"]}', '', point['explanation'], '']
	return '\n'.join(lines)


def main(argv):
	from workbench.key_points import current
	from workbench.library import safe_path
	directory = Path(argv[0]).resolve()
	value = current(directory)
	if value is None:
		print('這個單元還沒有有效的重點清單', file=sys.stderr)
		return 1
	print(render_report(safe_path(directory, 'material.md').read_text(encoding='utf-8'), value))
	return 0


if __name__ == '__main__':
	sys.exit(main(sys.argv[1:]))
