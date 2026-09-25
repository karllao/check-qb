"""Isolated UI test server. No real qBittorrent, tracker, email or notification requests."""

import tempfile
from pathlib import Path

import uvicorn

from check_qb.api import create_app
from check_qb.service import Service
from check_qb.storage import Store
from tests.fakes import FakeQB, prepare, torrent


def main():
    with tempfile.TemporaryDirectory(prefix="check-qb-ui-") as directory:
        store = Store(Path(directory))
        settings = store.settings()
        settings.rules.feeds = ["订阅"]
        store.save_settings(settings)
        fake = FakeQB(torrents=[torrent(tags="personal", name="示例纪录片 [2 GiB]")])
        service = Service(store, lambda _: fake, prepare)
        app = create_app(store, service, setup_token="ui-test-setup")
        uvicorn.run(app, host="127.0.0.1", port=8877, access_log=False)


if __name__ == "__main__":
    main()
