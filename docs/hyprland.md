# Hyprland lines for Shoji

Shoji does not edit your Hyprland config. Add these yourself (Lua config, Hyprland 0.55+; a hyprlang
version follows).

## Lua (`hyprland.lua`)

```lua
local c = require("theme")   -- ~/.config/hypr/theme.lua, written by `shoji apply`

-- autostart
hl.on("hyprland.start", function()
    hl.exec_cmd("~/.local/bin/shoji apply")      -- re-applies the saved palette, quietly
    hl.exec_cmd("waybar")
    hl.exec_cmd("swaync")
    hl.exec_cmd("~/.local/bin/hypr-widgets")     -- ensō OSD, Koyomi calendar, popovers, theme manager
    hl.exec_cmd("~/.local/bin/hypr-term --service")  -- optional: keeps one ghostty running for instant windows
    hl.exec_cmd("~/.local/bin/shoji wallpaper")  -- ink-mountain wallpaper via awww, hyprpaper or swaybg
end)

-- paper hairlines: the accent never draws a border
hl.config({ general = { border_size = 1,
    col = { active_border = c.edge_active, inactive_border = c.edge_dim } },
    decoration = { rounding = 16 },
    -- tabbed windows: paper tabs, the active one sealed in the accent
    group = { col = { border_active = c.edge_active, border_inactive = c.edge_dim },
        groupbar = { font_family = "Zen Kaku Gothic New", font_size = 11, height = 20, gradients = true,
            gradient_rounding = 8, rounding = 8, indicator_height = 0, gaps_in = 4, gaps_out = 4,
            col = { active = c.accent, inactive = c.surface0 },
            text_color = c.on_accent, text_color_inactive = c.muted } } })

-- glass behind every shell surface
hl.layer_rule({ name = "shoji-blur",
    match = { namespace = "^(waybar|swaync-control-center|swaync-notification-window|launcher|logout_dialog|hypr-calendar|hypr-osd|hypr-pop|hypr-zazen|hypr-card|hypr-drawer)$" },
    blur = true, ignore_alpha = 0.2 })
hl.layer_rule({ name = "shoji-osd", match = { namespace = "^hypr-osd$" }, animation = "popin 90%" })
hl.layer_rule({ name = "shoji-zazen", match = { namespace = "^hypr-zazen$" }, animation = "fade" })
hl.layer_rule({ name = "shoji-card", match = { namespace = "^hypr-card$" }, animation = "slide right" })
hl.layer_rule({ name = "shoji-drawer", match = { namespace = "^hypr-drawer$" }, animation = "slide right" })
hl.layer_rule({ name = "shoji-pop", match = { namespace = "^hypr-pop$" }, animation = "popin 96%" })
-- Koyomi's two halves fade together: swaync's layer covers the screen (it catches outside clicks),
-- so a slide would move it ~1400 px against the calendar's ~480 px and they would arrive apart
hl.layer_rule({ name = "shoji-cal", match = { namespace = "^hypr-calendar$" }, animation = "fade" })
hl.layer_rule({ name = "shoji-panel", match = { namespace = "^swaync-control-center$" }, animation = "fade" })
-- Shoji's motion scale (speed 1 = 100 ms), the same steps hypr-widgets, waybar and swaync use:
-- state 150 ms, content and shell surfaces 180 ms, space (windows, workspaces) 320 ms; all ease
-- out, no springs, nothing overshoots
hl.curve("easeOutQuint", { type = "bezier", points = { {0.23, 1}, {0.32, 1} } })
hl.animation({ leaf = "border",           enabled = true, speed = 1.5, bezier = "easeOutQuint" })
hl.animation({ leaf = "windows",          enabled = true, speed = 3.2, bezier = "easeOutQuint" })
hl.animation({ leaf = "windowsIn",        enabled = true, speed = 3.2, bezier = "easeOutQuint", style = "popin 90%" })
hl.animation({ leaf = "windowsOut",       enabled = true, speed = 1.5, bezier = "linear",       style = "popin 90%" })
hl.animation({ leaf = "windowsMove",      enabled = true, speed = 3.2, bezier = "easeOutQuint" })
hl.animation({ leaf = "layers",           enabled = true, speed = 1.8, bezier = "easeOutQuint" })
hl.animation({ leaf = "layersIn",         enabled = true, speed = 1.8, bezier = "easeOutQuint", style = "fade" })
hl.animation({ leaf = "layersOut",        enabled = true, speed = 1.5, bezier = "linear",       style = "fade" })
hl.animation({ leaf = "fade",             enabled = true, speed = 1.8, bezier = "easeOutQuint" })
hl.animation({ leaf = "workspaces",       enabled = true, speed = 3.2, bezier = "easeOutQuint", style = "slidefade 15%" })
hl.animation({ leaf = "specialWorkspace", enabled = true, speed = 3.2, bezier = "easeOutQuint", style = "slidefadevert 25%" })
-- toasts slide in through swaync CSS; Hyprland's layer animation stretches the stack when it resizes
hl.layer_rule({ name = "shoji-toasts", match = { namespace = "^swaync-notification-window$" }, no_anim = true })

-- keys
hl.bind("SUPER + SHIFT + T", hl.dsp.exec_cmd("~/.local/bin/hypr-pop theme"))
hl.bind("SUPER + Space",     hl.dsp.exec_cmd("~/.local/bin/hypr-pop launcher"))
-- ghostty opens in ~70 ms instead of ~1 s: a D-Bus action on the running instance
hl.bind("SUPER + Return",    hl.dsp.exec_cmd("~/.local/bin/hypr-term"), { description = "Apps: Open terminal" })
-- every bind with a description ("Group: what it does") shows up here, as keycaps
hl.bind("SUPER + slash",     hl.dsp.exec_cmd("~/.local/bin/hypr-pop keys"), { description = "Help: All shortcuts" })
-- one key per app you live in: focus it if open (again = next window), start it if not.
-- The launcher shows the key next to the app when the command is `gtk-launch <desktop id>`.
hl.bind("SUPER + K", hl.dsp.exec_cmd("~/.local/bin/hypr-focus-or-launch slack gtk-launch com.slack.Slack"),
        { description = "Apps: Slack" })
hl.bind("SUPER + B", hl.dsp.exec_cmd("~/.local/bin/hypr-focus-or-launch '^google-chrome$' gtk-launch google-chrome"),
        { description = "Apps: Browser" })
-- tabbed windows: Super+T groups the window, Super+[ / ] walk the tabs
hl.bind("SUPER + T",            hl.dsp.group.toggle(), { description = "Windows: Tab windows (group) on / off" })
hl.bind("SUPER + bracketright", hl.dsp.group.next(),   { description = "Windows: Next tab" })
hl.bind("SUPER + bracketleft",  hl.dsp.group.prev(),   { description = "Windows: Previous tab" })
-- 坐禅 focus session: silent, no bar, other windows dimmed, an ensō counts down (again = stop)
hl.bind("SUPER + Z", hl.dsp.exec_cmd("~/.local/bin/shoji-zazen toggle"), { description = "System: Zazen (25 min focus)" })
hl.bind("XF86AudioRaiseVolume", hl.dsp.exec_cmd("~/.local/bin/hypr-osd up"),   { locked = true, repeating = true })
hl.bind("XF86AudioLowerVolume", hl.dsp.exec_cmd("~/.local/bin/hypr-osd down"), { locked = true, repeating = true })
hl.bind("XF86AudioMute",        hl.dsp.exec_cmd("~/.local/bin/hypr-osd mute"), { locked = true })
hl.bind("XF86AudioMicMute",     hl.dsp.exec_cmd("~/.local/bin/hypr-osd micmute"), { locked = true })
-- laptops (needs brightnessctl): the same ensō shows 明 · BRIGHT
hl.bind("XF86MonBrightnessUp",   hl.dsp.exec_cmd("~/.local/bin/hypr-osd bright-up"),   { locked = true, repeating = true })
hl.bind("XF86MonBrightnessDown", hl.dsp.exec_cmd("~/.local/bin/hypr-osd bright-down"), { locked = true, repeating = true })
```

