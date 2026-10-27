# Changelog

## 0.8.1 — 2026-10-27

- Zazen no longer turns the bar inside out: it asks Hyprland whether the bar is showing before it
  toggles it (a hidden waybar drops to the bottom layer). A waybar restart in the middle of a
  session used to leave Super+Z showing the bar on start and hiding it on stop.
- Preferences is easy to reach: **Super+,**, listed in Super+/, and a click on the drawer's Focus
  card (Esc returns to the drawer).
- Hot edge: one strip per monitor, kept in step when monitors come and go; the pointer has to rest
  still for 500 ms (any movement restarts the wait, a held button cancels, fullscreen skips). The
  drawer then ignores clicks for 600 ms, so a click aimed at the window below never lands on a card.
- Counts in words, singular and plural in all three languages ("13 of 14 running" instead of
  "13/14"); Homelab says "Checking…" once it is set up but before its first reading.

## 0.8.0 — 2026-10-27

- 家 Homelab: `shoji-homelab` watches Docker (by compose stack), systemd units, public endpoints,
  disks / memory / swap and backup ages every 30 s; the bar shows a quiet 11 px server glyph, red
  with the number down beside it (two modules, one font each, so both sit on the bar's centre).
  Its popover (`hypr-pop homelab`) opens under the cursor: NEEDS YOU first, then a quiet inventory
  (muted dots and names, readings in each row's tooltip, actions dimmed until the row is hovered);
  it restarts, stops, starts, runs timers and opens logs without asking. Opt-in: nothing shows until
  `~/.config/shoji/homelab.json` exists. Changes (down, back up) send a notification.
- 休 The rest card: after zazen, one suggestion over a dimmed desktop (prefs "zazen_dim"), picked
  by `shoji_widgets/rest.py` for the minutes, hour, weather, next meeting and your skip history;
  box breathing with an ensō; ✓ / ↻ / ⏭ logged to ~/.local/state/shoji-rest.log. Focus and rest
  lengths in Preferences ("zazen": 25/5, 50/10, 90/20; every 4th rest "zazen_long").
- Your own popovers: `~/.config/shoji/popovers/*.py` (`POPOVERS = [...]`, built on `Listing`,
  the Homelab look) and your own bar modules in `~/.config/shoji/waybar-local.json`.

## 0.7.0 — 2026-10-26

- The wallpaper is Fuji in ink, laid out on the golden ratio: the summit where the 0.382 lines
  cross, the sun or tonight's moon in the golden spiral's eye, a gentle 1 : 5 profile with a flat
  crater top, snow as deep as the season, mist at the foot, three pines.
- The lock screen shows that picture sharp and without its moon; the ensō and the clock stand
  where the moon was, the date and the password field below.
- `tests/live/run.sh`: Shoji driven in a second Hyprland hidden inside yours, checked on screen
  (meetings and Silent, Alt+Tab, idle → ink → lock, batches, the end-of-day card through AT-SPI,
  the eye rest, label heights). `--shots` takes the README screenshots and demo.gif on demo data.
- Fixed:
  - card text sat low: GTK 3 doubles a label's height on screen when letter-spacing is 1px or more;
  - the pointer stayed visible over the ink screen;
  - the screen size could come from a switched-off monitor;
  - `shoji apply` kept a stale lock picture.

## 0.6.0 — 2026-10-26

- 設 Preferences: every prefs.json choice in one popover, a line on what each does.
- 仕舞い the end of the day: a card at 17:00 on weekdays; Done for today keeps Silent on until 07:00.
- 通 notification batches (30 or 60 minutes) with one card of what came in, by app.
- 遠 rest your eyes: 20 seconds of looking far away every 20 minutes at the screen (optional).
- 俳句: a haiku of the season fills a free day in Koyomi.
- The ink screen flows into the lock screen (`shoji-ink lock`).
- `shoji slack`: the palette as Slack's four-colour custom theme.
- Icon buttons have names for screen readers.
- Fixed, found by running everything live in a nested Hyprland:
  - the ink screen never showed (GDK 4 was loaded before GTK 3);
  - Alt+Tab did not switch windows (focus was sent while the cards still held the keyboard);
  - Silent stayed on for good when hypr-widgets restarted during a meeting;
  - the Rin bell switch did nothing until the next login;
  - cards kept a taller first size.

## 0.5.0 — 2026-10-26

- 墨 Ink: an idle screen before the lock. The desktop sinks into the palette's ground and slow
  ink drops bloom on it, with the time and the day's 候; hypridle starts and stops it
  (`config/hypr/hypridle.conf`). Reduced motion keeps it still; prefs `"ink": false` turns it off.
- Koyomi and the popovers in Indonesian and Japanese: prefs `"lang"`, or the Language chip in the
  theme manager. Dates follow (26 Oktober, 10月26日).
- Sumi 墨 and Shiro 白: high-contrast palettes, every text pair at WCAG AAA.
- `shoji greeter`: the login screen (greetd + ReGreet) in your palette. It only writes files in
  your home and prints the root steps; switching display manager stays your call (docs/greeter.md).
- Tested in an Arch container: the PKGBUILD builds and installs, `shoji-setup` and uninstall run.
  Found there: uninstall left newer scripts behind (now every script in bin/ is covered).

## 0.4.1 — 2026-10-26

- CI: script syntax and the logic tests on every push (badge in the README).
- Koyomi by keyboard (click it first): arrows move the day, PgUp/PgDn the month, Home is today,
  Enter opens the day, Esc closes the panel.
- install.sh copies only files from bin/ (a bin/__pycache__ made it stop).

## 0.4.0 — 2026-10-26

- Clipboard history popover (Super+Shift+V): search, copy back, delete an entry, clear all.
- Alt+Tab as window cards with app icons, most recent first.
- Your own palette from the Theme manager: a ground and an accent, contrast checked live.
- 夕暮れ: the wallpaper's sky turns pink at dawn, gold before sunset, violet after.
- The bar shows a Bluetooth device's battery when it drops to 20 %.
- `shoji doctor --deps`: what is installed and what each missing piece adds.
- One-line install with a checksum (bootstrap.sh), and a PKGBUILD for Arch.

## 0.3.2 — 2026-10-26

- Reduced motion (Super+Shift+M) now stills everything: Hyprland, GTK, the bar's equalizer, swaync,
  and all of Shoji's glides, slides, fades and tweens; it survives a login and a config reload.
- hypr-widgets split into the shoji_widgets package (base, koyomi, popovers, overlays); every
  surface renders pixel-identical to the single file it was.
- Bluetooth popover (right-click the toggle in Koyomi): paired devices, connected first, with their
  battery; click to connect or disconnect.
- tests/: logic tests (seasons and contrast, meetings, the media player choice, zazen counts).

## 0.3.1 — 2026-10-26

- Quiet in meetings: Silent turns itself on while a calendar event runs or the screen is shared,
  and a reminder card with Join appears 10 minutes before an event.
- Multi-monitor and HiDPI: Koyomi and the swaync panel re-centre on the focused monitor (hypr-widgets
  updates swaync's margin when focus moves), the shortcuts sheet fits narrow or scaled screens.
- README: a 17-second demo GIF.

## 0.3.0 — 2026-10-26

- Koyomi shows the weather in one kanji beside the micro-season (霜始降 · 曇 31°), from Open-Meteo
  for the city of your time zone (prefs "weather" to change or turn off).
- Zazen: a 5-minute rest (休) after each session, the count of notifications that waited, and the
  day's sessions in Koyomi (座 ×N).
- Screenshots: a preview card in the bottom right with Open / Folder / Delete (hypr-shot is now
  part of Shoji).

## 0.2.2 — 2026-10-26

- One motion scale across Shoji: state 150 ms, content 180 ms, space 320 ms, all easing out
  (hypr-widgets, waybar, swaync, the documented Hyprland animations; no springs).
- Hover and selection fade; the launcher, shortcuts search and notification list glide on the
  mouse wheel; the Koyomi month slides and the agenda crossfades; the Media seek bar runs smoothly
  and play/pause no longer rebuilds the popover.
- Toasts fade through swaync itself; the CSS slide that replayed on the next toast is gone.
- swaync patch (docs/patches/swaync-0.11.0-shoji-motion.patch): wheel glide plus 180 ms group
  animations.

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
