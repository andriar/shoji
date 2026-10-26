"""Constants, the one motion scale, palette and prefs helpers, GTK CSS, layer windows, Glide and
the ensō drawing that every surface shares."""
import calendar as cal_mod
import datetime
import importlib.machinery
import json
import math
import os
import shutil
import subprocess
import sys
import threading
import time
import urllib.parse
import urllib.request
from pathlib import Path

import cairo
import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("GtkLayerShell", "0.1")
gi.require_version("PangoCairo", "1.0")
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import Gdk, GdkPixbuf, GLib, Gio, Gtk, GtkLayerShell as Layer, Pango, PangoCairo  # noqa: E402

try:  # events and tasks for Koyomi come from Evolution Data Server (package gir1.2-ecal-2.0); optional
    gi.require_version("ECal", "2.0")
    gi.require_version("EDataServer", "1.2")
    gi.require_version("ICalGLib", "3.0")
    from gi.repository import ECal, EDataServer, ICalGLib  # noqa: E402
except (ValueError, ImportError):
    ECal = None

HOME = Path.home()
RUN = Path(os.environ.get("XDG_RUNTIME_DIR", "/tmp"))
FIFO = RUN / "hypr-osd.fifo"
PIDFILE = RUN / "hypr-widgets.pid"
COLORS = HOME / ".config/waybar/colors.css"
THEME = HOME / ".config/shoji/current.json"
PREFS = HOME / ".config/shoji/prefs.json"
SHOJI = str(HOME / ".local/bin/shoji")
LUCIDE = json.loads((HOME / ".local/share/fonts/Shoji/lucide-info.json").read_text())
CC_WIDTH = 420      # swaync control-center-width
GAP = 8
OSD_MS = 1400
# one motion scale for Shoji: state changes 150 ms, content that moves 180 ms (ease-out)
STATE_MS, CONTENT_MS = 150, 180
OSD_TWEEN_MS = CONTENT_MS
# reduced motion (hypr-motion, Super+Shift+M; prefs "reduced_motion"): no glides, slides, fades or
# tweens; states and positions change at once. Updated live through the FIFO ("motion<TAB>on|off").
MOTION = {"reduced": False}


def reduced():
    return MOTION["reduced"]
WEEK_K = "日月火水木金土"  # Sunday first, like the calendar grid
AGENDA_ROWS = 4     # agenda lines under the grid; the card keeps one height (gen_swaync CAL_HEIGHT)

# 七十二候 lives in shoji (stdlib only), so `shoji greet` can use it from a shell without GTK
_shoji = importlib.machinery.SourceFileLoader("shoji_ko", SHOJI).load_module()
KO, micro_season = _shoji.KO, _shoji.micro_season


def icon(name):
    return chr(int(LUCIDE[name]["encodedCode"].lstrip("\\"), 16))


def sh(*cmd):
    return subprocess.run(cmd, capture_output=True, text=True).stdout.strip()


def spawn(*cmd):
    subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)


def theme():
    try:
        return json.loads(THEME.read_text())
    except (OSError, ValueError):
        return {"tokens": {"base": "#111827", "text": "#e6e9f0", "muted": "#97a0b5", "accent": "#d9b05a",
                           "on_accent": "#17161b"}, "dark": True}


def prefs():
    try:
        return json.loads(PREFS.read_text())
    except (OSError, ValueError):
        return {}


def save_prefs(**kw):
    p = prefs()
    p.update(kw)
    PREFS.write_text(json.dumps(p, indent=1) + "\n")


def rgba(h, a=1.0):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)) + (a,)


