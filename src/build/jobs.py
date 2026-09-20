"""准备供体实例并检查轮廓缓存覆盖的设计网格"""

import lib as sources
from lib import (
	FAMILIES,
	OUTLINE_DESIGN_VERSION,
	PUNCTUATION,
	PUNCTUATION_DOT_SHIFT,
	PUNCTUATION_RIGHT_SHIFT_FRACTION,
	PUNCTUATION_TOP_REFERENCE,
	QUOTES,
	SOURCES,
	TEMP,
	WEIGHTS,
	WIDTHS,
	BuildJob,
	FamilyConfig,
	italic_styles,
	patch_codepoints,
	slanted_codepoints,
	variable_path,
)


def prepare_jobs(
	key: str, config: FamilyConfig, italic: bool = False
) -> list[BuildJob]:
	"""按各补丁来源选择样式并准备全部宽度字重位置"""
	work = TEMP / key / ("italic" if italic else "normal")
	work.mkdir(parents=True, exist_ok=True)
	base = sources.subset_font(
		variable_path(config["source"], italic),
		(0x2D, 0x2E, 0x30, 0x31, 0x3E, 0x4F, 0x6C, 0x7C, 0x2026),
	)
	quotes = (
		sources.subset_font(variable_path("Noto_Serif", italic), QUOTES)
		if key != "serif"
		else None
	)
	alternate = (
		sources.subset_font(variable_path("Noto_Sans"), (0x2014,))
		if key == "mono"
		else None
	)
	style_source = base
	jobs: list[BuildJob] = []
	for weight, weight_name in WEIGHTS.items():
		if weight < config["minimum"]:
			continue
		cjk_source = (
			SOURCES
			/ config["cjk"]
			/ "static"
			/ f"{config['cjk'].replace('_', '')}-{weight_name}.ttf"
		)
		cjk_path = work / f"cjk-{weight}.ttf"
		cjk = sources.subset_font(
			cjk_source, (*PUNCTUATION, 0x6C, PUNCTUATION_TOP_REFERENCE)
		)
		cjk.save(cjk_path)
		cjk.close()
		for width in WIDTHS:
			stem = f"{weight}-{width:g}"
			base_path = work / f"base-{stem}.ttf"
			sources.instantiate(base, weight, width, base_path)
			job: BuildJob = {
				"family": key,
				"weight": weight,
				"width": width,
				"base": str(base_path),
				"cjk": str(cjk_path),
				"italic": italic,
				"codepoints": list(patch_codepoints(config, italic)),
				"slanted_codepoints": list(slanted_codepoints(key, italic)),
				"italic_angle": style_source["post"].italicAngle,
				"caret_slope_rise": style_source["hhea"].caretSlopeRise,
				"caret_slope_run": style_source["hhea"].caretSlopeRun,
				"output": str(work / f"patch-{stem}.json"),
				"punctuation_top_reference": PUNCTUATION_TOP_REFERENCE,
				"punctuation_dot_shift": PUNCTUATION_DOT_SHIFT,
				"punctuation_right_shift_fraction": PUNCTUATION_RIGHT_SHIFT_FRACTION,
				"outline_design_version": OUTLINE_DESIGN_VERSION,
			}
			if quotes is not None:
				quote_path = work / f"quotes-{stem}.ttf"
				sources.instantiate(quotes, weight, width, quote_path)
				job["quotes"] = str(quote_path)
			if alternate is not None:
				alternate_path = work / f"alternate-{stem}.ttf"
				sources.instantiate(alternate, weight, width, alternate_path)
				job["alternate"] = str(alternate_path)
			jobs.append(job)
	base.close()
	if quotes is not None:
		quotes.close()
	if alternate is not None:
		alternate.close()
	return jobs


def validate_jobs(jobs: list[BuildJob]) -> None:
	"""拒绝缺失、重复或使用旧补丁设计的轮廓缓存"""
	expected = {
		(key, italic, weight, width)
		for key, config in FAMILIES.items()
		for italic in italic_styles(key)
		for weight in WEIGHTS
		if weight >= config["minimum"]
		for width in WIDTHS
	}
	actual = {
		(job["family"], job.get("italic", False), job["weight"], job["width"])
		for job in jobs
	}
	if actual != expected or len(jobs) != len(expected):
		raise ValueError(
			"Cached outlines do not cover all styles; rebuild without --reuse-outlines"
		)
	for job in jobs:
		if (
			job.get("outline_design_version") != OUTLINE_DESIGN_VERSION
			or job.get("codepoints")
			!= list(patch_codepoints(FAMILIES[job["family"]], job["italic"]))
			or job.get("slanted_codepoints")
			!= list(slanted_codepoints(job["family"], job["italic"]))
			or job.get("punctuation_top_reference") != PUNCTUATION_TOP_REFERENCE
			or job.get("punctuation_dot_shift") != PUNCTUATION_DOT_SHIFT
			or job.get("punctuation_right_shift_fraction")
			!= PUNCTUATION_RIGHT_SHIFT_FRACTION
		):
			raise ValueError(
				"Cached outlines use an older style design; rebuild without --reuse-outlines"
			)
