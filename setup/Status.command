#!/usr/bin/env bash
set -e
cd "$(dirname "$0")/.."

if [ ! -x ".venv/bin/python" ]; then
    echo "Chưa cài đặt. Hãy chạy Install.command trước."
    read -n 1 -s -r -p "Nhấn phím bất kỳ để đóng..."
    exit 2
fi

echo "▶ Trạng thái service & watcher"
.venv/bin/python -m tools.asset_index.service status
echo
read -n 1 -s -r -p "Nhấn phím bất kỳ để đóng..."
echo
