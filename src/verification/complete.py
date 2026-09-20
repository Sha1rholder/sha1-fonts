"""核验完整字体的来源覆盖、变量轮廓及无需回退的映射"""

import hashlib

from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont

from lib import (
	FamilyConfig,
	complete_font_path,
	font_path,
	patch_codepoints,
	subset_font,
	variable_path,
)

from .geometry import best_cmap, require
from .metadata import check_version


def verify_complete_family(config: FamilyConfig, italic: bool, version: str) -> dict:
	"""核验完整字体覆盖、元数据及三类来源在变量轴上的结果"""
	path = complete_font_path(config, italic)
	with (
		TTFont(path, checkChecksums=2, recalcTimestamp=False) as complete,
		TTFont(variable_path(config["source"], italic), recalcTimestamp=False) as base,
		TTFont(font_path(config, italic), recalcTimestamp=False) as patch,
	):
		expected = dict(best_cmap(base))
		if not italic:
			with TTFont(variable_path(config["cjk"]), recalcTimestamp=False) as cjk:
				for codepoint, name in best_cmap(cjk).items():
					expected.setdefault(codepoint, name)
			expected.update(best_cmap(patch))
		_require_metadata(complete, config, italic)
		check_version(complete, version, config["complete"])
		require(
			set(best_cmap(complete)) == set(expected),
			f"Complete coverage: {config['complete']} {italic}",
		)
		_require_source_samples(
			path,
			variable_path(config["source"], italic),
			font_path(config, italic),
			config,
			italic,
		)
	report = {
		"family": config["complete"],
		"style": "italic" if italic else "normal",
		"glyphs": complete["maxp"].numGlyphs,
		"codepoints": len(best_cmap(complete)),
		"bytes": path.stat().st_size,
		"sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
	}
	print(
		f"Verified {config['complete']} {'Italic' if italic else 'Roman'}: {report['codepoints']} codepoints",
		flush=True,
	)
	return report


def _require_metadata(font: TTFont, config: FamilyConfig, italic: bool) -> None:
	"""确认完整字体保留两个可变轴并以独立家族名发布"""
	require(
		[
			(axis.axisTag, axis.minValue, axis.defaultValue, axis.maxValue)
			for axis in font["fvar"].axes
		]
		== [("wght", config["minimum"], 400, 900), ("wdth", 62.5, 100, 100)],
		f"Complete axes: {config['complete']}",
	)
	require(
		"gvar" in font and "STAT" in font and "HVAR" not in font,
		f"Complete variation tables: {config['complete']}",
	)
	require(
		font["name"].getDebugName(1) == config["complete"]
		and font["name"].getDebugName(2) == ("Italic" if italic else "Regular"),
		f"Complete naming: {config['complete']}",
	)


def _require_source_samples(
	complete_path,
	base_path,
	patch_path,
	config: FamilyConfig,
	italic: bool,
) -> None:
	"""比较补丁、拉丁来源和直立SC来源的代表性变量字形"""
	patch_codepoint = next(iter(patch_codepoints(config, italic)))
	_sample_matches(complete_path, patch_path, patch_codepoint, config, italic)
	_sample_matches(complete_path, base_path, 0x41, config, italic, tolerance=1)
	if not italic:
		_sample_matches(
			complete_path,
			variable_path(config["cjk"]),
			0x4E2D,
			config,
			italic,
			tolerance=2,
		)


def _sample_matches(
	complete_path,
	source_path,
	codepoint: int,
	config: FamilyConfig,
	italic: bool,
	tolerance: int = 0,
) -> None:
	"""在低、常规和高字重位置比较一个来源字形的轮廓和步进"""
	with (
		subset_font(complete_path, (codepoint,)) as complete_subset,
		subset_font(source_path, (codepoint,)) as source_subset,
	):
		source_axes = {axis.axisTag for axis in source_subset["fvar"].axes}
		for weight in (config["minimum"], 400, 900):
			with (
				instantiateVariableFont(
					complete_subset,
					{"wght": weight, "wdth": 100},
					inplace=False,
				) as complete_instance,
				instantiateVariableFont(
					source_subset,
					{
						axis: value
						for axis, value in {"wght": weight, "wdth": 100}.items()
						if axis in source_axes
					},
					inplace=False,
				) as source_instance,
			):
				complete_name = best_cmap(complete_instance)[codepoint]
				source_name = best_cmap(source_instance)[codepoint]
				complete_coordinates = complete_instance["glyf"][
					complete_name
				].getCoordinates(complete_instance["glyf"])[0]
				source_coordinates = source_instance["glyf"][
					source_name
				].getCoordinates(source_instance["glyf"])[0]
				require(
					len(complete_coordinates) == len(source_coordinates)
					and all(
						abs(complete_value - source_value) <= tolerance
						for complete_point, source_point in zip(
							complete_coordinates, source_coordinates
						)
						for complete_value, source_value in zip(
							complete_point, source_point
						)
					),
					f"Complete source outline: {config['complete']} {codepoint:04X}",
				)
				require(
					all(
						abs(complete_value - source_value) <= tolerance
						for complete_value, source_value in zip(
							complete_instance["hmtx"][complete_name],
							source_instance["hmtx"][source_name],
						)
					),
					f"Complete source advance: {config['complete']} {codepoint:04X}",
				)
