---
name: video-renderer
description: Render video short-form cuối cùng từ TOML render plan, voice audio, source asset, subtitle, overlay, và quy tắc style VDS bằng renderer của project (Remotion hoặc FFmpeg).
---

# Video Renderer

## Quy tắc đầu ra (BẮT BUỘC)

- Mọi nội dung do AI/LLM sinh ra (warning message, render report comment) **bắt buộc viết bằng tiếng Việt CÓ DẤU**.
- Cấm asciify (vd KHÔNG được viết "asset thieu" thay cho "asset thiếu").
- Tên file (TS/TSX), tên component (`OverlayText`, `MediaLayer`...), tên hằng (`SAFE_BOX_WIDTH`, `MAX_CHARS_PER_PAGE`...), enum (`fade_slide`, `cover`, `cut`...), CLI flag, file path, model id, code TypeScript/JavaScript giữ nguyên tiếng Anh — không dịch.

## Mục tiêu

Thực thi render cuối cùng từ `source/render_plan.toml` và sinh ra file video. Cho production job-scoped, tạo hoặc cập nhật Remotion project riêng dưới `jobs/<job_id>/remotion/` và render job đó độc lập.

Dùng skill này khi user yêu cầu render, export, preview, hoặc sản xuất video cuối cùng sau khi đã có render plan.

Khi skill này tạo, cập nhật, validate, preview, hoặc render Remotion project, BẮT BUỘC load và tham chiếu skill chính thức `$remotion-best-practices` trước khi đưa ra quyết định triển khai đặc thù Remotion.

Trước khi bắt đầu công việc Remotion, verify skill chính thức tồn tại bằng `scripts/ensure-remotion-skill.sh` từ repo root. Nếu thiếu, cài bằng `npx skills add remotion-dev/skills --yes` sau khi xin phép user về quyền truy cập network.

## Quy tắc môi trường script

Trước khi chạy bất kỳ renderer hoặc script nào của skill này, đọc file `.env` ở repo-root trước. File này nằm cạnh `jobs/`, `skills/`, và `env.example`. Chỉ kiểm tra các key cần thiết có tồn tại không; tuyệt đối không in giá trị secret. Chỉ dùng `--env-file` không phải repo-root khi user yêu cầu rõ ràng.

## Quy tắc render text ownership (BẮT BUỘC)

- Mọi chữ xuất hiện trên frame video (headline, lower-third, brand tag, date stamp, subtitle, reaction text, source credit) **phải do Remotion render** bằng component/layer trong `jobs/<job_id>/remotion/src/`.
- **Cấm tuyệt đối** render chữ bằng FFmpeg filters (`drawtext`, `subtitles`, `ass`), ImageMagick (`magick`, `convert`), hoặc script Python để burn text trực tiếp lên pixel.
- FFmpeg chỉ được dùng cho encode/mux/concat/trim media sau khi phần hình chữ đã được Remotion xuất ra.
- Nếu phát hiện pipeline hiện tại đang dùng FFmpeg/ImageMagick/Python để tạo chữ, phải dừng và migrate text layer sang Remotion trước khi render final.

## Đầu vào

- `source/render_plan.toml`.
- Audio voice từ `ausynclab-voice`.
- Source asset ảnh/video.
- VDS tùy chọn cho tham chiếu style.
- Renderer của project. Cho video job, mặc định Remotion project job-scoped.

## Đầu ra

File cuối cùng mặc định:

```text
output/final_video.mp4
```

Khi đã có video job, ghi vào:

```text
jobs/<job_id>/output/final_video.mp4
```

Cũng ghi 1 render report khi cần:

```text
output/render_report.toml
```

Cho job-scoped run:

```text
jobs/<job_id>/output/render_report.toml
```

## Quy tắc bàn giao trong Codex (BẮT BUỘC)

Khi render/preview/final video đã hoàn thành và file video tồn tại, phản hồi cuối cho user **bắt buộc nhúng video ngay trong Codex** bằng Markdown media tag với **đường dẫn tuyệt đối**:

```markdown
![Final video](/absolute/path/to/jobs/<job_id>/output/final_video.mp4)
```

Không chỉ trả text path. Cũng nên kèm một link file fallback:

```markdown
[final_video.mp4](/absolute/path/to/jobs/<job_id>/output/final_video.mp4)
```

