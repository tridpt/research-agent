"""Streamlit web UI for research-agent.

Run with:
    streamlit run ui/app.py

Reuses the existing agent core unchanged; this module is a thin UI layer that
collects configuration, runs a research session, streams the agent's steps live,
renders the cited report, supports follow-up chat, source previews, persistent
history, and HTML/Markdown export.
"""
from __future__ import annotations

import os
import sys
import tempfile
import time
from dataclasses import replace
from functools import partial
from pathlib import Path

import streamlit as st

# Make the src/ layout importable without an editable install.
_SRC = Path(__file__).resolve().parent.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

# Local UI helpers.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import (  # noqa: E402
    add_history_item,
    load_history,
    parse_model_list,
    report_to_html,
    save_history,
)

from research_agent.agent import run_session  # noqa: E402
from research_agent.cache import CachingFetchTool, FetchCache  # noqa: E402
from research_agent.config import resolve_settings  # noqa: E402
from research_agent.error_diagnostics import diagnose_llm_error  # noqa: E402
from research_agent.errors import ConfigError, LLMError  # noqa: E402
from research_agent.evaluate import evaluate_report  # noqa: E402
from research_agent.fetch_tool import HttpFetchTool  # noqa: E402
from research_agent.llm import Message, OpenAICompatibleProvider  # noqa: E402
from research_agent.models import Report, SessionState, TraceEventType  # noqa: E402
from research_agent.multi_agent import run_multi_agent  # noqa: E402
from research_agent.observability import CollectingEmitter  # noqa: E402
from research_agent.reflection import run_with_reflection  # noqa: E402
from research_agent.render import render_markdown  # noqa: E402
from research_agent.retry import RetryingLLMProvider  # noqa: E402
from research_agent.search_tool import (  # noqa: E402
    DuckDuckGoSearchTool,
    FallbackSearchTool,
    TavilySearchTool,
)
from research_agent.source_quality import (  # noqa: E402
    assess_source,
    is_local_pdf_source,
    source_display_name,
    source_quality_summary,
)
from research_agent.synthesizer import synthesize, synthesize_stream  # noqa: E402
from research_agent.url_safety import public_http_url_error  # noqa: E402
from research_agent.usage import UsageTracker, format_usage  # noqa: E402


def render_step_vi(event) -> str:
    """Mô tả một bước của agent bằng tiếng Việt, thân thiện với người dùng."""
    detail = event.detail or {}
    rnd = event.round_index
    if event.type is TraceEventType.ACTION_SELECTED:
        action = detail.get("action", "")
        if action == "search":
            return f"🔍 Đang tìm kiếm trên web: “{detail.get('query', '')}”"
        if action == "read":
            return f"📖 Đang đọc nguồn: {detail.get('url', '')}"
        if action == "finish":
            return "✅ Đã đủ thông tin — bắt đầu viết báo cáo"
        if action == "calculate":
            return f"🧮 Đang tính toán: {detail.get('expression', '')}"
        if action == "get_weather":
            return f"🌦️ Đang lấy thời tiết: {detail.get('location', '')}"
        if action == "get_stock":
            return f"📈 Đang lấy dữ liệu chứng khoán: {detail.get('symbol', '')}"
        if action == "get_wikipedia":
            return f"📚 Đang tra Wikipedia: {detail.get('topic', '')}"
        if action == "arxiv_search":
            return f"🎓 Đang tìm bài báo arXiv: {detail.get('paper_query', '')}"
        if action == "convert":
            return f"🔁 Đang chuyển đổi: {detail.get('conversion', '')}"
        if action == "get_news":
            return f"📰 Đang tìm tin gần đây: {detail.get('news_query', '')}"
        if action == "get_github":
            return f"🐙 Đang tra GitHub: {detail.get('repo', '')}"
        if action == "now":
            return "🗓️ Đang lấy ngày giờ hiện tại"
        if action == "plan":
            subs = detail.get("sub_questions", "")
            return "🧩 Lập kế hoạch, chia thành các câu hỏi nhỏ:\n   • " + subs.replace(" | ", "\n   • ")
        return f"⚙️ Hành động: {action}"
    if event.type is TraceEventType.ROUND_COMPLETED:
        return f"   ↳ Xong vòng {rnd} · đã thu thập {event.sources_count} nguồn"
    err = detail.get("error", "")
    if "already read" in err:
        return "   ⚠️ Nguồn này đã đọc rồi, bỏ qua"
    if "domain cap" in err:
        return "   ⚠️ Đã đủ nguồn từ trang này, chuyển sang trang khác"
    if "previously failed" in err or "substituting" in err:
        return "   ↻ Nguồn lỗi, tự chuyển sang nguồn khác"
    if "fetch" in err or "HTTP" in err or "SSL" in err:
        return "   ⚠️ Không tải được trang này (có thể bị chặn), thử nguồn khác"
    if "search" in err:
        return "   ⚠️ Tìm kiếm không có kết quả, thử lại"
    return f"   ⚠️ {err}"