CSS = b"""
* { font-family: "Zen Kaku Gothic New", "lucide", "JetBrainsMono Nerd Font"; font-size: 12px; }
.panel {
  background: @elev2;
  border: 1px solid @edge;
  border-radius: 16px;
  padding: 14px;
  color: @text;
}
/* every state change eases (hover, selection, a toggle turning on): STATE_MS */
button, .row, .app-row, .key-row, .sheet-row, .chip, .toggle, .day, .agenda-row, .nav, .card, .link {
  transition: background-color 150ms ease-out, color 150ms ease-out, box-shadow 150ms ease-out,
              border-color 150ms ease-out;
}
.muted { color: @muted; }
.label-small { color: @muted; font-size: 10.5px; letter-spacing: 1px; }
.mono { font-family: "JetBrainsMono Nerd Font"; font-size: 11px; color: @muted; }
.display { font-family: "Kaisei Opti"; font-weight: 700; font-size: 22px; color: @text; }
.title { font-size: 13px; font-weight: 700; }
.sep { background: @edge; min-height: 1px; }

/* koyomi */
.wk { font-family: "Kaisei Opti"; font-size: 10.5px; color: @muted; }
.day { min-width: 30px; min-height: 22px; border-radius: 4px; font-size: 12px; color: @text; }
.day.other { color: alpha(@text, 0.32); }
.day.past { color: alpha(@text, 0.6); }
.season { font-family: "Kaisei Opti"; font-size: 12px; color: @muted; letter-spacing: 1px; }
.day.today { background: @accent; color: @on_accent; font-weight: 700; }
button.day { padding: 0; border: none; box-shadow: none; background-image: none; }
.agenda button.day { min-height: 25px; }  /* room for the event dot */
.agenda .day .num { margin-bottom: 4px; }
button.day:not(.today) { background: transparent; }
button.day:not(.today):hover { background: @hover; }
.day.sel { box-shadow: inset 0 0 0 1px @accent; }
.day .mark { min-width: 4px; min-height: 4px; border-radius: 2px; background: @accent; margin-bottom: 1px; }
.day.today .mark { background: @on_accent; }
.day.other .mark { opacity: 0.4; }
.agenda-row { background: transparent; background-image: none; border: none; box-shadow: none;
              border-radius: 8px; padding: 0 8px; min-height: 24px; color: @text; }
.agenda-row:hover { background: @hover; }
/* quick toggles at the foot of Koyomi: accent = on */
.toggle { background: @group; background-image: none; border: none; box-shadow: none; border-radius: 8px;
          min-height: 36px; padding: 0; color: @text; }
.toggle label { font-family: "lucide"; font-size: 15px; }
.toggle:hover { background: @hover; }
.toggle.on { background: @accent; color: @on_accent; }
.toggle.off-alert { color: @alert; }
/* Koyomi + the swaync panel read as one container: square inner corners, one hairline between */
.panel.koyomi { border-top-right-radius: 0; border-bottom-right-radius: 0; border-right-width: 0; }
.agenda-row .when { font-family: "JetBrainsMono Nerd Font"; font-size: 11px; color: @muted; }
.agenda-row .tick { font-family: "lucide"; font-size: 11px; }
.agenda-row.more { color: @muted; }
.nav { background: transparent; border: none; box-shadow: none; color: @muted; min-width: 24px; min-height: 22px;
       padding: 0; border-radius: 4px; font-family: "lucide"; }
.nav:hover { background: @hover; color: @text; }

/* rows inside popovers */
.row { background: transparent; border: none; box-shadow: none; border-radius: 8px; padding: 0 10px;
       min-height: 34px; color: @muted; }
.row:hover { background: @hover; color: @text; }
.row.active { background: alpha(@text, 0.10); color: @text; }
.row .icon { font-family: "lucide"; font-size: 14px; }
.chip { background: @group; border: none; box-shadow: none; border-radius: 8px; padding: 2px 10px;
        color: @text; font-size: 10.5px; min-height: 22px; }
.chip:hover { background: @hover; }
.chip.on { background: @accent; color: @on_accent; }
.link { background: transparent; border: none; box-shadow: none; color: @muted; padding: 2px 10px;
        border-radius: 8px; min-height: 26px; }
.link:hover { background: @hover; color: @text; }
scale trough { min-height: 4px; border-radius: 2px; background: @track; border: none; }
scale highlight { min-height: 4px; border-radius: 2px; background: @accent; border: none; }
scale slider { min-width: 14px; min-height: 14px; margin: -5px; border-radius: 7px; background: @text;
               border: none; box-shadow: none; }

/* theme manager */
.card { background: @group; border: 2px solid transparent; border-radius: 12px; padding: 8px;
        box-shadow: none; color: @text; }
.card:hover { background: @hover; }
.card.active { border-color: @accent; }
.card .name { font-family: "Kaisei Opti"; font-weight: 700; font-size: 13px; }
/* media: glass. A thinner pane than the other panels, so the blurred desktop and the cover's
   colour wash show through; a hairline and a top highlight give the glass an edge */
.panel.media { background-color: alpha(@base, 0.42); border: 1px solid alpha(@text, 0.16);
               box-shadow: inset 0 1px alpha(@text, 0.10); }
.media-title { font-size: 15px; font-weight: 700; color: @text; }
.media-btn { min-width: 40px; min-height: 40px; padding: 0; }
.media-btn label { font-family: "lucide"; font-size: 18px; }
.play { background: @text; color: @base; border: none; box-shadow: none; background-image: none;
        border-radius: 20px; min-width: 44px; min-height: 44px; }
.play label { font-size: 20px; }
.play:hover { background: @accent; color: @on_accent; }
.seal { background: @accent; color: @on_accent; border-radius: 4px; min-width: 28px; min-height: 28px;
        font-family: "Kaisei Opti"; font-weight: 700; font-size: 15px; }
switch { background: alpha(@text, 0.18); border: none; border-radius: 10px; min-height: 18px; }
switch:checked { background: @accent; }
switch slider { background: @text; border: none; border-radius: 8px; min-width: 14px; min-height: 14px; }
switch:checked slider { background: @on_accent; }

/* launcher */
.searchbar { background: @group; border-radius: 12px; padding: 2px 10px; }
.searchbar .icon { font-family: "lucide"; font-size: 15px; color: @muted; }
entry.search { background: transparent; border: none; box-shadow: none; color: @text; font-size: 15px;
               min-height: 38px; caret-color: @accent; }
entry.search selection { background: alpha(@accent, 0.35); }
.kbd { font-family: "JetBrainsMono Nerd Font"; font-size: 10.5px; color: @muted; border: 1px solid @edge;
       border-radius: 4px; padding: 1px 5px; }
list { background: transparent; }
.app-row { background: transparent; border-radius: 8px; padding: 6px 10px; min-height: 36px; }
.app-row:hover { background: @hover; }
.app-row:selected { background: alpha(@text, 0.10); }
.app-row .app-name { font-size: 13px; color: @text; }
.app-row .desc { font-size: 10.5px; color: @muted; }

/* shortcuts sheet */
.key-row { background: transparent; border-radius: 8px; padding: 5px 10px; min-height: 30px; }
.key-row:hover { background: @hover; }
.key-row:selected { background: alpha(@text, 0.10); }
.key-row .desc { font-size: 13px; color: @text; }
.key-row .group { font-size: 10.5px; color: @muted; }
.cap { font-family: "JetBrainsMono Nerd Font"; font-size: 11px; color: @text; background: @group;
       border: 1px solid @edge; border-bottom-width: 2px; border-radius: 4px; padding: 1px 7px; min-width: 12px; }
.key-row:selected .cap { border-color: alpha(@accent, 0.6); }
.key-head { font-size: 10.5px; letter-spacing: 1px; color: @muted; padding: 18px 10px 4px; }
.sheet-row { background: transparent; border: none; box-shadow: none; border-radius: 8px; padding: 3px 8px;
             min-height: 26px; }
.sheet-row:hover { background: @hover; }
.sheet-row:disabled { opacity: 1; }
.sheet-row .desc { font-size: 12px; color: @text; }
.sheet-row .cap { font-size: 10.5px; padding: 1px 5px; border: none; }
"""

