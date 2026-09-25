import hashlib
import json
import os
from pathlib import Path
import secrets
import sqlite3
import time
from contextlib import contextmanager

from cryptography.fernet import Fernet, InvalidToken
from platformdirs import user_data_path

from .models import Settings


def data_directory() -> Path:
    return Path(os.environ.get("CHECK_QB_DATA_DIR", str(user_data_path("check-qb", appauthor=False))))


def password_hash(password: str, salt: str | None = None) -> str:
    salt = salt or secrets.token_hex(16)
    derived = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1).hex()
    return f"{salt}:{derived}"


def verify_password(password: str, saved: str) -> bool:
    return secrets.compare_digest(password_hash(password, saved.split(":")[0]), saved)


class Store:
    def __init__(self, path: Path | None = None):
        self.path = path or data_directory()
        self.path.mkdir(parents=True, exist_ok=True, mode=0o700)
        key = os.environ.get("CHECK_QB_ENCRYPTION_KEY")
        keyfile = self.path / "secrets.key"
        if not key:
            if not keyfile.exists():
                try:
                    with keyfile.open("xb") as file:
                        file.write(Fernet.generate_key())
                    keyfile.chmod(0o600)
                except FileExistsError:
                    pass
            key = keyfile.read_bytes()
        self.cipher = Fernet(key)
        self.dbpath = self.path / "check-qb.sqlite3"
        with self.connect() as db:
            db.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS kv (key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS sessions (token TEXT PRIMARY KEY, csrf TEXT, expires REAL);
                CREATE TABLE IF NOT EXISTS runs (
                    id INTEGER PRIMARY KEY, kind TEXT, started REAL, finished REAL,
                    status TEXT, detail TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS articles (
                    key TEXT PRIMARY KEY, hash TEXT, state TEXT, updated REAL);
                CREATE TABLE IF NOT EXISTS attempts (host TEXT, created REAL);
            """)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.dbpath, timeout=10)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def seal(self, value) -> str:
        return self.cipher.encrypt(json.dumps(value, ensure_ascii=False).encode()).decode()

    def unseal(self, value: str):
        try:
            return json.loads(self.cipher.decrypt(value.encode()))
        except InvalidToken:
            raise RuntimeError("配置解密失败，请恢复与数据库匹配的密钥") from None

    def get(self, key, default=None):
        with self.connect() as db:
            row = db.execute("SELECT value FROM kv WHERE key=?", (key,)).fetchone()
        return self.unseal(row[0]) if row else default

    def put(self, key, value):
        with self.connect() as db:
            db.execute("INSERT OR REPLACE INTO kv VALUES (?,?)", (key, self.seal(value)))

    def setup(self, password: str) -> bool:
        with self.connect() as db:
            result = db.execute(
                "INSERT OR IGNORE INTO kv VALUES ('admin',?)", (self.seal(password_hash(password)),)
            )
            return bool(result.rowcount)

    def settings(self) -> Settings:
        data = self.get("settings", {})
        notification = data.get("notifications", {})
        # Retired provider fields must not prevent existing installations from starting.
        notification.pop("iyuu_enabled", None)
        notification.pop("iyuu_token", None)
        return Settings.model_validate(data)

    def save_settings(self, settings: Settings):
        self.put("settings", settings.model_dump())

    def start_run(self, kind: str, detail: dict) -> int:
        with self.connect() as db:
            row = db.execute(
                "INSERT INTO runs(kind,started,status,detail) VALUES (?,?,?,?)",
                (kind, time.time(), "running", self.seal(detail)),
            )
            return row.lastrowid

    def update_run(self, run_id: int, detail: dict, status: str | None = None):
        with self.connect() as db:
            if status:
                db.execute(
                    "UPDATE runs SET detail=?,status=?,finished=? WHERE id=?",
                    (self.seal(detail), status, time.time(), run_id),
                )
            else:
                db.execute("UPDATE runs SET detail=? WHERE id=?", (self.seal(detail), run_id))

    def history(self, limit=50, offset=0):
        with self.connect() as db:
            rows = db.execute(
                "SELECT * FROM runs ORDER BY id DESC LIMIT ? OFFSET ?", (limit, offset)
            ).fetchall()
        return [dict(row) | {"detail": self.unseal(row["detail"])} for row in rows]

    def article(self, key: str, torrent_hash: str, state: str):
        with self.connect() as db:
            db.execute(
                "INSERT OR REPLACE INTO articles VALUES (?,?,?,?)", (key, torrent_hash, state, time.time())
            )

    def articles(self):
        with self.connect() as db:
            return {row["key"]: dict(row) for row in db.execute("SELECT * FROM articles")}

    def recover(self):
        # The caller must hold the execution lock: no live run may be marked interrupted.
        with self.connect() as db:
            db.execute(
                "UPDATE runs SET status='interrupted',finished=? WHERE status='running'", (time.time(),)
            )
            db.execute("DELETE FROM runs WHERE finished < ?", (time.time() - 90 * 86400,))
            db.execute("DELETE FROM sessions WHERE expires < ?", (time.time(),))
            db.execute("DELETE FROM attempts WHERE created < ?", (time.time() - 900,))
