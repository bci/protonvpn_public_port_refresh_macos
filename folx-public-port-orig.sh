#!/bin/bash
#  protonvpn-public-port-refresh.sh
#  Created by Kent Behrends, kent@bci.com, 2024-03-01.
#
# Usage:
#
#   ./protonvpn-public-port-refresh.sh [switch]
#
#   Where switch is:
#       -a name app to control, currently supports only Folx3-setapp
#       -h print usage
#       -n no app control, just public port refreshing
#
# Tested on:
#   macOS 14.4
#
# Uses:
#   ProtonVPN (peer-to-peer VPN server, Wineguard protocol)
#   natpmp-client.py
#   folx (macOS, setapp version)
#
# The public port is dynamic with TTL 60 seconds. This script will request
# a port, set the folx public port default, then refresh it every 45 seconds.
#
# appControl=""             # No app to control
# appControl="Folx3-setapp" # Control the folx app
appControl="Folx3-setapp"
folxPath="/Applications/Setapp/Folx.app" # Use /Applications/Folx.app for non-setapp version
folxDefaults="com.eltima.Folx3-setapp" # Use com.eltima.Folx3 for non-setapp version
natpmpPath="$HOME/Library/Python/3.9/bin/natpmp-client.py"
#
# Command line parse
#
while getopts ":a:hn" OPTION; do
    case "$OPTION" in
        a)  appControl="$OPTARG" ;;
        h) echo "usage: $0 [-h] [-n] [-a app-name]"; exit ;;
        n) appControl="" ;;
        ?) echo "usage: $0 [-h] [-n] [-a app-name]"; exit ;;
    esac
done
#
# port: Current ProtonVPN dynamic public port
#
echo "Requesting public dynamic port..."
port=`$natpmpPath -g 10.2.0.1 0 0 | awk '{print $15}' | cut -d, -f 1`
if [[ "$port" == "" ]]
then
    echo "---"
    echo "Current VPN gateway does not support NAT-PMP"
    echo "Verify VPN server is a peer-to-peer server"
    exit
fi
portChanged=0
portAquired=`date`
#
# App control, Set defaults and open
#
if [[ "$appControl" == "Folx3-setapp" ]]
then
#
    echo "Setting folx public port to $port"
    defaults write $folxDefaults GeneralUserSettings -dict-add TorrentTCPPort $port
    #
    # Open Folx
    #
    echo "Opening $folxPath"
    open $folxPath
fi
#
# refresh: true to keep looping
#
refresh="true"
#
# Loop forever, or until 'y' entered in Quit? Need to keep refreshing public port number from ProtonVpn's p2p servers
# If public port changes, update Folx.app
#
while [ "$refresh" == "true" ]
    do
        newPort=`$natpmpPath -g 10.2.0.1 0 0 | awk '{print $15}' | cut -d, -f 1`
        #echo "Refreshing public port: $newPort"
        
        # Check if port exists
        if [[ "$newPort" == "" ]]
        then
            echo "Lost connection... Try again in 30 seconds..."
            sleep 30
            newPort=`$natpmpPath -g 10.2.0.1 0 0 | awk '{print $15}' | cut -d, -f 1`
            if [[ "$newPort" == "" ]]
            then
                echo "Lost connection, quiting."
                break
            fi
        fi
        if [[ "$port" != "$newPort" ]]
        then
            echo "Public port changed from $port to $newPort. Setting new public port in Folx"
            port=$newPort
            portChanged=$((portChanged+1))
            portAquired=`date`
            #
            # App control, Close, Set defaults and Open
            #
            if [[ "$appControl" == "true" ]]
            then
                #
                # Stop, set the new port, and Start Folx.app
                #
                echo "Restarting Folx (30 seconds)..."
                osascript -e 'quit app "Folx"'
                sleep 30
                defaults write $folxDefaults GeneralUserSettings -dict-add TorrentTCPPort $port
                open $folxPath
            fi
        fi
        #
        # Allow for safe breaking of while loop - will continue if no keyboard input within 45 seconds
        #
        echo ""
        echo "`date` - public port has changed $portChanged time(s), last change at $portAquired"
        read -t 45 -p "Quit [(n),y, Refresh public port $port in 45 seconds]: " quittingTime
        echo ""
        if [[ "$quittingTime" == "y" ]]
        then
            refresh="false"
        fi
    done
#
# App control, Close
#
if [[ "$appControl" == "Folx3-setapp" ]]
then
    #
    # Shutdown folx
    #
    echo "Shutting doen Folx"
    osascript -e 'quit app "Folx"'
fi
