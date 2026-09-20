# Sha1字体

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

100%由GPT辅助开发

## 下载与构建

从[GitHub Releases](https://github.com/Sha1rholder/sha1-fonts/releases/latest)选择一个压缩包即可：

- `Sha1-Complete.7z`：可独立使用的完整字体，位于`Sha1/complete/`
- `Sha1-Patch.7z`：需要搭配Noto字体使用的轻量补丁，位于`Sha1/patch/`

每个压缩包都包含OFL许可证，以及对应系列的构建清单和验证报告。SHA-256校验和见Release说明

`Sha1/`为构建产物，已由Git忽略。每次向`master`推送更新，GitHub Actions都会构建并验证字体、运行回归测试，然后发布标签为`v<N>`的Release，其中`N`为发布工作流的运行编号，字体内部版本为`N.000`

重跑同一次任务时编号不变，失败的任务可能造成跳号。在`master`上手动运行工作流即可发布新版本，无需修改源码

本地构建和浏览器预览需要安装Git LFS、uv、支持Python脚本的FontForge和HarfBuzz，然后运行：

```sh
git lfs pull
uv run --frozen --project src python src/main.py build
uv run --frozen --project src python -m unittest discover -s src/tests -t src
```

本地构建默认版本为`0.000`。通过环境变量指定版本，无需修改源码：

```sh
SHA1_RELEASE_NUMBER=42 uv run --frozen --project src python src/main.py build
```

编号范围为0到32767。单独验证时会读取`Sha1/manifest.json`中的版本，不需要再次设置环境变量

详细说明见[构建文档](src/README.md)，浏览器预览使用本地构建的字体

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

# 许可证与来源

原始Noto文件保持不变。派生字体使用Sha1家族名称和PostScript名称，以SIL OFL 1.1发布。每个Release压缩包都包含构建生成的许可证`Sha1/OFL.txt`

实现参考：[FontForge的Python脚本接口](https://fontforge.org/docs/scripting/python.html)、[FontForge字形接口](https://fontforge.org/docs/scripting/python/fontforge.html)和[fontTools变量字体构建模块](https://fonttools.readthedocs.io/en/latest/varLib/index.html)
