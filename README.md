# check-qb 2.0

为小磁盘设计的 qBittorrent 自动化 Web 面板。中文界面，支持 Windows / Linux，通过一个 Python 进程提供前端、API 和任务调度。

- 浏览器配置连接、RSS、大小范围、数量上限、磁盘预留和替换策略。
- 只管理带 `check-qb` 标签的种子；可手动选择现有种子接管。
- 预览每项接受/跳过原因，记录实际操作、部分失败和待核对状态。
- 可配置 HTTP 签到、通用 Webhook 和 SMTP 通知。
- 单管理员登录、服务端会话、CSRF 防护、加密配置和脱敏响应。

## 安装与启动

需要 Python 3.11+；从源码构建前端需要 Node.js 22。qBittorrent 必须启用 Web UI 和 RSS，建议使用仍受支持的 4.6+/5.x。旧版缺少标签或 `seeding_time` 字段时，相应自动管理功能不可用；面板连接测试会报告字段支持情况。

### Windows（PowerShell）

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock
.\.venv\Scripts\python.exe -m pip install -e . --no-deps
cd frontend
npm ci
npm run build
cd ..
.\.venv\Scripts\check-qb.exe serve
```

也可在安装、构建完成后双击 `start_check.bat`。

### Linux

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock
.venv/bin/python -m pip install -e . --no-deps
cd frontend
npm ci
npm run build
cd ..
.venv/bin/check-qb serve
```

日常启动可用 `sh start_check.sh`，无需启动 Node 服务。前端产物在 `check_qb/static/`，不提交 Git；构建 Python wheel 前先构建前端，静态文件会随 wheel 打包。`requirements.lock` 固定后端及测试依赖，前端由 `frontend/package-lock.json` 锁定。

打开 <http://127.0.0.1:8765>，复制启动终端中的一次性设置凭据，创建至少 10 个字符的管理员密码。服务重启会更换尚未使用的设置凭据，创建管理员后不能再次初始化。

局域网访问：

```sh
check-qb serve --host 0.0.0.0 --port 8765
```

在其他设备打开运行机器的 IP 和端口，按需开放系统防火墙。默认只监听本机；局域网 HTTP 适用于可信网络。此版本不提供公网部署配置，代理头默认不被信任。

## 第一次使用

1. 在“规则设置”填写 qBittorrent Web UI 地址和用户名、密码；qBittorrent 5.2+ 也可填写在 Web UI 设置中生成的 API Key，配置后会优先使用 API Key。**保存连接**后测试。
2. 读取已配置的 RSS 列表，选择一个或多个来源。文件夹路径也会包含其子订阅；路径使用反斜杠，例如 `订阅\站点`。
3. 设置大小、数量、磁盘预留和替换条件，保存规则。默认 1–6 GiB、5 个托管种子、预留 5 GiB、下载完成且累计做种 12 小时。
4. 在“种子管理”勾选希望交给工具管理的现有任务，确认接管。原分类和其他标签保留。
5. 在总览预览计划，检查原因；可手动执行一次，再开启定时检查。首次安装默认暂停，签到按每个任务自身的开关独立调度。

修改凭据时留空保留原值，“清除”会在保存后删除已存值。普通设置的刷新会重新载入服务器配置，放弃未保存编辑。

