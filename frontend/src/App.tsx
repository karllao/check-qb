import RulesPage from "./pages/RulesPage";
import NotificationsPage from "./pages/NotificationsPage";
import OverviewPage from "./pages/OverviewPage";
import TaskEditor from "./pages/TaskEditor";
import { useCallback, useEffect, useState } from "react";
import {
  ArrowDownToLine,
  ArrowRight,
  Bell,
  CalendarCheck,
  ChevronRight,
  Database,
  History,
  HardDrive,
  LayoutDashboard,
  LogOut,
  Menu,
  Play,
  Plus,
  RefreshCw,
  Settings2,
  ShieldCheck,
  Sprout,
  X,
} from "lucide-react";
import { api, cleanSettings, setCsrf } from "./api";
import {
  Badge,
  bytes,
  date,
  Empty,
  Field,
  labels,
  Loading,
  Modal,
  PlanTable,
  RunList,
} from "./components";
import type {
  Attendance,
  Dashboard,
  Plan,
  Run,
  Settings,
  Torrent,
} from "./types";

const navigation = [
  { id: "overview", label: "总览", icon: LayoutDashboard },
  { id: "torrents", label: "种子管理", icon: Database },
  { id: "rules", label: "规则设置", icon: Settings2 },
  { id: "attendance", label: "签到任务", icon: CalendarCheck },
  { id: "notifications", label: "通知渠道", icon: Bell },
  { id: "history", label: "运行记录", icon: History },
];
const descriptions: Record<string, string> = {
  overview: "让下载有序，让空间有余。",
  torrents: "明确管理范围，每一个任务都在掌握之中。",
  rules: "把重复的判断，交给适合你的规则。",
  attendance: "每天的小事，按时完成。",
  notifications: "值得关注的变化，及时送达。",
  history: "每一步操作，都有迹可循。",
};

