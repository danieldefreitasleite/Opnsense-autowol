#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AutoWoL - Email Notifier (SMTP)
Natively supports Plain, STARTTLS, and SSL connections.
"""

import ssl
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

logger = logging.getLogger("autowol.notifiers.email")


def send_email(
    config: dict,
    subject: str,
    message: str,
    html_message: str = None
) -> tuple[bool, str]:
    """
    Sends an email using standard SMTP.
    Config schema:
      host: str (e.g. 'smtp.gmail.com')
      port: int (default 587 or 465)
      username: str (optional)
      password: str (optional)
      use_tls: bool (default True)
      use_ssl: bool (default False)
      from_addr: str
      to_addrs: list[str] or comma-separated str
    """
    if not config.get("enabled", False):
        return True, "Email notification disabled in configuration."

    smtp_host = config.get("host")
    if not smtp_host:
        return False, "SMTP host is missing in configuration."

    use_ssl = config.get("use_ssl", False)
    use_tls = config.get("use_tls", not use_ssl)
    default_port = 465 if use_ssl else (587 if use_tls else 25)
    smtp_port = int(config.get("port") or default_port)

    from_addr = config.get("from_addr") or config.get("username")
    to_addrs = config.get("to_addrs", [])
    if isinstance(to_addrs, str):
        to_addrs = [addr.strip() for addr in to_addrs.split(",") if addr.strip()]

    if not from_addr or not to_addrs:
        return False, "Email sender (from_addr) or recipients (to_addrs) not configured."

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = ", ".join(to_addrs)

    msg.attach(MIMEText(message, "plain", "utf-8"))
    if html_message:
        msg.attach(MIMEText(html_message, "html", "utf-8"))

    try:
        if use_ssl:
            context = ssl.create_default_context()
            server = smtplib.SMTP_SSL(smtp_host, smtp_port, context=context, timeout=15)
        else:
            server = smtplib.SMTP(smtp_host, smtp_port, timeout=15)
            if use_tls:
                context = ssl.create_default_context()
                server.starttls(context=context)

        username = config.get("username")
        password = config.get("password")
        if username and password:
            server.login(username, password)

        server.sendmail(from_addr, to_addrs, msg.as_string())
        server.quit()
        msg_ok = f"Email sent successfully to {', '.join(to_addrs)}"
        logger.info(msg_ok)
        return True, msg_ok
    except Exception as e:
        err_msg = f"Failed to send email via {smtp_host}:{smtp_port}: {e}"
        logger.error(err_msg)
        return False, err_msg
