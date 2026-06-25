"""Lightweight bilingual (Vietnamese/English) strings for the Streamlit UI.

``t(lang, key, **fmt)`` returns the localized string; unknown keys fall back to
the key itself so a missing translation is visible but never crashes the UI.
"""
from __future__ import annotations

LANGS = ("vi", "en")

TRANSLATIONS: dict[str, dict[str, str]] = {
    "app_title": {"vi": "🔎 Research Agent", "en": "🔎 Research Agent"},
    "app_caption": {
        "vi": "Trợ lý nghiên cứu tự động: tìm web, đọc nguồn, viết báo cáo có trích dẫn.",
        "en": "Autonomous research assistant: searches the web, reads sources, writes a cited report.",
    },
    "ui_lang_label": {"vi": "Ngôn ngữ giao diện", "en": "Interface language"},
    "cfg_header": {"vi": "⚙️ Cấu hình", "en": "⚙️ Configuration"},
    "provider_label": {"vi": "Nhà cung cấp LLM", "en": "LLM provider"},
    "api_key_label": {"vi": "API key", "en": "API key"},
    "api_key_help": {
        "vi": "Bấm 'Lưu cấu hình' bên dưới để nhớ lâu dài (ghi vào file .env).",
        "en": "Click 'Save config' below to persist it (written to the .env file).",
    },
    "base_url_label": {"vi": "Base URL", "en": "Base URL"},
    "model_label": {"vi": "Model", "en": "Model"},
    "save_cfg_btn": {"vi": "💾 Lưu cấu hình", "en": "💾 Save config"},
    "save_cfg_ok": {
        "vi": "Đã lưu vào .env — lần sau mở app sẽ tự điền sẵn.",
        "en": "Saved to .env — it will be pre-filled next time.",
    },
    "mode_label": {"vi": "Chế độ nghiên cứu", "en": "Research mode"},
    "mode_help": {
        "vi": "Reflect: tự chấm điểm và đào sâu. Multi-agent: chia nhỏ câu hỏi.",
        "en": "Reflect: self-grades and digs deeper. Multi-agent: splits the question.",
    },
    "report_lang_label": {"vi": "Ngôn ngữ báo cáo", "en": "Report language"},
    "report_lang_help": {
        "vi": "Chọn ngôn ngữ cho báo cáo cuối cùng.",
        "en": "Choose the language of the final report.",
    },
    "lang_vi": {"vi": "Tiếng Việt", "en": "Vietnamese"},
    "lang_en": {"vi": "English", "en": "English"},
    "lang_auto": {"vi": "Tự động (theo câu hỏi)", "en": "Auto (match the question)"},
    "style_label": {"vi": "Độ dài báo cáo", "en": "Report length"},
    "style_help": {
        "vi": "Ngắn gọn: tóm tắt nhanh. Chuyên sâu: phân tích kỹ, nhiều mục.",
        "en": "Brief: quick summary. Deep: thorough, multi-section analysis.",
    },
    "style_standard": {"vi": "Tiêu chuẩn", "en": "Standard"},
    "style_brief": {"vi": "Ngắn gọn", "en": "Brief"},
    "style_deep": {"vi": "Chuyên sâu", "en": "Deep"},
    "limits_header": {"vi": "Giới hạn", "en": "Limits"},
    "max_rounds": {"vi": "Số vòng tối đa", "en": "Max rounds"},
    "max_sources": {"vi": "Số nguồn tối đa", "en": "Max sources"},
    "min_domains": {"vi": "Số tên miền tối thiểu", "en": "Min domains"},
    "per_source_chars": {"vi": "Ký tự mỗi nguồn", "en": "Chars per source"},
    "per_source_help": {
        "vi": "Giảm nếu gặp lỗi 'request too large' trên free tier.",
        "en": "Lower this if you hit 'request too large' on a free tier.",
    },
    "round_delay": {"vi": "Độ trễ giữa các vòng (giây)", "en": "Delay between rounds (s)"},
    "round_delay_help": {
        "vi": "Tăng lên (vd 3-5s) nếu hay gặp lỗi 429 trên free tier như Groq.",
        "en": "Increase (e.g. 3-5s) if you hit 429 errors on a free tier like Groq.",
    },
    "advanced_header": {"vi": "Nâng cao", "en": "Advanced"},
    "prefetch_label": {"vi": "Tải trước song song (số nguồn)", "en": "Parallel prefetch (count)"},
    "prefetch_help": {
        "vi": "Tải trước N kết quả đầu để đọc nhanh hơn (0 = tắt).",
        "en": "Prefetch the top N results for faster reads (0 = off).",
    },
    "cache_llm_label": {"vi": "Cache phản hồi LLM", "en": "Cache LLM responses"},
    "cache_llm_help": {
        "vi": "Tái dùng phản hồi cho prompt giống hệt (tiết kiệm, nhanh hơn khi chạy lại).",
        "en": "Reuse responses for identical prompts (cheaper, faster re-runs).",
    },
    "recency_label": {"vi": "Ưu tiên thông tin mới", "en": "Prioritize recent info"},
    "recency_help": {
        "vi": "Hướng agent tới nguồn mới + công cụ ngày giờ/tin tức.",
        "en": "Steer the agent toward fresh sources + the date/news tools.",
    },
    "tavily_label": {"vi": "Tavily API key (tùy chọn)", "en": "Tavily API key (optional)"},
    "tavily_help": {
        "vi": "Để trống thì dùng DuckDuckGo miễn phí.",
        "en": "Leave empty to use free DuckDuckGo search.",
    },
    "pdf_label": {"vi": "PDF cho phép agent đọc (tùy chọn)", "en": "PDF the agent may read (optional)"},
    "pdf_help": {
        "vi": "Chỉ dùng cho lượt chạy này, tối đa 20 MB; file sẽ bị xóa ngay sau đó.",
        "en": "Used only for this run, max 20 MB; the file is deleted afterward.",
    },
    "question_label": {"vi": "Câu hỏi nghiên cứu của bạn", "en": "Your research question"},
    "question_placeholder": {
        "vi": "Ví dụ: Sự khác nhau giữa SQL và NoSQL là gì?",
        "en": "e.g. What are the differences between SQL and NoSQL?",
    },
    "run_btn": {"vi": "🚀 Bắt đầu nghiên cứu", "en": "🚀 Start research"},
    "err_question": {"vi": "Vui lòng nhập câu hỏi.", "en": "Please enter a question."},
    "err_api_key": {"vi": "Vui lòng nhập API key ở thanh bên.", "en": "Please enter an API key in the sidebar."},
    "agent_working": {"vi": "🧠 Agent đang làm gì", "en": "🧠 What the agent is doing"},
    "researching": {"vi": "Đang nghiên cứu...", "en": "Researching..."},
    "done": {"vi": "Hoàn tất!", "en": "Done!"},
    "error": {"vi": "Lỗi", "en": "Error"},
    "report_header": {"vi": "📄 Báo cáo", "en": "📄 Report"},
    "report_writing": {"vi": "📄 Báo cáo (đang viết...)", "en": "📄 Report (writing...)"},
    "stats_line": {
        "vi": "⏱️ Thời gian: {elapsed:.1f} giây  ·  📚 Số nguồn: {n}  ·  🔧 Chế độ: {mode}",
        "en": "⏱️ Time: {elapsed:.1f}s  ·  📚 Sources: {n}  ·  🔧 Mode: {mode}",
    },
    "dl_md": {"vi": "⬇️ Markdown (.md)", "en": "⬇️ Markdown (.md)"},
    "dl_html": {"vi": "⬇️ HTML", "en": "⬇️ HTML"},
    "dl_html_help": {
        "vi": "Mở file HTML rồi dùng 'In → Lưu thành PDF' của trình duyệt.",
        "en": "Open the HTML then use the browser's 'Print → Save as PDF'.",
    },
    "dl_pdf": {"vi": "⬇️ PDF (.pdf)", "en": "⬇️ PDF (.pdf)"},
    "dl_pdf_help": {"vi": "Xuất PDF trực tiếp (hỗ trợ tiếng Việt).", "en": "Direct PDF export (Unicode-safe)."},
    "dl_pdf_disabled": {
        "vi": "Cần gói 'fpdf2' và một font Unicode. Hãy dùng nút HTML rồi in ra PDF.",
        "en": "Needs 'fpdf2' and a Unicode font. Use the HTML button then print to PDF.",
    },
    "dl_docx": {"vi": "⬇️ Word (.docx)", "en": "⬇️ Word (.docx)"},
    "dl_docx_help": {"vi": "Xuất file Word mở được trực tiếp.", "en": "Export a ready-to-open Word file."},
    "dl_docx_disabled": {
        "vi": "Cần gói 'python-docx'. Cài: pip install python-docx",
        "en": "Needs 'python-docx'. Install: pip install python-docx",
    },
    "sources_header": {"vi": "📚 Nguồn đã dùng", "en": "📚 Sources used"},
    "no_sources": {"vi": "Không có nguồn nào.", "en": "No sources."},
    "open_source": {"vi": "🔗 Mở trang gốc", "en": "🔗 Open original page"},
    "pdf_no_origin": {
        "vi": "PDF bạn đã cung cấp; không có trang web gốc.",
        "en": "Your provided PDF; there is no source web page.",
    },
    "preview_caption": {"vi": "Trích đoạn nội dung agent đã đọc:", "en": "Excerpt the agent read:"},
    "no_preview": {"vi": "(Không có nội dung xem trước.)", "en": "(No preview available.)"},
    "chat_header": {"vi": "💬 Hỏi tiếp về báo cáo", "en": "💬 Ask follow-up questions"},
    "chat_caption": {
        "vi": "Đặt câu hỏi nối tiếp; agent trả lời dựa trên báo cáo và nguồn ở trên.",
        "en": "Ask follow-ups; the agent answers from the report and sources above.",
    },
    "chat_placeholder": {
        "vi": "Ví dụ: Tóm tắt ngắn gọn trong 3 ý chính giúp tôi",
        "en": "e.g. Summarize this in 3 key points",
    },
    "chat_need_key": {
        "vi": "Vui lòng nhập API key ở thanh bên để hỏi tiếp.",
        "en": "Please enter an API key in the sidebar to ask follow-ups.",
    },
    "answering": {"vi": "Đang trả lời...", "en": "Answering..."},
    "compare_expander": {"vi": "⚖️ So sánh nhiều model song song", "en": "⚖️ Compare multiple models side by side"},
    "compare_caption": {
        "vi": "Chạy cùng một câu hỏi qua nhiều model (chế độ thường) và xem báo cáo cùng chỉ số cạnh nhau.",
        "en": "Run one question across multiple models (normal mode) and compare reports + metrics.",
    },
    "compare_question": {"vi": "Câu hỏi để so sánh", "en": "Question to compare"},
    "compare_models": {"vi": "Danh sách model (phân tách bằng dấu phẩy, tối đa 4)", "en": "Models (comma-separated, max 4)"},
    "compare_models_help": {
        "vi": "Ví dụ: openai/gpt-oss-20b, llama-3.3-70b-versatile",
        "en": "e.g. openai/gpt-oss-20b, llama-3.3-70b-versatile",
    },
    "compare_btn": {"vi": "⚖️ Chạy so sánh", "en": "⚖️ Run comparison"},
    "compare_err_models": {"vi": "Hãy nhập ít nhất 2 model khác nhau để so sánh.", "en": "Enter at least 2 different models to compare."},
    "history_header": {"vi": "🕘 Lịch sử nghiên cứu", "en": "🕘 Research history"},
    "history_caption": {
        "vi": "Được lưu vào file, vẫn còn sau khi tắt/mở lại app.",
        "en": "Saved to disk; persists across app restarts.",
    },
    "clear_history": {"vi": "🗑️ Xóa toàn bộ lịch sử", "en": "🗑️ Clear all history"},
}


def t(lang: str, key: str, **fmt: object) -> str:
    """Return the localized string for ``key`` in ``lang`` (fallback: key)."""
    entry = TRANSLATIONS.get(key)
    if not entry:
        return key
    text = entry.get(lang) or entry.get("vi") or key
    return text.format(**fmt) if fmt else text
