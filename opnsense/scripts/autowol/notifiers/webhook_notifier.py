#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AutoWoL - Webhook Notifier
Supports Discord, Slack, Ntfy.sh, and Generic JSON Webhooks (n8n, Home Assistant, etc.)
"""

import json
import logging
import urllib.request

logger = logging.getLogger("autowol.notifiers.webhook")


def _send_discord(cfg: dict, message: str, event: str, host: dict) -> tuple[bool, str]:
    url = cfg.get("url")
    if not url:
        return False, "Discord webhook requires 'url'."

    is_recovered = event == "recovery"
    color = 0x2ECC71 if is_recovered else 0xE74C3C  # Green or Red
    title = f"✅ Host Online: {host.get('name', 'Unknown')}" if is_recovered else f"🚨 AutoWoL Falha: {host.get('name', 'Unknown')}"

    embed = {
        "title": title,
        "description": message,
        "color": color,
        "fields": [
            {"name": "Host", "value": str(host.get("name")), "inline": True},
            {"name": "IP", "value": str(host.get("ip")), "inline": True},
            {"name": "MAC", "value": str(host.get("mac")), "inline": True}
        ],
        "footer": {"text": "OPNsense AutoWoL Monitor"}
    }
    payload = json.dumps({"embeds": [embed]}).encode("utf-8")
    headers = {"Content-Type": "application/json", "User-Agent": "OPNsense-AutoWoL/1.0"}
    req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return True, f"Discord webhook delivered (status {resp.status})"
    except Exception as e:
        return False, f"Discord webhook failed: {e}"


def _send_ntfy(cfg: dict, message: str, event: str, host: dict) -> tuple[bool, str]:
    url = cfg.get("url")
    topic = cfg.get("topic")
    if not url and not topic:
        return False, "Ntfy requires either 'url' or 'topic'."

    target_url = url or f"https://ntfy.sh/{topic}"
    is_recovered = event == "recovery"
    priority = "3" if is_recovered else "5"  # High or Urgent
    tags = "heavy_check_mark" if is_recovered else "warning,skull"
    title = f"AutoWoL: {host.get('name')} {'Restabelecido' if is_recovered else 'FALHA DE BOOT'}"

    headers = {
        "Title": title,
        "Priority": priority,
        "Tags": tags,
        "User-Agent": "OPNsense-AutoWoL/1.0"
    }
    token = cfg.get("token")
    if token:
        headers["Authorization"] = f"Bearer {token}"

    data = message.encode("utf-8")
    req = urllib.request.Request(target_url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return True, f"Ntfy notification delivered (status {resp.status})"
    except Exception as e:
        return False, f"Ntfy notification failed: {e}"


def _send_generic_json(cfg: dict, message: str, event: str, host: dict) -> tuple[bool, str]:
    url = cfg.get("url")
    if not url:
        return False, "Generic webhook requires 'url'."

    payload = json.dumps({
        "event": event,
        "message": message,
        "host": host,
        "source": "opnsense-autowol"
    }).encode("utf-8")

    headers = cfg.get("headers") or {}
    if "Content-Type" not in headers:
        headers["Content-Type"] = "application/json"
    if "User-Agent" not in headers:
        headers["User-Agent"] = "OPNsense-AutoWoL/1.0"

    req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return True, f"Generic webhook delivered (status {resp.status})"
    except Exception as e:
        return False, f"Generic webhook failed: {e}"


def send_webhook(config: dict, message: str, event: str = "alert", host: dict = None) -> tuple[bool, str]:
    """
    Dispatches message to configured webhook.
    Supported types:
      - 'discord'
      - 'ntfy'
      - 'generic'
    """
    if not config.get("enabled", False):
        return True, "Webhook notification disabled in configuration."

    hook_type = (config.get("type") or "generic").lower()
    host_info = host or {}

    if hook_type == "discord":
        return _send_discord(config, message, event, host_info)
    elif hook_type == "ntfy":
        return _send_ntfy(config, message, event, host_info)
    else:
        return _send_generic_json(config, message, event, host_info)
