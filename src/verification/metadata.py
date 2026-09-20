"""核验发布清单、命名、样式标记与变量字体表"""

from typing import Any, cast

import lib as sources
from lib import (
	DIST,
	FAMILIES,
	VERSION,
	complete_font_path,
	font_path,
	italic_styles,
	patch_codepoints,
	style_name,
)

from .geometry import best_cmap, require


def check_manifest(manifest):
	"""核验来源哈希以及发布家族样式的完整覆盖"""
	require(
		manifest["sources_sha256"] == sources.source_hashes(), "Source hashes changed"
	)
	expected_styles = {
		(
			config["patch"],
			"italic" if italic else "normal",
			str(font_path(config, italic).relative_to(DIST)),
		)
		for key, config in FAMILIES.items()
		for italic in italic_styles(key)
	}
	expected_styles.update(
		{
			(
				config["complete"],
				"italic" if italic else "normal",
				str(complete_font_path(config, italic).relative_to(DIST)),
			)
			for key, config in FAMILIES.items()
			for italic in italic_styles(key)
		}
	)
	require(
		len(manifest["fonts"]) == len(expected_styles)
		and {
			(entry["family"], entry["style"], entry["file"])
			for entry in manifest["fonts"]
		}
		== expected_styles,
		"Manifest style coverage",
	)


def check_font(font, key, config, italic, family_jobs, postscript_names):
	"""核验一个家族样式的元数据并记录全局唯一名称"""
	label = f"{key} {'Italic' if italic else 'Roman'}"
	codepoints = patch_codepoints(config, italic)
	require(set(best_cmap(font)) == set(codepoints), f"Unexpected cmap: {label}")
	require(
		len(font.getGlyphOrder()) == len(codepoints) + 1,
		f"Unexpected extra glyphs: {label}",
	)
	require(
		[
			(axis.axisTag, axis.minValue, axis.defaultValue, axis.maxValue)
			for axis in font["fvar"].axes
		]
		== [("wght", config["minimum"], 400, 900), ("wdth", 62.5, 100, 100)],
		f"Axis ranges: {key}",
	)
	require(len(font["fvar"].instances) == len(family_jobs), f"Instance count: {key}")
	require(
		{
			tuple(sorted(instance.coordinates.items()))
			for instance in font["fvar"].instances
		}
		== {
			tuple(sorted({"wght": job["weight"], "wdth": job["width"]}.items()))
			for job in family_jobs
		},
		f"Instance coverage: {key}",
	)
	require(
		"gvar" in font and "HVAR" in font and "STAT" in font,
		f"Missing variation tables: {key}",
	)
	require(
		font["name"].getDebugName(5) == f"Version {VERSION}", f"Font version: {key}"
	)
	head = cast(Any, font["head"])
	require(
		abs(head.fontRevision - float(VERSION)) <= 1 / 65536,
		f"Font revision: {key}",
	)
	for name_id in (1, 4, 6, 16, 25):
		debug_name = font["name"].getDebugName(name_id)
		if debug_name is None:
			raise AssertionError(f"Missing name record: {key} {name_id}")
		require(debug_name.startswith("Sha1"), f"Derived naming: {key} {name_id}")
	os2 = cast(Any, font["OS/2"])
	require(
		os2.fsType == 0 and bool(os2.fsSelection & 1) == italic,
		f"Embedding/italic flags: {label}",
	)
	require(
		bool(os2.fsSelection & 0x40) != italic and bool(head.macStyle & 2) == italic,
		f"Regular/mac italic flags: {label}",
	)
	require(
		font["name"].getDebugName(2) == ("Italic" if italic else "Regular")
		and font["name"].getDebugName(16) == config["patch"],
		f"Style linking: {label}",
	)
	post = cast(Any, font["post"])
	hhea = cast(Any, font["hhea"])
	require(
		post.italicAngle == family_jobs[0]["italic_angle"]
		and (post.italicAngle < 0) == italic,
		f"Italic angle: {label}",
	)
	require(
		(hhea.caretSlopeRise, hhea.caretSlopeRun)
		== (family_jobs[0]["caret_slope_rise"], family_jobs[0]["caret_slope_run"]),
		f"Caret slope: {label}",
	)
	stat = font["STAT"].table
	require(
		[axis.AxisTag for axis in stat.DesignAxisRecord.Axis]
		== ["wght", "wdth", "ital"],
		f"STAT style axes: {label}",
	)
	style_values = [
		value for value in stat.AxisValueArray.AxisValue if value.AxisIndex == 2
	]
	require(
		len(style_values) == 1 and style_values[0].Value == int(italic),
		f"STAT italic value: {label}",
	)
	for name_id in (6, 25):
		name = font["name"].getDebugName(name_id)
		require(name not in postscript_names, f"Duplicate PostScript name: {name}")
		postscript_names.add(name)
	for instance in font["fvar"].instances:
		expected_name = style_name(
			instance.coordinates["wght"], instance.coordinates["wdth"], italic
		)
		require(
			font["name"].getDebugName(instance.subfamilyNameID) == expected_name,
			f"Named instance style: {label}",
		)
