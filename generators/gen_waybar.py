#!/usr/bin/env python3
"""Shoji bar: writes ~/.config/waybar/{config.jsonc,style.css}. Run after editing; waybar reloads on SIGUSR2.

One paper strip, three zones:
  left    search · workspaces 一二三四 (seal = current; shoji-ws, clickable) · window title
  center  time + weekday kanji · unread dot          (click: Koyomi panel = swaync + calendar)
  right   load · on-only indicators · network · mic · ensō volume · battery · tray
Icons are Lucide (font family "lucide"); private-use glyphs are written with chr(), never typed.
"""
import json
from pathlib import Path

W = Path.home() / ".config/waybar"
ICONS = json.loads((Path.home() / ".local/share/fonts/Shoji/lucide-info.json").read_text())


def L(name):
    return chr(int(ICONS[name]["encodedCode"].lstrip("\\"), 16))


BIN = "~/.local/bin"
WS = [f"custom/ws#w{n}" for n in range(1, 11)]
cfg = {
    "layer": "top", "position": "top", "height": 30,
    "margin-top": 6, "margin-left": 10, "margin-right": 10, "spacing": 0,
    "modules-left": ["custom/launcher", "custom/ws-watch", *WS, "hyprland/window"],
    "modules-center": ["custom/clock", "custom/notification"],
    "modules-right": ["custom/record", "custom/system", "custom/keepawake", "custom/nightlight",
                      "network", "pulseaudio#mic", "image#vol", "pulseaudio", "image#bat", "battery", "group/tray"],

    "custom/launcher": {"format": L("search"), "tooltip-format": "Search apps (Super+Space)",
                        "on-click": f"{BIN}/hypr-pop launcher"},
    # hyprland/workspaces clicks send `dispatch workspace N`, which Lua-mode Hyprland rejects:
    # shoji-ws watches Hyprland and these buttons dispatch the Lua way
    "custom/ws-watch": {"exec": f"{BIN}/shoji-ws watch", "tooltip": False},
    **{m: {"exec": f"cat $XDG_RUNTIME_DIR/shoji-ws/{n} 2>/dev/null", "return-type": "json",
           "interval": "once", "signal": 7,
           "on-click": f"hyprctl dispatch 'hl.dsp.focus({{ workspace = {n} }})'",
           "on-scroll-up": "hyprctl dispatch 'hl.dsp.focus({ workspace = \"e-1\" })'",
           "on-scroll-down": "hyprctl dispatch 'hl.dsp.focus({ workspace = \"e+1\" })'"}
       for n, m in enumerate(WS, start=1)},
    "hyprland/window": {"format": "{title}", "max-length": 56, "separate-outputs": True,
                        "rewrite": {"(.*) — Mozilla Firefox": "$1", "(.*) - Google Chrome": "$1"}},

    "custom/clock": {"exec": f"{BIN}/shoji-clock", "return-type": "json", "interval": 10,
                     "on-click": "swaync-client -t -sw"},
    "custom/notification": {
        "format": "{icon}", "return-type": "json", "exec": "swaync-client -swb", "escape": True, "tooltip": False,
        "format-icons": {"notification": "■", "dnd-notification": L("bell-off"), "inhibited-notification": "■",
                         "dnd-inhibited-notification": L("bell-off"), "none": "", "inhibited-none": "",
                         "dnd-none": L("bell-off"), "dnd-inhibited-none": L("bell-off")},
        "on-click": "swaync-client -t -sw", "on-click-right": "swaync-client -d -sw",
    },

    "custom/record": {"exec": f"{BIN}/hypr-record status", "return-type": "json",
                      "interval": "once", "signal": 9, "on-click": f"{BIN}/hypr-record toggle"},
    "custom/system": {"exec": f"{BIN}/hypr-sysload", "return-type": "json", "interval": 5,
                      "on-click": f"{BIN}/hypr-toggle-app 'dev\\.hypr\\.btop' ghostty --class=dev.hypr.btop --confirm-close-surface=false -e btop"},
    # on/off switches live in the Koyomi panel; the bar only shows the ones that are on
    "custom/keepawake": {"exec": f"{BIN}/keep-awake status", "return-type": "json",
                         "interval": "once", "signal": 12, "on-click": f"{BIN}/keep-awake toggle"},
    "custom/nightlight": {"exec": f"{BIN}/hypr-nightlight status", "return-type": "json",
                          "interval": "once", "signal": 8, "on-click": f"{BIN}/hypr-nightlight toggle"},

    "network": {
        "format-ethernet": L("ethernet-port"), "format-wifi": L("wifi"), "format-disconnected": L("wifi-off"),
        "tooltip-format": "{ifname} · {ipaddr}\nClick: network", "tooltip-format-disconnected": "Offline\nClick: network",
        "on-click": f"{BIN}/hypr-pop network",
    },
    "pulseaudio#mic": {
        "format": "{format_source}", "format-source": L("mic"), "format-source-muted": L("mic-off"),
        "tooltip-format": "Mic {source_volume}% · {source_desc}\nClick: mute · Right: sound devices",
        "on-click": f"{BIN}/hypr-osd micmute", "on-click-right": f"{BIN}/hypr-pop audio",
        "on-scroll-up": "wpctl set-volume -l 1 @DEFAULT_AUDIO_SOURCE@ 5%+",
        "on-scroll-down": "wpctl set-volume @DEFAULT_AUDIO_SOURCE@ 5%-",
    },
    # volume = ensō ring image + number; both open the Sound popover, scroll = the knob
    "image#vol": {"exec": f"{BIN}/shoji-level vol", "interval": 2, "signal": 10, "size": 16,
                  "on-click": f"{BIN}/hypr-pop audio", "on-click-middle": f"{BIN}/hypr-osd mute",
                  "on-scroll-up": f"{BIN}/hypr-osd up", "on-scroll-down": f"{BIN}/hypr-osd down",
                  "tooltip": False},
    "pulseaudio": {
        "format": "{volume}", "format-muted": "off", "format-bluetooth": "{volume}",
        "tooltip-format": "{desc}\nClick: sound devices · Middle: mute · Scroll: volume",
        "on-click": f"{BIN}/hypr-pop audio", "on-click-middle": f"{BIN}/hypr-osd mute",
        "on-scroll-up": f"{BIN}/hypr-osd up", "on-scroll-down": f"{BIN}/hypr-osd down",
    },
    "image#bat": {"exec": f"{BIN}/shoji-level bat", "interval": 30, "size": 16, "tooltip": False,
                  "on-click": f"{BIN}/hypr-pop battery"},
    "battery": {
        "states": {"low": 20, "critical": 10}, "format": "{capacity}%",
        "tooltip-format": "{timeTo}\nClick: battery and power mode",
        "on-click": f"{BIN}/hypr-pop battery",
    },
    # app tray icons stay tucked away: hover the dots to slide them out
    "group/tray": {"orientation": "inherit", "modules": ["custom/traydots", "tray"],
                   "drawer": {"transition-duration": 220, "transition-left-to-right": False,
                              "children-class": "tray-item"}},
    "custom/traydots": {"format": L("ellipsis"), "tooltip-format": "App icons — hover to show"},
    "tray": {"spacing": 8, "icon-size": 16},
}
(W / "config.jsonc").write_text("// Generated by ~/.config/shoji/gen_waybar.py — edit that, not this file\n"
                                + json.dumps(cfg, indent=2, ensure_ascii=False) + "\n")

