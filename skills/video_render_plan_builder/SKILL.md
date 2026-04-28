---
name: video-render-plan-builder
description: Chuyển VDS, creative plan, transcript, và semantic asset mapping thành TOML edit decision list chi tiết với crop, timing, text overlay, subtitle, motion, audio, transition, và chỉ thị render.
---

# Video Render Plan Builder

## Quy tắc đầu ra (BẮT BUỘC)

- Mọi nội dung do AI/LLM sinh ra (`reason`, ghi chú, nội dung text overlay nếu agent tự sinh) **bắt buộc viết bằng tiếng Việt CÓ DẤU**.
- Cấm asciify (vd KHÔNG được viết "song chau" thay cho "sống chậm" trong overlay text).
- Tên trường (`fps`, `crop_anchor`, `transition_in`...), enum (`cover`, `contain`, `cut`, `soft_cut`, `fade_slide`...), CLI flag, file path, model id giữ nguyên tiếng Anh — không dịch.
- Style ID (`MAIN_TITLE`, `SUBTITLES`, `PUNCH_TAG`...) giữ nguyên SCREAMING_SNAKE_CASE.

## Quy tắc môi trường script

Trước khi chạy bất kỳ script nào của skill này, đọc file `.env` ở repo-root trước. File này nằm cạnh `jobs/`, `skills/`, và `env.example`. Chỉ kiểm tra các key cần thiết có tồn tại không; tuyệt đối không in giá trị secret. Chỉ dùng `--env-file` không phải repo-root khi user yêu cầu rõ ràng.

## Mục tiêu

Tạo edit decision list cụ thể được renderer sử dụng. Skill này trả lời câu hỏi mỗi asset đã map sẽ được biên tập như thế nào.

Dùng skill này sau khi `semantic-asset-mapper` đã chọn xong asset.

## Đầu vào

- VDS từ `video-design-spec-builder`.
- `source/creative_plan.toml`.
- `source/transcript_word_level.toml`.
- `source/semantic_mapping.toml`.
- Asset music/SFX tùy chọn.

## Đầu ra

Ghi hoặc trả về TOML. Đường dẫn mặc định:

```text
source/render_plan.toml
```

Khi đã có video job, ghi vào:

```text
jobs/<job_id>/source/render_plan.toml
```

## Quy trình

1. Set render setting toàn cục: fps, resolution, aspect ratio, duration.
2. Chuyển mỗi semantic mapping thành render clip.
3. Quyết định crop/fit, source trim, playback speed, camera motion, transition, và color treatment.
4. Thêm subtitle từ transcript word-level với style/timing theo VDS.
5. Thêm overlay text từ creative plan.
6. Thêm audio plan: voice, BGM, ambience, ducking, fades.
7. Validate liên tục, file thiếu, clip overlap, và timing text khó đọc.

## Quy tắc text layer handoff (BẮT BUỘC)

- Skill này chỉ tạo **data contract** cho text (`[[overlays]]`, `[[subtitles]]`, style refs, timing).
- Mọi text trong render plan phải được thiết kế để Remotion tiêu thụ trực tiếp; không phát sinh hướng dẫn burn text bằng FFmpeg/ImageMagick/Python.
- Không thêm field/hint dạng `ffmpeg_drawtext`, `imagemagick_caption`, `python_pillow_text` hoặc bất kỳ cơ chế tương đương.
- Nếu job yêu cầu “không subtitle”, đặt `subtitles = []` hoặc skip tạo subtitle ở render plan; vẫn giữ text overlay nếu creative yêu cầu, và renderer Remotion chịu trách nhiệm vẽ.

## Hợp đồng TOML

```toml
[render]
fps = 30
width = 1080
height = 1920
duration_seconds = 45.0
background = "black"

[style]
vds_path = "source/vds.md"
subtitle_style = "SUBTITLES"
title_style = "MAIN_TITLE"
color_treatment = "match_vds"

[audio.voice]
file_path = "source/voice.wav"
start = 0.0
gain_db = 0.0

[audio.music]
file_path = ""
start = 0.0
gain_db = -18.0
duck_under_voice = true

[[clips]]
id = "CLIP_001"
mapping_id = "MAP_001"
file_path = "source/input/clip01.mp4"
type = "video"
timeline_start = 0.0
timeline_end = 5.2
source_start = 0.0
source_end = 5.8
fit = "cover"
crop_anchor = "center"
speed = 1.0
motion = "slow_push_in"
transition_in = "cut"
transition_out = "soft_cut"
color = "match_vds"

[[subtitles]]
start = 0.12
end = 2.4
text = "..."
words_ref = ["W_0001", "W_0002"]
style = "SUBTITLES"

[[overlays]]
id = "TXT_01"
start = 0.0
end = 3.2
text = "..."
style = "MAIN_TITLE"
position = "upper_third"
animation_in = "fade_slide"
animation_out = "fade"
```

## Quy tắc chất lượng

- Render clip không được overlap trừ khi có chủ đích layer compositing.
- Text phải có đủ thời gian on-screen để đọc.
- Dùng transcript word-level cho subtitle, không dùng timing xấp xỉ từ script.
- Giữ implementation đặc thù renderer ra khỏi file này trừ khi user yêu cầu chỉ một renderer.

## Script tiện ích

Dùng script đi kèm để generate EDL deterministic và validate:

```bash
python skills/video_render_plan_builder/scripts/build_render_plan.py build \
  --mapping source/semantic_mapping.toml \
  --transcript source/transcript_word_level.toml \
  --creative-plan source/creative_plan.toml \
  --voice-audio source/voice.wav \
  --output source/render_plan.toml

python skills/video_render_plan_builder/scripts/build_render_plan.py validate \
  --render-plan source/render_plan.toml
```

Cho job-scoped run, truyền path job tường minh:

```bash
python skills/video_render_plan_builder/scripts/build_render_plan.py build \
  --mapping jobs/<job_id>/source/semantic_mapping.toml \
  --transcript jobs/<job_id>/source/transcript_word_level.toml \
  --creative-plan jobs/<job_id>/source/creative_plan.toml \
  --voice-audio jobs/<job_id>/source/voice.wav \
  --vds-path jobs/<job_id>/source/vds.md \
  --output jobs/<job_id>/source/render_plan.toml
```

Script chuyển semantic mapping thành clip, sinh subtitle từ câu transcript, mang overlay text từ creative plan, thêm phần voice/music, và validate timing clip/subtitle.
