"""提供独立于轮廓构建算法的测量与断言"""

from copy import deepcopy

from fontTools.pens.areaPen import AreaPen
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.pointInsidePen import PointInsidePen
from fontTools.pens.pointPen import PointToSegmentPen


def require(condition, message):
	"""在核验失败时给出可定位的错误"""
	if not condition:
		raise AssertionError(message)


def best_cmap(font):
	"""返回字体的Unicode映射，缺失时立即报告无效字体"""
	cmap = font.getBestCmap()
	if cmap is None:
		raise ValueError("Font has no Unicode cmap")
	return cmap


def bounds(font, codepoint):
	"""测量字形的实际曲线边界"""
	glyph_set = font.getGlyphSet()
	pen = BoundsPen(glyph_set)
	glyph_set[best_cmap(font)[codepoint]].draw(pen)
	return pen.bounds


def contour_bounds(glyph, index):
	"""测量指定轮廓的坐标边界"""
	start = glyph.endPtsOfContours[index - 1] + 1 if index else 0
	points = glyph.coordinates[start : glyph.endPtsOfContours[index] + 1]
	return (
		min(x for x, y in points),
		min(y for x, y in points),
		max(x for x, y in points),
		max(y for x, y in points),
	)


def contour_area(glyph, index):
	"""积分计算单个二次轮廓的实际填充面积"""
	start = glyph.endPtsOfContours[index - 1] + 1 if index else 0
	end = glyph.endPtsOfContours[index] + 1
	pen = AreaPen()
	point_pen = PointToSegmentPen(pen)
	point_pen.beginPath()
	for point, flag in zip(glyph.coordinates[start:end], glyph.flags[start:end]):
		point_pen.addPoint(tuple(point), "qcurve" if flag & 1 else None)
	point_pen.endPath()
	return abs(pen.value)


def contour_glyph(glyph, index):
	"""提取单个轮廓供独立核验来源节点和拓扑"""
	start = glyph.endPtsOfContours[index - 1] + 1 if index else 0
	end = glyph.endPtsOfContours[index] + 1
	result = deepcopy(glyph)
	result.coordinates = glyph.coordinates[start:end]
	result.flags = glyph.flags[start:end]
	result.endPtsOfContours = [end - start - 1]
	result.numberOfContours = 1
	return result


def ink_at(font, codepoint, x, y):
	"""避开节点射线退化并验证指定位置是实心还是字腔"""
	glyph_set = font.getGlyphSet()
	pen = PointInsidePen(glyph_set, (x + 0.03125, y + 0.0625))
	glyph_set[best_cmap(font)[codepoint]].draw(pen)
	return pen.getResult()


def check_source_points(actual, source, offset_x=0, offset_y=0, scale_x=1, scale_y=1):
	"""核对来源控制点仍存在且只发生预期缩放或平移"""
	for point, flag in zip(source.coordinates, source.flags):
		matches = [
			max(
				abs(candidate[0] - point[0] * scale_x - offset_x),
				abs(candidate[1] - point[1] * scale_y - offset_y),
			)
			for candidate, candidate_flag in zip(actual.coordinates, actual.flags)
			if (candidate_flag & 1) == (flag & 1)
		]
		require(matches and min(matches) <= 1.1, "Source outline was changed")


def check_source_contour(actual, source):
	"""核对独立来源轮廓并计入FontForge显式展开的二次曲线中点"""
	flags = [flag & 1 for flag in source.flags]
	implied = sum(
		not left and not right for left, right in zip(flags, flags[1:] + flags[:1])
	)
	require(
		len(actual.coordinates) == len(source.coordinates) + implied,
		"Source contour topology was changed",
	)
	check_source_points(actual, source)
