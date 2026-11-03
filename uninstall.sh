#!/usr/bin/env bash
# Restore the files install.sh replaced (from its last backup). Fonts and wallpapers stay.
set -euo pipefail
last="$HOME/.local/share/shoji/last-backup"
[ -s "$last" ] || { echo "No Shoji backup found."; exit 1; }
backup=$(cat "$last")
"$HOME/.local/bin/shoji-ink" stop 2>/dev/null || true
systemctl --user stop shoji-session.service 2>/dev/null || true
for u in "$(cd "$(dirname "$0")" && pwd)"/config/systemd/user/*.service; do
  rm -f "$HOME/.config/systemd/user/$(basename "$u")"
done
systemctl --user daemon-reload 2>/dev/null || true
echo "Restoring $backup"
tar xzf "$backup" -C "$HOME"
# every script Shoji installs, unless the backup had one of that name (then it was restored above)
for f in "$(cd "$(dirname "$0")" && pwd)"/bin/*; do
  f=$(basename "$f")
  [ "$f" = __pycache__ ] && continue
  tar tzf "$backup" | grep -qx ".local/bin/$f" || rm -f "$HOME/.local/bin/$f"
done
rm -f "$HOME"/.local/share/shoji/widgets/shoji_widgets/*.py
rmdir "$HOME/.local/share/shoji/widgets/shoji_widgets" "$HOME/.local/share/shoji/widgets" 2>/dev/null || true
pkill -f "$HOME/.local/bin/hypr-widgets" 2>/dev/null || true
echo "Done. Remove the Shoji lines from your Hyprland config, then log out and in."
