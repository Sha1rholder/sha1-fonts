"""把轮廓JSON转换为静态母版并检查点序兼容性"""

import json
from array import array
from pathlib import Path
from typing import Any, cast

from fontTools.fontBuilder import FontBuilder
from fontTools.misc.roundTools import otRound
from fontTools.ttLib import TTFont
from fontTools.ttLib.tables._g_l_y_f import Glyph, GlyphCoordinates, flagOverlapSimple
from fontTools.ttLib.tables.ttProgram import Program

import lib as sources
from lib import (
	EPOCH,
	VERSION,
	BuildJob,
	FamilyConfig,
	patch_codepoints,
	style_name,
)


def make_glyph(contours):
	"""将FontForge原始点序写入TrueType而不单独优化母版"""
	glyph = Glyph()
	glyph.numberOfContours = len(contours)
	glyph.program = Program()
	glyph.program.fromBytecode(b"")
	if not contours:
		return glyph
	glyph.coordinates = GlyphCoordinates(
		[(otRound(x), otRound(y)) for contour in contours for x, y, on_curve in contour]
	)
	glyph.flags = array(
		"B", [on_curve for contour in contours for x, y, on_curve in contour]
	)
	glyph.flags[0] |= flagOverlapSimple
	glyph.endPtsOfContours = []
	count = 0
	for contour in contours:
		count += len(contour)
		glyph.endPtsOfContours.append(count - 1)
	return glyph


def master_font(job: BuildJob, config: FamilyConfig, original: TTFont) -> TTFont:
	"""建立含正确命名和排版度量的最小静态母版"""
	data = json.loads(Path(job["output"]).read_text(encoding="ascii"))
	cmap = {
		cp: f"uni{cp:04X}" for cp in sorted(patch_codepoints(config, job["italic"]))
	}
	glyphs = {".notdef": make_glyph([])}
	metrics = {".notdef": (0, 0)}
	for cp, name in cmap.items():
		entry = data[str(cp)]
		glyph = make_glyph(entry["contours"])
		glyph.recalcBounds(None)
		glyphs[name] = glyph
		metrics[name] = (entry["width"], glyph.xMin)
	original_head = cast(Any, original["head"])
	fb = FontBuilder(original_head.unitsPerEm, isTTF=True)
	fb.setupGlyphOrder(list(glyphs))
	fb.setupCharacterMap(cmap)
	fb.setupGlyf(glyphs)
	fb.setupHorizontalMetrics(metrics)
	hhea = cast(Any, original["hhea"])
	fb.setupHorizontalHeader(
		ascent=hhea.ascent,
		descent=hhea.descent,
		lineGap=hhea.lineGap,
		caretSlopeRise=job["caret_slope_rise"],
		caretSlopeRun=job["caret_slope_run"],
	)
	italic = job["italic"]
	style = style_name(job["weight"], job["width"], italic)
	family = config["patch"]
	ps_name = f"{family.replace(' ', '')}-{style.replace(' ', '')}"
	fb.setupNameTable(
		{
			"familyName": family,
			"styleName": style,
			"typographicFamily": family,
			"typographicSubfamily": style,
			"uniqueFontIdentifier": f"{VERSION};SHA1;{ps_name}",
			"fullName": f"{family} {style}",
			"psName": ps_name,
			"version": f"Version {VERSION}",
			"copyright": sources.copyright_text(),
			"manufacturer": "Sha1 font contributors",
			"description": "Minimal Noto-derived glyph patches. Built with FontForge and fontTools.",
			"licenseDescription": "This Font Software is licensed under the SIL Open Font License, Version 1.1.",
			"licenseInfoURL": "https://openfontlicense.org",
		}
	)
	os2 = cast(Any, original["OS/2"])
	fb.setupOS2(
		sTypoAscender=os2.sTypoAscender,
		sTypoDescender=os2.sTypoDescender,
		sTypoLineGap=os2.sTypoLineGap,
		usWinAscent=os2.usWinAscent,
		usWinDescent=os2.usWinDescent,
		sxHeight=os2.sxHeight,
		sCapHeight=os2.sCapHeight,
		usWeightClass=job["weight"],
		usWidthClass={62.5: 2, 75: 3, 87.5: 4, 100: 5}[job["width"]],
		fsSelection=0x81 if italic else 0xC0,
		fsType=0,
		achVendID="SHA1",
	)
	post = cast(Any, original["post"])
	fb.setupPost(
		italicAngle=job["italic_angle"],
		underlinePosition=post.underlinePosition,
		underlineThickness=post.underlineThickness,
	)
	fb.setupMaxp()
	head = cast(Any, fb.font["head"])
	head.created = EPOCH
	head.modified = EPOCH
	head.fontRevision = float(VERSION)
	head.macStyle = 2 if italic else 0
	fb.font.recalcTimestamp = False
	return fb.font


def check_topology(masters):
	"""在合成之前拒绝不兼容的轮廓以防静默丢失变化"""
	for name in masters[0].getGlyphOrder():
		signatures = set()
		for master in masters:
			glyph = master["glyf"][name]
			signatures.add(
				(
					glyph.numberOfContours,
					tuple(getattr(glyph, "endPtsOfContours", ())),
					tuple(flag & 1 for flag in getattr(glyph, "flags", ())),
				)
			)
		if len(signatures) != 1:
			raise ValueError(f"Incompatible master topology: {name}: {signatures}")
