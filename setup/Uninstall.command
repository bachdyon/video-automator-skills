#!/usr/bin/env bash
set -e
cd "$(dirname "$0")/.."

if [ ! -x ".venv/bin/python" ]; then
    echo "Chưa cài đặt — không có gì để gỡ."
    read -n 1 -s -r -p "Nhấn phím bất kỳ để đóng..."
    exit 0
fi

echo "▶ Gỡ service asset-index"
.venv/bin/python -m tools.asset_index.service uninstall
echo
read -n 1 -s -r -p "Xong. Nhấn phím bất kỳ để đóng..."
echo
