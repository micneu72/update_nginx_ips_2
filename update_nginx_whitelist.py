#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
	Script Name:     update_nginx_whitelist.py
	CreationDate:    30.01.2025
	Last Modified:   
	Copyright:       Michael N. (c)2025
	Purpose:         
"""

import argparse
import subprocess
from pathlib import Path
import socket

def resolve_ips(domain):
    """
    Ermittelt die eindeutigen IPv4- und IPv6-Adressen für eine gegebene Domain.
    """
    ipv4_addresses = set()
    ipv6_addresses = set()

    try:
        # IPv4-Auflösung
        for info in socket.getaddrinfo(domain, None, socket.AF_INET):
            ipv4_addresses.add(info[4][0])
    except socket.gaierror:
        pass

    try:
        # IPv6-Auflösung
        for info in socket.getaddrinfo(domain, None, socket.AF_INET6):
            ipv6_addresses.add(info[4][0])
    except socket.gaierror:
        pass

    if not ipv4_addresses and not ipv6_addresses:
        print(f"Warnung: Keine IP-Adressen für {domain} gefunden.")

    return list(ipv4_addresses), list(ipv6_addresses)

def create_ip_list(source_file):
    """
    Erstellt die Allowlist mit eindeutigen IP-Adressen basierend auf den DNS-Einträgen.
    """
    allowlist = set()
    with open(source_file, 'r') as file:
        domains = sorted(file.read().splitlines())
        for domain in domains:
            if domain.strip():  # Überspringe leere Zeilen
                ipv4_addresses, ipv6_addresses = resolve_ips(domain)

                for ip in ipv4_addresses:
                    allowlist.add(f"allow {ip}; # from {domain} (IPv4)")
                for ip in ipv6_addresses:
                    allowlist.add(f"allow {ip}; # from {domain} (IPv6)")
    return "\n".join(sorted(allowlist))

def check_and_update_allowlist(allowlist, allow_file):
    """
    Überprüft und aktualisiert die Allowlist-Datei, falls Änderungen erforderlich sind.
    """
    allow_file_path = Path(allow_file)
    current_content = allow_file_path.read_text() if allow_file_path.exists() else ""

    if current_content != allowlist:
        print("Änderungen erkannt! Aktualisiere die Allowlist-Datei und lade Nginx neu.")
        allow_file_path.write_text(allowlist)
        try:
            subprocess.run(["nginx", "-t"], check=True)
            subprocess.run(["systemctl", "reload", "nginx"], check=True)
            print("Nginx wurde erfolgreich neu geladen.")
        except subprocess.CalledProcessError as e:
            print(f"Fehler beim Testen oder Neuladen von Nginx: {e}")
    else:
        print("Keine Änderungen erkannt. Keine Aktion erforderlich.")

def main():
    parser = argparse.ArgumentParser(
        description="Aktualisiert die Nginx-Konfigurationsdatei für erlaubte IPs basierend auf einer Domainliste."
    )
    parser.add_argument("domain_list", type=str, help="Pfad zur Datei mit der Liste von Domains.")
    parser.add_argument("allow_file", type=str, help="Pfad zur Nginx-Allowlist-Datei.")

    args = parser.parse_args()

    allowlist = create_ip_list(args.domain_list)
    check_and_update_allowlist(allowlist, args.allow_file)

if __name__ == "__main__":
    main()

