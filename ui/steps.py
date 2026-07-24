"""Pure rendering of agent trace events into human-friendly step lines.

No Streamlit calls, so ``render_step`` can be unit-tested directly. ``app.py``
calls it for each live event while a research session runs.
"""
from __future__ import annotations

from research_agent.models import TraceEventType


def render_step(event, lang: str = "vi") -> str:
    """Describe one agent step in a user-friendly way (Vietnamese or English)."""
    vi = lang != "en"
    detail = event.detail or {}
    rnd = event.round_index
    if event.type is TraceEventType.ACTION_SELECTED:
        action = detail.get("action", "")
        q = detail.get("query", "")
        if action == "search":
            return (f"🔍 Đang tìm kiếm trên web: “{q}”" if vi else f"🔍 Searching the web: “{q}”")
        if action == "read":
            u = detail.get("url", "")
            return (f"📖 Đang đọc nguồn: {u}" if vi else f"📖 Reading source: {u}")
        if action == "finish":
            return ("✅ Đã đủ thông tin — bắt đầu viết báo cáo" if vi
                    else "✅ Enough information — writing the report")
        if action == "calculate":
            e = detail.get("expression", "")
            return (f"🧮 Đang tính toán: {e}" if vi else f"🧮 Calculating: {e}")
        if action == "get_weather":
            loc = detail.get("location", "")
            return (f"🌦️ Đang lấy thời tiết: {loc}" if vi else f"🌦️ Getting weather: {loc}")
        if action == "get_stock":
            s = detail.get("symbol", "")
            return (f"📈 Đang lấy dữ liệu chứng khoán: {s}" if vi else f"📈 Getting stock quote: {s}")
        if action == "get_wikipedia":
            tpc = detail.get("topic", "")
            return (f"📚 Đang tra Wikipedia: {tpc}" if vi else f"📚 Looking up Wikipedia: {tpc}")
        if action == "arxiv_search":
            pq = detail.get("paper_query", "")
            return (f"🎓 Đang tìm bài báo arXiv: {pq}" if vi else f"🎓 Searching arXiv: {pq}")
        if action == "convert":
            c = detail.get("conversion", "")
            return (f"🔁 Đang chuyển đổi: {c}" if vi else f"🔁 Converting: {c}")
        if action == "get_news":
            nq = detail.get("news_query", "")
            return (f"📰 Đang tìm tin gần đây: {nq}" if vi else f"📰 Finding recent news: {nq}")
        if action == "get_github":
            r = detail.get("repo", "")
            return (f"🐙 Đang tra GitHub: {r}" if vi else f"🐙 Looking up GitHub: {r}")
        if action == "get_dictionary":
            w = detail.get("word", "")
            return (f"📖 Đang tra từ điển: {w}" if vi else f"📖 Looking up the dictionary: {w}")
        if action == "crossref_search":
            dq = detail.get("doi_query", "")
            return (f"🔬 Đang tìm bài báo (CrossRef): {dq}" if vi else f"🔬 Searching CrossRef: {dq}")
        if action == "pubmed_search":
            pmq = detail.get("pubmed_query", "")
            return (f"🧬 Đang tìm bài báo y sinh (PubMed): {pmq}" if vi
                    else f"🧬 Searching PubMed: {pmq}")
        if action == "openalex_search":
            oaq = detail.get("openalex_query", "")
            return (f"🎓 Đang tìm học thuật (OpenAlex): {oaq}" if vi
                    else f"🎓 Searching OpenAlex: {oaq}")
        if action == "now":
            return ("🗓️ Đang lấy ngày giờ hiện tại" if vi else "🗓️ Getting the current date/time")
        if action == "plan":
            subs = detail.get("sub_questions", "")
            head = ("🧩 Lập kế hoạch, chia thành các câu hỏi nhỏ:" if vi
                    else "🧩 Planning — splitting into sub-questions:")
            return head + "\n   • " + subs.replace(" | ", "\n   • ")
        return (f"⚙️ Hành động: {action}" if vi else f"⚙️ Action: {action}")
    if event.type is TraceEventType.ROUND_COMPLETED:
        return (f"   ↳ Xong vòng {rnd} · đã thu thập {event.sources_count} nguồn" if vi
                else f"   ↳ Round {rnd} done · {event.sources_count} sources collected")
    err = detail.get("error", "")
    if "already read" in err:
        return ("   ⚠️ Nguồn này đã đọc rồi, bỏ qua" if vi else "   ⚠️ Already read this source, skipping")
    if "domain cap" in err:
        return ("   ⚠️ Đã đủ nguồn từ trang này, chuyển sang trang khác" if vi
                else "   ⚠️ Enough from this site, switching to another")
    if "previously failed" in err or "substituting" in err:
        return ("   ↻ Nguồn lỗi, tự chuyển sang nguồn khác" if vi
                else "   ↻ Source failed, switching to another")
    if "fetch" in err or "HTTP" in err or "SSL" in err:
        return ("   ⚠️ Không tải được trang này (có thể bị chặn), thử nguồn khác" if vi
                else "   ⚠️ Couldn't load this page (maybe blocked), trying another")
    if "search" in err:
        return ("   ⚠️ Tìm kiếm không có kết quả, thử lại" if vi else "   ⚠️ Search returned nothing, retrying")
    return f"   ⚠️ {err}"
