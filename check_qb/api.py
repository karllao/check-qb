from contextlib import asynccontextmanager
import hashlib
import hmac
import secrets
import time
from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from filelock import FileLock, Timeout
from pydantic import BaseModel, Field, ValidationError

from .models import Settings
from .notifications import notify
from .planner import feeds, managed
from .qb import QBError
from .service import Busy, Service
from .storage import Store, verify_password

API = "/api/v1"


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def public_settings(settings: Settings):
    value = settings.model_dump()
    connection = value["connection"]
    for field in ("password", "api_key"):
        connection[field + "_configured"] = bool(connection.pop(field))
    notification = value["notifications"]
    for field in ("webhook_url", "webhook_headers", "webhook_body", "smtp_password"):
        notification[field + "_configured"] = bool(notification.pop(field))
    for task in value["attendance"]:
        for field in ("cookie", "headers", "body"):
            task[field + "_configured"] = bool(task.pop(field))
    return value


def merge_settings(old, update):
    """Omitted secrets are preserved; explicit empty values clear them."""
    result = old.model_dump()
    for section in ("connection", "rules", "schedule", "notifications"):
        if section in update:
            if not isinstance(update[section], dict):
                raise ValueError("配置分区必须是对象")
            result[section].update(update[section])
    if "attendance" in update:
        existing = {task["id"]: task for task in result["attendance"]}
        result["attendance"] = [existing.get(task.get("id"), {}) | task for task in update["attendance"]]
    if set(update) - set(result):
        raise ValueError("配置包含未知字段")
    return Settings.model_validate(result)


class Credentials(BaseModel):
    password: str = Field(min_length=10, max_length=200)
    setup_token: str = ""


class Adopt(BaseModel):
    hashes: list[str] = Field(min_length=1, max_length=1000)


class Acknowledge(BaseModel):
    key: str


class SettingsPatch(BaseModel):
    """Partial settings; omitted secrets retain their encrypted values. GET returns presence flags."""

    connection: dict | None = None
    rules: dict | None = None
    schedule: dict | None = None
    notifications: dict | None = None
    attendance: list[dict] | None = None
    model_config = {"extra": "forbid"}


