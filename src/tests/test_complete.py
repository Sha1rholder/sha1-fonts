"""核验完整发布字体的覆盖范围和不含SC的Italic规则"""

import unittest

from fontTools.ttLib import TTFont

from lib import (
	FAMILIES,
	complete_font_path,
	font_path,
	italic_styles,
	variable_path,
)
from verification.geometry import best_cmap


class CompleteFontTests(unittest.TestCase):
	"""覆盖完整字体的来源并集和独立家族命名"""

	def test_complete_coverage(self):
		"""完整字体应编码原字体栈在当前样式下的全部有效码位"""
		for key, config in FAMILIES.items():
			for italic in italic_styles(key):
				with (
					self.subTest(family=key, italic=italic),
					TTFont(complete_font_path(config, italic)) as complete,
					TTFont(variable_path(config["source"], italic)) as base,
					TTFont(font_path(config, italic)) as patch,
				):
					expected = set(best_cmap(base)) | set(best_cmap(patch))
					if not italic:
						with TTFont(variable_path(config["cjk"])) as cjk:
							expected |= set(best_cmap(cjk))
					self.assertEqual(set(best_cmap(complete)), expected)
					self.assertEqual(
						complete["name"].getDebugName(1), config["complete"]
					)
					self.assertEqual(
						complete["name"].getDebugName(2),
						"Italic" if italic else "Regular",
					)

	def test_italic_has_no_sc_coverage(self):
		"""Italic完整字体不应因合并SC而获得中日韩字形"""
		for key in ("sans", "serif"):
			with TTFont(complete_font_path(FAMILIES[key], True)) as font:
				self.assertNotIn(0x4E2D, best_cmap(font))
