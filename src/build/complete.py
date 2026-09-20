"""将补丁和Noto来源合并为无需回退的完整变量字体"""

from copy import deepcopy
from itertools import pairwise
from typing import Any, cast

from fontTools.misc.roundTools import otRound
from fontTools.otlLib.builder import buildStatTable
from fontTools.ttLib import TTFont
from fontTools.ttLib.tables._g_l_y_f import GlyphCoordinates
from fontTools.ttLib.tables.TupleVariation import TupleVariation
from fontTools.varLib.instancer import instantiateVariableFont

from lib import (
	DIST,
	EPOCH,
	VERSION,
	WEIGHTS,
	WIDTHS,
	FamilyConfig,
	complete_font_path,
	font_path,
	variable_path,
)


def build_complete(config: FamilyConfig, italic: bool = False):
	"""以Noto为底叠加补丁，并为直立样式补入SC字形"""
	path = complete_font_path(config, italic)
	path.parent.mkdir(parents=True, exist_ok=True)
	with (
		TTFont(variable_path(config["source"], italic), recalcTimestamp=False) as font,
		TTFont(font_path(config, italic), recalcTimestamp=False) as patch,
	):
		_restrict_weight_range(font, config)
		if not italic:
			with TTFont(variable_path(config["cjk"]), recalcTimestamp=False) as cjk:
				_add_missing_cjk(font, cjk)
		_overlay_patch(font, patch)
		_finalize(font, config, italic)
		font.save(path)
		glyph_count = font["maxp"].numGlyphs
	print(f"Built {path.name} ({glyph_count} glyphs)", flush=True)
	return {
		"file": str(path.relative_to(DIST)),
		"family": config["complete"],
		"style": "italic" if italic else "normal",
		"glyphs": glyph_count,
	}


def _restrict_weight_range(font: TTFont, config: FamilyConfig) -> None:
	"""裁去SC没有来源的拉丁轻字重范围并重映射现有差分"""
	axis = next(axis for axis in font["fvar"].axes if axis.axisTag == "wght")
	if axis.minValue != config["minimum"]:
		instantiateVariableFont(
			font,
			{"wght": (config["minimum"], axis.defaultValue, axis.maxValue)},
			inplace=True,
		)


def _add_missing_cjk(target: TTFont, cjk: TTFont) -> None:
	"""补入拉丁来源没有映射的SC字形及其字重变化"""
	target_cmap = _best_cmap(target)
	missing = {
		codepoint: name
		for codepoint, name in _best_cmap(cjk).items()
		if codepoint not in target_cmap
	}
	source_names = _glyph_closure(cjk, set(missing.values()))
	name_map = _rename_glyphs(target, source_names)
	target_glyf = target["glyf"]
	target_hmtx = target["hmtx"].metrics
	for source_name in source_names:
		target_name = name_map[source_name]
		glyph = deepcopy(cjk["glyf"][source_name])
		if glyph.isComposite():
			for component in glyph.components:
				component.glyphName = name_map[component.glyphName]
		target_glyf.glyphs[target_name] = glyph
		target_hmtx[target_name] = cjk["hmtx"][source_name]
		_variations_for_cjk_glyph(target, cjk, source_name, target_name)
	_add_cmap(
		target, {codepoint: name_map[name] for codepoint, name in missing.items()}
	)
	_update_glyph_order(target, source_names, name_map)


def _glyph_closure(font: TTFont, names: set[str]) -> list[str]:
	"""返回包含复合字形组件的稳定字形闭包"""
	pending = list(names)
	while pending:
		name = pending.pop()
		glyph = font["glyf"][name]
		if glyph.isComposite():
			for component in glyph.components:
				if component.glyphName not in names:
					names.add(component.glyphName)
					pending.append(component.glyphName)
	return [name for name in font.getGlyphOrder() if name in names]


