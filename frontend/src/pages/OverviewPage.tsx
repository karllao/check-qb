import {
  ArrowDownToLine,
  ArrowRight,
  CalendarCheck,
  Database,
  Eye,
  HardDrive,
  Pause,
  Play,
  Rss,
  ShieldCheck,
} from "lucide-react";
import { Badge, bytes, date, Loading, RunList } from "../components";
import { api } from "../api";
import type {
  SettingsPageProps,
  Dashboard,
  Plan,
  Run,
  Settings,
} from "../types";
type Props = Omit<SettingsPageProps, "save" | "setMessage"> & {
  dashboard: Dashboard | null;
  navigate: (page: string) => void;
  loadDashboard: () => Promise<void>;
  setPreview: (plan: Plan) => void;
  setConfirm: (value: "execute") => void;
  setSelectedRun: (run: Run) => void;
};
export default function OverviewPage({
  settings,
  update,
  busy,
  action,
  dashboard,
  navigate,
  loadDashboard,
  setPreview,
  setConfirm,
  setSelectedRun,
}: Props) {
  return (
    <>
      <section className="hero-panel">
        <div>
          <span className="hero-kicker">
            <span className="pulse-dot" /> 自动化状态
          </span>
          <h2>
            {dashboard?.schedule_enabled
              ? "按你的节奏，持续运行。"
              : "准备就绪，由你开启。"}
          </h2>
          <p>
            {dashboard?.schedule_enabled
              ? "规则已接管日常检查，运行结果会记录在这里。"
              : "先连接客户端并预览规则，再开启自动调度。"}
          </p>
          <div className="button-row">
            <button
              className="button lime"
              disabled={busy}
              onClick={() =>
                void action(async () =>
                  setPreview(await api<Plan>("/runs/preview")),
                )
              }
            >
              <Eye size={17} /> 预览本轮计划
            </button>
            <button
              className="button dark-outline"
              disabled={busy}
              onClick={() => setConfirm("execute")}
            >
              <Play size={15} />
              立即执行
            </button>
          </div>
        </div>
        <div className="hero-graphic" aria-hidden="true">
          <div className="orbit orbit-one" />
          <div className="orbit orbit-two" />
          <div className="graphic-center">
            <ArrowDownToLine size={40} strokeWidth={1.5} />
          </div>
          <span className="graphic-node node-one">
            <Rss size={19} />
          </span>
          <span className="graphic-node node-two">
            <ShieldCheck size={20} />
          </span>
          <span className="graphic-caption">LESS MANAGING. MORE LIVING.</span>
        </div>
      </section>
      {!dashboard ? (
        <Loading />
      ) : (
        <>
          <div className="stats-grid">
            <Stat
              icon={<Database size={20} />}
              label="托管种子"
              value={String(dashboard.managed_count ?? "—")}
              unit={`/ ${settings.rules.max_count}`}
              note={`客户端共 ${dashboard.total_count ?? "—"} 个任务`}
            />
            <Stat
              icon={<HardDrive size={20} />}
              label="可用磁盘空间"
              value={bytes(dashboard.free_bytes)}
              note={`至少保留 ${settings.rules.reserve_gib} GiB`}
            />
            <Stat
              icon={<Rss size={20} />}
              label="已选 RSS"
              value={String(settings.rules.feeds.length)}
              unit="个订阅路径"
              note="按大小和标题规则筛选"
            />
            <Stat
              icon={<CalendarCheck size={20} />}
              label="下次种子检查"
              value={date(
                dashboard.jobs.find((job) => job.id === "torrents")?.next_run,
              )}
              note={
                dashboard.schedule_enabled
                  ? settings.schedule.timezone
                  : "自动调度已暂停"
              }
            />
          </div>
          {!dashboard.connected && (
            <div className="notice warning">
              {dashboard.error || "尚未连接客户端"}
              <button className="text-button" onClick={() => navigate("rules")}>
                配置连接 <ArrowRight size={14} />
              </button>
            </div>
          )}
          {dashboard.pending.length > 0 && (
            <section className="panel">
              <div className="section-heading">
                <h2>有操作需要核对</h2>
                <Badge value="uncertain" />
              </div>
              <p className="muted">
                请先在 qBittorrent
                检查这些哈希对应的新增结果，以及运行记录中的删除结果。确认后该文章不会再次自动尝试。
              </p>
              {dashboard.pending.map((item) => (
                <div className="pending-row" key={item.key}>
                  <code>{item.hash}</code>
                  <button
                    className="button secondary"
                    disabled={busy}
                    onClick={() => {
                      if (
                        window.confirm(
                          "确认已检查 qBittorrent 和运行记录？此文章将不再自动尝试。",
                        )
                      )
                        void action(async () => {
                          await api("/runs/acknowledge", "POST", {
                            key: item.key,
                          });
                          await loadDashboard();
                        }, "核对已记录");
                    }}
                  >
                    已核对，继续
                  </button>
                </div>
              ))}
            </section>
          )}
          <div className="overview-grid">
            <section className="panel">
              <div className="section-heading">
                <h2>最近活动</h2>
                <button
                  className="text-button"
                  onClick={() => navigate("history")}
                >
                  全部记录 <ArrowRight size={15} />
                </button>
              </div>
              <RunList runs={dashboard.recent} onSelect={setSelectedRun} />
            </section>
            <section className="panel strategy-card">
              <div className="section-heading">
                <h2>当前管理规则</h2>
                <ShieldCheck size={20} />
              </div>
              <div className="rule-line">
                <span>管理标签</span>
                <code>check-qb</code>
              </div>
              <div className="rule-line">
                <span>大小范围</span>
                <strong>
                  {settings.rules.min_gib} – {settings.rules.max_gib} GiB
                </strong>
              </div>
              <div className="rule-line">
                <span>替换条件</span>
                <strong>
                  {settings.rules.replacement === "seed_time"
                    ? "完成下载并做种"
                    : "添加时间超过"}{" "}
                  {settings.rules.age_hours} 小时
                </strong>
              </div>
              <div className="rule-line">
                <span>定时检查</span>
                <Badge
                  value={dashboard.schedule_enabled ? "online" : "neutral"}
                >
                  {dashboard.schedule_enabled ? "运行中" : "已暂停"}
                </Badge>
              </div>
              <button
                className="button secondary full"
                disabled={busy}
                onClick={() =>
                  void action(async () => {
                    const result = await api<Settings>("/settings", "PUT", {
                      schedule: {
                        enabled: !dashboard.schedule_enabled,
                      },
                    });
                    update("schedule", result.schedule);
                    await loadDashboard();
                  })
                }
              >
                {dashboard.schedule_enabled ? (
                  <Pause size={16} />
                ) : (
                  <Play size={16} />
                )}
                {dashboard.schedule_enabled ? "暂停种子调度" : "开启种子调度"}
              </button>
              <small>签到任务按各自的启用状态独立调度。</small>
            </section>
          </div>
        </>
      )}
    </>
  );
}
function Stat({
  icon,
  label,
  value,
  unit,
  note,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  unit?: string;
  note: string;
}) {
  return (
    <section className="stat-card">
      <div className="stat-label">
        {label}
        {icon}
      </div>
      <div className="stat-value">
        {value}
        <span>{unit}</span>
      </div>
      <small>{note}</small>
    </section>
  );
}
