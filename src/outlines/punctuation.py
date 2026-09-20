"""修改中文标点的空心圆、实心笔画和括号标记"""

import fontforge  # ty: ignore[unresolved-import]  # 由FontForge的Python运行时提供
import psMat  # ty: ignore[unresolved-import]  # 由FontForge的Python运行时提供

from lib import BuildJob

from . import geometry, transforms


def patch_punctuation(glyph, period, stem_top=None, dot_shift=0):
	"""按句号线宽加粗实心部分并将主体对齐汉字上界"""
	period_boxes = sorted(
		(contour.boundingBox() for contour in period.foreground),
		key=lambda box: box[2] - box[0],
		reverse=True,
	)
	outer, inner = period_boxes
	stroke = (
		sum(
			outer[axis + 2] - outer[axis] - inner[axis + 2] + inner[axis]
			for axis in (0, 1)
		)
		/ 4
	)
	contours = list(glyph.foreground)
	if glyph.unicode == 0xFF0C:
		dots = []
	else:
		dots = (
			range(len(contours))
			if glyph.unicode == 0xFF1A
			else [
				min(
					range(len(contours)),
					key=lambda i: (
						contours[i].boundingBox()[3] - contours[i].boundingBox()[1]
					),
				)
			]
		)
	stem_shift = (
		stem_top
		- max(
			contour.boundingBox()[3]
			for index, contour in enumerate(contours)
			if index not in dots
		)
		if stem_top is not None
		else 0
	)
	layer = fontforge.layer(True)
	for index, contour in enumerate(contours):
		if index not in dots:
			geometry.embolden_contour(contour, stroke)
			if stem_shift:
				contour.transform(psMat.translate(0, stem_shift))
			layer += contour
			continue
		left, bottom, right, top = contour.boundingBox()
		center_x, center_y = (left + right) / 2, (bottom + top) / 2 - dot_shift
		for box, clockwise in ((outer, True), (inner, False)):
			ring = geometry.circle(0, 0, 1, clockwise=clockwise)
			ring.transform(
				((box[2] - box[0]) / 2, 0, 0, (box[3] - box[1]) / 2, center_x, center_y)
			)
			layer += ring
	glyph.foreground = layer


def shift_punctuation_right(glyph, fraction):
	"""将标点全部轮廓右移指定步进比例且保留原步进"""
	width = glyph.width
	glyph.transform(psMat.translate(width * fraction, 0))
	glyph.width = width


def mark_parenthesis(glyph, left_side):
	"""裁掉外侧三分之一字格并将中部横线连接到字格五分点"""
	original_width = glyph.width
	width = int(original_width * 2 / 3 + 0.5)
	if left_side:
		glyph.transform(psMat.translate(width - original_width, 0))
	glyph.width = width
	_, bottom, _, top = glyph.boundingBox()
	center_y = (bottom + top) / 2
	stem_left, stem_right = glyph.foreground.xBoundsAtY(center_y)
	thickness = max(12, (stem_right - stem_left) * 0.7)
	if left_side:
		start, end = width / 5, (stem_left + stem_right) / 2
	else:
		start, end = (stem_left + stem_right) / 2, width * 4 / 5
	glyph.foreground += geometry.rectangle(
		start, center_y - thickness / 2, end, center_y + thickness / 2
	)


def patch_cjk(target, cjk, job: BuildJob) -> None:
	"""按任务参数处理中文标点和括号"""
	for codepoint in (0xFF01, 0xFF0C, 0xFF1A, 0xFF1B, 0xFF1F):
		stem_top = (
			cjk[job["punctuation_top_reference"]].boundingBox()[3]
			if codepoint in (0xFF01, 0xFF1F)
			else None
		)
		shift_dot = job["punctuation_dot_shift"] if codepoint in (0xFF01, 0xFF1F) else 0
		glyph = transforms.copy_glyph(target, cjk, codepoint)
		patch_punctuation(
			glyph,
			cjk[0x3002],
			stem_top=stem_top,
			dot_shift=shift_dot,
		)
		shift_punctuation_right(glyph, job["punctuation_right_shift_fraction"])
	for codepoint in (0x3001, 0x3002):
		glyph = transforms.copy_glyph(target, cjk, codepoint)
		shift_punctuation_right(glyph, job["punctuation_right_shift_fraction"])
	for codepoint in (0xFF08, 0xFF09):
		glyph = transforms.copy_glyph(target, cjk, codepoint)
		mark_parenthesis(glyph, codepoint == 0xFF08)
