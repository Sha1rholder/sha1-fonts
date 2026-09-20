"""以原生圆环构造带右上开口、斜笔和弯钩的艺术字O"""

import math
from itertools import pairwise

import fontforge  # ty: ignore[unresolved-import]  # 由FontForge的Python运行时提供

from lib import BuildJob


def bezier(points, amount):
	"""用德卡斯特里奥算法求任意阶曲线上的位置"""
	while len(points) > 1:
		points = [
			(a[0] + (b[0] - a[0]) * amount, a[1] + (b[1] - a[1]) * amount)
			for a, b in pairwise(points)
		]
	return points[0]


def quadratic_segments(contour):
	"""展开隐式中点并将来源轮廓转换为二次曲线段"""
	points = [(point.x, point.y, point.on_curve) for point in contour]
	expanded = []
	for point, following in zip(points, points[1:] + points[:1]):
		expanded.append(point)
		if not point[2] and not following[2]:
			expanded.append(
				((point[0] + following[0]) / 2, (point[1] + following[1]) / 2, True)
			)
	start = next(index for index, point in enumerate(expanded) if point[2])
	points = expanded[start:] + expanded[:start]
	points.append(points[0])
	segments = []
	index = 0
	while index < len(points) - 1:
		first, following = points[index : index + 2]
		if following[2]:
			segments.append((first[:2], bezier((first, following), 0.5), following[:2]))
			index += 1
		else:
			segments.append((first[:2], following[:2], points[index + 2][:2]))
			index += 2
	return segments


def line_hits(segments, origin, direction):
	"""求来源二次曲线与直线的交点"""
	hits = []
	for segment in segments:
		values = [
			(point[0] - origin[0]) * direction[1]
			- (point[1] - origin[1]) * direction[0]
			for point in segment
		]
		a, b, c = (
			values[0] - 2 * values[1] + values[2],
			2 * (values[1] - values[0]),
			values[0],
		)
		if abs(a) < 1e-8:
			roots = [-c / b] if abs(b) > 1e-8 else []
		else:
			discriminant = b * b - 4 * a * c
			roots = (
				[
					(-b - math.sqrt(discriminant)) / (2 * a),
					(-b + math.sqrt(discriminant)) / (2 * a),
				]
				if discriminant >= 0
				else []
			)
		for root in roots:
			if -1e-8 <= root <= 1 + 1e-8:
				hits.append(bezier(segment, min(1, max(0, root))))
	return hits


def radial_point(segments, center, radii, angle):
	"""按归一化极角取得原生圆环上的对应位置"""
	direction = (radii[0] * math.cos(angle), radii[1] * math.sin(angle))
	return max(
		line_hits(segments, center, direction),
		key=lambda point: (
			(point[0] - center[0]) * direction[0]
			+ (point[1] - center[1]) * direction[1]
		),
	)


def add_point(contour, point, on_curve=True):
	"""追加具有明确曲线类型的轮廓节点"""
	contour += fontforge.point(*point, on_curve)


def add_quadratic(contour, middle, end):
	"""用端点和曲线中点拟合一段二次曲线"""
	start = contour[-1]
	add_point(
		contour,
		(
			2 * middle[0] - (start.x + end[0]) / 2,
			2 * middle[1] - (start.y + end[1]) / 2,
		),
		False,
	)
	add_point(contour, end)


def add_arc(contour, segments, center, radii, start, end):
	"""用固定四十段二次曲线保留来源圆环的比例与笔画粗细"""
	for index in range(40):
		middle = radial_point(
			segments, center, radii, start + (end - start) * (index + 0.5) / 40
		)
		point = radial_point(
			segments, center, radii, start + (end - start) * (index + 1) / 40
		)
		add_quadratic(contour, middle, point)


def add_cubic(contour, points):
	"""用固定四段二次曲线逼近弯钩的三次曲线"""
	for index in range(4):
		add_quadratic(
			contour, bezier(points, (index + 0.5) / 4), bezier(points, (index + 1) / 4)
		)


def hook_curves(root, crown, shoulder, tangent, height):
	"""构造两段相切曲线使弯钩平顺接入原生圆环"""
	distance = crown[0] - root[0]
	first = (
		root,
		(root[0] + distance * 0.55, root[1]),
		(crown[0] - distance * 0.25, crown[1]),
		crown,
	)
	second = (
		crown,
		((crown[0] + shoulder[0]) / 2, crown[1]),
		(
			shoulder[0] - tangent[0] * height * 0.08,
			shoulder[1] - tangent[1] * height * 0.08,
		),
		shoulder,
	)
	return first, second


