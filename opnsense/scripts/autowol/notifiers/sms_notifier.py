#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AutoWoL - SMS Notifier
Supports Twilio SMS and Generic HTTP SMS Gateways (e.g. Android SMS Gateways, Modem APIs).
"""

import json
import base64
import logging
import urllib.parse
import urllib.request

logger = logging.getLogger("autowol.notifiers.sms")


def _send_twilio_sms(cfg: dict, message: str) -> tuple[bool, str]:
    account_sid = cfg.get("account_sid")
    auth_token = cfg.get("auth_token")
    from_num = cfg.get("from_number")
    to_num = cfg.get("phone")

    if not account_sid or not auth_token or not from_num or not to_num:
        return False, "Twilio SMS requires 'account_sid', 'auth_token', 'from_number', and 'phone'."

    url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"
    form_data = urllib.parse.urlencode({
        "From": from_num,
        "To": to_num,
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
            return True, f"Twilio SMS sent successfully (status {resp.status})"
    except Exception as e:
        return False, f"Twilio SMS request failed: {e}"


def _send_http_gateway(cfg: dict, message: str) -> tuple[bool, str]:
    url_template = cfg.get("url")
    phone = cfg.get("phone", "")
    method = (cfg.get("method") or "GET").upper()

    if not url_template:
        return False, "HTTP SMS gateway requires 'url'."

    encoded_msg = urllib.parse.quote(message)
    encoded_phone = urllib.parse.quote(phone)

    target_url = url_template.replace("{phone}", encoded_phone).replace("{message}", encoded_msg)

    headers = cfg.get("headers") or {}
    if "User-Agent" not in headers:
        headers["User-Agent"] = "OPNsense-AutoWoL/1.0"

    data = None
    if method == "POST":
        payload_template = cfg.get("payload_template")
        if payload_template and isinstance(payload_template, dict):
            payload_str = json.dumps(payload_template)
            payload_str = payload_str.replace("{phone}", phone).replace("{message}", message)
            data = payload_str.encode("utf-8")
            if "Content-Type" not in headers:
                headers["Content-Type"] = "application/json"
        else:
            data = urllib.parse.urlencode({"phone": phone, "message": message}).encode("utf-8")
            if "Content-Type" not in headers:
                headers["Content-Type"] = "application/x-www-form-urlencoded"

    req = urllib.request.Request(target_url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return True, f"HTTP SMS gateway sent successfully (HTTP {resp.status})"
    except Exception as e:
        return False, f"HTTP SMS gateway request failed: {e}"


def send_sms(config: dict, message: str) -> tuple[bool, str]:
    """
    Dispatches SMS to configured provider.
    Supported providers:
      - 'twilio'
      - 'http_gateway'
    """
    if not config.get("enabled", False):
        return True, "SMS notification disabled in configuration."

    provider = (config.get("provider") or "twilio").lower()

    if provider == "twilio":
        return _send_twilio_sms(config, message)
    elif provider in ("http_gateway", "gateway", "http"):
        return _send_http_gateway(config, message)
    else:
        return False, f"Unsupported SMS provider '{provider}'."
