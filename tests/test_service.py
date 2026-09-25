import pytest

from check_qb.planner import GIB
from check_qb.qb import QBError
from check_qb.service import Busy
from .fakes import NEW_HASH, OLD_HASH, torrent


def test_preview_has_no_mutation(service, fake, store):
    assert service.preview()["items"][0]["action"] == "add"
    assert fake.calls == ["read"]
    assert store.articles() == {}
    assert store.history() == []


def test_add_verify_then_mark(service, fake, store):
    result = service.run()
    assert result["status"] == "success"
    assert fake.calls.index(("add", NEW_HASH)) < fake.calls.index(("mark", "订阅\\站点", "article-1"))
    assert list(store.articles().values())[0]["state"] == "added"
    service.run()
    assert sum(c == ("add", NEW_HASH) for c in fake.calls) == 1


def replacement(store, fake):
    settings = store.settings()
    settings.rules.max_count = 1
    store.save_settings(settings)
    fake.data["torrents"] = [torrent()]


def test_replacement_failure_stops_and_persists(service, fake, store):
    replacement(store, fake)
    fake.add_error = True
    result = service.run()
    assert result["status"] == "partial"
    assert ("delete", OLD_HASH) in fake.calls
    assert not any(isinstance(c, tuple) and c[0] == "mark" for c in fake.calls)
    assert list(store.articles().values())[0]["state"] == "uncertain"
    service.run()
    assert sum(c == ("delete", OLD_HASH) for c in fake.calls) == 1


def test_delete_failure_never_adds(service, fake, store):
    replacement(store, fake)
    fake.delete_error = True
    assert service.run()["status"] == "partial"
    assert ("add", NEW_HASH) not in fake.calls
    assert fake.data["torrents"][0]["hash"] == OLD_HASH


@pytest.mark.parametrize("attribute", ["add_timeout_after", "delete_timeout_after"])
def test_timeout_is_reconciled_without_repeating_writes(attribute, service, fake, store):
    replacement(store, fake)
    setattr(fake, attribute, True)
    assert service.run()["status"] == "success"
    assert sum(c == ("delete", OLD_HASH) for c in fake.calls) == 1
    assert sum(c == ("add", NEW_HASH) for c in fake.calls) == 1


def test_disk_must_actually_be_released(service, fake, store):
    replacement(store, fake)
    fake.data["free_bytes"] = 5 * GIB
    fake.release_disk = False
    assert service.run()["status"] == "partial"
    assert ("delete", OLD_HASH) in fake.calls
    assert ("add", NEW_HASH) not in fake.calls


def test_metadata_failure_before_delete(service, fake, store):
    replacement(store, fake)

    def broken(*args):
        raise QBError("无法读取元数据")

    service.prepare = broken
    assert service.run()["status"] == "failed"
    assert ("delete", OLD_HASH) not in fake.calls


def test_recover_crash_with_existing_target(service, fake, store):
    store.article("pending", NEW_HASH, "adding")
    fake.data["torrents"] = [torrent(hash=NEW_HASH)]
    run_id = store.start_run("torrents", {"actions": []})
    assert service.run()["status"] == "success"
    assert store.articles()["pending"]["state"] == "added"
    assert next(r for r in store.history() if r["id"] == run_id)["status"] == "interrupted"


def test_lock_blocks_overlapping_manual_and_scheduled_runs(service):
    with service.lock():
        with pytest.raises(Busy):
            service.run()


def test_notification_failure_does_not_change_run_success(service, monkeypatch):
    monkeypatch.setattr("check_qb.service.notify", lambda *args: [{"channel": "SMTP", "status": "failed"}])
    result = service.run()
    assert result["status"] == "success"
    assert result["detail"]["notifications"][0]["status"] == "failed"