# Provider presets: label -> (base_url, default_model).
PRESETS = {
    "Groq": ("https://api.groq.com/openai/v1", "openai/gpt-oss-20b"),
    "Gemini": ("https://generativelanguage.googleapis.com/v1beta/openai/", "gemini-2.5-flash-lite"),
    "OpenAI": ("https://api.openai.com/v1", "gpt-4o-mini"),
    "Khác (tùy chỉnh)": ("", ""),
}
QUALITY_LABELS_VI = {"high": "Cao", "medium": "Trung bình", "low": "Thấp"}

st.set_page_config(page_title="Research Agent", page_icon="🔎", layout="wide")
st.title("🔎 Research Agent")
st.caption("Trợ lý nghiên cứu tự động: tìm web, đọc nguồn, viết báo cáo có trích dẫn.")


# --------------------------------------------------------------------------
# Persisted config (.env) + persistent history (json)
# --------------------------------------------------------------------------
ENV_PATH = Path(__file__).resolve().parent.parent / ".env"


def load_env_file() -> dict[str, str]:
    data: dict[str, str] = {}
    if ENV_PATH.exists():
        for raw in ENV_PATH.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            data[k.strip()] = v.strip()
    return data


def save_env_file(values: dict[str, str]) -> None:
    current = load_env_file()
    current.update({k: v for k, v in values.items() if v})
    lines = [
        "# Saved by the Research Agent UI. Keep this file private.",
        *[f"{k}={v}" for k, v in current.items()],
        "",
    ]
    ENV_PATH.write_text("\n".join(lines), encoding="utf-8")


_SAVED = load_env_file()


def _initial(key: str, default: str = "") -> str:
    return _SAVED.get(key) or os.environ.get(key, "") or default


# Load persistent history once into session state.
if "history" not in st.session_state:
    st.session_state["history"] = load_history()