def create_app(store: Store | None = None, service: Service | None = None, setup_token=None):
    store = store or Store()
    service = service or Service(store)
    scheduler = BackgroundScheduler()
    bootstrap = setup_token or secrets.token_urlsafe(24)

    def scheduled_run(task_id=None):
        try:
            service.run_attendance(task_id) if task_id else service.run()
        except Busy:
            detail = {"reason": "其他任务正在执行，本次调度已跳过"}
            run_id = store.start_run("attendance" if task_id else "torrents", detail)
            store.update_run(run_id, detail, "skipped")

    def reschedule():
        scheduler.remove_all_jobs()
        if not store.get("admin"):
            return
        settings = store.settings()
        schedule = settings.schedule
        if schedule.enabled:
            kwargs = {"id": "torrents", "max_instances": 1, "coalesce": True, "misfire_grace_time": 60}
            if schedule.mode == "cron":
                scheduler.add_job(
                    scheduled_run,
                    CronTrigger.from_crontab(schedule.cron, timezone=schedule.timezone),
                    **kwargs,
                )
            else:
                scheduler.add_job(scheduled_run, "interval", seconds=schedule.interval_seconds, **kwargs)
        for task in settings.attendance:
            if task.enabled:
                hour, minute = map(int, task.time.split(":"))
                scheduler.add_job(
                    scheduled_run,
                    "cron",
                    hour=hour,
                    minute=minute,
                    timezone=schedule.timezone,
                    args=[task.id],
                    id="attendance-" + task.id,
                    max_instances=1,
                    coalesce=True,
                    misfire_grace_time=60,
                )

    @asynccontextmanager
    async def lifespan(app):
        server_lock = FileLock(store.path / "server.lock", timeout=0)
        try:
            server_lock.acquire()
        except Timeout:
            raise RuntimeError("该数据目录已有 Web 服务，请只启动一个进程") from None
        try:
            try:
                with service.lock():
                    store.recover()
            except Timeout:
                pass
            if not store.get("admin"):
                try:
                    print(f"\n首次设置凭据（仅本次启动有效）：{bootstrap}\n", flush=True)
                except UnicodeEncodeError:
                    # Direct ASGI launches may use a legacy Windows stdout encoding.
                    print(f"\nSetup token (valid for this startup only): {bootstrap}\n", flush=True)
            reschedule()
            scheduler.start()
            yield
        finally:
            if scheduler.running:
                scheduler.shutdown(wait=True)
            server_lock.release()

    app = FastAPI(title="check-qb API", version="2.0.0", lifespan=lifespan)
    app.state.store = store
    app.state.service = service

    @app.exception_handler(QBError)
    async def qb_error(request, error):
        return JSONResponse({"detail": str(error)}, status_code=502)

    @app.exception_handler(Busy)
    @app.exception_handler(Timeout)
    async def busy_error(request, error):
        return JSONResponse({"detail": "已有任务正在执行，请稍后再试"}, status_code=409)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, error):
        return JSONResponse(
            {"detail": "请求格式或字段值无效", "fields": [list(e["loc"]) for e in error.errors()]},
            status_code=422,
        )

    @app.exception_handler(ValueError)
    async def value_error(request, error):
        return JSONResponse({"detail": "数据或匹配规则无效，请检查配置"}, status_code=422)

    @app.middleware("http")
    async def security_headers(request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        if request.url.path.startswith(API):
            response.headers["Cache-Control"] = "no-store"
        if not request.url.path.startswith(("/docs", "/redoc")):
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
            )
        return response

    def authenticated(request: Request):
        token = request.cookies.get("check_qb_session", "")
        with store.connect() as db:
            row = db.execute(
                "SELECT * FROM sessions WHERE token=? AND expires>?", (digest(token), time.time())
            ).fetchone()
        if not row:
            raise HTTPException(401, "请先登录")
        if request.method not in ("GET", "HEAD", "OPTIONS"):
            csrf = request.headers.get("X-CSRF-Token", "")
            if not hmac.compare_digest(row["csrf"], digest(csrf)):
                raise HTTPException(403, "页面凭据已失效，请刷新后重试")
        return row

    def rate_limit(request):
        host = request.client.host if request.client else "local"
        with store.connect() as db:
            db.execute("DELETE FROM attempts WHERE created < ?", (time.time() - 900,))
            count = db.execute("SELECT count(*) FROM attempts WHERE host=?", (host,)).fetchone()[0]
            if count >= 5:
                raise HTTPException(429, "尝试过于频繁，请 15 分钟后再试")
            db.execute("INSERT INTO attempts VALUES (?,?)", (host, time.time()))

    def issue_session(request, response):
        token = secrets.token_urlsafe(32)
        csrf = hmac.new(token.encode(), b"check-qb-csrf", hashlib.sha256).hexdigest()
        with store.connect() as db:
            db.execute(
                "INSERT INTO sessions VALUES (?,?,?)", (digest(token), digest(csrf), time.time() + 43200)
            )
        response.set_cookie(
            "check_qb_session",
            token,
            httponly=True,
            samesite="strict",
            max_age=43200,
            secure=request.url.scheme == "https",
            path="/",
        )
        return {"authenticated": True, "csrf": csrf}

    @app.get(API + "/auth/status")
    def auth_status(request: Request):
        try:
            authenticated(request)
            logged_in = True
        except HTTPException:
            logged_in = False
        return {"setup_required": not bool(store.get("admin")), "authenticated": logged_in}

    @app.post(API + "/auth/setup")
    def setup(body: Credentials, request: Request, response: Response):
        rate_limit(request)
        if not hmac.compare_digest(body.setup_token, bootstrap):
            raise HTTPException(403, "首次设置凭据无效，请查看服务启动终端")
        if not store.setup(body.password):
            raise HTTPException(409, "管理员已经创建，请登录")
        return issue_session(request, response)

    @app.post(API + "/auth/login")
    def login(body: Credentials, request: Request, response: Response):
        rate_limit(request)
        saved = store.get("admin")
        if not saved or not verify_password(body.password, saved):
            raise HTTPException(401, "密码错误")
        return issue_session(request, response)

    @app.get(API + "/auth/session", dependencies=[Depends(authenticated)])
    def session(request: Request):
        csrf = hmac.new(
            request.cookies["check_qb_session"].encode(), b"check-qb-csrf", hashlib.sha256
        ).hexdigest()
        return {"csrf": csrf}

    @app.post(API + "/auth/logout", dependencies=[Depends(authenticated)])
    def logout(request: Request, response: Response):
        with store.connect() as db:
            db.execute(
                "DELETE FROM sessions WHERE token=?", (digest(request.cookies.get("check_qb_session", "")),)
            )
        response.delete_cookie("check_qb_session", path="/")
        return {"ok": True}

    @app.get(API + "/settings", dependencies=[Depends(authenticated)])
    def settings_get():
        return public_settings(store.settings())

    @app.put(API + "/settings", dependencies=[Depends(authenticated)])
    def settings_put(body: SettingsPatch):
        try:
            with service.lock():
                settings = merge_settings(store.settings(), body.model_dump(exclude_none=True))
                store.save_settings(settings)
                reschedule()
                return public_settings(settings)
        except (ValidationError, ValueError, TypeError, AttributeError) as error:
            if isinstance(error, ValidationError):
                fields = [".".join(str(p) for p in e["loc"]) for e in error.errors()]
                raise HTTPException(422, "配置无效，请检查：" + ", ".join(fields or ["字段组合"])) from None
            raise HTTPException(422, "配置格式无效") from None

    @app.get(API + "/connection", dependencies=[Depends(authenticated)])
    def connection():
        snapshot = service.snapshot()
        return {
            "connected": True,
            "version": snapshot["version"],
            "api_version": snapshot["api_version"],
            "free_bytes": snapshot["free_bytes"],
            "save_path": snapshot["save_path"],
            "seed_time_supported": all("seeding_time" in t for t in snapshot["torrents"]),
            "tags_supported": all("tags" in t for t in snapshot["torrents"]),
        }

    @app.get(API + "/dashboard", dependencies=[Depends(authenticated)])
    def dashboard():
        result = {
            "schedule_enabled": store.settings().schedule.enabled,
            "jobs": [
                {"id": j.id, "next_run": j.next_run_time.isoformat() if j.next_run_time else None}
                for j in scheduler.get_jobs()
            ],
            "recent": store.history(5),
            "pending": [
                r
                for r in store.articles().values()
                if r["state"] in ("adding", "deleting", "deleted", "uncertain")
            ],
        }
        try:
            snapshot = service.snapshot()
            result.update(
                connected=True,
                version=snapshot["version"],
                free_bytes=snapshot["free_bytes"],
                managed_count=sum(managed(t) for t in snapshot["torrents"]),
                total_count=len(snapshot["torrents"]),
            )
        except QBError as error:
            result.update(connected=False, error=str(error))
        return result

    @app.get(API + "/rss", dependencies=[Depends(authenticated)])
    def rss():
        with service.client_factory(store.settings().connection) as qb:
            return [{"path": f["path"], "count": len(f["articles"])} for f in feeds(qb.rss())]

    @app.get(API + "/torrents", dependencies=[Depends(authenticated)])
    def torrents():
        with service.client_factory(store.settings().connection) as qb:
            return [
                {
                    k: t.get(k)
                    for k in (
                        "hash",
                        "name",
                        "size",
                        "total_size",
                        "progress",
                        "state",
                        "added_on",
                        "seeding_time",
                        "tags",
                    )
                }
                | {"managed": managed(t)}
                for t in qb.torrents()
            ]

    @app.post(API + "/torrents/adopt", dependencies=[Depends(authenticated)])
    def adopt(body: Adopt):
        with service.lock():
            with service.client_factory(store.settings().connection) as qb:
                current = {t["hash"] for t in qb.torrents()}
                if not set(body.hashes).issubset(current):
                    raise HTTPException(409, "部分种子已不存在，请刷新列表")
                qb.adopt(body.hashes)
                confirmed = {t["hash"] for t in qb.torrents() if managed(t)}
                if not set(body.hashes).issubset(confirmed):
                    raise QBError("未能确认所有标签已添加，请刷新列表核对")
        return {"ok": True}

    @app.get(API + "/runs/preview", dependencies=[Depends(authenticated)])
    def preview():
        return service.preview()

    @app.post(API + "/runs/execute", dependencies=[Depends(authenticated)])
    def execute():
        return service.run()

    @app.get(API + "/runs", dependencies=[Depends(authenticated)])
    def history(limit: int = 50, offset: int = 0):
        return store.history(max(1, min(limit, 100)), max(0, offset))

    @app.post(API + "/runs/acknowledge", dependencies=[Depends(authenticated)])
    def acknowledge(body: Acknowledge):
        with service.lock():
            record = store.articles().get(body.key)
            if not record or record["state"] not in ("adding", "deleting", "deleted", "uncertain"):
                raise HTTPException(404, "待核对记录不存在")
            with service.client_factory(store.settings().connection) as qb:
                service.reconcile(qb)
            record = store.articles()[body.key]
            if record["state"] != "added":
                store.article(body.key, record["hash"], "acknowledged")
            detail = {"key": body.key, "reason": "管理员已核对，此文章不会再次自动尝试"}
            run_id = store.start_run("review", detail)
            store.update_run(run_id, detail, "success")
        return {"ok": True}

    @app.post(API + "/attendance/{task_id}/run", dependencies=[Depends(authenticated)])
    def attendance_run(task_id: str):
        try:
            return service.run_attendance(task_id)
        except ValueError:
            raise HTTPException(404, "签到任务不存在") from None

    @app.post(API + "/notifications/test", dependencies=[Depends(authenticated)])
    def notification_test():
        with service.lock():
            result = notify(
                store.settings().notifications, "check-qb 测试通知", "通知渠道已连接。", force=True
            )
            run_id = store.start_run("notification", {"notifications": result})
            store.update_run(
                run_id,
                {"notifications": result},
                "failed" if any(r["status"] == "failed" for r in result) else "success",
            )
            return result

    @app.get("/healthz")
    def health():
        return {"status": "ok"}

    static = Path(__file__).parent / "static"
    if (static / "assets").exists():
        app.mount("/assets", StaticFiles(directory=static / "assets"), name="assets")

    @app.get("/")
    def index():
        if (static / "index.html").exists():
            return FileResponse(static / "index.html")
        return JSONResponse(
            {"detail": "前端尚未构建，请在 frontend 执行 npm ci && npm run build"}, status_code=503
        )

    return app
