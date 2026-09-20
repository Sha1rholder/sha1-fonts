"""定义字体配置、项目路径和来源字体处理"""

import hashlib
from pathlib import Path
from typing import NotRequired, TypedDict

EPOCH = 3856896000
VERSION = "1.131"
OUTLINE_DESIGN_VERSION = 3
WEIGHTS = {
	100: "Thin",
	200: "ExtraLight",
	300: "Light",
	400: "Regular",
	500: "Medium",
	600: "SemiBold",
	700: "Bold",
	800: "ExtraBold",
	900: "Black",
}
WIDTHS = {62.5: "ExtraCondensed", 75: "Condensed", 87.5: "SemiCondensed", 100: ""}
PUNCTUATION_TOP_REFERENCE = 0x4E2D  # 以同字重“中”的上界作为满高汉字顶线
PUNCTUATION_DOT_SHIFT = 16
PUNCTUATION_RIGHT_SHIFT_FRACTION = 1 / 8
QUOTES = (0x2018, 0x2019, 0x201C, 0x201D)
PUNCTUATION = (0x3001, 0x3002, 0xFF01, 0xFF08, 0xFF09, 0xFF0C, 0xFF1A, 0xFF1B, 0xFF1F)


class FamilyConfig(TypedDict):
	"""声明家族的来源与补丁字符集合"""

	patch: str
	complete: str
	source: str
	cjk: str
	minimum: int
	codepoints: tuple[int, ...]
	italic_codepoints: tuple[int, ...]


class BuildJob(TypedDict):
	"""声明经JSON传递给FontForge及验证器的单个母版任务"""

	family: str
	weight: int
	width: float
	base: str
	cjk: str
	quotes: NotRequired[str]
	alternate: NotRequired[str]
	italic: bool
	codepoints: list[int]
	slanted_codepoints: list[int]
	italic_angle: float
	caret_slope_rise: int
	caret_slope_run: int
	output: str
	punctuation_top_reference: int
	punctuation_dot_shift: float
	punctuation_right_shift_fraction: float
	outline_design_version: int


FAMILIES: dict[str, FamilyConfig] = {
	"sans": {
		"patch": "Sha1 Sans Patch",
		"complete": "Sha1 Sans",
		"source": "Noto_Sans",
		"cjk": "Noto_Sans_SC",
		"minimum": 100,
		"codepoints": (0x2D, 0x30, 0x4F, 0x6C, 0x7C, 0x2026, *QUOTES, *PUNCTUATION),
		"italic_codepoints": (0x2D, 0x30, 0x4F, 0x6C, 0x7C, 0x2026, *QUOTES),
	},
	"mono": {
		"patch": "Sha1 Sans Mono Patch",
		"complete": "Sha1 Sans Mono",
		"source": "Noto_Sans_Mono",
		"cjk": "Noto_Sans_SC",
		"minimum": 100,
		"codepoints": (
			0x2D,
			0x30,
			0x31,
			0x4F,
			0x6C,
			0x7C,
			0x2014,
			0x2026,
			*QUOTES,
			*PUNCTUATION,
		),
		"italic_codepoints": (),
	},
	"serif": {
		"patch": "Sha1 Serif Patch",
		"complete": "Sha1 Serif",
		"source": "Noto_Serif",
		"cjk": "Noto_Serif_SC",
		"minimum": 200,
		"codepoints": (0x2D, 0x30, 0x4F, 0x7C, 0x2026, *PUNCTUATION),
		"italic_codepoints": (0x2D, 0x30, 0x4F, 0x7C, 0x2026),
	},
}


def italic_styles(key: str) -> tuple[bool, ...]:
	"""返回家族需要构建的直立和斜体样式"""
	return (False,) if key == "mono" else (False, True)


def patch_codepoints(config: FamilyConfig, italic: bool = False) -> tuple[int, ...]:
	"""返回当前样式需要编码的补丁字符集"""
	return config["italic_codepoints"] if italic else config["codepoints"]


def slanted_codepoints(key: str, italic: bool) -> tuple[int, ...]:
	"""选择没有原生斜体来源而需在构建时倾斜的字符"""
	if not italic:
		return ()
	if key == "sans":
		return (0x6C,)
	return ()


def style_name(weight: int, width: float, italic: bool = False) -> str:
	"""组合可安装的宽度、字重与斜体样式名称"""
	weight_name = "" if italic and weight == 400 else WEIGHTS[weight]
	return " ".join(
		part
		for part in (WIDTHS[width], weight_name, "Italic" if italic else "")
		if part
	)


ROOT = Path(__file__).resolve().parents[1]
SOURCES = ROOT / "Noto"
TEMP = ROOT / "temp" / "build"
DIST = ROOT / "Sha1"
PATCH = DIST / "patch"
COMPLETE = DIST / "complete"
FONTFORGE_SCRIPT = ROOT / "src" / "main.py"


def variable_path(directory: str, italic: bool = False) -> Path:
	"""优先定位请求样式，来源没有斜体时保留直立字形"""
	paths = sorted((SOURCES / directory).glob("*VariableFont*.ttf"))
	if italic:
		for path in paths:
			if "Italic" in path.name:
				return path
	return next(path for path in paths if "Italic" not in path.name)


def font_path(config: FamilyConfig, italic: bool = False) -> Path:
	"""返回样式对应的发布文件路径"""
	style = "-Italic" if italic else ""
	return (
		PATCH / f"{config['patch'].replace(' ', '')}{style}-VariableFont_wdth,wght.ttf"
	)


def complete_font_path(config: FamilyConfig, italic: bool = False) -> Path:
	"""返回样式对应的完整字体发布文件路径"""
	style = "-Italic" if italic else ""
	return (
		COMPLETE
		/ f"{config['complete'].replace(' ', '')}{style}-VariableFont_wdth,wght.ttf"
	)


def source_hashes():
	"""记录所有仓库字体和许可证的哈希"""
	return {
		str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
		for path in sorted(SOURCES.glob("Noto_*/**/*"))
		if path.is_file() and (path.suffix == ".ttf" or path.name == "OFL.txt")
	}


def subset_font(path, codepoints):
	"""仅提取制作补丁所需的来源轮廓"""
	from fontTools import subset
	from fontTools.ttLib import TTFont

	font = TTFont(path, recalcTimestamp=False)
	options = subset.Options(
		layout_features=[], name_IDs=["*"], name_legacy=True, name_languages=["*"]
	)
	worker = subset.Subsetter(options=options)
	worker.populate(unicodes=codepoints)
	worker.subset(font)
	return font


def instantiate(font, weight, width, path):
	"""从变量字体的副本生成临时静态来源"""
	from fontTools.varLib.instancer import instantiateVariableFont

	instance = instantiateVariableFont(
		font, {"wght": weight, "wdth": width}, inplace=False, optimize=False
	)
	instance.save(path)
	instance.close()


def copyright_text():
	"""保留各来源版权声明并注明派生修改"""
	lines = []
	for path in sorted(SOURCES.glob("Noto_*/OFL.txt")):
		line = path.read_text(encoding="utf-8").splitlines()[0]
		if line not in lines:
			lines.append(line)
	lines.append(
		"Copyright 2026 Sha1 font contributors. Modifications to the original fonts."
	)
	return "\n".join(lines)


def write_license():
	"""为派生字体附上OFL"""
	license_text = (SOURCES / "Noto_Sans" / "OFL.txt").read_text(encoding="utf-8")
	license_text = copyright_text() + "\n\n" + license_text.split("\n\n", 1)[1]
	(DIST / "OFL.txt").write_text(license_text, encoding="utf-8")
