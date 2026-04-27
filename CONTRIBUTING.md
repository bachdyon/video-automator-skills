# Đóng góp cho video-automator-skills

Cảm ơn bạn đã quan tâm đến dự án. Tài liệu này tóm tắt cách báo bug, đề xuất feature, và đóng góp code/skill mới.

## Báo bug

Mở [GitHub Issue](https://github.com/bachdyon/video-automator-skills/issues) với các thông tin:

- **OS** + version (macOS 14, Windows 11, Ubuntu 22.04…).
- **Python version** (`python3 --version`).
- Lệnh đã chạy + output lỗi đầy đủ.
- Nếu liên quan asset index: dán nội dung `.asset_index/state.json`.
- Bước tái hiện ngắn gọn.

## Đề xuất feature

Mở Issue với label `feature-request`, mô tả:

- Use case cụ thể (bạn đang làm gì, gặp khó khăn gì).
- Đề xuất giải pháp (nếu có).
- Skill nào sẽ bị ảnh hưởng.

## Quy trình PR

1. Fork repo, tạo branch theo dạng `feat/<short-name>` hoặc `fix/<short-name>`.
2. Commit message dùng [Conventional Commits](https://www.conventionalcommits.org/) (tiếng Anh): `feat(asset-index): add audio resample analyzer`.
3. Trước khi mở PR:
   - Test sạch: `bash setup/Install.command` trên máy chưa cài.
   - Preview docs: `cd docs && mint dev` (mở `http://localhost:3000`).
   - Verify link: `cd docs && mint broken-links`.
4. PR mô tả rõ: vấn đề giải quyết, thay đổi chính, cách test.

## Code style

- **Python**: dùng `ruff` (cấu hình mặc định), 4 spaces, type hints khi có thể, docstring cho function public.
- **MDX**: 1 ý/câu, sentence case heading, dùng MDX components khi cần (`<Note>`, `<Tip>`, `<Steps>`, `<AccordionGroup>`).
- **Ngôn ngữ**: nội dung docs/UX viết tiếng Việt; comment code, commit message, PR title viết tiếng Anh để dễ đọc cross-team. Thuật ngữ kỹ thuật (`watcher`, `embedding`, `idempotent`, `pipeline`, `fork`, `branch`…) giữ nguyên tiếng Anh.

## Đóng góp skill mới

Pattern khi viết skill mới:

1. Copy thư mục `skills/_shared/` làm template (giữ pattern shared utils).
2. Tạo `skills/<your-skill>/SKILL.md` theo format hiện có (frontmatter `name`, `description` ngắn để Cursor index được).
3. Cập nhật [AGENTS.md](AGENTS.md) thêm dòng `$your-skill` vào mục **Project Skills**.
4. Tạo trang `docs/skills/<your-skill>.mdx` port nội dung SKILL.md sang MDX (giữ nguyên nội dung kỹ thuật).
5. Thêm `skills/<your-skill>` vào `docs/docs.json` group **Skills**.
6. Test trong 1 job dummy: `jobs/test-<your-skill>/input/...`.

## Code of Conduct

- Tôn trọng người khác trong mọi tương tác (Issue, PR, discussion).
- Phê bình mang tính xây dựng, không công kích cá nhân.
- Không spam, không quảng cáo, không đăng nội dung độc hại/bất hợp pháp.
- Không chia sẻ API key, secret, hoặc dữ liệu cá nhân của người khác.

## License của contribution

Đóng góp vào repo này được xem như đồng ý cấp quyền cho `bachdyon` theo **PolyForm Noncommercial 1.0.0** (xem [LICENSE](LICENSE)). Nếu contribution của bạn có ý định thương mại hoặc cần điều khoản license khác, vui lòng thoả thuận với tác giả trước.

## Liên hệ

- GitHub Issues: https://github.com/bachdyon/video-automator-skills/issues
- DM tác giả: [@bachdyon](https://github.com/bachdyon)
