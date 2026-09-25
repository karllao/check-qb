let csrf = "";
export const setCsrf = (value: string) => {
  csrf = value;
};

export async function api<T>(
  path: string,
  method = "GET",
  body?: unknown,
): Promise<T> {
  const response = await fetch("/api/v1" + path, {
    method,
    credentials: "same-origin",
    headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf },
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
  });
  const data = await response
    .json()
    .catch(() => ({ detail: "服务暂时不可用，请稍后重试" }));
  if (!response.ok) {
    if (response.status === 401 && !path.startsWith("/auth"))
      window.dispatchEvent(new Event("session-expired"));
    throw new Error(
      typeof data.detail === "string" ? data.detail : "请求失败，请检查输入",
    );
  }
  return data as T;
}

export function cleanSettings<T>(value: T): T {
  return JSON.parse(
    JSON.stringify(value, (key, entry) =>
      key.endsWith("_configured") ? undefined : entry,
    ),
  );
}
