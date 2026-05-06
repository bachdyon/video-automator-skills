---
name: subtitle_punch_tag_shortform
description: Short-form subtitle với dòng normal + PUNCH_TAG đồng bộ word-level, chunk ~7–8 từ, chọn punch bằng phán đoán ngữ nghĩa, không bỏ sót/không trùng từ, không xuống dòng giữa Whisper word, punch 2 lớp z-index (shadow dưới / fill sạch trên). Dùng khi build Remotion caption kiểu TikTok/Reels vùng ngực, hoặc khi cần spec chuẩn hóa punch_segments + renderer.
---

# subtitle_punch_tag_shortform

Skill mô tả **end-to-end** pipeline phụ đề short-form: **một dòng (hoặc nhiều dòng) “normal”** + **một cụm PUNCH** (to, đậm), đồng bộ **100%** với transcript có timestamp từng từ (`word_id`), không mất chữ, không nhân đôi từ giữa normal và punch.

Tham chiếu triển khai mẫu: job `jobs/2026-05-06_004_style-caption-chest-zone/remotion/src/composition.tsx`.

---

## 1. Mục tiêu UX

| Thành phần | Vai trò |
|------------|---------|
| **Normal** | Phần lời “nền” trong chunk, màu trắng (hoặc theo VDS), hiện dần theo `word.start` |
| **PUNCH** | Cụm nhấn mạnh semantic, một **màu solid** / chunk (ví dụ luân phiên vàng `#ffe800` và đỏ `#ff1600`), uppercase, shadow **chỉ** ở lớp dưới (xem §6) |
| **Layout** | Normal trên, punch dưới (stack dọc); punch có thể có decor orbit (optional) |

---

## 2. Nguồn sự thật: transcript word-level

- Mỗi từ có **`id` ổn định** (ví dụ `W_0001` …), **`word`**, **`start`**, **`end`**.
- File thường: `jobs/<job_id>/source/transcript_word_level.toml` hoặc array `words` đã merge vào `template-props.json`.
- **Quy tắc vàng**: mọi logic hiển thị **phải** map qua `word_id` — không render punch/normal bằng cách “đoán” chuỗi từ overlay text cố định vì sẽ lệch timing và lệch tokenization so với Whisper.

---

## 3. Phân chunk theo cửa sổ ~7–8 từ (không đụng đến cách chọn punch)

- Chia toàn bộ câu chuyện thành các chunk liên tiếp, mỗi chunk chứa danh sách **`word_ids`** (thường 7 từ, chunk cuối có thể ngắn hơn).
- **Thời đoạn chunk** (để biết đang ở chunk nào):  
  `tStart = min(words[i].start)`, `tEnd = max(words[i].end)` với `i ∈ word_ids`.
- **Không được** để hai chunk chia cùng một `word_id` hoặc bỏ sót id — phải kiểm tra tập hợp:

```text
⋃ chunks[k].word_ids  ==  toàn bộ W_0001 … W_NNNN
∀ k≠l: chunks[k].word_ids ∩ chunks[l].word_ids = ∅
```

- Gợi ý artifact: `source/punch_segments.json` (hoặc field trong props Remotion) với `chunks[]`.

---

## 4. Chọn PUNCH_TAG — phán đoán ngữ nghĩa (AI), không rule cứng

### 4.1 Nguyên tắc

- Trong **mỗi chunk**, chọn **một cụm liên tục** các `punch_word_ids` là **“đắt giá”** nhất về mặt nội dung (khái niệm trọng tâm, cú twist, lời kêu gọi, từ khóa nhớ).
- **Không** hard-code danh sách từ khóa (“luôn punch chữ X”) vì sẽ sai ngữ cảnh.
- **Không** nhất thiết mỗi chunk đều có punch — có thể `punch_word_ids: []` nếu không có cụm đủ mạnh (renderer phải xử lý).

### 4.2 Ràng buộc với normal

- **`punch_word_ids` ⊆ `word_ids`** của cùng chunk.
- **Normal** = các từ trong chunk **trừ** punch: hiển thị theo thứ tự đọc nhưng **không** lặp lại bất kỳ từ nào đã nằm trong punch.

### 4.3 Ghi lại lý do (khuyến nghị)

- Mỗi chunk có `punch_rationale` ngắn để review sau và để template job khác học pattern.

---

## 5. Không bỏ sót text — đồng bộ hiển thị

### 5.1 Normal line

- Lấy `normalWordIds = word_ids \ punch_word_ids` (giữ thứ tự trong chunk).
- Với thời điểm `t`, chỉ append các từ có `word.start <= t` (typewriter theo từ đầu tiên → hết chunk).

### 5.2 Punch line

- Timing punch: từ `punchFirstStart = min(punch words start)` đến `punchLastEnd = max(punch words end)` (+ optional hold ngắn ~0.1–0.2s).
- Hiển thị **chỉ** các token punch (theo `punch_word_ids`), uppercase trên UI.

### 5.3 Kiểm chứng nhanh trước render

- Script: đếm `len(words)` trong transcript vs số `word_id` xuất hiện đúng một lần trong `⋃ chunks.word_ids`.
- Visual: không được có khoảng “câm” dài bất thường giữa hai từ liền kề trong cùng chunk trừ khi silence thật trong audio.

