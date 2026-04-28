Thư mục font dùng chung cho mọi job (cùng cấp với jobs/).

Đặt file bản quyền tại đây, ví dụ:
  UTM Bebas.ttf   (hoặc UTM-Bebas.ttf — phải khớp staticFile trong composition)

Font preview có thể ghi "UTM BEBAS" (full name, toàn hoa). Trong code Remotion
font-family / FontFace vẫn dùng tên đăng ký: UTM Bebas (B hoa, ebas thường, có dấu cách).

Trước khi render Remotion, chạy đồng bộ (từ thư mục remotion của job):
  npm run render
hoặc:
  node ../../../scripts/sync-fonts.mjs

File sẽ được copy vào remotion/public/fonts/ để staticFile() đọc được.
