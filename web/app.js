"use strict";

(() => {
	const $ = (selector) => document.querySelector(selector);
	const specimens = [...document.querySelectorAll(".specimen")];
	for (const specimen of specimens) {
		specimen.setAttribute("role", "group");
		specimen.setAttribute("aria-label", `${specimen.dataset.family === "mono" ? "Mono" : specimen.dataset.family === "serif" ? "Serif" : "Sans"}${specimen.dataset.kind === "patch" ? "Sha1补丁" : "原版Noto"}字体样本`);
	}
	const input = $("#test-text");
	const defaults = input.value;
	const controls = { size: $("#font-size"), weight: $("#font-weight"), width: $("#font-width"), italic: $("#italic") };
	const theme = $("#theme");
	theme.value = document.documentElement.dataset.theme || "system";
	theme.addEventListener("change", () => {
		if (theme.value === "system") delete document.documentElement.dataset.theme;
		else document.documentElement.dataset.theme = theme.value;
		try { localStorage.setItem("sha1-theme", theme.value); } catch {}
	});

	const globalStatus = $("#global-status");
	function notice(message) {
		globalStatus.hidden = false;
		globalStatus.textContent = message;
		for (const specimen of specimens) specimen.querySelector(".load-status").hidden = true;
	}
	if (!window.FontFace || !document.fonts) {
		notice("当前浏览器无法确认字体加载状态，字体样本暂不显示；你仍可获取字体使用");
		return;
	}

	let manifest;
	const faces = new Map();
	const localFonts = new Map();
	let guardsPromise;
	const segmenter = window.Intl?.Segmenter ? new Intl.Segmenter("zh", { granularity: "grapheme" }) : null;
	const ignorable = (point) => point === 9 || point === 10 || point === 13 || /\p{Default_Ignorable_Code_Point}/u.test(String.fromCodePoint(point));
	const contains = (ranges, point) => ranges.some(([start, end]) => point >= start && point <= end);
	const alias = (key, local = false) => `Sha1Web-${key}${local ? "-local" : ""}`;
	const descriptors = (font) => ({
		// 每个原生斜体来源使用独立别名，中文回退始终保持直立
		style: "normal", weight: font.axes.wght.join(" "),
		stretch: font.axes.wdth ? font.axes.wdth.map((value) => `${value}%`).join(" ") : "100%",
	});
	const unicodeRange = (ranges) => ranges.map(([start, end]) => `U+${start.toString(16)}${start === end ? "" : `-${end.toString(16)}`}`).join(",");

	function guards() {
		if (!guardsPromise) guardsPromise = (async () => {
			const response = await fetch(manifest.guard.file);
			if (!response.ok) throw new Error("Coverage guard unavailable");
			const data = await response.arrayBuffer();
			return Promise.all(["100%", "225%"].map(async (sizeAdjust, index) => {
				const face = await new FontFace(`Sha1Guard${index}`, data, { sizeAdjust }).load();
				if (face.sizeAdjust !== sizeAdjust) throw new Error("Size adjustment unavailable");
				document.fonts.add(face);
				return face;
			}));
		})();
		return guardsPromise;
	}

	function pixels(name, axis, value, text) {
		const canvas = document.createElement("canvas");
		canvas.width = 640;
		canvas.height = 100;
		const context = canvas.getContext("2d", { willReadFrequently: true });
		if (!context) throw new Error("Canvas unavailable");
		context.font = `${axis === "wght" ? value : 400} 64px "${name}"`;
		// Canvas匹配也需要请求对应字重/字宽，默认400/normal会覆盖face的轴默认值
		if (axis === "wdth") context.fontStretch = value === 62.5 ? "extra-condensed" : "normal";
		context.fillText(text, 10, 76);
		return context.getImageData(0, 0, canvas.width, canvas.height).data;
	}
	const different = (first, second) => first.some((value, index) => value !== second[index]);

	async function findLocal(key) {
		const font = manifest.fonts[key];
		if (!font.local.length) return null;
		const probes = [];
		const probeText = key.includes("_SC-") ? "中文" : "Hm012";
		try {
			const source = font.local.map((name) => `local(${JSON.stringify(name)})`).join(",");
			const face = new FontFace(alias(key, true), source, { ...descriptors(font), unicodeRange: unicodeRange(font.ranges) });
			await face.load();
			// local()命中并不证明它是可变字体；对每个所需轴单独比较真实轮廓
			for (const [axis, bounds] of Object.entries(font.axes)) {
				const images = [];
				for (const value of bounds) {
					const name = `Sha1Probe-${key}-${axis}-${value}`;
					const probe = await new FontFace(name, source, { ...descriptors(font), variationSettings: `"${axis}" ${value}` }).load();
					document.fonts.add(probe);
					probes.push(probe);
					images.push(pixels(name, axis, value, probeText));
				}
				if (!different(images[0], images[1])) return null;
			}
			await guards();
			document.fonts.add(face);
			const canvas = document.createElement("canvas");
			const context = canvas.getContext("2d");
			if (!context) { document.fonts.delete(face); return null; }
			const local = { face, context, coverage: new Map() };
			// 确认探针字形来自本地字体，避免fallback的变化被误认作可变轴响应
			if ([...probeText].some((char) => !localContains(local, key, char.codePointAt(0)))) {
				document.fonts.delete(face);
				return null;
			}
			return local;
		} catch {
			return null;
		} finally {
			for (const face of probes) document.fonts.delete(face);
		}
	}

	function localFor(key) {
		if (!localFonts.has(key)) localFonts.set(key, findLocal(key));
		return localFonts.get(key);
	}
	function localContains(local, key, point) {
		if (!local.coverage.has(point)) {
			const text = String.fromCodePoint(point);
			const widths = [0, 1].map((guard) => {
				local.context.font = `32px "${alias(key, true)}", "Sha1Guard${guard}"`;
				return local.context.measureText(text).width;
			});
			local.coverage.set(point, Math.abs(widths[0] - widths[1]) < .01);
		}
		return local.coverage.get(point);
	}

	function loadChunk(key, chunk) {
		const cacheKey = chunk.file;
		if (!faces.has(cacheKey)) {
			const face = new FontFace(alias(key), `url(${JSON.stringify(new URL(chunk.file, document.baseURI).href)})`, {
				...descriptors(manifest.fonts[key]), unicodeRange: unicodeRange(chunk.ranges),
			});
			const promise = face.load().then(() => { document.fonts.add(face); return face; }).catch((error) => {
				faces.delete(cacheKey); // 失败后创建新FontFace，让重试真的发起请求
				throw error;
			});
			faces.set(cacheKey, promise);
		}
		return faces.get(cacheKey);
	}
	async function ensureFont(key, points) {
		const local = await localFor(key);
		const needed = local ? [...points].filter((point) => !localContains(local, key, point)) : [...points];
		await Promise.all(manifest.fonts[key].chunks.filter((chunk) => needed.some((point) => contains(chunk.ranges, point))).map((chunk) => loadChunk(key, chunk)));
	}

	function fontChain(specimen, italic) {
		const family = manifest.families[specimen.dataset.family];
		const result = [];
		if (specimen.dataset.kind === "patch") {
			if (italic && family.patchItalic) result.push(family.patchItalic);
			result.push(family.patch);
		}
		if (italic && family.latinItalic) result.push(family.latinItalic);
		result.push(family.latin, family.cjk);
		return result;
	}
	function prepareText(text, chain) {
		const requirements = new Map();
		const fragments = [];
		const missing = new Set();
		const graphemes = segmenter ? [...segmenter.segment(text)].map((part) => part.segment) : [...text];
		for (const grapheme of graphemes) {
			const owners = [];
			let unsupported = false;
			for (const character of grapheme) {
				const point = character.codePointAt(0);
				// Emoji变体不能让数字或标点绕过缺字提示，再回退到系统emoji
				if (point === 0xfe0f || /\p{Emoji_Presentation}/u.test(character)) unsupported = true;
				if (ignorable(point)) continue;
				const key = chain.find((source) => contains(manifest.fonts[source].ranges, point));
				if (!key) unsupported = true;
				else owners.push([key, point]);
			}
			if (unsupported) {
				const label = [...grapheme].map((char) => `U+${char.codePointAt(0).toString(16).toUpperCase().padStart(4, "0")}`).join(" ");
				fragments.push({ missing: label });
				missing.add(label);
			} else {
				for (const [key, point] of owners) {
					if (!requirements.has(key)) requirements.set(key, new Set());
					requirements.get(key).add(point);
				}
				// 组合附加符号可能让浏览器为整个簇选字，提前加载能覆盖整簇的Noto来源
				if (owners.length > 1 && /\p{Mark}/u.test(grapheme)) {
					const source = chain.find((key) => owners.every(([, point]) => contains(manifest.fonts[key].ranges, point)));
					if (source) {
						if (!requirements.has(source)) requirements.set(source, new Set());
						for (const [, point] of owners) requirements.get(source).add(point);
					}
				}
				if (typeof fragments.at(-1) === "string") fragments[fragments.length - 1] += grapheme;
				else fragments.push(grapheme);
			}
		}
		return { requirements, fragments, missing };
	}

	async function render(specimen) {
		const revision = (specimen.revision || 0) + 1;
		specimen.revision = revision;
		const sample = specimen.querySelector(".font-sample");
		const status = specimen.querySelector(".load-status");
		const live = specimen.hasAttribute("data-live");
		const chain = fontChain(specimen, live && controls.italic.checked);
		const text = live ? input.value : specimen.dataset.text;
		const prepared = prepareText(text, chain);
		sample.hidden = true;
		specimen.setAttribute("aria-busy", "true");
		status.textContent = "正在加载所需字形…";
		status.hidden = false;
		specimen.querySelector(".missing-note")?.remove();
		// 长等待给出提示，但绝不因超时展示fallback
		const slow = setTimeout(() => {
			if (specimen.revision === revision) status.textContent = "字体仍在加载，请稍候…";
		}, 8000);
		try {
			await Promise.all([...prepared.requirements].map(([key, points]) => ensureFont(key, points)));
			if (specimen.revision !== revision) return;
			const fragment = document.createDocumentFragment();
			for (const part of prepared.fragments) {
				if (typeof part === "string") fragment.append(document.createTextNode(part));
				else {
					const marker = document.createElement("span");
					marker.className = "missing-glyph";
					marker.setAttribute("role", "img");
					marker.setAttribute("aria-label", `未收录字符${part.missing}`);
					marker.title = `未收录字符${part.missing}`;
					fragment.append(marker);
				}
			}
			sample.replaceChildren(fragment);
			sample.style.fontFamily = chain.flatMap((key) => [`"${alias(key)}"`, `"${alias(key, true)}"`]).join(",");
			applyAxes(sample, live);
			if (prepared.missing.size) {
				const note = document.createElement("p");
				note.className = "missing-note";
				note.textContent = `虚线框为未收录字符：${[...prepared.missing].slice(0, 6).join("、")}${prepared.missing.size > 6 ? "等" : ""}`;
				specimen.append(note);
			}
			sample.hidden = false;
			status.hidden = true;
		} catch {
			if (specimen.revision !== revision) return;
			status.textContent = "字体加载失败";
			const retry = document.createElement("button");
			retry.type = "button";
			retry.className = "text-button";
			retry.textContent = "重试";
			retry.addEventListener("click", () => render(specimen));
			status.append(retry);
		} finally {
			clearTimeout(slow);
			if (specimen.revision === revision) specimen.setAttribute("aria-busy", "false");
		}
	}

	function applyAxes(sample, live = true) {
		sample.style.fontWeight = live ? controls.weight.value : "400";
		sample.style.fontStretch = `${live ? controls.width.value : 100}%`;
		sample.style.fontVariationSettings = `"wght" ${live ? controls.weight.value : 400}, "wdth" ${live ? controls.width.value : 100}`;
	}
	function updateControls() {
		document.documentElement.style.setProperty("--sample-size", `${controls.size.value}px`);
		$("#size-value").value = `${controls.size.value}px`;
		$("#weight-value").value = controls.weight.value;
		$("#width-value").value = `${controls.width.value}%`;
		$("#italic-note").hidden = !controls.italic.checked;
	}
	let timer;
	let composing = false;
	function updateLive() {
		clearTimeout(timer);
		// 立即隐藏旧文本并使旧Promise失效，防抖只延迟新请求
		for (const specimen of specimens.filter((item) => item.hasAttribute("data-live"))) {
			specimen.revision = (specimen.revision || 0) + 1;
			specimen.querySelector(".font-sample").hidden = true;
			specimen.querySelector(".missing-note")?.remove();
		}
		if (!composing && manifest) timer = setTimeout(() => {
			for (const specimen of specimens.filter((item) => item.hasAttribute("data-live"))) render(specimen);
		}, 80);
	}
	input.addEventListener("compositionstart", () => { composing = true; });
	input.addEventListener("compositionend", () => { composing = false; updateLive(); });
	input.addEventListener("input", updateLive);
	controls.size.addEventListener("input", updateControls);
	for (const control of [controls.weight, controls.width]) control.addEventListener("input", () => {
		updateControls();
		for (const specimen of specimens.filter((item) => item.hasAttribute("data-live"))) applyAxes(specimen.querySelector(".font-sample"));
	});
	controls.italic.addEventListener("input", () => { updateControls(); updateLive(); });
	$("#reset").addEventListener("click", () => {
		input.value = defaults;
		controls.size.value = "28";
		controls.weight.value = "400";
		controls.width.value = "100";
		controls.italic.checked = false;
		updateControls();
		updateLive();
	});
	updateControls();
	async function start() {
		try {
			const response = await fetch("fonts.json");
			if (!response.ok) throw new Error("Font manifest unavailable");
			manifest = await response.json();
			for (const specimen of specimens) render(specimen);
		} catch {
			notice("字体清单加载失败");
			const retry = document.createElement("button");
			retry.className = "text-button";
			retry.textContent = "重试";
			retry.addEventListener("click", () => { globalStatus.hidden = true; start(); });
			globalStatus.append(" ", retry);
		}
	}
	start();
})();
