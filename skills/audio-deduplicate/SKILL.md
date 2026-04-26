---
name: audio-deduplicate
description: Làm sạch bản ghi giọng nói WAV/MP3 theo workflow 2-phase semantic - AI viết lại nội dung không lặp vào TOML, sau đó căn keep flag từng token để render audio cuối.
metadata:
  short-description: Khử lặp audio theo 2-phase semantic
---

# Audio Deduplicate (2-phase semantic)

## TL;DR

Làm sạch lặp/restart/vấp trong file `.wav|.mp3` bằng 2 phase do AI thực hiện:

1. **Phase 1**: AI đọc `reconstructed_article` (verbatim từ ASR), viết bản `reconstructed_article_rewrite` không lặp ý, ghi vào TOML.
2. **Phase 2**: AI duyệt `[[words]]`, gán `keep=false` cho token KHÔNG thuộc rewrite (dùng helper `apply_keep_flags.py` với danh sách ID range).
3. Render concat các đoạn `keep=true`, output WAV/MP3.

## Hard Rules (BẮT BUỘC, không vi phạm)

1. **Workflow 2-phase.** Phase 1 trước Phase 2. Render từ chối nếu `metadata.rewrite_status != "filled"`.
2. **Chỉ chỉnh `keep` flag trên token gốc.** KHÔNG thêm/sửa/xoá/đảo token. KHÔNG thay đổi `id`, `word`, `start`, `end`.
3. **AI quyết định ngữ nghĩa**, script chỉ thực thi cơ học. KHÔNG tạo script ad-hoc/heredoc để tự động compute keep.
4. **Chỉ dùng 5 script chuẩn**: `ensure_faster_whisper.py`, `extract_words_timestamps.py`, `build_words_timestamp.py`, `apply_keep_flags.py`, `render_from_keep_words.py`.
5. **File trung gian** trong `jobs/{job_id}/input/audio/tmp/`. Output cuối: `jobs/{job_id}/input/audio/<ten>_output.wav|mp3`.
6. **Text fields multi-line.** `reconstructed_article.text` và `reconstructed_article_rewrite.text` PHẢI ở dạng `"""..."""`, mỗi câu 1 dòng.

## Pipeline at a glance

| Bước | Script | Input | Output |
| --- | --- | --- | --- |
| 1 | `setup/ensure_faster_whisper.py` | — | model cache |
| 2 | `audio/extract_words_timestamps.py` | audio gốc | `tmp/words.json`, `tmp/extract_plan.json` |
| 3 | `words/build_words_timestamp.py` | `tmp/words.json` | `tmp/words_timestamp.toml` (rewrite_status=`pending`) |
| 4 | **PHASE 1 (AI)** | `tmp/words_timestamp.toml` | cùng file, `rewrite_status=filled` |
| 5 | **PHASE 2 (AI + `words/apply_keep_flags.py`)** | cùng file | cùng file, `keep=false` cho token bỏ |
| 6 | `audio/render_from_keep_words.py` | TOML + audio | `<ten>_output.wav`, `tmp/render_keep_plan.json` |

## Step 1 – Setup (chạy lần đầu)

```bash
python3 skills/audio-deduplicate/scripts/setup/ensure_faster_whisper.py --model small
```

## Step 2 – Extract words

```bash
python3 skills/audio-deduplicate/scripts/audio/extract_words_timestamps.py \
  jobs/{job_id}/input/audio/<ten>.wav \
  --output-words-json jobs/{job_id}/input/audio/tmp/words.json \
  --language vi \
  --plan-json jobs/{job_id}/input/audio/tmp/extract_plan.json
```

## Step 3 – Build TOML

```bash
python3 skills/audio-deduplicate/scripts/words/build_words_timestamp.py \
  --input-words jobs/{job_id}/input/audio/tmp/words.json \
  --output-toml jobs/{job_id}/input/audio/tmp/words_timestamp.toml
```

TOML output (skeleton, multi-line text format):

```toml
[metadata]
source_words_file = "..."
mode = "two_phase_semantic_keep_review"
original_word_count = 799
rewrite_status = "pending"

[reconstructed_article]
text = """
Câu verbatim 1.
Câu verbatim 2 có lặp/restart.
…
"""

[reconstructed_article_rewrite]
text = ""

[[words]]
id = "W_000001"
word = "Nhà"
start = 0.0
end = 0.38
keep = true
```

