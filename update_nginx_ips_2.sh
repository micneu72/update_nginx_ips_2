#!/bin/bash
## ----------------------------------------------------------------------------
## Script Name:     update_nginx_ips_2.sh
## CreationDate:    08.11.2022
## Last Modified:   27.10.2024 13:15:31
## Copyright:       Michael N. (c)2022
## Purpose:         Aktualisiert die Nginx-Konfigurationsdatei für erlaubte IPs,
##                  basierend auf den DNS-Einträgen in einer gegebenen Domänenliste.
## ----------------------------------------------------------------------------

# Funktion zur Erstellung der IP-Liste basierend auf den DNS-Einträgen
createIPlist() {
    sorted_file=$(sort "$SOURCEFILE")  # Zuweisung erfolgt separat
    local line
    for line in $sorted_file; do
        ddns_record="$line"
        
        if [[ -n $ddns_record ]]; then
            # DNS-Auflösung und IP-Ermittlung
            resolved_ips=$(getent ahosts "$ddns_record" | awk '/STREAM/ { print $1 }')
            for ip in $resolved_ips; do
                if [[ -n $ip ]]; then
                    ALLOWLIST+="allow $ip; # from $ddns_record\n"
                fi
            done
        fi
    done
}

# Funktion zur Überprüfung und Aktualisierung der Nginx-Allowlist
checkIPs() {
    local active_list  # Deklaration separat
    active_list=$(cat "$ALLOWFILE")  # Zuweisung separat
    
    if [[ "$active_list" != "$ALLOWLIST" ]]; then
        echo -e "$ALLOWLIST" > "$ALLOWFILE"
        systemctl reload nginx > /dev/null 2>&1
    fi
}

# Hauptskriptstart: Parameter-Check und Aufruf der Funktionen
if [[ $# -ne 2 ]]; then
    echo -e "Usage: $0 <domain-list> <allowed-nginx>\n"
    exit 42
fi

ALLOWLIST=""
SOURCEFILE=$1
ALLOWFILE=$2

createIPlist
checkIPs