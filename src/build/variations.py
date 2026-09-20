"""为字重和字宽网格构造精确的轮廓与步进变化"""

from fontTools.ttLib.tables._g_l_y_f import GlyphCoordinates
from fontTools.ttLib.tables.TupleVariation import TupleVariation
from fontTools.varLib.builder import buildVarData, buildVarRegionList, buildVarStore
from fontTools.varLib.models import normalizeValue

from lib import WEIGHTS, WIDTHS


def local_support(values, value, limits):
	"""用相邻网格节点定义局部三角支撑"""
	index = values.index(value)
	neighbors = (
		values[max(0, index - 1)],
		value,
		values[min(len(values) - 1, index + 1)],
	)
	return tuple(normalizeValue(item, limits) for item in neighbors)


def exact_grid_variations(font, jobs, masters, config):
	"""用整数网格差分避免多层增量舍入影响同字重来源"""
	grid = {(job["weight"], job["width"]): master for job, master in zip(jobs, masters)}
	weights = [weight for weight in WEIGHTS if weight >= config["minimum"]]
	widths = list(WIDTHS)
	terms = []
	for weight, width in grid:
		if (weight, width) == (400, 100):
			continue
		support = {}
		if weight != 400:
			support["wght"] = local_support(
				weights, weight, (config["minimum"], 400, 900)
			)
		if width != 100:
			support["wdth"] = local_support(widths, width, (62.5, 100, 100))
		coefficients = [((weight, width), 1), ((400, 100), -1)]
		if weight != 400 and width != 100:
			coefficients = [
				((weight, width), 1),
				((weight, 100), -1),
				((400, width), -1),
				((400, 100), 1),
			]
		terms.append((support, coefficients))
	advance_deltas = []
	for name in font.getGlyphOrder():
		coordinates = {
			location: master["glyf"]._getCoordinatesAndControls(
				name, master["hmtx"].metrics
			)[0]
			for location, master in grid.items()
		}
		variations = []
		advances = []
		for support, coefficients in terms:
			delta = GlyphCoordinates([(0, 0)] * len(coordinates[(400, 100)]))
			for location, coefficient in coefficients:
				delta += coordinates[location] * coefficient
			if any(x or y for x, y in delta):
				variations.append(
					TupleVariation(
						support, [delta[index] for index in range(len(delta))]
					)
				)
			advances.append(
				sum(
					grid[location]["hmtx"][name][0] * coefficient
					for location, coefficient in coefficients
				)
			)
		font["gvar"].variations[name] = variations
		advance_deltas.append(advances)
	regions = buildVarRegionList(
		[support for support, coefficients in terms],
		[axis.axisTag for axis in font["fvar"].axes],
	)
	font["HVAR"].table.VarStore = buildVarStore(
		regions, [buildVarData(range(len(terms)), advance_deltas, optimize=False)]
	)
	font["HVAR"].table.AdvWidthMap = None
	font["HVAR"].table.LsbMap = None
	font["HVAR"].table.RsbMap = None
