"""島 Shima, the island: one pill at the top centre that holds the clock and grows around it with
whatever is going on (prefs "island": true), the way the Dynamic Island grows around the camera.
It replaces the ensō OSD, the zazen ensō and the bar's clock and now-playing; lists stay in their
popovers and a click on the island opens them.

  pill        the clock, always: the island's fixed core, as the camera is on an iPhone
  wings       one activity joins the pill, on both sides of the clock: what it is on the left,
              its live value on the right (ensō | 19m, ⏲ | 9:58, the cover | the music's bars)
  droplets    a second activity and on sit apart beside it, as on an iPhone, then the first source
              with something to say; three at most. A droplet is born out of the pill's right
              edge, stretches a neck and pulls free; going, it melts back in
  open        hover the pill 0.3 s (it swells at once to say it heard) or click it: it grows down
              under the clock with the activity's details, or the date. A click on a droplet opens
              it where it is, into a card, the others moving along. A click on what is open acts
              (pause, the Media popover); leaving closes it
  borrowed    a level (volume, mic, brightness) for 1.4 s or something that just spoke up takes
              the whole pill for a moment, then gives it back

Activities, first first: a zazen session, the 遠 eye rest, timers and stopwatches (shoji-timer's,
and GNOME Clocks' timers read off its window by shoji-clocks; the one ending first first), the
music while it plays. Never more than three show at once.

Sources (prefs "island_sources": commands, each a string or a list) print nothing, or JSON
{"short", "text", "tooltip", "click": [argv], "through": bool}: "short" sits in the droplet; a source
that appears speaks up in the pill for 3 s ("text"), and so does a "through" one whose text changes.
During a zazen focus session only sources that say "through" show; Shoji ships none (the kind of
thing meant: a coding agent stuck at a prompt).

Everything is drawn live with kept Pango layouts (a new layout costs 5-15 ms, three frames at
180 Hz); content never scales, it slides and fades. Frames run only while something moves, and
the music's bars redraw 15 times a second only while they show."""
import datetime
import signal

from shoji_widgets.base import *  # noqa: F401,F403
from shoji_widgets import timers as timerlib

W, H = 1240, 132          # the surface: room for the pill and an open droplet's card, transparent elsewhere
TOP = 5                   # the pill (1 px into the surface) lines up with the bar's halves: y 6, 30 high
BAND = 30                 # the top band: the clock, and the droplets beside it
CORE_W = 96
ALPHA = 0.62, 0.82        # the bar's paper while slim, the popovers' once open; Hyprland blurs behind
GAP_X = 8                 # between the pill and a droplet once free
BREAK = 7                 # the neck snaps when the gap passes this (it settles at GAP_X: no neck at rest)
MAX_DROPS = 2             # the pill (with one activity) and two droplets: three at most, as on an iPhone
BURST_S, PEEK_S, DONE_S = 3.0, 1.5, 5.0
HOVER_MS, LEAVE_MS = 300, 100
SOURCE_S = 5
FONT = "Zen Kaku Gothic New"
OPEN = {None: (232, 58), "zazen": (320, 86), "eyes": (320, 86), "timer": (320, 86), "stopwatch": (300, 86),
        "media": (380, 92)}
WINGS = {"zazen": 48, "eyes": 48, "timer": 60, "stopwatch": 60, "media": 48}   # each side alike: the clock stays centred
DROP_W = {"zazen": 60, "eyes": 60, "timer": 66, "stopwatch": 66, "media": 56}
PICK_S = 4                # a picked activity left without the pointer ever reaching it closes after this


class Spring:
    """A value on a spring set the way motion designers do: response (seconds to get there) and
    damping ratio (1 = no overshoot, under 1 = a little give). Sub-stepped, so a long frame stays stable."""
    def __init__(self, v, response=0.4, zeta=0.75):
        self.v, self.target, self.vel = v, v, 0.0
        self.tune(response, zeta)

    def tune(self, response, zeta):
        self.k = (2 * math.pi / response) ** 2
        self.c = 4 * math.pi * zeta / response

    def step(self, dt):
        n = max(1, math.ceil(dt / 0.004))
        for _ in range(n):
            a = self.k * (self.target - self.v) - self.c * self.vel
            self.vel += a * dt / n
            self.v += self.vel * dt / n

    def settled(self, eps=0.3):
        return abs(self.target - self.v) < eps and abs(self.vel) < eps * 4

    def land(self):
        self.v, self.vel = self.target, 0.0


def die_with_us():
    """For a helper started with Popen: it ends when hypr-widgets does (Linux PR_SET_PDEATHSIG),
    instead of living on until its next line finds the pipe closed."""
    import ctypes
    ctypes.CDLL("libc.so.6", use_errno=True).prctl(1, signal.SIGTERM)


def radius(h):
    """A capsule while slim; a softer rounded rectangle once tall."""
    return min(h / 2, 18 + max(0.0, h - 36) * 0.21)


def parse_item(out):
    """A source's output as {"short", "text", "tooltip", "click", "through"}, or None for nothing."""
    try:
        data = json.loads(out) if out.strip() else None
    except ValueError:
        return None
    if not isinstance(data, dict):
        return None
    text = str(data.get("text") or "").strip()
    short = str(data.get("short") or "").strip() or text[:1]
    if not text:
        return None
    click = data.get("click")
    return {"short": short, "text": text, "tooltip": str(data.get("tooltip") or ""),
            "click": click if isinstance(click, list) and click else None,
            "through": bool(data.get("through"))}


def activities(zazen, eyes, user_timers, media):
    """What is going on, first first: zazen, the eye rest, running timers and stopwatches, playing
    music, then paused timers (still there, but nothing moves)."""
    acts = [{"kind": "zazen", "key": "zazen", "state": zazen}] if zazen else []
    if eyes:
        acts.append({"kind": "eyes", "key": "eyes", "state": eyes})
    as_act = lambda t: {"kind": t["kind"], "key": "t:" + t["id"], "state": t}
    acts += [as_act(t) for t in user_timers if not t.get("paused")]
    if media and media.get("playing"):
        acts.append({"kind": "media", "key": "media", "state": media})
    return acts + [as_act(t) for t in user_timers if t.get("paused")]


def choose(level, burst, acts, items, focus, fullscreen):
    """(main, droplets): main is "level", "burst", the first activity (its wings round the clock),
    "clock", or None (hidden); the droplets are the other activities, then source items, three at
    most. A level or a burst borrows the pill and leaves the droplets as they were."""
    shown = [i for i in items if i and (i["through"] or not focus)]
    if fullscreen:
        return ("level" if level else None), []
    drops = acts[1:] + shown
    if level:
        main = "level"
    elif burst and (burst.get("peek") or any(burst["text"] == i["text"] for i in shown)):
        main, drops = "burst", [d for d in drops if d.get("text") != burst["text"]]
    else:
        main = acts[0] if acts else "clock"
    return main, drops[:MAX_DROPS]


