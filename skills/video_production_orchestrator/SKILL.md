---
name: video-production-orchestrator
description: Điều phối toàn bộ pipeline video short-form dài hạn từ video mẫu, yêu cầu sáng tạo mới, raw asset, sinh voice, transcribe, semantic mapping, render plan, đến render cuối cùng.
---

# Video Production Orchestrator

## Quy tắc đầu ra (BẮT BUỘC)

- Mọi nội dung do AI/LLM sinh ra (status note, lý do skip, cảnh báo gửi user) **bắt buộc viết bằng tiếng Việt CÓ DẤU**.
- Cấm asciify (vd KHÔNG được viết "hoan thanh" thay cho "hoàn thành").
- Tên skill (kebab-case), tên stage trong code (`video-job-manager`, `asset-semantic-extractor`...), CLI flag, file path, JSON/TOML key giữ nguyên tiếng Anh — không dịch.

## Mục tiêu

Chạy đầy đủ pipeline sinh video từ:

- video mẫu
- yêu cầu user mới
- raw asset

đến:

- video short-form đã render cuối cùng

Skill này điều phối các skill khác. Không nên thay thế công việc chuyên môn của chúng.

## Quy tắc môi trường script

Trước khi chạy bất kỳ script nào ở bất kỳ stage nào, đọc file `.env` ở repo-root trước. File này nằm cạnh `jobs/`, `skills/`, và `env.example`. Truyền `.env` qua `--env-file` khi script hỗ trợ. Chỉ kiểm tra các key cần thiết có tồn tại không; tuyệt đối không in giá trị secret. Chỉ dùng `--env-file` không phải repo-root khi user yêu cầu rõ ràng.

## Khi nào dùng

Dùng skill này khi user yêu cầu tạo, regenerate, preview, hoặc sản xuất 1 video mới hoàn chỉnh dùng phong cách tham khảo và source material mới.

## Thứ tự pipeline

0. **Job Workspace**
   - Dùng `video-job-manager`.
   - Input: yêu cầu user, reference media, raw asset.
   - Output: `jobs/<job_id>/job.toml` và các folder job chuẩn.
   - Mọi path sau này nên nằm trong job directory này.

1. **Reference Style**
   - Dùng `video-design-spec-builder`.
   - Input: video mẫu/tham khảo.
   - Output: VDS dùng đi dùng lại tại `jobs/<job_id>/source/vds.md`.

2. **Creative Plan**
   - Dùng `video-creative-planner`.
   - Input: brief user + VDS.
   - Output: `jobs/<job_id>/source/creative_plan.toml`.

3. **Voice**
   - Dùng `ausynclab-voice`.
   - Input: kịch bản voiceover từ creative plan.
   - Output: `jobs/<job_id>/source/voice.wav` hoặc `.mp3`, kèm `jobs/<job_id>/source/voice_selection.toml`.

4. **Transcript Timing**
   - Dùng `$word-timestamps-extractor`.
   - Input: audio voice đã sinh.
   - Output: `jobs/<job_id>/source/transcript_word_level.toml`.

5. **AI Image Synthesis (CÓ ĐIỀU KIỆN)**
   - Dùng `fal-image-generator`. Chỉ chạy khi:
     - User chỉ định raw assets sẽ là AI-generated, hoặc
     - `creative_plan.toml` có `scene_intents[].asset_requirements` chứa `ai_generated` / `ai_image`, hoặc
     - `jobs/<job_id>/input/raw_assets/` rỗng và user không định cung cấp footage.
   - Input: `creative_plan.toml` + (tùy chọn) ảnh tham chiếu nhân vật ở `jobs/<job_id>/input/reference/`.
   - Output: PNG vào `jobs/<job_id>/input/raw_assets/images/ai_generated/` + log `jobs/<job_id>/source/ai_image_generation.toml`.
   - Yêu cầu `FAL_API_KEY` trong `.env`. Skip stage này nếu user đã có raw assets thật.

6. **Asset Index**
   - Dùng `asset-semantic-extractor`.
   - Input: ảnh/video raw (kể cả ảnh AI vừa sinh ở stage 5 nếu có).
   - Output: `jobs/<job_id>/source/asset_semantics.toml`.
   - Khi watcher asset-index (`tools/asset_index`) đang chạy, ưu tiên `python -m tools.asset_index.exporter <raw-folder> --output ...` để mỗi file chỉ gọi Gemini tối đa 1 lần trên toàn project. Watcher đã pre-analyze mọi thứ thả vào `raw_assets/` hoặc `jobs/*/input/raw_assets/`; exporter chỉ đọc `.asset_index/index.db` và viết cùng hợp đồng TOML. File chưa index sẽ được auto-index theo nhu cầu. Chỉ skip toàn bộ stage này khi user opt-out khỏi index.

