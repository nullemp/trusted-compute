#!/usr/bin/env bash
# Download examples Python wheels for offline install.
# Run from project root (with network). Requires Python with pip.
set -e
cd "$(dirname "$0")/.."

REQ="examples/requirements.txt"
OUT_DIR="examples/offline_wheels"

if [[ ! -f "$REQ" ]]; then
  echo "Not found: $REQ" >&2
  exit 1
fi

if ! command -v python3 &>/dev/null; then
  if ! command -v python &>/dev/null; then
    echo "Python not found. Install Python and run: python3 -m pip download -r $REQ -d $OUT_DIR" >&2
    exit 1
  fi
  PYTHON=python
else
  PYTHON=python3
fi

mkdir -p "$OUT_DIR"
# 若系统设置了不可用的代理，pip 会报 ProxyError；在子 shell 中临时取消代理，直连 PyPI
(
  for k in HTTP_PROXY HTTPS_PROXY http_proxy https_proxy ALL_PROXY all_proxy; do unset "$k"; done
  "$PYTHON" -m pip download -r "$REQ" -d "$OUT_DIR"
)
echo "Wheels saved to: $OUT_DIR"