class Drop:
    """A droplet beside the pill. Its left edge sits `off` from its neighbour's right edge: below
    zero it is still inside the neighbour, being born or melting back."""
    def __init__(self, view, hold=False):
        self.view, self.key, self.leaving, self.hold = view, view["key"], False, hold
        w, h = view["size"]
        self.w, self.h = Spring(w, 0.34, 0.8), Spring(h, 0.42, 0.8)
        self.off = Spring(-w, 0.50, 0.60)
        self.off.target = -w if hold else GAP_X   # held: waits inside until a leaving droplet is home

    def come(self, view):
        """Back, or a new size: opening into a card (a little give) or closing (none)."""
        (ow, oh), (w, h) = self.view["size"], view["size"]
        opening = w * h > ow * oh
        self.w.tune(*((0.38, 0.78) if opening else (0.45, 1.0)))
        self.h.tune(*((0.42, 0.80) if opening else (0.32, 1.0)))
        self.view, self.leaving = view, False
        self.w.target, self.h.target, self.off.target = w, h, GAP_X

    def leave(self):
        self.leaving = True
        self.off.tune(0.40, 0.85)
        self.off.target = -self.w.v

    def springs(self):
        return self.w, self.h, self.off


class Island:
    LAYOUTS = {}
    MEASURE = cairo.Context(cairo.ImageSurface(cairo.FORMAT_ARGB32, 1, 1))

    def __init__(self):
        self.win = layer_window("hypr-island", Layer.Layer.OVERLAY)
        Layer.set_anchor(self.win, Layer.Edge.TOP, True)
        Layer.set_margin(self.win, Layer.Edge.TOP, TOP)
        Layer.set_exclusive_zone(self.win, -1)    # over the bar, not below the room it keeps
        self.area = Gtk.DrawingArea()
        self.area.set_size_request(W, H)
        self.area.connect("draw", self.draw)
        self.win.add_events(Gdk.EventMask.ENTER_NOTIFY_MASK | Gdk.EventMask.LEAVE_NOTIFY_MASK
                            | Gdk.EventMask.POINTER_MOTION_MASK | Gdk.EventMask.BUTTON_PRESS_MASK
                            | Gdk.EventMask.SCROLL_MASK)
        self.win.connect("enter-notify-event", self.on_motion)    # a pointer that lands without moving
        self.win.connect("motion-notify-event", self.on_motion)
        self.win.connect("leave-notify-event", self.on_leave)
        self.win.connect("button-press-event", self.on_press)
        self.win.connect("scroll-event", self.on_scroll)
        self.win.add(self.area)
        self.win.connect("realize", lambda *_: self.update_input())
        # what there is to show
        self.level = None                   # (kind, pct, muted), for OSD_MS
        self.timers = {}                    # "zazen" / "eyes" -> the shoji-zazen state
        self.user_timers = []               # shoji-timer, from TimerBell
        self.clock_timers = []              # GNOME Clocks, from shoji-clocks
        self.media, self.cover, self.cover_hex = None, None, None
        self.items, self.seen = {}, {}      # source command -> item; -> what it last said
        self.burst, self.fullscreen = None, False
        self.level_timer = self.burst_timer = self.eq_timer = 0
        # what is shown and how it moves
        self.main, self.drops = self.compose("clock"), []
        w, h = self.main["size"]
        self.w, self.h = Spring(w), Spring(h)
        self.p = Spring(1.0, 0.30, 1.0)     # the content's way from the old view to the new
        self.lv = Spring(0.0, 0.22, 1.0)    # the level bar glides to a new value
        self.sw = Spring(0.0, 0.25, 0.7)    # the swell under a hovering pointer
        self.old = None
        self.ticking, self.last_t = False, None
        self.hover, self.hover_timer, self.leave_timer, self.open = None, 0, 0, False
        self.picked, self.picked_seen, self.pick_timer = None, False, 0   # the activity clicked open
        self.minute = None
        self.win.show_all()
        GLib.timeout_add_seconds(1, self.second)
        self.polling = False
        self.poll()
        GLib.timeout_add_seconds(SOURCE_S, self.poll)
        threading.Thread(target=self.follow_media, daemon=True).start()
        if shutil.which("gnome-clocks") and prefs().get("island_clocks", True):
            threading.Thread(target=self.follow_clocks, daemon=True).start()

    # ---- inputs
    def set_level(self, title, pct, muted):
        low = title.lower()
        kind = "mic" if low.startswith("micro") else "bri" if low.startswith("bright") else "vol"
        self.level = (kind, max(0, min(100, pct)), muted)
        self.lv.target = 0 if muted else self.level[1] / 100
        if self.level_timer:
            GLib.source_remove(self.level_timer)
        self.level_timer = GLib.timeout_add(OSD_MS, self.end_level)
        self.refresh()

    def end_level(self):
        self.level_timer, self.level = 0, None
        self.refresh()
        return False

    def set_timer(self, key, state):
        if state:
            self.timers[key] = state
        else:
            self.timers.pop(key, None)
        self.refresh()

    def set_user_timers(self, found):
        self.user_timers = found
        self.refresh()

    def follow_clocks(self):
        """shoji-clocks watch: a line whenever GNOME Clocks' timers change (it rings them itself)."""
        try:
            proc = subprocess.Popen([str(HOME / ".local/bin/shoji-clocks"), "watch"], stdout=subprocess.PIPE,
                                    stderr=subprocess.DEVNULL, text=True,
                                    preexec_fn=die_with_us)
        except OSError:
            return
        for line in proc.stdout:
            try:
                rows = json.loads(line)["timers"]
            except (ValueError, KeyError, TypeError):
                continue
            GLib.idle_add(self.set_clock_timers, rows)

    def set_clock_timers(self, rows):
        now, out = time.time(), []
        for r in rows:
            old = next((t for t in self.clock_timers if t["i"] == r["i"]), None)
            running = r["running"]
            # keep the old anchor while it agrees to a second: the label only has whole seconds
            if old and bool(old["paused"]) != running and abs(timerlib.left(old, now) - r["left"]) < 1.2:
                out.append(old)
                continue
            out.append({"id": f"clocks{r['i']}", "i": r["i"], "kind": "timer", "label": "Clocks",
                        "seconds": r["total"], "spent": r["total"] - r["left"], "start": now,
                        "paused": None if running else now, "clocks": True})
        self.clock_timers = out
        self.refresh()
        return False

    def announce(self, text, glyph="timer"):
        """Something finished (a timer): it takes the pill for a few seconds."""
        self.speak({"short": text[:1], "text": text, "tooltip": "", "click": None, "through": True,
                    "peek": True, "glyph": glyph, "key": "done:" + text}, DONE_S)
        self.refresh()

    def focus(self):
        t = self.timers.get("zazen")
        return bool(t) and t.get("phase") == "focus"

    def set_fullscreen(self, on):
        if on != self.fullscreen:
            self.fullscreen = on
            self.refresh()

    @staticmethod
    def commands():
        out = []
        for cmd in prefs().get("island_sources") or []:
            if isinstance(cmd, str):
                cmd = cmd.split()
            if isinstance(cmd, list) and cmd:
                out.append([os.path.expanduser(cmd[0])] + cmd[1:])
        return out

    def poll(self):
        if not self.polling:
            cmds = self.commands()
            for key in list(self.items):
                if key not in map(tuple, cmds):
                    self.items.pop(key)
            if cmds:
                self.polling = True
                threading.Thread(target=self.read_sources, args=(cmds,), daemon=True).start()
        return True

    def read_sources(self, cmds):
        got = {}
        for cmd in cmds:
            try:
                out = subprocess.run(cmd, capture_output=True, text=True, timeout=4).stdout
            except (OSError, subprocess.TimeoutExpired):
                out = ""
            item = parse_item(out)
            if item:
                item["key"] = " ".join(cmd)
            got[tuple(cmd)] = item
        GLib.idle_add(self.set_items, got)

    def set_items(self, got):
        self.polling = False
        for key, item in got.items():
            before = self.seen.get(key)
            said = item["text"] if item else None
            # speaks up when it appears, or when what comes through zazen changes; a count that
            # moves (待 5 -> 6) only changes the droplet
            new = said and (before is None or (item["through"] and said != before))
            if new and (item["through"] or not self.focus()):
                self.speak(item)
            self.seen[key], self.items[key] = said, item
        self.refresh()
        return False

    def speak(self, item, seconds=BURST_S):
        self.burst = item
        if self.burst_timer:
            GLib.source_remove(self.burst_timer)
        self.burst_timer = GLib.timeout_add(int(seconds * 1000), self.end_burst)

    def end_burst(self):
        self.burst_timer = 0
        if self.hover != "main":     # it stays while the pointer is on it
            self.burst = None
            self.refresh()
        return False

    def follow_media(self):
        """shoji-media watch prints a line whenever the track or its state changes; on a new
        track, shoji-media info names the cover (fetching it when it is on the web)."""
        try:
            proc = subprocess.Popen([str(HOME / ".local/bin/shoji-media"), "watch"], stdout=subprocess.PIPE,
                                    stderr=subprocess.DEVNULL, text=True,
                                    preexec_fn=die_with_us)
        except OSError:
            return
        title = None
        for line in proc.stdout:
            try:
                d = json.loads(line)
            except ValueError:
                continue
            cls = d.get("class") or ""
            playing = "playing" in (cls if isinstance(cls, list) else [cls])
            lines = (d.get("tooltip") or "").split("\n")
            media = {"title": d.get("text") or "", "artist": lines[1] if len(lines) > 1 else "",
                     "playing": playing} if d.get("text") else None
            GLib.idle_add(self.set_media, media)
            if media and media["title"] != title:
                title = media["title"]
                GLib.idle_add(self.set_cover, *self.read_cover())

    @staticmethod
    def read_cover():
        """(pixbuf 48 px, its most vivid colour as #hex) of the playing track's cover, or (None, None)."""
        try:
            out = subprocess.run([str(HOME / ".local/bin/shoji-media"), "info"], capture_output=True,
                                 text=True, timeout=6).stdout
            url = json.loads(out).get("mpris:artUrl") or ""
        except (OSError, ValueError, subprocess.TimeoutExpired):
            return None, None
        if url.startswith("file://"):
            path = urllib.parse.unquote(url[7:])
        elif url.startswith(("http://", "https://")):
            import hashlib
            path = str(HOME / ".cache/shoji/covers" / hashlib.sha1(url.encode()).hexdigest())
        else:
            return None, None
        try:
            pix = GdkPixbuf.Pixbuf.new_from_file_at_scale(path, 48, 48, False)
        except GLib.Error:
            return None, None
        small = pix.scale_simple(16, 16, GdkPixbuf.InterpType.BILINEAR)
        data, n, stride = small.get_pixels(), small.get_n_channels(), small.get_rowstride()
        acc, total = [0.0, 0.0, 0.0], 0.0
        for y in range(16):
            for x in range(16):
                r, g, b = (data[y * stride + x * n + i] / 255 for i in range(3))
                w = (max(r, g, b) - min(r, g, b)) * max(r, g, b) + 0.02
                acc = [acc[0] + r * w, acc[1] + g * w, acc[2] + b * w]
                total += w
        rgb = [c / total for c in acc]
        lift = 0.75 / max(0.75, max(rgb))   # bright enough to read on the dark paper
        rgb = [min(1.0, c * lift + 0.12) for c in rgb]
        return pix, "#" + "".join(f"{int(c * 255):02x}" for c in rgb)

    def set_cover(self, pix, hex_):
        if pix is None:
            self.cover, self.cover_hex = None, None
        else:
            surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, pix.get_width(), pix.get_height())
            cr = cairo.Context(surf)
            Gdk.cairo_set_source_pixbuf(cr, pix, 0, 0)
            cr.paint()
            self.cover, self.cover_hex = surf, hex_
        self.redraw()
        return False

    def track_position(self):
        """(seconds played, track length) as of now, from the last reading; asks again every 2 s
        while a view shows it (never otherwise)."""
        pos = getattr(self, "pos", None)
        now = time.monotonic()
        if not getattr(self, "pos_asking", False) and (pos is None or now - pos[2] > 2):
            self.pos_asking = True
            threading.Thread(target=self.read_position, daemon=True).start()
        if not pos:
            return 0, 0
        played, length, at = pos
        if self.media and self.media["playing"]:
            played += now - at
        return min(played, length), length

    def read_position(self):
        try:
            out = subprocess.run([str(HOME / ".local/bin/shoji-media"), "info"], capture_output=True, text=True,
                                 timeout=4).stdout
            d = json.loads(out)
            got = (float(d.get("position") or 0), int(d.get("mpris:length") or 0) / 1e6, time.monotonic())
        except (OSError, ValueError, subprocess.TimeoutExpired):
            got = (0.0, 0.0, time.monotonic())   # no length: no bar, and the next try waits 2 s too
        GLib.idle_add(self.set_position, got)

    def set_position(self, got):
        self.pos, self.pos_asking = got, False
        self.redraw()
        return False

    def set_media(self, media):
        old = self.media
        self.media = media
        if media and media["playing"] and (not old or old["title"] != media["title"]):
            # a new track says its name for a moment, then the bars take over
            text = media["title"] + (f" — {media['artist']}" if media["artist"] else "")
            self.speak({"short": "♫", "text": text, "tooltip": "", "click": None, "through": True,
                        "peek": True, "glyph": "music", "markup": True, "key": "peek"}, PEEK_S)
        self.refresh()
        return False

    # ---- what to show
    def acts(self):
        now = time.time()
        found = sorted(self.user_timers + self.clock_timers, key=lambda t: (
            t["kind"] != "timer", timerlib.left(t, now) if t["kind"] == "timer" else t["start"]))
        return activities(self.timers.get("zazen"), self.timers.get("eyes"), found, self.media)

    def refresh(self):
        item_list = [self.items[k] for k in self.items if self.items[k]]
        acts = self.acts()
        if self.picked and not any(a["key"] == self.picked for a in acts):
            self.picked = None              # it ended while open
        main, drops = choose(self.level, self.burst, acts, item_list, self.focus(), self.fullscreen)
        if main is None:
            self.win.hide()
            return
        if not self.win.get_visible():
            self.win.show_all()
        if main in ("level", "burst"):
            view = self.compose(main, self.burst if main == "burst" else None)
        elif main == "clock":
            view = self.compose("open" if self.open else "clock")
        else:
            view = self.compose("open" if self.open else "wings", main)
        self.go(view, [self.compose("card" if d.get("key") == self.picked and d.get("kind") else "drop", d)
                       for d in drops])
        self.music_bars()

    def compose(self, kind, obj=None):
        """A view: what it draws and the size it wants."""
        v = {"kind": kind, "obj": obj, "key": (obj or {}).get("key") or (obj or {}).get("text") or kind}
        v["size"] = self.size(v)
        return v

    def size(self, v):
        k, o = v["kind"], v["obj"] or {}
        if k == "wings":
            return 2 * WINGS[o["kind"]] + CORE_W, BAND
        if k == "open":
            return OPEN[o.get("kind")]
        if k == "level":
            return 250, BAND
        if k == "burst":
            return min(460, 44 + self.measure(self.burst_markup(o), 400) + 18), 34
        if k == "card":
            return OPEN[o["kind"]]
        if k == "drop":
            if o.get("kind") in DROP_W:
                return DROP_W[o["kind"]], BAND
            return max(30, self.measure(f'<span size="9pt" weight="500">{esc(o["short"])}</span>') + 20), BAND
        return CORE_W, BAND

    def burst_markup(self, item):
        text = item["text"] if item.get("markup") else esc(item["text"])   # shoji-media escapes its own
        return f'<span size="9.5pt" weight="500">{text}</span>'

    def same(self, a, b):
        return a["kind"] == b["kind"] and a["key"] == b["key"] and a["size"] == b["size"]

    def go(self, main, drops):
        moved = self.place(drops)
        if self.same(main, self.main):
            self.main = main      # fresh numbers, same shape: no morph
            if moved:
                self.animate()
            self.redraw()
            return
        (ow, oh), (w, h) = self.main["size"], main["size"]
        if w * h > ow * oh:   # opening: the width leads, a little give
            self.w.tune(0.38, 0.78)
            self.h.tune(0.42, 0.80)
        else:                 # closing: the height goes first, no bounce
            self.w.tune(0.45, 1.0)
            self.h.tune(0.32, 1.0)
        self.w.target, self.h.target = w, h
        self.old, self.main = self.main, main
        self.p.v, self.p.vel, self.p.target = 0.0, 0.0, 1.0
        self.animate()

    def place(self, views):
        """A droplet that is new is born out of its neighbour; one no longer wanted melts back."""
        moved, keys, before = False, [v["key"] for v in views], list(self.drops)
        for d in self.drops:
            if d.key not in keys and not d.leaving:
                d.leave()
                moved = True
        for v in views:
            d = next((d for d in self.drops if d.key == v["key"]), None)
            if d is None:
                self.drops.append(Drop(v, hold=any(o.leaving for o in self.drops)))
                moved = True
            elif d.leaving or v["size"] != d.view["size"]:
                d.come(v)
                moved = True
            else:
                d.view = v
        order = {k: i for i, k in enumerate(keys)}
        self.drops.sort(key=lambda d: order[d.key] if d.key in order else before.index(d) - 0.5)
        return moved

    def springs(self):
        return [self.w, self.h, self.p, self.lv, self.sw] + [s for d in self.drops for s in d.springs()]

    def animate(self):
        if reduced():
            for d in self.drops:
                if d.hold:
                    d.hold, d.off.target = False, GAP_X
            for s in self.springs():
                s.land()
            self.old, self.drops = None, [d for d in self.drops if not d.leaving]
            self.update_input()
            self.redraw()
            return
        if not self.ticking:
            self.ticking, self.last_t = True, None
            self.area.add_tick_callback(self.tick)

    # ---- frames: only while something moves
    def tick(self, _w, clock):
        t = clock.get_frame_time() / 1e6
        dt = min(1 / 20, t - self.last_t) if self.last_t else 1 / 60
        self.last_t = t
        springs = self.springs()
        for s in springs:
            s.step(dt)
        self.drops = [d for d in self.drops if not (d.leaving and d.off.settled(1.0))]
        for d in self.drops:   # one droplet at a time: a new one leaves once the going one is (nearly) in
            if d.hold and not any(o.leaving and o.off.v > -o.w.v * 0.5 for o in self.drops):
                d.hold, d.off.target = False, GAP_X
        self.update_input()
        self.redraw()
        if all(s.settled(0.002) if s in (self.p, self.lv, self.sw) else s.settled() for s in springs):
            for s in springs:
                s.land()
            self.old = None
            self.drops = [d for d in self.drops if not d.leaving]
            self.update_input()
            self.ticking = False
            return False
        return True

    def second(self):
        """Once a second: the minute, the timers' numbers; a redraw, never a frame loop."""
        minute = time.strftime("%H:%M")
        if self.acts() or self.open or minute != self.minute:
            self.minute = minute
            self.refresh()
        return True

    def music_bars(self):
        """The bars move while the music plays and shows (pill or droplet): 15 redraws a second."""
        showing = any(v["kind"] in ("wings", "drop", "card") and (v["obj"] or {}).get("kind") == "media"
                      for v in [self.main] + [d.view for d in self.drops])
        want = showing and bool(self.media and self.media["playing"]) and not reduced()
        if want and not self.eq_timer:
            self.eq_timer = GLib.timeout_add(66, self.bars_frame)
        elif not want and self.eq_timer:
            GLib.source_remove(self.eq_timer)
            self.eq_timer = 0

    def bars_frame(self):
        if not self.ticking:
            self.redraw()
        return True

    # ---- geometry and input
    def bounds(self):
        """x0, x1, bottom of what is drawn now: the pill and its droplets."""
        x, y, w, h = self.pill()
        x1, bottom = x + w, y + h
        for _d, bx, by, bw, bh, _g in self.drop_boxes():
            x1, bottom = max(x1, bx + bw), max(bottom, by + bh)
        return x - 10, x1 + 10, bottom + 12     # with the shadow

    def redraw(self):
        """Repaint only where the island is and just was: the surface is wide for an open card,
        and painting all of it every frame costs as much as the island itself."""
        x0, x1, bottom = self.bounds()
        px0, px1, pb = getattr(self, "painted", (x0, x1, bottom))
        self.painted = (x0, x1, bottom)
        lo, hi = int(min(x0, px0)) - 1, int(math.ceil(max(x1, px1))) + 1
        self.area.queue_draw_area(lo, 0, hi - lo, int(math.ceil(max(bottom, pb))) + 1)

    def pill(self):
        s = max(0.0, self.sw.v)
        w, h = max(1.0, self.w.v + 8 * s), max(1.0, self.h.v + 2 * s)
        return (W - w) / 2, 1, w, h      # 1 px down so the ring's top edge isn't cut by the surface

    def drop_boxes(self):
        """(drop, x, y, w, h, gap) left to right, the gap to its neighbour (below 0: still inside it)."""
        x, y, w, _h = self.pill()
        right, out = x + w, []
        for d in self.drops:
            dw, dh, gap = max(1.0, d.w.v), max(1.0, d.h.v), d.off.v
            out.append((d, right + gap, y, dw, dh, gap))
            right = max(right, right + gap + dw)
        return out

    def update_input(self):
        if not self.win.get_window():
            return
        x, y, w, h = self.pill()
        region = cairo.Region(cairo.RectangleInt(int(x), int(y), int(math.ceil(w)), int(math.ceil(h))))
        for d, bx, by, bw, bh, _ in self.drop_boxes():
            if not d.leaving:
                region.union(cairo.RectangleInt(int(bx), int(by), int(math.ceil(bw)), int(math.ceil(bh))))
        self.win.input_shape_combine_region(region)

    def part(self, ev):
        """"main", or the key of the droplet under the pointer."""
        for d, bx, _by, bw, _bh, _ in self.drop_boxes():
            if not d.leaving and bx <= ev.x <= bx + bw:
                return d.key
        return "main"

    def on_motion(self, _w, ev):
        where = self.part(ev)
        if self.leave_timer:
            GLib.source_remove(self.leave_timer)
            self.leave_timer = 0
        if self.sw.target != 1.0:   # at once: it heard you
            self.sw.target = 1.0
            self.animate()
        if where != self.hover:
            self.hover = where
            if self.hover_timer:
                GLib.source_remove(self.hover_timer)
            self.hover_timer = GLib.timeout_add(HOVER_MS, self.hovered)
        return False

    def hovered(self):
        self.hover_timer = 0
        if self.picked:
            self.picked_seen = self.picked_seen or self.hover == self.picked
            return False
        self.open = self.hover == "main" and self.main["kind"] in ("clock", "wings", "open")
        self.refresh()
        return False

    def on_leave(self, _w, ev):
        if ev.detail == Gdk.NotifyType.INFERIOR:
            return False
        if self.hover_timer:
            GLib.source_remove(self.hover_timer)
            self.hover_timer = 0
        if not self.leave_timer:
            self.leave_timer = GLib.timeout_add(LEAVE_MS, self.left)
        return False

    def left(self):
        self.leave_timer, self.hover, self.open = 0, None, False
        self.sw.target = 0.0
        if self.picked and self.picked_seen:
            self.picked = None
        if not self.burst_timer:
            self.burst = None
        self.refresh()
        self.animate()
        return False

    def pick(self, key):
        self.picked, self.picked_seen, self.open = key, False, False
        if self.pick_timer:
            GLib.source_remove(self.pick_timer)
        self.pick_timer = GLib.timeout_add_seconds(PICK_S, self.unpick)
        self.refresh()

    def unpick(self):
        """Clicked open, but the pointer never came over it: it closes by itself."""
        self.pick_timer = 0
        if self.picked and not self.picked_seen and self.hover != self.picked:
            self.picked = None
            self.refresh()
        return False

    def act_actions(self, act):
        """button -> argv for an activity, in the pill or a droplet."""
        bin_ = str(HOME / ".local/bin")
        k = act["kind"]
        if k == "media":
            return {1: [f"{bin_}/hypr-pop", "media"], 3: [f"{bin_}/shoji-media", "toggle"]}
        if k == "timer" and act["state"].get("clocks"):
            return {1: [f"{bin_}/shoji-clocks", "toggle", str(act["state"]["i"])],
                    3: [f"{bin_}/hypr-focus-or-launch", "gnome.clocks", "gnome-clocks"]}
        if k in ("timer", "stopwatch"):
            tid = act["state"]["id"]
            return {1: [f"{bin_}/shoji-timer", "toggle", tid], 3: [f"{bin_}/shoji-timer", "cancel", tid]}
        return {}

    def on_press(self, _w, ev):
        where = self.part(ev)
        d = next((d for d in self.drops if d.key == where), None)
        view = d.view if d else self.main
        obj, kind = view["obj"] or {}, view["kind"]
        if kind in ("drop", "burst") and "text" in obj:   # a source item
            if ev.button == 1 and obj.get("click"):
                spawn(*obj["click"])
            return True
        bin_ = str(HOME / ".local/bin")
        if d and obj.get("kind") and ev.button == 1 and d.key != self.picked:   # open it where it is
            self.pick(d.key)
            return True
        if not d and kind == "wings" and ev.button == 1:   # the pill's activity: open it under the clock
            self.open = True
            self.refresh()
            return True
        if obj.get("kind"):
            cmd = self.act_actions(obj).get(ev.button)
        elif kind == "level":
            cmd = {1: [f"{bin_}/hypr-pop", "audio"], 2: [f"{bin_}/hypr-osd", "mute"]}.get(ev.button)
        else:
            cmd = {1: ["swaync-client", "-t", "-sw"]}.get(ev.button)
        if cmd:
            spawn(*cmd)
        return True

    def on_scroll(self, _w, ev):
        up = ev.direction == Gdk.ScrollDirection.UP or (
            ev.direction == Gdk.ScrollDirection.SMOOTH and ev.get_scroll_deltas()[2] < 0)
        d = next((d for d in self.drops if d.key == self.part(ev)), None)
        view = d.view if d else self.main
        what = (view["obj"] or {}).get("kind") or view["kind"]
        bin_ = str(HOME / ".local/bin")
        if what in ("level", "clock", "open"):
            spawn(f"{bin_}/hypr-osd", "up" if up else "down")
        elif what == "media":
            spawn(f"{bin_}/shoji-media", "previous" if up else "next")
        return True

    # ---- drawing
    def shape(self, cr, x, y, w, h):
        x, y, w, h = x + 0.5, y + 0.5, w - 1, h - 1     # the 1 px ring sits on whole pixels
        r = radius(h)
        cr.new_sub_path()
        cr.arc(x + w - r, y + r, r, -math.pi / 2, 0)
        cr.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
        cr.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
        cr.arc(x + r, y + r, r, math.pi, 3 * math.pi / 2)
        cr.close_path()

    def neck(self, cr, xa, xb, cy, t, outline=False):
        """The bridge between two shapes a few px apart: a band where they still touch, a thread
        just before it snaps (t 1 -> 0). Its ends sit inside both round ends."""
        e = 11.0
        nh = max(1.2, e * (0.15 + 0.85 * t ** 1.6))
        a, b = xa - 7, xb + 7
        m, q = (a + b) / 2, (b - a) / 4
        cr.move_to(a, cy - e)
        cr.curve_to(a + q, cy - e, m - q, cy - nh, m, cy - nh)
        cr.curve_to(m + q, cy - nh, b - q, cy - e, b, cy - e)
        if outline:
            cr.move_to(b, cy + e)
        else:
            cr.line_to(b, cy + e)
        cr.curve_to(b - q, cy + e, m + q, cy + nh, m, cy + nh)
        cr.curve_to(m - q, cy + nh, a + q, cy + e, a, cy + e)
        if not outline:
            cr.close_path()

    def tint(self, view, t):
        """The ring's colour: the activity's own, the way an iPhone tints the island's key line."""
        o = view["obj"] or {}
        k, st = o.get("kind"), o.get("state") or {}
        if k == "media":
            return self.cover_hex or t["accent"]
        if k == "zazen":
            return t["accent"] if st.get("phase") == "focus" else t["muted"]
        if k == "timer":
            return t["muted"] if st.get("paused") else t["accent"]
        if k in ("eyes", "stopwatch"):
            return t["muted"]
        if view["kind"] in ("burst", "drop") and o.get("through"):
            return t["accent"]
        return None

    def draw(self, _w, cr):
        t = theme()["tokens"]
        x, y, w, h = self.pill()
        boxes = self.drop_boxes()
        shapes = [(x, y, w, h)] + [b[1:5] for b in boxes]
        tints = [self.tint(self.main, t)] + [self.tint(b[0].view, t) for b in boxes]
        necks, left = [], x + w
        for d, bx, by, bw, bh, gap in boxes:
            if -14 < gap < BREAK:
                necks.append((left, bx, y + BAND / 2, (BREAK - gap) / (BREAK + 14)))
            left = max(left, bx + bw)

        x0 = min(s_[0] for s_ in shapes) - 2
        x1 = max(s_[0] + s_[2] for s_ in shapes) + 2
        cr.rectangle(x0 - 8, 0, x1 - x0 + 16, max(s_[1] + s_[3] for s_ in shapes) + 12)   # and the shadow
        cr.clip()

        def fill_all(skip=None):     # every shape and neck but one (by index, shapes first)
            for i, s_ in enumerate(shapes):
                if i != skip:
                    self.shape(cr, *s_)
            for i, n in enumerate(necks, start=len(shapes)):
                if i != skip:
                    self.neck(cr, *n)

        # a soft shadow under whatever is open (it now lies over windows, not over the bar); only
        # outside the shapes, or it would darken the see-through paper too
        lifts = [max(0.0, min(1.0, (s_[3] - BAND - 2) / 24)) for s_ in shapes]
        if max(lifts) > 0.02:
            cr.push_group()
            for s_, lift in zip(shapes, lifts):
                for k in range(1, 7) if lift > 0.02 else ():
                    self.shape(cr, s_[0] - k, s_[1] + 2 - k * 0.4, s_[2] + 2 * k, s_[3] + 2 * k)
                    cr.set_source_rgba(0, 0, 0, 0.045 * lift)
                    cr.fill()
            cr.set_operator(cairo.OPERATOR_DEST_OUT)
            for s_ in shapes:
                self.shape(cr, *s_)
            cr.set_source_rgba(0, 0, 0, 1)
            cr.fill()
            cr.pop_group_to_source()
            cr.paint()
        # the paper: one fill for the pill, the droplets and the necks, so where they meet is not darker
        open_ = max(0.0, min(1.0, (h - BAND) / 30))
        cr.push_group()
        fill_all()
        cr.set_source_rgba(*rgba(t["base"]))
        cr.fill()
        cr.pop_group_to_source()
        cr.paint_with_alpha(ALPHA[0] + (ALPHA[1] - ALPHA[0]) * open_)
        # light from above: the top few pixels a shade brighter, as on lacquer
        sheen = cairo.LinearGradient(0, y, 0, y + 16)
        sheen.add_color_stop_rgba(0, 1, 1, 1, 0.06)
        sheen.add_color_stop_rgba(1, 1, 1, 1, 0.0)
        cr.push_group()
        fill_all()
        cr.set_source(sheen)
        cr.fill()
        cr.pop_group_to_source()
        cr.paint()
        # the ring: each outline less what lies inside the others, so joined shapes share one edge
        for i, s_ in enumerate(shapes + [None] * len(necks)):
            cr.push_group()
            if s_:
                self.shape(cr, *s_)
            else:
                self.neck(cr, *necks[i - len(shapes)], outline=True)
            tint = tints[i] if i < len(tints) else tints[0]
            cr.set_source_rgba(*rgba(tint or t["text"]))
            cr.set_line_width(1)
            cr.stroke()
            cr.set_operator(cairo.OPERATOR_DEST_OUT)
            fill_all(skip=i)
            cr.fill()
            cr.pop_group_to_source()
            cr.paint_with_alpha(0.32 if tint else 0.14)     # tinted, quietly; plain: the bar's @edge
        for d, bx, by, bw, bh, gap in boxes:
            a = max(0.0, min(1.0, (gap + bw) / (bw + GAP_X))) ** 2
            cr.save()
            self.shape(cr, bx, by, bw, bh)
            cr.clip()
            self.content(cr, d.view, bx, by, bw, bh, a, 0, t)
            cr.restore()
        self.shape(cr, x, y, w, h)
        cr.clip()
        p = max(0.0, min(1.0, self.p.v))
        core = lambda v: v["kind"] in ("clock", "wings", "open")
        if self.old is None:
            ca = 1.0 if core(self.main) else 0.0
        elif core(self.old) and core(self.main):
            ca = 1.0                                       # the core stays put while all else moves
        elif core(self.main):
            ca = max(0.0, min(1.0, (p - 0.3) / 0.5))
        else:
            ca = max(0.0, 1 - p / 0.3)
        if ca > 0.01:
            self.draw_core(cr, x + w / 2, y + BAND / 2, ca, t)
        if self.old:   # the old content goes first, the new one comes after: never both at once
            out = min(1.0, p / 0.3)
            self.content(cr, self.old, x, y, w, h, (1 - out) ** 1.5, -3 * out, t)
        come = max(0.0, min(1.0, (p - 0.3) / 0.5)) if self.old else 1.0
        self.content(cr, self.main, x, y, w, h, come, 4 * (1 - come), t)
        return False

    # ---- text and glyphs, laid out once
    def layout(self, cr, markup, width=None):
        """A laid-out text, kept: a fresh Pango layout per draw costs 5-15 ms (font fallback for the
        kanji, shaping). Reused, it is rebound to the context and drawn."""
        key = (markup, width)
        lay = self.LAYOUTS.get(key)
        if lay is None:
            if len(self.LAYOUTS) > 160:
                self.LAYOUTS.clear()
            lay = PangoCairo.create_layout(cr)
            lay.set_markup(f'<span font_family="{FONT}">{markup}</span>', -1)
            if width:
                lay.set_width(int(width * Pango.SCALE))
                lay.set_ellipsize(Pango.EllipsizeMode.END)
            self.LAYOUTS[key] = lay
        else:
            PangoCairo.update_layout(cr, lay)
        return lay

    def measure(self, markup, width=None):
        return self.layout(self.MEASURE, markup, width).get_pixel_size()[0]

    def text(self, cr, markup, x, cy, alpha, color, align="center", width=None):
        if alpha <= 0.01:
            return 0
        lay = self.layout(cr, markup, width)
        lw, lh = lay.get_pixel_size()
        cr.set_source_rgba(*rgba(color, alpha))
        cr.move_to(x - (lw / 2 if align == "center" else 0), cy - lh / 2)
        PangoCairo.show_layout(cr, lay)
        return lw

    def glyph(self, cr, name, x, cy, alpha, color, size="10pt"):
        self.text(cr, f'<span font_family="lucide" size="{size}">{icon(name)}</span>', x, cy, alpha, color)

    def draw_core(self, cr, cx, cy, a, t):
        now = datetime.datetime.now()
        self.text(cr, f'<span weight="500" size="10.5pt">{now:%H:%M}</span>'
                      f'<span font_family="Kaisei Opti" size="9pt">  {WEEK_K[(now.weekday() + 1) % 7]}</span>',
                  cx, cy, a, t["text"])

    def draw_cover(self, cr, cx, cy, size, a, t):
        if not self.cover:
            self.glyph(cr, "music", cx, cy, a, t["accent"], size="9.5pt")
            return
        cr.save()
        r = min(5.0, size / 4)
        x0, y0 = cx - size / 2, cy - size / 2
        cr.new_sub_path()
        cr.arc(x0 + size - r, y0 + r, r, -math.pi / 2, 0)
        cr.arc(x0 + size - r, y0 + size - r, r, 0, math.pi / 2)
        cr.arc(x0 + r, y0 + size - r, r, math.pi / 2, math.pi)
        cr.arc(x0 + r, y0 + r, r, math.pi, 3 * math.pi / 2)
        cr.close_path()
        cr.clip()
        k = size / self.cover.get_width()
        cr.translate(x0, y0)
        cr.scale(k, k)
        cr.set_source_surface(self.cover, 0, 0)
        cr.get_source().set_filter(cairo.FILTER_GOOD)
        cr.paint_with_alpha(a)
        cr.restore()

    def draw_bars(self, cr, cx, cy, a, t, n=4):
        """Music bars, Spotify-style decoration rather than a spectrum: they move while it plays."""
        color = self.cover_hex or t["accent"]
        playing = bool(self.media and self.media["playing"])
        now = time.monotonic()
        bw, gap, hmax = 2.6, 2.4, 13.0
        x0 = cx - (n * bw + (n - 1) * gap) / 2
        cr.set_source_rgba(*rgba(color if playing else t["muted"], a))
        for i, (f, ph) in enumerate(((5.1, 0.0), (7.3, 1.3), (4.2, 2.1), (6.4, 0.7))[:n]):
            level = 0.3 + 0.7 * abs(math.sin(now * f * 0.5 + ph)) if playing and not reduced() else 0.35
            bh = max(bw, hmax * level)
            bx, by = x0 + i * (bw + gap), cy - bh / 2
            cr.new_sub_path()
            cr.arc(bx + bw / 2, by + bw / 2, bw / 2, math.pi, 0)
            cr.arc(bx + bw / 2, by + bh - bw / 2, bw / 2, 0, math.pi)
            cr.close_path()
            cr.fill()

    def content(self, cr, view, x, y, w, h, a, dy, t):
        """A view's own content (not the clock): the open body hangs
        under the core band, a borrowed pill is centred; dy slides it while it fades."""
        if a <= 0.01:
            return
        k, o = view["kind"], view["obj"] or {}
        tw, th = view["size"]
        cy = y + BAND / 2 + dy
        if k == "wings":   # each wing holds to its edge of the pill
            ww = WINGS[o["kind"]]
            self.wing(cr, o, "left", x + ww / 2 + 3, cy, a, t)
            self.wing(cr, o, "right", x + w - ww / 2 - 3, cy, a, t)
        elif k == "open":
            self.body(cr, o, x + w / 2 - tw / 2, y + BAND + dy, tw, th - BAND, a, t)
        elif k in ("drop", "card"):
            if "text" in o:
                self.text(cr, f'<span size="9pt" weight="500">{esc(o["short"])}</span>', x + w / 2, cy, a,
                          t["accent"] if o.get("through") else t["text"])
                return
            # the droplet's own face holds at its left while it widens, and gives way to the
            # card's details, centred in the card (no clock up there to make room for)
            ow, oh = OPEN[o["kind"]]
            reveal = max(0.0, min(1.0, (h - BAND - 4) / (oh - BAND - 4)))
            self.mini(cr, o, x + DROP_W[o["kind"]] / 2, cy, a * (1 - reveal) ** 2, t)
            if reveal > 0.01:
                self.body(cr, o, x, y + BAND / 2 + 6 * (1 - reveal), ow, oh - BAND, a * reveal ** 1.5, t)
        elif k == "level":
            self.draw_level(cr, x + w / 2 - tw / 2, tw, cy, a, t)
        elif k == "burst":
            bx = x + w / 2 - tw / 2
            ccy = y + h / 2 + dy
            if o.get("glyph"):
                self.glyph(cr, o["glyph"], bx + 20, ccy, a, t["accent"], size="9.5pt")
            else:
                cr.set_source_rgba(*rgba(t["accent"], a))
                cr.arc(bx + 20, ccy, 4, 0, 2 * math.pi)
                cr.fill()
            self.text(cr, self.burst_markup(o), bx + 34, ccy, a, t["text"], align="left", width=tw - 48)

    # ---- per activity
    def timer_numbers(self, o):
        """(fraction done, the value to read, colour key) of a timer-like activity."""
        st, now = o["state"], time.time()
        if o["kind"] in ("zazen", "eyes"):
            total = st["minutes"] * 60
            left = max(0.0, total - (now - st["start"]))
            short = f"{math.ceil(left)}s" if o["kind"] == "eyes" else f"{math.ceil(left / 60)}m"
            return 1 - left / total, short, left, total
        if o["kind"] == "timer":
            left = max(0.0, timerlib.left(st, now))
            return 1 - left / st["seconds"], timerlib.fmt(math.ceil(left)), left, st["seconds"]
        ran = timerlib.ran(st, now)
        return (ran % 60) / 60, timerlib.fmt(ran), ran, None

    def wing(self, cr, o, side, cx, cy, a, t):
        """One side of the pill's activity: what it is on the left, its live value on the right."""
        k, st = o["kind"], o["state"]
        if k in ("zazen", "eyes"):
            frac, short, _, _ = self.timer_numbers(o)
            resting = st.get("phase") in ("rest", "look")
            if side == "left":
                cr.new_path()
                enso(cr, cx, cy, 7.5, frac, rgba(t["muted"] if resting else t["accent"], a), 2.2,
                     track=rgba(t["text"], 0.10 * a))
            else:
                self.text(cr, f'<span font_family="Kaisei Opti" weight="bold" size="10.5pt">{short}</span>', cx, cy,
                          a, t["text"])
        elif k in ("timer", "stopwatch"):
            _, short, _, _ = self.timer_numbers(o)
            paused = bool(st.get("paused"))
            col = t["muted"] if paused else t["accent"]
            if side == "left":
                self.glyph(cr, "pause" if paused else ("timer" if k == "timer" else "hourglass"), cx, cy, a, col,
                           size="9.5pt")
            else:
                self.text(cr, f'<span weight="500" size="10pt">{short}</span>', cx, cy, a, col)
        elif k == "media":
            if side == "left":
                self.draw_cover(cr, cx, cy, 20, a, t)
            else:
                self.draw_bars(cr, cx, cy, a, t)

    def mini(self, cr, o, cx, cy, a, t):
        """An activity as a droplet: what it is and its live value, not just a logo."""
        k, st = o["kind"], o["state"]
        if k in ("zazen", "eyes"):
            frac, short, _, _ = self.timer_numbers(o)
            resting = st.get("phase") in ("rest", "look")
            cr.new_path()   # enso() draws from the current point: start clean
            enso(cr, cx - 14, cy, 7, frac, rgba(t["muted"] if resting else t["accent"], a), 2.0,
                 track=rgba(t["text"], 0.10 * a))
            self.text(cr, f'<span font_family="Kaisei Opti" weight="bold" size="9.5pt">{short}</span>', cx + 10, cy,
                      a, t["text"])
        elif k in ("timer", "stopwatch"):
            _, short, _, _ = self.timer_numbers(o)
            paused = bool(st.get("paused"))
            col = t["muted"] if paused else t["accent"]
            self.glyph(cr, "pause" if paused else ("timer" if k == "timer" else "hourglass"), cx - 20, cy, a, col,
                       size="8.5pt")
            self.text(cr, f'<span size="9pt" weight="500">{short}</span>', cx + 8, cy, a, col)
        elif k == "media":
            self.draw_cover(cr, cx - 11, cy, 18, a, t)
            self.draw_bars(cr, cx + 12, cy, a, t, n=3)

    def body(self, cr, o, bx, by, bw, bh, a, t):
        """The open pill under the core band."""
        k = o.get("kind")
        mid = by + bh / 2
        if k is None:
            now = datetime.datetime.now()
            self.text(cr, f'<span size="9pt">{esc(day_name(now))} · {esc(day_month(now))}</span>', bx + bw / 2,
                      by + bh / 2 - 2, a, t["muted"])
        elif k == "media":
            m = self.media or {}
            self.draw_cover(cr, bx + 40, mid - 2, 46, a, t)
            self.text(cr, f'<span weight="500" size="11pt">{m.get("title", "")}</span>', bx + 74, mid - 15, a,
                      t["text"], align="left", width=bw - 92)
            self.text(cr, f'<span size="9pt">{m.get("artist", "")}</span>', bx + 74, mid + 3, a, t["muted"],
                      align="left", width=bw - 92)
            done, length = self.track_position()
            if length:
                tx, tw = bx + 74, bw - 92 - 44
                self.track(cr, tx, mid + 19, tw, 1.0, rgba(t["text"], 0.14 * a), 3)
                self.track(cr, tx, mid + 19, tw, min(1.0, done / length), rgba(self.cover_hex or t["accent"], a), 3)
                self.text(cr, f'<span size="8pt">-{timerlib.fmt(length - done)}</span>', bx + bw - 22, mid + 19, a,
                          t["muted"], align="center")
        else:
            st = o["state"]
            frac, _, value, total = self.timer_numbers(o)
            resting = st.get("phase") in ("rest", "look") or st.get("paused")
            if k == "timer":
                frac = 1 - frac   # a timer's ring is what is left: full at the start, as on an iPhone
            cr.new_path()   # enso() draws from the current point: start clean
            enso(cr, bx + 40, mid, 19, frac, rgba(t["muted"] if resting else t["accent"], a), 3.0,
                 track=rgba(t["text"], 0.14 * a))
            big = timerlib.fmt(math.ceil(value) if total else value)
            self.text(cr, f'<span font_family="Kaisei Opti" weight="bold" size="16pt">{big}</span>', bx + 74,
                      mid - 11, a, t["text"], align="left")
            if k in ("zazen", "eyes"):
                what = {"focus": T("Focus"), "rest": T("Rest"), "look": T("Look far away")}.get(st.get("phase"), "")
            else:
                what = st.get("label") or T("Timer" if k == "timer" else "Stopwatch")
            if st.get("paused"):
                when = T("paused")
            elif total:
                ends = datetime.datetime.now() + datetime.timedelta(seconds=value)
                when = T("until {t}").format(t=f"{ends:%H:%M}")
            else:
                when = T("since {t}").format(t=f"{datetime.datetime.fromtimestamp(st['start'] - st.get('spent', 0)):%H:%M}")
            self.text(cr, f'<span size="8.5pt">{esc(what)} · {esc(when)}</span>', bx + 74, mid + 13, a, t["muted"],
                      align="left", width=bw - 90)

    def track(self, cr, x, cy, w, frac, color, th):
        """A bar with round ends, filled to frac."""
        fw = w * frac
        if fw < 0.5:
            return
        r = th / 2
        cr.new_path()
        cr.arc(x + r, cy, r, math.pi / 2, 3 * math.pi / 2)
        cr.arc(x + max(r, fw - r), cy, r, -math.pi / 2, math.pi / 2)
        cr.close_path()
        cr.set_source_rgba(*color)
        cr.fill()

    def draw_level(self, cr, x, w, cy, a, t):
        kind, pct, muted = self.level or ("vol", 0, False)
        name = {"vol": "volume-x" if muted else "volume-2", "mic": "mic-off" if muted else "mic", "bri": "sun"}[kind]
        self.glyph(cr, name, x + 22, cy, a, t["muted"] if muted else t["text"])
        bx, bw = x + 42, w - 94
        self.track(cr, bx, cy, bw, 1.0, rgba(t["text"], 0.14 * a), 5)
        self.track(cr, bx, cy, bw, max(0.0, min(1.0, self.lv.v)), rgba(t["muted"] if muted else t["accent"], a), 5)
        self.text(cr, f'<span size="9pt" weight="500">{T("muted") if muted else pct}</span>', x + w - 28, cy, a,
                  t["text"])


def esc(s):
    return GLib.markup_escape_text(s)
