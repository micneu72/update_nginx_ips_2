#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
	Script Name:     update_nginx_whitelist.py
	CreationDate:    26.06.2025
	Last Modified:   26.06.2025 22:41:27
	Copyright:       Michael N. (c)2025
	Purpose:         
-------------------------

Ermittelt alle IPv4- und IPv6-Adressen (AAAA) zu den angegebenen
DynDNS-/Host-Namen, fasst die IPv6-Adressen zu einem (konfigurierbaren)
Prefix zusammen und schreibt daraus eine Include-Datei für nginx.

• IPv4  → jede Adresse einzeln whitelisten (NAT).
• IPv6  → nur das Netzpräfix (z. B. /56) whitelisten,
          sodass Privacy-Adressen der Clients abgedeckt sind.

Falls sich die generierte Datei ändert, wird optional
`nginx -t` und `systemctl reload nginx` ausgeführt.
"""

from __future__ import annotations

import argparse
import filecmp
import ipaddress
import socket
import subprocess
import sys
from pathlib import Path
from typing import List, Set, Tuple

# ------------------------------------------------------------
# Einstellungen
# ------------------------------------------------------------

DEFAULT_IPV6_PREFIX_LEN = 56      # bei Bedarf anpassen
DEFAULT_TIMEOUT_SEC = 3           # DNS-Timeout (nur Python ≥ 3.11 nutzt ihn)
NGINX_RELOAD_CMD = ["systemctl", "reload", "nginx"]
NGINX_TEST_CMD   = ["nginx", "-t"]

# ------------------------------------------------------------
# Hilfsfunktionen
# ------------------------------------------------------------

def resolve_ips(host: str,
                timeout: int = DEFAULT_TIMEOUT_SEC) -> Tuple[Set[str], Set[str]]:
    """Liefert (ipv4_set, ipv6_set) für einen Hostnamen."""
    ipv4: Set[str] = set()
    ipv6: Set[str] = set()

    try:
        # Ab Python 3.11 existiert das Argument „timeout“
        try:
            infos = socket.getaddrinfo(
                host, None,
                family = socket.AF_UNSPEC,
                proto  = socket.IPPROTO_TCP,
                timeout = timeout          # type: ignore[arg-type]
            )
        except TypeError:
            # Rückfall → ältere Pythons (< 3.11) ohne timeout-Parameter
            infos = socket.getaddrinfo(
                host, None,
                family = socket.AF_UNSPEC,
                proto  = socket.IPPROTO_TCP
            )
    except socket.gaierror as err:
        print(f"[WARN] {host}: DNS-Lookup fehlgeschlagen – {err}", file=sys.stderr)
        return ipv4, ipv6

    for family, _type, _proto, _canon, sockaddr in infos:
        if family == socket.AF_INET:        # IPv4
            ipv4.add(sockaddr[0])
        elif family == socket.AF_INET6:     # IPv6
            ipv6.add(sockaddr[0])

    return ipv4, ipv6


def collapse_ipv6_to_prefix(ipv6_addrs: Set[str],
                            prefix_len: int) -> Set[ipaddress.IPv6Network]:
    """Fasst IPv6-Adressen zu Networks gleicher Präfixlänge zusammen."""
    return {
        ipaddress.IPv6Network(f"{addr}/{prefix_len}", strict=False)
        for addr in ipv6_addrs
    }


def create_allowlist(domain_list: List[str],
                     ipv6_prefix_len: int) -> List[str]:
    """Erzeugt die nginx-allow-Zeilen als sortierte Liste."""
    allow_lines: Set[str] = set()

    for host in domain_list:
        host = host.strip()
        if not host or host.startswith("#"):
            continue   # leer / Kommentar

        ipv4_addrs, ipv6_addrs = resolve_ips(host)

        # IPv4: jede Adresse einzeln
        for ip in ipv4_addrs:
            allow_lines.add(f"allow {ip};  # {host} IPv4")

        # IPv6: nur das Präfix
        for net in collapse_ipv6_to_prefix(ipv6_addrs, ipv6_prefix_len):
            allow_lines.add(
                f"allow {net.compressed};  # {host} IPv6 /{ipv6_prefix_len}"
            )

    # Sortiert: IPv4 (kein „:“) zuerst, dann IPv6
    return sorted(allow_lines, key=lambda line: (':' in line, line))


def write_if_changed(content_lines: List[str], target_file: Path) -> bool:
    """Schreibt Datei nur bei geändertem Inhalt. → True = geändert."""
    tmp_file = target_file.with_suffix(".tmp")
    tmp_file.write_text("\n".join(content_lines) + "\n", encoding="utf-8")

    changed = (
        not target_file.exists()
        or not filecmp.cmp(tmp_file, target_file, shallow=False)
    )

    if changed:
        tmp_file.replace(target_file)
        print(f"[INFO] Datei aktualisiert: {target_file}")
    else:
        tmp_file.unlink()

    return changed


def run_cmd(cmd: List[str]) -> None:
    """Führt ein Kommando aus – wirft Fehler bei Exit-Code ≠ 0."""
    print(f"[INFO] Starte: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(result.stdout)
        print(result.stderr, file=sys.stderr)
        raise RuntimeError(f"Befehl fehlgeschlagen: {' '.join(cmd)}")
    print(result.stdout, end="")


# ------------------------------------------------------------
# Main-Funktion
# ------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Aktualisiert eine nginx-Whitelist basierend auf DynDNS-Hosts."
    )
    parser.add_argument(
        "domain_file",
        type=Path,
        help="Textdatei mit je einem Host/DynDNS-Namen pro Zeile"
    )
    parser.add_argument(
        "allow_include",
        type=Path,
        help="Ziel-Datei (nginx include), z. B. /etc/nginx/whitelist.conf"
    )
    parser.add_argument(
        "--ipv6-prefix-len", "-p",
        type=int,
        default=DEFAULT_IPV6_PREFIX_LEN,
        help=f"Prefix-Länge für IPv6-Whitelist (Default: {DEFAULT_IPV6_PREFIX_LEN})"
    )
    parser.add_argument(
        "--no-reload",
        action="store_true",
        help="nginx nach Änderungen NICHT automatisch testen/reloaden"
    )
    args = parser.parse_args()

    # ---------- Domain-Liste laden
    if not args.domain_file.exists():
        parser.error(f"Domain-Datei nicht gefunden: {args.domain_file}")

    domains = args.domain_file.read_text(encoding="utf-8").splitlines()

    # ---------- Allow-Liste erstellen
    allow_lines = create_allowlist(domains, args.ipv6_prefix_len)
    allow_lines.append("deny  all;")    # letzte Regel

    # ---------- Datei schreiben (falls nötig)
    changed = write_if_changed(allow_lines, args.allow_include)

    # ---------- nginx testen & ggf. reloaden
    if changed and not args.no_reload:
        try:
            run_cmd(NGINX_TEST_CMD)
            run_cmd(NGINX_RELOAD_CMD)
            print("[INFO] nginx erfolgreich neu geladen.")
        except RuntimeError as err:
            print(f"[ERROR] {err}", file=sys.stderr)
            sys.exit(1)
    elif changed:
        print("[WARN] nginx-Konfiguration geändert – Reload unterdrückt (--no-reload).")
    else:
        print("[INFO] Keine Änderungen an der Whitelist.")


# ------------------------------------------------------------
if __name__ == "__main__":
    main()