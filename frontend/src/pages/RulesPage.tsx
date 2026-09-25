import { useState } from "react";
import { CircleHelp, Radio, RefreshCw, Rss, Save } from "lucide-react";
import { Field, Secret, Toggle } from "../components";
import { SectionTitle, NumberField } from "../forms";
import { api } from "../api";
import type { SettingsPageProps } from "../types";
export default function RulesPage({
  settings,
  update,
  save,
  busy,
  action,
  setMessage,
}: SettingsPageProps) {
  const [feedList, setFeedList] = useState<{ path: string; count: number }[]>(
    [],
  );
  return (
    <div className="settings-stack">
      <section className="panel">
        <SectionTitle
          number="01"
          title="连接 qBittorrent"
          description="使用 Web UI 账号密码，或 qBittorrent 5.2+ 的 API Key。配置 API Key 后会优先使用。"
        />
        <form
          onSubmit={(e) => {
            e.preventDefault();
            void save("connection");
          }}
        >
          <div className="form-grid">
            <Field label="Web UI 地址">
              <input
                type="url"
                required
                value={settings.connection.url}
                onChange={(e) =>
                  update("connection", {
                    ...settings.connection,
                    url: e.target.value,
                  })
                }
              />
            </Field>
            <Field label="用户名">
              <input
                required
                value={settings.connection.username}
                onChange={(e) =>
                  update("connection", {
                    ...settings.connection,
                    username: e.target.value,
                  })
                }
              />
            </Field>
            <Secret
              label="Web UI 密码"
              value={settings.connection.password}
              configured={settings.connection.password_configured}
              onChange={(v) =>
                update("connection", {
                  ...settings.connection,
                  password: v,
                })
              }
            />
            <Secret
              label="API Key（qBittorrent 5.2+）"
              value={settings.connection.api_key}
              configured={settings.connection.api_key_configured}
              onChange={(v) =>
                update("connection", {
                  ...settings.connection,
                  api_key: v,
                })
              }
            />
            <Field label="请求超时（秒）">
              <input
                type="number"
                min={2}
                max={120}
                value={settings.connection.timeout}
                onChange={(e) =>
                  update("connection", {
                    ...settings.connection,
                    timeout: +e.target.value,
                  })
                }
              />
            </Field>
          </div>
          <div className="form-footer">
            <button
              className="button secondary"
              type="button"
              disabled={busy}
              onClick={() =>
                void action(async () => {
                  const result = await api<{
                    version: string;
                    save_path: string;
                    seed_time_supported: boolean;
                    tags_supported: boolean;
                  }>("/connection");
                  setMessage(
                    `连接成功：${result.version} · ${result.save_path}${!result.seed_time_supported ? " · 当前任务缺少做种时长字段" : ""}${!result.tags_supported ? " · 当前客户端缺少标签支持" : ""}`,
                  );
                })
              }
            >
              <Radio size={16} />
              测试已保存的连接
            </button>
            <button className="button primary" disabled={busy}>
              <Save size={16} />
              保存连接
            </button>
          </div>
        </form>
      </section>
      <section className="panel">
        <SectionTitle
          number="02"
          title="订阅与筛选"
          description="从 qBittorrent 已配置的 RSS 中选择来源。GB 按十进制、GiB 按二进制换算。"
        />
        <form
          onSubmit={(e) => {
            e.preventDefault();
            void save("rules");
          }}
        >
          <div className="feed-selector">
            <div className="section-heading">
              <h3>订阅来源</h3>
              <button
                className="text-button"
                type="button"
                disabled={busy}
                onClick={() =>
                  void action(async () => setFeedList(await api("/rss")))
                }
              >
                <RefreshCw size={14} />
                读取订阅列表
              </button>
            </div>
            {feedList.length ? (
              feedList.map((feed) => (
                <label key={feed.path} className="feed-option">
                  <input
                    type="checkbox"
                    checked={settings.rules.feeds.includes(feed.path)}
                    onChange={(e) =>
                      update("rules", {
                        ...settings.rules,
                        feeds: e.target.checked
                          ? [...settings.rules.feeds, feed.path]
                          : settings.rules.feeds.filter((f) => f !== feed.path),
                      })
                    }
                  />
                  <Rss size={16} />
                  <span>{feed.path}</span>
                  <small>{feed.count} 个条目</small>
                </label>
              ))
            ) : (
              <p className="muted">连接保存后，点击“读取订阅列表”选择来源。</p>
            )}
            <Field label="已选订阅路径（每行一个，也支持文件夹路径）">
              <textarea
                rows={3}
                value={settings.rules.feeds.join("\n")}
                onChange={(e) =>
                  update("rules", {
                    ...settings.rules,
                    feeds: e.target.value.split("\n"),
                  })
                }
                onBlur={() =>
                  update("rules", {
                    ...settings.rules,
                    feeds: settings.rules.feeds
                      .map((f) => f.trim())
                      .filter(Boolean),
                  })
                }
              />
            </Field>
          </div>
          <div className="form-grid">
            <NumberField
              label="最小大小（GiB）"
              value={settings.rules.min_gib}
              min={0}
              onChange={(v) =>
                update("rules", { ...settings.rules, min_gib: v })
              }
            />
            <NumberField
              label="最大大小（GiB）"
              value={settings.rules.max_gib}
              min={0.01}
              onChange={(v) =>
                update("rules", { ...settings.rules, max_gib: v })
              }
            />
            <NumberField
              label="最多托管种子数"
              value={settings.rules.max_count}
              min={1}
              step={1}
              onChange={(v) =>
                update("rules", { ...settings.rules, max_count: v })
              }
            />
            <NumberField
              label="最小保留空间（GiB）"
              value={settings.rules.reserve_gib}
              min={0}
              onChange={(v) =>
                update("rules", {
                  ...settings.rules,
                  reserve_gib: v,
                })
              }
            />
            <Field label="替换策略">
              <select
                value={settings.rules.replacement}
                onChange={(e) =>
                  update("rules", {
                    ...settings.rules,
                    replacement: e.target.value as "seed_time" | "added_time",
                  })
                }
              >
                <option value="seed_time">完成下载且累计做种达标</option>
                <option value="added_time">
                  按添加时间替换（含未完成任务）
                </option>
              </select>
            </Field>
            <NumberField
              label="时间阈值（小时）"
              min={0.01}
              value={settings.rules.age_hours}
              onChange={(v) =>
                update("rules", { ...settings.rules, age_hours: v })
              }
            />
          </div>
          <Field
            label="标题正则（可选）"
            hint="留空只按大小过滤；无法识别大小的条目会跳过。"
          >
            <input
              value={settings.rules.title_pattern}
              placeholder="例如：1080p|2160p"
              onChange={(e) =>
                update("rules", {
                  ...settings.rules,
                  title_pattern: e.target.value,
                })
              }
            />
          </Field>
          <div className="notice subtle">
            <CircleHelp size={18} />
            <span>
              替换会删除旧种及文件，仅作用于 check-qb
              标签。空间估算会预留所有未完成下载的占用；无法判断磁盘归属时暂停新增。
            </span>
          </div>
          <div className="form-footer">
            <span />
            <button className="button primary" disabled={busy}>
              <Save size={16} />
              保存规则
            </button>
          </div>
        </form>
      </section>
      <section className="panel">
        <SectionTitle
          number="03"
          title="自动调度"
          description="手动执行与定时任务共享执行锁，避免重复操作。"
        />
        <form
          onSubmit={(e) => {
            e.preventDefault();
            void save("schedule");
          }}
        >
          <Toggle
            checked={settings.schedule.enabled}
            onChange={(v) =>
              update("schedule", {
                ...settings.schedule,
                enabled: v,
              })
            }
          >
            启用种子定时检查
          </Toggle>
          <div className="form-grid">
            <Field label="调度方式">
              <select
                value={settings.schedule.mode}
                onChange={(e) =>
                  update("schedule", {
                    ...settings.schedule,
                    mode: e.target.value as "interval" | "cron",
                  })
                }
              >
                <option value="interval">固定间隔</option>
                <option value="cron">Cron 表达式</option>
              </select>
            </Field>
            {settings.schedule.mode === "interval" ? (
              <NumberField
                label="间隔（秒）"
                min={30}
                step={1}
                value={settings.schedule.interval_seconds}
                onChange={(v) =>
                  update("schedule", {
                    ...settings.schedule,
                    interval_seconds: v,
                  })
                }
              />
            ) : (
              <Field label="五字段 Cron" hint="分 时 日 月 星期；星期一为 0。">
                <input
                  required
                  value={settings.schedule.cron}
                  onChange={(e) =>
                    update("schedule", {
                      ...settings.schedule,
                      cron: e.target.value,
                    })
                  }
                />
              </Field>
            )}
            <Field label="时区" hint="也用于每日签到。">
              <input
                required
                value={settings.schedule.timezone}
                onChange={(e) =>
                  update("schedule", {
                    ...settings.schedule,
                    timezone: e.target.value,
                  })
                }
              />
            </Field>
          </div>
          <div className="form-footer">
            <span />
            <button className="button primary" disabled={busy}>
              <Save size={16} />
              保存调度
            </button>
          </div>
        </form>
      </section>
    </div>
  );
}
