---
name: subtitle-punch-tag-shortform
description: Short-form subtitle normal + PUNCH đồng bộ word-level; chunk cố định bằng script; punch do coding agent gán bằng suy luận ngữ nghĩa (cấm heuristic chọn punch trong code). Punch 2 lớp z-index, ~7–8 từ/chunk. Dùng khi build Remotion TikTok/Reels hoặc chuẩn hóa punch_segments.
---

# subtitle-punch-tag-shortform

Skill mô tả pipeline phụ đề short-form: **normal** + **PUNCH** đồng bộ `word_id`, không mất token, không trùng từ giữa normal và punch.

Tham chiếu renderer: `jobs/2026-05-06_004_personal_brand_no_broll/remotion/src/composition.tsx`.

---

## Hợp đồng: agent tự động vs code

| Việc | Ai làm | Ghi chú |
|------|--------|---------|
| Đọc transcript word-level, chia `word_ids` theo cửa sổ | **Script** | Deterministic, không “hiểu” nội dung |
| Xuất chunk + token cho bước punch | **Script** | `--write-agent-input`, không chứa punch |
| Chọn `punch_word_ids`, viết `punch_rationale` | **Coding agent (LLM)** | Đọc từng chunk như lời nói / ngữ cảnh |
| Merge + kiểm tra subset, liên tiếp | **Script** | `--merge-punch` |

**User không bắt buộc sửa tay file** khi có agent: agent chạy script → đọc input → suy luận → ghi merge JSON → chạy lại script → render.

---

## Cấm tuyệt đối (punch)

Trong **Python / script / codebase**:

- Cấm heuristic chọn punch: danh sách từ khóa cố định, điểm số, regex ưu tiên, độ dài token, tần suất, “ưu tiên danh từ”, v.v.
- Cấm nhúng logic “nếu có chữ X thì punch” trong repo.
- Được phép: chia chunk, validate, merge JSON, xuất file tiêu thụ bởi agent.

Chọn punch **chỉ** được thực hiện qua **suy luận ngữ nghĩa của LLM** khi đọc (và nếu có thì nghe) lời trong chunk — tương đương “tư duy người nghe”, không phải rule máy.

---

## 1. Mục tiêu UX

| Thành phần | Vai trò |
|------------|---------|
| **Normal** | Lời nền trong chunk, hiện dần theo `word.start` |
| **PUNCH** | Cụm nhấn mạnh nội dung, màu solid/chunk, uppercase, shadow chỉ lớp dưới |
| **Layout** | Normal trên, punch dưới |

---

## 2. Nguồn sự thật: transcript word-level

- Mỗi từ: `id` (vd `W_0001`), `word`, `start`, `end`.
- File: `jobs/<job_id>/source/transcript_word_level.toml` hoặc `template-props.json` → `words[]`.
- **Quy tắc vàng**: mọi hiển thị map qua `word_id`, không overlay text tự bịa chuỗi.

---

## 3. Phân chunk (~7–8 từ) — script

- Chia lần lượt, không chồng, không sót id (union = toàn bộ `W_*`).
- Artifact: `skills/subtitle-punch-tag-shortform/scripts/build_template_props_from_transcript.py`

```bash
python3 skills/subtitle-punch-tag-shortform/scripts/build_template_props_from_transcript.py \
  --transcript jobs/<job_id>/source/transcript_word_level.toml \
  --output jobs/<job_id>/remotion/public/template-props.json \
  --write-agent-input jobs/<job_id>/source/punch_agent_input.json \
  --chunk-size 7 --fps 30 --duration-seconds <giây video>
```

`--write-agent-input` ghi JSON có `chunks[].tokens[]` (id/word/start/end) — **không** punch.

---

## 4. Chọn PUNCH — chỉ agent (LLM)

### 4.1 Nguyên tắc nội dung

- Mỗi chunk: một cụm **liên tục** `punch_word_ids` là phần “đắt” nhất về ý (khái niệm trọng tâm, twist, câu chốt) **theo cách agent đọc chunk**, không theo checklist cố định trong code.
- Có thể `punch_word_ids: []` nếu chunk không có cụm đủ mạnh.
- `punch_word_ids ⊆ word_ids`; normal = chunk trừ punch, không lặp token.
- **`punch_rationale`**: 1–2 câu tiếng Việt có dấu — giải thích vì sao agent chọn cụm đó khi **đọc** chunk (không chép template vô nghĩa).

