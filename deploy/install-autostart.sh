#!/bin/sh
# Make the Sismo-LA station come back on its own after a reboot or a power cut.
#
# WHAT ACTUALLY GOES WRONG, measured on the reference board 2026-08-31:
#
#   02:37:12  dockerd starts
#   02:37:17  dockerd finishes loading containers and STARTS sismo-la-main-1
#   02:37:17  arduino-app-cli.service starts
#   02:37:18  something sends SIGTERM to the container
#   02:37:28  it has not exited, so dockerd forces it -- exit 137
#             "ShouldRestart failed, container will not be restarted
#              ... hasBeenManuallyStopped=true"
#
# So the Docker restart policy is not ignored, it works: the container is
# started at boot. The App Lab daemon then stops it, because App Lab has no
# notion of an app that should still be running. Worse, Docker records that as
# a deliberate stop, and "unless-stopped" means exactly "restart unless someone
# stopped it on purpose" -- so from the NEXT boot on, the container is not even
# started. That is why the station stayed dead through two power cycles.
#
# Cron would be the natural place to start the app a bit later, and it is
# unusable here: the `arduino` account's password is expired, so PAM refuses
# every job it owns ("pam_unix(cron:account): expired password for user
# arduino"). The @reboot entry fires and does nothing -- not even creating its
# log file. Resetting that password needs a console or root, which we do not
# have; `adb` logs in unprivileged and `adb root` is refused by the image.
#
# What is left is Docker itself: dockerd starts as root at boot and never
# consults PAM. This installs a small sidecar container with
# "--restart always" that waits out the App Lab reconcile and then keeps the
# station up. No root, no password, no cron.
#
# Run it ON the board:  sh deploy/install-autostart.sh
set -e

APP_DIR=${1:-/home/arduino/ArduinoApps/sismo-la}
WATCHDOG=sismo-la-watchdog

container=$(docker ps -a --filter "name=sismo-la-main" --format '{{.Names}}' | head -1)
if [ -z "$container" ]; then
  echo "error: no sismo-la container. Start the app once first:"
  echo "  arduino-app-cli app start $APP_DIR"
  exit 1
fi

# 1. Keep the restart policy anyway. It is not sufficient -- see above -- but it
#    is what recovers the station when dockerd alone is restarted, and it costs
#    nothing. "always" rather than "unless-stopped" precisely because App Lab's
#    stop is recorded as manual and "unless-stopped" would honour it forever.
#    CAUTION: `arduino-app-cli app start|restart` RECREATES the container with
#    the compose policy, which is "no". Re-run this script after every deploy;
#    it is idempotent.
docker update --restart always "$container" >/dev/null
echo "docker:   $container -> restart=always"

# 2. The sidecar. It needs the Docker socket (group-only access, so pass the
#    group in) and the app folder, read-only, for the script and the opt-out
#    file. The image is the app's own, which is already on the board -- nothing
#    is pulled, so this still works when the boot comes up without a network.
image=$(docker inspect -f '{{.Config.Image}}' "$container")
gid=$(getent group docker | cut -d: -f3)

docker rm -f "$WATCHDOG" >/dev/null 2>&1 || true
docker run -d \
  --name "$WATCHDOG" \
  --restart always \
  --group-add "$gid" \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v "$APP_DIR":/station:ro \
  -e SISMO_CONTAINER="$container" \
  --entrypoint python3 \
  "$image" /station/deploy/watchdog.py >/dev/null
echo "watchdog: $WATCHDOG running on $image (docker gid $gid)"

echo
echo "To stop the station on purpose without the watchdog undoing it:"
echo "  touch $APP_DIR/.autostart-disabled"
echo
echo "The ONLY conclusive test is a real reboot or power cut. After it:"
echo "  docker ps --format '{{.Names}} {{.Status}}'   # both containers up"
echo "  docker logs $WATCHDOG                         # what it decided"
echo "  curl -sf http://<board>:8000/api/state >/dev/null && echo dashboard ok"
