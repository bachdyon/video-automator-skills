---
name: shot-coverage-planner
description: Giải quyết coverage shortage và lặp asset trong baseline semantic mapping bằng cách ra quyết định kiểu editor sáng tạo (cutaway B-roll, hold + Ken Burns, slowdown). Thiết kế cho AI agent (không gọi LLM nội bộ) — agent đọc context, áp khung quyết định, và viết decisions JSON để 1 helper script nhỏ apply lên TOML.
---

# Shot Coverage Planner

## Quy tắc đầu ra (BẮT BUỘC)

- Mọi nội dung do agent/LLM sinh ra (`rationale`, `reason`, ghi chú biên tập) **bắt buộc viết bằng tiếng Việt CÓ DẤU**.
- Cấm asciify (vd KHÔNG được viết "doi lap" thay cho "đối lập").
- Tên trường (`scene_id`, `strategy`, `sub_clips`...), enum value (`cutaway_subdivision`, `slowdown`, `hold_and_kenburns`, `keep`), CLI flag, file path giữ nguyên tiếng Anh — không dịch.
- Mood/tags trong `asset_scenes` giữ kebab-case ASCII (vd `binh-yen`, `tinh-lang`).

## Quy tắc môi trường script

Trước khi chạy bất kỳ script nào, đọc file `.env` ở repo-root trước. File này nằm cạnh `jobs/`, `skills/`, và `env.example`. Chỉ kiểm tra các key cần thiết có tồn tại không; tuyệt đối không in giá trị secret. Skill này KHÔNG gọi LLM API — mọi quyết định sáng tạo do agent tự đưa ra.

## Mục tiêu

Lấy baseline `semantic_mapping.toml` (1-1 scene → asset, do `semantic-asset-mapper` chạy với `--no-cutaway` sinh ra) cùng toàn bộ creative context, và sinh ra `semantic_mapping.toml` **đã chỉnh sửa** sao cho mỗi scene hoặc:

- Có source coverage ≥ timeline duration (không loop, không freeze), HOẶC
- Được chia có chủ đích thành nhiều sub-clip (cutaway / B-roll layering), HOẶC
- Dùng phương án thay thế đã được duyệt có chủ ý (slowdown, hold-end-frame trên still + Ken Burns) khi chia nhỏ sẽ phá narrative.

**Quan trọng:** agent — không phải Python heuristic — chọn strategy và asset. Các script đi kèm chỉ làm I/O cơ học và validate.

## Khi nào gọi

Sau `semantic-asset-mapper` (chạy với `--no-cutaway`) và trước `video-render-plan-builder`. Luôn gọi nếu bất kỳ baseline mapping nào có source duration ngắn hơn timeline duration của nó, hoặc bất kỳ asset_id nào được dùng quá `--repetition-threshold` lần trên timeline (mặc định 3).

## Đầu vào (cần để agent suy luận)

| Path | Cho agent biết điều gì |
| --- | --- |
| `source/creative_plan.toml` | LÝ DO mỗi scene tồn tại: `narrative_role`, `visual_intent`, `mood`, `preferred_shot_types`, `asset_requirements` |
| `source/transcript_word_level.toml` | KHI NÀO mỗi scene phát: timestamp câu/từ để neo biên cutaway vào nhịp lời nói tự nhiên |
| `source/asset_semantics.toml` | CÓ footage gì: mỗi row `asset_scenes[]` có `description, subjects, actions, environment, shot_type, camera_motion, composition, colors, mood, semantic_tags, recommended_uses, avoid_uses, start, end`. Khi asset-index DB đã populate, regenerate TOML này bằng `python -m tools.asset_index.exporter raw_assets/ --output jobs/<job_id>/source/asset_semantics.toml` để phản ánh pool mới nhất. |
| `.asset_index/index.db` (tùy chọn) | Pool ứng viên B-roll SÂU HƠN so với `asset_semantics.toml`. Dùng `tools.asset_index.search.search_assets("intent text", k=10, source_root="raw_assets")` để mò các phương án cutaway mà baseline mapper bỏ sót. |
| `source/semantic_mapping.toml` (baseline) | Mapping 1-1 HIỆN TẠI với `start, end, source_start, source_end, fit_score, fit_labels, fallback` |
| `source/vds.md` (tùy chọn) | Ràng buộc PHONG CÁCH: pacing, tone, do/don't |