export default function App() {
  const [auth, setAuth] = useState<{
    setup_required: boolean;
    authenticated: boolean;
  } | null>(null);
  const [page, setPage] = useState("overview");
  const [settings, setSettings] = useState<Settings | null>(null);
  const [dashboard, setDashboard] = useState<Dashboard | null>(null);
  const [torrents, setTorrents] = useState<Torrent[] | null>(null);
  const [runs, setRuns] = useState<Run[] | null>(null);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [menu, setMenu] = useState(false);
  const [preview, setPreview] = useState<Plan | null>(null);
  const [selectedRun, setSelectedRun] = useState<Run | null>(null);
  const [selected, setSelected] = useState<string[]>([]);
  const [confirm, setConfirm] = useState<"execute" | "adopt" | null>(null);
  const [editingTask, setEditingTask] = useState<Attendance | null>(null);
  const [offset, setOffset] = useState(0);

  const action = async (work: () => Promise<void>, success = "") => {
    setBusy(true);
    setError("");
    setMessage("");
    try {
      await work();
      if (success) setMessage(success);
    } catch (e) {
      setError(e instanceof Error ? e.message : "操作失败，请稍后重试");
    } finally {
      setBusy(false);
    }
  };
  const loadDashboard = useCallback(
    async () => setDashboard(await api<Dashboard>("/dashboard")),
    [],
  );
  useEffect(() => {
    void api<{ setup_required: boolean; authenticated: boolean }>(
      "/auth/status",
    )
      .then(async (result) => {
        if (result.authenticated)
          setCsrf((await api<{ csrf: string }>("/auth/session")).csrf);
        setAuth(result);
      })
      .catch((e) => setError(e.message));
    const expired = () => {
      setAuth({ setup_required: false, authenticated: false });
      setSettings(null);
      setCsrf("");
    };
    window.addEventListener("session-expired", expired);
    return () => window.removeEventListener("session-expired", expired);
  }, []);
  useEffect(() => {
    if (!auth?.authenticated) return;
    void action(async () => {
      setSettings(await api<Settings>("/settings"));
      await loadDashboard();
    });
  }, [auth?.authenticated, loadDashboard]);
  useEffect(() => {
    if (!auth?.authenticated) return;
    if (page === "torrents")
      void action(async () => setTorrents(await api<Torrent[]>("/torrents")));
    if (page === "history")
      void action(async () =>
        setRuns(await api<Run[]>(`/runs?offset=${offset}`)),
      );
  }, [page, auth?.authenticated, offset]);
  useEffect(() => {
    if (!auth?.authenticated || page !== "overview") return;
    const timer = window.setInterval(() => {
      if (!busy) void loadDashboard().catch(() => {});
    }, 30000);
    return () => window.clearInterval(timer);
  }, [auth?.authenticated, page, busy, loadDashboard]);

  const navigate = (id: string) => {
    setPage(id);
    setMenu(false);
    setError("");
    setMessage("");
  };
  const update = <K extends keyof Settings>(key: K, value: Settings[K]) =>
    setSettings((s) => (s ? { ...s, [key]: value } : s));
  const save = (key: keyof Settings) =>
    action(async () => {
      const result = await api<Settings>(
        "/settings",
        "PUT",
        cleanSettings({ [key]: settings![key] }),
      );
      update(key, result[key]);
      await loadDashboard();
    }, "设置已保存");
  const refresh = () =>
    action(async () => {
      if (page === "overview") await loadDashboard();
      else if (page === "torrents")
        setTorrents(await api<Torrent[]>("/torrents"));
      else if (page === "history")
        setRuns(await api<Run[]>(`/runs?offset=${offset}`));
      else {
        setSettings(await api<Settings>("/settings"));
        setMessage("已载入保存的配置");
      }
    });

  if (!auth)
    return (
      <main className="auth-screen">
        <div className="auth-card">
          <Brand />
          {error ? (
            <div className="notice warning">
              {error}
              <button
                className="button secondary"
                onClick={() => window.location.reload()}
              >
                重新连接
              </button>
            </div>
          ) : (
            <Loading />
          )}
        </div>
      </main>
    );
  if (!auth.authenticated)
    return (
      <main className="auth-screen">
        <div className="auth-art">
          <div className="orb one" />
          <div className="orb two" />
          <Brand />
          <div className="auth-copy">
            <span className="eyebrow">A LITTLE SPACE. MORE POSSIBILITIES.</span>
            <h1>
              下载有序，
              <br />
              空间有余。
            </h1>
            <p>
              让种子、订阅与日常任务，
              <br />
              在一个安静的空间里井然有序。
            </p>
            <div className="auth-chips">
              <span>
                <ShieldCheck size={16} /> 明确管理边界
              </span>
              <span>
                <HardDrive size={16} /> 关心每一寸空间
              </span>
            </div>
          </div>
          <small>check-qb / 2.0</small>
        </div>
        <div className="auth-form">
          <div className="auth-card">
            <span className="eyebrow">YOUR DOWNLOAD COMPANION</span>
            <h2>{auth.setup_required ? "从这里开始" : "欢迎回来"}</h2>
            <p>
              {auth.setup_required
                ? "创建管理员账号，开启你的自动化面板。"
                : "登录后，继续管理你的下载空间。"}
            </p>
            <form
              onSubmit={(e) => {
                e.preventDefault();
                const data = new FormData(e.currentTarget);
                void action(async () => {
                  const result = await api<{ csrf: string }>(
                    "/auth/" + (auth.setup_required ? "setup" : "login"),
                    "POST",
                    {
                      password: data.get("password"),
                      setup_token: data.get("token") || "",
                    },
                  );
                  setCsrf(result.csrf);
                  setAuth({ setup_required: false, authenticated: true });
                  if (auth.setup_required) setPage("rules");
                });
              }}
            >
              {auth.setup_required && (
                <Field
                  label="首次设置凭据"
                  hint="在启动服务的终端中查看一次性凭据。"
                >
                  <input
                    name="token"
                    required
                    autoComplete="off"
                    placeholder="粘贴终端中的设置凭据"
                  />
                </Field>
              )}
              <Field
                label="管理员密码"
                hint={
                  auth.setup_required
                    ? "至少 10 个字符，请使用独立密码。"
                    : undefined
                }
              >
                <input
                  name="password"
                  required
                  minLength={10}
                  maxLength={200}
                  type="password"
                  autoComplete={
                    auth.setup_required ? "new-password" : "current-password"
                  }
                  placeholder="输入管理员密码"
                />
              </Field>
              {error && (
                <div role="alert" className="notice warning">
                  {error}
                </div>
              )}
              <button className="button primary full" disabled={busy}>
                {busy
                  ? "正在验证…"
                  : auth.setup_required
                    ? "创建管理员"
                    : "登录面板"}
                <ArrowRight size={18} />
              </button>
            </form>
            <small className="auth-foot">
              <ShieldCheck size={14} /> 凭据加密保存，仅用于你的自动化任务。
            </small>
          </div>
        </div>
      </main>
    );

  const current = navigation.find((item) => item.id === page)!;
  return (
    <div className="app-shell">
      <aside className={`sidebar ${menu ? "open" : ""}`}>
        <Brand />
        <div className="workspace-label">
          个人工作空间 <span>LOCAL</span>
        </div>
        <nav aria-label="主导航">
          {navigation.map((item) => (
            <button
              key={item.id}
              className={page === item.id ? "active" : ""}
              onClick={() => navigate(item.id)}
            >
              <item.icon size={19} />
              <span>{item.label}</span>
              {page === item.id && <span className="nav-dot" />}
            </button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="sidebar-tip">
            <Sprout size={23} />
            <strong>小磁盘，也从容。</strong>
            <p>只管理带 check-qb 标签的种子，把空间留给下一份期待。</p>
          </div>
          <button
            className="logout"
            disabled={busy}
            onClick={() =>
              void action(async () => {
                await api("/auth/logout", "POST");
                setCsrf("");
                setAuth({ setup_required: false, authenticated: false });
                setSettings(null);
              })
            }
          >
            <LogOut size={17} /> 退出登录<span>v2.0</span>
          </button>
        </div>
      </aside>
      {menu && (
        <button
          className="mobile-overlay"
          aria-label="收起菜单"
          onClick={() => setMenu(false)}
        />
      )}
      <div className="main-shell">
        <header className="topbar">
          <div>
            <button
              className="icon-button mobile-menu"
              aria-label="打开菜单"
              onClick={() => setMenu(!menu)}
            >
              <Menu size={21} />
            </button>
            <span>工作空间</span>
            <ChevronRight size={14} />
            <strong>{current.label}</strong>
          </div>
          <div className="topbar-right">
            <span
              className={`connection-dot ${dashboard?.connected ? "online" : ""}`}
            />
            <span>
              {dashboard?.connected ? "qBittorrent 已连接" : "等待连接"}
            </span>
            <span className="avatar">A</span>
          </div>
        </header>
        <main className="main-content">
          <div className="page-heading">
            <div>
              <span className="eyebrow">
                {page === "overview"
                  ? "WORKSPACE OVERVIEW"
                  : "YOUR AUTOMATION, YOUR WAY"}
              </span>
              <h1>
                {current.label}
                <span className="heading-dot">.</span>
              </h1>
              <p>{descriptions[page]}</p>
            </div>
            <button
              className="button secondary"
              disabled={busy}
              onClick={() => void refresh()}
            >
              <RefreshCw size={16} className={busy ? "spin" : ""} />
              刷新
            </button>
          </div>
          {error && (
            <div className="notice warning" role="alert">
              {error}
              <button
                className="icon-button"
                aria-label="关闭错误"
                onClick={() => setError("")}
              >
                <X size={16} />
              </button>
            </div>
          )}
          {message && (
            <div className="notice success" role="status">
              {message}
            </div>
          )}
          {!settings ? (
            <Loading />
          ) : (
            <>
              {page === "overview" && (
                <OverviewPage
                  settings={settings}
                  update={update}
                  busy={busy}
                  action={action}
                  dashboard={dashboard}
                  navigate={navigate}
                  loadDashboard={loadDashboard}
                  setPreview={setPreview}
                  setConfirm={setConfirm}
                  setSelectedRun={setSelectedRun}
                />
              )}
              {page === "torrents" && (
                <section className="panel">
                  <div className="section-heading">
                    <div>
                      <h2>
                        客户端任务{" "}
                        <span className="count">{torrents?.length ?? 0}</span>
                      </h2>
                      <p>选中任务并添加管理标签后，才会参与自动替换。</p>
                    </div>
                    <button
                      className="button primary"
                      disabled={busy || !selected.length}
                      onClick={() => setConfirm("adopt")}
                    >
                      <Plus size={16} />
                      接管选中项 {selected.length > 0 && `(${selected.length})`}
                    </button>
                  </div>
                  {!torrents ? (
                    <Loading />
                  ) : !torrents.length ? (
                    <Empty title="客户端暂无种子">
                      连接 RSS 后，可以预览符合规则的新任务。
                    </Empty>
                  ) : (
                    <div className="table-scroll">
                      <table>
                        <thead>
                          <tr>
                            <th>选择</th>
                            <th>名称 / 进度</th>
                            <th>大小</th>
                            <th>做种时长</th>
                            <th>添加时间</th>
                            <th>管理状态</th>
                          </tr>
                        </thead>
                        <tbody>
                          {torrents.map((t) => (
                            <tr key={t.hash}>
                              <td>
                                <input
                                  type="checkbox"
                                  aria-label={`选择 ${t.name}`}
                                  disabled={t.managed}
                                  checked={selected.includes(t.hash)}
                                  onChange={(e) =>
                                    setSelected(
                                      e.target.checked
                                        ? [...selected, t.hash]
                                        : selected.filter((h) => h !== t.hash),
                                    )
                                  }
                                />
                              </td>
                              <td className="wide">
                                <strong>{t.name}</strong>
                                <div className="progress-track">
                                  <span
                                    style={{
                                      width: `${Math.min(100, t.progress * 100)}%`,
                                    }}
                                  />
                                </div>
                                <small>
                                  {(t.progress * 100).toFixed(1)}% · {t.state}
                                </small>
                              </td>
                              <td className="nowrap">
                                {bytes(t.total_size || t.size)}
                              </td>
                              <td>
                                {t.seeding_time == null
                                  ? "不支持"
                                  : `${(t.seeding_time / 3600).toFixed(1)} h`}
                              </td>
                              <td className="nowrap">{date(t.added_on)}</td>
                              <td>
                                <Badge value={t.managed ? "online" : "neutral"}>
                                  {t.managed ? "托管中" : "未接管"}
                                </Badge>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </section>
              )}
              {page === "rules" && (
                <RulesPage
                  settings={settings}
                  update={update}
                  save={save}
                  busy={busy}
                  action={action}
                  setMessage={setMessage}
                />
              )}
              {page === "attendance" && (
                <section className="panel">
                  <div className="section-heading">
                    <div>
                      <h2>每日签到</h2>
                      <p>HTTP 状态正常不等于签到成功，请配置明确的结果标志。</p>
                    </div>
                    <button
                      className="button primary"
                      onClick={() =>
                        setEditingTask({
                          name: "",
                          enabled: false,
                          url: "",
                          method: "GET",
                          time: "09:00",
                          success: { text: "", regex: false },
                          already: { text: "", regex: false },
                          expired: { text: "", regex: false },
                        })
                      }
                    >
                      <Plus size={16} />
                      新建任务
                    </button>
                  </div>
                  {!settings.attendance.length ? (
                    <Empty title="把每日签到交给这里">
                      配置站点地址、Cookie 与成功标志，按时自动执行。
                    </Empty>
                  ) : (
                    <div className="task-grid">
                      {settings.attendance.map((task) => (
                        <article className="task-card" key={task.id}>
                          <div className="section-heading">
                            <span className="task-icon">
                              <CalendarCheck size={22} />
                            </span>
                            <Badge value={task.enabled ? "online" : "neutral"}>
                              {task.enabled ? "已启用" : "已暂停"}
                            </Badge>
                          </div>
                          <h3>{task.name}</h3>
                          <p>
                            {task.method} · 每日 {task.time} ·{" "}
                            {settings.schedule.timezone}
                          </p>
                          <div className="button-row">
                            <button
                              className="button secondary"
                              disabled={busy}
                              onClick={() => setEditingTask(task)}
                            >
                              编辑任务
                            </button>
                            <button
                              className="text-button"
                              disabled={busy}
                              onClick={() => {
                                if (
                                  window.confirm(
                                    `立即请求“${task.name}”的签到地址？`,
                                  )
                                )
                                  void action(async () => {
                                    const r = await api<{
                                      status: string;
                                      reason: string;
                                    }>(`/attendance/${task.id}/run`, "POST");
                                    setMessage(
                                      `${labels[r.status] || r.status}：${r.reason}`,
                                    );
                                  });
                              }}
                            >
                              <Play size={14} />
                              执行一次
                            </button>
                          </div>
                        </article>
                      ))}
                    </div>
                  )}
                </section>
              )}
              {page === "notifications" && (
                <NotificationsPage
                  settings={settings}
                  update={update}
                  save={save}
                  busy={busy}
                  action={action}
                  setMessage={setMessage}
                />
              )}
              {page === "history" && (
                <section className="panel">
                  <div className="section-heading">
                    <div>
                      <h2>执行时间线</h2>
                      <p>记录保留 90 天，点击查看判断依据和实际操作。</p>
                    </div>
                    <Badge value="neutral">每页 50 条</Badge>
                  </div>
                  {runs ? (
                    <RunList runs={runs} onSelect={setSelectedRun} />
                  ) : (
                    <Loading />
                  )}
                  <div className="pagination">
                    <button
                      className="button secondary"
                      disabled={!offset || busy}
                      onClick={() => setOffset(Math.max(0, offset - 50))}
                    >
                      上一页
                    </button>
                    <span>第 {offset / 50 + 1} 页</span>
                    <button
                      className="button secondary"
                      disabled={!runs || runs.length < 50 || busy}
                      onClick={() => setOffset(offset + 50)}
                    >
                      下一页
                    </button>
                  </div>
                </section>
              )}
            </>
          )}
          <footer className="page-footer">
            <span>
              <Sprout size={14} /> CHECK-QB
            </span>
            <span>少一点重复，多一点从容。</span>
          </footer>
        </main>
      </div>
      {preview && (
        <Modal title="本轮执行预览" onClose={() => setPreview(null)}>
          <p className="muted">
            预览不会刷新 RSS
            或修改种子。执行时会重新读取状态，实际操作可能变化。
          </p>
          <PlanTable plan={preview} />
          <div className="form-footer">
            <span>替换操作会删除旧种及文件。</span>
            <button
              className="button primary"
              disabled={busy}
              onClick={() => {
                setPreview(null);
                setConfirm("execute");
              }}
            >
              立即执行
            </button>
          </div>
        </Modal>
      )}
      {confirm && (
        <Modal
          title={confirm === "adopt" ? "确认接管选中种子" : "确认执行本轮任务"}
          onClose={() => setConfirm(null)}
        >
          <p className="confirm-copy">
            {confirm === "adopt"
              ? `将为 ${selected.length} 个种子添加 check-qb 标签。之后这些种子会参与数量限制和自动替换，符合替换规则时将删除种子及文件。`
              : "将按已保存规则刷新 RSS、添加种子，并在满额时替换符合条件的托管种子。替换会删除旧种及文件。"}
          </p>
          <div className="form-footer">
            <button
              className="button secondary"
              onClick={() => setConfirm(null)}
            >
              取消
            </button>
            <button
              className="button primary"
              disabled={busy}
              onClick={() => {
                const type = confirm;
                setConfirm(null);
                void action(async () => {
                  if (type === "adopt") {
                    await api("/torrents/adopt", "POST", { hashes: selected });
                    setSelected([]);
                    setTorrents(await api("/torrents"));
                    setMessage("选中种子已接管");
                  } else {
                    const r = await api<{ id: number; status: string }>(
                      "/runs/execute",
                      "POST",
                    );
                    await loadDashboard();
                    setMessage(
                      `任务 #${r.id}：${labels[r.status]}，可在运行记录查看详情`,
                    );
                  }
                });
              }}
            >
              确认{confirm === "adopt" ? "接管" : "执行"}
            </button>
          </div>
        </Modal>
      )}
      {selectedRun && (
        <Modal
          title={`运行记录 #${selectedRun.id}`}
          onClose={() => setSelectedRun(null)}
        >
          <div className="record-meta">
            <Badge value={selectedRun.status} />
            <span>{date(selectedRun.started)}</span>
          </div>
          {(selectedRun.detail.error || selectedRun.detail.reason) && (
            <div className="notice subtle">
              {selectedRun.detail.error || selectedRun.detail.reason}
            </div>
          )}
          {selectedRun.detail.actions?.map((a, i) => (
            <div className="action-record" key={i}>
              <div>
                <strong>{a.title}</strong>
                <Badge value={a.status} />
              </div>
              <p>
                {a.reason || labels[a.action]}
                {a.warning && ` · ${a.warning}`}
              </p>
              {a.deleted_hash && <small>删除对象：{a.deleted_hash}</small>}
            </div>
          ))}
          {selectedRun.detail.plan && (
            <details>
              <summary>查看当时的完整计划</summary>
              <PlanTable plan={selectedRun.detail.plan} />
            </details>
          )}
          {!!selectedRun.detail.notifications?.length && (
            <div className="notification-results">
              <h3>通知结果</h3>
              {selectedRun.detail.notifications.map((n) => (
                <p key={n.channel}>
                  {n.channel} <Badge value={n.status} /> {n.reason}
                </p>
              ))}
            </div>
          )}
        </Modal>
      )}
      {editingTask && settings && (
        <TaskEditor
          task={editingTask}
          busy={busy}
          onClose={() => setEditingTask(null)}
          onSave={(task) =>
            void action(async () => {
              const tasks = task.id
                ? settings.attendance.map((t) => (t.id === task.id ? task : t))
                : [...settings.attendance, task];
              const result = await api<Settings>(
                "/settings",
                "PUT",
                cleanSettings({ attendance: tasks }),
              );
              update("attendance", result.attendance);
              setEditingTask(null);
            }, "签到任务已保存")
          }
          onDelete={() => {
            if (window.confirm("删除这个签到任务？"))
              void action(async () => {
                const result = await api<Settings>(
                  "/settings",
                  "PUT",
                  cleanSettings({
                    attendance: settings.attendance.filter(
                      (t) => t.id !== editingTask.id,
                    ),
                  }),
                );
                update("attendance", result.attendance);
                setEditingTask(null);
              }, "签到任务已删除");
          }}
        />
      )}
    </div>
  );
}

function Brand() {
  return (
    <div className="brand">
      <span className="brand-icon">
        <ArrowDownToLine size={23} strokeWidth={2.3} />
      </span>
      <strong>
        check-qb<span>.</span>
      </strong>
    </div>
  );
}
