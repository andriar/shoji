# Changelog

## 0.1.2 — 2026-10-24

- Lock screen background comes from `~/.cache/shoji/lock.png`, written by `shoji` (and hypr-wall),
  so a clean install no longer shows a black lock screen.
- Softer mist band in the wallpaper (no visible edge on light palettes).
- README: screenshots and step-by-step install for Ubuntu/Debian and Arch.

## 0.1.1 — 2026-10-24

- Light palettes (Hiru, Yuki): the terminal's bright row now goes darker, so all 16 colors pass 4.5:1
  (seven were 2.5–4.4:1). `shoji doctor` checks the terminal colors too.
- Follow the sun switches only at 06:00 and 18:00, so a palette picked by hand is no longer
  overwritten a few minutes later.
- Brightness keys (`hypr-osd bright-up|bright-down`, needs brightnessctl) show the ensō as 明 · BRIGHT.
- Battery popover (`hypr-pop battery`): ensō level, time left, power mode via power-profiles-daemon.

## 0.1.0 — 2026-10-24

First public draft.

- `shoji`: six palettes (Aizome, Yoru, Yozakura, Koke, Hiru, Yuki), one generator for Hyprland,
  waybar, swaync, fuzzel, hyprlock, wlogout, ghostty, starship, btop, qt6ct, GTK 3/4 and fzf.
- Renders the ink-mountain wallpaper, the lock-screen ensō, the bar's ensō level rings and an icon
  theme with paper folders (Lucide glyphs), per palette.
- `hypr-widgets`: ensō volume / mic OSD (shows through Do Not Disturb), Koyomi calendar card,
  Sound and Network popovers, theme manager, app launcher.
- `shoji wallpaper` works with awww, hyprpaper (0.8 block syntax) or swaybg.
- Installer with backup, uninstaller; tested with a clean home in a nested Hyprland.
