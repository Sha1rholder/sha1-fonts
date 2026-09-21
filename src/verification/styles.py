"""核验供体样式、斜体覆盖和回退字体的字重表现"""

import math
from copy import deepcopy
from typing import Any, cast

from fontTools.pens.areaPen import AreaPen
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont

import lib as sources
from lib import FAMILIES, QUOTES, font_path, italic_styles, variable_path

from .geometry import best_cmap, bounds, require

ITALIC_CODEPOINTS = {
	"sans": {0x2D, 0x30, 0x31, 0x4F, 0x6C, 0x7C, 0x2026, *QUOTES},
	"serif": {0x2D, 0x30, 0x31, 0x4F, 0x7C, 0x2026},
}
SLANTED_CODEPOINTS = {
	"sans": {0x6C},
	"mono": set(),
	"serif": set(),
}


def check_style_sources(job, base, cjk, alternate, quotes):
	"""核对各借用来源的样式选择和预期的直立回退"""
	require(
		set(job["slanted_codepoints"])
		== (SLANTED_CODEPOINTS[job["family"]] if job["italic"] else set()),
		f"Incomplete constructed obliques: {job['family']}",
	)
	for role, font, has_italic in (
		("base", base, job["family"] != "mono"),
		("cjk", cjk, False),
		("alternate", alternate, False),
		("quotes", quotes, True),
	):
		if font is not None:
			require(
				bool(font["OS/2"].fsSelection & 1) == (job["italic"] and has_italic),
				f"Wrong donor style: {job['family']} {role}",
			)


def check_italic_coverage(instance, upright, job):
	"""核对斜体覆盖，并防止关键字符退回直立轮廓"""
	require(
		set(best_cmap(instance)) == ITALIC_CODEPOINTS[job["family"]],
		f"Unexpected italic coverage: {job['family']}",
	)
	reference = instantiateVariableFont(
		upright, {"wght": job["weight"], "wdth": job["width"]}, inplace=False
	)
	changed = set()
	for cp in best_cmap(instance):
		if cp not in best_cmap(reference):
			continue
		name = best_cmap(instance)[cp]
		glyph, original = instance["glyf"][name], reference["glyf"][name]
		if (
			glyph.coordinates != original.coordinates
			or glyph.endPtsOfContours != original.endPtsOfContours
			or glyph.flags != original.flags
			or instance["hmtx"][name] != reference["hmtx"][name]
		):
			changed.add(cp)
	require(
		(
			{0x30, 0x31, 0x4F, 0x6C}
			if job["family"] == "sans"
			else {0x31}
			if job["family"] == "mono"
			else {0x30, 0x31, 0x4F}
		)
		<= changed,
		f"Missing italic outlines: {job['family']}",
	)
	reference.close()


def check_latin_styles():
	"""逐字验证拉丁字符的字体内样式和粗体轮廓，保留来源固定线宽的下划线"""
	codepoints = (*range(0x21, 0x7F), *QUOTES)
	reports = []
	for key, config in FAMILIES.items():
		for italic in italic_styles(key):
			patch = TTFont(font_path(config, italic))
			source = sources.subset_font(
				variable_path(config["source"], italic), codepoints
			)
			instances = {
				(font, weight): instantiateVariableFont(
					font, {"wght": weight, "wdth": 100}, inplace=False
				)
				for font in (patch, source)
				for weight in (400, 700)
			}
			for cp in codepoints:
				font = patch if cp in best_cmap(patch) else source
				require(cp in best_cmap(font), f"Missing Latin glyph: {key} {cp:04X}")
				os2 = cast(Any, font["OS/2"])
				expected_italic = italic and not (
					key == "mono" and cp not in best_cmap(patch)
				)
				require(
					bool(os2.fsSelection & 1) == expected_italic,
					f"Missing font style: {key} {italic} {cp:04X}",
				)
				areas = []
				for weight in (400, 700):
					instance = instances[(font, weight)]
					glyph_set = instance.getGlyphSet()
					pen = AreaPen(glyph_set)
					glyph_set[best_cmap(instance)[cp]].draw(pen)
					areas.append(abs(pen.value))
				name = best_cmap(font)[cp]
				require(
					all(
						instances[(font, weight)]["OS/2"].usWeightClass == weight
						for weight in (400, 700)
					),
					f"Wrong native weight: {key} {italic} {cp:04X}",
				)
				# 原始Serif下划线跨字重共用轮廓，保留该来源设计
				if cp != 0x5F:
					outlines = [
						instances[(font, weight)]["glyf"][name].getCoordinates(
							instances[(font, weight)]["glyf"]
						)[0]
						for weight in (400, 700)
					]
					require(
						outlines[0] != outlines[1],
						f"Identical regular and bold outlines: {key} {italic} {cp:04X}",
					)
					require(
						areas[1] > areas[0] * 1.01,
						f"Missing bold outline: {key} {italic} {cp:04X} {areas}",
					)
			for font in (*instances.values(), patch, source):
				font.close()
			reports.append(
				{
					"family": config["patch"],
					"style": "italic" if italic else "normal",
					"glyphs": len(codepoints),
				}
			)
	print(
		f"Verified Latin styles and bold outlines for 98 Latin glyphs in all {len(reports)} faces",
		flush=True,
	)
	return reports


def upright_geometry(instance, job):
	"""反向展开构建时的倾斜，以独立核验原补丁形状和步进"""
	geometry = deepcopy(instance)
	slope = math.tan(math.radians(-job["italic_angle"]))
	for cp in job["slanted_codepoints"]:
		name = best_cmap(geometry)[cp]
		glyph = geometry["glyf"][name]
		_, bottom, _, top = bounds(geometry, cp)
		for index, (x, y) in enumerate(glyph.coordinates):
			glyph.coordinates[index] = (x - slope * (y - (bottom + top) / 2), y)
		glyph.recalcBounds(geometry["glyf"])
		geometry["hmtx"][name] = (geometry["hmtx"][name][0], glyph.xMin)
	return geometry
