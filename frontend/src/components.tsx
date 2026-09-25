import { useEffect, useId, useRef, type ReactNode } from "react";
import { ArrowUpRight, Check, LoaderCircle, X } from "lucide-react";
import type { Plan, Run } from "./types";

export const bytes = (n?: number | null) =>
  n == null || n < 0
    ? "—"
    : n >= 1024 ** 3
      ? (n / 1024 ** 3).toFixed(1) + " GiB"
      : (n / 1024 ** 2).toFixed(1) + " MiB";
export const date = (n?: number | string | null) =>
  n
    ? new Date(typeof n === "number" ? n * 1000 : n).toLocaleString("zh-CN", {
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
      })
    : "—";
export const labels: Record<string, string> = {
  success: "已完成",
  failed: "失败",
  partial: "部分完成",
  interrupted: "已中断",
  running: "执行中",
  skipped: "已跳过",
  skip: "跳过",
  add: "新增",
  replace: "替换",
  uncertain: "待核对",
  unknown: "结果未知",
  expired: "凭据失效",
  already: "已签到",
  checking: "核验中",
  adding: "添加中",
  deleted: "旧种已删除",
  deleting: "删除中",
  torrents: "种子任务",
  attendance: "签到任务",
  notification: "通知测试",
  review: "人工核对",
};

export function Badge({
  value,
  children,
}: {
  value: string;
  children?: ReactNode;
}) {
  return (
    <span
      className={`badge ${["success", "add", "already", "online"].includes(value) ? "good" : ["failed", "expired", "partial", "uncertain"].includes(value) ? "warn" : "neutral"}`}
    >
      {children || labels[value] || value}
    </span>
  );
}
export function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: ReactNode;
}) {
  const id = useId();
  const element = React.isValidElement<{ id?: string }>(children)
    ? React.cloneElement(children, { id })
    : children;
  return (
    <div className="field">
      <label htmlFor={id}>{label}</label>
      {element}
      {hint && <small>{hint}</small>}
    </div>
  );
}
import React from "react";
export function Secret({
  label,
  value,
  configured,
  onChange,
}: {
  label: string;
  value?: string;
  configured?: boolean;
  onChange: (value: string | undefined) => void;
}) {
  return (
    <Field
      label={label}
      hint={
        value === ""
          ? "保存后清除已存凭据"
          : configured
            ? "已安全保存；留空保留原值"
            : "尚未配置"
      }
    >
      <div className="secret">
        <input
          aria-label={label}
          type="password"
          autoComplete="new-password"
          value={value || ""}
          placeholder={configured ? "••••••••（已保存）" : "输入凭据"}
          onChange={(e) => onChange(e.target.value || undefined)}
        />
        <button
          type="button"
          className="text-button"
          onClick={() => onChange("")}
        >
          清除
        </button>
      </div>
    </Field>
  );
}
export function Toggle({
  checked,
  onChange,
  children,
}: {
  checked: boolean;
  onChange: (v: boolean) => void;
  children: ReactNode;
}) {
  return (
    <label className="toggle-label">
      <input
        type="checkbox"
        role="switch"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
      />
      <span className="switch" />
      <span>{children}</span>
    </label>
  );
}
export function Empty({
  title,
  children,
}: {
  title: string;
  children?: ReactNode;
}) {
  return (
    <div className="empty">
      <span className="empty-icon">
        <Check size={24} />
      </span>
      <h3>{title}</h3>
      <p>{children}</p>
    </div>
  );
}
export function Loading() {
  return (
    <div className="loading">
      <LoaderCircle className="spin" size={20} /> 正在读取…
    </div>
  );
}
export function Modal({
  title,
  children,
  onClose,
}: {
  title: string;
  children: ReactNode;
  onClose: () => void;
}) {
  const dialog = useRef<HTMLElement>(null);
  const close = useRef(onClose);
  close.current = onClose;
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    dialog.current?.focus();
    const keydown = (event: KeyboardEvent) => {
      if (event.key === "Escape") close.current();
      if (event.key !== "Tab") return;
      const elements = Array.from(
        dialog.current?.querySelectorAll<HTMLElement>(
          'button:not(:disabled), input:not(:disabled), textarea, select, summary, [tabindex="0"]',
        ) || [],
      );
      const first = elements[0],
        last = elements.at(-1);
      if (
        event.shiftKey &&
        (document.activeElement === first ||
          document.activeElement === dialog.current)
      ) {
        event.preventDefault();
        last?.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first?.focus();
      }
    };
    document.addEventListener("keydown", keydown);
    return () => {
      document.body.style.overflow = overflow;
      document.removeEventListener("keydown", keydown);
      previous?.focus();
    };
  }, []);
  return (
    <div className="modal-backdrop" onClick={onClose}>
      <section
        ref={dialog}
        tabIndex={-1}
        className="modal"
        role="dialog"
        aria-modal="true"
        aria-label={title}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="section-heading">
          <h2>{title}</h2>
          <button className="icon-button" aria-label="关闭" onClick={onClose}>
            <X size={20} />
          </button>
        </div>
        {children}
      </section>
    </div>
  );
}
export function PlanTable({ plan }: { plan: Plan }) {
  return (
    <>
      {plan.disk_warning && (
        <div className="notice warning">{plan.disk_warning}</div>
      )}
      {plan.items.length === 0 ? (
        <Empty title="暂无可评估的 RSS 条目">
          检查订阅源选择；预览仅使用 qBittorrent 当前缓存。
        </Empty>
      ) : (
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>RSS 条目</th>
                <th>大小</th>
                <th>计划</th>
                <th>原因</th>
              </tr>
            </thead>
            <tbody>
              {plan.items.map((item, index) => (
                <tr key={item.key + index}>
                  <td className="wide">
                    <strong>{item.title}</strong>
                    <small>
                      {item.feed}
                      {item.delete && ` · 替换：${item.delete.name}`}
                    </small>
                  </td>
                  <td className="nowrap">{bytes(item.size)}</td>
                  <td>
                    <Badge value={item.action} />
                  </td>
                  <td className="reason">{item.reason}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}
export function RunList({
  runs,
  onSelect,
}: {
  runs: Run[];
  onSelect: (run: Run) => void;
}) {
  return runs.length ? (
    <div className="run-list">
      {runs.map((run) => (
        <button className="run-row" key={run.id} onClick={() => onSelect(run)}>
          <span className={`run-dot ${run.status}`} />
          <span className="run-title">
            <strong>{run.detail.name || labels[run.kind] || run.kind}</strong>
            <small>
              #{run.id} · {date(run.started)}
            </small>
          </span>
          <Badge value={run.status} />
          <ArrowUpRight size={17} />
        </button>
      ))}
    </div>
  ) : (
    <Empty title="一切就绪，等待第一次运行">
      执行一次预览，看看规则会如何处理你的订阅。
    </Empty>
  );
}
