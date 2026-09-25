"""Bounded, authenticated qBittorrent Web API access."""

from contextlib import AbstractContextManager
import hashlib
import base64
import time
from urllib.parse import parse_qs, urlsplit

import bencodepy
import httpx

from .models import Connection


class QBError(RuntimeError):
    """Messages contain no response bodies, credentials or download URLs."""


class QB(AbstractContextManager):
    def __init__(self, settings: Connection):
        self.settings = settings
        parsed = urlsplit(settings.url)
        origin = f"{parsed.scheme}://{parsed.netloc}"
        headers = {"Referer": origin + "/"}
        if settings.api_key:
            headers["Authorization"] = "Bearer " + settings.api_key
        self.http = httpx.Client(
            base_url=settings.url.rstrip("/") + "/",
            timeout=settings.timeout,
            follow_redirects=False,
            headers=headers,
        )

    def __enter__(self):
        try:
            if self.settings.api_key:
                try:
                    self.request("GET", "app/version")
                except QBError as error:
                    if "认证失败" in str(error):
                        raise QBError("qBittorrent API Key 无效或已失效") from None
                    raise
                return self
            response = self.request(
                "POST",
                "auth/login",
                data={"username": self.settings.username, "password": self.settings.password},
            )
            if response.text.strip() != "Ok.":
                raise QBError(
                    "qBittorrent 登录失败，请检查账号密码；若使用 5.2+ API Key，请填写 API Key 字段"
                )
            return self
        except Exception:
            self.http.close()
            raise

    def __exit__(self, *args):
        self.http.close()

    def request(self, method, endpoint, **kwargs):
        for attempt in range(2 if method == "GET" else 1):
            try:
                response = self.http.request(method, "api/v2/" + endpoint, **kwargs)
                if response.status_code in (401, 403):
                    if endpoint == "auth/login" and response.status_code == 403:
                        raise QBError("qBittorrent 已因登录失败次数过多暂时封禁此客户端 IP")
                    raise QBError("qBittorrent 认证失败或会话已失效")
                if response.status_code == 404:
                    raise QBError(f"当前 qBittorrent 不支持所需接口：{endpoint}")
                response.raise_for_status()
                return response
            except (httpx.TimeoutException, httpx.NetworkError):
                if method == "GET" and attempt == 0:
                    continue
                raise QBError("qBittorrent 请求超时或连接失败，操作结果需要核对") from None
            except httpx.HTTPStatusError as error:
                raise QBError(f"qBittorrent 接口 {endpoint} 返回 HTTP {error.response.status_code}") from None

    def json(self, endpoint, expected, **kwargs):
        try:
            value = self.request("GET", endpoint, **kwargs).json()
            if not isinstance(value, expected):
                raise ValueError()
            return value
        except (ValueError, TypeError):
            raise QBError(f"qBittorrent 接口 {endpoint} 返回了无效数据") from None

    def torrents(self):
        return self.json("torrents/info", list)

    def rss(self):
        return self.json("rss/items", dict, params={"withData": "true"})

    def snapshot(self):
        preferences = self.json("app/preferences", dict)
        transfer = self.json("sync/maindata", dict).get("server_state", {})
        torrent_list = self.torrents()
        if any(not isinstance(t, dict) or not isinstance(t.get("hash"), str) for t in torrent_list):
            raise QBError("种子列表缺少有效哈希，无法安全执行")
        return {
            "torrents": torrent_list,
            "rss": self.rss(),
            "save_path": preferences.get("save_path", ""),
            "free_bytes": transfer.get("free_space_on_disk"),
            "version": self.request("GET", "app/version").text.strip(),
            "api_version": self.request("GET", "app/webapiVersion").text.strip(),
        }

    def refresh(self, path):
        self.request("POST", "rss/refreshItem", data={"itemPath": path})

    def mark(self, path, article_id):
        if not article_id:
            return
        self.request("POST", "rss/markAsRead", data={"itemPath": path, "articleId": article_id})

    def adopt(self, hashes):
        self.request("POST", "torrents/addTags", data={"hashes": "|".join(hashes), "tags": "check-qb"})

    def delete(self, torrent_hash):
        self.request("POST", "torrents/delete", data={"hashes": torrent_hash, "deleteFiles": "true"})

    def add(self, prepared, save_path):
        data = {"tags": "check-qb", "savepath": save_path, "autoTMM": "false"}
        if prepared.get("content"):
            response = self.request(
                "POST",
                "torrents/add",
                data=data,
                files={"torrents": ("download.torrent", prepared["content"], "application/x-bittorrent")},
            )
        else:
            response = self.request("POST", "torrents/add", data=data | {"urls": prepared["url"]})
        if response.text.strip() != "Ok.":
            raise QBError("qBittorrent 未确认接受新增种子")

    def wait_hash(self, torrent_hash, present=True):
        for attempt in range(6):
            found = next((t for t in self.torrents() if t.get("hash", "").lower() == torrent_hash), None)
            if bool(found) == present:
                return found if present else True
            if attempt < 5:
                time.sleep(1)
        return None


def prepare_torrent(url: str, declared_size: int):
    """Resolve identity before destructive actions. Only v1/hybrid metadata is accepted."""
    parsed = urlsplit(url)
    if parsed.scheme == "magnet":
        hashes = parse_qs(parsed.query).get("xt", [])
        raw_hash = next((h[9:] for h in hashes if h.startswith("urn:btih:")), "")
        try:
            if len(raw_hash) == 32:
                raw_hash = base64.b32decode(raw_hash.upper()).hex()
            if len(raw_hash) != 40 or len(bytes.fromhex(raw_hash)) != 20:
                raise ValueError()
        except (ValueError, base64.binascii.Error):
            raise QBError("磁力链接缺少可核验的 v1 哈希") from None
        return {"hash": raw_hash.lower(), "size": declared_size, "url": url}
    if parsed.scheme not in ("http", "https"):
        raise QBError("下载地址必须为 HTTP、HTTPS 或带 v1 哈希的磁力链接")
    try:
        # Never reuse the authenticated qBittorrent session for tracker URLs.
        with httpx.stream("GET", url, timeout=20, follow_redirects=True) as response:
            response.raise_for_status()
            content = bytearray()
            for chunk in response.iter_bytes():
                content.extend(chunk)
                if len(content) > 8 * 1024 * 1024:
                    raise QBError("种子元数据超过 8 MiB 限制")
        metadata = bencodepy.decode(bytes(content))
        info = metadata[b"info"]
        if b"pieces" not in info:
            raise QBError("当前仅支持能核验 v1 哈希的种子（含混合种子）")
        size = sum(f[b"length"] for f in info[b"files"]) if b"files" in info else info[b"length"]
        if not isinstance(size, int) or size <= 0:
            raise ValueError()
        torrent_hash = hashlib.sha1(bencodepy.encode(info)).hexdigest()
        return {"hash": torrent_hash, "size": size, "content": bytes(content)}
    except QBError:
        raise
    except Exception:
        raise QBError("无法获取或解析种子元数据，本项未执行") from None
