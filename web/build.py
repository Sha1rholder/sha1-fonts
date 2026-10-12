"""构建独立展示页；仅使用Patch与保留可变轴的Noto子集"""

import hashlib
import io
import json
import os
import shutil
import sys
from concurrent.futures import ProcessPoolExecutor
from html.parser import HTMLParser
from pathlib import Path

from fontTools import __version__, subset
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont
from fontTools.ttLib.woff2 import WOFF2FlavorData

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
OUTPUT = ROOT / "dist"
CACHE = ROOT / "temp" / "web-fonts"
sys.path.insert(0, str(ROOT / "src"))
from lib import (
	EPOCH,
	FAMILIES,
	font_path,
	italic_styles,
	patch_codepoints,
	variable_path,
)


def ranges(codepoints):
	"""将实际覆盖压缩成不重叠的闭区间"""
	result = []
	for point in sorted(set(codepoints)):
		if result and point == result[-1][1] + 1:
			result[-1][1] = point
		else:
			result.append([point, point])
	return result


class SampleText(HTMLParser):
	"""只提取字体样本，页面说明使用系统字体"""

	def __init__(self):
		super().__init__()
		self.points = set(range(0x20, 0x7F))
		self.in_textarea = False

	def handle_starttag(self, tag, attrs):
		attributes = dict(attrs)
		self.points.update(map(ord, attributes.get("data-text", "")))
		if tag == "textarea" and attributes.get("id") == "test-text":
			self.in_textarea = True

	def handle_endtag(self, tag):
		if tag == "textarea":
			self.in_textarea = False

	def handle_data(self, data):
		if self.in_textarea:
			self.points.update(map(ord, data))