def _rename_glyphs(target: TTFont, source_names: list[str]) -> dict[str, str]:
	"""为冲突的SC字形名分配不与拉丁来源重叠的名称"""
	known = set(target.getGlyphOrder())
	result = {}
	for source_name in source_names:
		target_name = source_name
		if target_name in known:
			index = 1
			target_name = f"sha1cjk.{source_name}"
			while target_name in known:
				index += 1
				target_name = f"sha1cjk{index}.{source_name}"
		known.add(target_name)
		result[source_name] = target_name
	return result


def _variations_for_cjk_glyph(
	target: TTFont, cjk: TTFont, source_name: str, target_name: str
) -> None:
	"""将SC从最细默认母版重定基准为完整字体的常规字重"""
	variations = cjk["gvar"].variations[source_name]
	if not variations:
		target["gvar"].variations[target_name] = []
		return
	if len(variations) != 1 or variations[0].axes != {"wght": (0.0, 1.0, 1.0)}:
		raise ValueError(f"Unsupported SC variation: {source_name}")
	factor = _cjk_regular_factor(target, cjk)
	source_glyf = cjk["glyf"]
	coordinates, controls = source_glyf._getCoordinatesAndControls(
		source_name, cjk["hmtx"].metrics
	)
	variation = deepcopy(variations[0])
	variation.calcInferredDeltas(coordinates, controls.endPts)
	deltas = [delta or (0, 0) for delta in variation.coordinates]
	target_glyf = target["glyf"]
	target_coordinates, _ = target_glyf._getCoordinatesAndControls(
		target_name, target["hmtx"].metrics
	)
	target_coordinates += GlyphCoordinates(_scale_deltas(deltas, factor))
	target_coordinates.toInt()
	target_glyf._setCoordinates(target_name, target_coordinates, target["hmtx"].metrics)
	target["gvar"].variations[target_name] = [
		TupleVariation({"wght": (-1.0, -1.0, 0.0)}, _scale_deltas(deltas, -factor)),
		TupleVariation({"wght": (0.0, 1.0, 1.0)}, _scale_deltas(deltas, 1 - factor)),
	]


def _cjk_regular_factor(target: TTFont, cjk: TTFont) -> float:
	"""计算SC默认字重到完整字体常规字重的轴映射后距离"""
	target_axis = next(axis for axis in target["fvar"].axes if axis.axisTag == "wght")
	cjk_axis = next(axis for axis in cjk["fvar"].axes if axis.axisTag == "wght")
	if target_axis.defaultValue < cjk_axis.defaultValue:
		raise ValueError("Complete font default precedes the SC default")
	position = (target_axis.defaultValue - cjk_axis.defaultValue) / (
		cjk_axis.maxValue - cjk_axis.defaultValue
	)
	return _avar_value(cjk, "wght", position)


def _avar_value(font: TTFont, axis_tag: str, position: float) -> float:
	"""按字体的avar分段映射一个已归一化的轴位置"""
	avar = font.get("avar")
	segments = getattr(avar, "segments", {}).get(axis_tag, {})
	points = sorted({-1.0: -1.0, 0.0: 0.0, 1.0: 1.0, **segments}.items())
	for (before, before_value), (after, after_value) in pairwise(points):
		if before <= position <= after:
			if before == after:
				return before_value
			return before_value + (after_value - before_value) * (position - before) / (
				after - before
			)
	return position


def _scale_deltas(deltas, factor: float):
	"""缩放并取整坐标差分以满足TrueType编码要求"""
	return [(otRound(x * factor), otRound(y * factor)) for x, y in deltas]


def _update_glyph_order(
	target: TTFont, source_names: list[str], name_map: dict[str, str]
) -> None:
	"""同步字形顺序及依赖于字形数量的度量表"""
	order = [*target.getGlyphOrder(), *(name_map[name] for name in source_names)]
	target.setGlyphOrder(order)
	target["glyf"].glyphOrder = order
	target["maxp"].recalc(target)
	target["hhea"].recalc(target)