# --------------------------------------------------------------------------
# Sidebar: configuration
# --------------------------------------------------------------------------
with st.sidebar:
    st.header("⚙️ Cấu hình")

    _saved_provider = _SAVED.get("RESEARCH_AGENT_PROVIDER_LABEL", "Groq")
    _provider_names = list(PRESETS.keys())
    _provider_index = _provider_names.index(_saved_provider) if _saved_provider in _provider_names else 0
    provider = st.selectbox("Nhà cung cấp LLM", _provider_names, index=_provider_index)
    preset_url, preset_model = PRESETS[provider]

    api_key = st.text_input(
        "API key",
        type="password",
        value=_initial("RESEARCH_AGENT_API_KEY"),
        help="Bấm 'Lưu cấu hình' bên dưới để nhớ lâu dài (ghi vào file .env).",
    )
    base_url = st.text_input("Base URL", value=_initial("RESEARCH_AGENT_BASE_URL", preset_url))
    model = st.text_input("Model", value=_initial("RESEARCH_AGENT_MODEL", preset_model))

    if st.button("💾 Lưu cấu hình", use_container_width=True):
        save_env_file(
            {
                "RESEARCH_AGENT_API_KEY": api_key,
                "RESEARCH_AGENT_BASE_URL": base_url,
                "RESEARCH_AGENT_MODEL": model,
                "RESEARCH_AGENT_PROVIDER_LABEL": provider,
                "RESEARCH_AGENT_TAVILY_API_KEY": st.session_state.get("tavily_key_val", ""),
            }
        )
        st.success("Đã lưu vào .env — lần sau mở app sẽ tự điền sẵn.")

    st.divider()
    mode = st.radio(
        "Chế độ nghiên cứu",
        ["Thường", "Tự đánh giá (reflect)", "Đa agent (multi-agent)"],
        help="Reflect: tự chấm điểm và đào sâu. Multi-agent: chia nhỏ câu hỏi.",
    )

    lang_label = st.radio(
        "Ngôn ngữ báo cáo",
        ["Tiếng Việt", "English", "Tự động (theo câu hỏi)"],
        help="Chọn ngôn ngữ cho báo cáo cuối cùng.",
    )
    lang_code = {"Tiếng Việt": "vi", "English": "en"}.get(lang_label)

    style_label = st.radio(
        "Độ dài báo cáo",
        ["Tiêu chuẩn", "Ngắn gọn", "Chuyên sâu"],
        help="Ngắn gọn: tóm tắt nhanh. Chuyên sâu: phân tích kỹ, nhiều mục.",
    )
    style_code = {"Ngắn gọn": "brief", "Tiêu chuẩn": "standard", "Chuyên sâu": "deep"}[style_label]

    st.divider()
    st.subheader("Giới hạn")
    max_rounds = st.slider("Số vòng tối đa", 2, 20, 8)
    max_sources = st.slider("Số nguồn tối đa", 1, 10, 3)
    min_domains = st.slider("Số tên miền tối thiểu", 1, 5, 2)
    per_source_chars = st.slider("Ký tự mỗi nguồn", 800, 6000, 2000, step=200,
                                 help="Giảm nếu gặp lỗi 'request too large' trên free tier.")
    round_delay = st.slider("Độ trễ giữa các vòng (giây)", 0.0, 10.0, 0.0, step=0.5,
                            help="Tăng lên (vd 3-5s) nếu hay gặp lỗi 429 trên free tier như Groq.")

    tavily_key = st.text_input(
        "Tavily API key (tùy chọn)", type="password",
        value=_initial("RESEARCH_AGENT_TAVILY_API_KEY"),
        key="tavily_key_val",
        help="Để trống thì dùng DuckDuckGo miễn phí.",
    )

    selected_pdf = st.file_uploader(
        "PDF cho phép agent đọc (tùy chọn)",
        type=["pdf"],
        help="Chỉ dùng cho lượt chạy này, tối đa 20 MB; file sẽ bị xóa ngay sau đó.",
    )


# --------------------------------------------------------------------------
# Builders
# --------------------------------------------------------------------------
def _build_settings():
    overrides = {
        "api_key": api_key,
        "base_url": base_url,
        "model": model,
        "max_rounds": max_rounds,
        "max_sources": max_sources,
        "min_domains": min_domains,
        "per_source_char_limit": per_source_chars,
        "round_delay_seconds": round_delay,
        "verbose": True,
    }
    return resolve_settings(env=dict(os.environ), cli_overrides=overrides)


def _build_search(settings):
    providers = []
    if tavily_key:
        providers.append(TavilySearchTool(api_key=tavily_key, max_results=settings.budget.max_sources))
    providers.append(DuckDuckGoSearchTool(max_results=settings.budget.max_sources))
    return FallbackSearchTool(providers)


def _build_llm(settings, usage=None):
    return RetryingLLMProvider(
        OpenAICompatibleProvider(
            api_key=settings.api_key, base_url=settings.base_url, model=settings.model, usage=usage
        ),
        max_attempts=settings.max_llm_attempts,
    )


def _prepare_selected_pdf(uploaded_file):
    """Store one explicitly selected PDF in an isolated temporary directory."""
    if uploaded_file is None:
        return None, None
    max_bytes = 20 * 1024 * 1024
    data = uploaded_file.getvalue()
    if len(data) > max_bytes:
        raise ValueError("PDF lớn hơn giới hạn 20 MB.")
    if not data.startswith(b"%PDF-"):
        raise ValueError("File đã chọn không phải PDF hợp lệ.")
    temporary_dir = tempfile.TemporaryDirectory(prefix="research-agent-pdf-")
    file_name = Path(getattr(uploaded_file, "name", "selected.pdf")).name
    if not file_name or file_name == "." or not file_name.lower().endswith(".pdf"):
        file_name = "selected.pdf"
    path = Path(temporary_dir.name) / file_name
    path.write_bytes(data)
    return temporary_dir, path