## Quy trình

### Bước 1 — Phát hiện gap (cơ học)

Chạy helper để sinh `coverage_context.json` tóm tắt mọi scene cần quyết định sáng tạo:

```bash
python skills/shot_coverage_planner/scripts/detect_gaps.py \
  --mapping jobs/<job_id>/source/semantic_mapping.toml \
  --asset-semantics jobs/<job_id>/source/asset_semantics.toml \
  --creative-plan jobs/<job_id>/source/creative_plan.toml \
  --transcript jobs/<job_id>/source/transcript_word_level.toml \
  --output jobs/<job_id>/source/coverage_context.json \
  --shortage-threshold 0.5 \
  --repetition-threshold 3
```

JSON có 2 key cấp đầu:

- `gaps[]` — mỗi entry là 1 scene có baseline mapping với `timeline_duration - source_duration > shortage_threshold` HOẶC asset_id chính bị dùng quá nhiều. Mỗi entry có scene intent, metadata clip primary hiện có, và các candidate `asset_scenes[]` đã rank kèm `available_duration`, `times_used_in_baseline`, `recommended_uses`, `mood`, `colors`, `shot_type`, v.v.
- `usage_stats` — đếm lặp theo `asset_id` và `asset_scene_id` từ baseline.

Script không tự chọn gì cả; nó chỉ đưa cho agent 1 gói context được biên tập sẵn để agent khỏi phải đọc lại từng file.

### Bước 2 — Agent quyết định (SÁNG TẠO — đây là điểm cốt lõi của skill)

Mở `coverage_context.json` và, với mỗi gap, áp **Khung Quyết Định** bên dưới. Ghi `coverage_decisions.json` cạnh file context với cấu trúc sau:

```json
{
  "decisions": [
    {
      "scene_id": "SC_02",
      "strategy": "cutaway_subdivision",
      "rationale": "Clip primary 4s nhưng scene 12s. Voice-over đối lập giữa văn phòng và đồng ruộng; cắt giữa selfie talking-head và B-roll phụ nữ cuốc đất sẽ làm rõ sự đối lập bằng hình ảnh.",
      "sub_clips": [
        {
          "asset_scene_id": "AST_006_SC_01",
          "role": "primary",
          "timeline_start": 9.58,
          "timeline_end": 13.60,
          "source_start": 0.0,
          "source_end": 4.02,
          "reason": "Cho narrator on-camera để khẩu hình khớp câu mở đầu."
        },
        {
          "asset_scene_id": "AST_005_SC_02",
          "role": "cutaway_1",
          "timeline_start": 13.60,
          "timeline_end": 17.60,
          "source_start": 8.0,
          "source_end": 12.0,
          "reason": "Cắt sang bàn chân trần đung đưa cuốc — phản đề trực quan với hình ảnh dân văn phòng."
        }
      ]
    },
    {
      "scene_id": "SC_07",
      "strategy": "slowdown",
      "rationale": "Single-take cảnh khoảng lặng cảm xúc; cắt ngang sẽ phá khoảnh khắc. Hạ xuống 0.85x cho không gian thở.",
      "sub_clips": [
        {
          "asset_scene_id": "AST_001_SC_02",
          "role": "primary",
          "timeline_start": 72.02,
          "timeline_end": 79.90,
          "source_start": 0.0,
          "source_end": 6.7,
          "playback_rate": 0.85,
          "reason": "Giữ khoảnh khắc; hơi chậm lại kéo 6.7s source thành 7.88s timeline."
        }
      ]
    }
  ]
}
```

`strategy` BẮT BUỘC là 1 trong: `cutaway_subdivision`, `slowdown`, `hold_and_kenburns`, `keep` (giữ nguyên — gap chấp nhận được).

### Bước 3 — Apply patch (cơ học)

```bash
python skills/shot_coverage_planner/scripts/apply_patch.py \
  --mapping jobs/<job_id>/source/semantic_mapping.toml \
  --decisions jobs/<job_id>/source/coverage_decisions.json \
  --asset-semantics jobs/<job_id>/source/asset_semantics.toml \
  --output jobs/<job_id>/source/semantic_mapping.toml
```

Script:

