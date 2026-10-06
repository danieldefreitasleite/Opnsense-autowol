#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AutoWoL - Main Daemon & CLI Controller for OPNsense
Monitors critical network hosts, dispatches Wake-on-LAN packets, and alerts via multiple channels.
"""

import os
import sys
import json
import time
import logging
import argparse
from pathlib import Path
from datetime import datetime

# Local module imports
from wol import send_magic_packet
from prober import check_host
from notifiers import dispatch_alerts

DEFAULT_CONFIG_PATHS = [
    "/usr/local/etc/autowol/config.json",
    "./etc/autowol/config.json",
    "./config.json"
]

DEFAULT_STATE_PATHS = [
    "/var/run/autowol_state.json",
    "./autowol_state.json"
]

DEFAULT_LOG_PATHS = [
    "/var/log/autowol.log",
    "./autowol.log"
]


class FlushingFileHandler(logging.FileHandler):
    def emit(self, record):
        super().emit(record)
        self.flush()


def setup_logging(verbose: bool = False, log_file: str = None) -> logging.Logger:
    """Configures logging to console and persistent log file."""
    logger = logging.getLogger("autowol")
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)
    logger.handlers.clear()

    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    target_log_file = log_file
    if not target_log_file:
        for p in DEFAULT_LOG_PATHS:
            try:
                parent = Path(p).parent
                if parent.exists() and os.access(parent, os.W_OK):
                    target_log_file = p
                    break
            except Exception:
                continue

    if target_log_file:
        try:
            file_handler = FlushingFileHandler(target_log_file, encoding="utf-8")
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
        except Exception as e:
            logger.warning(f"Could not open log file {target_log_file}: {e}")

    return logger


def load_from_opnsense_xml(xml_path: str = "/conf/config.xml") -> dict | None:
    """Parses OPNsense /conf/config.xml directly to extract live AutoWoL configuration."""
    p = Path(xml_path)
    if not p.is_file():
        return None
    try:
        import xml.etree.ElementTree as ET
        tree = ET.parse(str(p))
        root = tree.getroot()
        autowol_node = root.find(".//AutoWoL")
        if autowol_node is None:
            for elem in root.iter():
                if elem.tag.lower() == "autowol":
                    autowol_node = elem
                    break
        if autowol_node is None:
            return None

        # Parse general settings
        general = {}
        gen_node = autowol_node.find("general")
        if gen_node is not None:
            for child in gen_node:
                general[child.tag] = child.text.strip() if child.text else ""

        # Parse hosts
        hosts = []
        hosts_node = autowol_node.find("hosts")
        if hosts_node is not None:
            for h in hosts_node.findall("host"):
                h_uuid = h.attrib.get("uuid", "")
                h_dict = {"id": h_uuid}
                for child in h:
                    h_dict[child.tag] = child.text.strip() if child.text else ""

                if not h_dict.get("name") and not h_dict.get("mac") and not h_dict.get("ip"):
                    continue

                h_dict["enabled"] = str(h_dict.get("enabled", "1")).strip() in ("1", "true", "True")
                try:
                    h_dict["wol_port"] = int(h_dict.get("wol_port") or 9)
                except (ValueError, TypeError):
                    h_dict["wol_port"] = 9
                try:
                    h_dict["max_retries"] = int(h_dict.get("max_retries") or 3)
                except (ValueError, TypeError):
                    h_dict["max_retries"] = 3
                try:
                    h_dict["boot_grace_period_seconds"] = int(h_dict.get("boot_grace_period_seconds") or 60)
                except (ValueError, TypeError):
                    h_dict["boot_grace_period_seconds"] = 60

                tcp_p = h_dict.get("tcp_port")
                if tcp_p:
                    try:
                        h_dict["tcp_port"] = int(tcp_p)
                    except (ValueError, TypeError):
                        h_dict["tcp_port"] = None
                else:
                    h_dict["tcp_port"] = None

                hosts.append(h_dict)

        # Parse notifications
        notifications = {}
        notif_node = autowol_node.find("notifications")
        if notif_node is not None:
            for ch in notif_node:
                ch_dict = {}
                for child in ch:
                    val = child.text.strip() if child.text else ""
                    if child.tag in ("enabled", "use_tls", "use_ssl"):
                        ch_dict[child.tag] = val in ("1", "true", "True")
                    elif child.tag == "port":
                        try:
                            ch_dict["port"] = int(val)
                        except (ValueError, TypeError):
                            ch_dict["port"] = 587
                    elif child.tag == "to_addrs":
                        ch_dict["to_addrs"] = [x.strip() for x in val.split(",") if x.strip()]
                    else:
                        ch_dict[child.tag] = val
                notifications[ch.tag] = ch_dict

        return {
            "settings": {
                "retry_mode": general.get("retry_mode", "cron"),
                "default_broadcast_ip": general.get("default_broadcast_ip", "255.255.255.255"),
                "default_wol_port": int(general.get("default_wol_port") or 9),
                "check_timeout_seconds": float(general.get("check_timeout_seconds") or 2),
                "max_retries": int(general.get("max_retries") or 3),
                "boot_grace_period_seconds": int(general.get("boot_grace_period_seconds") or 60),
                "alert_cooldown_minutes": int(general.get("alert_cooldown_minutes") or 120),
                "repeat_alerts": str(general.get("repeat_alerts", "0")).strip() in ("1", "true", "True"),
                "notify_on_recovery": str(general.get("notify_on_recovery", "1")).strip() in ("1", "true", "True"),
                "log_file": "/var/log/autowol.log"
            },
            "hosts": hosts,
            "notifications": notifications
        }
    except Exception as e:
        sys.stderr.write(f"Aviso ao ler XML {xml_path}: {e}\n")
        return None


def load_config(config_path: str = None) -> dict:
    """Loads configuration: checks explicit path, then /conf/config.xml, then config.json."""
    if config_path and Path(config_path).is_file():
        if config_path.endswith(".xml"):
            xml_cfg = load_from_opnsense_xml(config_path)
            if xml_cfg:
                return xml_cfg
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)

    # 1. Attempt reading live OPNsense config.xml directly
    xml_cfg = load_from_opnsense_xml("/conf/config.xml")
    if xml_cfg and xml_cfg.get("hosts"):
        return xml_cfg

    # 2. Check JSON config candidates
    for p in DEFAULT_CONFIG_PATHS:
        if p and Path(p).is_file():
            try:
                with open(p, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if xml_cfg and not data.get("hosts") and xml_cfg.get("hosts"):
                        data["hosts"] = xml_cfg["hosts"]
                    return data
            except Exception:
                continue

    # 3. Fall back to XML config even if hosts is empty
    if xml_cfg:
        return xml_cfg

    # 4. Fallback safe default
    return {
        "settings": {
            "retry_mode": "cron",
            "default_broadcast_ip": "255.255.255.255",
            "default_wol_port": 9,
            "check_timeout_seconds": 2.0,
            "max_retries": 3,
            "boot_grace_period_seconds": 60,
            "alert_cooldown_minutes": 120,
            "repeat_alerts": False,
            "notify_on_recovery": True,
            "log_file": "/var/log/autowol.log"
        },
        "hosts": [],
        "notifications": {}
    }


def load_state(state_path: str = None) -> tuple[dict, str]:
    """Loads persistent state file."""
    candidates = [state_path] if state_path else DEFAULT_STATE_PATHS
    target_path = None
    for p in candidates:
        if p:
            parent = Path(p).parent
            if parent.exists() and os.access(parent, os.W_OK):
                target_path = p
                break

    if not target_path:
        target_path = DEFAULT_STATE_PATHS[-1]

    if Path(target_path).is_file():
        try:
            with open(target_path, "r", encoding="utf-8") as f:
                return json.load(f), target_path
        except Exception:
            return {}, target_path
    return {}, target_path


def save_state(state: dict, state_path: str):
    """Atomically saves state to disk."""
    temp_path = f"{state_path}.tmp"
    with open(temp_path, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)
    os.replace(temp_path, state_path)


class AutoWoLEngine:
    def __init__(self, config: dict, state_path: str = None, logger: logging.Logger = None):
        self.config = config
        self.logger = logger or logging.getLogger("autowol.engine")
        self.state, self.state_file = load_state(state_path)
        self.settings = config.get("settings", {})
        self.notifications = config.get("notifications", {})
        self.hosts = config.get("hosts", [])

    def get_host_state(self, host_id: str) -> dict:
        if host_id not in self.state:
            self.state[host_id] = {
                "status": "UNKNOWN",
                "attempts": 0,
                "last_seen_online": None,
                "last_attempt_time": 0,
                "last_alert_time": 0
            }
        return self.state[host_id]

    def get_status_overview(self) -> list[dict]:
        """
        Returns a structured list of status for all configured hosts,
        combining configuration details with runtime state.
        """
        overview = []
        for host in self.hosts:
            h_id = host.get("id") or host.get("name")
            h_state = self.state.get(h_id, {})
            max_retries = int(host.get("max_retries") or self.settings.get("max_retries", 3))

            raw_status = h_state.get("status", "NOT_CHECKED")
            attempts = h_state.get("attempts", 0)
            last_seen = h_state.get("last_seen_online")
            last_details = h_state.get("last_details")

            last_seen_formatted = None
            if last_seen:
                try:
                    dt = datetime.fromisoformat(last_seen)
                    last_seen_formatted = dt.strftime("%d/%m/%Y %H:%M:%S")
                except Exception:
                    last_seen_formatted = str(last_seen)

            overview.append({
                "id": h_id,
                "name": host.get("name", h_id),
                "ip": host.get("ip", "N/A"),
                "mac": host.get("mac", "N/A"),
                "enabled": host.get("enabled", True),
                "check_method": host.get("check_method", "icmp"),
                "status": raw_status,
                "attempts": attempts,
                "max_retries": max_retries,
                "last_seen_online": last_seen_formatted or "Ainda não detectado",
                "last_details": last_details or "Aguardando primeira verificação"
            })
        return overview

    def check_all_hosts(self) -> dict[str, dict]:
        """Iterates over all enabled hosts and performs check / wake / alert lifecycle."""
        enabled_hosts = [h for h in self.hosts if h.get("enabled", True)]
        if not enabled_hosts:
            self.logger.info("=== Ciclo de Checagem AutoWoL: Nenhuma máquina cadastrada ou ativa para monitorar ===")
            return {}

        self.logger.info(f"=== Ciclo de Checagem AutoWoL Iniciado ({len(enabled_hosts)} hosts ativos) ===")
        results = {}
        for host in enabled_hosts:
            h_id = host.get("id") or host.get("name")
            self.logger.info(f"[Host: {host.get('name')}] Iniciando verificação IP: {host.get('ip')}...")
            results[h_id] = self.process_host(host)

        save_state(self.state, self.state_file)
        self.logger.info(f"=== Ciclo de Checagem AutoWoL Finalizado. Estado persistido em {self.state_file} ===")
        return results

    def process_host(self, host: dict) -> dict:
        h_id = host.get("id") or host.get("name")
        h_name = host.get("name", h_id)
        ip = host.get("ip")
        mac = host.get("mac")
        bcast = host.get("broadcast_ip") or self.settings.get("default_broadcast_ip", "255.255.255.255")
        port = int(host.get("wol_port") or self.settings.get("default_wol_port", 9))
        method = host.get("check_method") or "icmp"
        tcp_port = host.get("tcp_port")
        timeout_sec = float(host.get("check_timeout_seconds") or self.settings.get("check_timeout_seconds", 2.0))

        max_retries = int(host.get("max_retries") or self.settings.get("max_retries", 3))
        grace_period = int(host.get("boot_grace_period_seconds") or self.settings.get("boot_grace_period_seconds", 60))
        cooldown_mins = int(self.settings.get("alert_cooldown_minutes", 120))
        notify_recovery = self.settings.get("notify_on_recovery", True)
        mode = host.get("retry_mode") or self.settings.get("retry_mode", "cron")

        h_state = self.get_host_state(h_id)
        now_ts = time.time()
        now_iso = datetime.now().isoformat()

        # Step 1: Probe host
        online, probe_method, details = check_host(ip, method, tcp_port, timeout_sec)
        h_state["last_details"] = details
        self.logger.debug(f"Host {h_name} probe: online={online} method={probe_method} details={details}")

        if online:
            prev_status = h_state.get("status")
            h_state["last_seen_online"] = now_iso
            h_state["status"] = "ONLINE"
            h_state["attempts"] = 0

            if prev_status in ("WAKING", "ALERTED"):
                self.logger.info(f"Host '{h_name}' RESTABELECIDO com sucesso!")
                if notify_recovery:
                    dispatch_alerts(self.notifications, host, event="recovery")
            else:
                self.logger.info(f"Host '{h_name}' está ONLINE ({details}).")

            return {"status": "ONLINE", "details": details}

        # Step 2: Host is OFFLINE
        self.logger.warning(f"Host '{h_name}' está OFFLINE ({details})")

        if mode == "immediate":
            return self._handle_immediate_mode(host, h_state, details, max_retries, grace_period)
        else:
            return self._handle_cron_mode(host, h_state, details, max_retries, grace_period, cooldown_mins, now_ts)

    def _handle_cron_mode(self, host, h_state, details, max_retries, grace_period, cooldown_mins, now_ts):
        """Cron mode: progresses retry counter with each periodic check."""
        h_name = host.get("name")
        mac = host.get("mac")
        bcast = host.get("broadcast_ip") or self.settings.get("default_broadcast_ip", "255.255.255.255")
        port = int(host.get("wol_port") or self.settings.get("default_wol_port", 9))

        curr_status = h_state.get("status", "ONLINE")
        attempts = h_state.get("attempts", 0)
        last_attempt = h_state.get("last_attempt_time", 0)
        last_alert = h_state.get("last_alert_time", 0)

        # Check if still in boot grace period
        if curr_status == "WAKING" and (now_ts - last_attempt < grace_period):
            remaining = int(grace_period - (now_ts - last_attempt))
            self.logger.info(f"Host '{h_name}' está em fase de boot (restam {remaining}s de grace period). Aguardando.")
            return {"status": "WAKING", "attempts": attempts, "details": f"Booting ({remaining}s remaining)"}

        if attempts < max_retries:
            attempts += 1
            h_state["attempts"] = attempts
            h_state["status"] = "WAKING"
            h_state["last_attempt_time"] = now_ts
            self.logger.info(f"Enviando Wake-on-LAN para '{h_name}' (Tentativa {attempts}/{max_retries})...")
            send_magic_packet(mac, bcast, port)
            return {"status": "WAKING", "attempts": attempts, "details": f"WoL packet {attempts} sent"}
        else:
            # Exceeded max retries!
            if curr_status != "ALERTED":
                self.logger.critical(
                    f"Host '{h_name}' FALHOU ao iniciar após {attempts} tentativas de WoL. DISPARANDO ALERTAS!"
                )
                h_state["status"] = "ALERTED"
                h_state["last_alert_time"] = now_ts
                dispatch_alerts(self.notifications, host, event="alert", attempts=attempts, max_retries=max_retries)
                return {"status": "ALERTED", "attempts": attempts, "details": "Max retries exceeded, alerts sent"}
            else:
                # Already alerted, check cooldown
                cooldown_sec = cooldown_mins * 60
                if now_ts - last_alert >= cooldown_sec and self.settings.get("repeat_alerts", False):
                    self.logger.warning(f"Cooldown expirado. Reenviando alertas de falha para '{h_name}'...")
                    h_state["last_alert_time"] = now_ts
                    dispatch_alerts(self.notifications, host, event="alert", attempts=attempts, max_retries=max_retries)
                    return {"status": "ALERTED", "attempts": attempts, "details": "Alert re-sent after cooldown"}
                else:
                    self.logger.info(f"Host '{h_name}' permanece offline. Alertas em cooldown (nenhum flood).")
                    return {"status": "ALERTED", "attempts": attempts, "details": "In cooldown"}

    def _handle_immediate_mode(self, host, h_state, details, max_retries, grace_period):
        """Immediate mode: loops and verifies within the same execution run."""
        h_name = host.get("name")
        mac = host.get("mac")
        ip = host.get("ip")
        bcast = host.get("broadcast_ip") or self.settings.get("default_broadcast_ip", "255.255.255.255")
        port = int(host.get("wol_port") or self.settings.get("default_wol_port", 9))
        method = host.get("check_method") or "icmp"
        tcp_port = host.get("tcp_port")

        for attempt in range(1, max_retries + 1):
            h_state["attempts"] = attempt
            h_state["status"] = "WAKING"
            h_state["last_attempt_time"] = time.time()
            self.logger.info(f"[Modo Imediato] Enviando WoL para '{h_name}' (Tentativa {attempt}/{max_retries})...")
            send_magic_packet(mac, bcast, port)

            self.logger.info(f"[Modo Imediato] Aguardando {grace_period}s para inicialização da máquina...")
            time.sleep(grace_period)

            online, _, check_diag = check_host(ip, method, tcp_port)
            if online:
                self.logger.info(f"[Modo Imediato] Host '{h_name}' respondeu com sucesso! Boot OK.")
                h_state["status"] = "ONLINE"
                h_state["attempts"] = 0
                h_state["last_seen_online"] = datetime.now().isoformat()
                return {"status": "ONLINE", "details": f"Online after {attempt} WoL"}

        # If loop completed without coming online
        self.logger.critical(
            f"[Modo Imediato] Host '{h_name}' não ligou após {max_retries} tentativas. DISPARANDO ALERTAS!"
        )
        h_state["status"] = "ALERTED"
        h_state["last_alert_time"] = time.time()
        dispatch_alerts(self.notifications, host, event="alert", attempts=max_retries, max_retries=max_retries)
        return {"status": "ALERTED", "attempts": max_retries, "details": "Boot failed after all retries"}

    def wake_single_host(self, host_identifier: str) -> tuple[bool, str]:
        """
        Sends a manual Wake-on-LAN packet to a single host by UUID, Name, IP, or MAC.
        Returns (success: bool, message: str).
        """
        target = None
        ident_clean = host_identifier.strip().lower()
        ident_mac_clean = ident_clean.replace("-", ":").replace(".", "")

        for h in self.hosts:
            h_id = str(h.get("id", "")).strip().lower()
            h_name = str(h.get("name", "")).strip().lower()
            h_ip = str(h.get("ip", "")).strip().lower()
            h_mac = str(h.get("mac", "")).strip().lower().replace("-", ":").replace(".", "")

            if ident_clean in (h_id, h_name, h_ip) or (ident_mac_clean and ident_mac_clean == h_mac):
                target = h
                break

        # Fallback: check if the identifier itself is a MAC address
        import re
        mac_pattern = r"^([0-9a-fA-F]{2}[:-]){5}([0-9a-fA-F]{2})$|^[0-9a-fA-F]{12}$"
        if not target and re.match(mac_pattern, host_identifier.strip()):
            target = {
                "name": f"Dispositivo MAC ({host_identifier})",
                "mac": host_identifier.strip(),
                "broadcast_ip": self.settings.get("default_broadcast_ip", "255.255.255.255"),
                "wol_port": self.settings.get("default_wol_port", 9)
            }

        if not target:
            msg = f"Máquina '{host_identifier}' não encontrada na configuração."
            self.logger.error(msg)
            print(f"Erro: {msg}")
            return False, msg

        t_name = target.get("name") or host_identifier
        t_mac = target.get("mac")
        bcast = target.get("broadcast_ip") or self.settings.get("default_broadcast_ip", "255.255.255.255")
        port = int(target.get("wol_port") or self.settings.get("default_wol_port", 9))

        ok, wol_err = send_magic_packet(t_mac, bcast, port)
        if ok:
            succ_msg = f"Magic Packet (WoL) enviado com sucesso para '{t_name}' ({t_mac}) via {bcast}:{port}."
            self.logger.info(succ_msg)
            print(succ_msg)
            return True, succ_msg
        else:
            err_msg = f"Falha ao enviar WoL para '{t_name}' ({t_mac}): {wol_err}"
            self.logger.error(err_msg)
            print(f"Erro: {err_msg}")
            return False, err_msg

    def test_alert(self, channel: str = "all") -> dict:
        """Sends a test alert across notification channels."""
        test_host = {
            "id": "test-host",
            "name": "Servidor de Teste AutoWoL",
            "ip": "192.168.1.100",
            "mac": "AA:BB:CC:DD:EE:FF"
        }
        self.logger.info(f"Enviando alerta de teste para canal: {channel}...")
        cfg = self.notifications
        if channel != "all":
            # Filter config to only requested channel
            cfg = {channel: self.notifications.get(channel, {})}
            cfg[channel]["enabled"] = True

        return dispatch_alerts(cfg, test_host, event="alert", attempts=1, max_retries=3)


def decode_host_argument(raw_val: str) -> str:
    """Decodes host argument which may be hex-encoded, base64-encoded, or plain text."""
    if not raw_val:
        return ""
    val = raw_val.strip()

    # 1. Try Hex decode (only if even length and valid hex)
    if len(val) >= 2 and len(val) % 2 == 0 and all(c in "0123456789abcdefABCDEF" for c in val):
        try:
            decoded = bytes.fromhex(val).decode("utf-8")
            if decoded.isprintable():
                return decoded
        except Exception:
            pass

    # 2. Try Base64 decode
    try:
        import base64
        decoded = base64.b64decode(val.encode("utf-8")).decode("utf-8")
        if decoded.isprintable():
            return decoded
    except Exception:
        pass

    # 3. Plain text
    return val


def main():
    parser = argparse.ArgumentParser(description="OPNsense AutoWoL & Host Monitor Daemon")
    parser.add_argument(
        "--action",
        choices=["check", "wake", "status", "test-alert", "reset"],
        default="check",
        help="Action to execute"
    )
    parser.add_argument("--config", "-c", help="Path to config.json or config.xml")
    parser.add_argument("--state", "-s", help="Path to state.json")
    parser.add_argument("--host", help="Host ID, Name, or MAC for 'wake' action")
    parser.add_argument("--host-arg", help="Universal encoded Host ID, Name, or MAC for 'wake' action")
    parser.add_argument("--host-hex", help="Hex-encoded Host ID, Name, or MAC for 'wake' action")
    parser.add_argument("--host-b64", help="Base64-encoded Host ID, Name, or MAC for 'wake' action")
    parser.add_argument("--channel", default="all", help="Notification channel to test for 'test-alert'")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose debug output")

    args = parser.parse_args()

    # Setup logger immediately so any invocation is recorded in /var/log/autowol.log
    logger = setup_logging(verbose=args.verbose)

    cfg = load_config(args.config)
    log_file = cfg.get("settings", {}).get("log_file")
    if log_file:
        logger = setup_logging(verbose=args.verbose, log_file=log_file)

    engine = AutoWoLEngine(cfg, state_path=args.state, logger=logger)

    if args.action == "check":
        results = engine.check_all_hosts()
        print(json.dumps(results, indent=2))
    elif args.action == "wake":
        raw_val = args.host_arg or args.host_hex or args.host_b64 or args.host
        if not raw_val:
            err_msg = "Ação 'wake' requer o parâmetro de máquina/host."
            logger.error(err_msg)
            print(f"Erro: {err_msg}")
            sys.exit(1)

        host_target = decode_host_argument(raw_val)
        logger.info(f"Comando WoL manual solicitado para: '{host_target}'")
        ok, _ = engine.wake_single_host(host_target)
        sys.exit(0 if ok else 1)
    elif args.action == "status":
        overview = engine.get_status_overview()
        print(json.dumps(overview, ensure_ascii=False))
    elif args.action == "test-alert":
        results = engine.test_alert(args.channel)
        print(json.dumps({k: {"success": v[0], "message": v[1]} for k, v in results.items()}, indent=2))
    elif args.action == "reset":
        _, s_path = load_state(args.state)
        if Path(s_path).exists():
            os.remove(s_path)
            logger.info(f"Estado apagado com sucesso: {s_path}")
        else:
            logger.info("Nenhum arquivo de estado para apagar.")


if __name__ == "__main__":
    main()