def _request_research_retry() -> None:
    """Queue one user-initiated retry for the next Streamlit rerun."""
    st.session_state["_retry_research"] = True


def _show_llm_error(exc: LLMError, retry_key: str | None = None) -> None:
    """Render a safe diagnosis rather than the provider's raw response body."""
    diagnosis = diagnose_llm_error(exc)
    st.error(f"**{diagnosis.title_vi}**\n\n{diagnosis.detail_vi}")
    st.caption("Gợi ý: " + " • ".join(diagnosis.suggestions_vi))
    if diagnosis.retryable and retry_key is not None:
        st.caption("Bạn có thể thử lại thủ công; agent sẽ chạy một phiên mới.")
        st.button(
            "🔁 Thử lại",
            key=retry_key,
            type="primary",
            use_container_width=True,
            on_click=_request_research_retry,
        )


# --------------------------------------------------------------------------
# Main: question + run
# --------------------------------------------------------------------------
auto_retry_research = bool(st.session_state.pop("_retry_research", False))
question = st.text_input("Câu hỏi nghiên cứu của bạn", placeholder="Ví dụ: Sự khác nhau giữa SQL và NoSQL là gì?")
run_clicked = st.button("🚀 Bắt đầu nghiên cứu", type="primary", use_container_width=True) or auto_retry_research

if run_clicked:
    if not question.strip():
        st.error("Vui lòng nhập câu hỏi.")
    elif not api_key.strip():
        st.error("Vui lòng nhập API key ở thanh bên.")
    else:
        try:
            settings = _build_settings()
        except ConfigError as exc:
            st.error(f"Lỗi cấu hình: {exc}")
            st.stop()

        try:
            _pdf_temp_dir, approved_pdf_path = _prepare_selected_pdf(selected_pdf)
        except ValueError as exc:
            st.error(str(exc))
            st.stop()
        if approved_pdf_path is not None:
            settings = replace(settings, allowed_pdf_paths=(approved_pdf_path,))

        usage_tracker = UsageTracker()
        llm = _build_llm(settings, usage=usage_tracker)
        search = _build_search(settings)
        fetch = CachingFetchTool(
            HttpFetchTool(
                blocked_domains=settings.blocked_domains,
                per_source_char_limit=settings.per_source_char_limit,
            ),
            FetchCache(Path(".research_agent_cache"), ttl_seconds=settings.cache_ttl),
            url_validator=public_http_url_error,
        )

        st.subheader("🧠 Agent đang làm gì")
        steps_box = st.empty()
        steps: list[str] = []

        def _on_event(line: str, event) -> None:
            steps.append(render_step_vi(event))
            steps_box.markdown("\n\n".join(steps[-25:]))

        emit = CollectingEmitter(verbose=True, on_event=_on_event)
        synth_fn = partial(synthesize, language=lang_code, style=style_code)

        started = time.time()
        report = None
        stream_in_normal = mode.startswith("Thường")

        with st.status("Đang nghiên cứu...", expanded=True) as status:
            try:
                if mode.startswith("Đa agent"):
                    report = run_multi_agent(question, settings, llm, search, fetch, synth_fn, time.time, emit)
                elif mode.startswith("Tự đánh giá"):
                    report = run_with_reflection(question, settings, llm, search, fetch, synth_fn, time.time, emit)
                elif stream_in_normal:
                    # Normal mode: gather sources first (no synthesis), so we can
                    # stream the report text afterwards.
                    state = SessionState(question=question, started_at=time.time())

                    def _collect_only(_q, _srcs, _llm, _tool_notes):
                        return Report(question=_q, body_markdown="", sources=tuple(_srcs))

                    pre = run_session(
                        question,
                        settings,
                        llm,
                        search,
                        fetch,
                        _collect_only,
                        time.time,
                        emit,
                        initial_state=state,
                    )
                    gathered = list(pre.sources)
                else:
                    report = run_session(question, settings, llm, search, fetch, synth_fn, time.time, emit)
                status.update(label="Hoàn tất!", state="complete")
            except LLMError as exc:
                status.update(label="Lỗi", state="error")
                _show_llm_error(exc, retry_key="retry_research")
                st.stop()

        # Stream the report body live for normal mode (into a temporary area
        # that is cleared afterwards, so the final formatted report below is the
        # single source of truth).
        if stream_in_normal:
            st.subheader("📄 Báo cáo (đang viết...)")
            stream_area = st.empty()
            gen = synthesize_stream(
                question,
                gathered,
                llm,
                tool_notes=state.tool_notes,
                language=lang_code,
                style=style_code,
            )
            _result = {}

            def _text_stream():
                try:
                    while True:
                        yield next(gen)
                except StopIteration as stop:
                    _result["report"] = stop.value

            try:
                with stream_area.container():
                    st.write_stream(_text_stream())
            except LLMError as exc:
                _show_llm_error(exc, retry_key="retry_research")
                st.stop()
            report = _result.get("report") or synthesize(
                question,
                gathered,
                llm,
                tool_notes=state.tool_notes,
                language=lang_code,
                style=style_code,
            )
            stream_area.empty()

        elapsed = time.time() - started

        markdown = render_markdown(report)
        # Keep source URL + a content preview for the "source preview" feature.
        sources = [
            {
                "url": s.url,
                "label": source_display_name(s.url),
                "preview": (s.content or "")[:1500],
                "quality": source_quality_summary(s).label,
                "quality_score": str(source_quality_summary(s).score),
                "quality_reason": source_quality_summary(s).reason,
            }
            for s in report.sources
        ]

        st.session_state["history"] = add_history_item(
            st.session_state["history"],
            question=question,
            markdown=markdown,
            sources=sources,
            elapsed=elapsed,
            mode=mode,
            usage=format_usage(usage_tracker, settings.model),
        )
        # Remember the latest report for the follow-up chat context.
        st.session_state["last_report"] = {"question": question, "markdown": markdown}
        st.session_state["chat"] = []