1. Thay mọi row `[[mappings]]` có `scene_id` xuất hiện trong decision bằng các sub-clip của agent (đánh số lại, điền `coverage_strategy`, `playback_rate`, `subdivision_role`, `subdivision_index`, `subdivision_total`, `gap_seconds`).
2. Validate: timeline liên tục (không gap, không overlap), clamp `source_end <= asset_scene.end + asset.duration_seconds`, file tồn tại, sub-clip min duration ≥ 0.6s.
3. Từ chối ghi nếu decision tham chiếu `asset_scene_id` không tồn tại hoặc đẩy `source_end` vượt thời lượng asset thật.

Nếu script báo lỗi, sửa `coverage_decisions.json` rồi chạy lại — không bao giờ sửa TOML bằng tay.

## Khung Quyết Định (lõi sáng tạo)

### A. Chọn strategy

Áp **rule khớp đầu tiên** cho mỗi scene, dựa vào kích thước gap và intent narrative.

| Gap (`timeline_duration - source_duration`) | Strategy mặc định | Điều kiện override |
| --- | --- | --- |
| ≤ 0.5s | `keep` (margin chấp nhận được; clip phát ngắn, render plan có thể giữ frame cuối ≤ 0.5s không artifact) | Không override |
| 0.5–1.5s | `slowdown` ở 0.85–1.0x | Dùng `cutaway_subdivision` nếu scene năng lượng cao / cắt nhanh (nhiều subject, pacing tag `fast`/`punchy`) |
| 1.5–4s | `cutaway_subdivision` (primary + 1 cutaway) | Chỉ dùng `slowdown` (≥0.7x) khi footage primary là single-take cảm xúc/thân mật (`mood` tag có `intimate`, `binh-yen`, `tinh-lang`) và cắt sẽ phá khoảnh khắc. Dùng `hold_and_kenburns` nếu asset là ảnh tĩnh. |
| > 4s | `cutaway_subdivision` (primary + 2–4 cutaway) | Hầu như không bao giờ override; cảnh giữ rất dài cảm thấy "gãy" trên social/short-form |

Cận dưới slowdown: **0.65x** (chậm hơn nữa nhìn giả). Nếu phép tính đòi < 0.65x, chuyển sang `cutaway_subdivision`.

### B. Chọn asset cho `cutaway_subdivision`

Với mỗi cutaway, scoring mọi candidate `asset_scene` so với scene intent cha và chọn cái tốt nhất, áp các quy tắc sáng tạo theo thứ tự:

1. **Liên quan ngữ nghĩa trước.** Cutaway phải đẩy/hỗ trợ/đối lập với lời nói trong scene. Loại ứng viên có `description` không liên quan tới `visual_intent` của scene.
2. **Đa dạng hơn lặp lại.** Không bao giờ đặt 2 sub-clip liên tiếp từ cùng `asset_id`. Nếu `asset_id` của candidate trùng sub-clip trước đó, hạ ưu tiên trừ khi không có phương án nào khác qua được rule 1.
3. **Tiếp nối HOẶC đối lập — chọn có chủ đích.** Hoặc match `mood`/`colors`/`shot_type` với primary (tiếp nối) cho cảm giác mượt, hoặc cố ý lệch (cắt đối lập) khi script đối lập 2 ý. Viết rõ phương án chọn trong `reason`.
4. **Tôn trọng `recommended_uses` / `avoid_uses`.** Ưu tiên asset có `recommended_uses` chứa `b_roll`, `cutaway`, `insert`. Bỏ qua asset nào có `avoid_uses` chặn vai trò đang gán (vd tránh asset `high-energy-cut` cho scene thiền định).
5. **Coi chừng over-use.** Nếu `usage_stats.asset_id_counts[X] >= repetition_threshold`, chỉ chọn lại X khi không thể thay thế.
6. **Giữ sub-clip min ≥ 0.8s.** Mục tiêu 1.5–3s/cutaway cho short-form; không bao giờ dưới 0.8s (nhìn như flicker trên TikTok).

Với mỗi sub-clip, set `source_start` / `source_end` về đoạn của asset_scene khớp nhất với intent của cutaway (có thể lấy 2s ở giữa của 1 asset_scene 8s — chọn moment biểu cảm nhất).

### C. Chọn tham số cho `slowdown`

