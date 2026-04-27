---
name: asset-semantic-extractor
description: Sinh TOML semantic index cho ảnh/video raw để các skill phía sau map vào kịch bản. Ưu tiên đọc từ asset-index SQLite vector DB (mỗi file gọi Gemini đúng 1 lần trong toàn bộ project), chỉ fallback về probe + vision pass tươi khi không có index.
---

# Asset Semantic Extractor

## Quy tắc đầu ra (BẮT BUỘC)

- Mọi nội dung do AI/LLM sinh ra (`summary`, `description`, `visual_style`, `subjects`, `actions`, `environment`, `privacy_notes`, `quality_notes`...) **bắt buộc viết bằng tiếng Việt CÓ DẤU**.
- Cấm asciify (vd KHÔNG được viết "cong truong" thay cho "công trường" trong description).
- `tags`, `mood`, `semantic_tags`, `recommended_uses`, `avoid_uses` giữ ASCII lowercase kebab-case (vd: `vat-va`, `chan-thuc`, `b-roll-cong-truong`).
- Tên trường (`summary`, `mood`, `start`, `end`...), CLI flag, file path, JSON/TOML key, model id (Gemini, OpenAI) giữ nguyên tiếng Anh — không dịch.

## Quy tắc môi trường script

Trước khi chạy bất kỳ script nào của skill này, đọc file `.env` ở repo-root trước. File này nằm cạnh `jobs/`, `skills/`, và `env.example`. Chỉ kiểm tra các key cần thiết có tồn tại không; tuyệt đối không in giá trị secret ra log, terminal, TOML artifact, hay phản hồi. Chỉ dùng `--env-file` không phải repo-root khi user yêu cầu rõ ràng.

## Mục tiêu

Tạo semantic index dùng đi dùng lại được cho ảnh/video raw. Skill này không quyết định asset nào đi vào video cuối; nó chỉ mô tả mỗi asset chứa gì.

Dùng skill này khi user cung cấp folder hoặc file ảnh/video raw và cần chuẩn bị cho `semantic-asset-mapper`.

## Đầu vào

- Một hoặc nhiều file/folder ảnh/video.
- VDS hoặc creative plan tùy chọn (dùng trong chế độ vector-search để pre-filter pool asset).

## Đầu ra

Ghi hoặc trả về TOML. Đường dẫn mặc định:

```text
source/asset_semantics.toml
```

Khi đã có video job tồn tại, ghi vào:

```text
jobs/<job_id>/source/asset_semantics.toml
```

Hợp đồng TOML (`[[assets]]` + `[[asset_scenes]]`) không thay đổi nên `semantic-asset-mapper` và `shot-coverage-planner` vẫn tiêu thụ nguyên trạng.

## Đường ưu tiên: export từ asset-index DB

Repo có sẵn watcher (`tools/asset_index`) liên tục phân tích bất kỳ file mới nào thả vào `raw_assets/` hoặc `jobs/*/input/raw_assets/` bằng Gemini và lưu vào `.asset_index/index.db`. Luôn ưu tiên đọc DB này hơn là chạy lại Gemini.

### A. Folder export (mặc định cho mọi job)

```bash
python -m tools.asset_index.exporter raw_assets/ \
  --output source/asset_semantics.toml
```

Job-scoped:

```bash
python -m tools.asset_index.exporter jobs/<job_id>/input/raw_assets/ \
  --output jobs/<job_id>/source/asset_semantics.toml
```

Mặc định, file nào chưa có trong DB sẽ được auto-index ngay tại chỗ qua `tools.asset_index.router` (1 lần gọi Gemini, sau đó lưu lại). Để bỏ qua auto-index, truyền `--no-auto-index` và các file thiếu sẽ được báo qua warning `NOT_INDEXED`.

### B. Vector search theo creative plan (pool lớn)

Khi `raw_assets/` có hàng chục/hàng trăm file nhưng chỉ một số ít liên quan đến video mới, dùng vector search để rút gọn pool:

```bash
python -m tools.asset_index.exporter \
  --from-creative-plan jobs/<job_id>/source/creative_plan.toml \
  --output jobs/<job_id>/source/asset_semantics.toml \
  --top-per-intent 5 \
  --source-root raw_assets   # hoặc 'jobs', hoặc 'jobs/<job_id>/input/raw_assets'
```

Lệnh này embed mỗi `scene_intent` (narrative_role + visual_intent + spoken_text + mood + asset_requirements), chạy KNN trên index, dedupe, và ghi subset asset khớp ra TOML. Kết hợp với `--media video` hoặc `--media image` để giới hạn theo loại media.

