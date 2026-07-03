# Hướng dẫn sử dụng Research Agent 🔎🤖

Tài liệu này hướng dẫn bạn cài đặt và dùng **research-agent** từ đầu, kể cả khi
bạn chưa quen với dòng lệnh.

Research Agent là một trợ lý nghiên cứu tự động: bạn đưa một câu hỏi, nó tự tìm
web nhiều vòng, đọc nhiều nguồn, rồi viết một báo cáo Markdown **có trích dẫn**.

---

## Mục lục
1. [Cần chuẩn bị gì](#1-cần-chuẩn-bị-gì)
2. [Cài đặt](#2-cài-đặt)
3. [Lấy API key (miễn phí)](#3-lấy-api-key-miễn-phí)
4. [Cấu hình bằng file .env](#4-cấu-hình-bằng-file-env)
5. [Chạy lần đầu](#5-chạy-lần-đầu)
6. [Ba chế độ nghiên cứu](#6-ba-chế-độ-nghiên-cứu)
7. [Các tùy chọn (flags)](#7-các-tùy-chọn-flags)
8. [Đọc kết quả](#8-đọc-kết-quả)
9. [Mẹo & khắc phục sự cố](#9-mẹo--khắc-phục-sự-cố)
10. [Câu hỏi thường gặp](#10-câu-hỏi-thường-gặp)
11. [Giao diện web](#11-giao-diện-web)

---

## 1. Cần chuẩn bị gì

- **Python 3.11 trở lên** (kiểm tra: mở PowerShell gõ `python --version`).
- **Một API key** của một nhà cung cấp LLM (xem mục 3 — có lựa chọn miễn phí).
- Kết nối Internet (để tìm web và gọi mô hình AI).

---

## 2. Cài đặt

Mở **PowerShell**, đi tới thư mục dự án và cài đặt:

```powershell
cd d:\FunApp\research-agent
python -m pip install -e ".[dev]"
```

Lệnh này cài agent cùng mọi thư viện cần thiết. Chỉ cần làm một lần.

> Không muốn cài Python? Nếu có Docker, chạy:
> `docker build -t research-agent .` rồi
> `docker run --rm -p 8501:8501 -e RESEARCH_AGENT_API_KEY=key-cua-ban research-agent`
> và mở http://localhost:8501.

---

## 3. Lấy API key (miễn phí)

Agent cần một mô hình AI để "suy nghĩ". Bạn dùng được bất kỳ nhà cung cấp nào
tương thích OpenAI. Hai lựa chọn miễn phí:

### Groq (khuyến nghị — nhanh, hạn mức rộng)
1. Vào https://console.groq.com
2. Đăng nhập, vào mục **API Keys** → **Create API Key**.
3. Copy key (dạng `gsk_...`).

### Google Gemini (hạn mức miễn phí hẹp hơn)
1. Vào https://aistudio.google.com/apikey
2. Tạo key (dạng `AIza...`).

> ⚠️ **Bảo mật:** Xem API key như mật khẩu. Không dán lên chat công khai, không
> commit vào Git. Nếu lỡ lộ, vào trang trên xóa key cũ và tạo key mới.

---

## 4. Cấu hình bằng file .env

Để khỏi gõ lại key mỗi lần, tạo một file tên `.env` trong thư mục dự án.
Có sẵn file mẫu `.env.example` — copy nó:

```powershell
Copy-Item .env.example .env
```

Mở `.env` bằng trình soạn thảo và điền key của bạn. Ví dụ dùng **Groq**:

```
RESEARCH_AGENT_API_KEY=gsk_...key_cua_ban...
RESEARCH_AGENT_BASE_URL=https://api.groq.com/openai/v1
RESEARCH_AGENT_MODEL=openai/gpt-oss-20b
RESEARCH_AGENT_PER_SOURCE_CHARS=2000
```

Nếu dùng **Gemini**, thay 3 dòng đầu thành:

```
RESEARCH_AGENT_API_KEY=AIza...key_cua_ban...
RESEARCH_AGENT_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
RESEARCH_AGENT_MODEL=gemini-2.5-flash-lite
```

> File `.env` đã được `.gitignore` bỏ qua nên sẽ không bị đưa lên Git.

---

## 5. Chạy lần đầu

Cách dễ nhất là dùng script `run.ps1` — nó tự đọc `.env` rồi chạy:

```powershell
.\run.ps1 "Trí tuệ nhân tạo tạo sinh là gì?" -o baocao.md -v
```

Giải thích:
- `"Trí tuệ nhân tạo tạo sinh là gì?"` — câu hỏi của bạn (đặt trong ngoặc kép).
- `-o baocao.md` — lưu báo cáo ra file `baocao.md`.
- `-v` — chế độ chi tiết: hiện từng bước agent đang làm (rất hữu ích để học).

Trong lúc chạy bạn sẽ thấy các dòng như:
```
[round 0] SEARCH query='...'      ← agent đang tìm web
[round 1] READ url=https://...    ← agent đang đọc một trang
[round 2] FINISH                  ← agent thấy đủ thông tin, bắt đầu viết
Report written to: baocao.md      ← đã lưu báo cáo
```

---

## 6. Ba chế độ nghiên cứu

### a) Chế độ thường (mặc định)
Tìm → đọc → viết báo cáo. Nhanh và đủ dùng cho hầu hết câu hỏi.
```powershell
.\run.ps1 "Sự khác nhau giữa HTTP và HTTPS" -o baocao.md -v
```

### b) Chế độ tự đánh giá — `--reflect`
Sau khi viết nháp, agent **tự chấm điểm** báo cáo của mình, tìm chỗ còn thiếu và
nghiên cứu thêm để lấp, rồi mới chốt. Báo cáo kỹ hơn, tốn nhiều lệnh gọi hơn.
```powershell
.\run.ps1 "So sánh gRPC và REST" --reflect -v
```

### c) Chế độ đa agent — `--multi-agent`
Một "đội" agent phối hợp:
- **Planner** chia câu hỏi lớn thành vài câu hỏi nhỏ,
- **Researcher** nghiên cứu từng câu hỏi nhỏ,
- **Writer** gộp lại thành một báo cáo.

Hợp với câu hỏi rộng, nhiều khía cạnh.
```powershell
.\run.ps1 "Tình hình pin thể rắn năm 2026" --multi-agent -v
```

### Công cụ agent tự dùng khi cần
Ngoài tìm/đọc web, agent có thể tự gọi thêm các công cụ phù hợp với câu hỏi —
bạn không cần bật gì:
- **Thời tiết**: lấy thời tiết hiện tại của một địa điểm.
- **Chứng khoán**: lấy giá mới nhất của một mã cổ phiếu/chỉ số (vd `AAPL`,
  `^GSPC`, `BTC-USD`) — không cần API key.
- **Wikipedia**: tra cứu tóm tắt bách khoa của một chủ đề (định nghĩa, bối cảnh).
- **arXiv**: tìm và đọc tóm tắt các bài báo học thuật (không cần key).
- **Chuyển đổi**: đổi đơn vị hoặc tiền tệ (vd `10 km to miles`, `100 USD to EUR`).
- **Tin tức**: tìm tin/bài gần đây về một chủ đề (qua Hacker News).
- **GitHub**: tra thông tin repo (sao, ngôn ngữ, giấy phép, bản phát hành mới nhất).
- **Từ điển**: tra định nghĩa một từ tiếng Anh (không cần key).
- **CrossRef**: tìm bài báo bình duyệt + DOI (bổ trợ arXiv, không cần key).
- **Máy tính**: tính toán số học chính xác cho con số trong báo cáo.
- **Ngày giờ**: lấy ngày giờ hiện tại cho câu hỏi kiểu "mới nhất", "hôm nay".
- **Đọc PDF**: chỉ đọc đúng file PDF bạn chỉ định bằng `--pdf duongdan.pdf`.

---

## 7. Các tùy chọn (flags)

| Flag | Ý nghĩa |
|---|---|
| `-o`, `--out` | Đường dẫn file báo cáo (vd `-o baocao.md`) |
| `-v`, `--verbose` | Hiện chi tiết từng bước suy luận |
| `--max-rounds` | Số vòng tối đa (mặc định 8) |
| `--max-sources` | Số nguồn tối đa đọc (mặc định 12) |
| `--max-seconds` | Thời gian tối đa cho một phiên |
| `--min-domains` | Cố đọc ít nhất bao nhiêu tên miền khác nhau |
| `--max-per-domain` | Tối đa bao nhiêu trang từ một tên miền |
| `--reflect` | Bật chế độ tự đánh giá |
| `--reflect-iterations` | Số vòng đánh giá lại tối đa |
| `--multi-agent` | Bật chế độ đội đa agent |
| `--memory` | Nhớ kết quả nghiên cứu cũ và gợi lại khi gặp câu hỏi liên quan |
| `--memory-file` | Đường dẫn file lưu bộ nhớ (mặc định `.research_agent_memory.json`) |
| `--style` | Độ dài/độ sâu báo cáo: `brief` (ngắn), `standard` (mặc định), `deep` (chuyên sâu) |
| `--prefetch` | Tải trước N kết quả đầu song song để đọc nhanh hơn (0 = tắt, mặc định 3) |
| `--cache-llm` | Lưu & tái dùng phản hồi LLM cho prompt giống hệt |
| `--reputation-file` | File JSON bổ sung domain uy tín/kém (kèm `weights` chỉnh điểm theo domain) cho việc xếp hạng nguồn |
| `--chat` | Sau báo cáo, hỏi nối tiếp ngay trên terminal (trả lời dựa trên báo cáo) |
| `--lang` | Ép ngôn ngữ báo cáo/trả lời: `vi` hoặc `en` |
| `--no-cache` | Tắt bộ nhớ đệm (không dùng lại trang đã tải) |
| `--cache-dir` | Thư mục lưu bộ nhớ đệm |
| `--model` | Đổi mô hình cho lần chạy này |

Ví dụ kết hợp:
```powershell
.\run.ps1 "Kubernetes là gì?" -o k8s.md -v --max-sources 3 --min-domains 2
```

### Xuất PDF / Word trực tiếp
Đặt phần mở rộng file là `.pdf` hoặc `.docx` thì agent xuất thẳng định dạng đó
(đều hỗ trợ tiếng Việt):
```powershell
.\run.ps1 "Kubernetes là gì?" -o baocao.pdf -v
.\run.ps1 "Kubernetes là gì?" -o baocao.docx -v
```
Cần gói tùy chọn tương ứng. Cài một lần:
```powershell
python -m pip install -e ".[pdf,docx]"
```
Nếu máy thiếu gói (hoặc font Unicode cho PDF), agent sẽ tự lưu thành `.md` thay thế.

### Bộ nhớ dài hạn
Thêm `--memory` để agent **ghi nhớ** mỗi lần nghiên cứu và **gợi lại** những lần
liên quan ở các phiên sau, dùng làm ngữ cảnh nền (vẫn tự tìm nguồn mới):
```powershell
.\run.ps1 "RAG là gì?" --memory -v
.\run.ps1 "So sánh RAG và fine-tuning" --memory -v   # tận dụng lại lần trước
```

### Chọn độ dài báo cáo
Dùng `--style` để chọn độ dài/độ sâu: `brief` (ngắn gọn), `standard` (mặc định),
`deep` (chuyên sâu, chia mục rõ ràng):
```powershell
.\run.ps1 "Định lý CAP là gì?" --style brief
.\run.ps1 "Phân tích kiến trúc microservices" --style deep -v
```

### Hỏi nối tiếp ngay trên terminal
Thêm `--chat` để sau khi viết báo cáo, bạn hỏi tiếp ngay trong terminal (agent
trả lời dựa trên báo cáo vừa tạo). Gõ dòng trống hoặc `quit` để thoát:
```powershell
.\run.ps1 "RAG là gì?" --chat
```
Khi chạy với `-v`, mỗi vòng còn hiển thị tiến độ so với giới hạn (số vòng/số nguồn).

---

## 8. Đọc kết quả

Sau khi chạy xong:
- Báo cáo được lưu vào file `.md` bạn chỉ định (mở bằng VS Code hay bất kỳ trình
  xem Markdown nào).
- Một bản tóm tắt hiện ngay trên màn hình.

Mỗi báo cáo gồm:
- **Phần thân**: câu trả lời có cấu trúc, mỗi luận điểm chính kèm trích dẫn dạng
  `[https://...]`.
- **Mục Sources**: danh sách tất cả nguồn đã thực sự đọc.

> Agent chỉ trích dẫn những nguồn nó **đã đọc thật** — không bịa nguồn. Nếu không
> tìm được thông tin đáng tin, nó sẽ nói rõ thay vì bịa.

---

## 9. Mẹo & khắc phục sự cố

**Lỗi `Configuration error: Missing required API key`**
→ Bạn chưa đặt key. Kiểm tra file `.env` có dòng `RESEARCH_AGENT_API_KEY=...`.

**Lỗi `429` / `quota` / `rate limit`**
→ Bạn gọi quá nhiều trong thời gian ngắn (thường gặp với Gemini free tier).
Chờ 1 phút rồi thử lại, hoặc đổi sang Groq (hạn mức rộng hơn).

**Lỗi `413` / `Request too large` / `tokens per minute`**
→ Nội dung nạp vào mô hình quá lớn. Giảm `RESEARCH_AGENT_PER_SOURCE_CHARS`
(vd 1500) và `--max-sources` (vd 2).

**Một vài trang báo lỗi `403` hoặc `SSL`**
→ Bình thường: vài website chặn bot. Agent **tự động** bỏ qua và chọn nguồn
khác, không bị gián đoạn.

**Agent tìm mãi không đọc**
→ Giảm phạm vi câu hỏi cho cụ thể hơn, hoặc tăng `--max-rounds`.

---

## 10. Câu hỏi thường gặp

**Dữ liệu của tôi có bị gửi đi đâu không?**
Câu hỏi của bạn được gửi tới nhà cung cấp LLM bạn chọn (Groq/Gemini) và nội dung
trang web được gửi cho mô hình để tổng hợp. Không có máy chủ trung gian nào khác.

**Có tốn tiền không?**
Groq và Gemini đều có hạn mức miễn phí. Tìm kiếm web qua DuckDuckGo cũng miễn phí.

**Đổi mô hình khác được không?**
Được. Bất kỳ API tương thích OpenAI nào (OpenAI, Groq, Gemini, hay Ollama chạy
local) đều dùng được — chỉ cần đổi `RESEARCH_AGENT_BASE_URL` và
`RESEARCH_AGENT_MODEL`.

**Chạy không cần file .env được không?**
Được, đặt biến môi trường trực tiếp trong PowerShell trước khi chạy:
```powershell
$env:RESEARCH_AGENT_API_KEY="gsk_..."
$env:RESEARCH_AGENT_BASE_URL="https://api.groq.com/openai/v1"
$env:RESEARCH_AGENT_MODEL="openai/gpt-oss-20b"
research-agent "câu hỏi của bạn" -v
```

---

## 11. Giao diện web

Nếu bạn không thích dùng dòng lệnh, có sẵn một **giao diện web** đơn giản.

### Cài đặt (một lần)
```powershell
python -m pip install streamlit
```

### Khởi động
```powershell
.\run-ui.ps1
```
Trình duyệt sẽ tự mở tại `http://localhost:8501`. Nếu không, mở thủ công địa chỉ
đó. Để dừng: quay lại cửa sổ PowerShell và nhấn `Ctrl + C`.

### Cách dùng giao diện
1. **Thanh bên trái (Cấu hình):**
   - **Ngôn ngữ giao diện**: chuyển toàn bộ UI giữa Tiếng Việt / English (ở trên cùng).
   - Chọn **Nhà cung cấp LLM** (Groq / Gemini / OpenAI / tùy chỉnh).
   - Dán **API key** của bạn.
   - Base URL và Model sẽ tự điền sẵn theo nhà cung cấp.
   - Bấm **💾 Lưu cấu hình** để nhớ lâu dài — key được ghi vào file `.env`, lần
     sau mở app **tự điền sẵn**, không phải nhập lại.
   - Chọn **Chế độ** (Thường / Tự đánh giá / Đa agent).
   - Chọn **Ngôn ngữ báo cáo** (Tiếng Việt / English / Tự động).
   - Chỉnh các thanh trượt giới hạn nếu cần.
2. **Khung chính:**
   - Gõ câu hỏi vào ô.
   - Bấm **🚀 Bắt đầu nghiên cứu**.
3. Bạn sẽ thấy **các bước của agent** (bằng tiếng Việt) chạy trực tiếp, rồi
   **báo cáo** hiện ra, kèm dòng thống kê thời gian/số nguồn.

### Các tính năng của giao diện
- **🌐 Ngôn ngữ báo cáo**: chọn tiếng Việt để báo cáo ra tiếng Việt dù nguồn là
  tiếng Anh.
- **📏 Độ dài báo cáo**: chọn Ngắn gọn / Tiêu chuẩn / Chuyên sâu ở thanh bên.
- **⚙️ Nâng cao**: chỉnh tải-trước song song, bật cache phản hồi LLM, và ưu tiên
  thông tin mới ngay trong thanh bên.
- **⭐ Uy tín nguồn**: dán một đoạn JSON để tự chỉnh cách xếp hạng nguồn theo
  tên miền của bạn — ví dụ
  `{"established": ["my-lab.example"], "weights": {"my-lab.example": 15}}`
  (cộng/trừ điểm cho từng miền). Áp dụng cho lượt chạy hiện tại.
- **⬇️ Tải báo cáo**: dạng **Markdown**, **HTML**, **PDF trực tiếp**, hoặc
  **Word (.docx)** (PDF/Word hỗ trợ tiếng Việt; nếu máy thiếu gói/font, dùng nút
  HTML rồi "In → Lưu thành PDF").
- **📚 Xem trước nguồn**: bấm vào từng nguồn để xem đoạn nội dung agent đã đọc,
  hoặc mở trang gốc.
- **⚖️ So sánh nhiều model**: chạy cùng một câu hỏi qua 2–4 model song song và
  xem báo cáo cùng các chỉ số (số nguồn, tên miền, trích dẫn, điểm chất lượng)
  cạnh nhau — tiện để chọn model phù hợp.
- **💬 Hỏi tiếp**: đặt câu hỏi nối tiếp ngay dưới báo cáo; agent trả lời dựa trên
  báo cáo và nguồn, giữ ngữ cảnh hội thoại.
- **🕘 Lịch sử**: mọi báo cáo được **lưu vào file**, vẫn còn sau khi tắt/mở lại
  app. Mở lại xem hoặc tải về bất cứ lúc nào.

> Sau khi bấm **Lưu cấu hình**, API key được lưu vào file `.env` (đã được Git bỏ
> qua). Bạn chỉ cần nhập một lần duy nhất.

---

Chúc bạn nghiên cứu vui vẻ! Nếu muốn hiểu sâu cách agent hoạt động bên trong,
xem thêm `README.md` và mã nguồn trong `src/research_agent/`.
