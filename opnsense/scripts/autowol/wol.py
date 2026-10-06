#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AutoWoL - Wake-on-LAN Magic Packet Generator
Executes natively in OPNsense / FreeBSD without external dependencies.
"""

import re
import socket
import struct
import logging

logger = logging.getLogger("autowol.wol")


def normalize_mac(mac_str: str) -> bytes:
    """
    Normalizes a MAC address string into 6 raw bytes.
    Accepts formats:
      - 00:11:22:33:44:55
      - 00-11-22-33-44-55
      - 0011.2233.4455
      - 001122334455
    """
    cleaned = re.sub(r"[^0-9a-fA-F]", "", mac_str.strip())
    if len(cleaned) != 12:
        raise ValueError(
            f"Invalid MAC address '{mac_str}': expected 12 hexadecimal characters, got {len(cleaned)}"
        )
    return bytes.fromhex(cleaned)


def build_magic_packet(mac_bytes: bytes) -> bytes:
    """
    Constructs a WoL Magic Packet:
    6 bytes of 0xFF followed by 16 repetitions of the 6-byte MAC address.
    Total payload size = 6 + (16 * 6) = 102 bytes.
    """
    if len(mac_bytes) != 6:
        raise ValueError(f"MAC bytes must be exactly 6 bytes long, got {len(mac_bytes)}")
    return (b"\xff" * 6) + (mac_bytes * 16)


def send_magic_packet(
    mac: str,
    broadcast_ip: str = "255.255.255.255",
    port: int = 9,
    bind_ip: str = None
) -> tuple[bool, str]:
    """
    Sends a Wake-on-LAN magic packet over UDP broadcast.

    :param mac: Target MAC address (e.g. '00:11:22:33:44:55')
    :param broadcast_ip: Subnet broadcast IP (e.g. '192.168.1.255' or '255.255.255.255')
    :param port: Destination UDP port (usually 9 or 7)
    :param bind_ip: Optional local IP address to bind to specific interface
    :return: (success: bool, description: str)
    """
    try:
        mac_bytes = normalize_mac(mac)
        payload = build_magic_packet(mac_bytes)
    except ValueError as e:
        msg = f"Failed to construct WoL packet: {e}"
        logger.error(msg)
        return False, msg

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        if bind_ip:
            sock.bind((bind_ip, 0))
        sock.sendto(payload, (broadcast_ip, port))
        msg = f"Magic Packet sent to {mac} via {broadcast_ip}:{port}"
        logger.info(msg)
        return True, msg
    except Exception as e:
        msg = f"Error sending Magic Packet to {mac} via {broadcast_ip}:{port} - {e}"
        logger.error(msg)
        return False, msg
    finally:
        sock.close()


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <MAC> [broadcast_ip] [port]")
        sys.exit(1)

    target_mac = sys.argv[1]
    bcast = sys.argv[2] if len(sys.argv) > 2 else "255.255.255.255"
    p = int(sys.argv[3]) if len(sys.argv) > 3 else 9

    ok, message = send_magic_packet(target_mac, bcast, p)
    print(f"Result: {message}")
    sys.exit(0 if ok else 1)