Trước khi gửi phản hồi cuối, verify file được nhúng tồn tại và size > 0. Nếu output bàn giao là biến thể khác như `final_video_under25mb_h264.mp4`, nhúng đúng file bàn giao đó. Nếu vì lý do kỹ thuật không thể nhúng media trong Codex, phải nói rõ lý do và vẫn cung cấp link file tuyệt đối.

## Layout Remotion job-scoped

Mỗi video job sở hữu Remotion project riêng:

```text
jobs/<job_id>/
  source/
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
        Scene.tsx
        MediaLayer.tsx
        SubtitleLayer.tsx
        OverlayText.tsx
        AudioLayer.tsx
        .....
      styles/
        tokens.generated.ts
        global.css
        ....
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

Giữ `.env` ở repo-root, ngoài mọi job folder, cạnh `jobs/` và `skills/`. Không tạo `jobs/<job_id>/source/.env` trừ khi user yêu cầu rõ override theo job.

## Quy trình

1. Đọc `.env` ở repo-root khi cần credentials hoặc renderer settings.
2. Validate mọi file được tham chiếu trong `render_plan.toml` đều tồn tại.
3. Validate timeline duration, clip overlap, audio thiếu, font thiếu, và format không hỗ trợ.
4. Cho job-scoped run, verify/install `$remotion-best-practices`, load nó, rồi tạo hoặc cập nhật `jobs/<job_id>/remotion/` từ render plan.
5. Copy hoặc symlink media cần thiết vào `jobs/<job_id>/remotion/public/assets/`, rồi generate `render-plan.generated.ts` và `assets.generated.ts`.
6. Render preview hoặc final export từ trong Remotion project của job.
7. Verify file output tồn tại, duration khác 0, và có audio.
8. Ghi `render_report.toml`, cập nhật `logs/render.log` khi cần, và báo warning.

## Hợp đồng Render Report

```toml
[render]
status = "success"
output_path = "output/final_video.mp4"
duration_seconds = 45.0
width = 1080
height = 1920
fps = 30
has_audio = true
renderer = "remotion"
remotion_project_path = "jobs/<job_id>/remotion"
composition_id = "MainVideo"

[[warnings]]
code = "LOW_RES_ASSET"
message = "Asset source/input/image01.jpg đã bị upscale."
file_path = "source/input/image01.jpg"
```

## Quy tắc text-safety (bắt buộc cho mọi Remotion project skill này scaffold)

Canvas dọc 1080×1920 chỉ có ~880px chiều rộng text an toàn sau padding 2 bên. Text overlay và subtitle **tuyệt đối không được overflow ngang**. Mọi component text Remotion do skill này sinh ra phải triển khai cả 4 phòng tuyến:

1. **Bounded box.** Container `maxWidth: 880` (≤82% width canvas), padding ngang 28px mỗi bên.
2. **Hard word-break.** `wordBreak: "break-word"` VÀ `overflowWrap: "anywhere"` trên container text; `whiteSpace: "pre-wrap"` (KHÔNG phải `"pre"`) trên span highlight inline để subtitle wrap được trong token nếu cần.
3. **Auto-shrink fontSize.** Cài helper `fitFontSize(baseFontSize, fontWeight, textLength, uppercase)` ước lượng char width theo font weight (`900 → 0.62em`, `800 → 0.58em`, `700 → 0.56em`, `400 → 0.5em`, `+8%` cho uppercase) và shrink fontSize theo `√(safeCapacity / textLength)` khi text vượt capacity 2 dòng ở base size. Hard floor: 40px.
4. **Subtitle page split.** Page do `@remotion/captions createTikTokStyleCaptions` sinh có thể đóng gói 6+ token. Sau khi nhận `result.pages`, post-process để tách bất kỳ page nào có chiều dài `tokens.text` ghép vượt `MAX_CHARS_PER_PAGE` (mặc định 26). Dùng `combineTokensWithinMilliseconds: 800–1000` thay vì giá trị cao hơn.

Snippet tham chiếu cho `OverlayText.tsx`:

```tsx
const SAFE_BOX_WIDTH = 880;

const CHAR_WIDTH_RATIO_BY_WEIGHT: Record<string, number> = {
  "900": 0.62, "800": 0.58, "700": 0.56, "600": 0.54, "400": 0.5,
};