Check the exact `hl.config` / `hl.bind` shape against `/usr/share/hypr/hyprland.lua` for your version,
then run `Hyprland --verify-config`.

## hyprlang (`hyprland.conf`)

```ini
source = ~/.config/hypr/theme.conf

exec-once = ~/.local/bin/shoji apply
exec-once = waybar
exec-once = swaync
exec-once = ~/.local/bin/hypr-widgets
exec-once = ~/.local/bin/hypr-term --service
exec-once = ~/.local/bin/shoji wallpaper

general {
    border_size = 1
    col.active_border = $edge
    col.inactive_border = rgba(00000000)
}
decoration { rounding = 16 }

layerrule = blur, ^(waybar|swaync-control-center|swaync-notification-window|launcher|logout_dialog|hypr-calendar|hypr-osd|hypr-pop|hypr-zazen|hypr-card)$
layerrule = ignorealpha 0.2, ^(waybar|swaync-control-center|swaync-notification-window|launcher|logout_dialog|hypr-calendar|hypr-osd|hypr-pop|hypr-zazen|hypr-card)$
layerrule = noanim, ^(swaync-notification-window)$

bind = SUPER SHIFT, T, exec, ~/.local/bin/hypr-pop theme
bind = SUPER, Space, exec, ~/.local/bin/hypr-pop launcher
bindd = SUPER, Return, Apps: Open terminal, exec, ~/.local/bin/hypr-term
bindd = SUPER, slash, Help: All shortcuts, exec, ~/.local/bin/hypr-pop keys
bindd = SUPER, K, Apps: Slack, exec, ~/.local/bin/hypr-focus-or-launch slack gtk-launch com.slack.Slack
bindd = SUPER, B, Apps: Browser, exec, ~/.local/bin/hypr-focus-or-launch '^google-chrome$' gtk-launch google-chrome
bindel = , XF86AudioRaiseVolume, exec, ~/.local/bin/hypr-osd up
bindel = , XF86AudioLowerVolume, exec, ~/.local/bin/hypr-osd down
bindl  = , XF86AudioMute, exec, ~/.local/bin/hypr-osd mute
bindl  = , XF86AudioMicMute, exec, ~/.local/bin/hypr-osd micmute
bindel = , XF86MonBrightnessUp, exec, ~/.local/bin/hypr-osd bright-up
bindel = , XF86MonBrightnessDown, exec, ~/.local/bin/hypr-osd bright-down
```

