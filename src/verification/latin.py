"""核验拉丁补丁的供体轮廓、笔画、字腔和步进"""

import math
from array import array
from copy import deepcopy

from fontTools.pens.areaPen import AreaPen
from fontTools.ttLib.tables._g_l_y_f import GlyphCoordinates

from lib import QUOTES

from .geometry import (
	best_cmap,
	bounds,
	check_source_contour,
	check_source_points,
	contour_bounds,
	contour_glyph,
	ink_at,
	require,
)


def check_quotes(font, quotes, family, position):
	"""核对引号沿用对应样式的Serif轮廓并只作预期等宽适配"""
	for cp in QUOTES:
		glyph = font["glyf"][best_cmap(font)[cp]]
		source = quotes["glyf"][best_cmap(quotes)[cp]]
		require(
			glyph.numberOfContours == source.numberOfContours,
			f"Quote contour count: {position} {cp:04X}",
		)
		width = font["hmtx"][best_cmap(font)[cp]][0]
		if family == "mono":
			left, _, right, _ = bounds(quotes, cp)
			scale = min(1, width * 0.8 / (right - left))
			check_source_points(
				glyph,
				source,
				scale_x=scale,
				offset_x=(width - scale * (left + right)) / 2,
			)
		else:
			check_source_points(glyph, source)
			require(
				width == quotes["hmtx"][best_cmap(quotes)[cp]][0],
				f"Quote advance: {position} {cp:04X}",
			)


def check_bar(font, base, position):
	"""核对加长竖线的笔画、居中圆点和原步进"""
	glyph = font["glyf"][best_cmap(font)[0x7C]]
	require(glyph.numberOfContours == 2, f"Bar contour count: {position}")
	stroke, dot = contour_bounds(glyph, 0), contour_bounds(glyph, 1)
	source = bounds(base, 0x7C)
	require(
		abs(stroke[3] - base["hhea"].ascent) <= 1.1
		and abs(stroke[1] - base["hhea"].descent) <= 1.1,
		f"Bar full height: {position}",
	)
	require(
		abs(stroke[0] - source[0]) <= 1.1 and abs(stroke[2] - source[2]) <= 1.1,
		f"Bar thickness: {position}",
	)
	require(dot[0] < stroke[0] and dot[2] > stroke[2], f"Invisible bar dot: {position}")
	require(
		abs(dot[0] + dot[2] - stroke[0] - stroke[2]) <= 1.1
		and abs(dot[1] + dot[3] - stroke[1] - stroke[3]) <= 1.1,
		f"Bar dot center: {position}",
	)
	require(
		abs(
			font["hmtx"][best_cmap(font)[0x7C]][0]
			- base["hmtx"][best_cmap(base)[0x7C]][0]
		)
		<= 1,
		f"Bar advance: {position}",
	)


def stem_edges(glyph, height):
	"""测量穿过指定高度的直线竖干边界"""
	hits = []
	start = 0
	for end in glyph.endPtsOfContours:
		points = list(glyph.coordinates[start : end + 1])
		flags = list(glyph.flags[start : end + 1])
		for index, (a, b) in enumerate(zip(points, points[1:] + points[:1])):
			if (
				flags[index] & 1
				and flags[(index + 1) % len(flags)] & 1
				and min(a[1], b[1]) < height < max(a[1], b[1])
			):
				hits.append(a[0] + (b[0] - a[0]) * (height - a[1]) / (b[1] - a[1]))
		start = end + 1
	return min(hits), max(hits)


