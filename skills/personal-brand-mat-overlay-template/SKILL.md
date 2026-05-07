---
name: personal-brand-mat-overlay-template
description: Personal brand video dọc — beat người (punch) vs beat trám (mờ + infographic + meme). Bắt buộc đọc templates/personal-brand-mat-overlay/template.toml mục [rules] trước khi chỉnh timing hoặc visualize.
---

# Personal brand — mat overlay

## Nguồn

- Thư mục template: `templates/personal-brand-mat-overlay/`
- Hợp đồng: `template.toml` (**`[rules]`** = thi hành, không tùy chọn)

## PHẢI THỰC HIỆN (trích `template.toml`)

1. **Hai kiểu hiện nội dung:** danh sách dòng → lần lượt được; biểu đồ / so sánh một cụm → **bật cả khối** tại mốc mở ý (vd. « CEO »).
2. **Độ dài beat trám:** bao hết cụm thoại trong lời gốc.
3. **So sánh hai phía:** một khung; nặng đỏ / nhẹ xanh lá.
4. **Meme:** trong `public`; rộng hơn dòng chữ dài nhất; cao theo tỷ lệ; cách phần khác ≥ 7% chiều cao khung.
5. **Chữ trên hình:** canh đúng khối, kiểm tra đúng độ phân giải xuất.
6. **Sau đổi visualize/timing:** **bắt buộc** `npm run render` (trừ khi user nói không).

## Đầu vào một job

- `remotion/public/assets/source.mp4`, `voice.wav`
- `remotion/public/template-props.json` — khớp voice
- `remotion/public/overlay-beats.json` — người / trám + mốc hiện
- `remotion/public/mat-memes/` — GIF local nếu dùng

## Lệnh (trong `jobs/<job_id>/remotion`)

```bash
npm install
npm run render
```

**Không** để `node_modules`, `build`, `out`, `output`, `.remotion` trong **`templates/personal-brand-mat-overlay/remotion`** khi commit. Xem `.cursor/rules/templates-no-generated.mdc`.

## Studio

```bash
npm run studio
```

## Instantiate

`skills/personal-brand-mat-overlay-template/scripts/instantiate.py` — copy shell vào `jobs/<id>/remotion`.

## Kiểm tra

```bash
python3 skills/job-to-template/scripts/audit_template.py \
  --template-id personal-brand-mat-overlay \
  --template-skill personal-brand-mat-overlay-template
```

## Liên quan

- `$job-to-template` — chuẩn hóa template từ job
- `$remotion-best-practices` — Remotion
