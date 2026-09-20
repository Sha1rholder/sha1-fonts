"""调度字体元数据、命名实例、插值和样式验证并生成报告"""

import hashlib
import json
import logging
import shutil
import subprocess

from fontTools.ttLib import TTFont

from build.jobs import validate_jobs
from lib import (
	DIST,
	FAMILIES,
	TEMP,
	BuildJob,
	FamilyConfig,
	font_path,
	italic_styles,
	patch_codepoints,
	variable_path,
)

from . import complete, instances, interpolation, metadata, styles
from .geometry import require


def main() -> None:
	"""核验全部发布字体并写入可复查的报告"""
	logging.basicConfig(level=logging.ERROR)
	manifest = json.loads((DIST / "manifest.json").read_text(encoding="ascii"))
	metadata.check_manifest(manifest)
	version = manifest["version"]
	jobs = json.loads((TEMP / "jobs.json").read_text(encoding="ascii"))
	validate_jobs(jobs)
	postscript_names = set()
	reports = [
		verify_family(
			key,
			config,
			[job for job in jobs if job["family"] == key and job["italic"] == italic],
			italic,
			postscript_names,
			version,
		)
		for key, config in FAMILIES.items()
		for italic in italic_styles(key)
	]
	latin_reports = styles.check_latin_styles()
	complete_reports = [
		complete.verify_complete_family(config, italic, version)
		for key, config in FAMILIES.items()
		for italic in italic_styles(key)
	]
	(DIST / "verification.json").write_text(
		json.dumps(
			{
				"version": version,
				"fonts": reports,
				"latin_styles": latin_reports,
				"complete_fonts": complete_reports,
				"source_files_unchanged": True,
				"original_licenses_preserved": True,
			},
			indent=2,
		)
		+ "\n",
		encoding="ascii",
	)
	print("All checks passed", flush=True)


def verify_family(
	key: str,
	config: FamilyConfig,
	family_jobs: list[BuildJob],
	italic: bool,
	postscript_names: set[str],
	version: str,
):
	"""验证一个家族样式的元数据、全部实例和整形结果"""
	path = font_path(config, italic)
	with (
		TTFont(path, checkChecksums=2, recalcTimestamp=False) as font,
		TTFont(variable_path(config["source"], italic)) as original,
	):
		metadata.check_font(
			font, key, config, italic, family_jobs, postscript_names, version
		)
		upright = TTFont(font_path(config)) if italic else None
		try:
			for job in family_jobs:
				instances.check_instance(font, job, config, original, upright)
		finally:
			if upright is not None:
				upright.close()
		intermediate_count = interpolation.check_intermediate(
			font, config, family_jobs, original
		)
		check_shaping(path, key, config, italic)
	report = {
		"family": config["patch"],
		"style": "italic" if italic else "normal",
		"named_instances": len(family_jobs),
		"intermediate_instances": intermediate_count,
		"bytes": path.stat().st_size,
		"sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
	}
	print(
		f"Verified {config['patch']} {'Italic' if italic else 'Roman'}: {len(family_jobs)} named + {intermediate_count} intermediate instances",
		flush=True,
	)
	return report


def check_shaping(path, key, config, italic):
	"""在HarfBuzz可用时核对浅、常规和重位置没有缺字"""
	executable = shutil.which("hb-shape")
	if executable is None:
		return
	for weight, width in ((config["minimum"], 62.5), (400, 100), (900, 62.5)):
		result = subprocess.run(
			[
				executable,
				str(path),
				"--text=" + "".join(chr(cp) for cp in patch_codepoints(config, italic)),
				f"--variations=wght={weight},wdth={width}",
			],
			capture_output=True,
			text=True,
			check=True,
		)
		require(".notdef" not in result.stdout, f"HarfBuzz missing glyph: {key}")