## Step 4 – PHASE 1: Semantic rewrite (AI)

### Trước khi viết: load context + pre-flight pivot scan

- Mở TOML, đọc TOÀN BỘ `reconstructed_article.text` (1 câu/dòng).
- Tự xác định "ý chính" của bài (5–10 ý) trước khi rewrite, để khỏi quên giữa chừng.
- **Pre-flight pivot scan (BẮT BUỘC)**: Quét tuần tự cặp câu liền kề. Với mỗi cụm 2-5 từ liên tiếp xuất hiện ≥2 lần ở các câu liền kề, đánh dấu là **"candidate restart pivot"**. Với mỗi pivot:
  1. Câu trước (A) có kết thúc trọn ý không? (chủ-vị đầy đủ + dấu kết câu hợp lý)
  2. Câu sau (B) có kết thúc trọn ý không? Có chứa phần đóng câu (?, !, kết luận, vị ngữ chính) không?
  3. Nếu **A cụt + B chứa phần đóng** → đây là **mid-sentence restart** → cần MERGE (xem T-restart-mid).

### Decision table (gặp X → làm Y)

| Tình huống ASR | Hành động trong rewrite |
| --- | --- |
| Lặp ý 2+ lần | Giữ 1 phiên bản đầy đủ thông tin nhất |
| Restart toàn câu (`thứ 3 là phải báo... thứ 3 là phải báo cho quản lý...`) | Giữ bản hoàn chỉnh, bỏ bản nháp |
| **Mid-sentence restart (pivot-phrase restart)** — câu A cụt ở pivot, câu B lặp pivot rồi nối phần đóng câu (`...xan lớp mặt bằng. Cái công việc xan lớp mặt bằng này thì nó sẽ như thế nào?`) | **MERGE**: giữ `prefix(A) + suffix(B)`, bỏ pivot ở câu B. Output: `prefix(A) + " " + suffix sau pivot ở B` |
| Vấp từ (`nhưng nhưng`, `về... về`) | Giữ 1 lần |
| Câu mở lặp + triển khai (`May là có người. May là mình với bố mình...`) | Giữ câu giàu thông tin hơn |
| Noise đa ngôn ngữ / tiếng vô nghĩa | Bỏ |
| Câu ngắn hơn nhưng cùng ý với câu dài hơn | Giữ câu dài (đầy đủ ý) |
| Typo ASR (`tuyết đối`, `bế tông`) | KHÔNG sửa (Phase 2 cần khớp token gốc) |
| Câu hoàn chỉnh không lặp | Giữ nguyên |

### Mid-sentence restart — ví dụ chuẩn

Verbatim:
```
Dân Vân Phòng ... bỏ phố về quê ... cụ thể là xan lớp mặt bằng.
Cái công việc xan lớp mặt bằng này thì nó sẽ như thế nào?
```

Pivot trùng = `xan lớp mặt bằng`. Câu A cụt (ý chưa hoàn chỉnh — speaker dự định hỏi tiếp). Câu B = `[pivot] thì nó sẽ như thế nào?` = phần đóng câu hỏi.

✘ **WRONG** (giữ 2 câu rời):
```
Dân Vân Phòng ... cụ thể là xan lớp mặt bằng.
Cái công việc xan lớp mặt bằng này thì nó sẽ như thế nào?
```

✓ **RIGHT** (MERGE: prefix A + suffix B):
```
Dân Vân Phòng ... cụ thể là xan lớp mặt bằng thì nó sẽ như thế nào?
```

Phase 2 ranges tương ứng: bỏ cụm pivot ở câu B (`Cái công việc xan lớp mặt bằng này` = W_033-W_040), giữ `thì nó sẽ như thế nào?` (W_041-W_046).

### Anti-patterns

- ✘ Thêm fact/từ mới không có trong nguồn.
- ✘ Đảo thứ tự câu so với nguồn.
- ✘ Sửa typo ASR thành chính tả chuẩn.
- ✘ Biên tập thành văn viết (giữ giọng văn nói).
- ✘ Dùng inline string 1 dòng dài; PHẢI multi-line `"""..."""`.
- ✘ Giữ 2 câu rời chỉ vì ASR đặt dấu chấm giữa câu (xem mid-sentence restart).
- ✘ Bỏ qua pre-flight pivot scan; nếu thấy pivot 2-5 từ trùng giữa 2 câu liền kề mà không kiểm tra MERGE → coi như chưa làm Phase 1.
- ✘ Để cùng 1 pivot xuất hiện ≥2 lần trong rewrite (trừ trường hợp ngữ nghĩa thực sự khác).

