# Changelog

## 0.2.1 — 2026-10-26

- README: a tour of every surface, features grouped, the keys in one table. Screenshots taken in a
  nested Hyprland with demo data (no private windows).
- Koyomi opens on the focused monitor (it used to take the first one), and the card shrinks back
  to the panel's height after the agenda loads.
- Koyomi's two halves fade in together.

## 0.2.0 — 2026-10-26

The zen release: a design pass argued out between three design reviews, a calmer bar, the Koyomi
panel as one container, music on the bar, focus sessions, and the palette reaching the apps you
live in.

- **Koyomi** is one container under the clock: the calendar (click a day for its events and due
  tasks from Evolution Data Server: Google calendars, holidays, Google Tasks), today's micro-season
  (七十二候) by the date, quick toggles that show their state, and the notifications beside it.
  Clicks reach it again (swaync no longer grabs the keyboard exclusively).
- **Notifications** stack per app (swaync 0.10+, see README for 24.04), clicking one takes you to
  its window and workspace, bot channels can be kept out of the panel (swaync-local.json), and a
  small synthesised bell (鈴) rings for critical ones.
- **Bar**: a bell for notifications; now playing as smooth CSS bars tinted with the cover's colour
  plus the title; the Media popover (cover on its own colour wash, seek bar) as glass; cpu · mem
  only from 70%.
- **Zazen** (Super+Z): 25 minutes of focus with an ensō counting down.
- **Look**: Kaisei Opti as the display font, one type scale and one radius scale, a brush-stroke
  ensō on the lock screen, ink-wash ridges and tonight's moon on the wallpaper, an optional
  seasonal accent (紅梅 / 青竹 / 紅葉 / 白群), tabbed windows (Super+T) as paper tabs.
- **App themes** from the palette: VS Code, Spotify (spicetify), Chrome.
- **Shortcuts sheet** (Super+/) aligned, nothing truncated, follows Hyprland reloads; screenshot
  keys for keyboards without PrtSc (Super+Shift+P / Super+Ctrl+P).
- Opt-in terminal greeting (`shoji greet`).

## 0.1.5 – 0.1.12 — 2026-10-25

- Terminal contrast on light palettes; Claude Code `auto` theme.
- Clickable workspaces under Lua Hyprland (shoji-ws), smoother toasts and OSD.
- Super+/ shortcuts sheet; app keys (Super+K Slack, B Chrome, D Discord, …).
- hypr-term: new ghostty windows in ~20 ms instead of ~1 s.
- GTK3 apps (Thunar first) follow the palette; `shoji apply` restarts Thunar in place.
- Launcher search no longer dies after the first open.

## 0.1.4 — 2026-10-24

- Launcher: Enter focuses the app's window when it is already open (Shift+Enter opens a new one).
- `hypr-focus-or-launch CLASS_REGEX COMMAND`: one key per app — focus it if open, start it if not,
  press again to cycle its windows. docs/hyprland.md has a Super+K → Slack example.

## 0.1.3 — 2026-10-24

- Launcher: apps did not open (click or Enter). Usage counts were written under
  `~/.local/state/shoji/`, which is the palette state file; they now live in
  `~/.local/state/shoji-launcher.json`, and saving them can no longer block a launch.
- Launcher: loose letters-in-order matching only applies to app names (fewer odd results).
- `hypr-pop launcher <text>` opens the launcher with a query.

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