### 4.2 Quy trình agent (bắt buộc)

1. Chạy script **có** `--write-agent-input` (và `--output` để có props tạm hoặc final).
2. Đọc `punch_agent_input.json` (toàn bộ chunk). Có thể đối chiếu audio/transcript đầy đủ nếu cần.
3. Với **từng** `chunk.id`, quyết định punch bằng **suy luận ngữ nghĩa** trên chuỗi từ trong chunk — **không** áp keyword list / điểm do code sinh.
4. Tạo `jobs/<job_id>/source/punch_merge.json`:

```json
{
  "chunks": [
    {
      "id": "C_001",
      "punch_word_ids": ["W_0002", "W_0003"],
      "punch_rationale": "…"
    }
  ]
}
```

Mỗi `id` phải khớp chunk do script sinh (`C_001` …). Có thể chỉ liệt kê chunk cần punch; chunk thiếu trong file → coi như không merge (giữ `[]`) **hoặc** agent phải liệt kê đủ — khuyến nghị: **liệt kê đủ mọi chunk** để QA dễ.

5. Chạy lại build **với** `--merge-punch source/punch_merge.json`.
6. Render Remotion như workflow job.

### 4.3 Lệnh merge

```bash
python3 skills/subtitle-punch-tag-shortform/scripts/build_template_props_from_transcript.py \
  --transcript jobs/<job_id>/source/transcript_word_level.toml \
  --output jobs/<job_id>/remotion/public/template-props.json \
  --merge-punch jobs/<job_id>/source/punch_merge.json \
  --chunk-size 7 --fps 30 --duration-seconds <giây>
```

---

## 5. Không bỏ sót text — đồng bộ hiển thị

### 5.1 Normal line

- `normalWordIds = word_ids \ punch_word_ids` (giữ thứ tự chunk).
- Theo `t`: chỉ các từ có `start <= t`.

### 5.2 Punch line

- `punchFirstStart` … `punchLastEnd` (+ hold ngắn trong composition).

### 5.3 QA nhanh

- Đếm `word_id` trong union chunk = `len(words)` transcript.
- Nghe xem không có khoảng câm lạ giữa hai token liền kề trong chunk.

---

## 6. Xuống dòng: không đứt giữa Whisper **word**

- Mỗi phần tử `words[]` là một token — `whiteSpace: nowrap`, `flexShrink: 0`.
- Hàng: `flexWrap: wrap`, xuống dòng **giữa** token.
- Grapheme: `Intl.Segmenter("vi", { granularity: "grapheme" })`.

### 6.3 Cỡ chữ punch

- Co giãn theo grapheme dài nhất trong cụm punch (xem composition mẫu).

### 6.4 Tách dòng hiển thị (optional)

- Khớp `subtitle-screen-splitter` / `split_subtitle_screens.py` (dấu câu + chữ hoa đầu câu).

---

## 7. Punch hai lớp — shadow dưới / fill trên

- Lớp dưới: `textShadow`; lớp trên: không shadow; cùng glyph.

### 7.3 Màu punch

- Theo `chunk.id` (hash ổn định) trong composition mẫu.

---

## 8. Props Remotion (tối thiểu)

- `words: { id, word, start, end }[]`
- `punch_segments: { version, chunk_word_size?, chunks: [{ id, word_ids, punch_word_ids, punch_rationale? }] }`

---

## 9. Checklist QA trước khi ship

1. Partition đúng, không thiếu `word_id`.
2. Punch ⊆ chunk; normal và punch không trùng token.
3. Không cắt nửa một Whisper word khi wrap punch.
4. Hai lớp punch chồng khớp glyph.
5. Dấu câu / capital: không gộp nhầm hai câu trên một dòng sau split.

---

## 10. Skill liên quan

- **`subtitle-screen-splitter`**
- **`word-timestamps-extractor`**
- **`video-renderer`**

---
