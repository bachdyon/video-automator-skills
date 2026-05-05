---
name: free-tts
description: Tạo giọng đọc miễn phí/local bằng VieNeu-TTS khi người dùng yêu cầu tự động tạo voice/narration/giọng đọc và repo-root `.env` không có `AUSYNCLAB_API_KEY`, hoặc khi user yêu cầu rõ dùng free TTS/VieNeu-TTS thay AusyncLab.
---

# Free TTS (VieNeu-TTS)

## Khi dùng skill này

Dùng skill này khi user yêu cầu kiểu:

- "tự động tạo giọng đọc cho ..."
- "tạo voice/narration miễn phí"
- "không có AusyncLab API key, tạo giọng đọc bằng local/free TTS"
- "dùng VieNeu-TTS"

Trigger mặc định: trước workflow voice, đọc `.env` ở repo root. Nếu không có `AUSYNCLAB_API_KEY` hoặc key rỗng, dùng `$free-tts` thay `$ausynclab-voice`.

Nếu `AUSYNCLAB_API_KEY` tồn tại nhưng user nói rõ "free TTS", "VieNeu-TTS", "local", hoặc "không dùng AusyncLab", vẫn dùng skill này.

## Nguồn chính thức

VieNeu-TTS GitHub: `https://github.com/pnnbao97/VieNeu-TTS`

Quickstart SDK chính thức:

```bash
pip install vieneu
```

Tùy chọn theo quickstart:

```bash
# Windows CPU pre-built
pip install vieneu --extra-index-url https://pnnbao97.github.io/llama-cpp-python-v0.3.16/cpu/

# macOS ARM64 / Apple Silicon, bật Metal acceleration
pip install vieneu --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/metal/
```

Repo VieNeu-TTS cũng hỗ trợ Web UI bằng `uv`:

```bash
git clone https://github.com/pnnbao97/VieNeu-TTS.git
cd VieNeu-TTS
uv sync
uv run vieneu-web
```

Trong pipeline video-agent, ưu tiên SDK + script bên dưới để ghi file audio ổn định cho các skill tiếp theo.

## Quy tắc đầu ra

- Mọi ghi chú/lý do do agent sinh ra trong TOML phải viết tiếng Việt có dấu.
- Văn bản narration tiếng Việt phải giữ nguyên dấu.
- Không yêu cầu hoặc in `AUSYNCLAB_API_KEY`; skill này không dùng AusyncLab.
- Nếu chưa có package `vieneu`, script sẽ tự động cài bằng chính Python đang chạy (`python -m pip install vieneu`). Nếu sandbox/network chặn, xin quyền chạy lại lệnh cài đặt rồi tiếp tục synthesize.

## Đầu vào

- Text trực tiếp từ user, hoặc file text.
- Creative plan TOML, thường là:

```text
source/creative_plan.toml
jobs/<job_id>/source/creative_plan.toml
```

- Tùy chọn: `--mode standard` (mặc định) hoặc `--mode turbo`.
- Tùy chọn: `--voice-id` để dùng preset voice cụ thể.
- Tùy chọn: `--ref-audio` để clone giọng bằng VieNeu-TTS. Với `turbo`, không cần `ref_text`; với `standard`, nên truyền `--ref-text` nếu có.
- Tùy chọn: `--voice-name` để dùng giọng clone đã đặt tên trong `.shared`.

## Voice clone và đặt tên giọng

VieNeu-TTS hỗ trợ voice clone bằng sample audio. Trong skill này, đặt tên giọng bằng file `.shared` nằm cùng cấp `.env` ở repo root.

Format `.shared`:

```text
GIONG_NAME=path/to/sample.wav
GIONG_NU_NEWS=/absolute/path/to/news_voice.mp3
```

Trong đó:

- Bên trái là tên giọng agent/user sẽ gọi bằng `--voice-name`.
- Tên giọng bắt buộc dùng ASCII không dấu: `A-Z`, `a-z`, `0-9`, `_`, và bắt đầu bằng chữ. Ví dụ đúng: `GIONG_NU_NEWS`, `GIONG_NAM_DOC`.
- Bên phải là path tới sample `.wav` hoặc `.mp3`.
- Path tương đối được resolve từ thư mục chứa `.shared`.
- Sample nên dài khoảng 3-5 giây, sạch tiếng, ít nhiễu.
- Với `--mode turbo`, VieNeu-TTS clone trực tiếp từ sample và không cần `ref_text`.
- Với `--mode standard`, nên truyền thêm `--ref-text` nếu biết câu trong sample để tăng độ chính xác.

## Đầu ra

Mặc định:

```text
source/voice.wav
source/voice_selection.toml
```

Khi có video job:

```text
jobs/<job_id>/source/voice.wav
jobs/<job_id>/source/voice_selection.toml
```

