#!/usr/bin/env bash
set -euo pipefail
shopt -s failglob

archiver=$(command -v 7zz || command -v 7z)
release_dir="$PWD/temp/release"
mkdir -p "$release_dir"

for series in Complete Patch; do
	kind=${series,,}
	stage=$(mktemp -d "$release_dir/${kind}.XXXXXX")
	mkdir -p "$stage/Sha1/$kind"
	cp Sha1/"$kind"/*.ttf "$stage/Sha1/$kind/"
	cp Sha1/OFL.txt "$stage/Sha1/"
	jq --arg prefix "$kind/" \
		'.fonts |= map(select(.file | startswith($prefix)))' \
		Sha1/manifest.json >"$stage/Sha1/manifest.json"
	if [[ $kind == complete ]]; then
		jq 'del(.fonts, .latin_styles)' Sha1/verification.json >"$stage/Sha1/verification.json"
	else
		jq 'del(.complete_fonts)' Sha1/verification.json >"$stage/Sha1/verification.json"
	fi
	archive="$release_dir/Sha1-$series.7z"
	# 重建压缩包，避免重跑时残留已经移除的文件
	rm -f "$archive"
	(
		cd "$stage"
		"$archiver" a -t7z -mx=7 "$archive" Sha1
	)
	rm -rf "$stage"
done

(
	cd "$release_dir"
	sha256sum Sha1-Complete.7z Sha1-Patch.7z >SHA256SUMS
)
