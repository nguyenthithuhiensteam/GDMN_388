"""
Kết nối dịch vụ AI (Claude API qua SDK chính thức `anthropic`).

- Chỉ hoạt động khi AI_ENABLED=True, có ANTHROPIC_API_KEY và đã cài gói `anthropic`
  (pip install -r requirements-ai.txt). Nếu không, mọi chức năng chính vẫn chạy bình thường.
- Trước khi gửi, văn bản được lọc bớt thông tin định danh (email, số điện thoại, số CCCD/CMND).
- Kết quả AI chỉ là bản nháp gợi ý; không tự động lưu/xuất bản/ban hành.
"""
import logging
import re

from django.conf import settings

logger = logging.getLogger(__name__)

# Các model hỗ trợ tham số fallbacks="default" (chuyển model dự phòng khi bị từ chối vì chính sách an toàn).
_FALLBACK_MODELS = {"claude-opus-5-5", "claude-opus-5", "claude-fable-5-1", "claude-sonnet-5-5"}

SYSTEM_PROMPT = (
    "Bạn là trợ lý hỗ trợ công việc hành chính, chuyên môn cho cán bộ, giáo viên một trường mầm non tại Việt Nam. "
    "Luôn viết bằng tiếng Việt chuẩn mực, rõ ràng, phù hợp môi trường giáo dục mầm non. "
    "Kết quả của bạn chỉ là bản nháp để người có thẩm quyền kiểm tra, chỉnh sửa và phê duyệt. "
    "Không bịa đặt số liệu, tên người, số hiệu văn bản hay trích dẫn pháp luật; nếu cần căn cứ pháp lý, "
    "hãy để chỗ trống dạng [cần bổ sung căn cứ] và nhắc người dùng kiểm chứng với văn bản hiện hành. "
    "Không đưa thông tin cá nhân của trẻ em vào nội dung."
)


class AIError(Exception):
    pass


def is_available():
    if not (settings.AI_ENABLED and settings.AI_API_KEY):
        return False
    try:
        import anthropic  # noqa: F401
    except ImportError:
        return False
    return True


_PATTERNS = [
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"), "[email]"),
    (re.compile(r"(?<!\d)(?:\+?84|0)(?:[\s.-]?\d){8,10}(?!\d)"), "[số điện thoại]"),
    (re.compile(r"(?<!\d)\d{12}(?!\d)"), "[số định danh]"),
    (re.compile(r"(?<!\d)\d{9}(?!\d)"), "[số định danh]"),
]


def redact(text):
    """Che thông tin định danh phổ biến trước khi gửi ra dịch vụ bên ngoài."""
    for pattern, repl in _PATTERNS:
        text = pattern.sub(repl, text)
    return text


def generate(prompt, max_tokens=4000):
    if not is_available():
        raise AIError("Mô-đun AI chưa được cấu hình.")
    import anthropic

    text = redact(prompt)[: settings.AI_MAX_INPUT_CHARS]
    client = anthropic.Anthropic(api_key=settings.AI_API_KEY, timeout=120.0, max_retries=2)
    params = {
        "model": settings.AI_MODEL,
        "max_tokens": max_tokens,
        "system": SYSTEM_PROMPT,
        "messages": [{"role": "user", "content": text}],
        "output_config": {"effort": settings.AI_EFFORT},
    }
    try:
        if settings.AI_MODEL in _FALLBACK_MODELS:
            response = client.beta.messages.create(
                **params, betas=["server-side-fallback-2026-07-01"], fallbacks="default",
            )
        else:
            response = client.messages.create(**params)
    except anthropic.AuthenticationError as exc:
        logger.error("AI: khóa API không hợp lệ")
        raise AIError("Khóa API AI không hợp lệ. Liên hệ quản trị hệ thống.") from exc
    except anthropic.RateLimitError as exc:
        raise AIError("Dịch vụ AI đang quá tải, vui lòng thử lại sau ít phút.") from exc
    except anthropic.APIStatusError as exc:
        logger.warning("AI: lỗi dịch vụ %s", exc.status_code)
        raise AIError("Dịch vụ AI trả về lỗi. Vui lòng thử lại sau.") from exc
    except anthropic.APIConnectionError as exc:
        raise AIError("Không kết nối được dịch vụ AI.") from exc
    if response.stop_reason == "refusal":
        raise AIError("Dịch vụ AI từ chối xử lý yêu cầu này. Hãy điều chỉnh nội dung yêu cầu.")
    out = "".join(block.text for block in response.content if block.type == "text").strip()
    if not out:
        raise AIError("Dịch vụ AI không trả về nội dung.")
    if response.stop_reason == "max_tokens":
        out += "\n\n[Nội dung có thể bị cắt ngắn do vượt giới hạn độ dài.]"
    return out
