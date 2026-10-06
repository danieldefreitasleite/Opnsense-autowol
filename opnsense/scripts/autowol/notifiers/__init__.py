#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AutoWoL Notification Hub
Coordinates multi-channel alerts across WhatsApp, Email, SMS, Telegram, and Webhooks.
"""

import logging
from datetime import datetime

from .email_notifier import send_email
from .whatsapp_notifier import send_whatsapp
from .sms_notifier import send_sms
from .telegram_notifier import send_telegram
from .webhook_notifier import send_webhook

logger = logging.getLogger("autowol.notifiers")


def format_messages(host: dict, event: str, attempts: int, max_retries: int) -> tuple[str, str, str]:
    """
    Returns (subject, plain_text, html_text) formatted for the given event.
    """
    host_name = host.get("name", "Desconhecido")
    host_ip = host.get("ip", "N/A")
    host_mac = host.get("mac", "N/A")
    now_str = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

    if event == "recovery":
        subject = f"[OPNsense AutoWoL] RESTABELECIDO: {host_name} está Online"
        plain = (
            f"✅ RESTABELECIDO: O host '{host_name}' voltou a responder na rede!\n\n"
            f"• IP: {host_ip}\n"
            f"• MAC: {host_mac}\n"
            f"• Data/Hora: {now_str}\n"
            f"• Status: Operacional / Online\n"
        )
        html = f"""
        <html>
        <body style="font-family: Arial, sans-serif; color: #333;">
            <div style="background-color: #2ECC71; color: white; padding: 15px; border-radius: 5px;">
                <h2>✅ Host Restabelecido</h2>
            </div>
            <p>O host <strong>{host_name}</strong> voltou a responder e está totalmente operacional.</p>
            <ul>
                <li><strong>IP:</strong> {host_ip}</li>
                <li><strong>MAC:</strong> {host_mac}</li>
                <li><strong>Horário:</strong> {now_str}</li>
            </ul>
            <hr>
            <small>OPNsense AutoWoL Monitor Service</small>
        </body>
        </html>
        """
    else:
        subject = f"[OPNsense AutoWoL] ALERTA CRÍTICO: {host_name} Inoperante após {attempts} tentativas"
        plain = (
            f"🚨 ALERTA CRÍTICO: O host '{host_name}' falhou ao iniciar!\n\n"
            f"Foram enviadas {attempts} tentativas de Wake-on-LAN (máximo permitido: {max_retries}), "
            f"mas o equipamento continua sem responder.\n\n"
            f"• IP: {host_ip}\n"
            f"• MAC: {host_mac}\n"
            f"• Tentativas WoL: {attempts}/{max_retries}\n"
            f"• Data/Hora: {now_str}\n"
            f"• Ação recomendada: Verificar cabeamento, energia ou hardware no local.\n"
        )
        html = f"""
        <html>
        <body style="font-family: Arial, sans-serif; color: #333;">
            <div style="background-color: #E74C3C; color: white; padding: 15px; border-radius: 5px;">
                <h2>🚨 Falha de Inicialização do Host</h2>
            </div>
            <p>O host <strong>{host_name}</strong> não iniciou após <strong>{attempts}</strong> tentativas de Wake-on-LAN.</p>
            <ul>
                <li><strong>IP:</strong> {host_ip}</li>
                <li><strong>MAC:</strong> {host_mac}</li>
                <li><strong>Tentativas realizadas:</strong> {attempts} de {max_retries}</li>
                <li><strong>Horário:</strong> {now_str}</li>
            </ul>
            <p style="color: #c0392b;"><strong>Ação requerida:</strong> Inspecione fisicamente a máquina ou a fonte de energia.</p>
            <hr>
            <small>OPNsense AutoWoL Monitor Service</small>
        </body>
        </html>
        """
    return subject, plain, html


def dispatch_alerts(
    notifications_cfg: dict,
    host: dict,
    event: str = "alert",
    attempts: int = 1,
    max_retries: int = 3
) -> dict[str, tuple[bool, str]]:
    """
    Sends alerts to all enabled notification channels.
    Returns a dictionary mapping channel_name -> (success: bool, status_message: str).
    """
    subject, plain_text, html_text = format_messages(host, event, attempts, max_retries)
    results = {}

    # Email
    email_cfg = notifications_cfg.get("email", {})
    if email_cfg.get("enabled", False):
        results["email"] = send_email(email_cfg, subject, plain_text, html_text)

    # WhatsApp
    wa_cfg = notifications_cfg.get("whatsapp", {})
    if wa_cfg.get("enabled", False):
        results["whatsapp"] = send_whatsapp(wa_cfg, plain_text)

    # SMS
    sms_cfg = notifications_cfg.get("sms", {})
    if sms_cfg.get("enabled", False):
        results["sms"] = send_sms(sms_cfg, plain_text)

    # Telegram
    tg_cfg = notifications_cfg.get("telegram", {})
    if tg_cfg.get("enabled", False):
        results["telegram"] = send_telegram(tg_cfg, plain_text)

    # Webhook
    hook_cfg = notifications_cfg.get("webhook", {})
    if hook_cfg.get("enabled", False):
        results["webhook"] = send_webhook(hook_cfg, plain_text, event=event, host=host)

    for ch, (ok, detail) in results.items():
        if ok:
            logger.info(f"[{ch.upper()}] Notificação enviada: {detail}")
        else:
            logger.error(f"[{ch.upper()}] Falha ao enviar notificação: {detail}")

    return results
