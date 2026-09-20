"""核验动态发布编号和两套字体实际写入的版本元数据"""

import json
import os
import subprocess
import unittest
from typing import Any, cast
from unittest.mock import patch

from fontTools.ttLib import TTFont

from lib import DIST, ROOT, release_version
from verification.metadata import check_version


class ReleaseVersionTests(unittest.TestCase):
	"""覆盖环境注入、非法编号和完整字体继承旧版本的回归"""

	def test_release_number_range(self):
		"""发布编号应生成定点数可表示的整数版本"""
		for number in ("0", "1", "42", "32767"):
			with self.subTest(number=number):
				self.assertEqual(release_version(number), f"{number}.000")
		for number in ("", "01", "-1", "1.131", "1e3", "32768", "2\n", "\u0661"):
			with self.subTest(number=number), self.assertRaises(ValueError):
				release_version(number)

	def test_version_from_environment(self):
		"""新进程应读取构建环境中的编号且本地默认版本为零"""
		for number, expected in ((None, "0.000"), ("42", "42.000")):
			with self.subTest(number=number), patch.dict(os.environ):
				os.environ.pop("SHA1_RELEASE_NUMBER", None)
				if number is not None:
					os.environ["SHA1_RELEASE_NUMBER"] = number
				result = subprocess.run(
					[
						"uv",
						"run",
						"--frozen",
						"python",
						"-c",
						"from lib import VERSION; print(VERSION)",
					],
					cwd=ROOT / "src",
					capture_output=True,
					text=True,
					check=True,
				)
				self.assertEqual(result.stdout.strip(), expected)

	def test_generated_font_versions(self):
		"""十个实际字体的版本记录均应与发布清单一致"""
		manifest = json.loads((DIST / "manifest.json").read_text(encoding="ascii"))
		version = manifest["version"]
		self.assertEqual(len(manifest["fonts"]), 10)
		for entry in manifest["fonts"]:
			with self.subTest(file=entry["file"]), TTFont(DIST / entry["file"]) as font:
				self.assertEqual(font["name"].getDebugName(5), f"Version {version}")
				self.assertEqual(cast(Any, font["head"]).fontRevision, float(version))
				identifier = font["name"].getDebugName(3)
				assert identifier is not None
				self.assertTrue(identifier.startswith(f"{version};SHA1;"))

	def test_reject_mismatched_version_records(self):
		"""验证器应拒绝旧版本字符串和错误的字体头版本"""
		manifest = json.loads((DIST / "manifest.json").read_text(encoding="ascii"))
		entry = manifest["fonts"][0]
		for field in ("name", "head"):
			with self.subTest(field=field), TTFont(DIST / entry["file"]) as font:
				if field == "name":
					font["name"].setName("Version 1.131", 5, 3, 1, 0x409)
				else:
					cast(Any, font["head"]).fontRevision = 1.131
				with self.assertRaises(AssertionError):
					check_version(font, manifest["version"], entry["file"])
