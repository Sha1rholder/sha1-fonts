"""核验命名实例与静态母版的一致性并调度各类字形检查"""

from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont

from build import masters
from lib import BuildJob, FamilyConfig

from . import custom, interpolation, latin, punctuation, styles
from .geometry import best_cmap


def check_instance(
	font: TTFont,
	job: BuildJob,
	config: FamilyConfig,
	original: TTFont,
	upright: TTFont | None = None,
) -> None:
	"""比较发布字体与母版并检查独立几何约束"""
	position = f"{job['family']} {'Italic' if job['italic'] else 'Roman'} {job['weight']} {job['width']}"
	instance = instantiateVariableFont(
		font, {"wght": job["weight"], "wdth": job["width"]}, inplace=False
	)
	expected = masters.master_font(job, config, original)
	base = TTFont(job["base"])
	cjk = TTFont(job["cjk"])
	cmap = best_cmap(instance)
	interpolation.check_named_instance(instance, expected, original, position)
	actual_instance = instance
	instance = (
		styles.upright_geometry(instance, job)
		if job["slanted_codepoints"]
		else instance
	)
	latin.check_middle_alignment(instance, base, position)
	if not job["italic"]:
		punctuation.check_punctuation(instance, cjk, position)
		punctuation.check_shifted_cjk_punctuation(instance, cjk, position)
		punctuation.check_parentheses(instance, cjk, position)
	if 0x4F in cmap:
		custom.check_o(instance, base, position)
	if 0x7C in cmap:
		latin.check_bar(instance, base, position)
	if 0x31 in cmap:
		latin.check_one(instance, base, job["family"], position)
	alternate = TTFont(job["alternate"]) if job.get("alternate") else None
	quotes = TTFont(job["quotes"]) if job.get("quotes") else None
	styles.check_style_sources(job, base, cjk, alternate, quotes)
	if quotes is not None:
		latin.check_quotes(instance, quotes, job["family"], position)
	if job["family"] == "sans" and 0x6C in cmap:
		latin.check_sans_l(instance, cjk, position)
	if job["family"] == "mono":
		latin.check_mono_letters(instance, base, position)
		latin.check_mono_dash(instance, alternate, position)
	latin.check_zero(instance, base, job["family"], position)
	if upright is not None:
		styles.check_italic_coverage(actual_instance, upright, job)
	if instance is not actual_instance:
		actual_instance.close()
	for resource in (instance, expected, base, cjk, alternate, quotes):
		if resource is not None:
			resource.close()
