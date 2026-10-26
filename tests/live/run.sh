#!/usr/bin/env bash
# Shoji's live test: a second Hyprland, hidden inside yours, runs Shoji from this checkout and
# drives it the way a user would (meetings, Alt+Tab, idle → ink → lock, batches, the end of the
# day, the eye rest), checking what reaches the screen. Offscreen renders cannot see these: every
# bug it was built from looked right offscreen.
#
#   tests/live/run.sh            about four minutes; prints PASS/FAIL per check, exits 1 on a FAIL
#
# What keeps it away from your session:
#   - its own HOME, runtime dir and session bus (nothing of yours is read or written but the fonts,
#     which it uses as they are);
#   - its window sits on a hidden special workspace (a runtime rule, undone at the end);
#   - stand-ins first on its PATH (tests/live/stubs.py): pkill / pgrep / pidof only see the test's
#     processes; loginctl, xdg-open, nmcli, bluetoothctl … only log the call;
#   - at the end every process with the test's HOME ends, and only those.
# Needs: a running Hyprland, grim, swaync, hypridle, hyprlock, gir1.2-atspi-2.0.
set -euo pipefail

REPO=$(cd "$(dirname "$0")/../.." && pwd)
[ -n "${HYPRLAND_INSTANCE_SIGNATURE:-}" ] || { echo "Run this from a Hyprland session: the test session hides inside it."; exit 2; }
for c in Hyprland hyprctl grim dbus-run-session swaync swaync-client hypridle hyprlock notify-send python3; do
  command -v "$c" >/dev/null || { echo "Missing: $c"; exit 2; }
done
python3 -c 'import gi; gi.require_version("Atspi", "2.0")' 2>/dev/null || { echo "Missing: gir1.2-atspi-2.0 (buttons are pressed through AT-SPI)"; exit 2; }
[ -s "$HOME/.local/share/fonts/Shoji/lucide-info.json" ] || { echo "Shoji's fonts are not installed (run install.sh once)."; exit 2; }

WORK=$(mktemp -d "${TMPDIR:-/tmp}/shoji-live.XXXXXX")
RUNDIR=$(mktemp -d "${TMPDIR:-/tmp}/sl.XXX")   # short: Wayland socket paths must stay under 108 bytes
chmod 700 "$RUNDIR"
H="$WORK/home"
HOST_WL="${XDG_RUNTIME_DIR}/${WAYLAND_DISPLAY:-wayland-1}"
RULE='hl.window_rule({ name = "shoji-live", match = { class = "^(aquamarine)$" }, workspace = "special:shoji-live silent", no_initial_focus = true })'
UNRULE='hl.window_rule({ name = "shoji-live", match = { class = "^shoji-never$" }, workspace = "special:shoji-live silent", no_initial_focus = true })'
export SHOJI_LIVE_HOME="$H"

cleanup() {
  n=$(SHOJI_LIVE_HOME="$H" python3 "$REPO/tests/live/stubs.py" killall)
  hyprctl eval "$UNRULE" >/dev/null 2>&1 || true
  echo "Ended $n test processes. Files: $WORK"
}
trap cleanup EXIT

echo "Setting up a test home in $WORK"
mkdir -p "$H/.local/bin" "$H/.local/share/shoji/widgets" "$H/.config/shoji" "$H/.config/hypr" \
         "$H/.local/share/evolution/calendar/system" "$H/.cache"
