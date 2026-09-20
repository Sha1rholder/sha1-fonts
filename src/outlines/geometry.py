"""创建基础轮廓并进行保留点序的几何运算"""

import math

import fontforge  # ty: ignore[unresolved-import]  # 由FontForge的Python运行时提供


def rectangle(left, bottom, right, top):
	"""创建顺时针矩形轮廓"""
	contour = fontforge.contour(True)
	for x, y in ((left, bottom), (left, top), (right, top), (right, bottom)):
		contour += fontforge.point(x, y, True)
	contour.closed = True
	return contour


def circle(center_x, center_y, radius, clockwise=True):
	"""用固定点序创建接近正圆的八段二次曲线"""
	contour = fontforge.contour(True)
	direction = -1 if clockwise else 1
	for segment in range(8):
		angle = -math.pi / 2 + direction * segment * math.pi / 4
		control_angle = angle + direction * math.pi / 8
		contour += fontforge.point(
			center_x + math.cos(angle) * radius,
			center_y + math.sin(angle) * radius,
			True,
		)
		control_radius = radius / math.cos(math.pi / 8)
		contour += fontforge.point(
			center_x + math.cos(control_angle) * control_radius,
			center_y + math.sin(control_angle) * control_radius,
			False,
		)
	contour.closed = True
	return contour


def embolden_contour(contour, amount):
	"""沿外法线加粗并保留点序、水平中心和垂直范围"""
	left, bottom, right, top = contour.boundingBox()
	points = [(point.x, point.y) for point in contour]
	direction = 1 if contour.isClockwise() else -1
	radius = amount / 2
	for index, point in enumerate(contour):
		x, y = points[index]
		previous = next(
			points[(index - step) % len(points)]
			for step in range(1, len(points))
			if points[(index - step) % len(points)] != (x, y)
		)
		following = next(
			points[(index + step) % len(points)]
			for step in range(1, len(points))
			if points[(index + step) % len(points)] != (x, y)
		)
		normals = []
		for dx, dy in (
			(x - previous[0], y - previous[1]),
			(following[0] - x, following[1] - y),
		):
			length = math.hypot(dx, dy)
			normals.append((-direction * dy / length, direction * dx / length))
		normal_x, normal_y = (
			normals[0][0] + normals[1][0],
			normals[0][1] + normals[1][1],
		)
		length = math.hypot(normal_x, normal_y)
		if length < 1e-6:
			normal_x, normal_y = normals[0]
			length = 1
		# 限制尖角延伸以免细小衬线形成长刺
		scale = min(
			radius
			/ max(
				1e-6, 1 + normals[0][0] * normals[1][0] + normals[0][1] * normals[1][1]
			),
			2 * radius / length,
		)
		point.x, point.y = x + normal_x * scale, y + normal_y * scale
	new_left, new_bottom, new_right, new_top = contour.boundingBox()
	scale_y = (top - bottom) / (new_top - new_bottom)
	contour.transform(
		(
			1,
			0,
			0,
			scale_y,
			(left + right - new_left - new_right) / 2,
			bottom - new_bottom * scale_y,
		)
	)
	return contour
