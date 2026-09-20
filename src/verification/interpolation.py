"""核验命名母版的一致性与网格中间位置的双线性插值"""

from itertools import pairwise

from fontTools.varLib.instancer import instantiateVariableFont

from build import masters as master_builder
from lib import WEIGHTS, WIDTHS, BuildJob, FamilyConfig, subset_font, variable_path

from . import custom
from .geometry import best_cmap, bounds, require


def check_intermediate(
	font, config: FamilyConfig, jobs: list[BuildJob], original
) -> int:
	"""核对每个网格中心等于四个角母版的双线性平均"""
	weights = [weight for weight in WEIGHTS if weight >= config["minimum"]]
	widths = list(WIDTHS)
	masters = {
		(job["weight"], job["width"]): master_builder.master_font(job, config, original)
		for job in jobs
	}
	source = subset_font(variable_path(config["source"], jobs[0]["italic"]), (0x4F,))
	count = 0
	for low, high in pairwise(weights):
		for narrow, wide in pairwise(widths):
			instance = instantiateVariableFont(
				font,
				{"wght": (low + high) / 2, "wdth": (narrow + wide) / 2},
				inplace=False,
			)
			corners = [
				masters[(weight, width)]
				for weight in (low, high)
				for width in (narrow, wide)
			]
			for cp, name in best_cmap(instance).items():
				box = bounds(instance, cp)
				width = instance["hmtx"][name][0]
				require(
					box[0] < box[2] and box[1] < box[3] and width > 0,
					f"Invalid intermediate: {config['patch']} {cp:04X}",
				)
				for index, point in enumerate(instance["glyf"][name].coordinates):
					for dimension in (0, 1):
						average = (
							sum(
								corner["glyf"][name].coordinates[index][dimension]
								for corner in corners
							)
							/ 4
						)
						require(
							abs(point[dimension] - average) <= 0.1,
							f"Nonlinear interpolation: {config['patch']} {cp:04X}",
						)
				require(
					abs(width - sum(corner["hmtx"][name][0] for corner in corners) / 4)
					<= 1,
					f"Intermediate advance: {config['patch']} {cp:04X}",
				)
			with instantiateVariableFont(
				source,
				{"wght": (low + high) / 2, "wdth": (narrow + wide) / 2},
				inplace=False,
			) as base:
				custom.check_o(
					instance,
					base,
					f"{config['patch']} {'Italic' if jobs[0]['italic'] else 'Roman'} {(low + high) / 2} {(narrow + wide) / 2}",
				)
			instance.close()
			count += 1
	for master in masters.values():
		master.close()
	source.close()
	return count


def check_named_instance(instance, expected, original, position):
	"""核对命名实例与母版的点序坐标、步进和裁剪边界"""
	for name in instance.getGlyphOrder():
		actual = instance["glyf"][name]
		reference = expected["glyf"][name]
		require(
			actual.numberOfContours == reference.numberOfContours,
			f"Contour count: {position} {name}",
		)
		if actual.numberOfContours:
			require(
				len(actual.coordinates) == len(reference.coordinates),
				f"Point count: {position} {name}",
			)
			require(
				max(
					abs(a - b)
					for pair_a, pair_b in zip(actual.coordinates, reference.coordinates)
					for a, b in zip(pair_a, pair_b)
				)
				<= 0.1,
				f"Interpolation mismatch: {position} {name}",
			)
			require(
				actual.yMin >= -original["OS/2"].usWinDescent
				and actual.yMax <= original["OS/2"].usWinAscent,
				f"Font clipping bounds: {position} {name}",
			)
		require(
			all(
				abs(a - b) <= 1
				for a, b in zip(instance["hmtx"][name], expected["hmtx"][name])
			),
			f"Advance/bearing mismatch: {position} {name}",
		)