## Idle: the ink screen, then the lock

`config/hypr/hypridle.conf` is a whole hypridle setup: at 8 minutes `shoji-ink` lets the desktop
sink into the palette's ground while drops of ink bloom on it (with the time and the 候 in a
corner); at 10 the lock; at 15 the screen goes off. Any input before the lock takes the ink away.
Copy it to `~/.config/hypr/hypridle.conf` (or add its first listener to yours, and put
`~/.local/bin/shoji-ink stop;` before your lock command), then restart hypridle.
`shoji-ink preview` shows it now (a click or a key closes it). With reduced motion the drops
stand still. It uses under a tenth of one CPU core while it shows (8 frames a second).

## GNOME on the same machine

`~/.config/gtk-*` is shared with GNOME. If you also log into GNOME, add an autostart entry that runs
`~/.local/bin/shoji gnome` (OnlyShowIn=GNOME) so GNOME gets its own look back.

## The widgets drawer

```lua
-- Super+grave, and a four-finger swipe from the right on a touchpad
hl.bind("SUPER + grave", hl.dsp.exec_cmd("~/.local/bin/hypr-pop drawer"))
hl.gesture({ fingers = 4, direction = "left", action = function() hl.exec_cmd("~/.local/bin/hypr-pop drawer") end })
```

Resting the pointer on the right screen edge opens it too (`"drawer_edge": false` in
`~/.config/shoji/prefs.json` turns that off).
