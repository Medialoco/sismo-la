#!/bin/sh
# Enable key-only SSH on the board, so the station can be deployed to and
# inspected over WiFi instead of only over USB.
#
# Why this exists: adbd on this board runs unprivileged and refuses `adb tcpip`,
# so there is no adb-over-network route. Without SSH the only remote surface is
# the read-only dashboard on port 8000, which means a station that is upstairs
# cannot be updated at all -- every change costs a trip to unplug the board,
# and unplugging resets the MCU (the router replays its gpioset on the reset
# line at startup), which loses the recording.
#
# Run as root, in the host namespace.

set -e

echo "== 1. clear the forced password change =="
# The arduino account has last-change = 0, i.e. "password must be changed".
# PAM's account stage refuses *every* session for such an account, which is
# why cron jobs never ran (pam_unix(cron:account): expired password) and why
# key-based SSH would be refused too. This sets the last-change date to today.
# It does NOT set or reveal a password: the account keeps whatever secret it
# had, so `sudo` is no more usable than before. Only the account-expiry flag
# is cleared, which is exactly what blocks non-interactive logins.
chage -d "$(date +%Y-%m-%d)" arduino
chage -l arduino | head -3

echo
echo "== 2. key-only sshd configuration =="
mkdir -p /etc/ssh/sshd_config.d
cat > /etc/ssh/sshd_config.d/10-sismo.conf <<'EOF'
# Sismo-LA: remote access to the station over the LAN.
# Keys only. The arduino account's password is unknown to its owner, so
# password authentication would be an attack surface with no legitimate user.
PubkeyAuthentication yes
PasswordAuthentication no
KbdInteractiveAuthentication no
PermitRootLogin no
EOF
sshd -t && echo "sshd configuration valid"

echo
echo "== 3. enable and start =="
systemctl enable ssh
systemctl start ssh
systemctl is-active ssh
ss -lntp | grep ':22' || echo "WARNING: nothing listening on 22"
