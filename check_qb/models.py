from typing import Literal
import json
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
import re
from uuid import uuid4

from apscheduler.triggers.cron import CronTrigger
from pydantic import BaseModel, Field, model_validator, field_validator


class Model(BaseModel):
    model_config = {"extra": "forbid"}


def http_url(value: str) -> str:
    from urllib.parse import urlsplit

    parsed = urlsplit(value)
    if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("请输入不含内嵌账号密码的 HTTP/HTTPS 地址")
    if parsed.fragment:
        raise ValueError("地址不能包含片段标识")
    return value


def valid_pattern(value: str) -> str:
    if len(value) > 500:
        raise ValueError("匹配表达式最长 500 个字符")
    try:
        re.compile(value)
    except re.error:
        raise ValueError("正则表达式无效") from None
    return value


class Connection(Model):
    url: str = "http://127.0.0.1:8080"
    username: str = "admin"
    password: str = ""
    api_key: str = ""
    timeout: int = Field(default=15, ge=2, le=120)
    _url = field_validator("url")(http_url)

    @model_validator(mode="after")
    def connection_url(self):
        from urllib.parse import urlsplit

        if urlsplit(self.url).query:
            raise ValueError("客户端地址不能包含查询参数")
        if self.api_key and not re.fullmatch(r"qbt_[A-Za-z0-9]{28}", self.api_key):
            raise ValueError("qBittorrent API Key 格式无效")
        return self


class Rules(Model):
    feeds: list[str] = Field(default_factory=list, max_length=100)
    min_gib: float = Field(default=1, ge=0, le=100000, allow_inf_nan=False)
    max_gib: float = Field(default=6, gt=0, le=100000, allow_inf_nan=False)
    max_count: int = Field(default=5, ge=1, le=10000)
    reserve_gib: float = Field(default=5, ge=0, le=100000, allow_inf_nan=False)
    replacement: Literal["seed_time", "added_time"] = "seed_time"
    age_hours: float = Field(default=12, gt=0, le=100000, allow_inf_nan=False)
    title_pattern: str = ""
    _pattern = field_validator("title_pattern")(valid_pattern)

    @model_validator(mode="after")
    def bounds(self):
        if self.min_gib > self.max_gib:
            raise ValueError("最小大小不能大于最大大小")
        return self


class Schedule(Model):
    enabled: bool = False
    mode: Literal["interval", "cron"] = "interval"
    interval_seconds: int = Field(default=120, ge=30, le=86400)
    cron: str = "*/2 8-23 * * *"
    timezone: str = "Asia/Tokyo"

    @model_validator(mode="after")
    def valid_schedule(self):
        try:
            ZoneInfo(self.timezone)
            CronTrigger.from_crontab(self.cron, timezone=self.timezone)
        except (ValueError, ZoneInfoNotFoundError):
            raise ValueError("时区或五字段 Cron 表达式无效（星期一为 0）") from None
        return self


class Match(Model):
    text: str = Field(default="", max_length=500)
    regex: bool = False

    @model_validator(mode="after")
    def pattern(self):
        if self.regex:
            valid_pattern(self.text)
        return self


class Attendance(Model):
    id: str = Field(default_factory=lambda: uuid4().hex, pattern=r"^[a-zA-Z0-9_-]{1,64}$")
    name: str = Field(min_length=1, max_length=80)
    enabled: bool = False
    url: str
    method: Literal["GET", "POST"] = "GET"
    headers: dict[str, str] = Field(default_factory=dict)
    cookie: str = ""
    body: str = Field(default="", max_length=100000)
    time: str = Field(default="09:00", pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")
    success: Match = Field(default_factory=Match)
    already: Match = Field(default_factory=Match)
    expired: Match = Field(default_factory=Match)
    _url = field_validator("url")(http_url)

    @model_validator(mode="after")
    def validate_task(self):
        if self.enabled and not (self.success.text or self.already.text):
            raise ValueError("启用签到前必须设置成功或已签到判定条件")
        for key, value in self.headers.items():
            if (
                key.lower() in ("host", "content-length", "connection")
                or "\n" in key + value
                or "\r" in key + value
            ):
                raise ValueError("请求头包含不允许的字段或换行")
        if "\r" in self.cookie or "\n" in self.cookie:
            raise ValueError("Cookie 不能包含换行")
        return self


class Notifications(Model):
    webhook_enabled: bool = False
    webhook_url: str = ""
    webhook_method: Literal["GET", "POST", "PUT", "PATCH", "DELETE"] = "POST"
    webhook_headers: dict[str, str] = Field(default_factory=dict)
    webhook_format: Literal["json", "form", "text"] = "json"
    webhook_body: str = Field(default="", max_length=100000)
    webhook_timeout: int = Field(default=15, ge=2, le=120)
    smtp_enabled: bool = False
    smtp_host: str = ""
    smtp_port: int = Field(default=465, ge=1, le=65535)
    smtp_security: Literal["ssl", "starttls"] = "ssl"
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    smtp_to: list[str] = Field(default_factory=list)
    events: list[Literal["summary", "failure", "expired"]] = Field(
        default_factory=lambda: ["failure", "expired"]
    )

    @model_validator(mode="after")
    def validate_channels(self):
        if self.webhook_enabled and not self.webhook_url.strip():
            raise ValueError("启用 Webhook 需要请求地址")
        if self.webhook_url:
            http_url(self.webhook_url)
            from urllib.parse import urlsplit

            if "{{" in urlsplit(self.webhook_url).netloc:
                raise ValueError("Webhook 变量只能用于 URL 路径和查询参数")
        for key, value in self.webhook_headers.items():
            if (
                not re.fullmatch(r"[!#$%&'*+.^_`|~0-9A-Za-z-]+", key)
                or key.lower() in ("host", "content-length", "connection", "transfer-encoding")
                or "\n" in value or "\r" in value
            ):
                raise ValueError("Webhook 请求头包含不允许的字段或换行")
        if self.webhook_body and self.webhook_format in ("json", "form"):
            try:
                body = json.loads(self.webhook_body)
            except ValueError:
                raise ValueError("Webhook 请求体必须为有效 JSON") from None
            if self.webhook_format == "form" and (
                not isinstance(body, dict) or any(not isinstance(v, str) for v in body.values())
            ):
                raise ValueError("Webhook 表单模板必须为值为字符串的 JSON 对象")
        if self.smtp_enabled and not (self.smtp_host and self.smtp_from and self.smtp_to):
            raise ValueError("启用 SMTP 需要服务器、发件人及收件人")
        if any("\r" in s or "\n" in s for s in [self.smtp_from, *self.smtp_to]):
            raise ValueError("邮件地址不能包含换行")
        return self


class Settings(Model):
    connection: Connection = Field(default_factory=Connection)
    rules: Rules = Field(default_factory=Rules)
    schedule: Schedule = Field(default_factory=Schedule)
    notifications: Notifications = Field(default_factory=Notifications)
    attendance: list[Attendance] = Field(default_factory=list, max_length=50)

    @model_validator(mode="after")
    def unique_ids(self):
        if len({task.id for task in self.attendance}) != len(self.attendance):
            raise ValueError("签到任务 ID 重复")
        return self
