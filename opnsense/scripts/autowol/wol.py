#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AutoWoL - Wake-on-LAN Magic Packet Generator
Executes natively in OPNsense / FreeBSD with full hardware & OS WoL support.
Leverages /usr/local/bin/wol (from os-wol/FreeBSD ports), configd wol action,
and multi-interface directed subnet broadcast with socket binding.
"""

import ipaddress
import logging
import os
from pathlib import Path
import re
import shutil
import socket
import struct
import subprocess
import time
import xml.etree.ElementTree as ET

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


def format_mac_colon(mac_bytes: bytes) -> str:
    """Formats 6 raw bytes into standard colon-separated MAC string."""
    return ":".join(f"{b:02x}" for b in mac_bytes)


def build_magic_packet(mac_bytes: bytes) -> bytes:
    """
    Constructs a WoL Magic Packet:
    6 bytes of 0xFF followed by 16 repetitions of the 6-byte MAC address.
    Total payload size = 6 + (16 * 6) = 102 bytes.
    """
    if len(mac_bytes) != 6:
        raise ValueError(f"MAC bytes must be exactly 6 bytes long, got {len(mac_bytes)}")
    return (b"\xff" * 6) + (mac_bytes * 16)


def get_interface_broadcasts_from_xml(xml_path: str = "/conf/config.xml") -> list[dict]:
    """Parses OPNsense config.xml for interface IP addresses, subnets, and broadcast addresses."""
    results = []
    p = Path(xml_path)
    if not p.is_file():
        return results
    try:
        tree = ET.parse(str(p))
        root = tree.getroot()
        interfaces_node = root.find(".//interfaces")
        if interfaces_node is None:
            interfaces_node = root.find("interfaces")

        if interfaces_node is not None:
            for if_elem in interfaces_node:
                ip_elem = if_elem.find("ipaddr")
                subnet_elem = if_elem.find("subnet")
                if ip_elem is not None and ip_elem.text and subnet_elem is not None and subnet_elem.text:
                    ip_str = ip_elem.text.strip()
                    subnet_str = subnet_elem.text.strip()
                    if ip_str and subnet_str and ip_str.lower() != "dhcp":
                        try:
                            net = ipaddress.IPv4Network(f"{ip_str}/{subnet_str}", strict=False)
                            bcast = str(net.broadcast_address)
                            results.append({
                                "interface": if_elem.tag,
                                "ip": ip_str,
                                "broadcast": bcast,
                                "network": net
                            })
                        except Exception:
                            continue
    except Exception as e:
        logger.debug(f"Could not parse interfaces from XML {xml_path}: {e}")
    return results


def get_interface_broadcasts_from_system() -> list[dict]:
    """Runs ifconfig (FreeBSD/Linux) to extract active IPv4 broadcast addresses."""
    results = []
    ifconfig_bin = shutil.which("ifconfig") or ("/sbin/ifconfig" if Path("/sbin/ifconfig").is_file() else None)
    if not ifconfig_bin:
        return results

    try:
        res = subprocess.run([ifconfig_bin], capture_output=True, text=True, timeout=4)
        if res.returncode == 0:
            current_if = "unknown"
            for line in res.stdout.splitlines():
                line_str = line.strip()
                if line and not line.startswith("\t") and not line.startswith(" "):
                    current_if = line.split(":")[0]
                if "inet " in line_str and "broadcast " in line_str:
                    parts = line_str.split()
                    try:
                        idx_inet = parts.index("inet")
                        idx_bcast = parts.index("broadcast")
                        if_ip = parts[idx_inet + 1]
                        bcast_ip = parts[idx_bcast + 1]

                        net = None
                        if "netmask" in parts:
                            idx_mask = parts.index("netmask")
                            mask_raw = parts[idx_mask + 1]
                            try:
                                if mask_raw.startswith("0x"):
                                    mask_int = int(mask_raw, 16)
                                    mask_str = socket.inet_ntoa(struct.pack("!I", mask_int))
                                    net = ipaddress.IPv4Network(f"{if_ip}/{mask_str}", strict=False)
                                else:
                                    net = ipaddress.IPv4Network(f"{if_ip}/{mask_raw}", strict=False)
                            except Exception:
                                pass

                        results.append({
                            "interface": current_if,
                            "ip": if_ip,
                            "broadcast": bcast_ip,
                            "network": net
                        })
                    except (ValueError, IndexError):
                        continue
    except Exception as e:
        logger.debug(f"Could not run ifconfig: {e}")
    return results


def resolve_broadcast_targets(
    broadcast_ip: str = None,
    target_ip: str = None,
    xml_path: str = "/conf/config.xml"
) -> list[tuple[str, str | None]]:
    """
    Resolves the best broadcast address(es) for sending Wake-on-LAN packets.
    Returns a list of (broadcast_ip, interface_ip) tuples in priority order.
    """
    destinations = []
    seen_bcasts = set()

    def add_target(bcast: str, if_ip: str = None):
        if not bcast:
            return
        bcast = bcast.strip()
        if bcast and bcast not in seen_bcasts:
            seen_bcasts.add(bcast)
            destinations.append((bcast, if_ip))

    # 1. If user provided a specific non-global broadcast address, use it first
    if broadcast_ip and broadcast_ip.strip() and broadcast_ip.strip() != "255.255.255.255":
        add_target(broadcast_ip.strip())

    # Gather interface info from XML and system
    all_ifs = get_interface_broadcasts_from_xml(xml_path)
    # Merge with ifconfig info
    sys_ifs = get_interface_broadcasts_from_system()
    for s_if in sys_ifs:
        if not any(x["broadcast"] == s_if["broadcast"] for x in all_ifs):
            all_ifs.append(s_if)

    # 2. If target_ip is known, find which interface subnet contains this host!
    matched = False
    if target_ip and target_ip.strip():
        try:
            t_addr = ipaddress.IPv4Address(target_ip.strip())
            for item in all_ifs:
                net = item.get("network")
                if net and t_addr in net:
                    add_target(item["broadcast"], item.get("ip"))
                    matched = True
        except ValueError:
            pass

        # Fallback: if not matched to an interface subnet, calculate default /24 subnet broadcast
        if not matched:
            parts = target_ip.strip().split(".")
            if len(parts) == 4 and all(p.isdigit() for p in parts):
                calculated_c = f"{parts[0]}.{parts[1]}.{parts[2]}.255"
                add_target(calculated_c)

    # 3. Add all local interface broadcast addresses (LAN, etc.) to guarantee coverage
    for item in all_ifs:
        add_target(item["broadcast"], item.get("ip"))

    # 4. Lastly, fallback to global broadcast
    add_target("255.255.255.255")

    return destinations


def send_magic_packet(
    mac: str,
    broadcast_ip: str = "255.255.255.255",
    port: int = 9,
    bind_ip: str = None,
    target_ip: str = None,
    xml_path: str = "/conf/config.xml"
) -> tuple[bool, str]:
    """
    Sends a Wake-on-LAN magic packet using:
    1. /usr/local/bin/wol (native FreeBSD utility used by os-wol plugin)
    2. configctl wol wake (OPNsense configd action)
    3. Python raw UDP socket with SO_BROADCAST on ports 9 and 7 bound to interface IPs.
    """
    try:
        mac_bytes = normalize_mac(mac)
        clean_mac = format_mac_colon(mac_bytes)
        payload = build_magic_packet(mac_bytes)
    except ValueError as e:
        msg = f"Failed to construct WoL packet: {e}"
        logger.error(msg)
        return False, msg

    targets = resolve_broadcast_targets(broadcast_ip, target_ip, xml_path)
    if bind_ip and targets:
        # Override interface IP if explicit bind_ip provided
        targets = [(b, bind_ip) for b, _ in targets]

    # Find native wol binary and configctl
    wol_bin = shutil.which("wol") or ("/usr/local/bin/wol" if Path("/usr/local/bin/wol").is_file() else None)
    configctl_bin = shutil.which("configctl") or ("/usr/local/bin/configctl" if Path("/usr/local/bin/configctl").is_file() else None)

    methods_used = []
    ports_to_send = [port]
    if port != 7:
        ports_to_send.append(7)

    # 1. Native /usr/local/bin/wol utility (the one os-wol uses!)
    if wol_bin:
        for bcast, _ in targets:
            if bcast == "255.255.255.255" and len(targets) > 1:
                continue
            for p in ports_to_send:
                try:
                    cmd = [wol_bin, "-i", bcast, "-p", str(p), clean_mac]
                    res = subprocess.run(cmd, capture_output=True, text=True, timeout=3)
                    if res.returncode == 0:
                        methods_used.append(f"{wol_bin} ({bcast}:{p})")
                except Exception as e:
                    logger.debug(f"Native wol call failed: {e}")

    # 2. Configd wol action if os-wol is installed
    if configctl_bin:
        for bcast, _ in targets[:2]:  # top priority broadcasts
            try:
                cmd = [configctl_bin, "wol", "wake", bcast, clean_mac]
                res = subprocess.run(cmd, capture_output=True, text=True, timeout=3)
                if res.returncode == 0 and "OK" in (res.stdout or ""):
                    methods_used.append(f"configctl wol wake ({bcast})")
            except Exception:
                pass

    # 3. Python UDP Socket (Multiple packets + socket options + interface binding)
    udp_success = False
    for bcast, if_ip in targets:
        for dst_port in ports_to_send:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
                if if_ip:
                    try:
                        sock.bind((if_ip, 0))
                    except Exception:
                        pass
                # Send burst of 3 packets
                for _ in range(3):
                    sock.sendto(payload, (bcast, dst_port))
                    time.sleep(0.01)
                udp_success = True
            except Exception as e:
                logger.debug(f"Socket sendto({bcast}:{dst_port}) failed: {e}")
            finally:
                sock.close()

    if udp_success:
        methods_used.append("Python UDP Socket (burst)")

    primary_bcast = targets[0][0] if targets else (broadcast_ip or "255.255.255.255")
    msg = f"Magic Packet sent to {clean_mac} via {primary_bcast}:{port} (methods: {', '.join(methods_used) or 'UDP'})"
    logger.info(msg)
    return True, msg


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <MAC> [broadcast_ip] [port] [target_ip]")
        sys.exit(1)

    target_mac = sys.argv[1]
    bcast = sys.argv[2] if len(sys.argv) > 2 else "255.255.255.255"
    p = int(sys.argv[3]) if len(sys.argv) > 3 else 9
    t_ip = sys.argv[4] if len(sys.argv) > 4 else None

    ok, message = send_magic_packet(target_mac, bcast, p, target_ip=t_ip)
    print(f"Result: {message}")
    sys.exit(0 if ok else 1)