def patch_o(target, base, job: BuildJob) -> None:
	"""按原生家族及样式生成艺术字O并保留步进和固定节点拓扑"""
	if 0x4F not in job["codepoints"]:
		return
	original = base[0x4F]
	layer = original.foreground
	_, bottom, _, top = original.boundingBox()
	slope = math.tan(math.radians(-job["italic_angle"])) if job["italic"] else 0
	middle_y = (bottom + top) / 2
	# 仅在设计坐标内消除倾角，最终恢复原生斜体圆环
	layer.transform((1, 0, -slope, 1, slope * middle_y, 0))
	outer = next(contour for contour in layer if contour.isClockwise())
	inner = next(contour for contour in layer if not contour.isClockwise())
	left, bottom, right, top = outer.boundingBox()
	inner_left, inner_bottom, inner_right, inner_top = inner.boundingBox()
	width, height = right - left, top - bottom
	inner_width, inner_height = inner_right - inner_left, inner_top - inner_bottom
	center = ((inner_left + inner_right) / 2, (inner_bottom + inner_top) / 2)
	radii = (width / 2, height / 2)
	start = (inner_left + inner_width * 0.25, inner_bottom + inner_height * 0.63)
	tip = (left + width * 0.85, top - height * 0.005)
	direction = (tip[0] - start[0], tip[1] - start[1])
	length = math.hypot(*direction)
	hairline = (top - inner_top + inner_bottom - bottom) / 2
	stroke = min(hairline * 0.6, inner_width * 0.16, inner_height * 0.12)
	normal = (
		-direction[1] * stroke / (2 * length),
		direction[0] * stroke / (2 * length),
	)
	upper_start, lower_start = (
		(start[0] + sign * normal[0], start[1] + sign * normal[1]) for sign in (1, -1)
	)
	upper_tip, lower_tip = (
		(tip[0] + sign * normal[0], tip[1] + sign * normal[1]) for sign in (1, -1)
	)
	valley = bezier((lower_start, lower_tip), 0.46)
	root = bezier((lower_start, lower_tip), 0.46 - stroke * 0.9 / direction[1])
	crown = (left + width * 0.83, bottom + height * 0.825)
	inner_crown = (
		crown[0] - (right - inner_right) * 0.5,
		min(crown[1] - hairline * 0.65, inner_top - inner_height * 0.1),
	)
	shoulder_angle = math.radians(25)
	result = fontforge.layer(True)
	for source, clockwise in ((outer, True), (inner, False)):
		segments = quadratic_segments(source)
		cut = max(
			line_hits(segments, upper_start, direction), key=lambda point: point[1]
		)
		cut_angle = math.atan2(
			(cut[1] - center[1]) / radii[1], (cut[0] - center[0]) / radii[0]
		)
		shoulder = radial_point(segments, center, radii, shoulder_angle)
		before = radial_point(segments, center, radii, shoulder_angle + 0.001)
		after = radial_point(segments, center, radii, shoulder_angle - 0.001)
		tangent_length = math.hypot(after[0] - before[0], after[1] - before[1])
		tangent = (
			(after[0] - before[0]) / tangent_length,
			(after[1] - before[1]) / tangent_length,
		)
		contour = fontforge.contour(True)
		if clockwise:
			add_point(contour, shoulder)
			add_arc(
				contour, segments, center, radii, shoulder_angle, cut_angle - math.tau
			)
			for point in (upper_tip, lower_tip, valley):
				add_point(contour, point)
			for curve in hook_curves(valley, crown, shoulder, tangent, height):
				add_cubic(contour, curve)
		else:
			add_point(contour, cut)
			add_arc(
				contour, segments, center, radii, cut_angle, shoulder_angle + math.tau
			)
			curves = hook_curves(root, inner_crown, shoulder, tangent, inner_height)
			for curve in reversed(curves):
				add_cubic(contour, tuple(reversed(curve)))
			for point in (lower_start, upper_start, cut):
				add_point(contour, point)
		# 闭合点由轮廓自身提供，避免重复节点影响插值
		del contour[-1]
		contour.closed = True
		result += contour
	result.transform((1, 0, slope, 1, -slope * middle_y, 0))
	glyph = target.createChar(0x4F)
	glyph.foreground = result
	glyph.width = original.width