def check_one(font, base, family, position):
	"""独立核验实心尖顶、家族底横及收窄后的Sans步进"""
	name, source_name = best_cmap(font)[0x31], best_cmap(base)[0x31]
	glyph, source = deepcopy(font["glyf"][name]), deepcopy(base["glyf"][source_name])
	require(
		glyph.numberOfContours == (1 if family == "serif" else 2),
		f"One flag/foot contour count: {position}",
	)
	advance, source_advance = font["hmtx"][name][0], base["hmtx"][source_name][0]
	require(
		abs(advance - source_advance * (0.85 if family == "sans" else 1)) <= 1.1,
		f"One advance: {position}",
	)
	offset = (advance - source_advance) / 2
	slope = math.tan(math.radians(-base["post"].italicAngle))
	for outline, shift in ((glyph, offset), (source, 0)):
		for index, (x, y) in enumerate(outline.coordinates):
			outline.coordinates[index] = (x - slope * y - shift, y)
	_, bottom, _, top = bounds(base, 0x31)
	height = top - bottom
	body = contour_bounds(glyph, 0)
	require(
		abs(body[1] - bottom) <= 1.1 and abs(body[3] - top) <= 1.1,
		f"One cap height: {position}",
	)
	stem = contour_glyph(glyph, 0)
	source_stem = max(
		(contour_glyph(source, index) for index in range(source.numberOfContours)),
		key=lambda contour: (
			contour_bounds(contour, 0)[3] - contour_bounds(contour, 0)[1]
		),
	)
	for row in (0.25, 0.3, 0.35):
		y = bottom + height * row
		left, right = stem_edges(stem, y)
		require(
			all(
				abs(a - b) <= 2.1
				for a, b in zip((left, right), stem_edges(source_stem, y))
			),
			f"One native stem: {position}",
		)
	thickness = right - left
	for index in range(glyph.numberOfContours):
		pen = AreaPen()
		contour_glyph(glyph, index).draw(pen, None)
		require(pen.value < 0, f"One solid winding: {position}")
	points = list(stem.coordinates)
	peaks = [index for index, point in enumerate(points) if abs(point[1] - top) <= 1.1]
	require(len(peaks) == 1, f"One single apex: {position}")
	peak = peaks[0]
	apex, tip, following = (
		points[peak],
		points[peak - 1],
		points[(peak + 1) % len(points)],
	)
	require(
		stem.flags[peak] & 1
		and stem.flags[peak - 1] & 1
		and abs(apex[0] - right) <= 2.1
		and tip[0] < left - thickness * 0.15
		and abs(tip[1] - (top - height * 0.18)) <= 1.1
		and abs(following[0] - right) <= 2.1
		and following[1] < bottom + height * 0.6,
		f"One seamless triangular head: {position}",
	)
	for row in (0.15, 0.45, 0.75):
		y = tip[1] + (apex[1] - tip[1]) * row
		edge = tip[0] + (apex[0] - tip[0]) * row
		for column in (0.2, 0.5, 0.8):
			x = edge + (right - edge) * column
			require(
				ink_at(font, 0x31, x + slope * y + offset, y),
				f"One solid flag: {position}",
			)
	if family == "serif":
		# 核对缩短后的原生曲线，避免把衬线替换为Sans矩形
		lower = deepcopy(source)
		indices = [
			index
			for index, point in enumerate(source.coordinates)
			if point[1] < bottom + height * 0.4
		]
		lower.coordinates = GlyphCoordinates(
			[source.coordinates[index] for index in indices]
		)
		for index, source_index in enumerate(indices):
			x, y = source.coordinates[source_index]
			edge = min(max(x, left), right)
			lower.coordinates[index] = (edge + (x - edge) * 0.8, y)
		lower.flags = array("B", [source.flags[index] for index in indices])
		check_source_points(glyph, lower)
		foot_left = min(x for x, y in glyph.coordinates if y < bottom + height * 0.4)
		require(
			left - tip[0] >= (left - foot_left) * 0.9 - 1.5,
			f"One flag/foot reach: {position}",
		)
		require(
			any(
				not flag & 1
				for point, flag in zip(stem.coordinates, stem.flags)
				if point[1] > bottom + height * 0.6
			),
			f"One serif shoulder: {position}",
		)
		return
	foot = contour_bounds(glyph, 1)
	require(
		left - tip[0] >= (left - foot[0]) * 0.9 - 1.5,
		f"One flag/foot reach: {position}",
	)
	require(
		foot[0] < left - thickness * 0.15
		and foot[2] > right + thickness * 0.15
		and abs(foot[1] - bottom) <= 1.1
		and bottom < foot[3] < bottom + height * 0.3,
		f"One short foot: {position}",
	)
	if family == "mono":
		source_foot = min(
			(contour_bounds(source, index) for index in range(source.numberOfContours)),
			key=lambda box: box[3] - box[1],
		)
		require(
			abs(foot[2] - foot[0] - (source_foot[2] - source_foot[0]) * 0.8) <= 2.1
			and abs(foot[0] + foot[2] - source_foot[0] - source_foot[2]) <= 2.1
			and abs(foot[3] - source_foot[3]) <= 1.1,
			f"One shortened mono foot: {position}",
		)
	else:
		require(
			foot[2] - foot[0] < advance * 0.85
			and abs(foot[3] - foot[1] - thickness) <= 2.1,
			f"One sans foot proportions: {position}",
		)


def check_mono_letters(font, base, position):
	"""核对等宽步进且小写l仅删除左下横脚"""
	width = base["hmtx"][best_cmap(base)[0x31]][0]
	for cp in (0x2D, 0x30, 0x31, 0x4F, 0x6C, 0x7C, 0x2026, *QUOTES):
		if cp not in best_cmap(font):
			continue
		require(
			font["hmtx"][best_cmap(font)[cp]][0] == width,
			f"Mono advance: {position} {cp:04X}",
		)
		if cp in QUOTES:
			box = bounds(font, cp)
			require(
				abs(box[0] + box[2] - width) / 2 <= 1.1,
				f"Mono centering: {position} {cp:04X}",
			)
	if 0x6C not in best_cmap(font):
		return
	ell = font["glyf"][best_cmap(font)[0x6C]]
	source_l = base["glyf"][best_cmap(base)[0x6C]]
	middle = (source_l.yMin + source_l.yMax) / 2
	edges = [
		a[0]
		for a, b in zip(
			source_l.coordinates,
			list(source_l.coordinates[1:]) + [source_l.coordinates[0]],
		)
		if a[0] == b[0] and min(a[1], b[1]) < middle < max(a[1], b[1])
	]
	stem_left = min(edges)
	require(
		len(ell.coordinates) == len(source_l.coordinates),
		f"Mono l topology: {position}",
	)
	for actual, source in zip(ell.coordinates, source_l.coordinates):
		expected_x = max(source[0], stem_left) if source[1] < middle else source[0]
		require(
			abs(actual[0] - expected_x) <= 1.1 and abs(actual[1] - source[1]) <= 1.1,
			f"Mono l foot: {position}",
		)


