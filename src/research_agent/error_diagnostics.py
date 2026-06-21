"""Safe, actionable explanations for LLM provider failures."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LLMErrorDiagnosis:
    """A user-facing diagnosis that never includes the provider response body."""

    kind: str
    title_vi: str
    detail_vi: str
    suggestions_vi: tuple[str, ...]
    retryable: bool


def diagnose_llm_error(error: BaseException | str) -> LLMErrorDiagnosis:
    """Classify a provider error without exposing raw details or credentials."""
    text = str(error).lower()

    if _contains_any(text, ("http 401", "http 403", "invalid_api_key", "invalid api key", "unauthorized", "forbidden")):
        return LLMErrorDiagnosis(
            kind="authentication",
            title_vi="Không xác thực được với nhà cung cấp mô hình",
            detail_vi="API key có thể sai, hết hiệu lực hoặc không có quyền dùng mô hình đã chọn.",
            suggestions_vi=(
                "Kiểm tra lại API key ở thanh bên.",
                "Xác nhận API key có quyền truy cập model này.",
            ),
            retryable=False,
        )

    if _contains_any(text, ("http 429", "rate limit", "rate_limit", "quota", "tokens per minute")):
        return LLMErrorDiagnosis(
            kind="rate_limit",
            title_vi="Nhà cung cấp đang giới hạn lượt gọi",
            detail_vi="Yêu cầu đã vượt giới hạn tạm thời hoặc quota của tài khoản.",
            suggestions_vi=(
                "Chờ 1–2 phút rồi thử lại.",
                "Giảm số nguồn hoặc ký tự mỗi nguồn nếu dùng gói miễn phí.",
            ),
            retryable=True,
        )

    if _contains_any(text, ("tool_use_failed", "tool call validation failed", "attempted to call tool", "function calling")):
        return LLMErrorDiagnosis(
            kind="tool_call",
            title_vi="Model không xử lý được tool call",
            detail_vi="Model hoặc endpoint hiện tại không tương thích hoàn toàn với cách agent gọi công cụ.",
            suggestions_vi=(
                "Đổi sang model hỗ trợ OpenAI-compatible tool calling.",
                "Kiểm tra Base URL có đúng với nhà cung cấp đã chọn.",
            ),
            retryable=False,
        )

    if _contains_any(text, ("http 404", "model_not_found", "model not found", "does not exist")):
        return LLMErrorDiagnosis(
            kind="model_not_found",
            title_vi="Không tìm thấy model đã chọn",
            detail_vi="Tên model hoặc Base URL không khớp với nhà cung cấp hiện tại.",
            suggestions_vi=(
                "Kiểm tra lại tên model ở thanh bên.",
                "Dùng preset nhà cung cấp để khôi phục Base URL mặc định.",
            ),
            retryable=False,
        )

    if _contains_any(text, ("timed out", "timeout", "connection error", "network", "dns", "ssl")):
        return LLMErrorDiagnosis(
            kind="network",
            title_vi="Không kết nối được tới nhà cung cấp mô hình",
            detail_vi="Kết nối mạng hoặc dịch vụ nhà cung cấp có thể đang gặp sự cố tạm thời.",
            suggestions_vi=(
                "Kiểm tra mạng và Base URL.",
                "Thử lại sau ít phút.",
            ),
            retryable=True,
        )

    if _contains_any(text, ("http 500", "http 502", "http 503", "http 504", "service unavailable")):
        return LLMErrorDiagnosis(
            kind="provider_unavailable",
            title_vi="Dịch vụ mô hình đang tạm thời không khả dụng",
            detail_vi="Nhà cung cấp trả về lỗi máy chủ sau các lần thử lại tự động.",
            suggestions_vi=(
                "Thử lại sau ít phút.",
                "Nếu lỗi kéo dài, đổi sang nhà cung cấp hoặc model khác.",
            ),
            retryable=True,
        )

    if _contains_any(text, ("http 400", "bad request", "invalid request")):
        return LLMErrorDiagnosis(
            kind="invalid_request",
            title_vi="Yêu cầu gửi tới mô hình không hợp lệ",
            detail_vi="Cấu hình model, Base URL hoặc khả năng của model có thể không khớp.",
            suggestions_vi=(
                "Kiểm tra Base URL và tên model.",
                "Đổi sang model hỗ trợ tool calling nếu đang nghiên cứu tự động.",
            ),
            retryable=False,
        )

    return LLMErrorDiagnosis(
        kind="unknown",
        title_vi="Không thể gọi mô hình",
        detail_vi="Nhà cung cấp trả về lỗi chưa thể phân loại an toàn.",
        suggestions_vi=(
            "Kiểm tra API key, Base URL và tên model.",
            "Thử lại sau ít phút hoặc đổi nhà cung cấp.",
        ),
        retryable=False,
    )


def _contains_any(text: str, signals: tuple[str, ...]) -> bool:
    return any(signal in text for signal in signals)