7. **Semantic Mapping (baseline 1-1)**
   - Dùng `semantic-asset-mapper`.
   - Input: creative plan + transcript + asset semantics + VDS.
   - Output: `jobs/<job_id>/source/semantic_mapping.toml` (1 asset best-fit cho mỗi scene; row có warning `SOURCE_SHORTER_THAN_TIMELINE` được giữ chủ ý cho bước sau).
   - Với pool `raw_assets/` lớn, ưu tiên `--use-vector-index` để mapper truy vấn trực tiếp `.asset_index/index.db` cho từng scene_intent thay vì scan TOML pre-build to tướng.

8. **Shot Coverage Decisions (sáng tạo)**
   - Dùng `shot-coverage-planner`.
   - Input: baseline `semantic_mapping.toml` + asset semantics + creative plan + transcript.
   - Quy trình: chạy `detect_gaps.py` để sinh `coverage_context.json`, agent (assistant này) viết `coverage_decisions.json` áp khung cutaway / slowdown / hold, rồi `apply_patch.py` viết lại `semantic_mapping.toml` với các sub-clip.
   - Output: `jobs/<job_id>/source/semantic_mapping.toml` đã chỉnh sửa kèm `coverage_context.json` và `coverage_decisions.json` để truy vết.

9. **Render Plan**
   - Dùng `video-render-plan-builder`.
   - Input: VDS + creative plan + transcript + semantic mapping đã chỉnh sửa.
   - Output: `jobs/<job_id>/source/render_plan.toml`.

10. **Render**
   - Dùng `video-renderer`, skill này phải verify/install và load skill chính thức `$remotion-best-practices` trước khi tạo hoặc cập nhật Remotion project job-scoped.
   - Input: render plan + media file.
   - Output: Remotion project job-scoped tại `jobs/<job_id>/remotion/`, sau đó `jobs/<job_id>/output/final_video.mp4`.

## Hợp đồng artifact

Layout workspace mặc định:

```text
jobs/<job_id>/
  job.toml
  input/
    reference/
    raw_assets/
    audio/
    brand/
  source/
    vds.md
    creative_plan.toml
    voice_selection.toml
    voice.wav
    transcript_word_level.toml
    asset_semantics.toml
    ai_image_generation.toml
    semantic_mapping.toml
    coverage_context.json
    coverage_decisions.json
    render_plan.toml
  remotion/
    package.json
    remotion.config.ts
    tsconfig.json
    src/
      Root.tsx
      Composition.tsx
      render-plan.generated.ts
      assets.generated.ts
      components/
      styles/
    public/
      assets/
  output/
    preview.mp4
    final_video.mp4
    thumbnail.jpg
    render_report.toml
  logs/
    render.log
    validation.log
```

## Checkpoint

Trước khi chuyển sang bước tiếp theo, verify:

- Job tồn tại và `job.toml` track yêu cầu và input.
- VDS tồn tại và chứa hướng dẫn style/timing.
- Creative plan có script và scene intents.
- Audio voice tồn tại và playable.
- Transcript phủ toàn bộ thời lượng voice.
- Asset semantics phủ mọi asset đã cung cấp.
- Semantic mapping liên tục và mỗi row có `start`, `end`, `file_path`, và `reason`.
- Mọi scene bị flag trong `coverage_context.json` đều có decision tương ứng trong `coverage_decisions.json` (không skip âm thầm).
- Render plan chỉ tham chiếu file tồn tại.
- Render cuối tồn tại và có audio.

## Quy tắc khôi phục

- Nếu request, reference, hay raw input được đăng ký/thay đổi, dùng `video-job-manager` để đánh dấu các stage downstream bị stale.
- Nếu voice thay đổi, rerun transcript, mapping, render plan, và render.
- Nếu asset thay đổi trong `raw_assets/` hoặc `jobs/*/input/raw_assets/`, watcher asset-index tự cập nhật `.asset_index/index.db`; rerun `asset-semantic-extractor` (giờ chỉ re-export từ DB), rồi mapping, render plan, và render.
- Nếu VDS thay đổi, rerun creative plan, mapping, render plan, và render.
- Nếu chỉ crop/transition/text styling thay đổi, rerun render plan và render.
- Nếu chỉ code renderer thay đổi, rerun render.

## Quy tắc chất lượng

- Giữ output mỗi stage trên disk để pipeline có thể debug.
- Không che lỗi bằng cách skip stage.
- Ưu tiên cập nhật artifact stale nhỏ nhất hơn là regenerate mọi thứ.
- Chỉ hỏi user về credentials thiếu, source media thiếu, hoặc quyết định sáng tạo không thể infer an toàn.
- Đánh dấu mỗi stage hoàn thành trong `job.toml` qua `video-job-manager`.
