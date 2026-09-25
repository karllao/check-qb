import { useState, type FormEvent } from "react";
import { Save } from "lucide-react";
import { Field, Secret, Toggle, Modal } from "../components";
import type { Attendance } from "../types";
export default function TaskEditor({
  task,
  busy,
  onClose,
  onSave,
  onDelete,
}: {
  task: Attendance;
  busy: boolean;
  onClose: () => void;
  onSave: (task: Attendance) => void;
  onDelete: () => void;
}) {
  const [draft, setDraft] = useState(task);
  const [headers, setHeaders] = useState<string | undefined>(
    task.headers ? JSON.stringify(task.headers, null, 2) : undefined,
  );
  const [error, setError] = useState("");
  const patch = (value: Partial<Attendance>) =>
    setDraft((d) => ({ ...d, ...value }));
  const submit = (e: FormEvent) => {
    e.preventDefault();
    try {
      const parsed: unknown =
        headers === undefined ? undefined : JSON.parse(headers || "{}");
      if (
        parsed !== undefined &&
        (!parsed ||
          typeof parsed !== "object" ||
          Array.isArray(parsed) ||
          Object.values(parsed).some((v) => typeof v !== "string"))
      )
        throw new Error();
      onSave({
        ...draft,
        ...(parsed === undefined
          ? {}
          : { headers: parsed as Record<string, string> }),
      });
    } catch {
      setError("请求头必须为 JSON 对象，且值必须为字符串。");
    }
  };
  return (
    <Modal title={task.id ? "编辑签到任务" : "新建签到任务"} onClose={onClose}>
      <form onSubmit={submit}>
        <Toggle checked={draft.enabled} onChange={(v) => patch({ enabled: v })}>
          启用每日自动签到
        </Toggle>
        <div className="form-grid">
          <Field label="任务名称">
            <input
              required
              value={draft.name}
              onChange={(e) => patch({ name: e.target.value })}
            />
          </Field>
          <Field label="每日时间">
            <input
              type="time"
              required
              value={draft.time}
              onChange={(e) => patch({ time: e.target.value })}
            />
          </Field>
          <Field label="签到地址">
            <input
              type="url"
              required
              value={draft.url}
              onChange={(e) => patch({ url: e.target.value })}
            />
          </Field>
          <Field label="请求方式">
            <select
              value={draft.method}
              onChange={(e) =>
                patch({ method: e.target.value as "GET" | "POST" })
              }
            >
              <option>GET</option>
              <option>POST</option>
            </select>
          </Field>
        </div>
        <Secret
          label="Cookie"
          value={draft.cookie}
          configured={draft.cookie_configured}
          onChange={(v) => patch({ cookie: v })}
        />
        <Field
          label="自定义请求头（JSON）"
          hint={
            draft.headers_configured
              ? "已保存，留空保留；填写 {} 清除。"
              : '例如 {"Content-Type":"application/x-www-form-urlencoded"}'
          }
        >
          <textarea
            value={headers || ""}
            rows={3}
            onChange={(e) => setHeaders(e.target.value || undefined)}
            spellCheck={false}
          />
        </Field>
        {draft.method === "POST" && (
          <>
            <Field
              label="请求体"
              hint={
                draft.body_configured
                  ? "已保存；留空保留。"
                  : "按站点要求填写表单编码或 JSON。"
              }
            >
              <textarea
                rows={3}
                value={draft.body || ""}
                onChange={(e) => patch({ body: e.target.value || undefined })}
              />
            </Field>
            <button
              className="text-button"
              type="button"
              onClick={() => patch({ body: "" })}
            >
              清除已存请求体
            </button>
          </>
        )}
        {(["expired", "already", "success"] as const).map((key) => (
          <div className="match-field" key={key}>
            <Field
              label={
                {
                  expired: "登录失效标志（优先判断）",
                  already: "已签到标志",
                  success: "签到成功标志",
                }[key]
              }
            >
              <input
                value={draft[key].text}
                onChange={(e) =>
                  patch({ [key]: { ...draft[key], text: e.target.value } })
                }
              />
            </Field>
            <label>
              <input
                type="checkbox"
                checked={draft[key].regex}
                onChange={(e) =>
                  patch({ [key]: { ...draft[key], regex: e.target.checked } })
                }
              />
              正则
            </label>
          </div>
        ))}
        <div className="notice subtle">
          不跟随重定向；超时或未匹配明确标志时记录为结果未知，不自动重试。
        </div>
        {error && <div className="notice warning">{error}</div>}
        <div className="form-footer">
          {task.id ? (
            <button
              className="text-button danger"
              type="button"
              disabled={busy}
              onClick={onDelete}
            >
              删除任务
            </button>
          ) : (
            <span />
          )}
          <button className="button primary" disabled={busy}>
            <Save size={16} />
            保存任务
          </button>
        </div>
      </form>
    </Modal>
  );
}