const fitFontSize = (
  baseFontSize: number,
  fontWeight: number | string | undefined,
  textLength: number,
  uppercase: boolean,
) => {
  const ratio = CHAR_WIDTH_RATIO_BY_WEIGHT[String(fontWeight ?? 700)] ?? 0.55;
  const upperBoost = uppercase ? 1.08 : 1;
  const twoLineCap = Math.floor(SAFE_BOX_WIDTH / (baseFontSize * ratio * upperBoost)) * 2;
  if (textLength <= twoLineCap) return baseFontSize;
  return Math.max(40, Math.round(baseFontSize * Math.sqrt(twoLineCap / textLength)));
};

// Áp dụng trên text div:
//   style={{ ...preset, fontSize: fittedFontSize, maxWidth: SAFE_BOX_WIDTH,
//            wordBreak: "break-word", overflowWrap: "anywhere",
//            whiteSpace: "pre-wrap", hyphens: "manual" }}
```

Các quy tắc này bổ sung cho giới hạn `max_chars` phía planner trong `video-creative-planner` và validator trong `video-render-plan-builder`. Coi đây là defense-in-depth: planner ràng buộc, builder cảnh báo, renderer bảo đảm.

## News intro + video dưới overlay (layout bắt buộc khi scaffold template kiểu bản tin)

Khi VDS hoặc brief mô tả **intro tin tức + video gốc phía sau / lower graphic**, mọi implementation Remotion phải tuân:

1. **Intro chrome nằm tối thiểu nửa dưới frame.** Hình chữ nhật full width, `bottom: 0`, `height` ~45–50%: **chỉ một dải % nhỏ ở mép trên** gradient tiếp giáp video; **phần còn lại nền đặc** `rgba(..., 0.9)`. **Video credit** góc trên canvas (tách khỏi panel), lấy từ **`render_plan.toml` → `[intro_chrome]` `video_credit`** và truyền vào Remotion `defaultProps` (bundle không đọc TOML runtime — phải giữ hai nơi khớp chuỗi). Trending / ngày / headline **neo theo đỉnh** panel. Margin tối thiểu **~100px** so viền canvas cho credit và khối chữ trong panel. Typography: `z-index` cao hơn `OffthreadVideo` / panel.
2. **Video layer dưới overlay:** bọc `OffthreadVideo` trong `overflow: "hidden"` + `object-fit: cover` và bias khung **lên trên** để mặt nằm phía trên vùng graphic: dùng `objectPosition: "center 15–25%"` và/hoặc `transform: translateY(-4% đến -8%) scale(1.04–1.08)` tùy footage; tinh chỉnh theo preview một frame tại điểm cắt intro.
3. **Source credit / “VIDEO: …”:** kích thước **~một nửa** so với bar mặc định (vd font 18px thay 36px), **không** dùng pill nền đen — chỉ `text-shadow` để đọc được trên footage.
4. **Font file local (vd. UTM Bebas):** lưu bản quyền trong **`fonts/`** ở root repo (cùng cấp thư mục `jobs/`). Trước `remotion studio` / `remotion render`, job Remotion chạy **`npm run sync-fonts`** (gọi `scripts/sync-fonts.mjs`) để copy `.ttf` / `.otf` / `.woff2` sang `remotion/public/fonts/` — `staticFile()` chỉ đọc từ `public/`.

Chỉnh sửa trực tiếp tại `jobs/<job_id>/remotion/src/` (thường `composition.tsx` / layer intro) là đúng chỗ nhất; **không** cần chạy lại voice, transcript, hay semantic mapping — chỉ `npx remotion render` lại sau khi sửa layout.

## Quy tắc chất lượng

- Ưu tiên renderer hiện có của repo hơn là thêm stack mới.
- Cho video job, ưu tiên Remotion project riêng cho mỗi job hơn là dùng chung 1 renderer project.
- Không sửa semantic mapping khi đang render; sửa file upstream nếu mapping sai.
- Giữ render implementation deterministic và reproducible từ TOML plan.
- Nếu cần browser/dev server cho visual verification, khởi động và verify trang/preview đã render trước khi handoff cuối.
- Cho full video production, render từ `jobs/<job_id>/source/render_plan.toml` và đánh dấu stage `render` trong `job.toml`.
- Mọi component render text phải tuân theo phần **Quy tắc text-safety** ở trên. Render KHÔNG được coi là "hoàn thành" nếu overlay hoặc subtitle overflow ngang.
