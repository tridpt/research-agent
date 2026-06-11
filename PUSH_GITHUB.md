# Đẩy dự án lên GitHub

Repo local đã sẵn sàng (đã `git init`, commit đầu tiên, nhánh `main`). Giờ chỉ
cần tạo repo trên GitHub và push. Làm theo các bước sau.

## Bước 1 — Tạo repo rỗng trên GitHub
1. Vào https://github.com/new
2. Đặt tên: `research-agent`
3. **Không** tích "Add a README / .gitignore / license" (repo local đã có rồi).
4. Bấm **Create repository**.

## Bước 2 — Kết nối và push
GitHub sẽ hiện địa chỉ repo. Chạy trong PowerShell (thay `tridpt` nếu khác):

```powershell
cd d:\FunApp\research-agent
git remote add origin https://github.com/tridpt/research-agent.git
git push -u origin main
```

Nếu được hỏi đăng nhập, dùng tài khoản GitHub của bạn (hoặc Personal Access
Token thay mật khẩu).

## Bước 3 — CI tự chạy
Repo đã có sẵn workflow `.github/workflows/ci.yml`. Ngay khi push, GitHub
Actions sẽ tự động chạy **lint (ruff) + type-check (mypy) + test (pytest)** trên
Python 3.11, 3.12, 3.13. Xem kết quả ở tab **Actions** của repo.

## ⚠️ Trước khi push — kiểm tra an toàn
- File `.env` (chứa API key) **đã được `.gitignore` bỏ qua** — sẽ không bị đẩy lên.
- Đã xác nhận: chỉ `.env.example` (file mẫu, không có key thật) được commit.
- **Nhắc lại:** các API key bạn từng dán trong quá trình làm việc nên được thu
  hồi và tạo mới (Groq: console.groq.com, Gemini: aistudio.google.com/apikey).

## (Tùy chọn) Thêm badge CI vào README
Sau khi push, thêm dòng này ngay dưới tiêu đề trong `README.md` (thay `tridpt`):

```markdown
![CI](https://github.com/tridpt/research-agent/actions/workflows/ci.yml/badge.svg)
```

Rồi commit lại:
```powershell
git add README.md
git commit -m "Add CI badge"
git push
```