API Key 可在 qBittorrent 的“选项 → Web UI → API Key”中生成，格式为 `qbt_` 加 28 个字母或数字。项目会按[官方 API Key 认证说明](https://github.com/qbittorrent/qBittorrent/wiki/API-Key-Authentication-(%E2%89%A5v5.2.0))发送 `Authorization: Bearer <API_KEY>`，不会再把它提交到账号密码登录接口。

## 执行规则与空间保护

未满额时补充新种；满额且存在合适新种时，按添加时间从早到晚替换符合条件的托管种子。可选择：

- **完成下载且累计做种达标**：使用 qBittorrent 的 `progress` 和 `seeding_time`。
- **按添加时间**：到达阈值后可替换，包括尚未下载完成的任务。

替换会删除旧种和文件。只作用于 `check-qb` 标签；低于数量上限不会为腾空间额外清理任务。托管数已超过上限时暂停新增与替换，请手动调整数量或上限。

大小解析支持 B、KB/MB/GB/TB 和 KiB/MiB/GiB/TiB。前者按 1000、后者按 1024 换算。使用标题中最后一个容量值，无法识别则跳过；旧版正则把 GB 近似为 GiB 的行为不再延续。

磁盘检查使用 qBittorrent 默认保存位置的剩余空间，扣除最小保留空间、全部任务未完成字节数，以及本批新增需求。未完成字节数保守视为额外占用，预分配文件可能导致保守跳过。新种强制使用默认保存路径并关闭自动分类路径管理。存在其他保存路径时，无法知道远端挂载关系，因此暂停新增；本版本没有逐磁盘路径映射。

HTTP 下载地址会在删除旧种前获取至多 8 MiB 的种子元数据，核验 v1 哈希和真实声明大小；仅支持 v1/混合种子。磁力链接须有 v1 哈希，大小使用 RSS 声明估算，实际内容仍以客户端为准。元数据获取使用独立连接，不会把 qBittorrent 密码或 Cookie 发送给站点。

预览只读取当前 RSS 缓存，不刷新订阅、标记已读或修改种子。执行会刷新 RSS；刷新是异步的，尚未完成刷新的条目留待下轮。执行前重新检查状态，删除后实际确认空间释放才新增。

每次操作先持久化意图，再请求远端。只有核验新增哈希与标签成功的文章才标记已读，其余文章保留。删除成功但新增失败属于**部分完成**，不会回滚已删除文件；任务停止并保留待核对记录。请求超时不盲目重发写操作，先核对远端。重启后自动核对已存在的新种，其余不确定状态阻止继续运行。人工核对前往总览，结合运行记录检查 qBittorrent，再点击“已核对，继续”；该文章之后不会自动重试。

单个数据目录只运行一个 Web 进程。手动、定时、命令行操作共享文件锁；若签到与其他任务重叠，该次调度记为跳过，可稍后手动执行。Cron 使用五字段，**星期一是 0、星期日是 6**，时区默认 `Asia/Tokyo`；系统时区不会覆盖已存设置。

## 通用签到与通知

在“签到任务”创建任务，填写名称、URL、GET/POST、Cookie、可选请求头（JSON）、POST 原始请求体和每日时间。表单 POST 通常填写 `Content-Type: application/x-www-form-urlencoded`，请求体为 `key=value`。

配置成功、已签到和凭据失效标志，可选文本或正则。失效标志优先，HTTP 200 本身不等于成功；不跟随重定向，不自动重试超时或未知结果。至少填写成功/已签到之一才能启用调度。验证码、动态 CSRF、浏览器挑战或多步登录流程不属于通用请求支持范围。

Webhook 与 SMTP 默认关闭。在“通知渠道”启用 Webhook，填写 HTTP/HTTPS URL、请求方法（GET / POST / PUT / PATCH / DELETE）、可选请求头（JSON 对象）和超时（2–120 秒）。请求头可配置 `Authorization` 等鉴权字段。

请求体支持 JSON、表单（URL 编码）和原始文本。JSON 支持嵌套对象和数组；表单模板使用值为字符串的 JSON 对象，发送时自动做表单编码。例如：

```json
{"msgtype":"text","text":{"content":"{{title}}\n{{message}}"}}
```

URL 路径、查询参数和请求体中的 `{{title}}`、`{{message}}`、`{{event}}` 分别替换为标题、消息和事件类型（`summary` / `failure` / `expired`）。URL 变量自动百分号编码；JSON 在解析后替换字符串值，避免消息中的引号、换行破坏结构。请求头不替换变量。GET 只发送 URL 和请求头，不发送请求体，例如 `https://example.com/notify?text={{message}}`。无自定义模板时，JSON／表单默认发送 `title`、`message`、`event` 三个字段，文本默认发送消息；文本可用自定义 `Content-Type` 发送其他格式。

Webhook URL、请求头、请求体加密保存，API 不回显；留空保留已存值，URL 点击“清除”、请求头填写 `{}`、请求体点击“恢复默认请求体”后保存才会清除。HTTP 2xx 视为发送成功，不解析服务商的业务状态码；不跟随重定向、不自动重试。

SMTP 支持 SSL 和 STARTTLS；两个渠道共用摘要、失败、凭据失效事件筛选。发送测试只针对已保存并启用的渠道，并忽略事件筛选。通知失败独立记录，不把已经成功的种子操作改为失败。响应正文、完整下载链接和请求凭据不写入历史。

旧 IYUU 专用配置在读取时忽略，后续保存配置时移除；不会自动转换或发送通知，请在 Webhook 中重新配置。旧版配置导入也不再导入通知 Token。

## 命令行与迁移

```sh
check-qb run --dry-run
check-qb run
check-qb import-legacy /path/to/legacy-config.py
check-qb --data-dir /path/to/data serve
```

`run` 始终只执行一轮，自动调度只在 Web 服务中运行。不要同时保留旧系统 Cron/任务计划与面板调度，以免多余运行；执行锁只阻止重叠，不阻止先后触发。

旧版根目录脚本、配置样例及 winCron 文件已移除。统一通过 `check-qb` 命令或 `start_check.bat` / `start_check.sh` 启动；签到任务在 Web 面板中管理和执行。

如需从旧版升级，可使用 `import-legacy` 导入自行保留的旧配置文件，上面的路径需替换为实际文件路径。导入前停止 Web 服务。导入器用 AST 读取 `main_config` 的字面量和 `re.compile('...')`，不会 import/执行旧文件；不支持的动态值会提示人工填写。导入保留“添加时间”替换策略，暂停种子调度和通知；数值大小范围仍需在面板检查。不会自动接管旧种。

自行保留的旧签到配置需手动迁移：每个 `test_url_list` 项建立一个签到任务，分别填入 `url`、`header.cookie` 及其他请求头，并新增明确结果标志；SMTP 字段移到通知页。

## 数据目录、备份和恢复

默认目录：Windows `%LOCALAPPDATA%\check-qb`；Linux `~/.local/share/check-qb`（遵循 XDG 设置）。可用 `CHECK_QB_DATA_DIR` 或全局 `--data-dir` 覆盖；所有启动入口必须指向同一目录。

- `check-qb.sqlite3`：加密配置、执行历史、文章去重、管理员密码哈希和会话。
- `secrets.key`：本机加密密钥；也可以通过 `CHECK_QB_ENCRYPTION_KEY` 提供 Fernet 密钥。
- `execution.lock`、`server.lock`：进程锁，不应手动删除运行中的锁文件。

停止服务后备份**整个数据目录**，并妥善保管环境变量提供的密钥。恢复时数据库和密钥必须配套，密钥丢失无法解密。Linux 新目录/密钥限制为仅当前用户；Windows 继承用户数据目录 ACL，共享机器上应确保只有运行账户可访问。加密不防御同时取得数据库和密钥的本机用户。

运行记录自动保留 90 天，维护在启动及任务执行时进行。文章去重记录保留，避免历史删除后重复下载；数据库版本为新建 v2，不直接兼容第三方数据库结构。

Linux 可使用 systemd 常驻运行；将 `ExecStart` 指向虚拟环境的 `check-qb serve`，并通过 `CHECK_QB_DATA_DIR` 指定持久目录。Windows 可用任务计划程序在登录时运行虚拟环境中的 `check-qb.exe serve`，不要再配置周期性启动。

## 开发和验证

```sh
python -m pytest -q
python -m ruff check check_qb tests
cd frontend
npm run typecheck
npm run build
npx playwright install chromium
npm run test:e2e
```

Playwright 启动真实 FastAPI 服务及内存模拟 qBittorrent，使用临时数据目录，不请求真实站点、删除真实文件或发送通知。桌面/手机测试截图位于 `frontend/test-results/`。后端测试模拟成功、超时、删除失败、磁盘未释放、中断恢复和凭据泄漏场景。GitHub Actions 覆盖 Windows/Linux、Python 3.11/3.12。

前端开发用 `npm run dev`，API 转发到本机 8765。生产仅运行 `check-qb serve`。API 文档：`/docs`；接口前缀 `/api/v1`。写接口需会话 Cookie 和 `X-CSRF-Token`，可通过登录响应或 `/auth/session` 获取。配置 PUT 支持部分更新；敏感字段省略表示保留，显式空值表示清除。健康检查 `/healthz` 不包含配置或凭据。

许可证沿用仓库的 GPL-3.0。
