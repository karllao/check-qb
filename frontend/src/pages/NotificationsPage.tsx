import { useEffect, useState } from "react";
import { Bell, Save } from "lucide-react";
import { Field, Secret, Toggle, labels } from "../components";
import { SectionTitle, NumberField } from "../forms";
import { api } from "../api";
import type { SettingsPageProps, Notice, Notifications } from "../types";
export default function NotificationsPage({
  settings,
  update,
  save,
  busy,
  action,
  setMessage,
}: SettingsPageProps) {
  const notification = settings.notifications;
  const patch = (value: Partial<Notifications>) =>
    update("notifications", { ...notification, ...value });
  const [headers, setHeaders] = useState(
    notification.webhook_headers
      ? JSON.stringify(notification.webhook_headers, null, 2)
      : "",
  );
  const [headersError, setHeadersError] = useState("");
  useEffect(() => {
    if (notification.webhook_headers === undefined) {
      setHeaders("");
      setHeadersError("");
    }
  }, [notification.webhook_headers]);
  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        if (headersError) return;
        void save("notifications");
      }}
      className="settings-stack"
    >
      <section className="panel">
        <SectionTitle
          number="01"
          title="Webhook 通知"
          description="自定义 HTTP 请求，接入机器人或其他通知服务。"
        />
        <Toggle
          checked={notification.webhook_enabled}
          onChange={(v) => patch({ webhook_enabled: v })}
        >
          启用 Webhook
        </Toggle>
        <Secret
          label="Webhook URL"
          value={notification.webhook_url}
          configured={notification.webhook_url_configured}
          onChange={(v) => patch({ webhook_url: v })}
        />
        <div className="form-grid">
          <Field label="Webhook 请求方法">
            <select
              value={notification.webhook_method}
              onChange={(e) =>
                patch({
                  webhook_method: e.target
                    .value as Notifications["webhook_method"],
                })
              }
            >
              {["GET", "POST", "PUT", "PATCH", "DELETE"].map((method) => (
                <option key={method}>{method}</option>
              ))}
            </select>
          </Field>
          <NumberField
            label="Webhook 超时（秒）"
            value={notification.webhook_timeout}
            min={2}
            step={1}
            onChange={(v) => patch({ webhook_timeout: v })}
          />
        </div>
        <Field
          label="Webhook 请求头（JSON）"
          hint={
            notification.webhook_headers_configured
              ? "已保存，留空保留；填写 {} 清除。"
              : '例如 {"Authorization":"Bearer token"}；值必须为字符串。'
          }
        >
          <textarea
            rows={3}
            value={headers}
            spellCheck={false}
            onChange={(e) => {
              const value = e.target.value;
              setHeaders(value);
              try {
                const parsed: unknown = value ? JSON.parse(value) : undefined;
                if (
                  parsed !== undefined &&
                  (!parsed ||
                    typeof parsed !== "object" ||
                    Array.isArray(parsed) ||
                    Object.values(parsed).some((v) => typeof v !== "string"))
                )
                  throw new Error();
                patch({
                  webhook_headers: parsed as Record<string, string> | undefined,
                });
                setHeadersError("");
              } catch {
                setHeadersError("请求头必须为 JSON 对象，且值必须为字符串。");
              }
            }}
          />
        </Field>
        {headersError && <div className="notice warning">{headersError}</div>}
        {notification.webhook_method !== "GET" && (
          <>
            <Field label="Webhook 请求体格式">
              <select
                value={notification.webhook_format}
                onChange={(e) =>
                  patch({
                    webhook_format: e.target
                      .value as Notifications["webhook_format"],
                  })
                }
              >
                <option value="json">JSON</option>
                <option value="form">表单（URL 编码）</option>
                <option value="text">原始文本</option>
              </select>
            </Field>
            <Field
              label="Webhook 请求体模板"
              hint={
                notification.webhook_body_configured
                  ? "已保存，留空保留；点击下方按钮恢复默认。"
                  : 'JSON／表单默认发送 title、message、event；文本默认发送消息。表单模板也使用 JSON 对象，例如 {"text":"{{message}}"}。'
              }
            >
              <textarea
                rows={5}
                value={notification.webhook_body || ""}
                spellCheck={false}
                placeholder={
                  '{"title":"{{title}}","message":"{{message}}","event":"{{event}}"}'
                }
                onChange={(e) =>
                  patch({ webhook_body: e.target.value || undefined })
                }
              />
            </Field>
            <button
              className="text-button"
              type="button"
              onClick={() => patch({ webhook_body: "" })}
            >
              {notification.webhook_body === ""
                ? "保存后恢复默认请求体"
                : "恢复默认请求体"}
            </button>
          </>
        )}
        <p className="notice subtle">
          {
            "URL 路径、查询参数和请求体支持 {{title}}、{{message}}、{{event}}。URL 变量自动编码，JSON 字符串自动转义；GET 不发送请求体。HTTP 2xx 视为成功，不跟随重定向，不自动重试。"
          }
        </p>
      </section>
      <section className="panel">
        <SectionTitle
          number="02"
          title="邮件通知"
          description="通过支持 SSL 或 STARTTLS 的 SMTP 服务发送。"
        />
        <Toggle
          checked={settings.notifications.smtp_enabled}
          onChange={(v) =>
            update("notifications", {
              ...settings.notifications,
              smtp_enabled: v,
            })
          }
        >
          启用 SMTP
        </Toggle>
        <div className="form-grid">
          <Field label="SMTP 服务器">
            <input
              value={settings.notifications.smtp_host}
              onChange={(e) =>
                update("notifications", {
                  ...settings.notifications,
                  smtp_host: e.target.value,
                })
              }
            />
          </Field>
          <NumberField
            label="端口"
            value={settings.notifications.smtp_port}
            min={1}
            step={1}
            onChange={(v) =>
              update("notifications", {
                ...settings.notifications,
                smtp_port: v,
              })
            }
          />
          <Field label="加密方式">
            <select
              value={settings.notifications.smtp_security}
              onChange={(e) =>
                update("notifications", {
                  ...settings.notifications,
                  smtp_security: e.target.value as "ssl" | "starttls",
                })
              }
            >
              <option value="ssl">SSL</option>
              <option value="starttls">STARTTLS</option>
            </select>
          </Field>
          <Field label="SMTP 用户名">
            <input
              value={settings.notifications.smtp_username}
              onChange={(e) =>
                update("notifications", {
                  ...settings.notifications,
                  smtp_username: e.target.value,
                })
              }
            />
          </Field>
          <Secret
            label="SMTP 密码 / 授权码"
            value={settings.notifications.smtp_password}
            configured={settings.notifications.smtp_password_configured}
            onChange={(v) =>
              update("notifications", {
                ...settings.notifications,
                smtp_password: v,
              })
            }
          />
          <Field label="发件人">
            <input
              type="email"
              value={settings.notifications.smtp_from}
              onChange={(e) =>
                update("notifications", {
                  ...settings.notifications,
                  smtp_from: e.target.value,
                })
              }
            />
          </Field>
          <Field label="收件人（逗号分隔）">
            <input
              value={settings.notifications.smtp_to.join(",")}
              onChange={(e) =>
                update("notifications", {
                  ...settings.notifications,
                  smtp_to: e.target.value.split(","),
                })
              }
              onBlur={() =>
                update("notifications", {
                  ...settings.notifications,
                  smtp_to: settings.notifications.smtp_to
                    .map((s) => s.trim())
                    .filter(Boolean),
                })
              }
            />
          </Field>
        </div>
      </section>
      <section className="panel">
        <h2>通知时机</h2>
        <div className="event-options">
          {[
            ["summary", "每次运行摘要"],
            ["failure", "任务失败或结果未知"],
            ["expired", "签到凭据失效"],
          ].map(([id, label]) => (
            <label key={id}>
              <input
                type="checkbox"
                checked={settings.notifications.events.includes(id)}
                onChange={(e) =>
                  update("notifications", {
                    ...settings.notifications,
                    events: e.target.checked
                      ? [...settings.notifications.events, id]
                      : settings.notifications.events.filter((v) => v !== id),
                  })
                }
              />
              {label}
            </label>
          ))}
        </div>
        <div className="form-footer">
          <button
            type="button"
            disabled={busy}
            className="button secondary"
            onClick={() => {
              if (window.confirm("向已保存并启用的通知渠道发送测试消息？"))
                void action(async () => {
                  const notices = await api<Notice[]>(
                    "/notifications/test",
                    "POST",
                  );
                  setMessage(
                    notices.length
                      ? notices
                          .map((n) => `${n.channel}：${labels[n.status]}`)
                          .join("；")
                      : "尚未启用通知渠道",
                  );
                });
            }}
          >
            <Bell size={16} />
            发送测试通知
          </button>
          <button className="button primary" disabled={busy || !!headersError}>
            <Save size={16} />
            保存通知配置
          </button>
        </div>
      </section>
    </form>
  );
}