# --------------------------------------------------------------------------
# Show the most recent report (if any) with export + source preview + chat
# --------------------------------------------------------------------------
history = st.session_state.get("history", [])
if history:
    latest = history[0]

    st.subheader("📄 Báo cáo")
    st.markdown(latest["markdown"])

    st.info(
        f"⏱️ Thời gian: {latest['elapsed']:.1f} giây  ·  "
        f"📚 Số nguồn: {len(latest['sources'])}  ·  "
        f"🔧 Chế độ: {latest['mode']}"
    )
    if latest.get("usage"):
        st.caption(f"🧮 {latest['usage']}")

    # --- Export: Markdown / HTML / PDF / DOCX ---
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.download_button(
            "⬇️ Markdown (.md)",
            data=latest["markdown"],
            file_name="bao-cao.md",
            mime="text/markdown",
            use_container_width=True,
        )
    with c2:
        st.download_button(
            "⬇️ HTML",
            data=report_to_html(latest["question"], latest["markdown"]),
            file_name="bao-cao.html",
            mime="text/html",
            use_container_width=True,
            help="Mở file HTML rồi dùng 'In → Lưu thành PDF' của trình duyệt.",
        )
    with c3:
        try:
            from research_agent.pdf_export import render_pdf_bytes

            pdf_bytes = render_pdf_bytes(latest["question"], latest["markdown"])
            st.download_button(
                "⬇️ PDF (.pdf)",
                data=pdf_bytes,
                file_name="bao-cao.pdf",
                mime="application/pdf",
                use_container_width=True,
                help="Xuất PDF trực tiếp (hỗ trợ tiếng Việt).",
            )
        except Exception:  # noqa: BLE001 - fall back gracefully to HTML export
            st.button(
                "⬇️ PDF (.pdf)",
                disabled=True,
                use_container_width=True,
                help="Cần gói 'fpdf2' và một font Unicode. Hãy dùng nút HTML rồi in ra PDF.",
            )
    with c4:
        try:
            from research_agent.docx_export import render_docx_bytes

            docx_bytes = render_docx_bytes(latest["question"], latest["markdown"])
            st.download_button(
                "⬇️ Word (.docx)",
                data=docx_bytes,
                file_name="bao-cao.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                use_container_width=True,
                help="Xuất file Word mở được trực tiếp.",
            )
        except Exception:  # noqa: BLE001 - fall back gracefully
            st.button(
                "⬇️ Word (.docx)",
                disabled=True,
                use_container_width=True,
                help="Cần gói 'python-docx'. Cài: pip install python-docx",
            )

    # --- Source preview: click to expand the text the agent actually read ---
    st.subheader("📚 Nguồn đã dùng")
    if not latest["sources"]:
        st.caption("Không có nguồn nào.")
    for i, s in enumerate(latest["sources"], 1):
        display_name = s.get("label", source_display_name(s["url"]))
        legacy_quality = assess_source(s["url"], s.get("preview"))
        quality = s.get("quality", legacy_quality.label)
        score = s.get("quality_score", str(legacy_quality.score))
        reason = s.get("quality_reason", legacy_quality.reason)
        quality_label = QUALITY_LABELS_VI.get(quality, "Chưa rõ")
        with st.expander(f"{i}. {display_name} · {quality_label} ({score}/100)"):
            if is_local_pdf_source(s["url"]):
                st.caption("PDF bạn đã cung cấp; không có trang web gốc.")
            else:
                st.link_button("🔗 Mở trang gốc", s["url"])
            if s.get("quality_reason"):
                st.caption("Đánh giá tự động (tham khảo): " + s["quality_reason"])
            if not s.get("quality_reason") and reason:
                st.caption("Automatic quality estimate: " + reason)
            preview = s.get("preview") or ""
            if preview:
                st.caption("Trích đoạn nội dung agent đã đọc:")
                st.text(preview + ("…" if len(preview) >= 1500 else ""))
            else:
                st.caption("(Không có nội dung xem trước.)")


    # --- Follow-up chat grounded in the latest report ---
    st.subheader("💬 Hỏi tiếp về báo cáo")
    st.caption("Đặt câu hỏi nối tiếp; agent trả lời dựa trên báo cáo và nguồn ở trên.")

    if "chat" not in st.session_state:
        st.session_state["chat"] = []

    for turn in st.session_state["chat"]:
        with st.chat_message(turn["role"]):
            st.markdown(turn["content"])

    follow_up = st.chat_input("Ví dụ: Tóm tắt ngắn gọn trong 3 ý chính giúp tôi")
    if follow_up:
        if not api_key.strip():
            st.error("Vui lòng nhập API key ở thanh bên để hỏi tiếp.")
        else:
            st.session_state["chat"].append({"role": "user", "content": follow_up})
            with st.chat_message("user"):
                st.markdown(follow_up)

            try:
                settings = _build_settings()
                chat_llm = _build_llm(settings)
            except ConfigError as exc:
                st.error(f"Lỗi cấu hình: {exc}")
                st.stop()

            # Build grounded messages: report as context + prior chat turns.
            lang_note = ""
            if lang_code == "vi":
                lang_note = " Trả lời bằng tiếng Việt."
            elif lang_code == "en":
                lang_note = " Answer in English."
            messages = [
                Message(
                    role="system",
                    content=(
                        "You are a helpful assistant answering follow-up questions about a "
                        "research report. Base your answers ONLY on the report below; if the "
                        "report doesn't contain the answer, say so honestly." + lang_note
                    ),
                ),
                Message(role="user", content=f"REPORT:\n{latest['markdown']}"),
            ]
            for turn in st.session_state["chat"]:
                messages.append(Message(role=turn["role"], content=turn["content"]))

            with st.chat_message("assistant"):
                with st.spinner("Đang trả lời..."):
                    try:
                        answer = chat_llm.generate(messages)
                    except LLMError as exc:
                        diagnosis = diagnose_llm_error(exc)
                        answer = (
                            f"**{diagnosis.title_vi}**\n\n{diagnosis.detail_vi}\n\n"
                            f"_Gợi ý: {' • '.join(diagnosis.suggestions_vi)}_"
                        )
                st.markdown(answer)
            st.session_state["chat"].append({"role": "assistant", "content": answer})


