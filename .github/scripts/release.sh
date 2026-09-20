#!/usr/bin/env bash
set -euo pipefail

tag="build-${GITHUB_SHA}"
release_dir="temp/release"
mkdir -p "$release_dir"

# 已发布的提交保持不变，重跑仅补完草稿
if gh release view "$tag" --json isDraft --jq '.isDraft' >"$release_dir/is-draft.txt"; then
	if [[ $(cat "$release_dir/is-draft.txt") == false ]]; then
		printf 'Release %s is already published\n' "$tag"
		exit 0
	fi
else
	printf 'Built and verified from commit [%s](%s/%s/commit/%s).\n\nDownload Sha1-fonts.zip for complete fonts, patches, the OFL license, and build and verification reports. Verify the archive with SHA256SUMS.\n' \
		"$GITHUB_SHA" "$GITHUB_SERVER_URL" "$GH_REPO" "$GITHUB_SHA" >"$release_dir/notes.md"
	gh release create "$tag" \
		--target "$GITHUB_SHA" \
		--title "Sha1 fonts ${GITHUB_SHA:0:12}" \
		--notes-file "$release_dir/notes.md" \
		--draft
fi

zip -q -r "$release_dir/Sha1-fonts.zip" Sha1
(
	cd "$release_dir"
	sha256sum Sha1-fonts.zip >SHA256SUMS
)
gh release upload "$tag" "$release_dir/Sha1-fonts.zip" "$release_dir/SHA256SUMS" --clobber

# 只有主分支当前提交可更新最新版，避免较慢的旧构建覆盖
latest=false
head_sha=$(gh api "repos/${GH_REPO}/commits/master" --jq '.sha')
if [[ $head_sha == "$GITHUB_SHA" ]]; then
	latest=true
fi
gh release edit "$tag" --draft=false --latest="$latest"
