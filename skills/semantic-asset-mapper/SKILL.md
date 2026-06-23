---
name: semantic-asset-mapper
description: Khớp transcript hoặc scene intents với asset ảnh/video đã được index ngữ nghĩa, sinh TOML timeline mapping với start, end, file_path, đoạn source được chọn và lý do.
---

# Semantic Asset Mapper

## Quy tắc đầu ra (BẮT BUỘC)

- Mọi nội dung do AI/LLM sinh ra (đặc biệt là trường `reason`, ghi chú, cảnh báo bằng văn xuôi) **bắt buộc viết bằng tiếng Việt CÓ DẤU**.
- Cấm asciify (vd KHÔNG được viết "lao dong" thay cho "lao động" trong reason).
- Tags, fit_labels, warning code, narrative_role giữ ASCII lowercase (vd: `semantic`, `mood`, `SOURCE_SHORTER_THAN_TIMELINE`).
- Tên trường, CLI flag, file path, JSON/TOML key giữ nguyên tiếng Anh — không dịch.

## Quy tắc môi trường script

Trước khi chạy bất kỳ script nào của skill này, đọc file `.env` ở repo-root trước. File này nằm cạnh `jobs/`, `skills/`, và `env.example`. Chỉ kiểm tra các key cần thiết có tồn tại không; tuyệt đối không in giá trị secret. Chỉ dùng `--env-file` không phải repo-root khi user yêu cầu rõ ràng.

## Mục tiêu

Khớp nội dung lời thoại và scene intent của video mới với asset phù hợp nhất. Skill này quyết định asset nào xuất hiện vào lúc nào và vì sao.

Dùng skill này sau khi đã có transcript/scene intents và asset semantic index.

## Đầu vào

- `source/creative_plan.toml` từ `video-creative-planner`.
- `source/transcript_word_level.toml` từ `$word-timestamps-extractor`.
- `source/asset_semantics.toml` từ `asset-semantic-extractor` **HOẶC** asset-index SQLite vector DB tại `.asset_index/index.db` (ưu tiên khi watcher đang chạy).
- VDS tùy chọn cho ràng buộc về pacing và vai trò scene.

Khi watcher asset-index đang hoạt động, chạy `asset-semantic-extractor` trước để nó sinh `source/asset_semantics.toml` từ DB mà không cần gọi lại Gemini, hoặc dùng `--use-vector-index` (xem bên dưới) để skill này tự kéo subset cần thiết từ DB.

## Đầu ra

Ghi hoặc trả về TOML. Đường dẫn mặc định:

```text
source/semantic_mapping.toml
```

Khi đã có video job, ghi vào:

```text
jobs/<job_id>/source/semantic_mapping.toml
```

## Quy trình

1. Đọc scene intents, transcript sentences, và asset semantics.
2. Căn biên scene vào timing transcript khi có thể.
3. Chọn asset dựa trên độ khớp ngữ nghĩa, mood, shot type, tính liên tục thị giác và ràng buộc chất lượng.
4. Ưu tiên match sub-scene của video nguồn hơn là dùng cả clip.
5. Chỉ dùng ảnh tĩnh khi phù hợp pacing hoặc không có video nào mạnh hơn.
6. Sinh **baseline** mapping 1-1: mỗi `scene_intent` được match với 1 `asset_scene` tốt nhất, kèm `start, end, source_start, source_end, fit_score, fit_labels`. KHÔNG chia nhỏ để bù coverage; đó là việc của `shot-coverage-planner`.
7. Đánh dấu mọi row có timeline duration vượt source duration với `warnings += ["SOURCE_SHORTER_THAN_TIMELINE"]` để stage tiếp theo biết chỗ nào cần xử lý.
8. Không quy định crop cuối, transitions, animation text, hay tham số render; để cho `video-render-plan-builder`.

## Bàn giao coverage shortage

Khi `timeline_duration - best_source_duration > 0.5s`, KHÔNG loop, freeze, hay auto-stitch cutaways tại đây. Emit row nguyên trạng với warning `SOURCE_SHORTER_THAN_TIMELINE` và để `shot-coverage-planner` đưa ra quyết định biên tập (cutaway / slowdown / hold + Ken Burns) bằng phán đoán sáng tạo của agent.

