"""核验轮廓缓存的网格覆盖和设计兼容性"""

import json
import unittest

from build.jobs import validate_jobs
from lib import (
	FAMILIES,
	OUTLINE_DESIGN_VERSION,
	WEIGHTS,
	WIDTHS,
	BuildJob,
	italic_styles,
	patch_codepoints,
	slanted_codepoints,
)


class JobCacheTests(unittest.TestCase):
	"""覆盖缓存完整性与旧版设计的拒绝路径"""

	def setUp(self):
		"""创建使用占位文件路径的完整母版任务网格"""
		self.jobs: list[BuildJob] = [
			{
				"family": key,
				"italic": italic,
				"weight": weight,
				"width": width,
				"base": "base.ttf",
				"cjk": "cjk.ttf",
				"output": "outline.json",
				"codepoints": list(patch_codepoints(config, italic)),
				"slanted_codepoints": list(slanted_codepoints(key, italic)),
				"italic_angle": -12 if italic else 0,
				"caret_slope_rise": 1000,
				"caret_slope_run": 0,
				"punctuation_top_reference": 0x4E2D,
				"punctuation_dot_shift": 16,
				"punctuation_right_shift_fraction": 0.125,
				"outline_design_version": OUTLINE_DESIGN_VERSION,
			}
			for key, config in FAMILIES.items()
			for italic in italic_styles(key)
			for weight in WEIGHTS
			if weight >= config["minimum"]
			for width in WIDTHS
		]

	def test_json_round_trip(self):
		"""确认JSON往返后的当前设计缓存仍可复用"""
		validate_jobs(json.loads(json.dumps(self.jobs)))

	def test_missing_position(self):
		"""拒绝缺少任意母版位置的缓存"""
		with self.assertRaisesRegex(ValueError, "do not cover all styles"):
			validate_jobs(self.jobs[:-1])

	def test_duplicate_position(self):
		"""拒绝网格完整但包含重复位置的缓存"""
		with self.assertRaisesRegex(ValueError, "do not cover all styles"):
			validate_jobs([*self.jobs, self.jobs[0]])

	def test_outdated_design(self):
		"""拒绝字符覆盖或构造斜体列表已经过时的缓存"""
		for field in ("codepoints", "slanted_codepoints"):
			with self.subTest(field=field):
				jobs = json.loads(json.dumps(self.jobs))
				jobs[0][field].append(0x20)
				with self.assertRaisesRegex(ValueError, "older style design"):
					validate_jobs(jobs)

	def test_outdated_geometry(self):
		"""拒绝字符集相同但轮廓版本或标点参数已经过时的缓存"""
		for field in (
			"outline_design_version",
			"punctuation_top_reference",
			"punctuation_dot_shift",
			"punctuation_right_shift_fraction",
		):
			with self.subTest(field=field):
				jobs = json.loads(json.dumps(self.jobs))
				jobs[0][field] += 1
				with self.assertRaisesRegex(ValueError, "older style design"):
					validate_jobs(jobs)

	def test_missing_design_version(self):
		"""拒绝尚未记录轮廓版本的旧任务文件"""
		jobs = json.loads(json.dumps(self.jobs))
		del jobs[0]["outline_design_version"]
		with self.assertRaisesRegex(ValueError, "older style design"):
			validate_jobs(jobs)
