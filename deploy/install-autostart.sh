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
# `adb root` is refused by the image.
#
# READ THIS BEFORE TRUSTING THE CRON HALF. On the reference board the
# `arduino` account's password is EXPIRED, and PAM refuses to run cron jobs
# for such an account:
#
#   CRON[391]: pam_unix(cron:account): expired password for user arduino
#              Authentication token is no longer valid; new one required
#
# The @reboot entry then fires and does nothing at all -- not even creating
# its log file, because the command never runs. A real power cut on
# 2026-08-31 left the board booted and on WiFi with the app down. So the
# Docker restart policy below is not the "fast path", it is the ONLY path
# until that password is reset, and the check at the end of this script tells
# you which situation you are in.
#
# deploy/sismo-la.service does the same job through systemd, is cleaner, and
# does not care about the password -- but installing it needs root.
#
# Run it ON the board:  sh deploy/install-autostart.sh
set -e

APP_DIR=${1:-/home/arduino/ArduinoApps/sismo-la}
CLI=/usr/bin/arduino-app-cli
LOG=/home/arduino/sismo-la-boot.log

# 1. Docker restarts the container by itself at boot, as root, without PAM in
#    the way. "unless-stopped" keeps the semantics of `arduino-app-cli app
#    stop` -- a deliberate stop stays a stop.
#    CAUTION: `arduino-app-cli app start|restart` RECREATES the container and
#    the new one carries the compose policy, which is "no". Re-run this script
#    after every deploy; it is idempotent.
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

# 3. Say plainly whether that cron entry can actually run. An expired password
#    makes it inert, and an autostart you believe in but that does not fire is
#    worse than none at all.
echo
if passwd --status "$(id -un)" 2>/dev/null | awk '{exit ($2=="P")?0:1}'; then
  echo "cron:   password looks usable, both mechanisms should work"
else
  echo "WARNING: this account's password is expired or unset, so PAM will"
  echo "         refuse the cron job and the @reboot entry above will never"
  echo "         run. The Docker policy is then your only autostart."
  echo "         Reset it (needs a console or root) to get cron back."
fi

echo
echo "The ONLY conclusive test is a real power cut. After it comes back:"
echo "  arduino-app-cli app list | grep sismo-la     # expect: running"
echo "  docker inspect sismo-la-main-1 --format '{{.HostConfig.RestartPolicy.Name}}'"
echo "  cat $LOG                                     # empty file = cron never ran"
