#!/usr/bin/env bash
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel)"
DST="$ROOT/src/competitive_verifier_resources/jekyll/assets/vendor"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

LICENSES_FILE="$ROOT/3rd-party-license.txt"
LEGACY_LICENSES_FILE="$ROOT/3rd-party-lisence.txt"
BEGIN_MARKER="BEGIN GENERATED VENDORED DOC ASSET LICENSES"
END_MARKER="END GENERATED VENDORED DOC ASSET LICENSES"

MATHJAX_VERSION="3.2.2"
HIGHLIGHTJS_VERSION="11.6.0"
HINTCSS_VERSION="2.7.0"

if [[ ! -f "$LICENSES_FILE" && -f "$LEGACY_LICENSES_FILE" ]]; then
  echo "::error::$LEGACY_LICENSES_FILE exists, but $LICENSES_FILE does not. Rename it first: git mv 3rd-party-lisence.txt 3rd-party-license.txt"
  exit 1
fi

require_command() {
  local command_name="$1"

  if ! command -v "$command_name" >/dev/null 2>&1; then
    echo "::error::required command not found: $command_name"
    exit 1
  fi
}

extract_npm_package() {
  local spec="$1"
  local out="$2"
  local tgz

  mkdir -p "$out"

  (
    cd "$TMP"
    npm_config_ignore_scripts=true npm pack --silent "$spec" > "$out/tarball-name.txt"
  )

  tgz="$(tail -n 1 "$out/tarball-name.txt")"
  tar -xzf "$TMP/$tgz" -C "$out"
}

copy_license_file() {
  local package_dir="$1"
  local destination="$2"
  local candidate

  for candidate in LICENSE LICENSE.md LICENSE.txt COPYING COPYING.md COPYING.txt; do
    if [[ -f "$package_dir/$candidate" ]]; then
      cp "$package_dir/$candidate" "$destination"
      return 0
    fi
  done

  echo "::error::license file not found under $package_dir"
  exit 1
}

copy_optional_notice_file() {
  local package_dir="$1"
  local destination="$2"
  local candidate

  for candidate in NOTICE NOTICE.md NOTICE.txt; do
    if [[ -f "$package_dir/$candidate" ]]; then
      cp "$package_dir/$candidate" "$destination"
      return 0
    fi
  done

  return 0
}

append_license_section() {
  local title="$1"
  local license_file="$2"
  local notice_file="${3:-}"

  printf -- '-----\n' >> "$TMP/generated-vendored-doc-licenses.txt"
  printf '%s\n\n' "$title" >> "$TMP/generated-vendored-doc-licenses.txt"
  cat "$license_file" >> "$TMP/generated-vendored-doc-licenses.txt"
  printf '\n' >> "$TMP/generated-vendored-doc-licenses.txt"

  if [[ -n "$notice_file" && -f "$notice_file" ]]; then
    printf '\nNOTICE\n\n' >> "$TMP/generated-vendored-doc-licenses.txt"
    cat "$notice_file" >> "$TMP/generated-vendored-doc-licenses.txt"
    printf '\n' >> "$TMP/generated-vendored-doc-licenses.txt"
  fi
}

write_versions_file() {
  {
    printf 'mathjax@%s\n' "$MATHJAX_VERSION"
    printf '@highlightjs/cdn-assets@%s\n' "$HIGHLIGHTJS_VERSION"
    printf 'hint.css@%s\n' "$HINTCSS_VERSION"
  } > "$DST/VERSIONS.txt"
}

# Update root 3rd-party-license.txt idempotently.
write_root_license_file() {
  local base_file="$TMP/3rd-party-license.base.txt"
  local stripped_base_file="$TMP/3rd-party-license.stripped.txt"

  if [[ -f "$LICENSES_FILE" ]]; then
    awk -v begin="$BEGIN_MARKER" -v end="$END_MARKER" '
      $0 == begin { skip = 1; next }
      $0 == end { skip = 0; next }
      !skip { print }
    ' "$LICENSES_FILE" > "$base_file"
  else
    : > "$base_file"
  fi

  # Strip all trailing blank lines from the base part.
  awk '
    { lines[NR] = $0 }
    END {
      last = NR
      while (last > 0 && lines[last] ~ /^[[:space:]]*$/) {
        --last
      }
      for (i = 1; i <= last; ++i) {
        print lines[i]
      }
    }
  ' "$base_file" > "$stripped_base_file"

  cp "$stripped_base_file" "$LICENSES_FILE"

  # Keep exactly one blank line between existing content and generated block.
  if [[ -s "$LICENSES_FILE" ]]; then
    printf '\n' >> "$LICENSES_FILE"
  fi

  printf '%s\n' "$BEGIN_MARKER" >> "$LICENSES_FILE"
  cat "$TMP/generated-vendored-doc-licenses.txt" >> "$LICENSES_FILE"
  printf '%s\n' "$END_MARKER" >> "$LICENSES_FILE"
}

require_command git
require_command npm
require_command tar

rm -rf "$DST"
mkdir -p \
  "$DST/mathjax" \
  "$DST/highlight/styles" \
  "$DST/hint"

# MathJax 3
extract_npm_package "mathjax@$MATHJAX_VERSION" "$TMP/mathjax"
cp -a "$TMP/mathjax/package/es5" "$DST/mathjax/"
copy_license_file "$TMP/mathjax/package" "$DST/mathjax/LICENSE.txt"
copy_optional_notice_file "$TMP/mathjax/package" "$DST/mathjax/NOTICE.txt"

# highlight.js
extract_npm_package "@highlightjs/cdn-assets@$HIGHLIGHTJS_VERSION" "$TMP/highlight"
cp "$TMP/highlight/package/highlight.min.js" "$DST/highlight/highlight.min.js"
cp -a "$TMP/highlight/package/styles/." "$DST/highlight/styles/"
copy_license_file "$TMP/highlight/package" "$DST/highlight/LICENSE.txt"
copy_optional_notice_file "$TMP/highlight/package" "$DST/highlight/NOTICE.txt"

# hint.css
extract_npm_package "hint.css@$HINTCSS_VERSION" "$TMP/hint"
cp "$TMP/hint/package/hint.min.css" "$DST/hint/hint.min.css"
copy_license_file "$TMP/hint/package" "$DST/hint/LICENSE.txt"
copy_optional_notice_file "$TMP/hint/package" "$DST/hint/NOTICE.txt"

write_versions_file

# Also publish a license bundle as part of generated documentation assets.
: > "$TMP/generated-vendored-doc-licenses.txt"

append_license_section \
  "MathJax npm package mathjax@$MATHJAX_VERSION" \
  "$DST/mathjax/LICENSE.txt" \
  "$DST/mathjax/NOTICE.txt"

append_license_section \
  "highlight.js CDN assets @highlightjs/cdn-assets@$HIGHLIGHTJS_VERSION" \
  "$DST/highlight/LICENSE.txt" \
  "$DST/highlight/NOTICE.txt"

append_license_section \
  "hint.css npm package hint.css@$HINTCSS_VERSION" \
  "$DST/hint/LICENSE.txt" \
  "$DST/hint/NOTICE.txt"

cp "$TMP/generated-vendored-doc-licenses.txt" "$DST/THIRD_PARTY_LICENSES.txt"
write_root_license_file

echo "Vendored assets written to $DST"
echo "Updated $LICENSES_FILE"