### Quality gate (vẫn bắt buộc)

Exporter copy nguyên cái có trong DB. Nếu thấy row nào Gemini sinh description trống hoặc trùng nhau, force re-analyze chỉ file đó:

```bash
.venv/bin/python -m tools.asset_index.router /absolute/path/to/file.mp4 --force
```

rồi chạy lại exporter.

## Fallback: probe + Gemini Vision pass tươi

Dùng khi watcher asset-index chưa cài (chưa có `.asset_index/index.db`), user opt-out tường minh, hoặc đang xử lý file ngoài workspace. Hai script dưới đây sinh cùng hợp đồng TOML từ đầu.

### Env key bắt buộc

`GEMINI_API_KEY` phải tồn tại và khác rỗng trong `.env`. Nếu thiếu hoặc rỗng:

1. DỪNG. Không bịa scene description, không fallback sang text bulk theo asset, và không tái sử dụng cùng một description cho nhiều scene của 1 asset.
2. Báo user: `GEMINI_API_KEY` bắt buộc cho asset semantic vision analysis.
3. Yêu cầu user thêm vào `.env` (dòng stub `GEMINI_API_KEY=` đã có sẵn trong `env.example`).
4. Chỉ tiếp tục sau khi user xác nhận đã set key.

### Bước 1 — probe scaffold

```bash
python skills/asset_semantic_extractor/scripts/probe_assets.py source/input \
  --output source/asset_semantics.toml \
  --sample-frames 3 \
  --scene-window-seconds 8
```

Job-scoped:

```bash
python skills/asset_semantic_extractor/scripts/probe_assets.py jobs/<job_id>/input/raw_assets \
  --output jobs/<job_id>/source/asset_semantics.toml \
  --sample-dir jobs/<job_id>/source/asset_samples \
  --sample-frames 3 \
  --scene-window-seconds 8
```

### Bước 2 — Gemini Vision pass

```bash
python skills/asset_semantic_extractor/scripts/analyze_with_gemini.py \
  --input source/asset_semantics.toml \
  --output source/asset_semantics.toml \
  --sample-dir source/asset_samples \
  --env-file .env \
  --strict
```

Script abort khi `GEMINI_API_KEY` thiếu, không có sample frame cho asset, mọi model Gemini cấu hình đều fail, hoặc `--strict` được set mà quality gate phát hiện description trùng / còn `TODO:` / tag không kebab-case. Luôn rerun script (thay vì sửa TOML bằng tay) khi raw asset thay đổi.

## Hợp đồng TOML (cả 2 đường đều sinh ra cái này)

```toml
[[assets]]
id = "AST_001"
file_path = "raw_assets/videos/clip01.mp4"
type = "video"
duration_seconds = 18.4
summary = "..."
visual_style = "handheld, ánh sáng tự nhiên, tông ấm, depth of field nông"
mood = ["binh-yen", "than-mat"]
tags = ["nha", "buoi-sang", "thuong-nhat"]
privacy_notes = []
quality_notes = []

[[asset_scenes]]
id = "AST_001_SC_01"
start = 0.0
end = 5.8
description = "..."
subjects = ["..."]
actions = ["..."]
environment = "..."
shot_type = "medium shot"
camera_motion = "slow handheld drift"
composition = "subject centered"
colors = ["trắng ấm", "xanh lá nhạt"]
mood = ["yen-tinh", "tu-tin"]
semantic_tags = ["thuong-nhat", "before-state"]
recommended_uses = ["intro", "reflective-beat"]
avoid_uses = ["high-energy-transition"]
sample_frames = [...]
```

Với ảnh, set `duration_seconds = 0.0` và tạo 1 scene từ `0.0` đến `0.0`.

## Quy tắc chất lượng

- Scene timestamp là số thực (giây).
- Description phải mô tả thị giác và sự thật trước, diễn giải sau.
- Giữ semantic tags ổn định và lowercase.
- Đánh dấu identifier cá nhân thay vì copy chúng vào output dùng lại.
- Không có 2 scene trong cùng 1 asset chia sẻ `description` giống hệt.
- Mọi `semantic_tags` đều lowercase, không khoảng trắng (dùng `-` hoặc `_`).
- `privacy_notes` và `quality_notes` được điền khi liên quan (khuôn mặt, biển số, audio leak, đoạn rung / cháy sáng).

Nếu các quy tắc trên fail trong TOML đã export, force-reindex file vi phạm bằng `tools.asset_index.router --force` rồi chạy lại exporter.
