# Shoji 障子

A calm Japanese-inspired theme for Hyprland: light through paper. One palette file drives the bar,
panels, launcher, lock screen, terminal, GTK/Qt apps and the wallpaper.

- **Six palettes**: 藍染 Aizome (indigo · gold, default), 夜 Yoru (ink · vermilion),
  夜桜 Yozakura (night · sakura), 苔 Koke (moss), 昼 Hiru (washi, light), 雪 Yuki (snow, light).
  Every text, secondary-text and accent color passes WCAG 4.5:1 on its ground (`shoji doctor`).
- **Ensō levels**: volume and mic show as an open brush circle, top right, even with Do Not Disturb on.
  Turning a keyboard volume knob grows the stroke.
- **One bar**: workspaces as 一 二 三 四 (the current one is a vermilion-style seal; switch to 1 2 3 4
  in the theme manager), time with the weekday in kanji, quiet status icons (Lucide).
- **Popovers** with one shape: Sound (output/input devices + volume), Network, Theme manager.
- **Koyomi** calendar next to the notification panel, kanji week, today as a seal.
- **Lock screen** with an ensō around the clock and the date in kanji.
- Rules: the accent only means "you are here" or "this is on" — never a border or decoration;
  no glow, no gradients on surfaces; nothing moves while idle.

## Install

Needs Hyprland, waybar, swaync, fuzzel, hyprlock, PipeWire (`wpctl`, `pactl`), NetworkManager (`nmcli`),
Python 3 with `python3-cairo` and `gir1.2-gtklayershell-0.1`, and one wallpaper tool (awww, hyprpaper or swaybg).
Recommended: Papirus icons (app icons; Shoji draws its own folders). Optional: ghostty, starship, btop, qt6ct,
brightnessctl and power-profiles-daemon (laptops: brightness ensō, battery popover with power mode).

Tested on Ubuntu 24.04 (Zorin OS 18) with Hyprland 0.56.2, waybar 0.14, swaync 0.9, hyprlock 0.9.6 —
including a clean-home install inside a nested Hyprland. Not yet tested: Arch / newer swaync (its GTK4
versions may need CSS changes), multi-monitor, HiDPI scaling, laptops (battery and brightness).

```sh
git clone <this repo> ~/shoji && ~/shoji/install.sh          # or: install.sh yoru
```

The installer backs up every file it replaces, downloads the fonts (Shippori Mincho and
Zen Kaku Gothic New under the SIL OFL, Lucide under ISC) and applies a palette. It does not touch
your Hyprland config: add the lines in [docs/hyprland.md](docs/hyprland.md), then log out and in.

`./uninstall.sh` restores the backup.

## Use

| | |
|---|---|
| `Super+Shift+T` | theme manager (palettes, follow-the-sun, kanji or arabic numerals) |
| `shoji apply koke` | switch palette from a terminal |
| `shoji list` · `shoji doctor` | palettes · contrast and font check |
| click the clock | Koyomi calendar + quick settings + notifications |
| click / scroll the ensō in the bar | Sound popover / volume |
| `Super+Space` | app launcher (frequent apps first, searches names, descriptions and keywords) |

## Files

`bin/shoji` is the single source of colors: edit `PALETTES` there to add one. It writes
`~/.config/{hypr/theme.*,waybar,swaync,wlogout}/colors.css`, fuzzel, ghostty, starship, btop, qt6ct and
GTK color files, renders the ensō images and the ink-mountain wallpaper. `bin/hypr-widgets` is one
small GTK3 layer-shell process for the OSD, calendar and popovers.

## License

MIT for the code (see LICENSE). Fonts keep their own licenses and are downloaded, not bundled.