### Output format BẮT BUỘC

Sửa trực tiếp 2 trường trong TOML:

```toml
[metadata]
rewrite_status = "filled"          # đổi từ "pending"

[reconstructed_article_rewrite]
text = """
Câu rewrite 1.
Câu rewrite 2.
…
"""
```

### Mini example

Input verbatim:
```
Nhưng mà nói về bài học thì chắc là không ở đâu.
Chỉ cho các bạn nhiều nhà mình.
Nhưng mà nói về kịp nạn thì cũng không.
Nhà mình thì mới đổ bế tông.
Nhà mình thì mới đổ bế tông được mấy hôm luôn.
Nhưng mà nói về kịp nạn thì chắc là không ở đâu nhiều như nhà mình.
```

Rewrite (giữ duy nhất câu hoàn chỉnh):
```
Nhà mình thì mới đổ bế tông được mấy hôm.
Nhưng mà nói về kịp nạn thì chắc là không ở đâu nhiều như nhà mình.
```

### Exit gate Phase 1 (BẮT BUỘC pass trước khi sang Phase 2)

- [ ] `rewrite_status = "filled"`.
- [ ] `reconstructed_article_rewrite.text` non-empty và ở dạng `"""..."""` multi-line.
- [ ] Mọi ý chính của `reconstructed_article` xuất hiện trong rewrite (không thiếu thông tin).
- [ ] Không thêm fact/từ mới, không đảo thứ tự, không sửa typo ASR.
- [ ] **Sentence-end check**: Mỗi câu rewrite kết thúc trọn ý (chủ-vị đầy đủ + dấu kết câu hợp lý). Nếu 1 câu rewrite "cụt" và câu sau bắt đầu bằng pivot trùng → quay lại MERGE.
- [ ] **Pivot-once rule**: Liệt kê tất cả pivot 2-5 từ xuất hiện ≥2 lần trong rewrite; mỗi pivot phải có lý do ngữ nghĩa rõ ràng (ví dụ: chủ đề thực sự được nhắc lại). Nếu không → còn nghi ngờ chưa MERGE.
- [ ] **Pre-flight pivot scan đã xử lý**: Mỗi candidate pivot đã được phân loại thành 1 trong: `[merge | drop-restart | keep-both-distinct-meaning]`.

## Step 5 – PHASE 2: Map keep flags (AI + script)

### Context reload trước khi map (ĐỌC LẠI 3 RULE)

1. Token nằm trong rewrite → `keep=true` (không vào `--remove`).
2. Token thuộc cụm bỏ (lặp/restart/vấp/noise) → đưa toàn cụm vào `--remove`.
3. Khi 1 ý xuất hiện 2 lần ở source nhưng rewrite chỉ giữ 1 lần → giữ phiên bản timestamp đẹp (ít nhiễu, prosody tự nhiên), bỏ phiên bản còn lại.

### Quy trình

1. Quét tuần tự `[[words]]` từ ID 1.
2. Mỗi khi gặp đầu một cụm bỏ, ghi nhận ID đầu. Khi cụm bỏ kết thúc, ghi nhận ID cuối → 1 range `lo-hi`.
3. Token rìa cụm bỏ (ví dụ `thì`, `là`, `về...`) nếu thuộc cụm bỏ thì cũng bỏ.
4. Tổng hợp tất cả range thành 1 chuỗi cách nhau bởi dấu phẩy.

### Apply

```bash
python3 skills/audio-deduplicate/scripts/words/apply_keep_flags.py \
  --words-toml jobs/{job_id}/input/audio/tmp/words_timestamp.toml \
  --reset \
  --remove "11-56,91-97,111,317-331,351-381,483-496,544-596,..."
```

Cờ:

- `--reset`: bỏ mọi flag cũ trước khi áp range mới (idempotent, dùng mặc định).
- `--keep-only "lo-hi,..."`: ngược lại, chỉ giữ các range liệt kê.
- `--dry-run`: tính toán nhưng KHÔNG ghi file (dùng để thử range).
- `--print-kept`: in chuỗi kept words ghép lại (read-only).
- `--diff-rewrite`: in `kept_words K/total`, `jaccard(token_set)` so với rewrite, danh sách token chỉ-có-1-bên.

### Anti-patterns

