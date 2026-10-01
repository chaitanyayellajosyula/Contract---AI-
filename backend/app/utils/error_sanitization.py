import re


_MAX_ERROR_LENGTH = 500
_SENSITIVE_ERROR_VALUE = re.compile(
    r"(?i)\b(authorization|access[_-]?token|refresh[_-]?token|token|api[_-]?key|secret|password|credential|cookie)\b"
    r"\s*[:=]\s*(?:\"[^\"]*\"|'[^']*'|[^\s,;&]+)"
)
_BEARER_VALUE = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+")
_URL_VALUE = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)
_STRUCTURED_RESPONSE = re.compile(r"(?is)(?:^|:\s*)(?:\{|<html\b|<!doctype\s+html)")


def sanitize_error_message(error: Exception | None) -> str:
    if error is None:
        return "Automatic ingestion failed"
    error_type = type(error).__name__[:80]
    raw_detail = str(error)
    detail = raw_detail.splitlines()[0] if raw_detail else ""
    if _STRUCTURED_RESPONSE.search(detail):
        detail = "remote response rejected"
    else:
        detail = _BEARER_VALUE.sub("Bearer [REDACTED]", detail)
        detail = _SENSITIVE_ERROR_VALUE.sub(r"\1=[REDACTED]", detail)
        detail = _URL_VALUE.sub("[URL]", detail)
    return f"{error_type}: {detail}".strip()[:_MAX_ERROR_LENGTH]