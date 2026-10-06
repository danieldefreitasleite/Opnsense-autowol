#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AutoWoL - WhatsApp Notifier
Supports CallMeBot (free), Evolution API, Z-API, Twilio WhatsApp, and Custom Webhooks.
Uses standard Python urllib without external libraries.
"""

import json
import base64
import logging
import urllib.parse
import urllib.request

logger = logging.getLogger("autowol.notifiers.whatsapp")


def _send_callmebot(cfg: dict, message: str) -> tuple[bool, str]:
    phone = cfg.get("phone")
    apikey = cfg.get("apikey")
    if not phone or not apikey:
        return False, "CallMeBot requires 'phone' and 'apikey'."

    params = {
        "phone": phone,
        "text": message,
        "apikey": apikey
    }
    url = f"https://api.callmebot.com/whatsapp.php?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": "OPNsense-AutoWoL/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = resp.read().decode("utf-8", errors="ignore")
            return True, f"CallMeBot response: {body.strip()[:100]}"
    except Exception as e:
        return False, f"CallMeBot request failed: {e}"


def _send_evolution_api(cfg: dict, message: str) -> tuple[bool, str]:
    server_url = (cfg.get("server_url") or "").rstrip("/")
    instance = cfg.get("instance")
    api_key = cfg.get("apikey")
    number = cfg.get("phone")

    if not server_url or not instance or not number:
        return False, "Evolution API requires 'server_url', 'instance', and 'phone'."

    endpoint = f"{server_url}/message/sendText/{instance}"
    payload = json.dumps({"number": number, "text": message}).encode("utf-8")

    headers = {
        "Content-Type": "application/json",
        "apikey": api_key or "",
        "User-Agent": "OPNsense-AutoWoL/1.0"
    }
    req = urllib.request.Request(endpoint, data=payload, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = resp.read().decode("utf-8", errors="ignore")
            return True, f"Evolution API success: {data[:120]}"
    except Exception as e:
        return False, f"Evolution API request failed: {e}"


def _send_z_api(cfg: dict, message: str) -> tuple[bool, str]:
    instance = cfg.get("instance")
    token = cfg.get("token")
    client_token = cfg.get("client_token")
    phone = cfg.get("phone")

    if not instance or not token or not phone:
        return False, "Z-API requires 'instance', 'token', and 'phone'."

    endpoint = f"https://api.z-api.io/instances/{instance}/token/{token}/send-text"
    payload = json.dumps({"phone": phone, "message": message}).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "OPNsense-AutoWoL/1.0"
    }
    if client_token:
        headers["Client-Token"] = client_token

    req = urllib.request.Request(endpoint, data=payload, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return True, f"Z-API success status {resp.status}"
    except Exception as e:
        return False, f"Z-API request failed: {e}"


def _send_twilio_whatsapp(cfg: dict, message: str) -> tuple[bool, str]:
    account_sid = cfg.get("account_sid")
    auth_token = cfg.get("auth_token")
    from_num = cfg.get("from_number")
    to_num = cfg.get("phone")

    if not account_sid or not auth_token or not from_num or not to_num:
        return False, "Twilio requires 'account_sid', 'auth_token', 'from_number', and 'phone'."

    from_val = from_num if from_num.startswith("whatsapp:") else f"whatsapp:{from_num}"
    to_val = to_num if to_num.startswith("whatsapp:") else f"whatsapp:{to_num}"

    url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"
    form_data = urllib.parse.urlencode({
        "From": from_val,
        "To": to_val,
        "Body": message
    }).encode("utf-8")

    auth_str = base64.b64encode(f"{account_sid}:{auth_token}".encode("utf-8")).decode("ascii")
    headers = {
        "Authorization": f"Basic {auth_str}",
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": "OPNsense-AutoWoL/1.0"
    }

    req = urllib.request.Request(url, data=form_data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return True, f"Twilio WhatsApp message queued (status {resp.status})"
    except Exception as e:
        return False, f"Twilio WhatsApp request failed: {e}"


def _send_custom_webhook(cfg: dict, message: str) -> tuple[bool, str]:
    url = cfg.get("url")
    if not url:
        return False, "Custom webhook requires 'url'."

    payload_template = cfg.get("payload_template")
    if payload_template and isinstance(payload_template, dict):
        payload_str = json.dumps(payload_template).replace("{{message}}", message)
        data = payload_str.encode("utf-8")
    else:
        data = json.dumps({"message": message}).encode("utf-8")

    headers = cfg.get("headers") or {}
    if "Content-Type" not in headers:
        headers["Content-Type"] = "application/json"
    headers["User-Agent"] = "OPNsense-AutoWoL/1.0"

    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return True, f"Custom WhatsApp webhook success: HTTP {resp.status}"
    except Exception as e:
        return False, f"Custom WhatsApp webhook request failed: {e}"


def send_whatsapp(config: dict, message: str) -> tuple[bool, str]:
    """
    Dispatches WhatsApp message to configured provider.
    Supported providers:
      - 'callmebot'
      - 'evolution_api'
      - 'z_api'
      - 'twilio'
      - 'custom_webhook'
    """
    if not config.get("enabled", False):
        return True, "WhatsApp notification disabled in configuration."

    provider = (config.get("provider") or "callmebot").lower()

    if provider == "callmebot":
        return _send_callmebot(config, message)
    elif provider in ("evolution_api", "evolution"):
        return _send_evolution_api(config, message)
    elif provider in ("z_api", "zapi"):
        return _send_z_api(config, message)
    elif provider == "twilio":
        return _send_twilio_whatsapp(config, message)
    elif provider in ("webhook", "custom_webhook"):
        return _send_custom_webhook(config, message)
    else:
        return False, f"Unsupported WhatsApp provider '{provider}'."
