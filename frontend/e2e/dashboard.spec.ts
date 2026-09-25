import { test, expect, type Page } from "@playwright/test";

async function navigate(page: Page, name: string) {
  if (await page.getByRole("button", { name: "打开菜单" }).isVisible())
    await page.getByRole("button", { name: "打开菜单" }).click();
  await page
    .getByRole("navigation")
    .getByRole("button", { name, exact: true })
    .click();
}

test("首次设置、规则、预览、接管、运行、签到与手机布局", async ({
  page,
}, testInfo) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/");
  await expect(page.getByLabel("管理员密码")).toBeVisible();
  const setup = await page
    .getByLabel("首次设置凭据")
    .isVisible()
    .catch(() => false);
  if (setup) await page.getByLabel("首次设置凭据").fill("ui-test-setup");
  await page.getByLabel("管理员密码").fill("browser-test-password");
  await page
    .getByRole("button", {
      name: setup ? "创建管理员" : "登录面板",
      exact: true,
    })
    .click();
  await expect(page.getByRole("navigation")).toBeAttached();
  await navigate(page, "规则设置");
  await expect(page.getByLabel("Web UI 地址")).toBeVisible();
  await page
    .getByLabel("Web UI 密码", { exact: true })
    .fill("private-qb-password");
  await page
    .getByLabel("API Key（qBittorrent 5.2+）", { exact: true })
    .fill("qbt_ABCDEFGHIJKLMNOPQRSTUVWXYZ12");
  await page.getByRole("button", { name: "保存连接", exact: true }).click();
  await expect(page.getByRole("status")).toHaveText("设置已保存");
  await expect(page.getByLabel("Web UI 密码", { exact: true })).toHaveValue("");
  const saved = await page.request.get("/api/v1/settings");
  const savedText = await saved.text();
  expect(savedText).not.toContain("private-qb-password");
  expect(savedText).not.toContain("qbt_ABCDEFGHIJKLMNOPQRSTUVWXYZ12");
  await page.getByRole("button", { name: "测试已保存的连接" }).click();
  await expect(page.getByRole("status")).toContainText("连接成功");
  await page.getByLabel("最多托管种子数").fill("6");
  await page.getByRole("button", { name: "保存规则", exact: true }).click();
  await expect(page.getByRole("status")).toHaveText("设置已保存");
  await page.getByRole("button", { name: "读取订阅列表" }).click();
  await expect(page.getByText("1 个条目", { exact: true })).toBeVisible();
  await navigate(page, "总览");
  await page.getByRole("button", { name: "预览本轮计划" }).click();
  await expect(page.getByRole("dialog")).toContainText("新种 [2 GiB]");
  await page.getByRole("button", { name: "关闭", exact: true }).click();
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({
    path: `test-results/overview-${testInfo.project.name}.png`,
    fullPage: true,
  });
  await navigate(page, "种子管理");
  const checkbox = page.getByRole("checkbox", {
    name: "选择 示例纪录片 [2 GiB]",
  });
  if (await checkbox.isEnabled()) {
    await checkbox.check();
    await page.getByRole("button", { name: /接管选中项/ }).click();
    await page.getByRole("button", { name: "确认接管", exact: true }).click();
    await expect(page.getByRole("status")).toContainText("已接管");
  }
  await expect(page.getByText("托管中", { exact: true }).first()).toBeVisible();
  await navigate(page, "总览");
  await page.getByRole("button", { name: "立即执行", exact: true }).click();
  await page.getByRole("button", { name: "确认执行", exact: true }).click();
  await expect(page.getByRole("status")).toContainText("已完成");
  await navigate(page, "运行记录");
  await page.locator(".run-row").first().click();
  await expect(page.getByRole("dialog")).toContainText("运行记录 #");
  await page.getByRole("button", { name: "关闭", exact: true }).click();
  await navigate(page, "签到任务");
  await page.getByRole("button", { name: "新建任务" }).click();
  await page.getByLabel("任务名称").fill(`测试签到-${testInfo.project.name}`);
  await page.getByLabel("签到地址").fill("https://example.invalid/attendance");
  await page
    .getByLabel("Cookie", { exact: true })
    .fill("session=private-cookie");
  await page.getByLabel("签到成功标志", { exact: true }).fill("签到成功");
  await page.getByRole("button", { name: "保存任务", exact: true }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(
    page.getByRole("heading", { name: `测试签到-${testInfo.project.name}` }),
  ).toBeVisible();
  await expect(page.locator("body")).not.toContainText("private-cookie");
  await navigate(page, "通知渠道");
  await expect(
    page.getByRole("heading", { name: "Webhook 通知", exact: true }),
  ).toBeVisible();
  await expect(page.getByText("IYUU 微信通知")).toHaveCount(0);
  await page
    .getByLabel("Webhook URL", { exact: true })
    .fill("https://example.invalid/private-webhook");
  await page
    .getByLabel("Webhook 请求头（JSON）")
    .fill('{"Authorization":"Bearer private-webhook-token"}');
  await page
    .getByLabel("Webhook 请求体模板")
    .fill('{"text":"{{message}}","secret":"private-webhook-body"}');
  await page.getByLabel("Webhook 请求方法").selectOption("PATCH");
  await page.getByRole("button", { name: "保存通知配置", exact: true }).click();
  await expect(page.getByLabel("Webhook URL", { exact: true })).toHaveValue("");
  await expect(page.getByLabel("Webhook 请求头（JSON）")).toHaveValue("");
  await expect(page.getByLabel("Webhook 请求体模板")).toHaveValue("");
  const webhookSettings = await (
    await page.request.get("/api/v1/settings")
  ).json();
  expect(webhookSettings.notifications.webhook_method).toBe("PATCH");
  expect(webhookSettings.notifications.webhook_headers_configured).toBe(true);
  expect(JSON.stringify(webhookSettings)).not.toContain("private-webhook");
  await page.getByLabel("Webhook 请求头（JSON）").fill('{"bad":1}');
  await expect(
    page.getByRole("button", { name: "保存通知配置", exact: true }),
  ).toBeDisabled();
  await page.getByLabel("Webhook 请求头（JSON）").fill("{}");
  await page
    .getByRole("button", { name: "恢复默认请求体", exact: true })
    .click();
  await page.getByRole("button", { name: "保存通知配置", exact: true }).click();
  await expect(page.getByLabel("Webhook 请求头（JSON）")).toHaveValue("");
  const clearedWebhook = await (
    await page.request.get("/api/v1/settings")
  ).json();
  expect(clearedWebhook.notifications.webhook_url_configured).toBe(true);
  expect(clearedWebhook.notifications.webhook_headers_configured).toBe(false);
  expect(clearedWebhook.notifications.webhook_body_configured).toBe(false);
  await expect(
    page.getByRole("heading", { name: "邮件通知", exact: true }),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBeTruthy();
  expect(errors).toEqual([]);
});

test("未登录不能读取设置或运行任务", async ({ request }) => {
  expect((await request.get("/api/v1/settings")).status()).toBe(401);
  expect((await request.post("/api/v1/runs/execute")).status()).toBe(401);
});
