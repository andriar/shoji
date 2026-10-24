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
    hl.exec_cmd("~/.local/bin/shoji wallpaper")  -- ink-mountain wallpaper via awww, hyprpaper or swaybg
end)

-- paper hairlines: the accent never draws a border
hl.config({ general = { border_size = 1,
    col = { active_border = c.edge_active, inactive_border = c.edge_dim } },
    decoration = { rounding = 18 } })

-- glass behind every shell surface
hl.layer_rule({ name = "shoji-blur",
    match = { namespace = "^(waybar|swaync-control-center|swaync-notification-window|launcher|logout_dialog|hypr-calendar|hypr-osd|hypr-pop)$" },
    blur = true, ignore_alpha = 0.2 })
hl.layer_rule({ name = "shoji-osd", match = { namespace = "^hypr-osd$" }, animation = "popin 90%" })
hl.layer_rule({ name = "shoji-pop", match = { namespace = "^hypr-pop$" }, animation = "popin 96%" })
hl.layer_rule({ name = "shoji-cal", match = { namespace = "^hypr-calendar$" }, animation = "slide top" })

-- keys
hl.bind("SUPER + SHIFT + T", hl.dsp.exec_cmd("~/.local/bin/hypr-pop theme"))
hl.bind("SUPER + Space",     hl.dsp.exec_cmd("~/.local/bin/hypr-pop launcher"))
hl.bind("XF86AudioRaiseVolume", hl.dsp.exec_cmd("~/.local/bin/hypr-osd up"),   { locked = true, repeating = true })
hl.bind("XF86AudioLowerVolume", hl.dsp.exec_cmd("~/.local/bin/hypr-osd down"), { locked = true, repeating = true })
hl.bind("XF86AudioMute",        hl.dsp.exec_cmd("~/.local/bin/hypr-osd mute"), { locked = true })
hl.bind("XF86AudioMicMute",     hl.dsp.exec_cmd("~/.local/bin/hypr-osd micmute"), { locked = true })
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
exec-once = ~/.local/bin/shoji wallpaper

general {
    border_size = 1
    col.active_border = $edge
    col.inactive_border = rgba(00000000)
}
decoration { rounding = 18 }

layerrule = blur, ^(waybar|swaync-control-center|swaync-notification-window|launcher|logout_dialog|hypr-calendar|hypr-osd|hypr-pop)$
layerrule = ignorealpha 0.2, ^(waybar|swaync-control-center|swaync-notification-window|launcher|logout_dialog|hypr-calendar|hypr-osd|hypr-pop)$

bind = SUPER SHIFT, T, exec, ~/.local/bin/hypr-pop theme
bind = SUPER, Space, exec, ~/.local/bin/hypr-pop launcher
bindel = , XF86AudioRaiseVolume, exec, ~/.local/bin/hypr-osd up
bindel = , XF86AudioLowerVolume, exec, ~/.local/bin/hypr-osd down
bindl  = , XF86AudioMute, exec, ~/.local/bin/hypr-osd mute
bindl  = , XF86AudioMicMute, exec, ~/.local/bin/hypr-osd micmute
```

## GNOME on the same machine

`~/.config/gtk-*` is shared with GNOME. If you also log into GNOME, add an autostart entry that runs
`~/.local/bin/shoji gnome` (OnlyShowIn=GNOME) so GNOME gets its own look back.
