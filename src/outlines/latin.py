"""修改拉丁字母、数字和符号的区分特征"""

import math

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


def mark_bar(glyph, base):
	"""将竖线延伸至字体升降部边界并添加居中实心圆"""
	left, bottom, right, top = glyph.boundingBox()
	low, high = base.hhea_descent, base.hhea_ascent
	center_x, center_y = (left + right) / 2, (low + high) / 2
	width = glyph.width
	scale = (high - low) / (top - bottom)
	glyph.transform((1, 0, 0, scale, 0, low - bottom * scale))
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


def serif_one_body(source, stem_left, stem_right, top, tip_x, tip_y, join_y):
	"""收短原生底部衬线并将实心旗头下缘圆滑接入竖干"""
	_, bottom, _, _ = source.boundingBox()
	cut = bottom + (top - bottom) * 0.4
	points = list(source)
	up = next(
		index
		for index, point in enumerate(points)
		if point.on_curve
		and points[(index + 1) % len(points)].on_curve
		and point.y < cut < points[(index + 1) % len(points)].y
	)
	down = next(
		index
		for index, point in enumerate(points)
		if point.on_curve
		and points[(index + 1) % len(points)].on_curve
		and point.y > cut > points[(index + 1) % len(points)].y
	)
	contour = fontforge.contour(True)
	for point in points[down + 1 :] + points[: up + 1]:
		x = point.x
		if x < stem_left:
			x = stem_left + (x - stem_left) * 0.8
		elif x > stem_right:
			x = stem_right + (x - stem_right) * 0.8
		contour += fontforge.point(x, point.y, point.on_curve)
	for x, y, on_curve in (
		(stem_left, cut, True),
		(stem_left, join_y, True),
		(stem_left, tip_y - (top - bottom) * 0.04, False),
		(tip_x, tip_y, True),
		(stem_right, top, True),
		(stem_right, cut, True),
	):
		contour += fontforge.point(x, y, on_curve)
	contour.closed = True
	return contour


def flag_one(glyph, angle, family):
	"""构造无台阶的实心三角旗头并按家族适配底横和步进"""
	slope = math.tan(math.radians(-angle))
	source = glyph.foreground
	source.transform((1, 0, -slope, 1, 0, 0))
	stem = max(
		source, key=lambda contour: contour.boundingBox()[3] - contour.boundingBox()[1]
	)
	_, bottom, _, top = stem.boundingBox()
	height = top - bottom
	stem_left, stem_right = stem.xBoundsAtY(bottom + height * 0.35)
	thickness = stem_right - stem_left
	center = (stem_left + stem_right) / 2
	left = min(point.x for point in stem if point.y > bottom + height * 0.5)
	foot = None
	if family == "serif":
		foot_left = min(point.x for point in stem if point.y < bottom + height * 0.4)
		foot_left = stem_left + (foot_left - stem_left) * 0.8
	elif family == "mono":
		foot = min(
			source,
			key=lambda contour: contour.boundingBox()[3] - contour.boundingBox()[1],
		)
		foot_left, _, foot_right, _ = foot.boundingBox()
		foot.transform((0.8, 0, 0, 1, (foot_left + foot_right) * 0.1, 0))
		foot_left = foot.boundingBox()[0]
	else:
		foot_width = max(glyph.width * 0.55, thickness * 1.6)
		foot_left = center - foot_width / 2
		foot = geometry.rectangle(
			foot_left, bottom, center + foot_width / 2, bottom + thickness
		)
	# 只向左扩展旗尖，使外伸长度接近底横且不收窄已有旗头
	reach = max((stem_left - left) * 0.4, (stem_left - foot_left) * 0.9)
	tip_y, join_y = (top - height * part for part in (0.18, 0.3))
	layer = fontforge.layer(True)
	if family == "serif":
		layer += serif_one_body(
			stem, stem_left, stem_right, top, stem_left - reach, tip_y, join_y
		)
	else:
		contour = fontforge.contour(True)
		for x, y in (
			(stem_right, bottom),
			(stem_left, bottom),
			(stem_left, join_y),
			(stem_left - reach, tip_y),
			(stem_right, top),
		):
			contour += fontforge.point(x, y, True)
		contour.closed = True
		layer += contour
	if foot is not None:
		layer += foot
	width = int(glyph.width * 0.85 + 0.5) if family == "sans" else glyph.width
	layer.transform((1, 0, slope, 1, (width - glyph.width) / 2, 0))
	glyph.foreground = layer
	glyph.width = width


def patch_latin(target, base, cjk, quotes, alternate, job: BuildJob) -> None:
	"""按家族选择拉丁补丁供体并执行对应修改"""
	for codepoint in (0x2D, 0x2026):
		transforms.align_middle(
			transforms.copy_glyph(target, base, codepoint), base[0x3E]
		)
	mark_bar(transforms.copy_glyph(target, base, 0x7C), base)
	dot_zero(transforms.copy_glyph(target, base, 0x30), base[0x2E])
	flag_one(
		transforms.copy_glyph(target, base, 0x31), job["italic_angle"], job["family"]
	)
	if job["family"] == "sans":
		transforms.copy_glyph(target, cjk, 0x6C)
	if job["family"] == "mono":
		trim_mono_l(transforms.copy_glyph(target, base, 0x6C))
		transforms.copy_glyph(target, alternate, 0x2014)
	if quotes is not None:
		for codepoint in (0x2018, 0x2019, 0x201C, 0x201D):
			glyph = transforms.copy_glyph(target, quotes, codepoint)
			if job["family"] == "mono":
				transforms.fit_mono(glyph, base[0x4F].width)
