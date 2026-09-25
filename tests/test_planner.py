import pytest

from check_qb.models import Rules
from check_qb.planner import GIB, article_key, budget, eligible, feeds, parse_size, plan, public_plan
from .fakes import FakeQB, article, torrent


@pytest.mark.parametrize(
    "text, expected",
    [
        ("Movie [2 GiB]", 2 * GIB),
        ("[1.5 GB]", 1500000000),
        ("x 512MiB", 512 * 1024**2),
        ("[1 TB]", 10**12),
        ("[1 KiB]", 1024),
        ("no size", None),
    ],
)
def test_size(text, expected):
    assert parse_size(text) == expected


def test_nested_feeds_and_unread_false():
    data = FakeQB(articles=[article(), article(id="2", isRead=True)]).snapshot()
    result = plan(data, Rules(feeds=["订阅"]))
    assert [i["action"] for i in result["items"]] == ["add", "skip"]
    assert feeds(data["rss"])[0]["path"] == "订阅\\站点"
    assert "url" not in public_plan(result)["items"][0]


def test_dedupe_and_capacity():
    data = FakeQB(articles=[article(), article(id="2")]).snapshot()
    result = plan(data, Rules(feeds=["订阅"], max_count=1))
    assert [i["action"] for i in result["items"]] == ["add", "skip"]
    seen = {article_key("订阅\\站点", article()): {"state": "adding"}}
    assert plan(data, Rules(feeds=["订阅"]), seen)["items"][0]["action"] == "skip"


def test_replacement_only_managed_and_seeded():
    rules = Rules(feeds=["订阅"], max_count=1)
    assert eligible(torrent(), rules)
    assert not eligible(torrent(tags="manual"), rules)
    assert not eligible(torrent(progress=0.99), rules)
    assert not eligible(torrent(seeding_time=1), rules)
    assert eligible(torrent(progress=0.5), Rules(replacement="added_time"), now=100000)
    data = FakeQB(torrents=[torrent(tags="manual")]).snapshot()
    assert plan(data, rules)["items"][0]["action"] == "add"
    data["torrents"].append(torrent())
    assert plan(data, rules)["items"][0]["action"] == "replace"


def test_disk_budget_accounts_for_unmanaged_downloads():
    data = FakeQB(torrents=[torrent(tags="manual", progress=0.1, amount_left=14 * GIB)]).snapshot()
    assert budget(data, 5)[0] == GIB
    assert plan(data, Rules(feeds=["订阅"]))["items"][0]["action"] == "skip"
    data["torrents"][0]["save_path"] = "/other-mount"
    assert budget(data, 5)[0] is None
    data["free_bytes"] = -1
    assert budget(data, 5)[0] is None


def test_above_capacity_never_deletes():
    data = FakeQB(torrents=[torrent(), torrent(hash="c" * 40)]).snapshot()
    assert plan(data, Rules(feeds=["订阅"], max_count=1))["items"][0]["action"] == "skip"


def test_oldest_eligible_first_and_missing_size():
    data = FakeQB(torrents=[torrent(hash="c" * 40, added_on=2), torrent(added_on=1)]).snapshot()
    assert plan(data, Rules(feeds=["订阅"], max_count=2))["items"][0]["delete"]["hash"] == "a" * 40
    data = FakeQB(articles=[article(title="unknown")]).snapshot()
    assert plan(data, Rules(feeds=["订阅"]))["items"][0]["reason"] == "标题缺少可识别大小"
