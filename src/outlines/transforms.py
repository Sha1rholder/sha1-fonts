"""复制字形并调整对齐、等宽适配与倾斜"""

import math

import psMat  # ty: ignore[unresolved-import]  # 由FontForge的Python运行时提供


def copy_glyph(target, source, codepoint):
	"""复制轮廓和字宽并展开引用"""
	original = source[codepoint]
	original.unlinkRef()
	glyph = target.createChar(codepoint)
	glyph.foreground = original.foreground
	glyph.width = original.width
	return glyph


def align_middle(glyph, reference):
	"""将符号垂直居中对齐参考字形并保留原步进"""
	reference_box, box = reference.boundingBox(), glyph.boundingBox()
	width = glyph.width
	glyph.transform(
		psMat.translate(0, (reference_box[1] + reference_box[3] - box[1] - box[3]) / 2)
	)
	glyph.width = width


def fit_mono(glyph, width, margin=0.1):
	"""将外来字形居中放入等宽字格并按需压缩"""
	left, _, right, _ = glyph.boundingBox()
	scale = min(1, width * (1 - 2 * margin) / (right - left))
	glyph.transform(psMat.scale(scale, 1))
	left, _, right, _ = glyph.boundingBox()
	glyph.transform(psMat.translate((width - left - right) / 2, 0))
	glyph.width = width


def slant_glyph(glyph, angle):
	"""围绕字形高度中心倾斜轮廓并保留原步进与点序"""
	_, bottom, _, top = glyph.boundingBox()
	width = glyph.width
	slope = math.tan(math.radians(-angle))
	glyph.transform((1, 0, slope, 1, -slope * (bottom + top) / 2, 0))
	glyph.width = width
