from copy import deepcopy

from check_qb.planner import GIB
from check_qb.qb import QBError

OLD_HASH = "a" * 40
NEW_HASH = "b" * 40


def torrent(**changes):
    return (
        dict(
            hash=OLD_HASH,
            name="旧种 [2 GiB]",
            tags="check-qb",
            added_on=1,
            seeding_time=50000,
            progress=1,
            save_path="/downloads",
            amount_left=0,
            completed=2 * GIB,
            total_size=2 * GIB,
            size=2 * GIB,
            state="uploading",
        )
        | changes
    )


def article(**changes):
    return (
        dict(
            id="article-1",
            title="新种 [2 GiB]",
            torrentURL="https://tracker.invalid/download/1",
            isRead=False,
        )
        | changes
    )


class FakeQB:
    def __init__(self, torrents=None, articles=None):
        self.data = {
            "torrents": torrents if torrents is not None else [],
            "rss": {
                "订阅": {
                    "站点": {
                        "url": "https://tracker.invalid/rss",
                        "articles": articles if articles is not None else [article()],
                    }
                }
            },
            "save_path": "/downloads",
            "free_bytes": 20 * GIB,
            "version": "v5.1.0",
            "api_version": "2.11.0",
        }
        self.calls = []
        self.add_error = False
        self.delete_error = False
        self.delete_timeout_after = False
        self.add_timeout_after = False
        self.release_disk = True

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def torrents(self):
        return deepcopy(self.data["torrents"])

    def snapshot(self):
        self.calls.append("read")
        return deepcopy(self.data)

    def rss(self):
        return deepcopy(self.data["rss"])

    def refresh(self, path):
        self.calls.append("refresh")

    def mark(self, path, article_id):
        self.calls.append(("mark", path, article_id))

    def adopt(self, hashes):
        self.calls.append(("adopt", hashes))
        for item in self.data["torrents"]:
            if item["hash"] in hashes:
                item["tags"] += ", check-qb"

    def delete(self, torrent_hash):
        self.calls.append(("delete", torrent_hash))
        if self.delete_error:
            raise QBError("删除请求失败")
        if self.release_disk:
            self.data["free_bytes"] += next(
                t["completed"] for t in self.data["torrents"] if t["hash"] == torrent_hash
            )
        self.data["torrents"] = [t for t in self.data["torrents"] if t["hash"] != torrent_hash]
        if self.delete_timeout_after:
            raise QBError("删除响应超时")

    def add(self, prepared, save_path):
        self.calls.append(("add", prepared["hash"]))
        if self.add_error:
            raise QBError("新增请求失败")
        self.data["torrents"].append(
            torrent(
                hash=prepared["hash"],
                name="新种 [2 GiB]",
                progress=0,
                amount_left=prepared["size"],
                completed=0,
            )
        )
        if self.add_timeout_after:
            raise QBError("新增响应超时")

    def wait_hash(self, torrent_hash, present=True):
        found = next((t for t in self.torrents() if t["hash"] == torrent_hash), None)
        return found if present else not bool(found)


def prepare(url, size):
    return {"hash": NEW_HASH, "size": size, "url": url}