def _overlay_patch(target: TTFont, patch: TTFont) -> None:
	"""用Patch轮廓、步进及变量差分覆盖同码位的Noto字形"""
	target_cmap = _best_cmap(target)
	patch_cmap = _best_cmap(patch)
	new_names = []
	for codepoint, patch_name in patch_cmap.items():
		target_name = target_cmap.get(codepoint)
		if target_name is None:
			target_name = _new_patch_name(target, patch_name)
			target["glyf"].glyphs[target_name] = deepcopy(patch["glyf"][patch_name])
			new_names.append(target_name)
		target["glyf"][target_name] = deepcopy(patch["glyf"][patch_name])
		target["hmtx"][target_name] = patch["hmtx"][patch_name]
		target["gvar"].variations[target_name] = deepcopy(
			patch["gvar"].variations[patch_name]
		)
		_add_cmap(target, {codepoint: target_name})
	if new_names:
		order = [*target.getGlyphOrder(), *new_names]
		target.setGlyphOrder(order)
		target["glyf"].glyphOrder = order
		target["maxp"].recalc(target)
		target["hhea"].recalc(target)


def _new_patch_name(target: TTFont, patch_name: str) -> str:
	"""为Noto没有的补丁码位创建唯一字形名"""
	known = set(target.getGlyphOrder())
	name = patch_name
	index = 1
	while name in known:
		index += 1
		name = f"sha1patch{index}.{patch_name}"
	return name


def _add_cmap(font: TTFont, mapping: dict[int, str]) -> None:
	"""向全部Unicode cmap子表写入指定码位映射"""
	for table in font["cmap"].tables:
		if table.isUnicode():
			table.cmap.update(
				{
					codepoint: name
					for codepoint, name in mapping.items()
					if table.format not in {4, 6} or codepoint <= 0xFFFF
				}
			)


def _best_cmap(font: TTFont) -> dict[int, str]:
	"""取得字体的Unicode映射，缺失时立即终止构建"""
	cmap = font.getBestCmap()
	if cmap is None:
		raise ValueError("Font has no Unicode cmap")
	return cmap


def _finalize(font: TTFont, config: FamilyConfig, italic: bool) -> None:
	"""删除失效的度量差分并写入Sha1完整字体元数据"""
	if "HVAR" in font:
		del font["HVAR"]
	font.recalcTimestamp = False
	head = cast(Any, font["head"])
	head.created = head.modified = EPOCH
	head.fontRevision = float(VERSION)
	for name_id in (1, 2, 3, 4, 6, 16, 17, 25):
		font["name"].removeNames(name_id)
	family = config["complete"]
	style = "Italic" if italic else "Regular"
	postscript = family.replace(" ", "") + ("-Italic" if italic else "-Regular")
	for platform, encoding, language in ((3, 1, 0x409), (1, 0, 0)):
		for name_id, value in (
			(1, family),
			(2, style),
			(3, f"{VERSION};SHA1;{postscript}"),
			(4, f"{family} {style}"),
			(6, postscript),
			(16, family),
			(17, style),
			(25, family.replace(" ", "")),
		):
			font["name"].setName(value, name_id, platform, encoding, language)
	buildStatTable(
		font,
		[
			{
				"tag": "wght",
				"name": "Weight",
				"values": [
					{"value": weight, "name": name, "flags": 2 if weight == 400 else 0}
					for weight, name in WEIGHTS.items()
					if weight >= config["minimum"]
				],
			},
			{
				"tag": "wdth",
				"name": "Width",
				"values": [
					{
						"value": width,
						"name": name or "Normal",
						"flags": 2 if width == 100 else 0,
					}
					for width, name in WIDTHS.items()
				],
			},
			{
				"tag": "ital",
				"name": "Italic",
				"values": [
					{"value": 1, "name": "Italic"}
					if italic
					else {"value": 0, "name": "Roman", "flags": 2, "linkedValue": 1}
				],
			},
		],
	)
