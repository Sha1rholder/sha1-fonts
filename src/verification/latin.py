"""核验拉丁补丁的供体轮廓、笔画、字腔和步进"""

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
		abs(stroke[3] - stroke[1] - (source[3] - source[1]) * 1.1) <= 1.1,
		f"Bar length: {position}",
	)
	require(
		abs(stroke[2] - stroke[0] - source[2] + source[0]) <= 1.1,
		f"Bar thickness: {position}",
	)
	require(dot[0] < stroke[0] and dot[2] > stroke[2], f"Invisible bar dot: {position}")
	require(
		abs(dot[0] + dot[2] - stroke[0] - stroke[2]) <= 1.1
		and abs(dot[1] + dot[3] - stroke[1] - stroke[3]) <= 1.1,
		f"Bar dot center: {position}",
	)
	require(
		font["hmtx"][best_cmap(font)[0x7C]][0]
		== base["hmtx"][best_cmap(base)[0x7C]][0],
		f"Bar advance: {position}",
	)


def check_mono_letters(font, base, position):
	"""核对等宽数字1仅删除底横且小写l仅删除左下横脚"""
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
	one = font["glyf"][best_cmap(font)[0x31]]
	source_one = base["glyf"][best_cmap(base)[0x31]]
	stem_index = max(
		range(source_one.numberOfContours),
		key=lambda index: (
			contour_bounds(source_one, index)[3] - contour_bounds(source_one, index)[1]
		),
	)
	stem = contour_glyph(source_one, stem_index)
	require(
		one.numberOfContours == 1 and source_one.numberOfContours == 2,
		f"Unexpected 1 foot: {position}",
	)
	check_source_contour(one, stem)
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
