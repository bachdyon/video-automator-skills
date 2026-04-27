---
name: video-job-manager
description: Tạo và quản lý các video job sản xuất biệt lập, gồm metadata yêu cầu, asset đầu vào, artifact theo stage, status, theo dõi stale, và path chuẩn cho pipeline video.
---

# Video Job Manager

## Quy tắc đầu ra (BẮT BUỘC)

- Mọi nội dung do AI/LLM sinh ra (`brief`, `title`, lý do stale, ghi chú trong todo) **bắt buộc viết bằng tiếng Việt CÓ DẤU**.
- Cấm asciify (vd KHÔNG được viết "stale do voice thay doi").
- `job.id`, tên stage (`creative_plan`, `render`...), enum status (`pending`, `running`, `done`, `failed`, `stale`), key TOML, CLI flag, file path giữ nguyên tiếng Anh — không dịch.

## Mục tiêu

Quản lý mọi thứ thuộc về 1 yêu cầu sinh video như 1 job có thể tái lập.

Skill này không tự tạo nội dung video. Nó tạo và bảo trì job workspace để các skill video khác đọc và ghi vào.

## Quy tắc môi trường script

Trước khi chạy bất kỳ script nào của skill này, đọc file `.env` ở repo-root trước. File này nằm cạnh `jobs/`, `skills/`, và `env.example`. Chỉ kiểm tra các key cần thiết có tồn tại không; tuyệt đối không in giá trị secret. Chỉ dùng `--env-file` không phải repo-root khi user yêu cầu rõ ràng.

## Khi nào dùng

Dùng skill này khi user bắt đầu yêu cầu video mới, thêm reference/input asset, hỏi status job, rerun một phần pipeline, hoặc cần tìm artifact của một yêu cầu video cụ thể.

## Layout mặc định

```text
.env
env.example
jobs/
  <job_id>/
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
      semantic_mapping.toml
      render_plan.toml
    remotion/
      package.json
      remotion.config.ts
      tsconfig.json
      src/
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
      pipeline_status.toml
      todo.toml
```

## Trách nhiệm

1. Tạo directory duy nhất `jobs/<job_id>`.
2. Lưu yêu cầu gốc trong `job.toml`.
3. Đăng ký reference video, raw asset, audio, file brand.
4. Track path artifact chuẩn cho mọi stage.
5. Đánh dấu stage pipeline là `pending`, `running`, `done`, `failed`, hoặc `stale`.
6. Đánh dấu stage downstream stale khi input thay đổi.
7. Cung cấp path để các skill khác sử dụng.
8. Bảo trì `logs/todo.toml` như danh sách todo luôn cập nhật cho job.

## Thứ tự stage

```text
request
reference_style
creative_plan
voice
transcript
asset_semantics
semantic_mapping
render_plan
render
```

## Script tiện ích

Dùng script đi kèm để quản lý state job deterministic:

```bash
python skills/video_job_manager/scripts/manage_job.py create \
  --title "Morning routine ad" \
  --brief "Tạo TikTok 45s phong cách reflective..." \
  --platform tiktok \
  --language vi \
  --target-duration 45

python skills/video_job_manager/scripts/manage_job.py register-input \
  --job jobs/2026-04-25_001_morning-routine-ad \
  --kind raw_assets \
  --path /path/to/clip.mp4 \
  --copy

python skills/video_job_manager/scripts/manage_job.py mark-stage \
  --job jobs/2026-04-25_001_morning-routine-ad \
  --stage creative_plan \
  --status done \
  --output source/creative_plan.toml

python skills/video_job_manager/scripts/manage_job.py stale-from \
  --job jobs/2026-04-25_001_morning-routine-ad \
  --stage voice \
  --reason "audio voice đã thay đổi"

python skills/video_job_manager/scripts/manage_job.py status \
  --job jobs/2026-04-25_001_morning-routine-ad

python skills/video_job_manager/scripts/manage_job.py todo \
  --job jobs/2026-04-25_001_morning-routine-ad
```

## Hợp đồng TOML

`job.toml` phải có:

```toml
[job]
id = "2026-04-25_001_morning-routine-ad"
title = "Morning routine ad"
status = "created"
created_at = "2026-04-25T10:00:00+07:00"
updated_at = "2026-04-25T10:00:00+07:00"

[request]
brief = "..."
platform = "tiktok"
language = "vi"
target_duration_seconds = 45

[paths]
job_dir = "jobs/2026-04-25_001_morning-routine-ad"
input_dir = "input"
reference_dir = "input/reference"
raw_assets_dir = "input/raw_assets"
source_dir = "source"
remotion_dir = "remotion"
output_dir = "output"

[[inputs]]
kind = "raw_assets"
path = "input/raw_assets/clip01.mp4"
original_path = "/path/to/clip01.mp4"

[[stages]]
name = "creative_plan"
status = "done"
output = "source/creative_plan.toml"
updated_at = "..."
reason = ""
```

`logs/todo.toml` phải đồng bộ với state stage:

```toml
[[todos]]
id = "TODO_003"
stage = "creative_plan"
title = "Tạo script, scene intents và overlay plan"
status = "done"
output = "source/creative_plan.toml"
updated_at = "..."
reason = ""
```

Mapping todo status:

```text
pending -> todo
running -> doing
done -> done
failed -> blocked
stale -> todo
```

## Quy tắc chất lượng

- Không bao giờ dùng `source/` chung cho 1 video job thật khi đã có job directory.
- Không ghi đè artifact của job khác.
- Đăng ký input thay đổi trước khi rerun stage pipeline.
- Khi input của 1 stage thay đổi, đánh dấu các stage downstream stale thay vì giả vờ chúng vẫn hợp lệ.
- Giữ mọi path trong `job.toml` tương đối so với job directory khi có thể.
- Mọi lệnh thay đổi state phải refresh `logs/todo.toml`.
