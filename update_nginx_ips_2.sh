#!/bin/bash
## ----------------------------------------------------------------------------
## Script Name:     update_nginx_ips_2.sh
## CreationDate:    08.11.2022
## Last Modified:   08.11.2022 20:16:11
## Copyright:       Michael N. (c)2022
## Purpose:         
##
## ----------------------------------------------------------------------------

createIPlist() {
    FILE=$(cat $SOURCEFILE | sort)
    for line in $FILE; do
        #echo $line
        ddns_record="$line"
        if [[ !  -z  $ddns_record ]]; then
            resolved_ip=`getent ahosts $line | awk '{ print $1 ; exit }'`
            IP=$(getent ahosts $line | grep STREAM)
            IFS=$'\n'
            IP=$(sed -e 's/\sSTREAM.*//' <<< $IP)
            for i in $IP; do
                i=$(sed -e 's/\s+//' <<< $i)
                i=$(sed -e 's/\s//g' <<< $i)
                echo $i | grep -e '(.+\s)' | awk '{ print $1 ; exit }'
                #i=$(sed -e 's/\s+//' <<< $i)
                if [[ !  -z  $i ]]; then
                    #echo "allow $i;# from $ddns_record"
                    ALLOWLIST+="allow $i;# from $ddns_record\n"
                fi
            done
        fi
    done
}

checkIPs() {
    ACTIVE=$(cat $ALLOWFILE)
    for i in $ACTIVE; do
	    ACTIVE2+="$i\n"
    done
    if [ "$ACTIVE2" != "$ALLOWLIST" ]; then
        echo -e $ALLOWLIST > $ALLOWFILE
	    systemctl reload nginx > /dev/null 2>&1
    fi
}

# funktionen ende

if [ $# -ne 2 ] ;then
   	echo  -e "Usage:  $0  <domain-list> <allowed-nginx> \n"
   	exit 42
fi

ALLOWLIST=""
SOURCEFILE=$1
ALLOWFILE=$2
createIPlist $FILE
#echo -e $ALLOWLIST
checkIPs $ALLOWFILE
