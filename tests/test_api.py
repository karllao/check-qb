import io

import pytest
from fastapi.testclient import TestClient

from check_qb.api import create_app


@pytest.fixture
def client(store, service):
    with TestClient(create_app(store, service, setup_token="setup-test")) as client:
        yield client


def login(client):
    response = client.post(
        "/api/v1/auth/setup", json={"password": "test-password-123", "setup_token": "setup-test"}
    )
    assert response.status_code == 200
    client.headers["X-CSRF-Token"] = response.json()["csrf"]


@pytest.mark.parametrize("encoding", ["cp1252", "ascii", "utf-8"])
def test_startup_with_redirected_stdout(store, service, monkeypatch, encoding):
    buffer = io.BytesIO()
    with io.TextIOWrapper(buffer, encoding=encoding, errors="strict") as stdout:
        with monkeypatch.context() as patch:
            patch.setattr("sys.stdout", stdout)
            with TestClient(create_app(store, service, setup_token="setup-test")) as client:
                assert client.get("/healthz").status_code == 200
                output = buffer.getvalue().decode(encoding)
                assert "setup-test" in output
                if encoding == "utf-8":
                    assert "首次设置凭据" in output
                else:
                    assert "Setup token" in output
                login(client)


def test_setup_and_auth_boundary(client):
    assert client.get("/api/v1/settings").status_code == 401
    assert (
        client.post(
            "/api/v1/auth/setup", json={"password": "test-password-123", "setup_token": "wrong"}
        ).status_code
        == 403
    )
    login(client)
    assert client.get("/api/v1/settings").status_code == 200
    assert "HttpOnly" in client.cookies.get("check_qb_session", "") or client.cookies.get("check_qb_session")
    client.headers.pop("X-CSRF-Token")
    assert client.put("/api/v1/settings", json={"rules": {"max_count": 2}}).status_code == 403
    session = client.get("/api/v1/auth/session").json()
    assert session == client.get("/api/v1/auth/session").json()
    client.headers["X-CSRF-Token"] = session["csrf"]
    assert client.post("/api/v1/auth/logout").status_code == 200
    assert client.get("/api/v1/settings").status_code == 401


def test_secret_redaction_preservation_and_encryption(client, store):
    login(client)
    secret = "never-expose-this-password"
    api_key = "qbt_" + "A" * 28
    response = client.put(
        "/api/v1/settings", json={"connection": {"password": secret, "api_key": api_key}}
    )
    assert response.status_code == 200
    assert secret not in response.text
    assert api_key not in response.text
    assert response.json()["connection"]["password_configured"]
    assert response.json()["connection"]["api_key_configured"]
    client.put("/api/v1/settings", json={"connection": {"username": "new-user"}})
    assert store.settings().connection.password == secret
    assert store.settings().connection.api_key == api_key
    assert secret.encode() not in store.dbpath.read_bytes()
    assert api_key.encode() not in store.dbpath.read_bytes()
    response = client.put("/api/v1/settings", json={"connection": {"password": {"bad": secret}}})
    assert response.status_code == 422
    assert secret not in response.text
    client.put("/api/v1/settings", json={"connection": {"password": ""}})
    assert store.settings().connection.password == ""
    client.put("/api/v1/settings", json={"connection": {"api_key": ""}})
    assert store.settings().connection.api_key == ""


def test_webhook_secrets_and_test_endpoint(client, store, monkeypatch):
    import httpx

    login(client)
    values = {
        "webhook_enabled": True,
        "webhook_url": "https://example.invalid/private-hook",
        "webhook_headers": {"Authorization": "Bearer private-token"},
        "webhook_body": '{"text":"{{message}}","token":"private-body"}',
    }
    response = client.put("/api/v1/settings", json={"notifications": values})
    assert response.status_code == 200
    for field in ("webhook_url", "webhook_headers", "webhook_body"):
        assert field not in response.json()["notifications"]
        assert response.json()["notifications"][field + "_configured"]
    client.put("/api/v1/settings", json={"notifications": {"webhook_timeout": 20}})
    for key, value in values.items():
        assert getattr(store.settings().notifications, key) == value
    for secret in ("private-hook", "private-token", "private-body"):
        assert secret not in client.get("/api/v1/settings").text
        assert secret.encode() not in store.dbpath.read_bytes()

    calls = []

    def request(method, url, **kwargs):
        calls.append((method, url, kwargs))
        return httpx.Response(204, request=httpx.Request(method, url))

    monkeypatch.setattr("check_qb.notifications.httpx.request", request)
    assert client.post("/api/v1/notifications/test").json() == [{"channel": "Webhook", "status": "success"}]
    assert len(calls) == 1
    assert calls[0][2]["timeout"] == 20
    history = client.get("/api/v1/runs")
    assert history.status_code == 200
    assert history.json()[0]["kind"] == "notification"
    for secret in ("private-hook", "private-token", "private-body"):
        assert secret not in history.text
    response = client.put("/api/v1/settings", json={"notifications": {
        "webhook_enabled": False, "webhook_url": "", "webhook_headers": {}, "webhook_body": "",
    }})
    assert response.status_code == 200
    assert store.settings().notifications.webhook_headers == {}
    assert store.settings().notifications.webhook_url == ""
    assert store.settings().notifications.webhook_body == ""


def test_validation_and_cron(client):
    login(client)
    assert client.put("/api/v1/settings", json={"rules": {"min_gib": 9, "max_gib": 1}}).status_code == 422
    assert client.put("/api/v1/settings", json={"schedule": {"cron": "invalid"}}).status_code == 422
    assert client.put("/api/v1/settings", json={"schedule": {"timezone": "unknown/zone"}}).status_code == 422
    assert client.put("/api/v1/settings", json={"rules": {"title_pattern": "["}}).status_code == 422
    assert (
        client.put("/api/v1/settings", json={"schedule": {"enabled": True, "mode": "cron"}}).status_code
        == 200
    )
    assert client.get("/api/v1/dashboard").json()["jobs"][0]["next_run"]


def test_rate_limit(client):
    for _ in range(5):
        assert client.post("/api/v1/auth/login", json={"password": "wrong-password"}).status_code == 401
    assert client.post("/api/v1/auth/login", json={"password": "wrong-password"}).status_code == 429


def test_attendance_secrets_and_disabled_default(client, store):
    login(client)
    response = client.put(
        "/api/v1/settings",
        json={
            "attendance": [
                {
                    "name": "test",
                    "url": "https://site.invalid",
                    "cookie": "secret-cookie",
                    "headers": {"Authorization": "secret-header"},
                    "body": "secret-body",
                }
            ]
        },
    )
    assert response.status_code == 200
    assert "secret-" not in response.text
    task = response.json()["attendance"][0]
    assert not task["enabled"]
    assert (
        client.put(
            "/api/v1/settings", json={"attendance": [{"id": task["id"], "name": "changed"}]}
        ).status_code
        == 200
    )
    assert store.settings().attendance[0].cookie == "secret-cookie"
    assert client.get("/api/v1/dashboard").json()["jobs"] == []
