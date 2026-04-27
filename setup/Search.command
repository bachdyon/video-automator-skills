#!/usr/bin/env bash
set -e
cd "$(dirname "$0")/.."

if [ ! -x ".venv/bin/python" ]; then
    echo "Chưa cài đặt. Hãy chạy Install.command trước."
    read -n 1 -s -r -p "Nhấn phím bất kỳ để đóng..."
    exit 2
fi

echo "▶ Tìm kiếm asset semantic"
echo "  (gõ truy vấn tiếng Việt hoặc tiếng Anh, Enter để tìm; Ctrl+C để thoát)"
while true; do
    printf "\n? "
    if ! IFS= read -r query; then
        echo
        break
    fi
    if [ -z "$query" ]; then
        continue
    fi
    .venv/bin/python -m tools.asset_index.search "$query" --top 5 || true
done