def chunks_for(codepoints, seed, patch=False):
	"""基础子集优先，其余按256码位区间分片，Patch保持独立"""
	points = set(codepoints)
	if patch:
		return [points]
	chunks = [points & seed] if points & seed else []
	buckets = {}
	for point in sorted(points - seed):
		buckets.setdefault(point // 256, set()).add(point)
	return chunks + list(buckets.values())


def encode_subset(path, points):
	options = subset.Options()
	options.name_IDs = [0, 1, 2, 3, 4, 5, 6, 13, 14, 16, 17, 25]
	options.name_legacy = True
	options.name_languages = ["*"]
	with TTFont(path, recalcTimestamp=False) as font:
		expected_axes = {
			axis.axisTag: (axis.minValue, axis.maxValue) for axis in font["fvar"].axes
		}
		worker = subset.Subsetter(options=options)
		worker.populate(unicodes=points)
		worker.subset(font)
		# GSUB闭包可能保留同字形的其他Unicode别名，限制cmap以免跨片重叠
		for table in font["cmap"].tables:
			if table.isUnicode() and hasattr(table, "cmap"):
				table.cmap = {
					point: name for point, name in table.cmap.items() if point in points
				}
		assert set(font.getBestCmap()) == set(points), (
			f"Subset coverage mismatch: {path}"
		)
		assert expected_axes == {
			axis.axisTag: (axis.minValue, axis.maxValue) for axis in font["fvar"].axes
		}
		font.flavor = "woff2"
		buffer = io.BytesIO()
		font.save(buffer)
		return buffer.getvalue()


def build_source(task):
	key, path, seed, is_patch = task
	path = Path(path)
	source_hash = hashlib.sha256(path.read_bytes()).hexdigest()
	with TTFont(path) as font:
		points = set(font.getBestCmap())
		axes = {
			axis.axisTag: [axis.minValue, axis.maxValue] for axis in font["fvar"].axes
		}
		names = list(
			dict.fromkeys(font["name"].getDebugName(index) for index in (4, 6))
		)
	result = {
		"axes": axes,
		"ranges": ranges(points),
		"local": [name for name in names if name] if not is_patch else [],
		"chunks": [],
	}
	for index, chunk in enumerate(chunks_for(points, seed, is_patch)):
		cache_key = hashlib.sha256(
			f"v1/{__version__}/{source_hash}/{sorted(chunk)}".encode()
		).hexdigest()
		cached = CACHE / f"{cache_key}.woff2"
		if not cached.exists():
			cached.write_bytes(encode_subset(path, chunk))
		data = cached.read_bytes()
		filename = f"fonts/{key}-{hashlib.sha256(data).hexdigest()[:12]}.woff2"
		shutil.copyfile(cached, OUTPUT / filename)
		result["chunks"].append(
			{
				"file": filename,
				"ranges": ranges(chunk),
				"bytes": len(data),
				"base": index == 0,
			}
		)
	print(f"{key}: {len(result['chunks'])} subsets", flush=True)
	return key, result


def coverage_guard(points, width):
	"""检测字体通过size-adjust产生不同步进，确认本地字符覆盖"""
	builder = FontBuilder(1000, isTTF=True)
	points = sorted(points)
	names = [f"u{point:x}" for point in points]
	order = [".notdef", "guard", *names]
	builder.setupGlyphOrder(order)
	pen = TTGlyphPen(None)
	pen.moveTo((50, 0))
	pen.lineTo((width - 50, 0))
	pen.lineTo((width - 50, 700))
	pen.lineTo((50, 700))
	pen.closePath()
	glyph = pen.glyph()
	component = TTGlyphPen({"guard": glyph})
	component.addComponent("guard", (1, 0, 0, 1, 0, 0))
	builder.setupGlyf(
		{
			".notdef": TTGlyphPen(None).glyph(),
			"guard": glyph,
			**dict.fromkeys(names, component.glyph()),
		}
	)
	builder.setupHorizontalMetrics(dict.fromkeys(order, (width, 0)))
	builder.setupHorizontalHeader(ascent=1000, descent=-200)
	# 保留BMP与完整Unicode兼容表；连续GID共享轮廓，WOFF2压缩重复组件
	builder.setupCharacterMap(dict(zip(points, names)))
	builder.setupNameTable(
		{
			"familyName": f"Sha1 Coverage Guard {width}",
			"styleName": "Regular",
			"uniqueFontIdentifier": f"Sha1CoverageGuard{width}",
			"fullName": f"Sha1 Coverage Guard {width}",
			"psName": f"Sha1CoverageGuard{width}",
		}
	)
	builder.setupOS2(
		sTypoAscender=1000, sTypoDescender=-200, usWinAscent=1000, usWinDescent=200
	)
	builder.setupPost(keepGlyphNames=False)
	builder.font.recalcTimestamp = False
	builder.font["head"].created = builder.font["head"].modified = EPOCH
	builder.font.flavor = "woff2"
	# 避免浏览器WOFF2解码器拒绝大量重复组件的glyf变换
	builder.font.flavorData = WOFF2FlavorData(transformedTables=set())
	buffer = io.BytesIO()
	builder.font.save(buffer)
	return buffer.getvalue()


def main():
	for key, config in FAMILIES.items():
		for italic in italic_styles(key):
			path = font_path(config, italic)
			if not path.is_file():
				raise SystemExit(
					"Missing Patch fonts. Run: uv run --project src python src/main.py build"
				)
			with TTFont(path) as font:
				if set(font.getBestCmap()) != set(patch_codepoints(config, italic)):
					raise SystemExit(
						f"Patch character set is stale: {path}. Rebuild the fonts first."
					)
	if not (ROOT / "Sha1" / "OFL.txt").is_file():
		raise SystemExit("Missing Sha1/OFL.txt; rebuild the fonts first")
	parser = SampleText()
	parser.feed((WEB / "index.html").read_text())
	OUTPUT.mkdir(exist_ok=True)
	(OUTPUT / "fonts").mkdir(exist_ok=True)
	(OUTPUT / "licenses").mkdir(exist_ok=True)
	CACHE.mkdir(parents=True, exist_ok=True)
	tasks, families, seen = [], {}, set()
	for key, config in FAMILIES.items():
		family = {
			"patch": f"{key}-patch",
			"latin": f"{key}-latin",
			"cjk": f"{config['cjk']}-web",
		}
		for italic in italic_styles(key):
			suffix = "-italic" if italic else ""
			tasks.append(
				(
					f"{key}-patch{suffix}",
					str(font_path(config, italic)),
					parser.points,
					True,
				)
			)
			tasks.append(
				(
					f"{key}-latin{suffix}",
					str(variable_path(config["source"], italic)),
					parser.points,
					False,
				)
			)
			if italic:
				family.update(
					{
						"patchItalic": f"{key}-patch-italic",
						"latinItalic": f"{key}-latin-italic",
					}
				)
		if family["cjk"] not in seen:
			tasks.append(
				(family["cjk"], str(variable_path(config["cjk"])), parser.points, False)
			)
			seen.add(family["cjk"])
		families[key] = family
	with ProcessPoolExecutor(max_workers=min(4, os.cpu_count() or 1)) as pool:
		fonts = dict(pool.map(build_source, tasks))
	all_points = {
		point
		for font in fonts.values()
		for start, end in font["ranges"]
		for point in range(start, end + 1)
	}
	guard = coverage_guard(all_points, 400)
	guard_file = f"fonts/coverage-guard-{hashlib.sha256(guard).hexdigest()[:12]}.woff2"
	(OUTPUT / guard_file).write_bytes(guard)
	manifest = {
		"families": families,
		"fonts": fonts,
		"guard": {"file": guard_file, "bytes": len(guard)},
	}
	(OUTPUT / "fonts.json").write_text(
		json.dumps(manifest, ensure_ascii=False, separators=(",", ":")) + "\n"
	)
	for filename in ("index.html", "style.css", "app.js"):
		shutil.copyfile(WEB / filename, OUTPUT / filename)
	shutil.copyfile(ROOT / "Sha1" / "OFL.txt", OUTPUT / "licenses" / "Sha1-OFL.txt")
	for license_file in sorted((ROOT / "Noto").glob("*/OFL.txt")):
		shutil.copyfile(
			license_file, OUTPUT / "licenses" / f"{license_file.parent.name}-OFL.txt"
		)
	used = {chunk["file"] for font in fonts.values() for chunk in font["chunks"]}
	used.add(guard_file)
	for artifact in (OUTPUT / "fonts").glob("*.woff2"):
		if artifact.relative_to(OUTPUT).as_posix() not in used:
			artifact.unlink()
	base_bytes = sum(
		font["chunks"][0]["bytes"] for key, font in fonts.items() if "italic" not in key
	)
	print(
		f"Built {OUTPUT}\nNormal base fonts: {base_bytes:,} bytes; manifest: {(OUTPUT / 'fonts.json').stat().st_size:,} bytes"
	)


if __name__ == "__main__":
	main()
