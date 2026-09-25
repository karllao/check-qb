from email.message import EmailMessage
import json
import re
import smtplib
import ssl
from urllib.parse import quote

import httpx

from .models import Notifications


def render_template(value, variables):
    if isinstance(value, str):
        return re.sub(r"\{\{(title|message|event)\}\}", lambda m: variables[m[1]], value)
    if isinstance(value, list):
        return [render_template(item, variables) for item in value]
    if isinstance(value, dict):
        return {key: render_template(item, variables) for key, item in value.items()}
    return value


def send_webhook(settings: Notifications, title: str, message: str, event: str):
    variables = {"title": title, "message": message, "event": event}
    url = render_template(settings.webhook_url, {k: quote(v, safe="") for k, v in variables.items()})
    headers = httpx.Headers(settings.webhook_headers)
    payload = {}
    if settings.webhook_method != "GET":
        if settings.webhook_format == "text":
            payload["content"] = render_template(settings.webhook_body or "{{message}}", variables).encode("utf-8")
            headers.setdefault("Content-Type", "text/plain; charset=utf-8")
        else:
            body = render_template(json.loads(settings.webhook_body), variables) if settings.webhook_body else variables
            payload["json" if settings.webhook_format == "json" else "data"] = body
    response = httpx.request(
        settings.webhook_method, url, headers=headers, timeout=settings.webhook_timeout,
        follow_redirects=False, **payload,
    )
    response.raise_for_status()


def notify(settings: Notifications, title: str, message: str, event="summary", force=False):
    results = []
    if not force and event not in settings.events:
        return results
    if settings.webhook_enabled:
        try:
            send_webhook(settings, title, message, event)
            results.append({"channel": "Webhook", "status": "success"})
        except Exception:
            results.append({"channel": "Webhook", "status": "failed", "reason": "通知发送失败，请检查配置"})
    if settings.smtp_enabled:
        try:
            mail = EmailMessage()
            mail["Subject"] = title
            mail["From"] = settings.smtp_from
            mail["To"] = ", ".join(settings.smtp_to)
            mail.set_content(message)
            context = ssl.create_default_context()
            if settings.smtp_security == "ssl":
                client = smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=15, context=context)
            else:
                client = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15)
            with client:
                if settings.smtp_security == "starttls":
                    client.starttls(context=context)
                if settings.smtp_username:
                    client.login(settings.smtp_username, settings.smtp_password)
                client.send_message(mail)
            results.append({"channel": "SMTP", "status": "success"})
        except Exception:
            results.append({"channel": "SMTP", "status": "failed", "reason": "邮件发送失败，请检查配置"})
    return results
