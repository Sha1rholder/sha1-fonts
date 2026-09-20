"""统一调度字体构建、核验和FontForge轮廓处理"""

import sys


def main() -> None:
	"""根据命令行参数选择构建、核验或FontForge工作进程"""
	command = sys.argv[1] if len(sys.argv) > 1 else None
	if command in {"build", "verify"}:
		del sys.argv[1]
	if command == "verify":
		from verification.runner import main as verify_main

		verify_main()
	elif command == "build" or command is None or command.startswith("-"):
		from build.pipeline import main as build_main
		from verification.runner import main as verify_main

		build_main()
		verify_main()
	else:
		from outlines.pipeline import main as fontforge_main

		fontforge_main()


if __name__ == "__main__":
	main()