- `playback_rate = source_duration / timeline_duration`, clamp về `[0.65, 1.0]`.
- Source span: full asset_scene window (`source_start = scene.start`, `source_end = scene.end`).

### D. Chọn tham số cho `hold_and_kenburns` (chỉ ảnh tĩnh)

- `source_start = 0.0`, `source_end = 0.0` (hoặc bất kỳ placeholder dài 0 — render plan xử lý ảnh tĩnh).
- Ghi trong `reason` hướng Ken Burns (`zoom_in_center`, `pan_left_to_right`, v.v.) để render plan đọc được.

### E. Sửa lặp

Nếu một baseline mapping qua được kiểm tra shortage nhưng nằm trong `usage_stats.over_used_asset_ids`, chỉ thay bằng asset khác khi có candidate khớp tốt hơn rõ rệt; không thì giữ nguyên nhưng log `reason: "dùng nhiều nhưng không thể thay cho intent này"`.

## Hợp đồng Decision JSON bắt buộc

Mỗi decision row PHẢI có:

- `scene_id` (khớp 1 `[[mappings]].scene_id` hiện có từ baseline)
- `strategy` ∈ `{cutaway_subdivision, slowdown, hold_and_kenburns, keep}`
- `rationale` (1–3 câu giải thích lựa chọn biên tập — người review cut sẽ đọc cái này)
- `sub_clips[]` (≥ 1 entry; `keep` có thể chỉ 1 entry mirror baseline)

Mỗi sub-clip PHẢI có:

- `asset_scene_id` (phải tồn tại trong `asset_semantics.toml`)
- `role` ∈ `{primary, cutaway_1, cutaway_2, …}` cho `cutaway_subdivision`; `primary` cho các strategy khác
- `timeline_start`, `timeline_end` (liên tục, không gap, không overlap trong scene cha)
- `source_start`, `source_end` (trong `[start, end]` của asset_scene và clamp theo asset duration)
- `playback_rate` (chỉ cho `slowdown`; mặc định 1.0 chỗ khác)
- `reason` (1 câu — clip này làm gì cho người xem)

## Ví dụ Patch

### Cutaway subdivision (gap 4s tách thành 3 sub-clip)

Baseline:

```toml
[[mappings]]
scene_id = "SC_05"
asset_scene_id = "AST_005_SC_11"
start = 37.68
end = 51.34
source_start = 0.0
source_end = 4.55
```

Sau quyết định của agent (3 sub-clip, asset đa dạng, contrast cut):

```toml
[[mappings]]
scene_id = "SC_05"
subdivision_role = "primary"
subdivision_index = 1
subdivision_total = 3
asset_scene_id = "AST_005_SC_11"
start = 37.68
end = 42.23
source_start = 0.0
source_end = 4.55
coverage_strategy = "cutaway_subdivision"

[[mappings]]
scene_id = "SC_05"
subdivision_role = "cutaway_1"
subdivision_index = 2
subdivision_total = 3
asset_scene_id = "AST_006_SC_01"
start = 42.23
end = 46.79
source_start = 1.5
source_end = 6.0
coverage_strategy = "cutaway_subdivision"
```

### Slowdown (gap 1.2s, khoảnh khắc thân mật giữ nguyên)

```toml
[[mappings]]
scene_id = "SC_07"
subdivision_role = "primary"
subdivision_index = 1
subdivision_total = 1
asset_scene_id = "AST_001_SC_02"
start = 72.02
end = 79.90
source_start = 0.0
source_end = 6.70
coverage_strategy = "slowdown"
playback_rate = 0.8503
```

## Quy tắc chất lượng

- Tổng timeline span được thay PHẢI bằng đúng span scene gốc (không drift).
- Sub-clip trong cùng 1 scene phải liên tục không lỗ (timeline_end của clip N == timeline_start của clip N+1).
- Không bao giờ tham chiếu file thiếu hoặc `asset_scene_id` không tồn tại.
- `playback_rate` ∈ [0.65, 1.5]; ngoài range này renderer sẽ warn.
- `reason` và `rationale` phải giải thích ý đồ biên tập bằng ngôn ngữ tự nhiên; KHÔNG paste mô tả asset.
- Agent BẮT BUỘC xử lý mọi gap mà `detect_gaps.py` báo. Dùng `strategy: "keep"` để tường minh chấp nhận gap thay vì bỏ qua âm thầm.
