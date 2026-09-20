# Sha1 fonts

Noto系列的字体补丁，对中英混输时的易混淆字符实现更高区分度并优化部分符号在不开启连字时的表现

易混淆字符：
- `I` `l` `1` `|`
- `,` `，`
- `:` `：`
- `;` `；`
- `!` `！`
- `?` `？`
- `'` `‘` `’`
- `"` `“` `”`
- `(` `（`
- `)` `）`
- `0` `O`

其它优化：
- `、`
- `。`
- `->`
- `…`
- `—`

100% vibe coded with GPT.

## Download and build

Download `Sha1-fonts.zip` from [GitHub Releases](https://github.com/Sha1rholder/sha1-fonts/releases/latest). The archive contains `Sha1/complete/`, `Sha1/patch/`, the OFL license, the build manifest, and the verification report. `SHA256SUMS` contains the archive checksum.

`Sha1/` is generated and ignored by Git. Every push to `master` builds and verifies the fonts, runs the regression tests, and publishes a release tagged `build-<commit SHA>`. The workflow can also be run manually on `master`.

For local builds and browser previews, install Git LFS, uv, FontForge with Python scripting support, and HarfBuzz, then run:

```sh
git lfs pull
uv run --frozen --project src python src/main.py build
uv run --frozen --project src python -m unittest discover -s src/tests -t src
```

See [the build documentation](src/README.md) for details. To preview a downloaded release, extract its `Sha1/` directory into the repository root.

## Sha1 Sans

Sha1 Sans = Sha1 Sans Patch + Noto Sans + Noto Sans SC

- `l`: Noto Sans SC加Variable font
- `|`: Noto Sans加长，中间加个实心小圆点
- `：` `；` `！` `？`: Noto Sans SC小圆点改成类似`。`的空心圆
- `！` `？`: 主体上移且空心圆点下移
- `，` `；` `！` `？`: 实心部分加粗使其匹配空心圆点的视觉重量
- `、` `，` `。` `：` `；` `！` `？`整体右移1/8步进宽度
- `‘` `’` `“` `”`: Noto Serif
- `（` `）`: Noto Sans SC宽度减至原来的2/3，横线从字格1/5或4/5处连接到主笔画中心
- `0`: Noto Sans改点零
- `O`: 自定义艺术字体
- `-`: Noto Sans上移到和Noto Sans的`>`中间持平
- `…`: Noto Sans上移到和Noto Sans的`>`中间持平

## Sha1 Sans Mono

Sha1 Sans Mono = Sha1 Sans Mono Patch + Noto Sans Mono + Noto Sans SC

- `l`: Noto Sans Mono去掉左下角的横
- `1`: Noto Sans Mono去掉底部的横
- `|`: Noto Sans Mono加长，中间加个实心小圆点
- `：` `；` `！` `？`: Noto Sans SC小圆点改成类似`。`的空心圆
- `！` `？`: 主体上移且空心圆点下移
- `，` `；` `！` `？`: 实心部分加粗使其匹配空心圆点的视觉重量
- `、` `，` `。` `：` `；` `！` `？`整体右移1/8步进宽度
- `‘` `’` `“` `”`: Noto Serif改等宽
- `（` `）`: Noto Sans SC宽度减至原来的2/3，横线从字格1/5或4/5处连接到主笔画中心
- `0`: Noto Sans Mono改点零
- `O`: 自定义艺术字体
- `-`: Noto Sans Mono上移到和Noto Sans Mono的`>`中间持平
- `…`: Noto Sans Mono上移到和Noto Sans Mono的`>`中间持平
- `—`: Noto Sans

## Sha1 Serif

Sha1 Serif = Sha1 Serif Patch + Noto Serif + Noto Serif SC

- `|`: Noto Serif加长，中间加个实心小圆点
- `：` `；` `！` `？`: Noto Serif SC小圆点改成类似`。`的空心圆
- `！` `？`: 主体上移且空心圆点下移
- `，` `；` `！` `？`: 实心部分加粗使其匹配空心圆点的视觉重量
- `、` `，` `。` `：` `；` `！` `？`整体右移1/8步进宽度
- `（` `）`: Noto Serif SC宽度减至原来的2/3，横线从字格1/5或4/5处连接到主笔画中心
- `0`: Noto Serif改点零
- `O`: 自定义艺术字体
- `-`: Noto Serif上移到和Noto Serif的`>`中间持平
- `…`: Noto Serif上移到和Noto Serif的`>`中间持平

# License and provenance

All original Noto files remain unchanged. The derived fonts use Sha1 family and PostScript names and are released under SIL OFL 1.1. Each build includes the generated license at `Sha1/OFL.txt` in the release archive.

Implementation references: [FontForge Python scripting](https://fontforge.org/docs/scripting/python.html), [FontForge glyph API](https://fontforge.org/docs/scripting/python/fontforge.html), and [fontTools varLib](https://fonttools.readthedocs.io/en/latest/varLib/index.html).
