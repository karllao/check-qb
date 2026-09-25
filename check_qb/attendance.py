import httpx

from .models import Attendance, Match
from .matching import search


def matches(condition: Match, text: str):
    if not condition.text:
        return False
    return search(condition.text, text) if condition.regex else condition.text in text


def classify(task: Attendance, status: int, text: str):
    if matches(task.expired, text) or status in (401, 403):
        return {"status": "expired", "reason": "登录凭据失效或命中失效标志"}
    if not 200 <= status < 300:
        return {"status": "failed", "reason": f"HTTP {status}，未跟随重定向"}
    if matches(task.already, text):
        return {"status": "already", "reason": "今天已经签到"}
    if matches(task.success, text):
        return {"status": "success", "reason": "命中签到成功标志"}
    return {"status": "unknown", "reason": "未匹配明确结果，请检查站点及判定条件"}


def attend(task: Attendance):
    try:
        headers = dict(task.headers)
        if task.cookie:
            headers["Cookie"] = task.cookie
        with httpx.stream(
            task.method,
            task.url,
            headers=headers,
            content=task.body.encode() if task.method == "POST" else None,
            timeout=30,
            follow_redirects=False,
        ) as response:
            content = bytearray()
            for chunk in response.iter_bytes():
                content.extend(chunk)
                if len(content) > 2 * 1024 * 1024:
                    return {"status": "unknown", "reason": "响应超过 2 MiB，未判定且未重试"}
            text = bytes(content).decode(response.encoding or "utf-8", errors="replace")
            return classify(task, response.status_code, text)
    except httpx.HTTPError:
        return {"status": "unknown", "reason": "连接失败或超时，结果不确定，未自动重试"}
