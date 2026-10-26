#!/usr/bin/env bash
# Shoji installer: fonts, scripts, generated configs. Backs up everything it replaces.
# Does not edit your hyprland config: see docs/hyprland.md for the lines to add.
set -euo pipefail

REPO=$(cd "$(dirname "$0")" && pwd)
STAMP=$(date +%Y%m%d-%H%M%S)
BACKUP="$HOME/.local/share/shoji/backup-$STAMP.tar.gz"
BIN="$HOME/.local/bin"
FONTS="$HOME/.local/share/fonts/Shoji"
PALETTE="${1:-aizome}"

say() { printf '\033[1m%s\033[0m\n' "$*"; }

say "1/6 Checking dependencies"
missing=()
for cmd in hyprctl waybar swaync swaync-client fuzzel hyprlock wpctl pactl nmcli python3 curl fc-cache; do
  command -v "$cmd" >/dev/null || missing+=("$cmd")
done
python3 -c 'import cairo, gi; gi.require_version("GtkLayerShell", "0.1")' 2>/dev/null || missing+=("python3-cairo / gir1.2-gtklayershell-0.1")
if [ ${#missing[@]} -gt 0 ]; then
  echo "Missing: ${missing[*]}"
  echo "Install them with your package manager, then run this again."
  exit 1
fi
command -v starship >/dev/null || echo "  (optional) starship not found: the terminal prompt stays as it is"
command -v ghostty  >/dev/null || echo "  (optional) ghostty not found: terminal colors are skipped"
python3 -c 'import gi; gi.require_version("ECal", "2.0")' 2>/dev/null \
  || echo "  (optional) gir1.2-ecal-2.0 not found: Koyomi shows no events or tasks"

say "2/6 Backing up current files to $BACKUP"
mkdir -p "$(dirname "$BACKUP")"
targets=()
for f in .config/waybar .config/swaync .config/fuzzel .config/wlogout/style.css .config/hypr/hyprlock.conf \
         .config/ghostty/config .config/starship.toml .config/gtk-3.0 .config/gtk-4.0 \
         .config/btop/btop.conf .config/qt6ct/qt6ct.conf; do
  [ -e "$HOME/$f" ] && targets+=("$f")
done
for f in shoji hypr-widgets hypr-osd hypr-pop hypr-shot hypr-motion hypr-clip shoji-btbat shoji-level shoji-clock shoji-ws shoji-media shoji-zazen hypr-term audio-switch fuzzel-at-cursor \
         hypr-toggle-app hypr-sysload keep-awake hypr-nightlight hypr-record hypr-wall; do
  [ -e "$BIN/$f" ] && targets+=(".local/bin/$f")
done
tar czf "$BACKUP" -C "$HOME" "${targets[@]}" 2>/dev/null || tar czf "$BACKUP" --files-from /dev/null
echo "$BACKUP" > "$HOME/.local/share/shoji/last-backup"

say "3/6 Fonts (Kaisei Opti, Zen Kaku Gothic New, Lucide)"
mkdir -p "$FONTS"
gf=https://raw.githubusercontent.com/google/fonts/main/ofl
for f in kaiseiopti/KaiseiOpti-{Regular,Medium,Bold} zenkakugothicnew/ZenKakuGothicNew-{Regular,Medium,Bold}; do
  out="$FONTS/$(basename "$f").ttf"
  [ -s "$out" ] || curl -fsSL -o "$out" "$gf/$f.ttf"
done
curl -fsSL -o "$FONTS/OFL-KaiseiOpti.txt" "$gf/kaiseiopti/OFL.txt"
curl -fsSL -o "$FONTS/OFL-ZenKakuGothicNew.txt" "$gf/zenkakugothicnew/OFL.txt"
lucide=https://cdn.jsdelivr.net/npm/lucide-static@0.460.0
[ -s "$FONTS/lucide.ttf" ] || curl -fsSL -o "$FONTS/lucide.ttf" "$lucide/font/lucide.ttf"
curl -fsSL -o "$FONTS/lucide-info.json" "$lucide/font/info.json"
curl -fsSL -o "$FONTS/LICENSE-lucide.txt" "$lucide/LICENSE"
fc-cache -f "$FONTS" >/dev/null

say "4/6 Scripts → $BIN"
mkdir -p "$BIN" "$HOME/.config/shoji"
install -m 755 "$REPO"/bin/* "$BIN/"
# hypr-widgets' surfaces: the shoji_widgets package
mkdir -p "$HOME/.local/share/shoji/widgets/shoji_widgets"
install -m 644 "$REPO"/widgets/shoji_widgets/*.py "$HOME/.local/share/shoji/widgets/shoji_widgets/"
install -m 644 "$REPO"/generators/*.py "$HOME/.config/shoji/"

say "5/6 Configs"
mkdir -p "$HOME/.config/fuzzel" "$HOME/.config/wlogout" "$HOME/.config/hypr" "$HOME/.config/waybar" "$HOME/.config/swaync"
sed "s|@HOME@|$HOME|g" "$REPO/config/fuzzel/fuzzel.ini" > "$HOME/.config/fuzzel/fuzzel.ini"
cp "$REPO/config/wlogout/style.css" "$HOME/.config/wlogout/style.css"
cp "$REPO/config/hypr/hyprlock.conf" "$HOME/.config/hypr/hyprlock.conf"
# prompt: only when you have none, or ask for it with SHOJI_PROMPT=1 (your old one is in the backup)
if command -v starship >/dev/null; then
  if [ ! -e "$HOME/.config/starship.toml" ] || [ "${SHOJI_PROMPT:-0}" = 1 ]; then
    cp "$REPO/config/starship.toml" "$HOME/.config/starship.toml"
  else
    echo "  kept your starship.toml (SHOJI_PROMPT=1 ./install.sh to use the Shoji prompt)"
  fi
fi
if command -v ghostty >/dev/null; then
  mkdir -p "$HOME/.config/ghostty"
  [ -e "$HOME/.config/ghostty/config" ] || cp "$REPO/config/ghostty/config" "$HOME/.config/ghostty/config"
  grep -q '^config-file = ?theme-local' "$HOME/.config/ghostty/config" ||
    sed -i '1i config-file = ?theme-local' "$HOME/.config/ghostty/config"
fi
python3 "$HOME/.config/shoji/gen_waybar.py"
python3 "$HOME/.config/shoji/gen_swaync.py"

say "6/6 Applying palette: $PALETTE"
"$BIN/shoji" apply "$PALETTE"

cat <<EOF

Done. Two things left for you:
  1. Add the Hyprland lines from docs/hyprland.md (autostart, blur, keybinds), then log out and in.
     Fonts only show up in waybar/swaync after they restart.
  2. Super+Shift+T opens the theme manager. \`shoji list\` shows every palette.

Undo everything: $REPO/uninstall.sh
EOF
