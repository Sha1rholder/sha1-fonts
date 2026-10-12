"""浏览器验收夹具：真实字体模拟本地查找，以及慢网和请求失败"""

import base64
import io
import json
import sys
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont

DIST = Path(__file__).resolve().parents[2] / "dist"
MANIFEST = json.loads((DIST / "fonts.json").read_text())


def local_fixture(static=False):
	entries = []
	for font in MANIFEST["fonts"].values():
		if not font["local"]:
			continue
		data = (DIST / font["chunks"][0]["file"]).read_bytes()
		if static:
			with TTFont(io.BytesIO(data)) as original:
				location = {
					"wght": 400,
					**({"wdth": 100} if "wdth" in font["axes"] else {}),
				}
				face = instantiateVariableFont(original, location, inplace=False)
				buffer = io.BytesIO()
				face.save(buffer)
				data = buffer.getvalue()
		entries.append(
			{"names": font["local"], "data": base64.b64encode(data).decode()}
		)
	return """(() => {
		const Native = window.FontFace;
		const entries = %s;
		window.FontFace = class extends Native {
			constructor(name, source, options) {
				if (typeof source === 'string' && source.startsWith('local(')) {
					const entry = entries.find(entry => entry.names.some(name => source.includes(JSON.stringify(name))));
					if (entry) source = Uint8Array.from(atob(entry.data), char => char.charCodeAt(0));
				}
				super(name, source, options);
			}
		};
	})();""" % json.dumps(entries)


FIXTURES = {
	"variable": local_fixture(),
	"static": local_fixture(True),
	"noapi": "window.FontFace = undefined;",
}


class Handler(SimpleHTTPRequestHandler):
	failed_once = False

	def __init__(self, *args, **kwargs):
		super().__init__(*args, directory=str(DIST), **kwargs)

	def do_GET(self):
		parts = urlsplit(self.path).path.strip("/").split("/", 1)
		mode = parts[0]
		if mode not in {"variable", "static", "slow", "failure", "none", "noapi"}:
			self.send_error(404)
			return
		self.path = "/" + (parts[1] if len(parts) > 1 else "")
		if self.path in ("/", "/index.html"):
			html = (DIST / "index.html").read_text()
			if mode in FIXTURES:
				html = html.replace(
					'<script src="app.js" defer></script>',
					f'<script>{FIXTURES[mode]}</script><script src="app.js" defer></script>',
				)
			data = html.encode()
			self.send_response(200)
			self.send_header("Content-Type", "text/html; charset=utf-8")
			self.send_header("Content-Length", str(len(data)))
			self.end_headers()
			self.wfile.write(data)
			return
		if self.path.endswith(".woff2"):
			if mode == "slow":
				time.sleep(2)
			if (
				mode == "failure"
				and "/mono-patch-" in self.path
				and not Handler.failed_once
			):
				Handler.failed_once = True
				self.send_error(503, "Intentional font failure")
				return
		super().do_GET()


if __name__ == "__main__":
	port = int(sys.argv[1]) if len(sys.argv) > 1 else 8767
	print(
		f"Browser QA: http://127.0.0.1:{port}/variable/ (static, slow, failure, none, noapi)",
		flush=True,
	)
	ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
