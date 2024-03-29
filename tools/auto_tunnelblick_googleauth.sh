#!/bin/bash

# Written by Alan. (https://github.com/wangyufeng0615/auto_tunnelblick_googleauth)

# Usage
# chmod +x vpn.sh
# setup: ./vpn.sh setup VPN_name account password otp_key
# on: ./vpn.sh on VPN_name
# off: ./vpn.sh off VPN_name

# brew install oath-toolkit
# brew install zbar
# save QR code to png file
# zbarimg ./qrcode.png
# oathtool --totp -b -d 6 "<OTP from zbarimg output>"
# osascript ./tunnelblick.osascript

# Parameters($1-$4): VPN_name, account, password, otp_key
setup() {
    # Set VPN account
    /usr/bin/security add-generic-password -U -s Tunnelblick-Auth-"$1" -a username -w "$2"

    # Set VPN password
    /usr/bin/security add-generic-password -U -s Tunnelblick-Auth-"$1"-Password -a password -w "$3"

    # Set OTP key (16 bytes usually)
    /usr/bin/security add-generic-password -U -s Tunnelblick-Auth-"$1"-OTPKey -a password -w "$4"

    echo 'Done. '
}

# Parameters($1): VPN_name
on() {
    # Get VPN password
    Password=$(/usr/bin/security find-generic-password -gs Tunnelblick-Auth-"$1"-Password -w)

    # Get OTP Key
    OTPKey=$(/usr/bin/security find-generic-password -gs Tunnelblick-Auth-"$1"-OTPKey -w)

    # Calculate OTP Code
    OTPCode=$(oathtool --totp -b -d 6 "$OTPKey")

    echo -e $OTPCode

    # Set the final 'VPN password + OTP code'
    /usr/bin/security add-generic-password -U -s Tunnelblick-Auth-"$1" -a password -w $Password$OTPCode

    # VPN on
    # echo 'Tell app "Tunnelblick" to connect '\"$1\" | osascript
    osascript ./tunnelblick.osascript $1 $OTPCode

    echo 'Done.'
}

# Parameters($1): VPN_name
off() {
    echo 'Tell app "Tunnelblick" to disconnect '\"$1\" | osascript

    echo 'Done.'
}

# Check user typed the mode parameters or not
if [ -n "$1" ]; then
    case $1 in
        setup)
            if [ -n "$5" ]; then
                setup "$2" "$3" "$4" "$5"
            else
                echo 'Please input [1.name of vpn  2.account  3.password  4.otp key] after "setup".'
                exit 1
            fi
            ;;
        on)
            if [ -n "$2" ]; then
                on "$2"
            else
                echo 'Please input the name of vpn that you want to connect after "on".'
                exit 1
            fi
            ;;
        off)
            if [ -n "$2" ]; then
                off "$2"
            else
                echo 'Please input the name of vpn that you want to disconnect after "on".'
                exit 1
            fi
            ;;
        *)
            echo 'Unknown mode.'
            exit 1
            ;;
    esac
else
    echo 'Please input script mode (setup, on, off)'
    exit 1
fi
