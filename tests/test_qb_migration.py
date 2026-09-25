import httpx
import pytest

from check_qb.cli import read_legacy
from check_qb.models import Connection
from check_qb.qb import QB, QBError, prepare_torrent


def test_login_post_and_auth_error():
    qb = QB(Connection(password="secret"))
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, text="Fails.")

    qb.http.close()
    qb.http = httpx.Client(base_url="http://qb/", transport=httpx.MockTransport(handler))
    with pytest.raises(QBError, match="登录失败"):
        with qb:
            pass
    assert calls[0].method == "POST"
    assert "secret" not in str(calls[0].url)


def test_api_key_uses_bearer_and_skips_login():
    key = "qbt_" + "a" * 28
    qb = QB(Connection(url="http://qb:8080/proxy", api_key=key))
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, text="v5.2.3")

    headers = dict(qb.http.headers)
    qb.http.close()
    qb.http = httpx.Client(
        base_url="http://qb:8080/proxy/", headers=headers, transport=httpx.MockTransport(handler)
    )
    with qb:
        pass
    assert len(calls) == 1
    assert calls[0].url.path == "/proxy/api/v2/app/version"
    assert calls[0].headers["Authorization"] == f"Bearer {key}"
    assert calls[0].headers["Referer"] == "http://qb:8080/"


def test_login_403_reports_temporary_ban():
    qb = QB(Connection(password="secret"))

    def handler(request):
        return httpx.Response(403)

    qb.http.close()
    qb.http = httpx.Client(base_url="http://qb/", transport=httpx.MockTransport(handler))
    with pytest.raises(QBError, match="暂时封禁"):
        with qb:
            pass


def test_only_reads_are_retried():
    qb = QB(Connection())
    calls = []

    def handler(request):
        calls.append(request)
        raise httpx.ReadTimeout("secret-response")

    qb.http.close()
    qb.http = httpx.Client(base_url="http://qb/", transport=httpx.MockTransport(handler))
    with pytest.raises(QBError):
        qb.request("GET", "torrents/info")
    assert len(calls) == 2
    with pytest.raises(QBError):
        qb.request("POST", "torrents/delete")
    assert len(calls) == 3
    qb.http.close()


def test_prepare_magnet_hash():
    assert prepare_torrent("magnet:?xt=urn:btih:" + "b" * 40, 123)["hash"] == "b" * 40
    with pytest.raises(QBError):
        prepare_torrent("magnet:?xt=urn:btih:invalid", 123)


def test_safe_legacy_import(tmp_path):
    path = tmp_path / "config.py"
    path.write_text(
        "raise RuntimeError('must not execute')\nclass main_config:\n    max_num = 5\n    rule = re.compile('movie')\n    token = dangerous()\n",
        encoding="utf-8",
    )
    values, warnings = read_legacy(path)
    assert values == {"max_num": 5, "rule": "movie"}
    assert len(warnings) == 1
