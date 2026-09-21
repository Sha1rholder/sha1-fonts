# Sha1字体

Noto系列的字体补丁，对中英混输时的易混淆字符实现更高区分度并优化部分符号在不开启连字时的表现

易混淆字符：
- `I` `l` `1` `7` `|`
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

Vibe-coded by GPT.

从[GitHub Releases](https://github.com/Sha1rholder/sha1-fonts/releases/latest)选择一个压缩包：
- `Sha1-Complete.7z`：可独立使用的完整字体
- `Sha1-Patch.7z`：需要搭配Noto系列字体使用的轻量补丁

## Sha1 Sans

Sha1 Sans = Sha1 Sans Patch + Noto Sans + Noto Sans SC

- `l`: Noto Sans SC加Variable font
- `1`: Noto Sans顶部加实心三角flag，底部加短横，步进缩短15%
- `|`: Noto Sans加长占满高度，中间加个实心小圆点
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
- `1`: Noto Sans Mono顶部加实心三角flag，底部横线稍微缩短
- `|`: Noto Sans Mono加长占满高度，中间加个实心小圆点
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

- `1`: Noto Serif顶部加实心三角flag，底部横线稍微缩短
- `|`: Noto Serif加长占满高度，中间加个实心小圆点
- `：` `；` `！` `？`: Noto Serif SC小圆点改成类似`。`的空心圆
- `！` `？`: 主体上移且空心圆点下移
- `，` `；` `！` `？`: 实心部分加粗使其匹配空心圆点的视觉重量
- `、` `，` `。` `：` `；` `！` `？`整体右移1/8步进宽度
- `（` `）`: Noto Serif SC宽度减至原来的2/3，横线从字格1/5或4/5处连接到主笔画中心
- `0`: Noto Serif改点零
- `O`: 自定义艺术字体
- `-`: Noto Serif上移到和Noto Serif的`>`中间持平
- `…`: Noto Serif上移到和Noto Serif的`>`中间持平

# 许可证与来源

原始Noto文件保持不变。派生字体使用Sha1家族名称和PostScript名称，以SIL OFL 1.1发布。每个Release压缩包都包含构建生成的许可证`Sha1/OFL.txt`

实现参考：[FontForge的Python脚本接口](https://fontforge.org/docs/scripting/python.html)、[FontForge字形接口](https://fontforge.org/docs/scripting/python/fontforge.html)和[fontTools变量字体构建模块](https://fonttools.readthedocs.io/en/latest/varLib/index.html)
