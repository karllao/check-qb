import regex


def search(pattern: str, text: str) -> bool:
    """Bound user-defined patterns so a bad expression cannot stall the scheduler."""
    try:
        return bool(regex.search(pattern, text, timeout=0.1))
    except TimeoutError:
        raise ValueError("正则匹配超过时间限制，请简化表达式") from None
