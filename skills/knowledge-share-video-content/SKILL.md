---
name: knowledge-share-video-content
description: Viết hoặc cập nhật video_content.md cho video chia sẻ kiến thức/giáo dục đời sống, với voiceover kể chuyện, câu mở đầu kéo người xem vào vai chính, luận điểm có câu hỏi phụ, và gợi ý visual AI không chữ.
---

# Knowledge Share Video Content

Use this skill when the user asks to write, rewrite, deepen, or structure `video_content.md` for a short knowledge-sharing video, especially Vietnamese educational explainers about economics, personal finance, consumer behavior, work, income, markets, or everyday systems.

This skill is for content writing only. If the task also creates a video job, use `$video-job-manager`. If the task also produces a production plan or scene intents in TOML, use `$video-creative-planner` only after the voiceover script has been explicitly approved, unless the user clearly opts out of approval.

## Voiceover Approval Gate (BẮT BUỘC)

Khi nội dung này sẽ đi vào pipeline tạo video, agent phải dừng sau bước viết voiceover:

- Ghi script hoàn chỉnh vào `jobs/<job_id>/source/narration.txt` và mục `## Voiceover hoàn chỉnh` trong `video_content.md`.
- Gửi nguyên văn voiceover script cho user duyệt.
- Không chạy TTS/voice, không tạo ảnh AI, không tạo scene JSON, không tạo subtitle cues, không instantiate template, và không render still/final trước khi user xác nhận rõ ràng.
- Nếu user yêu cầu chỉnh, chỉ sửa script rồi hỏi duyệt lại.
- Sau khi user duyệt, ghi `jobs/<job_id>/source/voiceover_approval.toml` để các skill phía sau biết script đã được chốt.

Ngoại lệ duy nhất: user nói rõ muốn bỏ qua bước duyệt script hoặc cho phép tự động tiếp tục.

## Output Location

- If the user names a job, write or update `jobs/<job_id>/source/video_content.md`.
- If a new video job already exists in context, use that job's `source/video_content.md`.
- If there is no job and the user only asks for content, return the markdown content directly unless they explicitly ask to create a file.

## Markdown Structure

Use this structure unless the user gives a stricter format:

```markdown
# <Tiêu đề>

## Mục tiêu video

## Câu mở đầu

## Voiceover hoàn chỉnh

## Câu hỏi phụ cần trả lời

## Cấu trúc triển khai

## Scene gợi ý

| # | Vai trò | Nội dung nói | Visual 3D isometric gợi ý | Quy tắc ảnh |
|---|---|---|---|---|

## Ghi chú style
```

Keep the markdown easy to hand off into voice generation, image generation, and Remotion planning. Avoid bloated explanations inside the file.

## Opening Rules

The opening must do five jobs:

1. Pull the viewer into the main role with a familiar personal situation.
2. Create an unresolved question.
3. Feel private and directly related to the viewer's life.
4. Avoid judging or blaming the viewer.
5. Name the lived experience first, then explain the mechanism later.

Vary the opening pattern across videos. Do not repeatedly begin with the same phrase. Useful patterns:

- `Hãy tưởng tượng bạn...`
- `Nếu điều này xảy ra với bạn...`
- `Có một lý do khiến nhiều người...`
- `Giả sử bạn...`
- `Có một sự thật...`
- `Có một chiêu kinh điển...`
- `Nếu chẳng may...`
- `Nếu bạn đang có...`
- `Bạn tưởng..., nhưng thật ra...`

Prefer natural story language:

- Strong: `Nếu bạn đang tính mua xe và chỉ nhìn vào giá bán, có thể bạn mới thấy một nửa câu chuyện. Vậy thì nửa còn lại là gì?`
- Weak: `Nửa còn lại nằm ở những khoản nào?`

The stronger line sounds like a person telling a story, not a document listing categories.

## Voiceover Rules

Write in Vietnamese with natural spoken rhythm. Use short sentences and clean transitions. The voiceover should be concise, but not shallow.

## Diction And Intensity

When the script needs a sharp, direct argument, use words with stronger emotional and social force instead of neutral phrasing. This is **tăng sắc thái biểu đạt** / **tăng cường độ ngôn ngữ**: choose diction that carries pressure, conflict, cost, or consequence.

Examples:

- Prefer `cạnh tranh khốc liệt hơn` over `cạnh tranh mạnh hơn`.
- Prefer `nặng nề và khó khăn hơn` over `nặng hơn` or `khó hơn`.
- Prefer `lời trách móc` over `lời trách` when the sentence is explicitly about blame.
- Prefer `bị đội lên` over `tăng lên` when describing social standards or costs becoming burdensome.

Do not overdo it on every sentence. Use high-intensity diction at argumentative pivots, hooks, objections, and takeaways; keep supporting explanation clear and spoken.

Avoid textbook phrases when they sound stiff:

- Avoid: `Lạm phát nguy hiểm vì nó không lấy tiền bằng một cú lớn.`
- Better: `Lạm phát thường không bước vào ví bạn rồi lấy đi một cục tiền. Nó chỉ làm từng món quanh bạn đắt hơn một chút.`

For every main claim, answer at least one supporting question so the argument feels solid:

- What exactly does the title mean?
- Why does this happen?
- What mechanism connects cause and effect?
- Is it always the viewer's fault? If not, say so clearly.
- What should the viewer look at, compare, or remember?

Default narrative flow:

1. Familiar situation.
2. Tension or question.
3. Mechanism.
4. Everyday examples.
5. No-blame clarification.
6. Memorable takeaway.

For economics and personal finance topics, explain the mechanism before giving advice. Avoid turning the video into moral judgment such as `do bạn tiêu hoang`, unless the point is explicitly about a behavior and still framed without contempt.

## Scene And Image Rules

Scene suggestions should help image/video generation, but must not bake text into the generated image.

For the current knowledge-sharing visual style:

- Generated image asset: `1:1` transparent PNG.
- Final video canvas: `9:16`.
- Image style: `3D isometric, bo tròn mềm mại`.
- No title, no labels, no numbers, no Vietnamese text, no Latin characters, no watermark inside the image.
- Titles, captions, slide labels, and numbers are added later by the layout/render step, not by image generation.

When describing visuals, use objects and relationships instead of text:

- Use: `một chiếc ví, các món đồ sinh hoạt xung quanh, mũi tên giá tăng không có chữ`
- Avoid: `bảng ghi "lạm phát", nhãn giá có số, hóa đơn có chữ`

Every row in the scene table should include the visual rule reminder:

`1:1 transparent PNG, không chữ, không số, không nhãn, không logo`

## Quality Checklist

Before finalizing `video_content.md`, check:

- The first sentence makes the viewer feel involved.
- The opening creates a real question, not just a topic announcement.
- The voiceover answers the main question and at least 3 supporting questions.
- The explanation has a mechanism, not just examples.
- The language sounds spoken, not academic.
- No line blames the viewer when the issue is systemic or partly external.
- The scene table does not request text, labels, or numbers inside images.
- Style notes say `1:1 transparent PNG` for generated assets and `9:16` for the final canvas.

## Creative Plan Handoff

If this content is later converted into `creative_plan.toml`, preserve these image generation rules:

```toml
[image_generation_rules]
style = "3D isometric, bo tròn mềm mại"
asset_aspect_ratio = "1:1"
final_canvas_aspect_ratio = "9:16"
output_format = "png"
transparent_background = true
no_text_in_images = true
prompt_negative = "không chữ, không số, không nhãn, không bảng text, không watermark, không ký tự tiếng Việt, không ký tự Latin, không logo, không nền trắng đặc, không khung, không tiêu đề"
```