# --------------------------------------------------------------------------
# Side-by-side model comparison
# --------------------------------------------------------------------------
st.divider()
with st.expander("⚖️ So sánh nhiều model song song"):
    st.caption(
        "Chạy cùng một câu hỏi qua nhiều model (chế độ thường) và xem báo cáo "
        "cùng các chỉ số bên cạnh nhau. Mỗi model dùng API key/base URL ở thanh bên."
    )
    compare_question = st.text_input(
        "Câu hỏi để so sánh",
        value=question or "",
        key="compare_question",
    )
    compare_models_text = st.text_input(
        "Danh sách model (phân tách bằng dấu phẩy, tối đa 4)",
        value=model,
        key="compare_models",
        help="Ví dụ: openai/gpt-oss-20b, llama-3.3-70b-versatile",
    )
    if st.button("⚖️ Chạy so sánh", use_container_width=True, key="run_compare"):
        models_to_compare = parse_model_list(compare_models_text)
        if not compare_question.strip():
            st.error("Vui lòng nhập câu hỏi để so sánh.")
        elif not api_key.strip():
            st.error("Vui lòng nhập API key ở thanh bên.")
        elif len(models_to_compare) < 2:
            st.error("Hãy nhập ít nhất 2 model khác nhau để so sánh.")
        else:
            try:
                base_settings = _build_settings()
            except ConfigError as exc:
                st.error(f"Lỗi cấu hình: {exc}")
                st.stop()
            search = _build_search(base_settings)
            cols = st.columns(len(models_to_compare))
            for col, model_name in zip(cols, models_to_compare, strict=False):
                with col:
                    st.markdown(f"**{model_name}**")
                    run_settings = replace(base_settings, model=model_name)
                    run_llm = _build_llm(run_settings)
                    run_fetch = CachingFetchTool(
                        HttpFetchTool(
                            blocked_domains=run_settings.blocked_domains,
                            per_source_char_limit=run_settings.per_source_char_limit,
                        ),
                        FetchCache(Path(".research_agent_cache"), ttl_seconds=run_settings.cache_ttl),
                        url_validator=public_http_url_error,
                    )
                    synth_fn = partial(synthesize, language=lang_code, style=style_code) if lang_code else partial(synthesize, style=style_code)
                    try:
                        with st.spinner(f"Đang chạy {model_name}..."):
                            cmp_report = run_session(
                                compare_question, run_settings, run_llm, search, run_fetch,
                                synth_fn, time.time, CollectingEmitter(verbose=False),
                            )
                    except LLMError as exc:
                        diagnosis = diagnose_llm_error(exc)
                        st.error(f"{diagnosis.title_vi}")
                        continue
                    metrics = evaluate_report(cmp_report)
                    st.caption(
                        f"📚 {metrics.n_sources} nguồn · 🌐 {metrics.n_domains} tên miền · "
                        f"🔖 {metrics.n_citations} trích dẫn · ⭐ {metrics.avg_source_quality:.0f}/100"
                    )
                    st.markdown(render_markdown(cmp_report))


