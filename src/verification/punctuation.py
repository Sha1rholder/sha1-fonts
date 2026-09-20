"""核验中文标点的空心圆、加粗、位移和括号连接"""

from lib import (
	PUNCTUATION_DOT_SHIFT,
	PUNCTUATION_RIGHT_SHIFT_FRACTION,
	PUNCTUATION_TOP_REFERENCE,
)

from .geometry import (
	best_cmap,
	bounds,
	check_source_points,
	contour_area,
	contour_bounds,
	ink_at,
	require,
)


def check_punctuation(font, cjk, position):
	"""核对实心部分加粗并齐平汉字上界且空心圆保持不变"""
	period = cjk["glyf"][best_cmap(cjk)[0x3002]]
	period_boxes = sorted(
		(contour_bounds(period, index) for index in range(period.numberOfContours)),
		key=lambda box: box[2] - box[0],
		reverse=True,
	)
	for cp in (0xFF01, 0xFF0C, 0xFF1A, 0xFF1B, 0xFF1F):
		glyph = font["glyf"][best_cmap(font)[cp]]
		source = cjk["glyf"][best_cmap(cjk)[cp]]
		boxes = [
			contour_bounds(source, index) for index in range(source.numberOfContours)
		]
		dots = (
			[]
			if cp == 0xFF0C
			else list(range(len(boxes)))
			if cp == 0xFF1A
			else [
				min(
					range(len(boxes)),
					key=lambda index: boxes[index][3] - boxes[index][1],
				)
			]
		)
		stem_top = (
			bounds(cjk, PUNCTUATION_TOP_REFERENCE)[3]
			if cp in (0xFF01, 0xFF1F)
			else None
		)
		dot_shift = PUNCTUATION_DOT_SHIFT if cp in (0xFF01, 0xFF1F) else 0
		right_shift = (
			font["hmtx"][best_cmap(font)[cp]][0] * PUNCTUATION_RIGHT_SHIFT_FRACTION
			if cp in (0xFF01, 0xFF0C, 0xFF1A, 0xFF1B, 0xFF1F)
			else 0
		)
		require(
			glyph.numberOfContours == source.numberOfContours + len(dots),
			f"Punctuation contours: {position} {cp:04X}",
		)
		require(
			font["hmtx"][best_cmap(font)[cp]][0] == cjk["hmtx"][best_cmap(cjk)[cp]][0],
			f"Punctuation advance: {position}",
		)
		output_index = 0
		stem_box, ring_top = None, None
		for index, source_box in enumerate(boxes):
			if index not in dots:
				stem_box = contour_bounds(glyph, output_index)
				expected_top = stem_top if stem_top is not None else source_box[3]
				require(
					abs(stem_box[3] - expected_top) <= 1.1,
					f"Punctuation top alignment: {position} {cp:04X}",
				)
				require(
					abs(stem_box[3] - stem_box[1] - source_box[3] + source_box[1])
					<= 1.1,
					f"Punctuation stem height: {position} {cp:04X}",
				)
				require(
					abs(
						stem_box[0]
						+ stem_box[2]
						- source_box[0]
						- source_box[2]
						- 2 * right_shift
					)
					<= 1.1,
					f"Punctuation stem center: {position} {cp:04X}",
				)
				require(
					stem_box[2] - stem_box[0] > source_box[2] - source_box[0] + 1,
					f"Punctuation stem width: {position} {cp:04X}",
				)
				require(
					contour_area(glyph, output_index)
					> contour_area(source, index) * 1.025,
					f"Punctuation ink weight: {position} {cp:04X}",
				)
				output_index += 1
				continue
			outer, inner = (
				contour_bounds(glyph, output_index),
				contour_bounds(glyph, output_index + 1),
			)
			center_x, center_y = (
				(source_box[0] + source_box[2]) / 2 + right_shift,
				(source_box[1] + source_box[3]) / 2 - dot_shift,
			)
			ring_top = outer[3]
			require(
				outer[0] < inner[0] < inner[2] < outer[2]
				and outer[1] < inner[1] < inner[3] < outer[3],
				f"Hollow counter: {position}",
			)
			require(
				abs(outer[0] + outer[2] - 2 * center_x) <= 1.1
				and abs(outer[1] + outer[3] - 2 * center_y) <= 1.1,
				f"Ring centering: {position}",
			)
			for actual_box, period_box in zip((outer, inner), period_boxes):
				for axis in (0, 1):
					require(
						abs(
							actual_box[axis + 2]
							- actual_box[axis]
							- period_box[axis + 2]
							+ period_box[axis]
						)
						<= 1.1,
						f"SC period size: {position} {cp:04X}",
					)
			require(
				not ink_at(font, cp, center_x, center_y),
				f"Filled punctuation counter: {position}",
			)
			require(
				ink_at(font, cp, (inner[2] + outer[2]) / 2, center_y),
				f"Missing ring stroke: {position}",
			)
			output_index += 2
		if cp in (0xFF01, 0xFF1F):
			require(
				stem_box is not None
				and ring_top is not None
				and stem_box[1] > ring_top,
				f"Punctuation stem touches ring: {position} {cp:04X}",
			)


def check_shifted_cjk_punctuation(font, cjk, position):
	"""核对顿号和句号仅右移一个八分之一步进"""
	for cp in (0x3001, 0x3002):
		name = best_cmap(font)[cp]
		glyph = font["glyf"][name]
		source = cjk["glyf"][best_cmap(cjk)[cp]]
		require(
			glyph.numberOfContours == source.numberOfContours,
			f"Shifted punctuation contours: {position} {cp:04X}",
		)
		require(
			font["hmtx"][name][0] == cjk["hmtx"][best_cmap(cjk)[cp]][0],
			f"Shifted punctuation advance: {position} {cp:04X}",
		)
		check_source_points(
			glyph,
			source,
			offset_x=font["hmtx"][name][0] * PUNCTUATION_RIGHT_SHIFT_FRACTION,
		)


def check_parentheses(font, cjk, position):
	"""核对括号只缩小步进且横线准确连接字格五分点与主体"""
	for cp in (0xFF08, 0xFF09):
		glyph = font["glyf"][best_cmap(font)[cp]]
		source = cjk["glyf"][best_cmap(cjk)[cp]]
		original_width = cjk["hmtx"][best_cmap(cjk)[cp]][0]
		width = font["hmtx"][best_cmap(font)[cp]][0]
		require(
			width == round(original_width * 2 / 3), f"Parenthesis advance: {position}"
		)
		require(glyph.numberOfContours == 2, f"Parenthesis contour count: {position}")
		shift = width - original_width if cp == 0xFF08 else 0
		check_source_points(glyph, source, offset_x=shift)
		bar = contour_bounds(glyph, 1)
		target = width / 5 if cp == 0xFF08 else width * 4 / 5
		require(
			abs((bar[0] if cp == 0xFF08 else bar[2]) - target) <= 1.1,
			f"Parenthesis fifth position: {position}",
		)
		body = contour_bounds(glyph, 0)
		require(
			bar[2] > body[0] if cp == 0xFF08 else bar[0] < body[2],
			f"Disconnected parenthesis mark: {position}",
		)