def check_zero(font, base, family, position):
	"""核对点零沿用本家族内外轮廓且圆点四周保留空隙"""
	glyph = font["glyf"][best_cmap(font)[0x30]]
	require(glyph.numberOfContours == 3, f"Zero dot count: {position}")
	source = base["glyf"][best_cmap(base)[0x30]]
	for actual_index, source_index in ((0, 0), (1, 2 if family == "mono" else 1)):
		actual_contour = contour_glyph(glyph, actual_index)
		source_contour = contour_glyph(source, source_index)
		check_source_contour(actual_contour, source_contour)
	require(
		all(abs(a - b) <= 1.1 for a, b in zip(bounds(font, 0x30), bounds(base, 0x30))),
		f"Zero silhouette: {position}",
	)
	require(
		font["hmtx"][best_cmap(font)[0x30]][0]
		== base["hmtx"][best_cmap(base)[0x30]][0],
		f"Zero advance: {position}",
	)
	inside = contour_bounds(glyph, 1)
	dot = contour_bounds(glyph, 2)
	x, y = (inside[0] + inside[2]) / 2, (inside[1] + inside[3]) / 2
	require(
		abs(dot[0] + dot[2] - 2 * x) <= 2.1 and abs(dot[1] + dot[3] - 2 * y) <= 2.1,
		f"Zero dot center: {position}",
	)
	period = bounds(base, 0x2E)
	scale = (dot[2] - dot[0]) / (period[2] - period[0])
	require(
		0 < scale <= 1.02
		and abs(dot[3] - dot[1] - scale * (period[3] - period[1])) <= 2.1,
		f"Zero dot proportions: {position}",
	)
	check_source_points(
		contour_glyph(glyph, 2),
		base["glyf"][best_cmap(base)[0x2E]],
		scale_x=scale,
		scale_y=scale,
		offset_x=x - scale * (period[0] + period[2]) / 2,
		offset_y=y - scale * (period[1] + period[3]) / 2,
	)
	require(ink_at(font, 0x30, x, y), f"Missing solid zero dot: {position}")
	for test_x, test_y in (
		(dot[0] - 2, y),
		(dot[2] + 2, y),
		(x, dot[1] - 2),
		(x, dot[3] + 2),
	):
		require(
			not ink_at(font, 0x30, test_x, test_y), f"Connected zero dot: {position}"
		)


def check_mono_dash(font, alternate, position):
	"""核对等宽系列的破折号完整保留Sans的轮廓和步进"""
	cp = 0x2014
	glyph = font["glyf"][best_cmap(font)[cp]]
	source = alternate["glyf"][best_cmap(alternate)[cp]]
	require(
		glyph.numberOfContours == source.numberOfContours
		and len(glyph.coordinates) == len(source.coordinates),
		f"Mono em dash topology: {position}",
	)
	check_source_points(glyph, source)
	require(
		font["hmtx"][best_cmap(font)[cp]][0]
		== alternate["hmtx"][best_cmap(alternate)[cp]][0],
		f"Mono em dash advance: {position}",
	)


def check_middle_alignment(font, base, position):
	"""核对连字符和省略号仅平移到大于号的垂直中心"""
	cmap = best_cmap(font)
	for codepoint in (0x2D, 0x2026):
		if codepoint not in cmap:
			continue
		box, reference, source = (
			bounds(font, codepoint),
			bounds(base, 0x3E),
			bounds(base, codepoint),
		)
		require(
			abs(box[1] + box[3] - reference[1] - reference[3]) / 2 <= 1.1,
			f"Middle alignment: {position} {codepoint:04X}",
		)
		require(
			abs(box[0] - source[0]) <= 1.1
			and abs(box[2] - source[2]) <= 1.1
			and abs(box[3] - box[1] - source[3] + source[1]) <= 1.1,
			f"Shifted symbol shape: {position}",
		)
		require(
			font["hmtx"][cmap[codepoint]][0]
			== base["hmtx"][best_cmap(base)[codepoint]][0],
			f"Shifted symbol advance: {position}",
		)


def check_sans_l(font, cjk, position):
	"""核对Sans小写l保留中文来源的轮廓和步进"""
	cmap, cjk_cmap = best_cmap(font), best_cmap(cjk)
	check_source_points(font["glyf"][cmap[0x6C]], cjk["glyf"][cjk_cmap[0x6C]])
	require(
		font["hmtx"][cmap[0x6C]][0] == cjk["hmtx"][cjk_cmap[0x6C]][0],
		f"SC l advance: {position}",
	)
