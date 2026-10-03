import unittest

from studio.mindmap import MindmapError, build_mindmap, canonical_mindmap, render_mindmap_svg


MATERIAL = "迴圈會重複執行。條件控制是否繼續。更新變數可以避免無限迴圈。"


def sample_map():
	return {"contract_version": "1.0", "title": "理解迴圈", "root_id": "loop",
		"nodes": [
			{"id": "loop", "label": "迴圈", "explanation": "重複執行指令。", "source_quote": "迴圈會重複執行"},
			{"id": "condition", "label": "條件", "explanation": "決定是否繼續。", "source_quote": "條件控制是否繼續"},
			{"id": "update", "label": "更新變數", "explanation": "避免無限迴圈。", "source_quote": "更新變數可以避免無限迴圈"},
		],
		"edges": [
			{"from": "loop", "to": "condition", "label": "由此控制", "source_quote": "條件控制是否繼續"},
			{"from": "loop", "to": "update", "label": "需要搭配", "source_quote": "更新變數可以避免無限迴圈"},
		]}


class TestMindmap(unittest.TestCase):
	def test_builds_bounded_cited_tree(self):
		calls = []
		candidate = sample_map()
		def complete(*args):
			calls.append(args)
			return candidate, {}
		result = build_mindmap(MATERIAL, "做成心智圖", complete)
		self.assertEqual(result["root_id"], "loop")
		self.assertEqual(len(calls), 1)
		self.assertIn(MATERIAL, calls[0][1])
		self.assertIsNot(result, candidate)

	def test_rejects_missing_quotes_and_invalid_tree(self):
		bad = sample_map()
		bad["edges"][0]["source_quote"] = "教材沒有這句"
		with self.assertRaises(MindmapError):
			build_mindmap(MATERIAL, "心智圖", lambda *_: (bad, {}))
		for mutate in (
			lambda m: m["edges"].append(m["edges"][0]),
			lambda m: m["edges"][1].update({"to": "condition"}),
			lambda m: m["nodes"][1].update({"id": "loop"}),
			lambda m: m.update({"html": "<script/>"}),
		):
			bad = sample_map()
			mutate(bad)
			with self.subTest(bad=bad), self.assertRaises(MindmapError):
				canonical_mindmap(bad)

	def test_rejects_source_limit_before_ai_and_hides_provider_error(self):
		calls = []
		with self.assertRaises(MindmapError):
			build_mindmap("字" * 30001, "心智圖", lambda *_: calls.append(1))
		self.assertEqual(calls, [])
		def fail(*_):
			raise RuntimeError("secret /private/path")
		with self.assertRaises(MindmapError) as context:
			build_mindmap(MATERIAL, "心智圖", fail)
		self.assertNotIn("secret", str(context.exception))

	def test_model_schema_uses_supported_array_bounds(self):
		# Anthropic structured output rejects minItems > 1 and every maxItems.
		def complete(_system, _user, schema):
			def arrays(value):
				if isinstance(value, dict):
					if value.get("type") == "array":
						yield value
					for child in value.values():
						yield from arrays(child)
				elif isinstance(value, list):
					for child in value:
						yield from arrays(child)
			for array in arrays(schema):
				self.assertIn(array.get("minItems", 0), (0, 1))
				self.assertNotIn("maxItems", array)
			return sample_map(), {}
		build_mindmap(MATERIAL, "做成心智圖", complete)

	def test_node_labels_do_not_split_short_dates_or_english_words(self):
		from xml.etree import ElementTree
		data = sample_map()
		data["nodes"][0]["label"] = "ChineseExamAssistant 專案"
		data["nodes"][1]["label"] = "現況（2026-07-12）"
		root = ElementTree.fromstring(render_mindmap_svg(data))
		ns = "{http://www.w3.org/2000/svg}"
		root_card = root.find(f"{ns}g[@data-node-id='loop']")
		condition_card = root.find(f"{ns}g[@data-node-id='condition']")
		self.assertEqual([text.text for text in root_card.findall(f"{ns}text")],
			["ChineseExamAssistant", "專案"])
		self.assertIn("現況（2026-07-12）", [text.text for text in condition_card.findall(f"{ns}text")])

	def test_relation_labels_live_inside_target_cards_not_over_connectors(self):
		from xml.etree import ElementTree
		root = ElementTree.fromstring(render_mindmap_svg(sample_map()))
		ns = "{http://www.w3.org/2000/svg}"
		for edge in sample_map()["edges"]:
			card = root.find(f"{ns}g[@data-node-id='{edge['to']}']")
			self.assertIsNotNone(card)
			self.assertIn(edge["label"], [item.text for item in card.findall(f"{ns}text")])
		self.assertEqual(root.findall(f"{ns}text"), [])

	def test_svg_escapes_untrusted_content_and_has_no_active_markup(self):
		map_data = sample_map()
		map_data["nodes"][0]["label"] = '<script>x</script>'
		svg = render_mindmap_svg(canonical_mindmap(map_data)).decode()
		self.assertIn("&lt;script&gt;", svg)
		self.assertNotIn("<script>", svg)
		self.assertIn("<svg", svg)
		self.assertIn("條件", svg)
		map_data["title"] = 'x" onload="alert(1)'
		svg = render_mindmap_svg(map_data).decode()
		from xml.etree import ElementTree
		root = ElementTree.fromstring(svg)
		self.assertNotIn("onload", root.attrib)
		self.assertEqual(root.find("{http://www.w3.org/2000/svg}title").text, 'x" onload="alert(1)')


	def test_svg_stays_valid_when_source_contains_xml_invalid_characters(self):
		from xml.etree import ElementTree
		material = MATERIAL + "\x00\ufffe"
		mindmap = build_mindmap(material, "心智圖", lambda *_: (sample_map(), {}))
		mindmap["nodes"][0]["label"] += "\ufffe"
		svg = render_mindmap_svg(mindmap, material)
		root = ElementTree.fromstring(svg)
		self.assertNotIn(b"\x00", svg)
		self.assertIn("\ufffd", root.find("{http://www.w3.org/2000/svg}desc").text)
		self.assertEqual(root.attrib["aria-describedby"], "source-evidence")
		with_source = render_mindmap_svg(sample_map(), MATERIAL).decode()
		parsed = ElementTree.fromstring(with_source)
		description = parsed.find('{http://www.w3.org/2000/svg}desc').text
		self.assertIn("條件控制是否繼續", description)
		self.assertIn(MATERIAL, description)


	def test_svg_has_named_title_and_description_for_accessibility(self):
		from xml.etree import ElementTree
		root = ElementTree.fromstring(render_mindmap_svg(sample_map(), MATERIAL))
		children = list(root)
		self.assertEqual(children[0].tag, "{http://www.w3.org/2000/svg}title")
		self.assertEqual(children[0].text, "理解迴圈")
		self.assertEqual(children[1].tag, "{http://www.w3.org/2000/svg}desc")
		ids = [element.attrib["id"] for element in root.iter() if "id" in element.attrib]
		self.assertEqual(len(ids), len(set(ids)))
		self.assertEqual(root.attrib["aria-labelledby"], ids[0])
		self.assertEqual(root.attrib["aria-describedby"], ids[1])