css = r'''/* Generated by ~/.config/shoji/gen_waybar.py. Colors from colors.css (shoji).
   Rules: one paper strip; accent only for "you are here" (workspace seal) and unread;
   everything else is text or muted text. */
@import url("colors.css");

* {
  font-family: "Zen Kaku Gothic New", "lucide", "JetBrainsMono Nerd Font";
  font-size: 12px;
  min-height: 0;
  border: none;
  border-radius: 0;
}

window#waybar { background: transparent; color: @text; }
window#waybar > box {
  background: @elev1;
  border: 1px solid @edge;
  border-radius: 9px;
  padding: 0 4px;
}

tooltip { background: @elev3; border: 1px solid @edge; border-radius: 10px; }
tooltip label { color: @text; padding: 4px 8px; font-size: 12px; }

/* every clickable thing */
#custom-launcher, #custom-ws, #window, #custom-clock, #custom-notification, #custom-record,
#custom-system, #custom-keepawake, #custom-nightlight, #network, #pulseaudio, #image, #battery, #tray {
  padding: 0 7px;
  margin: 3px 1px;
  border-radius: 5px;
  background: transparent;
  color: @text;
  transition: background 150ms ease-out, color 150ms ease-out;
}
#custom-launcher:hover, #custom-ws:hover, #custom-clock:hover, #custom-notification:hover,
#custom-system:hover, #network:hover, #pulseaudio:hover, #image:hover {
  background: @hover;
}

#custom-launcher { font-size: 13px; padding: 0 8px; }

/* workspaces: seal = current, bright = has windows, dim = empty */
#custom-ws.w1 { margin-left: 3px; }
#custom-ws.w10 { margin-right: 3px; }
#custom-ws {
  font-family: "Kaisei Opti";
  font-size: 13px;
  font-weight: 500;
  min-width: 14px;
  padding: 0 5px;
  color: @muted;
  background-image: none;
  box-shadow: none;
}
#custom-ws.occupied { color: @text; }
#custom-ws.active { background: @accent; color: @on_accent; font-weight: 700; }
#custom-ws.active:hover { background: @accent; }
#custom-ws.urgent { background: alpha(@alert, 0.30); color: @text; }

#window { color: @muted; padding-left: 8px; }
window#waybar.empty #window { background: transparent; }

#custom-clock { padding: 0 10px; }
#custom-notification { padding: 0 4px; margin-left: 0; font-size: 9px; color: @accent; }
#custom-notification.dnd-notification, #custom-notification.dnd-none,
#custom-notification.dnd-inhibited-notification, #custom-notification.dnd-inhibited-none {
  font-size: 12px; color: @muted;
}

#custom-system { font-family: "JetBrainsMono Nerd Font"; font-size: 11px; color: @muted; }
#custom-system.warning { color: @warn; }
#custom-system.critical { color: @alert; }
#custom-record.recording { color: @alert; }
#custom-keepawake.on, #custom-nightlight.on { color: @accent; }

#network { font-size: 13px; }
#network.disconnected { color: @alert; }
#pulseaudio { font-family: "JetBrainsMono Nerd Font"; font-size: 11px; padding-left: 2px; padding-right: 8px; }
#pulseaudio.muted { color: @muted; }
#image { padding: 0 2px 0 6px; margin-right: 0; }
#battery { font-family: "JetBrainsMono Nerd Font"; font-size: 11px; padding-left: 2px; }
#battery.low:not(.charging) { color: @alert; }
#battery.critical:not(.charging) { background: alpha(@alert, 0.22); color: @alert; }
#tray { padding: 0 4px; }
#custom-traydots { color: @muted; padding: 0 6px; font-size: 13px; }
/* app icons arrive in every color: keep them quiet until hovered (GTK3 has no grayscale filter) */
#tray > widget image { opacity: 0.72; }
#tray > widget:hover image, #tray > .needs-attention image { opacity: 1; }
'''
# the mic module shares #pulseaudio; give it the icon size back
css += "#pulseaudio.mic { font-family: \"lucide\"; font-size: 13px; padding: 0 7px; }\n"
(W / "style.css").write_text(css)
print("ok")
