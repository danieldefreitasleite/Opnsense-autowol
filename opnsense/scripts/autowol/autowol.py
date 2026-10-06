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


def load_config(config_path: str = None) -> dict:
    """Loads configuration from specified or default paths."""
    candidates = [config_path] if config_path else DEFAULT_CONFIG_PATHS
    chosen_path = None
    for p in candidates:
        if p and Path(p).is_file():
            chosen_path = p
            break

    if not chosen_path:
        raise FileNotFoundError(
            f"Configuration file not found. Checked: {', '.join(str(p) for p in candidates if p)}"
        )

    with open(chosen_path, "r", encoding="utf-8") as f:
        return json.load(f)


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

    def wake_single_host(self, host_identifier: str) -> bool:
        """Sends a manual Wake-on-LAN packet to a single host by ID or name."""
        target = None
        for h in self.hosts:
            if h.get("id") == host_identifier or h.get("name") == host_identifier:
                target = h
                break

        if not target:
            self.logger.error(f"Host '{host_identifier}' não encontrado na lista de hosts.")
            return False

        bcast = target.get("broadcast_ip") or self.settings.get("default_broadcast_ip", "255.255.255.255")
        port = int(target.get("wol_port") or self.settings.get("default_wol_port", 9))
        ok, msg = send_magic_packet(target.get("mac"), bcast, port)
        if ok:
            self.logger.info(f"Wake-on-LAN enviado para {target.get('name')}: {msg}")
        return ok

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


def main():
    parser = argparse.ArgumentParser(description="OPNsense AutoWoL & Host Monitor Daemon")
    parser.add_argument(
        "--action",
        choices=["check", "wake", "status", "test-alert", "reset"],
        default="check",
        help="Action to execute"
    )
    parser.add_argument("--config", "-c", help="Path to config.json")
    parser.add_argument("--state", "-s", help="Path to state.json")
    parser.add_argument("--host", help="Host ID or Name for 'wake' action")
    parser.add_argument("--channel", default="all", help="Notification channel to test for 'test-alert'")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose debug output")

    args = parser.parse_args()

    try:
        cfg = load_config(args.config)
    except Exception as e:
        print(f"Erro ao carregar configuração: {e}", file=sys.stderr)
        sys.exit(1)

    log_file = cfg.get("settings", {}).get("log_file")
    logger = setup_logging(verbose=args.verbose, log_file=log_file)

    engine = AutoWoLEngine(cfg, state_path=args.state, logger=logger)

    if args.action == "check":
        results = engine.check_all_hosts()
        print(json.dumps(results, indent=2))
    elif args.action == "wake":
        if not args.host:
            logger.error("Ação 'wake' requer o parâmetro --host <nome_ou_id>")
            sys.exit(1)
        ok = engine.wake_single_host(args.host)
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