provider = Gtk.CssProvider()


def load_css():
    try:
        colors = COLORS.read_bytes()
    except OSError:
        colors = b""
    still = b"* { transition: none; animation: none; }\n" if reduced() else b""
    try:
        provider.load_from_data(colors + CSS + still)
    except GLib.Error as e:
        print("css:", e, file=sys.stderr)


def layer_window(namespace, layer, keyboard=False):
    win = Gtk.Window()
    win.set_app_paintable(True)
    visual = win.get_screen().get_rgba_visual()
    if visual:
        win.set_visual(visual)
    Layer.init_for_window(win)
    Layer.set_namespace(win, namespace)
    Layer.set_layer(win, layer)
    Layer.set_keyboard_mode(win, Layer.KeyboardMode.ON_DEMAND if keyboard else Layer.KeyboardMode.NONE)
    win.connect("draw", clear_bg)
    return win


def clear_bg(_w, cr):
    cr.set_operator(cairo.OPERATOR_SOURCE)
    cr.set_source_rgba(0, 0, 0, 0)
    cr.paint()
    cr.set_operator(cairo.OPERATOR_OVER)
    return False


class Glide:
    """Eases a scrolled window's vertical position, like Shoji's swaync patch: a wheel notch or a
    keyboard step moves a target, the view follows in 180 ms (ease-out cubic), and quick notches add
    up instead of restarting. Touchpads keep GTK's own scrolling, which is already smooth."""
    STEP, MS = 96, CONTENT_MS

    def __init__(self, scrolled):
        self.sw, self.adj = scrolled, scrolled.get_vadjustment()
        self.tick, self.target, self.start, self.origin = 0, 0.0, 0, 0.0
        scrolled.connect("scroll-event", self.on_scroll)

    def on_scroll(self, _w, ev):
        dev = ev.get_source_device()
        if dev is not None and dev.get_source() == Gdk.InputSource.TOUCHPAD:
            return False
        if ev.direction == Gdk.ScrollDirection.SMOOTH:
            dy = ev.get_scroll_deltas()[2]
        else:
            dy = {Gdk.ScrollDirection.UP: -1, Gdk.ScrollDirection.DOWN: 1}.get(ev.direction, 0)
        if not dy:
            return False
        self.to((self.target if self.tick else self.adj.get_value()) + dy * self.STEP)
        return True

    def to(self, value):
        adj = self.adj
        self.target = max(adj.get_lower(), min(adj.get_upper() - adj.get_page_size(), value))
        if reduced():
            self.jump(self.target)
            return
        self.origin = adj.get_value()
        clock = self.sw.get_frame_clock()
        if clock is None:
            adj.set_value(self.target)
            return
        self.start = clock.get_frame_time()
        if not self.tick:
            self.tick = self.sw.add_tick_callback(self.frame)

    def jump(self, value):
        if self.tick:
            self.sw.remove_tick_callback(self.tick)
            self.tick = 0
        self.adj.set_value(value)

    def frame(self, _w, clock):
        t = (clock.get_frame_time() - self.start) / (self.MS * 1000)
        if t >= 1:
            self.adj.set_value(self.target)
            self.tick = 0
            return False
        self.adj.set_value(self.origin + (self.target - self.origin) * (1 - (1 - t) ** 3))
        return True


def click_through(win):
    win.input_shape_combine_region(cairo.Region())


def label(text, *classes, xalign=0.0):
    w = Gtk.Label(label=text, xalign=xalign)
    for c in classes:
        w.get_style_context().add_class(c)
    return w


def sep():
    s = Gtk.Box()
    s.get_style_context().add_class("sep")
    return s


def enso(cr, cx, cy, r, frac, color, width, track=None):
    start = -math.pi / 2 - math.radians(6)
    sweep = 2 * math.pi * 0.94
    cr.set_line_cap(cairo.LINE_CAP_ROUND)
    if track:
        cr.set_source_rgba(*track)
        cr.set_line_width(width * 0.7)
        cr.arc(cx, cy, r, start, start + sweep)
        cr.stroke()
    if frac > 0:
        cr.set_source_rgba(*color)
        cr.set_line_width(width)
        cr.arc(cx, cy, r, start, start + sweep * frac)
        cr.stroke()
        if frac > 0.08:
            cr.set_source_rgba(color[0], color[1], color[2], 0.5)
            cr.set_line_width(max(1.2, width * 0.24))
            cr.arc(cx, cy, r - width * 0.72, start + 0.07, start + sweep * frac * 0.78)
            cr.stroke()
