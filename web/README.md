# Sha1展示网页

独立的静态展示页，不修改开发者使用的根目录预览

页面先按编程、写作两个场景展示原版Noto与Sha1的对照，再提供自由输入。编程样本使用Mono，覆盖箭头、易混淆字母与数字、全角标点和竖线；写作样本同时使用Sans与Serif，展示引号、省略号与破折号。所有固定样本关闭连字并使用相同的对照排版，竖线示例单独采用紧凑行距

## 构建与预览

从仓库根目录运行，首次使用需要先生成Patch：

```sh
uv run --project src python src/main.py build
uv run --project src --extra web python web/build.py
uv run --project src python -m http.server 8766 --bind 127.0.0.1 --directory dist
```

打开[本地展示页](http://127.0.0.1:8766/)

修改HTML、CSS或JS后重新运行网页构建。字体子集缓存位于`temp/web-fonts/`，按来源文件、字符集和fontTools版本复用；生成的`dist/`和缓存不提交Git

整个`dist/`可直接交给静态托管服务。页面和字体使用相对路径，兼容GitHub Pages项目子路径，许可证在`dist/licenses/`

## 自动部署

[Pages工作流](../.github/workflows/pages.yml)在`master`分支的网页、构建代码、Noto来源字体或工作流更新后，从GitHub latest release下载`Sha1-Patch.7z`，构建网页、验证网页资产，并将`dist/`部署到GitHub Pages。字体发布工作流成功结束后也会更新网页。PR执行相同的下载、构建与验证，但不部署；也可从Actions页面手动触发，只有`master`分支会部署

首次使用需在仓库Settings → Pages → Build and deployment中将Source设为GitHub Actions

构建按分支和触发事件分别控制并发，同组的新构建会取消旧构建；推送与字体发布后的构建互不取消。部署单独排队，不取消正在进行的部署

网页产物名包含运行ID和重跑次数，部署使用构建任务输出的产物名，避免重跑后同名产物冲突；仅重跑部署时仍使用上次成功构建的产物

## 字体加载

- 部署时Patch来自GitHub latest release，本地预览可使用本地构建，不使用完整Sha1字体
- Noto保留可变轴，基础子集覆盖固定样本、默认输入和ASCII，其余按256码位区间生成独立WOFF2
- 字体清单记录真实cmap覆盖、轴范围、每个资源的字节数和本地字体名，不通过字体加载API的成功结果推测缺字情况
- 本地Noto先检查每个可变轴的实际轮廓变化，再复用一份按需加载的检测字体，通过不同度量检查当前字符覆盖；静态版、未命中和缺字均使用同源子集
- 原生斜体使用独立CSS别名，缺少斜体的中文与Mono保持直立；不启用字体合成
- 每个样本等待实际所需字体就绪后显示，失败后保留隐藏并允许重试；缺字使用CSS占位，不调用系统字体
- 页面文字不上传、不持久存储；仅主题偏好保存在localStorage

## 验证

```sh
uv run --project src --extra web python -m unittest discover -s web/tests
```

测试验证真实WOFF2的覆盖、轴、补丁字形与来源一致性和许可证。浏览器中检查输入、主题、中文输入法、断网重试及移动布局；开发者预览与字体回归页保持原状

可启动独立的浏览器验收服务，不影响正常预览或部署产物：

```sh
uv run --project src --extra web python web/tests/browser_server.py
```

在`http://127.0.0.1:8767/`后选择`variable/`、`static/`、`none/`、`slow/`、`failure/`或`noapi/`

`variable/`和`static/`使用真实WOFF2及其静态实例模拟本地字体查找；`slow/`延迟字体响应2秒；`failure/`让首次Mono Patch请求返回503，随后可重试恢复；`noapi/`禁用字体加载API。这些夹具只存在于测试服务，网页构建不会包含它们
