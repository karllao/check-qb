import pytest

from check_qb.storage import Store
from check_qb.service import Service
from .fakes import FakeQB, prepare


@pytest.fixture
def store(tmp_path):
    result = Store(tmp_path)
    settings = result.settings()
    settings.rules.feeds = ["订阅"]
    result.save_settings(settings)
    return result


@pytest.fixture
def fake():
    return FakeQB()


@pytest.fixture
def service(store, fake, monkeypatch):
    monkeypatch.setattr("check_qb.service.time.sleep", lambda _: None)
    return Service(store, lambda _: fake, prepare)