Cờ `--no-cutaway` của script là **mặc định** trong pipeline mới. Thuật toán cutaway heuristic legacy vẫn được giữ cho backward compatibility và có thể bật lại bằng `--legacy-cutaway`, nhưng không nên dùng trong production.

## Hợp đồng tối thiểu (BẮT BUỘC)

Danh sách lõi phải có đủ các trường này cho mỗi mapping:

```toml
[[mappings]]
start = 0.0
end = 5.2
file_path = "source/input/clip01.mp4"
reason = "Khớp với câu mở đầu về buổi sáng yên tĩnh."
```

## Hợp đồng mở rộng

Dùng các trường mở rộng khi đã có chi tiết source scene:

```toml
[[mappings]]
id = "MAP_001"
scene_id = "SC_01"
asset_id = "AST_001"
asset_scene_id = "AST_001_SC_01"
start = 0.0
end = 5.2
file_path = "source/input/clip01.mp4"
source_start = 0.0
source_end = 5.8
fit_score = 0.86
fit_labels = ["semantic", "mood", "pacing"]
reason = "Khớp với câu mở đầu về buổi sáng yên tĩnh."
fallback = false
warnings = []
```

## Quy tắc chất lượng

- Không bao giờ map một đoạn asset bị đánh dấu unusable trừ khi không còn lựa chọn; khi đó set `fallback = true`.
- Tránh lặp cùng visual quá nhiều trừ khi VDS yêu cầu lặp lại.
- Tôn trọng privacy notes trong asset semantics.
- Giữ timeline liên tục trừ khi có chỉ định im lặng/black screen có chủ đích.

## Script hỗ trợ

Dùng script đi kèm cho baseline mapping và validate:

```bash
python skills/semantic-asset-mapper/scripts/map_assets.py build \
  --creative-plan source/creative_plan.toml \
  --transcript source/transcript_word_level.toml \
  --asset-semantics source/asset_semantics.toml \
  --output source/semantic_mapping.toml

python skills/semantic-asset-mapper/scripts/map_assets.py validate \
  --mapping source/semantic_mapping.toml
```

Cho job-scoped run, truyền path job tường minh:

```bash
python skills/semantic-asset-mapper/scripts/map_assets.py build \
  --creative-plan jobs/<job_id>/source/creative_plan.toml \
  --transcript jobs/<job_id>/source/transcript_word_level.toml \
  --asset-semantics jobs/<job_id>/source/asset_semantics.toml \
  --output jobs/<job_id>/source/semantic_mapping.toml
```

Script chạy scoring token/tag deterministic, sinh các row mapping liên tục, và validate khoảng trống, overlap, range không hợp lệ, file thiếu. Dùng phán đoán LLM để cải thiện lựa chọn semantic và lý do sau khi đã có baseline.

### Chế độ vector-index (khuyến nghị khi raw_assets/ lớn)

Thay vì chuẩn bị `asset_semantics.toml` từ trước, để mapper vector-search asset-index DB cho mỗi scene intent rồi viết TOML rút gọn ngay tại chỗ:

```bash
python skills/semantic-asset-mapper/scripts/map_assets.py build \
  --creative-plan jobs/<job_id>/source/creative_plan.toml \
  --transcript jobs/<job_id>/source/transcript_word_level.toml \
  --asset-semantics jobs/<job_id>/source/asset_semantics.toml \
  --output jobs/<job_id>/source/semantic_mapping.toml \
  --use-vector-index \
  --top-per-intent 5 \
  --vector-source-root raw_assets   # hoặc 'jobs', hoặc 'jobs/<job_id>/input/raw_assets'
```

Lệnh này delegate sang `tools.asset_index.exporter.export_for_creative_plan`, hàm này embed mỗi scene_intent (narrative_role + visual_intent + spoken_text + mood + asset_requirements), chạy KNN trên `.asset_index/index.db`, dedupe, và ghi subset asset khớp vào `--asset-semantics` (ghi đè nếu đã tồn tại). Mapper sau đó đọc file đó như bình thường.

Các flag hữu ích:

- `--vector-media image|video` giới hạn theo loại media.
- `--vector-job-id <id>` giới hạn ở pool của 1 job.
- `--asset-index-db /path/to/index.db` trỏ tới DB ở vị trí khác.

Khi DB chưa được populate cho asset liên quan, ưu tiên chạy `asset-semantic-extractor` trước (nó auto-index file thiếu); chế độ vector của mapper **không** auto-index, chỉ đọc cái đã có.
