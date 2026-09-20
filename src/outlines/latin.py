"""修改拉丁字母、数字和符号的区分特征"""

import fontforge  # ty: ignore[unresolved-import]  # 由FontForge的Python运行时提供

from lib import BuildJob

from . import geometry, transforms


def dot_zero(glyph, period):
	"""保留零的内外轮廓并用留有字腔间隙的居中句点替换斜线"""
	outer = max(
		(contour for contour in glyph.foreground if contour.isClockwise()),
		key=lambda contour: (
			(contour.boundingBox()[2] - contour.boundingBox()[0])
			* (contour.boundingBox()[3] - contour.boundingBox()[1])
		),
	)
	inside = next(contour for contour in glyph.foreground if not contour.isClockwise())
	left, bottom, right, top = inside.boundingBox()
	center_x, center_y = (left + right) / 2, (bottom + top) / 2
	period_left, period_bottom, period_right, period_top = period.boundingBox()
	# 在圆点覆盖的高度内取字腔交集，避免窄体斜体的圆点碰到侧壁
	period_height = period_top - period_bottom
	scale, upper = 0, min(1, (top - bottom) / (2 * period_height))
	for _ in range(16):
		candidate = (scale + upper) / 2
		half_height = period_height * candidate / 2
		spans = [
			inside.xBoundsAtY(center_y + offset)
			for offset in (-half_height, 0, half_height)
		]
		clearance = min(min(center_x - span[0], span[1] - center_x) for span in spans)
		if (period_right - period_left) * candidate <= clearance:
			scale = candidate
		else:
			upper = candidate
	dot = period.foreground
	dot.transform(
		(
			scale,
			0,
			0,
			scale,
			center_x - scale * (period_left + period_right) / 2,
			center_y - scale * (period_bottom + period_top) / 2,
		)
	)
	layer = fontforge.layer(True)
	layer += outer
	layer += inside
	glyph.foreground = layer
	glyph.foreground += dot


def mark_bar(glyph):
	"""将竖线延长百分之十并在中间添加凸出笔画的实心圆"""
	left, bottom, right, top = glyph.boundingBox()
	center_x, center_y = (left + right) / 2, (bottom + top) / 2
	width = glyph.width
	glyph.transform((1, 0, 0, 1.1, 0, -center_y * 0.1))
	glyph.width = width
	radius = min(max(16, (right - left) * 0.9), width * 0.4)
	glyph.foreground += geometry.circle(center_x, center_y, radius)


def trim_mono_l(glyph):
	"""收回小写l的左下横脚并保留右侧横脚和原字宽"""
	layer = glyph.foreground
	_, bottom, _, top = glyph.boundingBox()
	middle = (bottom + top) / 2
	stem_left, _ = layer.xBoundsAtY(middle)
	for contour in layer:
		for point in contour:
			if point.y < middle and point.x < stem_left:
				point.x = stem_left
	glyph.foreground = layer


def trim_mono_one(glyph):
	"""删除数字1独立的底横轮廓并保留主体和原步进"""
	layer = fontforge.layer(True)
	layer += max(
		glyph.foreground,
		key=lambda contour: contour.boundingBox()[3] - contour.boundingBox()[1],
	)
	glyph.foreground = layer


def patch_latin(target, base, cjk, quotes, alternate, job: BuildJob) -> None:
	"""按家族选择拉丁补丁供体并执行对应修改"""
	for codepoint in (0x2D, 0x2026):
		transforms.align_middle(
			transforms.copy_glyph(target, base, codepoint), base[0x3E]
		)
	mark_bar(transforms.copy_glyph(target, base, 0x7C))
	dot_zero(transforms.copy_glyph(target, base, 0x30), base[0x2E])
	if job["family"] == "sans":
		transforms.copy_glyph(target, cjk, 0x6C)
	if job["family"] == "mono":
		trim_mono_l(transforms.copy_glyph(target, base, 0x6C))
		trim_mono_one(transforms.copy_glyph(target, base, 0x31))
		transforms.copy_glyph(target, alternate, 0x2014)
	if quotes is not None:
		for codepoint in (0x2018, 0x2019, 0x201C, 0x201D):
			glyph = transforms.copy_glyph(target, quotes, codepoint)
			if job["family"] == "mono":
				transforms.fit_mono(glyph, base[0x4F].width)
