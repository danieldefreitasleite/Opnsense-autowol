#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Automated Unit Tests for AutoWoL
Runs locally or on CI without any external dependencies.
"""

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add script directory to python path
sys.path.insert(0, str(Path(__file__).parent.parent / "opnsense" / "scripts" / "autowol"))

from wol import normalize_mac, build_magic_packet, send_magic_packet
from prober import check_host
from notifiers import format_messages, dispatch_alerts
from notifiers.whatsapp_notifier import _send_callmebot, _send_evolution_api, _send_twilio_whatsapp
from notifiers.sms_notifier import _send_twilio_sms, _send_http_gateway
from notifiers.telegram_notifier import send_telegram
from notifiers.webhook_notifier import _send_discord, _send_ntfy
from autowol import AutoWoLEngine


class TestWakeOnLan(unittest.TestCase):
    def test_normalize_mac_formats(self):
        expected = bytes.fromhex("001122334455")
        self.assertEqual(normalize_mac("00:11:22:33:44:55"), expected)
        self.assertEqual(normalize_mac("00-11-22-33-44-55"), expected)
        self.assertEqual(normalize_mac("0011.2233.4455"), expected)
        self.assertEqual(normalize_mac("001122334455"), expected)
        self.assertEqual(normalize_mac("  00:11:22:33:44:55  "), expected)
        self.assertEqual(normalize_mac("00:11:22:33:44:55".upper()), expected)

    def test_normalize_mac_invalid(self):
        with self.assertRaises(ValueError):
            normalize_mac("00:11:22:33")
        with self.assertRaises(ValueError):
            normalize_mac("invalid_mac_string")

    def test_build_magic_packet_structure(self):
        mac_bytes = bytes.fromhex("AABBCCDDEEFF")
        packet = build_magic_packet(mac_bytes)
        self.assertEqual(len(packet), 102)
        self.assertTrue(packet.startswith(b"\xff" * 6))
        # 16 repetitions of MAC
        for i in range(16):
            start = 6 + (i * 6)
            end = start + 6
            self.assertEqual(packet[start:end], mac_bytes)

    @patch("socket.socket")
    def test_send_magic_packet_success(self, mock_socket_cls):
        mock_sock = MagicMock()
        mock_socket_cls.return_value = mock_sock

        ok, msg = send_magic_packet("AA:BB:CC:DD:EE:FF", "192.168.1.255", 9)
        self.assertTrue(ok)
        self.assertIn("Magic Packet sent", msg)
        mock_sock.sendto.assert_called_once()


class TestFormatMessages(unittest.TestCase):
    def test_format_alert_and_recovery(self):
        host = {"name": "Servidor Teste", "ip": "192.168.1.50", "mac": "AA:BB:CC:DD:EE:FF"}

        # Alert
        subj, plain, html = format_messages(host, "alert", 3, 3)
        self.assertIn("ALERTA CRÍTICO", subj)
        self.assertIn("Servidor Teste", plain)
        self.assertIn("3/3", plain)
        self.assertIn("192.168.1.50", html)

        # Recovery
        subj_rec, plain_rec, html_rec = format_messages(host, "recovery", 0, 3)
        self.assertIn("RESTABELECIDO", subj_rec)
        self.assertIn("Online", plain_rec)
        self.assertIn("Servidor Teste", html_rec)


class TestNotifiersPayloads(unittest.TestCase):
    @patch("urllib.request.urlopen")
    def test_callmebot_url_encoding(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = b"OK - Message Queued"
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        cfg = {"phone": "+5511999999999", "apikey": "secret123"}
        ok, res = _send_callmebot(cfg, "Teste de Alerta")
        self.assertTrue(ok)
        self.assertIn("OK - Message Queued", res)

        called_req = mock_urlopen.call_args[0][0]
        self.assertIn("phone=%2B5511999999999", called_req.full_url)
        self.assertIn("apikey=secret123", called_req.full_url)

    @patch("urllib.request.urlopen")
    def test_telegram_send(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = b'{"ok": true, "result": {}}'
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        cfg = {"enabled": True, "bot_token": "123:ABC", "chat_id": "99999"}
        ok, msg = send_telegram(cfg, "Mensagem de Teste")
        self.assertTrue(ok)
        self.assertIn("successfully", msg)

    @patch("urllib.request.urlopen")
    def test_discord_webhook(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.status = 204
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        cfg = {"url": "https://discord.com/api/webhooks/123/abc"}
        host = {"name": "Host1", "ip": "1.2.3.4", "mac": "aa:bb:cc:dd:ee:ff"}
        ok, msg = _send_discord(cfg, "Falha de teste", "alert", host)
        self.assertTrue(ok)
        self.assertIn("status 204", msg)


class TestAutoWoLEngineStateTransitions(unittest.TestCase):
    def setUp(self):
        self.test_cfg = {
            "settings": {
                "retry_mode": "cron",
                "max_retries": 2,
                "boot_grace_period_seconds": 0,
                "alert_cooldown_minutes": 60,
                "notify_on_recovery": True
            },
            "hosts": [
                {
                    "id": "test-srv",
                    "name": "Host Teste",
                    "ip": "192.168.1.99",
                    "mac": "11:22:33:44:55:66",
                    "enabled": True
                }
            ],
            "notifications": {
                "telegram": {"enabled": False}
            }
        }
        self.state_file = "./test_state.json"
        if os.path.exists(self.state_file):
            os.remove(self.state_file)

    def tearDown(self):
        if os.path.exists(self.state_file):
            os.remove(self.state_file)

    @patch("autowol.send_magic_packet")
    @patch("autowol.check_host")
    @patch("autowol.dispatch_alerts")
    def test_lifecycle_offline_to_alert_to_recovery(self, mock_dispatch, mock_check, mock_wol):
        mock_wol.return_value = (True, "sent")
        engine = AutoWoLEngine(self.test_cfg, state_path=self.state_file)

        # 1. First run: Host is offline -> sends WoL #1, status WAKING, attempts=1
        mock_check.return_value = (False, "icmp", "Host unreachable")
        res1 = engine.check_all_hosts()
        self.assertEqual(res1["test-srv"]["status"], "WAKING")
        self.assertEqual(res1["test-srv"]["attempts"], 1)
        mock_wol.assert_called_once()
        mock_dispatch.assert_not_called()

        # 2. Second run: Still offline -> sends WoL #2, status WAKING, attempts=2
        res2 = engine.check_all_hosts()
        self.assertEqual(res2["test-srv"]["status"], "WAKING")
        self.assertEqual(res2["test-srv"]["attempts"], 2)
        self.assertEqual(mock_wol.call_count, 2)
        mock_dispatch.assert_not_called()

        # 3. Third run: Still offline -> Exceeded max_retries (2) -> triggers ALERTED and dispatches alerts!
        res3 = engine.check_all_hosts()
        self.assertEqual(res3["test-srv"]["status"], "ALERTED")
        mock_dispatch.assert_called_once()
        self.assertEqual(mock_dispatch.call_args[1]["event"], "alert")

        # 4. Fourth run: Still offline, status is ALERTED -> in cooldown, no new alerts sent
        res4 = engine.check_all_hosts()
        self.assertEqual(res4["test-srv"]["status"], "ALERTED")
        self.assertEqual(mock_dispatch.call_count, 1)  # No second alert flood

        # 5. Fifth run: Host comes online! -> Status ONLINE, attempts reset to 0, recovery alert dispatched
        mock_check.return_value = (True, "icmp", "Host responded in 1ms")
        res5 = engine.check_all_hosts()
        self.assertEqual(res5["test-srv"]["status"], "ONLINE")
        self.assertEqual(engine.state["test-srv"]["attempts"], 0)
        self.assertEqual(mock_dispatch.call_count, 2)
        self.assertEqual(mock_dispatch.call_args[1]["event"], "recovery")


if __name__ == "__main__":
    unittest.main()
