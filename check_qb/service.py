import time

from filelock import FileLock, Timeout

from .attendance import attend
from .notifications import notify
from .planner import GIB, budget, eligible, managed, plan, public_plan
from .qb import QB, QBError, prepare_torrent
from .storage import Store


class Busy(RuntimeError):
    pass


class Service:
    def __init__(self, store: Store, client_factory=QB, prepare=prepare_torrent):
        self.store = store
        self.client_factory = client_factory
        self.prepare = prepare

    def lock(self):
        return FileLock(self.store.path / "execution.lock", timeout=0)

    def snapshot(self):
        with self.client_factory(self.store.settings().connection) as qb:
            return qb.snapshot()

    def preview(self):
        settings = self.store.settings()
        with self.client_factory(settings.connection) as qb:
            return public_plan(plan(qb.snapshot(), settings.rules, self.store.articles()))

    def reconcile(self, qb):
        current = {t["hash"].lower(): t for t in qb.torrents()}
        pending = []
        for key, record in self.store.articles().items():
            if record["state"] in ("adding", "deleting", "deleted", "uncertain"):
                found = current.get(record["hash"])
                if found and managed(found):
                    self.store.article(key, record["hash"], "added")
                else:
                    pending.append(key)
        return pending

    def run(self):
        try:
            with self.lock():
                return self._run()
        except Timeout:
            raise Busy("已有任务正在执行，请等待完成") from None

    def _run(self):
        self.store.recover()
        settings = self.store.settings()
        detail = {"actions": [], "notifications": []}
        run_id = self.store.start_run("torrents", detail)
        status = "success"
        try:
            with self.client_factory(settings.connection) as qb:
                pending = self.reconcile(qb)
                if pending:
                    raise QBError("存在上次执行结果不确定的操作；请在运行记录中核对并确认后继续")
                for path in settings.rules.feeds:
                    qb.refresh(path)
                # RSS refresh is asynchronous; allow a short settle period, next run catches late articles.
                if settings.rules.feeds:
                    time.sleep(1)
                initial = plan(qb.snapshot(), settings.rules, self.store.articles())
                detail["plan"] = public_plan(initial)
                self.store.update_run(run_id, detail)
                for item in initial["items"]:
                    if item["action"] == "skip":
                        continue
                    action = {
                        "key": item["key"],
                        "title": item["title"],
                        "action": item["action"],
                        "status": "checking",
                    }
                    detail["actions"].append(action)
                    self.store.update_run(run_id, detail)
                    changed = False
                    prepared = None
                    try:
                        prepared = self.prepare(item["url"], item["size"])
                        if (
                            not settings.rules.min_gib * GIB
                            <= prepared["size"]
                            <= settings.rules.max_gib * GIB
                        ):
                            action.update(status="skipped", reason="元数据实际大小超出范围")
                            continue
                        fresh = qb.snapshot()
                        if any("tags" not in t for t in fresh["torrents"]):
                            raise QBError("客户端未提供标签字段，请升级 qBittorrent 后再启用自动管理")
                        if any(t["hash"].lower() == prepared["hash"] for t in fresh["torrents"]):
                            self.store.article(item["key"], prepared["hash"], "existing")
                            action.update(status="skipped", reason="相同哈希种子已经存在，未自动接管")
                            continue
                        count = sum(managed(t) for t in fresh["torrents"])
                        available, reason = budget(fresh, settings.rules.reserve_gib)
                        if reason:
                            action.update(status="skipped", reason=reason)
                            continue
                        if item["action"] == "replace":
                            old = next(
                                (t for t in fresh["torrents"] if t["hash"] == item["delete"]["hash"]), None
                            )
                            if count < settings.rules.max_count:
                                # A manual removal has opened a slot; never delete unnecessarily.
                                action["action"] = "add"
                            elif not old or not eligible(old, settings.rules):
                                action.update(status="skipped", reason="旧种状态发生变化，取消替换")
                                continue
                            else:
                                if (
                                    available + old.get("completed", 0) + old.get("amount_left", 0)
                                    < prepared["size"]
                                ):
                                    action.update(status="skipped", reason="元数据核验后预计空间不足，未删除")
                                    continue
                                action.update(status="deleting", deleted_hash=old["hash"])
                                self.store.article(item["key"], prepared["hash"], "deleting")
                                self.store.update_run(run_id, detail)
                                changed = True
                                try:
                                    qb.delete(old["hash"])
                                except QBError:
                                    if not qb.wait_hash(old["hash"], present=False):
                                        raise
                                if not qb.wait_hash(old["hash"], present=False):
                                    raise QBError("未能确认旧种删除结果，已停止本轮")
                                self.store.article(item["key"], prepared["hash"], "deleted")
                                action["status"] = "deleted"
                                self.store.update_run(run_id, detail)
                                for attempt in range(6):
                                    fresh = qb.snapshot()
                                    available, reason = budget(fresh, settings.rules.reserve_gib)
                                    if not reason and available >= prepared["size"]:
                                        break
                                    if attempt < 5:
                                        time.sleep(1)
                        fresh = qb.snapshot()
                        if any(t["hash"].lower() == prepared["hash"] for t in fresh["torrents"]):
                            # A concurrent external add must never cause an unrelated torrent to be adopted.
                            self.store.article(item["key"], prepared["hash"], "existing")
                            action.update(status="skipped", reason="执行前检测到相同哈希已存在，未重复添加")
                            if changed:
                                status = "partial"
                                break
                            continue
                        available, reason = budget(fresh, settings.rules.reserve_gib)
                        count = sum(managed(t) for t in fresh["torrents"])
                        if reason or available < prepared["size"] or count >= settings.rules.max_count:
                            message = reason or "重新核验后空间不足或数量已满"
                            if changed:
                                raise QBError(message + "；旧种已删除，本轮已停止")
                            action.update(status="skipped", reason=message)
                            continue
                        # Persist intent before the request, including the expected hash for crash recovery.
                        self.store.article(item["key"], prepared["hash"], "adding")
                        action["status"] = "adding"
                        self.store.update_run(run_id, detail)
                        changed = True
                        try:
                            qb.add(prepared, fresh["save_path"])
                        except QBError:
                            found = qb.wait_hash(prepared["hash"])
                            if not found or not managed(found):
                                raise
                        found = qb.wait_hash(prepared["hash"])
                        if not found or not managed(found):
                            raise QBError("新增种子或管理标签尚未核验成功，结果待确认")
                        self.store.article(item["key"], prepared["hash"], "added")
                        action.update(
                            status="success", hash=prepared["hash"], reason="已确认新增种子与管理标签"
                        )
                        try:
                            qb.mark(item["feed"], item["article_id"])
                        except QBError:
                            action["warning"] = "新增成功，但标记已读失败；本地去重已生效"
                    except QBError as error:
                        if changed and prepared:
                            self.store.article(item["key"], prepared["hash"], "uncertain")
                        action.update(status="uncertain" if changed else "failed", reason=str(error))
                        status = (
                            "partial"
                            if changed or any(a["status"] == "success" for a in detail["actions"])
                            else "failed"
                        )
                        break
                    finally:
                        self.store.update_run(run_id, detail)
        except QBError as error:
            detail["error"] = str(error)
            status = "failed"
        except Exception:
            detail["error"] = "执行发生内部错误，未自动重试；请检查配置及运行记录"
            status = "partial" if detail["actions"] else "failed"
        detail["notifications"] = notify(
            settings.notifications,
            "check-qb 种子任务",
            f"执行结果：{status}，操作数：{len(detail['actions'])}",
            "summary" if status == "success" else "failure",
        )
        self.store.update_run(run_id, detail, status)
        return {"id": run_id, "status": status, "detail": detail}

    def run_attendance(self, task_id):
        try:
            with self.lock():
                self.store.recover()
                settings = self.store.settings()
                task = next((t for t in settings.attendance if t.id == task_id), None)
                if not task:
                    raise ValueError("签到任务不存在")
                run_id = self.store.start_run("attendance", {"name": task.name})
                try:
                    result = attend(task)
                except Exception:
                    result = {"status": "unknown", "reason": "签到执行失败，未自动重试"}
                event = (
                    "expired"
                    if result["status"] == "expired"
                    else ("summary" if result["status"] in ("success", "already") else "failure")
                )
                detail = {
                    "name": task.name,
                    **result,
                    "notifications": notify(
                        settings.notifications, f"签到：{task.name}", result["reason"], event
                    ),
                }
                self.store.update_run(run_id, detail, result["status"])
                return {"id": run_id, **detail}
        except Timeout:
            raise Busy("已有任务正在执行，签到未执行，请稍后再试") from None
