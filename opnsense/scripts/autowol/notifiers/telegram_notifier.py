#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AutoWoL - Telegram Bot Notifier
Zero cost, instant, highly reliable notification channel for homelabs and sysadmins.
"""

import json
import logging
import urllib.parse
import urllib.request

logger = logging.getLogger("autowol.notifiers.telegram")


def send_telegram(config: dict, message: str) -> tuple[bool, str]:
    """
    Sends a message via Telegram Bot API.
    Config schema:
      bot_token: str (e.g. '123456789:ABCdefGHIjklMNOpqrsTUVwxyz')
      chat_id: str or int (e.g. '12345678' or '-100123456789')
      parse_mode: str (optional: 'HTML' or 'Markdown', default 'HTML')
    """
    if not config.get("enabled", False):
        return True, "Telegram notification disabled in configuration."

    bot_token = config.get("bot_token")
    chat_id = config.get("chat_id")
    if not bot_token or not chat_id:
        return False, "Telegram requires 'bot_token' and 'chat_id'."

    parse_mode = config.get("parse_mode", "HTML")
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"

    payload = json.dumps({
        "chat_id": chat_id,
        "text": message,
        "parse_mode": parse_mode,
        "disable_web_page_preview": True
    }).encode("utf-8")

    headers = {
        "Content-Type": "application/json",
        "User-Agent": "OPNsense-AutoWoL/1.0"
    }

    req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="ignore"))
            if data.get("ok"):
                return True, "Telegram message sent successfully."
            else:
                return False, f"Telegram API error: {data.get('description')}"
    except Exception as e:
        return False, f"Telegram request failed: {e}"