# --------------------------------------------------------------------------
# Persistent history (survives app restarts)
# --------------------------------------------------------------------------
if history:
    st.divider()
    st.subheader("🕘 Lịch sử nghiên cứu")
    st.caption("Được lưu vào file, vẫn còn sau khi tắt/mở lại app.")
    if st.button("🗑️ Xóa toàn bộ lịch sử"):
        st.session_state["history"] = []
        save_history([])
        st.rerun()

    for idx, item in enumerate(history):
        n_src = len(item.get("sources", []))
        title = (f"[{item['when']}] {item['question']}  ·  {item['mode']}  ·  "
                 f"{item['elapsed']:.1f}s  ·  {n_src} nguồn")
        with st.expander(title):
            st.markdown(item["markdown"])
            cc1, cc2 = st.columns(2)
            with cc1:
                st.download_button(
                    "⬇️ Markdown", data=item["markdown"],
                    file_name=f"bao-cao-{idx+1}.md", mime="text/markdown",
                    key=f"dl_md_{idx}", use_container_width=True,
                )
            with cc2:
                st.download_button(
                    "⬇️ HTML", data=report_to_html(item["question"], item["markdown"]),
                    file_name=f"bao-cao-{idx+1}.html", mime="text/html",
                    key=f"dl_html_{idx}", use_container_width=True,
                )
