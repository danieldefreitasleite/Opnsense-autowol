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


class TestHostArgumentDecodingAndMatching(unittest.TestCase):
    def test_decode_host_argument_formats(self):
        from autowol import decode_host_argument

        # Raw string
        self.assertEqual(decode_host_argument("Servidor NAS"), "Servidor NAS")

        # Hex encoded
        hex_val = binascii_hex = "Servidor NAS".encode("utf-8").hex()
        self.assertEqual(decode_host_argument(hex_val), "Servidor NAS")

        # Base64 encoded
        import base64
        b64_val = base64.b64encode("Estação Windows 11".encode("utf-8")).decode("utf-8")
        self.assertEqual(decode_host_argument(b64_val), "Estação Windows 11")

    @patch("autowol.send_magic_packet")
    def test_wake_matching_uuid_name_ip_mac(self, mock_wol):
        mock_wol.return_value = (True, "Magic packet sent")
        cfg = {
            "settings": {"default_broadcast_ip": "192.168.1.255", "default_wol_port": 9},
            "hosts": [
                {
                    "id": "c83e7428-1b54-469b-8e2b-f89a9f23e4d1",
                    "name": "Servidor NAS",
                    "ip": "192.168.1.50",
                    "mac": "00:11:32:AA:BB:CC",
                    "enabled": True
                }
            ]
        }
        engine = AutoWoLEngine(cfg)

        # Match by UUID
        ok, msg = engine.wake_single_host("c83e7428-1b54-469b-8e2b-f89a9f23e4d1")
        self.assertTrue(ok)
        self.assertIn("Servidor NAS", msg)

        # Match by Name (case insensitive)
        ok, msg = engine.wake_single_host("servidor nas")
        self.assertTrue(ok)

        # Match by IP
        ok, msg = engine.wake_single_host("192.168.1.50")
        self.assertTrue(ok)

        # Match by MAC (hyphen format)
        ok, msg = engine.wake_single_host("00-11-32-aa-bb-cc")
        self.assertTrue(ok)

        # Direct MAC address fallback (even if unlisted)
        ok, msg = engine.wake_single_host("AA:BB:CC:11:22:33")
        self.assertTrue(ok)
        self.assertIn("AA:BB:CC:11:22:33", msg)


class TestOPNsenseXmlParsing(unittest.TestCase):
    def test_parse_sample_opnsense_xml(self):
        from autowol import load_from_opnsense_xml
        import tempfile

        sample_xml = """<?xml version="1.0"?>
<opnsense>
  <OPNsense>
    <AutoWoL>
      <general>
        <enabled>1</enabled>
        <interval>5</interval>
        <retry_mode>cron</retry_mode>
        <default_broadcast_ip>192.168.1.255</default_broadcast_ip>
        <default_wol_port>9</default_wol_port>
        <check_timeout_seconds>3</check_timeout_seconds>
        <max_retries>4</max_retries>
        <boot_grace_period_seconds>90</boot_grace_period_seconds>
      </general>
      <hosts>
        <host uuid="uuid-test-1234">
          <enabled>1</enabled>
          <name>Desktop Escritório</name>
          <ip>192.168.1.80</ip>
          <mac>aa:bb:cc:dd:ee:01</mac>
          <check_method>both</check_method>
          <tcp_port>3389</tcp_port>
        </host>
      </hosts>
      <notifications>
        <telegram>
          <enabled>1</enabled>
          <bot_token>123456:ABC</bot_token>
          <chat_id>987654</chat_id>
        </telegram>
      </notifications>
    </AutoWoL>
  </OPNsense>
</opnsense>
"""
        with tempfile.NamedTemporaryFile("w", suffix=".xml", delete=False, encoding="utf-8") as tf:
            tf.write(sample_xml)
            tf_path = tf.name

        try:
            cfg = load_from_opnsense_xml(tf_path)
            self.assertIsNotNone(cfg)
            self.assertEqual(cfg["settings"]["interval"] if "interval" in cfg["settings"] else cfg["settings"]["max_retries"], 4)
            self.assertEqual(len(cfg["hosts"]), 1)
            h = cfg["hosts"][0]
            self.assertEqual(h["id"], "uuid-test-1234")
            self.assertEqual(h["name"], "Desktop Escritório")
            self.assertEqual(h["tcp_port"], 3389)
            self.assertTrue(cfg["notifications"]["telegram"]["enabled"])
        finally:
            if os.path.exists(tf_path):
                os.remove(tf_path)


if __name__ == "__main__":
    unittest.main()
