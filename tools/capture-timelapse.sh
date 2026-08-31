#!/bin/bash
#
# Capture the dashboard as a timelapse, then assemble it into a video.
#
#   ./tools/capture-timelapse.sh [frames] [url] [outdir]
#
# Point it at a freshly restarted `python main.py --replay` so calibration
# starts from zero: the whole interest of the clip is watching the error
# vectors shrink, which is invisible if the model is already converged.
#
# Headless Chrome sometimes writes the PNG and then never exits, which silently
# stalls a naive loop. We therefore poll for the file and kill the process
# ourselves rather than trusting it to return.
set -u

FRAMES=${1:-45}
URL=${2:-http://localhost:8090/}
OUT=${3:-/tmp/sismo-frames}
CHROME=${CHROME:-/Applications/Google Chrome.app/Contents/MacOS/Google Chrome}

if [ ! -x "$CHROME" ]; then
  echo "Chrome not found at: $CHROME (override with CHROME=...)" >&2
  exit 1
fi

if ! curl -sf -m 5 -o /dev/null "$URL"; then
  echo "No dashboard answering at $URL" >&2
  exit 1
fi

mkdir -p "$OUT"
rm -f "$OUT"/frame_*.png

for i in $(seq -w 1 "$FRAMES"); do
  frame="$OUT/frame_$i.png"
  "$CHROME" --headless --disable-gpu --hide-scrollbars --no-first-run \
    --virtual-time-budget=2500 --window-size=1440,900 \
    --screenshot="$frame" "$URL" >/dev/null 2>&1 &
  pid=$!

  for _ in $(seq 1 60); do
    [ -s "$frame" ] && break
    sleep 0.25
  done
  sleep 0.4
  kill "$pid" 2>/dev/null
  wait "$pid" 2>/dev/null

  echo "frame $i/$FRAMES"
  sleep 1
done

count=$(ls "$OUT"/frame_*.png 2>/dev/null | wc -l | tr -d ' ')
echo "captured $count frames in $OUT"

if command -v ffmpeg >/dev/null 2>&1; then
  # yuv420p and the /2*2 scale keep the file playable in browsers and by the
  # Hackster player, which reject odd pixel dimensions.
  ffmpeg -y -loglevel error -framerate 8 -pattern_type glob \
    -i "$OUT/frame_*.png" \
    -vf "scale=trunc(iw/2)*2:trunc(ih/2)*2" -c:v libx264 -pix_fmt yuv420p \
    "$OUT/calibration-timelapse.mp4"
  echo "wrote $OUT/calibration-timelapse.mp4"
else
  echo "ffmpeg not installed: frames captured, video not assembled" >&2
fi
