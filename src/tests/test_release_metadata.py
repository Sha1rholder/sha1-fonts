"""核验发布字体与报告不嵌入动态发布编号"""

import json
import os
import subprocess
import unittest
from typing import Any, cast

from fontTools.ttLib import TTFont

from lib import DIST, ROOT
from verification.metadata import check_release_metadata


class ReleaseMetadataTests(unittest.TestCase):
	def test_generated_assets_have_no_release_version(self):
		manifest = json.loads((DIST / "manifest.json").read_text())
		verification = json.loads((DIST / "verification.json").read_text())
		self.assertNotIn("version", manifest)
		self.assertNotIn("version", verification)
		self.assertEqual(len(manifest["fonts"]), 10)
		for entry in manifest["fonts"]:
			with self.subTest(file=entry["file"]), TTFont(DIST / entry["file"]) as font:
				check_release_metadata(font, entry["file"])

	def test_release_number_does_not_change_font_bytes(self):
		code = """
import hashlib, io, json
from fontTools.ttLib import TTFont
from build.masters import master_font
from lib import FAMILIES, TEMP, variable_path
job = json.loads((TEMP / 'jobs.json').read_text())[0]
config = FAMILIES[job['family']]
with TTFont(variable_path(config['source'], job['italic']), recalcTimestamp=False) as original:
    font = master_font(job, config, original)
    output = io.BytesIO()
    font.save(output)
    print(hashlib.sha256(output.getvalue()).hexdigest())
"""
		hashes = []
		for number in ("1", "42"):
			result = subprocess.run(
				["uv", "run", "--frozen", "python", "-c", code],
				cwd=ROOT / "src",
				env={**os.environ, "SHA1_RELEASE_NUMBER": number},
				capture_output=True,
				text=True,
				check=True,
			)
			hashes.append(result.stdout.strip())
		self.assertEqual(hashes[0], hashes[1])

	def test_reject_embedded_release_version(self):
		manifest = json.loads((DIST / "manifest.json").read_text())
		entry = manifest["fonts"][0]
		for field in ("name", "head", "identifier"):
			with self.subTest(field=field), TTFont(DIST / entry["file"]) as font:
				if field == "name":
					font["name"].setName("Version 42.000", 5, 3, 1, 0x409)
				elif field == "head":
					cast(Any, font["head"]).fontRevision = 42
				else:
					font["name"].setName("42.000;SHA1;Test", 3, 3, 1, 0x409)
				with self.assertRaises(AssertionError):
					check_release_metadata(font, entry["file"])
