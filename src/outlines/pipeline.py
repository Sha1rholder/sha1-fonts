"""在FontForge运行时调度字形补丁并导出原始轮廓点序"""

import json
import sys
from pathlib import Path

import fontforge  # ty: ignore[unresolved-import]  # 由FontForge的Python运行时提供

from lib import BuildJob

from . import custom, latin, punctuation, transforms


def main():
	"""读取FontForge脚本入口的任务文件参数"""
	run_jobs(Path(sys.argv[1]))


def run_jobs(jobs_path: Path) -> None:
	"""批量处理母版并复用同字重的中文来源"""
	jobs_path = Path(jobs_path)
	jobs = json.loads(jobs_path.read_text(encoding="ascii"))
	donors = {
		path: fontforge.open(path) for path in sorted({job["cjk"] for job in jobs})
	}
	for job in jobs:
		patch_master(job, donors)
	for donor in donors.values():
		donor.close()
	jobs_path.with_name("fontforge-version.txt").write_text(
		str(fontforge.version()) + "\n", encoding="ascii"
	)
	print(f"Patched {len(jobs)} masters with FontForge {fontforge.version()}")


def patch_master(job: BuildJob, donors) -> None:
	"""生成一个位置的补丁轮廓并导出原始点序"""
	base = fontforge.open(job["base"])
	cjk = donors[job["cjk"]]
	quotes = fontforge.open(job["quotes"]) if job.get("quotes") else None
	alternate = fontforge.open(job["alternate"]) if job.get("alternate") else None
	target = fontforge.font()
	target.em = base.em
	target.is_quadratic = True
	punctuation.patch_cjk(target, cjk, job)
	latin.patch_latin(target, base, cjk, quotes, alternate, job)
	custom.patch_o(target, base, job)
	glyphs = {glyph.unicode: glyph for glyph in target.glyphs()}
	for codepoint in job["slanted_codepoints"]:
		transforms.slant_glyph(glyphs[codepoint], job["italic_angle"])
	result = {}
	for glyph in target.glyphs():
		result[str(glyph.unicode)] = {
			"width": glyph.width,
			"contours": [
				[[point.x, point.y, int(point.on_curve)] for point in contour]
				for contour in glyph.foreground
			],
		}
	Path(job["output"]).write_text(
		json.dumps(result, sort_keys=True) + "\n", encoding="ascii"
	)
	target.close()
	base.close()
	if quotes is not None:
		quotes.close()
	if alternate is not None:
		alternate.close()
