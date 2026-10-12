"""校验真实网页字体资产，防止子集遗漏或可变字体静态化"""

import io
import json
import sys
import unittest
from pathlib import Path

from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from build import OUTPUT, WEB, SampleText, chunks_for, ranges


class WebAssets(unittest.TestCase):
	@classmethod
	def setUpClass(cls):
		cls.manifest = json.loads((OUTPUT / "fonts.json").read_text())

	def test_all_subsets_cover_manifest_and_keep_axes(self):
		for key, source in self.manifest["fonts"].items():
			with self.subTest(source=key):
				seen = set()
				for chunk in source["chunks"]:
					data = (OUTPUT / chunk["file"]).read_bytes()
					self.assertEqual(len(data), chunk["bytes"])
					with TTFont(io.BytesIO(data)) as font:
						points = set(font.getBestCmap())
						self.assertEqual(ranges(points), chunk["ranges"])
						self.assertFalse(seen & points)
						seen.update(points)
						self.assertEqual(
							{
								axis.axisTag: [axis.minValue, axis.maxValue]
								for axis in font["fvar"].axes
							},
							source["axes"],
						)
						self.assertIn("gvar", font)
				self.assertEqual(ranges(seen), source["ranges"])

	def test_fixed_samples_do_not_need_extra_shards(self):
		parser = SampleText()
		parser.feed((WEB / "index.html").read_text())
		for source in self.manifest["fonts"].values():
			all_points = {
				point
				for start, end in source["ranges"]
				for point in range(start, end + 1)
			}
			base_points = {
				point
				for start, end in source["chunks"][0]["ranges"]
				for point in range(start, end + 1)
			}
			self.assertLessEqual(all_points & parser.points, base_points)

	def test_patch_instances_match_ttf_after_conversion(self):
		from lib import FAMILIES, font_path

		for family, config in FAMILIES.items():
			for italic in (False, True) if family != "mono" else (False,):
				key = f"{family}-patch{'-italic' if italic else ''}"
				woff = OUTPUT / self.manifest["fonts"][key]["chunks"][0]["file"]
				for weight, width in ((400, 100), (700, 75)):
					with (
						TTFont(woff) as web_font,
						TTFont(font_path(config, italic)) as patch,
					):
						web_instance = instantiateVariableFont(
							web_font, {"wght": weight, "wdth": width}, inplace=False
						)
						patch_instance = instantiateVariableFont(
							patch, {"wght": weight, "wdth": width}, inplace=False
						)
						for point, name in web_instance.getBestCmap().items():
							original = patch_instance.getBestCmap()[point]
							self.assertEqual(
								web_instance["hmtx"].metrics[name],
								patch_instance["hmtx"].metrics[original],
							)
							self.assertEqual(
								web_instance["glyf"][name].getCoordinates(
									web_instance["glyf"]
								),
								patch_instance["glyf"][original].getCoordinates(
									patch_instance["glyf"]
								),
							)

	def test_only_woff2_and_all_licenses_are_packaged(self):
		for source in self.manifest["fonts"].values():
			for chunk in source["chunks"]:
				self.assertTrue(chunk["file"].startswith("fonts/"))
				self.assertTrue(chunk["file"].endswith(".woff2"))
		self.assertEqual(len(list((OUTPUT / "licenses").glob("*.txt"))), 6)
		self.assertFalse(list(OUTPUT.rglob("*.ttf")))

	def test_local_coverage_guard_covers_every_source(self):
		points = {
			point
			for source in self.manifest["fonts"].values()
			for start, end in source["ranges"]
			for point in range(start, end + 1)
		}
		with TTFont(OUTPUT / self.manifest["guard"]["file"]) as font:
			self.assertEqual(set(font.getBestCmap()), points)
			self.assertTrue(any(table.format == 12 for table in font["cmap"].tables))
			self.assertEqual(
				{font["hmtx"].metrics[name][0] for name in font.getBestCmap().values()},
				{400},
			)
			self.assertLess(self.manifest["guard"]["bytes"], 100_000)

	def test_sparse_shards_are_disjoint_and_skip_empty_buckets(self):
		points = {0x41, 0x4E00, 0x4EFF, 0x4F00, 0x20000}
		chunks = chunks_for(points, {0x41, 0x4E00})
		self.assertEqual(chunks, [{0x41, 0x4E00}, {0x4EFF}, {0x4F00}, {0x20000}])


if __name__ == "__main__":
	unittest.main()