---

## 6. Xuống dòng: không đứt giữa Whisper **word**

Whisper mỗi phần tử `words[]` là một **token** — coi là **khối không tách** khi wrap.

### 6.1 Layout

- **Mỗi word** (một string từ Whisper): bọc trong container `whiteSpace: nowrap`, `flexShrink: 0`, `display: inline-flex`.
- Hàng chứa nhiều word: `display: flex`, `flexWrap: wrap`, `justifyContent: center`, `gap` giữa các word — **xuống dòng chỉ xảy ra giữa các word**, không giữa các grapheme trong cùng word.

### 6.2 Grapheme (tiếng Việt)

- Để render từng chữ (layer punch, stroke từng glyph nếu có): dùng `Intl.Segmenter("vi", { granularity: "grapheme" })`; fallback `Array.from(str)`.
- Grapheme chỉ **bên trong** một Whisper word; không dùng grapheme để quyết định chỗ wrap giữa các khoảng trắng nội bộ word (word thường không có space).

### 6.3 Cỡ chữ punch co giãn

- `maxGraphemesInWord = max over all punch words of segmentGraphemes(word).length`
- `fontSize ≈ clamp(min, max, innerMaxWidth / (maxGraphemesInWord * emFactor))`  
  (tham số mẫu: `innerMaxWidth ≈ 800`, `emFactor ≈ 0.62` cho Be Vietnam 900 uppercase.)
- Đảm bảo **một word dài nhất** vẫn vừa một hàng ở `maxWidth` layout (≈ 880px container trừ padding).

### 6.4 Tách dòng **hiển thị** theo dấu câu / chữ hoa (optional nhưng khuyến nghị)

- **Khớp** skill `subtitle-screen-splitter` / script `skills/subtitle-screen-splitter/scripts/split_subtitle_screens.py`:
  - Sau khi thêm từ kết thúc bằng dấu `, . ! ? ; : …` → flush nhóm hiện tại (dấu nằm ở cuối nhóm trước khi tách).
  - Trước từ **viết hoa** bắt đầu câu mới khi nhóm đã có chữ → flush trước (thứ tự giống Python: capital flush **trước** khi push token; punctuation flush **sau** khi push).
- Áp dụng **sau** khi đã có danh sách string từ Whisper cho normal hoặc punch — để được nhiều “dòng visual” trong cùng chunk mà không phá timing từng từ.

---

## 7. Punch hai lớp text — khớp 100%, z-index cố định

Mục tiêu: lớp trên **không** có shadow (fill sạch); lớp dưới **chỉ** mang `textShadow` (ví dụ đen, nhiều blur).

### 7.1 Cấu trúc mỗi grapheme (khuyến nghị)

Một wrapper `position: relative; display: inline-block`:

1. **Lớp dưới** (`z-index: 0`):  
   - `position: absolute; left: 0; top: 0`  
   - Cùng **một object style typography** với lớp trên: `color`, `fontFamily`, `fontWeight`, `fontSize`, `lineHeight`, `textTransform`  
   - `textShadow: <stack đen>`  
   - `aria-hidden`, `pointerEvents: none`, `userSelect: none`

2. **Lớp trên** (`z-index: 1`):  
   - `position: relative`  
   - Cùng typography object  
   - `textShadow: none`

### 7.2 Vì sao “khớp chính xác”

- Hai span chứa **cùng một ký tự/grapheme**; lớp trên quyết định **box** của wrapper; lớp dưới căn `left/top` theo góc trên-trái của cùng box.
- **Không** dùng `text-stroke` trừ khi chủ đích — user có thể yêu cầu bỏ viền glyph; shadow chỉ ở lớp dưới.

### 7.3 Màu solid punch theo chunk (ví dụ)

- Hai màu cố định pool; chọn theo hash `chunk.id` (ổn định theo chunk): ví dụ chẵn → vàng, lẻ → đỏ.

---

## 8. Props Remotion (tối thiểu)

- `words: { id, word, start, end }[]`
- `punch_segments: { version, chunk_word_size?, chunks: [{ id, word_ids, punch_word_ids, punch_rationale? }] }`

Merge payload vào `remotion/public/template-props.json` hoặc import JSON độc lập.

---

## 9. Checklist QA trước khi ship

1. **Partition**: mỗi `word_id` đúng một chunk; không thiếu id.
2. **Punch ⊆ chunk**; **không overlap** từ giữa normal và punch.
3. **Wrap**: zoom video 400% — không có dòng punch cắt nửa một Whisper word.
4. **Hai lớp**: tắt lớp trên trong devtools — lớp dưới vẫn đọc được và shadow không “trôi” lệch typo.
5. **Dấu câu**: sau khi split display lines, không gộp nhầm hai câu vào một dòng khi đã flush theo `subtitle-screen-splitter`.

---

## 10. Skill liên quan

- **`subtitle-screen-splitter`**: tách dòng hiển thị theo dấu câu / chữ hoa (`skills/subtitle-screen-splitter/`).
- **`word_timestamps_extractor`**: tạo transcript word-level (`skills/word_timestamps_extractor/`).
- **`video_renderer` / template Remotion**: ghép composition (`skills/video_renderer/`).

---