Giữ path audio ổn định để `$word-timestamps-extractor`, render plan, và renderer dùng tiếp.

## Hợp đồng TOML

```toml
[voice]
provider = "vieneu-tts"
mode = "standard"
voice_id = "default"
voice_name = "VieNeu-TTS default preset"
language = "vi"
reference_audio = ""
reason = "Dùng VieNeu-TTS local/free vì không có AUSYNCLAB_API_KEY."

[audio]
file_path = "source/voice.wav"
format = "wav"
sample_rate = 24000
duration_seconds = 0.0
state = "SUCCEED"

[source]
script_path = "source/creative_plan.toml"
text_hash = "..."
```

## Workflow

1. Đọc `.env` repo-root, kiểm tra `AUSYNCLAB_API_KEY` có thiếu/rỗng không. Không in secret nếu key tồn tại.
2. Nếu thiếu key, hoặc user yêu cầu free/local/VieNeu, dùng workflow này.
3. Nếu chưa cài `vieneu`, script tự cài theo quickstart:

```bash
.venv/bin/python -m pip install vieneu
```

Nếu không có `.venv`, dùng Python hiện hành:

```bash
python3 -m pip install vieneu
```

Agent không nên dừng lại chỉ để bảo user cài thủ công; hãy để script tự cài. Chỉ hỏi/xin quyền khi sandbox hoặc network yêu cầu escalation.

4. Sinh audio bằng script đi kèm.
5. Ghi `voice_selection.toml`.
6. Nếu audio dùng cho subtitle/timing, chạy tiếp `$word-timestamps-extractor` trên `voice.wav`.

## Script tiện ích

Dùng script đi kèm thay vì viết lại SDK call:

```bash
.venv/bin/python skills/free_tts/scripts/free_tts.py \
  --text "Chào bạn. Đây là giọng đọc được tạo miễn phí bằng VieNeu-TTS." \
  --output-audio source/voice.wav \
  --output source/voice_selection.toml
```

Nếu môi trường cần extra index theo quickstart, truyền thêm:

```bash
.venv/bin/python skills/free_tts/scripts/free_tts.py \
  --text "Chào bạn." \
  --pip-extra-index-url https://abetlen.github.io/llama-cpp-python/whl/metal/ \
  --output-audio source/voice.wav \
  --output source/voice_selection.toml
```

Từ creative plan:

```bash
.venv/bin/python skills/free_tts/scripts/free_tts.py \
  --creative-plan jobs/<job_id>/source/creative_plan.toml \
  --output-audio jobs/<job_id>/source/voice.wav \
  --output jobs/<job_id>/source/voice_selection.toml
```

Turbo mode:

```bash
.venv/bin/python skills/free_tts/scripts/free_tts.py \
  --text-file source/narration.txt \
  --mode turbo \
  --output-audio source/voice.wav \
  --output source/voice_selection.toml
```

Voice cloning:

```bash
.venv/bin/python skills/free_tts/scripts/free_tts.py \
  --text "Đây là giọng đọc được clone bằng VieNeu-TTS." \
  --mode turbo \
  --ref-audio jobs/<job_id>/input/raw_assets/ref_voice.wav \
  --output-audio jobs/<job_id>/source/voice.wav \
  --output jobs/<job_id>/source/voice_selection.toml
```

Lưu sample thành giọng đặt tên trong `.shared`:

```bash
.venv/bin/python skills/free_tts/scripts/free_tts.py \
  --save-voice-name GIONG_NU_NEWS \
  --save-voice-audio jobs/<job_id>/input/raw_assets/ref_voice.wav
```

Dùng giọng đã đặt tên:

```bash
.venv/bin/python skills/free_tts/scripts/free_tts.py \
  --text "Đây là giọng đọc tự động dùng giọng đã lưu." \
  --mode turbo \
  --voice-name GIONG_NU_NEWS \
  --output-audio jobs/<job_id>/source/voice.wav \
  --output jobs/<job_id>/source/voice_selection.toml
```

Liệt kê giọng đã đặt tên trong `.shared`:

```bash
.venv/bin/python skills/free_tts/scripts/free_tts.py --list-named-voices
```

Liệt kê preset voices:

```bash
.venv/bin/python skills/free_tts/scripts/free_tts.py --list-voices
```

## Ghi chú chất lượng

- VieNeu-TTS Standard mode là lựa chọn mặc định theo quickstart SDK.
- Turbo mode nhanh, hỗ trợ English-Vietnamese code-switching và clone giọng dễ hơn, nhưng có thể kém ổn định với câu rất ngắn dưới 5 từ.
- Nếu text quá ngắn, nối thành câu tự nhiên hơn trước khi synthesize.
- Nếu output bị lỗi phát âm tên riêng/tiếng Anh, thử `--mode turbo`.
