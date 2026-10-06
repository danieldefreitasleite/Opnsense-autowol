#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AutoWoL - Host Connectivity Prober
Performs ICMP Ping and/or TCP port connectivity checks natively.
"""

import sys
import time
import socket
import logging
import subprocess

logger = logging.getLogger("autowol.prober")


def ping_host(ip: str, timeout_sec: float = 2.0, count: int = 2) -> tuple[bool, float, str]:
    """
    Performs an ICMP ping using the operating system's native ping utility.
    Supports FreeBSD (OPNsense), Linux, and Windows.
    
    :return: (is_alive: bool, elapsed_ms: float, details: str)
    """
    start_time = time.time()
    system = sys.platform.lower()

    if system.startswith("freebsd") or "bsd" in system:
        # FreeBSD ping: -c count, -t timeout in seconds
        cmd = ["/sbin/ping", "-c", str(count), "-t", str(int(timeout_sec)), ip]
    elif system.startswith("win"):
        # Windows ping: -n count, -w timeout in milliseconds
        cmd = ["ping", "-n", str(count), "-w", str(int(timeout_sec * 1000)), ip]
    else:
        # Linux ping: -c count, -W timeout in seconds
        cmd = ["ping", "-c", str(count), "-W", str(int(timeout_sec)), ip]

    try:
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout_sec + 2.0
        )
        elapsed = (time.time() - start_time) * 1000.0
        if proc.returncode == 0:
            return True, elapsed, f"ICMP ping responded in {elapsed:.1f}ms"
        else:
            return False, elapsed, f"ICMP ping failed (exit code {proc.returncode})"
    except subprocess.TimeoutExpired:
        elapsed = (time.time() - start_time) * 1000.0
        return False, elapsed, f"ICMP ping timed out after {timeout_sec}s"
    except Exception as e:
        elapsed = (time.time() - start_time) * 1000.0
        return False, elapsed, f"ICMP ping error: {e}"


def tcp_probe(ip: str, port: int, timeout_sec: float = 2.0) -> tuple[bool, float, str]:
    """
    Checks if a TCP port is open/responding. Useful when target firewall blocks ICMP.
    
    :return: (is_alive: bool, elapsed_ms: float, details: str)
    """
    start_time = time.time()
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout_sec)
    try:
        sock.connect((ip, port))
        sock.shutdown(socket.SHUT_RDWR)
        elapsed = (time.time() - start_time) * 1000.0
        return True, elapsed, f"TCP probe to {ip}:{port} succeeded in {elapsed:.1f}ms"
    except (socket.timeout, ConnectionRefusedError):
        # ConnectionRefusedError still implies the host OS network stack is UP!
        elapsed = (time.time() - start_time) * 1000.0
        # If connection is refused (RST packet received), the machine is definitely ON and routing!
        return True, elapsed, f"TCP probe {ip}:{port} host is UP (connection refused/RST received)"
    except Exception as e:
        elapsed = (time.time() - start_time) * 1000.0
        return False, elapsed, f"TCP probe {ip}:{port} failed: {e}"
    finally:
        sock.close()


def check_host(
    ip: str,
    method: str = "icmp",
    tcp_port: int = None,
    timeout_sec: float = 2.0
) -> tuple[bool, str, str]:
    """
    Checks host online status using configured method:
    - 'icmp': Ping only
    - 'tcp': TCP port only (requires tcp_port)
    - 'both' / 'auto': Tries ICMP first; falls back to TCP probe if configured.
    
    :return: (is_online: bool, method_used: str, details: str)
    """
    method = (method or "icmp").lower()

    if method == "tcp" and tcp_port:
        alive, _, details = tcp_probe(ip, tcp_port, timeout_sec)
        return alive, f"tcp:{tcp_port}", details

    # Default or ICMP probe
    alive, _, details = ping_host(ip, timeout_sec)
    if alive:
        return True, "icmp", details

    # Fallback to TCP if method is 'both' or 'auto' and tcp_port is provided
    if method in ("both", "auto") and tcp_port:
        tcp_alive, _, tcp_details = tcp_probe(ip, tcp_port, timeout_sec)
        if tcp_alive:
            return True, f"tcp:{tcp_port}", f"Ping failed, but {tcp_details}"
        return False, f"both:{tcp_port}", f"Ping failed AND {tcp_details}"

    return False, "icmp", details


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <IP> [method: icmp|tcp|both] [tcp_port]")
        sys.exit(1)

    target_ip = sys.argv[1]
    probe_method = sys.argv[2] if len(sys.argv) > 2 else "icmp"
    port_num = int(sys.argv[3]) if len(sys.argv) > 3 else None

    online, used_method, diag = check_host(target_ip, probe_method, port_num)
    print(f"Status: {'ONLINE' if online else 'OFFLINE'} | Method: {used_method} | Details: {diag}")
    sys.exit(0 if online else 1)
