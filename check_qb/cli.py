import argparse
import ast
import json
import sys
from pathlib import Path

import uvicorn
from filelock import FileLock, Timeout

from .api import create_app
from .models import Settings
from .service import Busy, Service
from .storage import Store


def read_legacy(path):
    """Read literals and re.compile(literal), never execute the old module."""
    tree = ast.parse(Path(path).read_text(encoding="utf-8-sig"))
    result, warnings = {}, []
    found = False
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == "main_config":
            found = True
            for entry in node.body:
                if (
                    not isinstance(entry, ast.Assign)
                    or len(entry.targets) != 1
                    or not isinstance(entry.targets[0], ast.Name)
                ):
                    continue
                name, value = entry.targets[0].id, entry.value
                try:
                    if isinstance(value, ast.Call):
                        if not (
                            isinstance(value.func, ast.Attribute)
                            and isinstance(value.func.value, ast.Name)
                            and value.func.value.id == "re"
                            and value.func.attr == "compile"
                            and len(value.args) == 1
                            and not value.keywords
                        ):
                            raise ValueError()
                        value = value.args[0]
                    result[name] = ast.literal_eval(value)
                except (ValueError, TypeError):
                    warnings.append(f"{name} 不是可安全导入的字面量，请手动填写")
    if not found:
        raise ValueError("未找到 main_config 配置类")
    return result, warnings


def main(argv=None):
    # Keep redirected JSON/help readable on Windows as well as Unix terminals.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure") and not stream.isatty():
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(prog="check-qb", description="qBittorrent 自动化管理面板")
    parser.add_argument("--data-dir", type=Path, help="配置、密钥和历史的存储目录")
    commands = parser.add_subparsers(dest="command", required=True)
    serve = commands.add_parser("serve", help="启动 Web 面板")
    serve.add_argument("--host", default="127.0.0.1", help="局域网访问请设置 0.0.0.0")
    serve.add_argument("--port", type=int, default=8765)
    run = commands.add_parser("run", help="执行一轮种子任务")
    run.add_argument("--dry-run", action="store_true", help="只预览，不修改远端状态")
    legacy = commands.add_parser("import-legacy", help="安全导入旧 config.py，不执行其中代码")
    legacy.add_argument("path", type=Path)
    args = parser.parse_args(argv)
    store = Store(args.data_dir)
    service = Service(store)
    try:
        if args.command == "serve":
            uvicorn.run(
                create_app(store), host=args.host, port=args.port, proxy_headers=False, access_log=False
            )
        elif args.command == "run":
            result = service.preview() if args.dry_run else service.run()
            print(json.dumps(result, ensure_ascii=False, indent=2))
            if result.get("status") in ("failed", "partial"):
                return 1
        elif args.command == "import-legacy":
            with service.lock(), FileLock(store.path / "server.lock", timeout=0):
                old, warnings = read_legacy(args.path)
                settings = store.settings()
                data = settings.model_dump()
                data["connection"].update(
                    url=old.get("main_url", settings.connection.url),
                    username=old.get("param", {}).get("username", "admin"),
                    password=old.get("param", {}).get("password", ""),
                )
                data["rules"].update(
                    max_count=old.get("max_num", 5),
                    age_hours=old.get("max_addtime", 43200) / 3600,
                    feeds=[old["rss_item"]] if old.get("rss_item") else [],
                    title_pattern=old.get("rule", ""),
                    replacement="added_time",
                )
                data["notifications"]["webhook_enabled"] = False
                data["notifications"]["smtp_enabled"] = False
                data["schedule"]["enabled"] = False
                store.save_settings(Settings.model_validate(data))
                print("配置已导入；调度和通知未启用。请在面板核对大小范围和管理标签。")
                for warning in warnings:
                    print(warning)
    except (Busy, Timeout):
        print("已有服务或任务正在使用数据目录，请稍后再试。", file=sys.stderr)
        return 1
    except Exception:
        print("操作失败，请检查配置、连接及数据目录权限。凭据和原始响应未输出。", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
