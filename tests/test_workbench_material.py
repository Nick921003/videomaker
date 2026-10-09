import hashlib
from pathlib import Path
import tempfile
import unittest

from workbench.library import Library, read_json


class TestCommonMaterial(unittest.TestCase):
	def test_plaintext_preserves_exact_source_and_line_positions(self):
		with tempfile.TemporaryDirectory() as root:
			library = Library(Path(root))
			text = '# 迴圈\n\n次數：3\n'
			uid, _ = library.create_unit(text, source_kind='txt')
			data = read_json(library.path(uid, 'material.json'))
			self.assertEqual(data['schema_version'], 1)
			self.assertEqual(data['content_version'], hashlib.sha256(text.encode()).hexdigest())
			self.assertEqual(data['sources'][0]['kind'], 'txt')
			self.assertEqual(data['sections'][0]['locator'], {'line_start': 1, 'line_end': 3})
			self.assertEqual(data['sections'][0]['text'], text)
			self.assertEqual(library.path(uid, data['sources'][0]['path']).read_bytes(), text.encode())

	def test_reuse_keeps_material_contract_and_metadata(self):
		with tempfile.TemporaryDirectory() as root:
			library = Library(Path(root))
			uid, _ = library.create_unit('原文\n')
			original = library.path(uid, 'material.json').read_bytes()
			meta = library.path(uid, 'meta.json').read_bytes()
			self.assertEqual(library.create_unit('原文\n', '新標題'), (uid, False))
			self.assertEqual(library.path(uid, 'material.json').read_bytes(), original)
			self.assertEqual(library.path(uid, 'meta.json').read_bytes(), meta)

	def test_normalized_pdf_is_not_mislabeled_as_original_source(self):
		with tempfile.TemporaryDirectory() as root:
			library = Library(Path(root))
			uid, _ = library.create_unit('整理後文字', source_kind='pdf')
			self.assertFalse(library.path(uid, 'material.json').exists())

	def test_uploaded_sources_survive_reuse_and_retain_review(self):
		from workbench.material import attach_source
		with tempfile.TemporaryDirectory() as root:
			library = Library(Path(root) / 'units')
			uid, _ = library.create_unit('整理後文字', source_kind='pdf')
			raw = Path(root) / 'lesson.pdf'
			raw.write_bytes(b'%PDF-original-one')
			pages = [{'page': 2, 'clean_text': '整理後文字', 'verified_quotes': ['原文'],
				'visual_notes': [], 'uncertainties': ['數字模糊']}]
			attach_source(library, uid, raw, 'pdf', '## 第 2 頁\n原文', pages)
			raw.write_bytes(b'%PDF-original-two')
			attach_source(library, uid, raw, 'pdf', '## 第 2 頁\n另一原文', pages)
			data = read_json(library.path(uid, 'material.json'))
			self.assertEqual(len(data['sources']), 2)
			self.assertEqual(len(data['sections']), 2)
			self.assertTrue(data['review']['required'])
			self.assertEqual(data['sections'][0]['locator'], {'page': 2})
			self.assertEqual(library.path(uid, data['sources'][0]['path']).read_bytes(), b'%PDF-original-one')
			attach_source(library, uid, raw, 'pdf', '## 第 2 頁\n另一原文', pages)
			self.assertEqual(len(read_json(library.path(uid, 'material.json'))['sources']), 2)

	def test_read_contract_rejects_version_drift_and_source_escape(self):
		from workbench.library import write_json
		with tempfile.TemporaryDirectory() as root:
			library = Library(Path(root))
			uid, _ = library.create_unit('原文')
			path = library.path(uid, 'material.json')
			data = read_json(path)
			data['sources'][0]['path'] = '../outside.txt'
			write_json(path, data)
			with self.assertRaises(ValueError):
				library.material(uid)
			data['sources'][0]['path'] = 'material.md'
			write_json(path, data)
			library.path(uid, 'material.md').write_text('變更正文')
			with self.assertRaises(ValueError):
				library.material(uid)

	def test_crlf_and_bom_do_not_invalidate_newly_saved_source(self):
		with tempfile.TemporaryDirectory() as root:
			library = Library(Path(root))
			text = '\ufeff# 教材\r\n原文\r\n'
			uid, _ = library.create_unit(text, source_kind='txt')
			data = library.material(uid)
			self.assertEqual(data['content_version'], hashlib.sha256(text.encode()).hexdigest())

	def test_composite_preserves_unknown_components_and_rejects_mixed_versions(self):
		from workbench.material import composite_provenance, provenance
		from workbench.library import write_json
		with tempfile.TemporaryDirectory() as root:
			library = Library(Path(root))
			uid, _ = library.create_unit('教材')
			directory = library.unit_dir(uid)
			data = library.material(uid)
			write_json(directory / 'q1.scene.source.json', provenance(data))
			result = composite_provenance(directory, ['q1', 'q2'])
			self.assertIsNone(result['content_version'])
			self.assertEqual(result['legacy_components'], ['q2'])
			write_json(directory / 'q2.scene.source.json', provenance(data))
			self.assertEqual(composite_provenance(directory, ['q1', 'q2'])['content_version'], data['content_version'])
			bad = provenance(data)
			bad['content_version'] = 'outdated'
			write_json(directory / 'q2.scene.source.json', bad)
			with self.assertRaises(ValueError):
				composite_provenance(directory, ['q1', 'q2'])
