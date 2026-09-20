"""合成一个家族样式的变量字体与发布记录"""

from fontTools.designspaceLib import (
	AxisDescriptor,
	DesignSpaceDocument,
	InstanceDescriptor,
	SourceDescriptor,
)
from fontTools.otlLib.builder import buildStatTable
from fontTools.ttLib import TTFont
from fontTools.varLib import build

from lib import (
	DIST,
	EPOCH,
	ROOT,
	WEIGHTS,
	WIDTHS,
	BuildJob,
	FamilyConfig,
	font_path,
	patch_codepoints,
	style_name,
	variable_path,
)

from . import masters as master_builder
from . import variations


def build_family(config: FamilyConfig, jobs: list[BuildJob], italic: bool = False):
	"""分别合成直立或斜体网格并保留同家族样式关联"""
	original = TTFont(variable_path(config["source"], italic), recalcTimestamp=False)
	designspace = DesignSpaceDocument()
	for tag, label, minimum, default, maximum in (
		("wght", "Weight", config["minimum"], 400, 900),
		("wdth", "Width", 62.5, 100, 100),
	):
		axis = AxisDescriptor()
		axis.tag, axis.name = tag, label
		axis.minimum, axis.default, axis.maximum = minimum, default, maximum
		designspace.addAxis(axis)
	masters = []
	for job in jobs:
		master = master_builder.master_font(job, config, original)
		masters.append(master)
		source = SourceDescriptor()
		source.font = master
		source.name = style_name(job["weight"], job["width"], italic)
		source.location = {"Weight": job["weight"], "Width": job["width"]}
		designspace.addSource(source)
		instance = InstanceDescriptor()
		instance.familyName = config["patch"]
		instance.styleName = source.name
		instance.postScriptFontName = (
			config["patch"].replace(" ", "") + "-" + source.name.replace(" ", "")
		)
		instance.location = dict(source.location)
		designspace.addInstance(instance)
	master_builder.check_topology(masters)
	font, _, _ = build(designspace, optimize=False)
	variations.exact_grid_variations(font, jobs, masters, config)
	font.recalcTimestamp = False
	font["head"].created = font["head"].modified = EPOCH
	font["name"].setName(
		config["patch"].replace(" ", "") + ("Italic" if italic else ""), 25, 3, 1, 0x409
	)
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
				"values": [{"value": 1, "name": "Italic"}]
				if italic
				else [{"value": 0, "name": "Roman", "flags": 2, "linkedValue": 1}],
			},
		],
	)
	path = font_path(config, italic)
	font.save(path)
	font.close()
	original.close()
	print(f"Built {path.relative_to(ROOT)} ({len(jobs)} instances)", flush=True)
	return {
		"file": str(path.relative_to(DIST)),
		"family": config["patch"],
		"style": "italic" if italic else "normal",
		"instances": len(jobs),
		"weight_range": [config["minimum"], 900],
		"width_range": [62.5, 100],
		"codepoints": [
			f"U+{cp:04X}" for cp in sorted(patch_codepoints(config, italic))
		],
	}
