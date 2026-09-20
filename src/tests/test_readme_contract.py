"""用发布字体和原始供体回归README要求及已修复的来源错误"""

import unittest
from copy import deepcopy

from fontTools.pens.transformPen import TransformPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont

from lib import FAMILIES, font_path, italic_styles, subset_font, variable_path
from verification.custom import check_o
from verification.geometry import best_cmap, bounds
from verification.latin import check_mono_dash, check_mono_letters, check_zero


def regular_instance(path):
	"""只提取字形回归所需字符并实例化常规字重"""
	with subset_font(
		path, (0x2D, 0x2E, 0x30, 0x31, 0x4F, 0x6C, 0x7C, 0x2014, 0x2026)
	) as font:
		return instantiateVariableFont(font, {"wght": 400, "wdth": 100}, inplace=False)


def replace_glyph(target, source, codepoint):
	"""替换单个轮廓以重现旧实现中的供体或笔画错误"""
	target_name = best_cmap(target)[codepoint]
	source_name = best_cmap(source)[codepoint]
	target["glyf"][target_name] = deepcopy(source["glyf"][source_name])
	target["hmtx"][target_name] = source["hmtx"][source_name]


class ReadmeContractTests(unittest.TestCase):
	"""覆盖艺术字O、点零、Mono底横和破折号的几何约束"""

	def test_artistic_o_all_styles(self):
		"""五个发布样式均应具有原生圆环、开口及连续斜笔"""
		for key, config in FAMILIES.items():
			for italic in italic_styles(key):
				with (
					self.subTest(family=key, italic=italic),
					regular_instance(font_path(config, italic)) as patch,
					regular_instance(variable_path(config["source"], italic)) as base,
				):
					check_o(patch, base, "regular")

	def test_o_rejects_dotted_placeholder(self):
		"""拒绝来源O加居中句点的旧占位字形"""
		with (
			regular_instance(font_path(FAMILIES["sans"])) as patch,
			regular_instance(variable_path("Noto_Sans")) as base,
		):
			glyphs = base.getGlyphSet()
			cmap = best_cmap(base)
			pen = TTGlyphPen(glyphs)
			glyphs[cmap[0x4F]].draw(pen)
			outer, period = bounds(base, 0x4F), bounds(base, 0x2E)
			glyphs[cmap[0x2E]].draw(
				TransformPen(
					pen,
					(
						1,
						0,
						0,
						1,
						(outer[0] + outer[2] - period[0] - period[2]) / 2,
						(outer[1] + outer[3] - period[1] - period[3]) / 2,
					),
				)
			)
			patch["glyf"][best_cmap(patch)[0x4F]] = pen.glyph()
			with self.assertRaisesRegex(AssertionError, "O contour count"):
				check_o(patch, base, "dotted placeholder")

	def test_o_rejects_plain_bowl(self):
		"""拒绝没有斜笔与开口的原生O"""
		with (
			regular_instance(font_path(FAMILIES["serif"])) as patch,
			regular_instance(variable_path("Noto_Serif")) as base,
		):
			replace_glyph(patch, base, 0x4F)
			with self.assertRaisesRegex(AssertionError, "O diagonal terminals"):
				check_o(patch, base, "plain bowl")

	def test_o_retains_mono_advance(self):
		"""拒绝艺术字修改Mono等宽步进"""
		with (
			regular_instance(font_path(FAMILIES["mono"])) as patch,
			regular_instance(variable_path("Noto_Sans_Mono")) as base,
		):
			name = best_cmap(patch)[0x4F]
			advance, bearing = patch["hmtx"][name]
			patch["hmtx"][name] = (advance + 20, bearing)
			with self.assertRaisesRegex(AssertionError, "O advance"):
				check_o(patch, base, "wrong mono advance")

	def test_o_rejects_upright_italic(self):
		"""拒绝在Italic字体中沿用直立艺术字"""
		with (
			regular_instance(font_path(FAMILIES["serif"], True)) as patch,
			regular_instance(variable_path("Noto_Serif", True)) as base,
			regular_instance(font_path(FAMILIES["serif"])) as wrong,
		):
			replace_glyph(patch, wrong, 0x4F)
			with self.assertRaises(AssertionError):
				check_o(patch, base, "upright italic")

	def test_native_dotted_zeros(self):
		"""每个已发布样式的点零都必须保留本家族原生来源"""
		for key, config in FAMILIES.items():
			for italic in italic_styles(key):
				with (
					self.subTest(family=key, italic=italic),
					regular_instance(font_path(config, italic)) as patch,
					regular_instance(variable_path(config["source"], italic)) as base,
				):
					check_zero(patch, base, key, "regular")

	def test_zero_rejects_wrong_family(self):
		"""拒绝将Mono零借给Sans的旧实现"""
		with (
			regular_instance(font_path(FAMILIES["sans"])) as patch,
			regular_instance(variable_path("Noto_Sans")) as base,
			regular_instance(font_path(FAMILIES["mono"])) as wrong,
		):
			replace_glyph(patch, wrong, 0x30)
			with self.assertRaises(AssertionError):
				check_zero(patch, base, "sans", "wrong donor")

	def test_zero_rejects_slash(self):
		"""拒绝Mono保留原始斜线零的旧实现"""
		with (
			regular_instance(font_path(FAMILIES["mono"])) as patch,
			regular_instance(variable_path("Noto_Sans_Mono")) as base,
		):
			replace_glyph(patch, base, 0x30)
			with self.assertRaises(AssertionError):
				check_zero(patch, base, "mono", "slashed zero")

	def test_zero_rejects_missing_dot(self):
		"""拒绝只有内外轮廓而没有实心点的零"""
		with (
			regular_instance(font_path(FAMILIES["serif"])) as patch,
			regular_instance(variable_path("Noto_Serif")) as base,
		):
			replace_glyph(patch, base, 0x30)
			with self.assertRaisesRegex(AssertionError, "Zero dot count"):
				check_zero(patch, base, "serif", "missing dot")

	def test_mono_one_retains_source_stem(self):
		"""确认Mono数字1只去底横并拒绝原始底横及Sans替代轮廓"""
		with (
			regular_instance(font_path(FAMILIES["mono"])) as patch,
			regular_instance(variable_path("Noto_Sans_Mono")) as base,
			regular_instance(variable_path("Noto_Sans")) as wrong,
		):
			check_mono_letters(patch, base, "regular")
			for source in (base, wrong):
				with self.subTest(source=source["name"].getDebugName(1)):
					replace_glyph(patch, source, 0x31)
					# 令错误供体也采用Mono步进，确保检查的重点仍是轮廓
					name = best_cmap(patch)[0x31]
					patch["hmtx"][name] = (
						base["hmtx"][best_cmap(base)[0x31]][0],
						patch["hmtx"][name][1],
					)
					with self.assertRaises(AssertionError):
						check_mono_letters(patch, base, "wrong one")

	def test_mono_em_dash_uses_sans(self):
		"""确认Mono显式提供Sans破折号并拒绝等宽来源"""
		with (
			regular_instance(font_path(FAMILIES["mono"])) as patch,
			regular_instance(variable_path("Noto_Sans")) as source,
			regular_instance(variable_path("Noto_Sans_Mono")) as wrong,
		):
			check_mono_dash(patch, source, "regular")
			replace_glyph(patch, wrong, 0x2014)
			with self.assertRaises(AssertionError):
				check_mono_dash(patch, source, "wrong em dash")

	def test_mono_has_no_italic_release(self):
		"""确认Mono没有斜体发布配置且保留点零与破折号覆盖"""
		self.assertEqual(italic_styles("mono"), (False,))
		self.assertEqual(FAMILIES["mono"]["italic_codepoints"], ())
		with TTFont(font_path(FAMILIES["mono"])) as font:
			self.assertTrue({0x30, 0x31, 0x2014} <= set(best_cmap(font)))
