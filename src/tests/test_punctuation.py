"""回归空心标点与逗号点头的尺寸关系"""

import unittest
from copy import deepcopy

from fontTools.varLib.instancer import instantiateVariableFont

from lib import FAMILIES, PUNCTUATION, SOURCES, WEIGHTS, font_path, subset_font
from verification.geometry import best_cmap, contour_bounds
from verification.punctuation import check_punctuation


class PunctuationTests(unittest.TestCase):
	def test_rings_follow_comma_head(self):
		"""三个家族的轻、常规及重字重均使用逗号尺寸，拒绝旧句号尺寸"""
		for key, config in FAMILIES.items():
			for weight in (config["minimum"], 300, 400, 700, 900):
				with (
					self.subTest(family=key, weight=weight),
					subset_font(font_path(config), PUNCTUATION) as variable,
					subset_font(
						SOURCES
						/ config["cjk"]
						/ "static"
						/ f"{config['cjk'].replace('_', '')}-{WEIGHTS[weight]}.ttf",
						(*PUNCTUATION, 0x4E2D),
					) as cjk,
					instantiateVariableFont(
						variable, {"wght": weight, "wdth": 100}, inplace=False
					) as patch,
				):
					check_punctuation(patch, cjk, "comma-sized")
					broken = deepcopy(patch)
					glyph = broken["glyf"][best_cmap(broken)[0xFF1A]]
					period = cjk["glyf"][best_cmap(cjk)[0x3002]]
					diameter = max(
						contour_bounds(period, i)[2] - contour_bounds(period, i)[0]
						for i in range(period.numberOfContours)
					)
					for index in range(0, glyph.numberOfContours, 2):
						left, bottom, right, top = contour_bounds(glyph, index)
						cx, cy = (left + right) / 2, (bottom + top) / 2
						scale = diameter / (right - left)
						start = glyph.endPtsOfContours[index - 1] + 1 if index else 0
						for point in range(
							start, glyph.endPtsOfContours[index + 1] + 1
						):
							x, y = glyph.coordinates[point]
							glyph.coordinates[point] = (
								cx + (x - cx) * scale,
								cy + (y - cy) * scale,
							)
					with self.assertRaisesRegex(
						AssertionError, "Comma-sized punctuation ring"
					):
						check_punctuation(broken, cjk, "old period size")
					broken.close()
