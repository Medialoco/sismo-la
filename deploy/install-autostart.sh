#!/bin/sh
# Make the Sismo-LA station come back on its own after a reboot or a power cut.
#
# App Lab has no autostart: `arduino-app-cli app start` creates the container
# with RestartPolicy=no, and the arduino-app-cli daemon does not re-launch the
# apps that were running before. Without this, an unattended station dies at
# the first power cut and nobody notices.
#
# This script needs NO root, which matters because the board's sudo password
# is easy to lose: `adb` logs in as the unprivileged `arduino` user and
# `adb root` is refused by the image. It relies only on what that user already
# has -- membership of the `docker` group, and a running `cron`.
#
# deploy/sismo-la.service does the same job through systemd and is cleaner,
# but installing it needs root.
#
# Run it ON the board:  sh deploy/install-autostart.sh
set -e

APP_DIR=${1:-/home/arduino/ArduinoApps/sismo-la}
CLI=/usr/bin/arduino-app-cli
LOG=/home/arduino/sismo-la-boot.log

# 1. Docker restarts the container by itself at boot. This is the fast path:
#    it needs neither cron nor the app-cli daemon. "unless-stopped" keeps the
#    semantics of `arduino-app-cli app stop` -- a deliberate stop stays a stop.
container=$(docker ps -a --filter "name=sismo-la" --format '{{.Names}}' | head -1)
if [ -n "$container" ]; then
  docker update --restart unless-stopped "$container" >/dev/null
  echo "docker: $container -> restart=unless-stopped"
else
  echo "docker: no sismo-la container yet, skipping (start the app once first)"
fi

# 2. Cron covers what Docker cannot: if the container was removed or the image
#    rebuilt, only app-cli can recreate it. `app restart` starts a stopped app
#    and restarts a running one, so running both mechanisms is harmless.
#    The delay lets docker, the router and the app-cli daemon settle first.
entry="@reboot sleep 90 && $CLI app restart $APP_DIR >> $LOG 2>&1"
(crontab -l 2>/dev/null | grep -v 'sismo-la' || true; echo "$entry") | crontab -
echo "cron:   $(crontab -l | grep -c 'sismo-la') @reboot entry installed"

echo
echo "Done. Verify with:  sudo reboot  (then, once it is back)"
echo "  arduino-app-cli app list | grep sismo-la"
echo "  cat $LOG"
