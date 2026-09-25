import httpx
import pytest

from check_qb.attendance import attend, classify
from check_qb.models import Attendance, Match
from check_qb.matching import search


@pytest.fixture
def task():
    return Attendance(
        name="站点",
        url="https://site.invalid",
        success=Match(text="签到成功"),
        already=Match(text="已经签到"),
        expired=Match(text="请登录"),
    )


@pytest.mark.parametrize(
    "code,text,status",
    [
        (200, "签到成功", "success"),
        (200, "已经签到", "already"),
        (200, "请登录 签到成功", "expired"),
        (200, "home", "unknown"),
        (302, "签到成功", "failed"),
        (403, "", "expired"),
        (500, "签到成功", "failed"),
    ],
)
def test_result_classification(task, code, text, status):
    assert classify(task, code, text)["status"] == status


def test_timeout_no_retry(task, monkeypatch):
    calls = []

    def timeout(*args, **kwargs):
        calls.append(kwargs)
        raise httpx.ReadTimeout("contains secret")

    monkeypatch.setattr("check_qb.attendance.httpx.stream", timeout)
    result = attend(task)
    assert result["status"] == "unknown"
    assert "secret" not in str(result)
    assert len(calls) == 1
    assert calls[0]["follow_redirects"] is False


def test_regex_timeout_is_bounded():
    with pytest.raises(ValueError):
        search("(a+)+$", "a" * 100000 + "!")
