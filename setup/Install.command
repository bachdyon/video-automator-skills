#!/usr/bin/env bash
set -e
cd "$(dirname "$0")/.."
echo "▶ Asset-index installer (macOS)"

if ! command -v python3 >/dev/null 2>&1; then
    echo "Bạn cần Python 3.10+ tại https://www.python.org/downloads/"
    read -n 1 -s -r -p "Nhấn phím bất kỳ để đóng cửa sổ..."
    exit 2
fi

python3 tools/asset_index/bootstrap.py "$@"
echo
read -n 1 -s -r -p "Xong. Nhấn phím bất kỳ để đóng cửa sổ..."
echo
