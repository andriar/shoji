#!/usr/bin/env bash
# Restore the files install.sh replaced (from its last backup). Fonts and wallpapers stay.
set -euo pipefail
last="$HOME/.local/share/shoji/last-backup"
[ -s "$last" ] || { echo "No Shoji backup found."; exit 1; }
backup=$(cat "$last")
echo "Restoring $backup"
tar xzf "$backup" -C "$HOME"
for f in shoji hypr-widgets hypr-pop shoji-level shoji-clock shoji-ws; do
  tar tzf "$backup" | grep -qx ".local/bin/$f" || rm -f "$HOME/.local/bin/$f"
done
pkill -f "$HOME/.local/bin/hypr-widgets" 2>/dev/null || true
echo "Done. Remove the Shoji lines from your Hyprland config, then log out and in."
