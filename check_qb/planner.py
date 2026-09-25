"""Pure planning: no network, writes, or changes to qBittorrent."""

import hashlib
import re
import time

from .models import Rules
from .matching import search

GIB = 1024**3
TAG = "check-qb"
SIZE = re.compile(r"(?<![\d.])(\d+(?:\.\d+)?)\s*(KiB|MiB|GiB|TiB|KB|MB|GB|TB|B)\b", re.I)


def parse_size(title: str):
    matches = list(SIZE.finditer(title))
    if not matches:
        return None
    match = matches[-1]
    unit = match[2].upper()
    power = {"B": 0, "KB": 1, "KIB": 1, "MB": 2, "MIB": 2, "GB": 3, "GIB": 3, "TB": 4, "TIB": 4}[unit]
    return int(float(match[1]) * (1024 if "I" in unit else 1000) ** power)


def managed(torrent):
    return TAG in [tag.strip() for tag in torrent.get("tags", "").split(",")]


def eligible(torrent, rules: Rules, now=None):
    if not managed(torrent):
        return False
    threshold = rules.age_hours * 3600
    if rules.replacement == "added_time":
        added = torrent.get("added_on", 0)
        return added > 0 and (now or time.time()) - added >= threshold
    return torrent.get("progress", 0) >= 1 and torrent.get("seeding_time", -1) >= threshold


def feeds(tree, prefix=""):
    result = []
    for name, node in tree.items():
        if not isinstance(node, dict):
            continue
        path = f"{prefix}\\{name}" if prefix else name
        if "articles" in node or "url" in node:
            result.append({"path": path, "articles": node.get("articles", [])})
        else:
            result.extend(feeds(node, path))
    return result


def article_key(path, article):
    identity = str(article.get("id") or article.get("torrentURL") or article.get("title", ""))
    return hashlib.sha256((path + "\0" + identity).encode()).hexdigest()


def normalized_path(path):
    value = path.replace("\\", "/").rstrip("/")
    return value.lower() if re.match(r"^[a-zA-Z]:", value) else value


def budget(snapshot, reserve):
    free = snapshot.get("free_bytes")
    path = snapshot.get("save_path")
    if not path or not isinstance(free, (int, float)) or free < 0:
        return None, "无法确定默认保存位置或剩余空间"
    remaining = 0
    for torrent in snapshot["torrents"]:
        # Different paths might be on the same remote disk; do not guess their mount relationship.
        if normalized_path(torrent.get("save_path", "")) != normalized_path(path):
            return None, "存在不同保存位置，无法可靠判断远端磁盘归属"
        left = torrent.get("amount_left")
        if not isinstance(left, (int, float)) or left < 0:
            return None, "无法确定未完成任务的预计磁盘占用"
        remaining += left
    return int(free - reserve * GIB - remaining), ""


def plan(snapshot, rules: Rules, seen=None, now=None):
    seen = seen or {}
    torrents = snapshot["torrents"]
    owned = [t for t in torrents if managed(t)]
    old = sorted([t for t in owned if eligible(t, rules, now)], key=lambda t: t["added_on"])
    slots = max(0, rules.max_count - len(owned))
    available, disk_reason = budget(snapshot, rules.reserve_gib)
    items = []
    urls = set()
    selected = rules.feeds
    for feed in feeds(snapshot["rss"]):
        if not any(feed["path"] == p or feed["path"].startswith(p + "\\") for p in selected):
            continue
        for article in feed["articles"]:
            title = str(article.get("title", "无标题"))
            key = article_key(feed["path"], article)
            url = article.get("torrentURL", "")
            size = parse_size(title)
            item = {
                "key": key,
                "title": title,
                "feed": feed["path"],
                "article_id": str(article.get("id", "")),
                "size": size,
                "action": "skip",
                "reason": "",
                "url": url,
            }
            reason = ""
            if article.get("isRead", False):
                reason = "文章已读"
            elif key in seen:
                reason = "已处理或上次结果待核对"
            elif not url:
                reason = "缺少下载地址"
            elif url in urls:
                reason = "本批下载地址重复"
            elif size is None:
                reason = "标题缺少可识别大小"
            elif not rules.min_gib * GIB <= size <= rules.max_gib * GIB:
                reason = "大小超出筛选范围"
            elif rules.title_pattern and not search(rules.title_pattern, title):
                reason = "不匹配标题规则"
            elif disk_reason:
                reason = disk_reason
            elif (
                rules.replacement == "seed_time"
                and slots == 0
                and any("seeding_time" not in t for t in owned)
            ):
                reason = "客户端未提供做种时长，请升级客户端或选择添加时间策略"
            elif len(owned) > rules.max_count:
                reason = "托管数量已超过上限，请先手动调整数量或提高上限"
            elif slots > 0:
                if available >= size:
                    item["action"] = "add"
                    slots -= 1
                    available -= size
                else:
                    reason = "剩余空间不足，已预留未完成任务占用"
            elif old:
                candidate = old[0]
                if normalized_path(candidate.get("save_path", "")) != normalized_path(snapshot["save_path"]):
                    reason = "旧种保存位置无法核验"
                elif available + candidate.get("completed", 0) + candidate.get("amount_left", 0) < size:
                    reason = "即使替换旧种，预计空间仍不足"
                else:
                    old.pop(0)
                    item["action"] = "replace"
                    item["delete"] = {"hash": candidate["hash"], "name": candidate["name"]}
                    # Estimate only for display; execution must measure actual free space after deletion.
                    available += candidate.get("completed", 0) + candidate.get("amount_left", 0) - size
            else:
                reason = "达到数量上限，暂无符合替换条件的托管种子"
            item["reason"] = reason or (
                "符合规则，执行前将重新核验"
                if item["action"] == "add"
                else "符合替换条件，删除后须重新核验空间"
            )
            items.append(item)
            urls.add(url)
    return {
        "managed_count": len(owned),
        "total_count": len(torrents),
        "free_bytes": snapshot.get("free_bytes"),
        "disk_warning": disk_reason,
        "items": items,
        "save_path": snapshot.get("save_path", ""),
    }


def public_plan(value):
    return value | {
        "items": [
            {k: v for k, v in item.items() if k not in ("url", "article_id")} for item in value["items"]
        ]
    }
