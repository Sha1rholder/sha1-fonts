"""独立核验艺术字O的原生圆环、斜笔、开口和字腔"""

import math

from fontTools.pens.areaPen import AreaPen
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.pointInsidePen import PointInsidePen
from fontTools.pens.recordingPen import RecordingPen
from fontTools.pens.transformPen import TransformPen

from .geometry import best_cmap, bounds, contour_glyph, require


def o_contours(font, transform):
	"""记录去除设计倾角后的各轮廓以便独立测量"""
	glyph = font["glyf"][best_cmap(font)[0x4F]]
	contours = []
	for index in range(glyph.numberOfContours):
		pen = RecordingPen()
		contour_glyph(glyph, index).draw(TransformPen(pen, transform), font["glyf"])
		contours.append(pen)
	return contours


def outline_bounds(contours):
	"""通过实际曲线极值测量一组轮廓的边界"""
	pen = BoundsPen(None)
	for contour in contours:
		contour.replay(pen)
	return pen.bounds


def outline_ink(contours, point):
	"""按非零环绕规则检测设计坐标中的实际填充"""
	pen = PointInsidePen(None, (point[0] + 0.03125, point[1] + 0.0625))
	for contour in contours:
		contour.replay(pen)
	return pen.getResult()


def straight_edges(contours):
	"""提取真实直线段以识别斜笔端面而不依赖节点编号"""
	edges = []
	for contour in contours:
		start = current = None
		for operator, points in contour.value:
			if operator == "moveTo":
				start = current = points[0]
			elif operator == "closePath":
				if current != start:
					edges.append((current, start))
			elif operator == "lineTo":
				edges.append((current, points[0]))
				current = points[0]
			else:
				current = points[-1]
	return edges


def check_bowl(actual, source, position):
	"""核对下半圆环与左上弧的原生比例和笔画粗细"""
	left, bottom, right, top = outline_bounds(source)
	width, height = right - left, top - bottom
	for row in (0.15, 0.3, 0.45, 0.55, 0.7, 0.85):
		for column in range(1, 25 if row <= 0.55 else 7):
			x, y = left + width * column / 25, bottom + height * row
			before = outline_ink(source, (x - 1.5, y))
			after = outline_ink(source, (x + 1.5, y))
			if before == after:
				require(
					outline_ink(actual, (x, y)) == before, f"O native bowl: {position}"
				)


def check_o(font, base, position):
	"""核验相连圆环、长斜笔、右上开口、空字腔和原生步进"""
	name, source_name = best_cmap(font)[0x4F], best_cmap(base)[0x4F]
	require(font["glyf"][name].numberOfContours == 2, f"O contour count: {position}")
	# 中间位置的来源度量与母版插值可能相差一个取整单位
	require(
		abs(font["hmtx"][name][0] - base["hmtx"][source_name][0]) <= 1,
		f"O advance: {position}",
	)
	_, bottom, _, top = bounds(base, 0x4F)
	slope = math.tan(math.radians(-base["post"].italicAngle))
	transform = (1, 0, -slope, 1, slope * (bottom + top) / 2, 0)
	actual, source = o_contours(font, transform), o_contours(base, transform)
	left, bottom, right, top = outline_bounds(source)
	width, height = right - left, top - bottom
	box = outline_bounds(actual)
	require(
		all(
			abs(box[axis] - value) <= 1.5
			for axis, value in enumerate((left, bottom, right))
		),
		f"O silhouette: {position}",
	)
	require(top - 1.5 <= box[3] <= top + height * 0.06, f"O cap height: {position}")
	for index, contour in enumerate(actual):
		pen = AreaPen()
		contour.replay(pen)
		require(pen.value * (-1 if index == 0 else 1) > 0, f"O winding: {position}")
	inner = outline_bounds(source[1:])
	center = ((inner[0] + inner[2]) / 2, (inner[1] + inner[3]) / 2)
	require(not outline_ink(actual, center), f"O empty counter: {position}")
	caps = [
		((a[0] + b[0]) / 2, (a[1] + b[1]) / 2, math.dist(a, b))
		for a, b in straight_edges(actual)
		if (b[0] - a[0]) * (b[1] - a[1]) < 0 and math.dist(a, b) > 1
	]
	require(len(caps) == 2, f"O diagonal terminals: {position}")
	start, tip = sorted(caps, key=lambda cap: cap[1])
	dx, dy = tip[0] - start[0], tip[1] - start[1]
	require(dx > width * 0.3 and dy > height * 0.3, f"O diagonal length: {position}")
	require(abs(start[2] - tip[2]) <= 2, f"O diagonal thickness: {position}")
	require(
		bottom + height * 0.5 < start[1] < bottom + height * 0.7
		and top - height * 0.04 < tip[1] < top + height * 0.04,
		f"O diagonal placement: {position}",
	)
	for amount in (0.08, 0.25, 0.5, 0.75, 0.95):
		require(
			outline_ink(actual, (start[0] + dx * amount, start[1] + dy * amount)),
			f"O connected diagonal: {position}",
		)
	require(
		not outline_ink(source, (start[0] + dx * 0.97, start[1] + dy * 0.97)),
		f"O projecting diagonal: {position}",
	)
	length = math.hypot(dx, dy)
	clearance = start[2] * 0.75 + height * 0.018
	slit = (
		start[0] + dx * 0.75 + dy / length * clearance,
		start[1] + dy * 0.75 - dx / length * clearance,
	)
	require(not outline_ink(actual, slit), f"O open shoulder: {position}")
	check_bowl(actual, source, position)
