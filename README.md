# Shoji 障子

A calm, Japanese-inspired theme for [Hyprland](https://hypr.land): light through paper.
One palette file drives the bar, panels, launcher, lock screen, terminal, GTK and Qt apps,
folder icons and the wallpaper.

![Shoji desktop: terminal and Files in the Aizome palette](docs/screenshots/desktop.png)

## What you get

- **Six palettes** — 藍染 Aizome (indigo · gold, default), 夜 Yoru (ink · vermilion),
  夜桜 Yozakura (night · sakura), 苔 Koke (moss), 昼 Hiru (washi, light), 雪 Yuki (snow, light).
  Text, secondary text, accent, all 16 terminal colors and diff lines pass WCAG 4.5:1 on every palette.
- **Ensō levels** — volume, mic and brightness show as an open brush circle in the top right,
  even with Do Not Disturb on. A keyboard volume knob grows the stroke; the arc and the number
  glide to the new level.
- **One quiet bar** — workspaces as 一 二 三 四 (the current one is a seal; switch to 1 2 3 4 if you
  prefer; click or scroll to switch), the time with the weekday in kanji, Lucide icons, app tray
  icons tucked behind ⋯.
- **Koyomi** — click the clock for a kanji calendar on top of quick settings and notifications.
- **Popovers with one shape** — Sound (devices and volume), Network, Battery (laptops), Theme.
- **Launcher** (Super+Space) — frequent apps first; searches names, descriptions and keywords.
  Enter focuses the app if it is already open; Shift+Enter opens a new window. Apps with their own
  key show it on the right.
- **Shortcuts** (Super+/) — one cheat sheet with every described bind, in columns by group; click
  one to run it, or start typing to search.
- **Notifications** slide in from the right edge one at a time; the stack never stretches.
- **Theme manager** (Super+Shift+T) — six palettes, follow the sun (light by day, dark at night).
- **Lock screen** with an ensō around the clock and the date in kanji.
- **Paper folders** — Shoji draws its own folder icons in the palette; app icons come from Papirus.

| Theme manager | Koyomi | Ensō OSD |
|---|---|---|
| ![Theme manager with six palettes](docs/screenshots/theme-manager.png) | ![Calendar card above quick settings and notifications](docs/screenshots/koyomi.png) | ![Volume ensō in the top right](docs/screenshots/osd.png) |

![Lock screen: ensō around the clock, date in kanji](docs/screenshots/lock.jpg)

The rules behind the look: the accent only means "you are here" or "this is on" (never a border),
surfaces are warm translucent paper with one hairline, and nothing moves while idle.

## Install

### 1. Dependencies

Shoji needs Hyprland, waybar, swaync, fuzzel, hyprlock, PipeWire, NetworkManager, Python 3 with
GTK 3 + gtk-layer-shell bindings and cairo, and one wallpaper tool (awww, hyprpaper or swaybg).

Ubuntu / Debian (Hyprland itself from your usual source):

```sh
sudo apt install waybar sway-notification-center fuzzel hyprlock hyprpaper wireplumber \
  pulseaudio-utils network-manager python3-gi python3-cairo gir1.2-gtk-3.0 \
  gir1.2-gtklayershell-0.1 papirus-icon-theme curl fontconfig
```

Arch (package names; Shoji has not been tested on Arch yet):

```sh
sudo pacman -S hyprland waybar swaync fuzzel hyprlock hyprpaper wireplumber libpulse \
  networkmanager python-gobject python-cairo gtk3 gtk-layer-shell papirus-icon-theme curl
```

Optional: `ghostty` and `starship` (terminal colors and the `❯` prompt), `btop`, `qt6ct`,
`brightnessctl` and `power-profiles-daemon` (laptops: brightness ensō, battery popover).

### Terminal tools (optional)

`bat`, `delta` and `fzf` keep their own themes, so a dark theme like Catppuccin Mocha is unreadable
on Hiru and Yuki. Point them at Shoji and they follow every palette switch:

```sh
# ~/.zshrc or ~/.bashrc: fzf colors and BAT_THEME=ansi (bat uses the 16 terminal colors)
[ -f ~/.config/shoji/shell.sh ] && source ~/.config/shoji/shell.sh
```

```ini
# ~/.gitconfig: delta diff colors from the palette
[include]
	path = ~/.config/shoji/delta.gitconfig
[delta]
	features = shoji
```

Apps that draw with fixed RGB colors need their own light/dark setting. Claude Code's `dark` theme
writes white text, which disappears on Hiru and Yuki: run `/theme` and pick **Auto (match terminal)**
(`"theme": "auto"` in `~/.claude/settings.json`). It reads the terminal background, so it follows
every palette.

### 2. Run the installer

```sh
git clone https://github.com/andriar/shoji ~/shoji
~/shoji/install.sh            # or: ~/shoji/install.sh yoru
```

It backs up every file it replaces (`~/.local/share/shoji/backup-*.tar.gz`), downloads the fonts
(Shippori Mincho, Zen Kaku Gothic New, Lucide), installs the scripts to `~/.local/bin`, generates
the configs and applies a palette. It keeps your `starship.toml`; run with `SHOJI_PROMPT=1` to use
the Shoji prompt.

### 3. Add the Hyprland lines

The installer does not touch your Hyprland config. Copy the block for your config format
(Lua for 0.55+, or `hyprland.conf`) from [docs/hyprland.md](docs/hyprland.md): autostart, blur,
window hairlines and the keys. Check it with `Hyprland --verify-config`, then log out and back in.

### Uninstall

```sh
~/shoji/uninstall.sh
```

Restores the backup. Remove the Shoji lines from your Hyprland config, then log out and in.

## Use

| | |
|---|---|
| `Super+Space` | app launcher (Enter = open or focus, Shift+Enter = new window) |
| `Super+/` | cheat sheet of every shortcut (type to search) |
| `hypr-focus-or-launch` | bind a key per app: focus it if open, start it if not |
| `Super+Shift+T` | theme manager |
| click the clock | calendar, quick settings, notifications |
| click / scroll the ensō in the bar | sound devices / volume |
| volume keys, keyboard knob | ensō OSD |
| `shoji apply koke` | switch palette from a terminal |
| `shoji list` · `shoji doctor` | palettes · contrast and font check |
| `shoji wallpaper` | show the palette's ink-mountain wallpaper |

## Make your own palette

Add an entry to `PALETTES` in `bin/shoji` (ground, text, muted, accent, text-on-accent, and the
wallpaper sky and hills), then `shoji doctor <name>` to check contrast and `shoji apply <name>`.

## How it is built

- `bin/shoji` — the palettes and every generator: Hyprland, waybar, swaync, wlogout, fuzzel,
  hyprlock, ghostty, starship, btop, qt6ct, GTK 3/4 and fzf colors, plus the wallpaper,
  ensō images and folder icons (cairo).
- `bin/hypr-widgets` — one small GTK3 layer-shell process (about 60 MB): ensō OSD, calendar card,
  popovers, theme manager and launcher.
- `generators/` — the waybar and swaync configs, generated so icons and buttons match what is
  installed.
- `bin/shoji-ws` — workspace buttons for waybar. Its `hyprland/workspaces` module switches with
  `dispatch workspace N`, which Hyprland's Lua config rejects, so the buttons are custom modules that
  dispatch `hl.dsp.focus({ workspace = N })`.

## Status

Tested on Ubuntu 24.04 (Zorin OS 18) with Hyprland 0.56.2, waybar 0.14, swaync 0.9 and hyprlock
0.9.6, including a clean-home install inside a nested Hyprland. Not yet tested: Arch and newer
swaync (GTK4), multi-monitor, HiDPI scaling and real laptops. Issues and screenshots welcome.

## License

Code: MIT (see LICENSE). Fonts keep their own licenses (SIL OFL for Shippori Mincho and
Zen Kaku Gothic New, ISC for Lucide) and are downloaded by the installer, not bundled.
Folder glyphs are Lucide icons (ISC).
