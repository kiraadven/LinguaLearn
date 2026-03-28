#!/usr/bin/env bash
set -euo pipefail

# Download required export fonts into static/fonts/
# Usage:
#   bash scripts/download_fonts.sh

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FONT_DIR="$ROOT_DIR/static/fonts"
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

mkdir -p "$FONT_DIR"

download_url() {
  local url="$1"
  local out="$2"
  if curl -fL --retry 3 --connect-timeout 15 "$url" -o "$FONT_DIR/$out"; then
    return 0
  fi

  # Mirror fallback for environments where raw.githubusercontent.com is unstable.
  if [[ "$url" == https://raw.githubusercontent.com/google/fonts/main/* ]]; then
    local mirror
    mirror="${url/https:\/\/raw.githubusercontent.com\/google\/fonts\/main\//https:\/\/cdn.jsdelivr.net\/gh\/google\/fonts@main\/}"
    curl -fL --retry 3 --connect-timeout 15 "$mirror" -o "$FONT_DIR/$out"
    return $?
  fi

  return 1
}

download_from_family_zip() {
  local family="$1"
  local out="$2"
  local match_regex="$3"
  local zip_path="$TMP_DIR/${out}.zip"
  local extract_dir="$TMP_DIR/${out}_extract"

  rm -rf "$extract_dir"
  mkdir -p "$extract_dir"

  curl -fL --retry 3 --connect-timeout 15 \
    "https://fonts.google.com/download?family=${family}" \
    -o "$zip_path"

  unzip -qo "$zip_path" -d "$extract_dir"

  local picked
  picked="$(find "$extract_dir" -type f \( -iname "*.ttf" -o -iname "*.otf" \) \
    | grep -E "$match_regex" \
    | head -n 1 || true)"

  if [[ -z "$picked" ]]; then
    return 1
  fi

  cp "$picked" "$FONT_DIR/$out"
}

download_with_fallback() {
  local out="$1"
  local family="$2"
  local match_regex="$3"
  shift 3
  local urls=("$@")

  echo "→ $out"

  for url in "${urls[@]}"; do
    if [[ -z "$url" ]]; then
      continue
    fi
    if download_url "$url" "$out" >/dev/null 2>&1; then
      echo "  ✓ direct"
      return 0
    fi
  done

  if download_from_family_zip "$family" "$out" "$match_regex" >/dev/null 2>&1; then
    echo "  ✓ family-zip fallback"
    return 0
  fi

  echo "  ✗ failed: $out" >&2
  return 1
}

# NOTE:
# Some families only provide variable font files. We rename to *-Regular.ttf
# because the render pipeline matches filenames, not internal style names.

download_with_fallback "NotoSerifSC-Regular.ttf" "Noto Serif SC" "NotoSerifSC|NotoSerif.*SC|SerifSC" \
  "https://raw.githubusercontent.com/google/fonts/main/ofl/notoserifsc/NotoSerifSC-Regular.ttf" \
  "https://raw.githubusercontent.com/google/fonts/main/ofl/notoserifsc/NotoSerifSC%5Bwght%5D.ttf"

download_with_fallback "ZCOOLXiaoWei-Regular.ttf" "ZCOOL XiaoWei" "XiaoWei|ZCOOLXiaoWei" \
  "https://raw.githubusercontent.com/google/fonts/main/ofl/zcoolxiaowei/ZCOOLXiaoWei-Regular.ttf"

download_with_fallback "MaShanZheng-Regular.ttf" "Ma Shan Zheng" "MaShanZheng|Ma.*Shan.*Zheng" \
  "https://raw.githubusercontent.com/google/fonts/main/ofl/mashanzheng/MaShanZheng-Regular.ttf"

download_with_fallback "LongCang-Regular.ttf" "Long Cang" "LongCang|Long.*Cang" \
  "https://raw.githubusercontent.com/google/fonts/main/ofl/longcang/LongCang-Regular.ttf"

download_with_fallback "ZhiMangXing-Regular.ttf" "Zhi Mang Xing" "ZhiMangXing|Zhi.*Mang.*Xing" \
  "https://raw.githubusercontent.com/google/fonts/main/ofl/zhimangxing/ZhiMangXing-Regular.ttf"

download_with_fallback "ZCOOLQingKeHuangYou-Regular.ttf" "ZCOOL QingKe HuangYou" "QingKe|ZCOOLQingKeHuangYou" \
  "https://raw.githubusercontent.com/google/fonts/main/ofl/zcoolqingkehuangyou/ZCOOLQingKeHuangYou-Regular.ttf"

download_with_fallback "NotoSansJP-Regular.ttf" "Noto Sans JP" "NotoSansJP|NotoSans.*JP" \
  "https://raw.githubusercontent.com/google/fonts/main/ofl/notosansjp/NotoSansJP%5Bwght%5D.ttf"

download_with_fallback "NotoSansKR-Regular.ttf" "Noto Sans KR" "NotoSansKR|NotoSans.*KR" \
  "https://raw.githubusercontent.com/google/fonts/main/ofl/notosanskr/NotoSansKR%5Bwght%5D.ttf"

download_with_fallback "DancingScript-Regular.ttf" "Dancing Script" "DancingScript|Dancing.*Script" \
  "https://raw.githubusercontent.com/google/fonts/main/ofl/dancingscript/DancingScript%5Bwght%5D.ttf"

download_with_fallback "Caveat-Regular.ttf" "Caveat" "Caveat" \
  "https://raw.githubusercontent.com/google/fonts/main/ofl/caveat/Caveat%5Bwght%5D.ttf"

download_with_fallback "Bitter-Regular.ttf" "Bitter" "Bitter" \
  "https://raw.githubusercontent.com/google/fonts/main/ofl/bitter/Bitter%5Bwght%5D.ttf"

download_with_fallback "Quicksand-Regular.ttf" "Quicksand" "Quicksand" \
  "https://raw.githubusercontent.com/google/fonts/main/ofl/quicksand/Quicksand%5Bwght%5D.ttf"

download_with_fallback "Rajdhani-Regular.ttf" "Rajdhani" "Rajdhani" \
  "https://raw.githubusercontent.com/google/fonts/main/ofl/rajdhani/Rajdhani-Regular.ttf" \
  "https://raw.githubusercontent.com/google/fonts/main/ofl/rajdhani/Rajdhani%5Bwght%5D.ttf"

echo
echo "Done. Downloaded fonts to: $FONT_DIR"
echo "Files:"
ls -1 "$FONT_DIR" | sed -n '1,200p'