for f in "$REPO"/bin/*; do if [ -f "$f" ]; then install -m 755 "$f" "$H/.local/bin/"; fi; done
cp -r "$REPO/widgets/shoji_widgets" "$H/.local/share/shoji/widgets/"
install -m 644 "$REPO"/generators/*.py "$H/.config/shoji/"
cp "$REPO/config/hypr/hyprlock.conf" "$H/.config/hypr/hyprlock.conf"
ln -s "$HOME/.local/share/fonts" "$H/.local/share/fonts"
python3 "$REPO/tests/live/stubs.py" install "$WORK/stubs"
cat > "$H/.config/shoji/prefs.json" <<'JSON'
{"auto_silent": true, "rin": false, "greet": false, "weather": false, "ink": true, "shimai": "",
 "batch": 0, "eye_rest": false, "seasonal": false, "follow_sun": false}
JSON

# the shipped idle steps, minutes made seconds; not general{}: it reacts to the real machine's sleep
python3 - "$REPO/config/hypr/hypridle.conf" "$WORK/hypridle.conf" <<'PY'
import re, sys
src = open(sys.argv[1]).read()
blocks = re.findall(r"listener \{.*?\n\}", src, re.S)
keep = [b.replace("timeout = 480", "timeout = 5").replace("timeout = 600", "timeout = 14") for b in blocks if "dpms" not in b]
open(sys.argv[2], "w").write("general {\n    ignore_systemd_inhibit = true\n}\n\n" + "\n\n".join(keep) + "\n")
PY

# today's calendar: an event running now, ending in two or three minutes, and one with a call link soon
MEETING_END=$(python3 - "$H/.local/share/evolution/calendar/system/calendar.ics" <<'PY'
import sys, datetime as dt
now = dt.datetime.now().replace(second=0, microsecond=0)
end = now + dt.timedelta(minutes=3)
z = lambda d: d.astimezone(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
ev = lambda uid, s, e, what, extra="": (f"BEGIN:VEVENT\r\nUID:{uid}\r\nDTSTAMP:{z(now)}\r\nDTSTART:{z(s)}\r\n"
                                        f"DTEND:{z(e)}\r\nSUMMARY:{what}\r\n{extra}END:VEVENT\r\n")
open(sys.argv[1], "w").write("BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//shoji live//EN\r\n"
    + ev("live-now", now - dt.timedelta(minutes=2), end, "Live test: design review")
    + ev("live-soon", now + dt.timedelta(minutes=6), now + dt.timedelta(minutes=30), "Live test: weekly sync",
         "DESCRIPTION:https://meet.google.com/aaa-bbbb-ccc\r\n")
    + "END:VCALENDAR\r\n")
print(end.isoformat())
PY
)

cat > "$WORK/hyprland.lua" <<LUA
hl.on("hyprland.start", function()
    hl.exec_cmd("swaync")
    hl.exec_cmd("~/.local/bin/hypr-widgets")
    hl.exec_cmd("sh -c 'echo \$DBUS_SESSION_BUS_ADDRESS > $WORK/bus'")
end)
hl.config({ animations = { enabled = false } })
LUA

ENVS=(HOME="$H" USER="$USER" LANG=en_US.UTF-8 LC_TIME=C.UTF-8 PATH="$WORK/stubs:$PATH"
      XDG_RUNTIME_DIR="$RUNDIR" XDG_DATA_DIRS="${XDG_DATA_DIRS:-/usr/local/share:/usr/share}"
      SHOJI_LIVE_HOME="$H" SHOJI_LIVE_WORK="$WORK" SHOJI_LIVE_MEETING_END="$MEETING_END"
      SHOJI_EYE_EVERY_S=20 HYPRLAND_NO_CRASHREPORTER=1)

echo "Palette and generated configs"
env -i "${ENVS[@]}" python3 "$H/.local/bin/shoji" apply aizome >/dev/null 2>&1 || true
env -i "${ENVS[@]}" python3 "$H/.config/shoji/gen_waybar.py" >/dev/null
env -i "${ENVS[@]}" python3 "$H/.config/shoji/gen_swaync.py" >/dev/null

echo "Starting the hidden test session"
hyprctl eval "$RULE" >/dev/null
env -i "${ENVS[@]}" WAYLAND_DISPLAY="$HOST_WL" dbus-run-session -- Hyprland -c "$WORK/hyprland.lua" >"$WORK/hyprland.log" 2>&1 &
disown   # ended by cleanup, without a job notice
for _ in $(seq 60); do
  sock=$(ls "$RUNDIR"/hypr/*/.socket.sock 2>/dev/null | head -1 || true)
  [ -n "$sock" ] && [ -s "$WORK/bus" ] && break
  sleep 0.5
done
[ -n "${sock:-}" ] || { echo "The test session did not start; see $WORK/hyprland.log"; exit 1; }
SIG=$(basename "$(dirname "$sock")")
WL=$(cd "$RUNDIR" && ls wayland-* 2>/dev/null | grep -v lock | head -1 || true)
INNER=(HYPRLAND_INSTANCE_SIGNATURE="$SIG" WAYLAND_DISPLAY="$WL" DBUS_SESSION_BUS_ADDRESS="$(cat "$WORK/bus")")

# a headless output to work on, and the hidden window's own output off
env -i "${ENVS[@]}" "${INNER[@]}" hyprctl output create headless SHOJI >/dev/null
env -i "${ENVS[@]}" "${INNER[@]}" hyprctl eval 'hl.monitor({ output = "SHOJI", mode = "1600x900@60", position = "4000x0", scale = 1 })' >/dev/null
env -i "${ENVS[@]}" "${INNER[@]}" hyprctl eval 'hl.monitor({ output = "WAYLAND-1", disabled = true })' >/dev/null

echo "Running the scenarios"
env -i "${ENVS[@]}" "${INNER[@]}" python3 "$REPO/tests/live/scenarios.py"