- ✘ Sinh script tạm để tính range tự động bằng heuristic.
- ✘ Sửa `id`, `word`, `start`, `end`.
- ✘ Bỏ qua cờ `--reset` khi rerun (sẽ stack flip với lần trước).

### Mini example

Cho 5 token đầu: `1=Nhà 2=mình 3=thì 4=mới 5=đổ` (thuộc rewrite); `6-10` lặp y hệt → range bỏ `6-10`.

```bash
... apply_keep_flags.py --reset --remove "6-10"
# flipped 5 word(s); keep=true count: 5/10
```

### Exit gate Phase 2 (BẮT BUỘC pass trước khi render)

```bash
python3 skills/audio-deduplicate/scripts/words/apply_keep_flags.py \
  --words-toml jobs/{job_id}/input/audio/tmp/words_timestamp.toml \
  --diff-rewrite
```

Yêu cầu:

- [ ] `jaccard(token_set) >= 0.95` (gần khớp ngữ nghĩa với rewrite).
- [ ] `in rewrite only` rỗng hoặc chỉ chứa từ rất phổ biến (như "1", "thì") — nếu có từ nội dung quan trọng còn thiếu → quay lại nới range.
- [ ] `in kept only` rỗng hoặc chỉ chứa từ filler còn sót do tokenize khác — nếu có cụm chưa bỏ → bổ sung range.

Nếu fail bất kỳ check nào, sửa danh sách `--remove` và rerun (không cần render giữa chừng).

## Step 6 – Render

```bash
python3 skills/audio-deduplicate/scripts/audio/render_from_keep_words.py \
  jobs/{job_id}/input/audio/<ten>.wav \
  --words-toml jobs/{job_id}/input/audio/tmp/words_timestamp.toml \
  --output jobs/{job_id}/input/audio/<ten>_output.wav \
  --pad-before 0.03 --pad-after 0.05 --merge-gap 0.08 \
  --plan-json jobs/{job_id}/input/audio/tmp/render_keep_plan.json
```

Auto-guards trong script:

- Hard fail nếu `rewrite_status != "filled"`.
- Hard fail nếu `reconstructed_article_rewrite.text` rỗng.
- Cảnh báo (không fail) nếu 100% token vẫn `keep=true` (audio không có lặp).

## Step 7 – Final QA

- [ ] File output đúng path `jobs/{job_id}/input/audio/<ten>_output.<ext>`.
- [ ] Không có file trung gian ngoài `tmp/`.
- [ ] `render_keep_plan.json` có `kept_word_count < original_word_count`.
- [ ] `output_duration_seconds < input_duration_seconds`.
- [ ] Nghe lại không còn lặp ý/restart/vấp từ; mạch nói tự nhiên.

## Tùy chọn render hữu ích

- `--pad-before` (mặc định `0.03`): padding trước mỗi đoạn keep.
- `--pad-after` (mặc định `0.05`): padding sau.
- `--merge-gap` (mặc định `0.08`): gộp 2 đoạn keep liền kề nếu khoảng trống nhỏ hơn.
- `--min-interval`: bỏ đoạn keep ngắn hơn ngưỡng.

## Troubleshooting

| Triệu chứng | Nguyên nhân | Xử lý |
| --- | --- | --- |
| Render báo `rewrite_status != filled` | Quên Phase 1 | Hoàn thành Phase 1, set `rewrite_status="filled"` |
| Render báo rewrite text empty | Chưa điền Phase 1 | Điền `reconstructed_article_rewrite.text` |
| Jaccard < 0.95 ở exit gate Phase 2 | Bỏ thừa hoặc thiếu | Xem `in rewrite only` / `in kept only`, sửa range |
| Output cụt câu, có vấp | Padding quá nhỏ | Tăng `--pad-before/--pad-after` |
| Output có khoảng lặng dài | `--merge-gap` quá nhỏ | Tăng `--merge-gap` |
| Audio đầu vào nhiều noise/đa ngôn ngữ | ASR token kém | Rewrite ở mức câu, range ở cụm lớn hơn |

## Lưu ý kiến trúc

- Skill chỉ điều khiển audio qua `keep`. Mọi phán xét ngữ nghĩa do AI đảm nhận trong Phase 1.
- TOML là single source of truth cho toàn bộ state. Mọi script đọc/ghi cùng 1 file.
- Pipeline idempotent: rerun với `--reset` cho cùng range cho ra cùng kết quả.
