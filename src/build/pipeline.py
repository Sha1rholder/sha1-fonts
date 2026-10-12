"""组织来源准备、FontForge轮廓处理、变量合成和发布清单"""

import argparse
import json
import logging
import subprocess

import fontTools

import lib as sources
from lib import (
	COMPLETE,
	DIST,
	FAMILIES,
	FONTFORGE_SCRIPT,
	PATCH,
	ROOT,
	TEMP,
	BuildJob,
	italic_styles,
)

from . import complete, family
from . import jobs as build_jobs


def main() -> None:
	"""解析构建参数并运行完整流水线"""
	parser = argparse.ArgumentParser(description=__doc__)
	parser.add_argument(
		"--reuse-outlines",
		action="store_true",
		help="Reuse existing FontForge outlines for local development",
	)
	args = parser.parse_args()
	logging.basicConfig(level=logging.ERROR)
	build_fonts(reuse_outlines=args.reuse_outlines)


def prepare_outlines(reuse_outlines: bool = False) -> list[BuildJob]:
	"""准备或读取轮廓任务并检查缓存与当前设计一致"""
	jobs_path = TEMP / "jobs.json"
	if reuse_outlines:
		jobs = json.loads(jobs_path.read_text(encoding="ascii"))
	else:
		jobs = []
		for key, config in FAMILIES.items():
			for italic in italic_styles(key):
				print(
					f"Preparing {config['patch']} {'Italic' if italic else 'Roman'}",
					flush=True,
				)
				jobs.extend(build_jobs.prepare_jobs(key, config, italic))
		jobs_path.write_text(json.dumps(jobs, indent=2) + "\n", encoding="ascii")
		with (TEMP / "fontforge.log").open("w", encoding="utf-8") as log:
			subprocess.run(
				[
					"fontforge",
					"-lang=py",
					"-script",
					str(FONTFORGE_SCRIPT),
					str(jobs_path),
				],
				cwd=ROOT,
				stdout=log,
				stderr=subprocess.STDOUT,
				check=True,
			)
		print(f"FontForge patched {len(jobs)} masters", flush=True)
	build_jobs.validate_jobs(jobs)
	return jobs


def build_fonts(reuse_outlines: bool = False) -> None:
	"""构建所有家族样式并确认来源未改写后发布清单"""
	for directory in (TEMP, DIST, PATCH, COMPLETE):
		directory.mkdir(parents=True, exist_ok=True)
	before = sources.source_hashes()
	jobs = prepare_outlines(reuse_outlines)
	outputs = [
		family.build_family(
			config,
			[job for job in jobs if job["family"] == key and job["italic"] == italic],
			italic,
		)
		for key, config in FAMILIES.items()
		for italic in italic_styles(key)
	]
	outputs.extend(
		complete.build_complete(config, italic)
		for key, config in FAMILIES.items()
		for italic in italic_styles(key)
	)
	sources.write_license()
	if before != sources.source_hashes():
		raise RuntimeError("An original source file changed during the build")
	manifest = {
		"fontforge_version": (TEMP / "fontforge-version.txt")
		.read_text(encoding="ascii")
		.strip(),
		"fonttools_version": fontTools.__version__,
		"fonts": outputs,
		"sources_sha256": before,
	}
	(DIST / "manifest.json").write_text(
		json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="ascii"
	)
	print("Original font and license hashes are unchanged", flush=True)
