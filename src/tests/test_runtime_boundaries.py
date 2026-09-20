"""核验命令入口与FontForge运行时的隔离"""

import subprocess
import tempfile
import unittest

from lib import ROOT


class RuntimeBoundaryTests(unittest.TestCase):
	"""检查拆分模块后仍可独立导入和从外部目录启动"""

	def test_fonttools_imports_without_fontforge(self):
		"""在新进程中导入全部普通模块且不加载轮廓运行时"""
		source = ROOT / "src"
		modules = [
			".".join(path.relative_to(source).with_suffix("").parts)
			for path in sorted(source.rglob("*.py"))
			if "outlines" not in path.parts
			and "tests" not in path.parts
			and ".venv" not in path.parts
			and ".ruff_cache" not in path.parts
			and path.name != "__init__.py"
		]
		code = (
			"import importlib, sys\n"
			f"for name in {modules!r}:\n"
			"    importlib.import_module(name)\n"
			"assert 'fontforge' not in sys.modules\n"
			"assert 'psMat' not in sys.modules\n"
			"assert not any(name.startswith('outlines.') for name in sys.modules)\n"
		)
		result = subprocess.run(
			["uv", "run", "--project", str(source), "python", "-c", code],
			cwd=ROOT / "src",
			capture_output=True,
			text=True,
			check=False,
		)
		self.assertEqual(result.returncode, 0, result.stderr)

	def test_build_entrypoint_from_another_directory(self):
		"""确认入口导入不依赖当前工作目录或手工设置模块路径"""
		(ROOT / "temp").mkdir(exist_ok=True)
		with tempfile.TemporaryDirectory(dir=ROOT / "temp") as directory:
			result = subprocess.run(
				[
					"uv",
					"run",
					"--project",
					str(ROOT / "src"),
					"python",
					str(ROOT / "src" / "main.py"),
					"--help",
				],
				cwd=directory,
				capture_output=True,
				text=True,
				check=False,
			)
		self.assertEqual(result.returncode, 0, result.stderr)
		self.assertIn("--reuse-outlines", result.stdout)
