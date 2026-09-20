#!/usr/bin/env bash
set -euo pipefail

release_number=${SHA1_RELEASE_NUMBER:?SHA1_RELEASE_NUMBER is required}
if [[ ! $release_number =~ ^[1-9][0-9]{0,4}$ ]] || ((release_number > 32767)); then
	printf 'Invalid release number: %s\n' "$release_number" >&2
	exit 1
fi
tag="v${release_number}"
release_dir="temp/release"
mkdir -p "$release_dir"
draft_exists=false

# 已发布的工作流编号保持不变，重跑仅补完草稿
if gh release view "$tag" --json isDraft --jq '.isDraft' >"$release_dir/is-draft.txt"; then
	draft_exists=true
	if [[ $(cat "$release_dir/is-draft.txt") == false ]]; then
		printf 'Release %s is already published\n' "$tag"
		exit 0
	fi
fi

font_version="${release_number}.000"
jq -e --arg version "$font_version" '.version == $version' Sha1/manifest.json >/dev/null
jq -e --arg version "$font_version" '.version == $version' Sha1/verification.json >/dev/null
bash .github/scripts/package.sh
printf 'Version %s, built and verified from commit [%s](%s/%s/commit/%s).\n\nChoose one archive:\n- Sha1-Complete.7z: standalone complete fonts.\n- Sha1-Patch.7z: lightweight patches for use with the Noto font families.\n\nEach archive includes its fonts, OFL license, build manifest, and verification report.\n\nSHA-256 checksums:\n\n```text\n' \
	"$release_number" "$GITHUB_SHA" "$GITHUB_SERVER_URL" "$GH_REPO" "$GITHUB_SHA" >"$release_dir/notes.md"
cat "$release_dir/SHA256SUMS" >>"$release_dir/notes.md"
printf '```\n' >>"$release_dir/notes.md"

if [[ $draft_exists == false ]]; then
	gh release create "$tag" \
		--target "$GITHUB_SHA" \
		--title "Sha1 fonts $tag" \
		--notes-file "$release_dir/notes.md" \
		--draft
fi

gh release upload "$tag" "$release_dir/Sha1-Complete.7z" "$release_dir/Sha1-Patch.7z" --clobber

# 只有主分支当前提交可更新最新版，避免较慢的旧构建覆盖
latest=false
head_sha=$(gh api "repos/${GH_REPO}/commits/master" --jq '.sha')
if [[ $head_sha == "$GITHUB_SHA" ]]; then
	latest=true
fi
gh release edit "$tag" --notes-file "$release_dir/notes.md" --draft=false --latest="$latest"
