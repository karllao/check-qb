import json
from urllib.parse import parse_qs

import httpx
import pytest
from pydantic import ValidationError

from check_qb.models import Notifications
from check_qb.notifications import notify


@pytest.fixture
def requests(monkeypatch):
    captured = []

    def request(method, url, **kwargs):
        assert kwargs.pop("follow_redirects") is False
        assert kwargs.pop("timeout") == 15
        request = httpx.Request(method, url, **kwargs)
        captured.append(request)
        return httpx.Response(204, request=request)

    monkeypatch.setattr("check_qb.notifications.httpx.request", request)
    return captured


def webhook(**kwargs):
    return Notifications(webhook_enabled=True, webhook_url="https://example.invalid/hook", **kwargs)


def test_nested_json_template_escapes_and_does_not_expand_message_variables(requests):
    settings = webhook(
        webhook_headers={"Authorization": "Bearer secret"},
        webhook_body='{"content":{"text":"{{title}}: {{message}}"},"items":["{{event}}",42]}',
    )
    message = '中文 "quote"\n\\ {{title}}'
    assert notify(settings, "标题", message, force=True) == [{"channel": "Webhook", "status": "success"}]
    assert json.loads(requests[0].content) == {
        "content": {"text": "标题: " + message}, "items": ["summary", 42],
    }
    assert requests[0].headers["Authorization"] == "Bearer secret"


@pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE"])
def test_default_payload_and_methods(requests, method):
    notify(webhook(webhook_method=method), "title", "{{title}}", event="failure")
    assert requests[0].method == method
    assert json.loads(requests[0].content) == {"title": "title", "message": "{{title}}", "event": "failure"}


def test_form_encoding(requests):
    notify(webhook(webhook_format="form", webhook_body='{"text":"{{message}}"}'), "title", "中文 &=+\n", force=True)
    assert parse_qs(requests[0].content.decode()) == {"text": ["中文 &=+\n"]}
    assert requests[0].headers["Content-Type"] == "application/x-www-form-urlencoded"


def test_raw_utf8_and_custom_content_type(requests):
    notify(webhook(webhook_format="text", webhook_body="<text>{{message}}</text>",
                   webhook_headers={"content-type": "application/xml"}), "title", "中文", force=True)
    assert requests[0].content.decode() == "<text>中文</text>"
    assert requests[0].headers["Content-Type"] == "application/xml"


def test_get_url_variables_are_encoded(requests):
    settings = Notifications(webhook_enabled=True, webhook_method="GET",
                             webhook_url="https://example.invalid/{{event}}?text={{message}}")
    notify(settings, "title", "中文 &x=1#part", event="failure")
    assert requests[0].url.path == "/failure"
    assert dict(requests[0].url.params) == {"text": "中文 &x=1#part"}
    assert requests[0].content == b""


def test_event_filter_force_and_disabled(requests):
    assert notify(webhook(), "title", "body") == []
    assert notify(Notifications(), "title", "body", force=True) == []
    assert requests == []
    assert notify(webhook(), "title", "body", force=True)[0]["status"] == "success"


@pytest.mark.parametrize("status", [302, 400, 500, None])
def test_failure_is_redacted_and_not_retried(monkeypatch, status):
    calls = []

    def request(*args, **kwargs):
        calls.append(args)
        if status is None:
            raise httpx.ReadTimeout("secret")
        return httpx.Response(status, text="secret", request=httpx.Request("POST", "https://example.invalid/secret"))

    monkeypatch.setattr("check_qb.notifications.httpx.request", request)
    result = notify(webhook(), "title", "body", force=True)
    assert result[0]["status"] == "failed"
    assert "secret" not in str(result)
    assert len(calls) == 1


@pytest.mark.parametrize("values", [
    {"webhook_enabled": True},
    {"webhook_url": "file:///tmp/test"},
    {"webhook_url": "https://user:pass@example.invalid"},
    {"webhook_url": "https://{{message}}/hook"},
    {"webhook_headers": {"Host": "example.invalid"}},
    {"webhook_headers": {"X-Test": "a\r\nb"}},
    {"webhook_headers": {"Bad Name": "value"}},
    {"webhook_body": "invalid json"},
    {"webhook_format": "form", "webhook_body": '{"nested":{}}'},
    {"webhook_timeout": 0},
])
def test_invalid_configuration(values):
    with pytest.raises(ValidationError):
        Notifications(**values)


def test_old_settings_load_without_retired_provider(store):
    data = store.settings().model_dump()
    data["notifications"].update(iyuu_enabled=True, iyuu_token="old-secret", smtp_host="mail.example.invalid")
    store.put("settings", data)
    migrated = store.settings()
    assert not migrated.notifications.webhook_enabled
    assert migrated.notifications.smtp_host == "mail.example.invalid"
    store.save_settings(migrated)
    assert "iyuu_token" not in store.get("settings")["notifications"]
