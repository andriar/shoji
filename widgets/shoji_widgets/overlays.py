"""Surfaces that come and go on their own: the ensō OSD, the screenshot and reminder cards,
Meetings (Silent while busy) and the zazen ensō."""
from shoji_widgets.base import *  # noqa: F401,F403
from shoji_widgets.popovers import *  # noqa: F401,F403


# ---------------------------------------------------------------- OSD
class Osd:
    SIZE = 116

    def __init__(self):
        self.win = layer_window("hypr-osd", Layer.Layer.OVERLAY)
        Layer.set_anchor(self.win, Layer.Edge.TOP, True)
        Layer.set_anchor(self.win, Layer.Edge.RIGHT, True)
        Layer.set_margin(self.win, Layer.Edge.TOP, GAP)
        Layer.set_margin(self.win, Layer.Edge.RIGHT, 16)
        self.area = Gtk.DrawingArea()
        self.area.set_size_request(self.SIZE, self.SIZE)
        self.area.connect("draw", self.draw)
        self.win.add(self.area)
        self.area.show()
        self.win.connect("realize", click_through)
        self.timer = 0
        self.pct, self.muted, self.kind = 0, False, "vol"
        # the arc and the number glide to a new level instead of jumping (easeOutCubic)
        self.shown, self.tween, self.ticking = 0.0, None, False

    def draw(self, _w, cr):
        t = theme()["tokens"]
        s = self.SIZE
        c = s / 2
        # paper disc + hairline
        cr.set_source_rgba(*rgba(t["base"], 0.80))
        cr.arc(c, c, c - 1, 0, 2 * math.pi)
        cr.fill_preserve()
        cr.set_source_rgba(*rgba(t["text"], 0.14))
        cr.set_line_width(1)
        cr.stroke()
        col = rgba(t["muted"] if self.muted else t["accent"])
        enso(cr, c, c, c - 15, self.shown / 100, col, 6, track=rgba(t["text"], 0.12))
        # number + label
        layout = self.area.create_pango_layout("")
        layout.set_markup(
            f'<span font_family="Kaisei Opti" weight="bold" size="21pt" foreground="{t["muted"] if self.muted else t["text"]}">'
            f'{"off" if self.muted else round(self.shown)}</span>', -1)
        w, h = layout.get_pixel_size()
        cr.move_to(c - w / 2, c - h / 2 - 6)
        PangoCairo.show_layout(cr, layout)
        sub = {"vol": "音量 · VOL", "mic": "マイク · MIC", "bri": "明 · BRIGHT"}[self.kind]
        if self.muted:
            sub = "MUTED"
        layout2 = self.area.create_pango_layout("")
        layout2.set_markup(f'<span font_family="Zen Kaku Gothic New" size="7.5pt" letter_spacing="1500" '
                           f'foreground="{t["muted"]}">{sub}</span>', -1)
        w2, h2 = layout2.get_pixel_size()
        cr.move_to(c - w2 / 2, c + h / 2 - 8)
        PangoCairo.show_layout(cr, layout2)
        return False

    def show(self, title, pct, muted):
        low = title.lower()
        self.kind = "mic" if low.startswith("micro") else "bri" if low.startswith("bright") else "vol"
        self.pct, self.muted = max(0, min(100, pct)), muted
        self.tween = (self.shown, 0 if muted else self.pct, None)
        if reduced():
            self.shown = self.tween[1]
            self.area.queue_draw()
        elif not self.ticking:
            self.ticking = True
            self.area.add_tick_callback(self.step)
        self.win.show()
        if self.timer:
            GLib.source_remove(self.timer)
        self.timer = GLib.timeout_add(OSD_MS, self.hide)

    def step(self, _w, clock):
        start, goal, t0 = self.tween
        now = clock.get_frame_time()
        if t0 is None:
            t0 = now
            self.tween = (start, goal, t0)
        x = min(1.0, (now - t0) / (OSD_TWEEN_MS * 1000))
        self.shown = start + (goal - start) * (1 - (1 - x) ** 3)
        self.area.queue_draw()
        if x >= 1:
            self.ticking = False
            return GLib.SOURCE_REMOVE
        return GLib.SOURCE_CONTINUE

    def hide(self):
        self.timer = 0
        self.win.hide()
        return False


# ---------------------------------------------------------------- screenshot card
class ShotCard:
    """After a screenshot (hypr-shot writes "shot<TAB>path"): a small card in the bottom right with
    the picture, already copied, and Open / Folder / Delete. It leaves after 6 s, or stays while the
    pointer is on it."""
    STAY_MS, W, H = 6000, 300, 170

    def __init__(self):
        self.win = layer_window("hypr-card", Layer.Layer.OVERLAY)
        for edge in (Layer.Edge.BOTTOM, Layer.Edge.RIGHT):
            Layer.set_anchor(self.win, edge, True)
            Layer.set_margin(self.win, edge, 16)
        self.box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.box.get_style_context().add_class("panel")
        events = Gtk.EventBox()
        events.add(self.box)
        events.connect("enter-notify-event", lambda *_: self.hold())
        events.connect("leave-notify-event", lambda *_: self.later())
        self.win.add(events)
        self.timer, self.path = 0, None

    def show(self, path):
        self.path = Path(path)
        try:
            pix = GdkPixbuf.Pixbuf.new_from_file_at_scale(str(self.path), self.W, self.H, True)
        except GLib.Error:
            return
        load_css()
        for c in self.box.get_children():
            self.box.remove(c)
        art = Gtk.DrawingArea()
        art.set_size_request(pix.get_width(), pix.get_height())
        art.set_halign(Gtk.Align.CENTER)
        art.connect("draw", self.draw, pix)
        click = Gtk.EventBox()
        click.add(art)
        click.connect("button-press-event", lambda *_: self.open())
        self.box.pack_start(click, False, False, 0)
        line = Gtk.Box(spacing=6)
        line.pack_start(label(T("Copied") + " · " + self.path.name.removeprefix("screenshot-"), "label-small"), True, True, 0)
        for ico, tip, fn in (("image", "Open", self.open), ("folder", "Show in folder", self.folder),
                             ("trash-2", "Delete", self.delete)):
            b = Gtk.Button(label=icon(ico))
            b.get_style_context().add_class("nav")
            b.set_tooltip_text(T(tip))
            b.connect("clicked", lambda _b, f=fn: f())
            line.pack_start(b, False, False, 0)
        self.box.pack_start(line, False, False, 0)
        self.box.show_all()
        self.win.show_all()
        self.later()

    @staticmethod
    def draw(_w, cr, pix):
        Media.rounded(cr, 0, 0, pix.get_width(), pix.get_height(), 8)
        cr.clip()
        Gdk.cairo_set_source_pixbuf(cr, pix, 0, 0)
        cr.paint()
        return False

    def hold(self):
        if self.timer:
            GLib.source_remove(self.timer)
            self.timer = 0
        return False

    def later(self):
        self.hold()
        self.timer = GLib.timeout_add(self.STAY_MS, self.hide)
        return False

    def hide(self):
        self.timer = 0
        self.win.hide()
        return False

    def open(self):
        viewer = shutil.which("eog") or shutil.which("loupe") or "xdg-open"
        spawn(viewer, str(self.path))
        self.hide()

    def folder(self):
        spawn("thunar", str(self.path)) if shutil.which("thunar") else spawn("xdg-open", str(self.path.parent))
        self.hide()

    def delete(self):
        self.path.unlink(missing_ok=True)
        self.hide()


# ---------------------------------------------------------------- meetings
class ReminderCard:
    """10 minutes before a timed event: a card in the bottom right (where the screenshot card sits)
    with the title and time, Join when the event carries a call link, and Dismiss. It stays until
    dismissed or five minutes after the start; a soft 鈴 announces it (prefs "rin")."""

    def __init__(self):
        self.win = layer_window("hypr-card", Layer.Layer.OVERLAY)
        for edge in (Layer.Edge.BOTTOM, Layer.Edge.RIGHT):
            Layer.set_anchor(self.win, edge, True)
            Layer.set_margin(self.win, edge, 16)
        self.box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.box.get_style_context().add_class("panel")
        self.box.set_size_request(300, -1)
        self.win.add(self.box)
        self.timer = 0

    def show(self, item):
        load_css()
        for c in self.box.get_children():
            self.box.remove(c)
        start = datetime.datetime.combine(datetime.date.today(),
                                          datetime.datetime.strptime(item["when"], "%H:%M").time())
        mins = max(0, round((start - datetime.datetime.now()).total_seconds() / 60))
        self.box.pack_start(label(f"{T('in {m} min').format(m=mins).upper()} · {item['when']}–{item['end']}", "label-small"), False, False, 0)
        title = label(item["title"], "title")
        title.set_ellipsize(Pango.EllipsizeMode.END)
        self.box.pack_start(title, False, False, 0)
        row = Gtk.Box(spacing=6)
        if item.get("url"):
            join = Gtk.Button(label=T("Join"))
            join.get_style_context().add_class("chip")
            join.get_style_context().add_class("on")
            join.connect("clicked", lambda *_: (spawn("xdg-open", item["url"]), self.hide()))
            row.pack_start(join, False, False, 0)
        later = Gtk.Button(label=T("Dismiss"))
        later.get_style_context().add_class("chip")
        later.connect("clicked", lambda *_: self.hide())
        row.pack_end(later, False, False, 0)
        self.box.pack_start(row, False, False, 2)
        self.box.show_all()
        self.win.show_all()
        if self.timer:
            GLib.source_remove(self.timer)
        stay = max(60, (start - datetime.datetime.now()).total_seconds() + 300)
        self.timer = GLib.timeout_add_seconds(int(stay), self.hide)
        rin = HOME / ".local/share/shoji/rin.wav"
        if prefs().get("rin", True) and rin.exists():
            spawn("pw-play", "--volume", "0.4", str(rin))

    def hide(self):
        self.timer = 0
        self.win.hide()
        return False


class Meetings:
    """Around today's timed events and screen sharing:
    - 静 Silent turns itself on while an event is running or the screen is being shared (Hyprland's
      screencast event), and off afterwards, with one note of how many notifications waited. If
      Silent was already on by hand, it is left alone. prefs "auto_silent": false turns this off.
    - a reminder card 10 minutes before each timed event."""

    def __init__(self, today):
        self.today, self.reasons, self.ours, self.held_from = today, set(), False, 0
        self.reminded = set()
        self.card = ReminderCard()
        GLib.timeout_add_seconds(30, self.tick)
        GLib.timeout_add_seconds(5, lambda: (self.tick(), False)[1])  # once the agenda has loaded

    def tick(self):
        now = datetime.datetime.now()
        hm, soon = now.strftime("%H:%M"), (now + datetime.timedelta(minutes=10)).strftime("%H:%M")
        timed = [i for i in self.today.items() if not i["task"] and i["when"] not in ("", "終日")]
        self.set("meeting", any(i["when"] <= hm < i["end"] for i in timed))
        for i in timed:
            key = (i["uid"], i["when"])
            if hm < i["when"] <= soon and key not in self.reminded:
                self.reminded.add(key)
                self.card.show(i)
        return True

    def set(self, reason, on):
        before = bool(self.reasons)
        (self.reasons.add if on else self.reasons.discard)(reason)
        if bool(self.reasons) == before or prefs().get("auto_silent", True) is False:
            return
        if self.reasons:
            if sh("swaync-client", "-D") == "true":
                return  # silent already, by hand: not ours to undo
            self.held_from = int(sh("swaync-client", "-c") or 0)
            sh("swaync-client", "-dn")
            self.ours = True
        elif self.ours:
            self.ours = False
            if sh("swaync-client", "-D") == "true":
                sh("swaync-client", "-df")
            held = max(0, int(sh("swaync-client", "-c") or 0) - self.held_from)
            if held:
                spawn("notify-send", "-a", "Shoji", "-u", "low", "静 · Silent is off again",
                      f"{held} notification{'s' * (held != 1)} waited while you were busy.")


# ---------------------------------------------------------------- zazen
class Zazen:
    """坐禅 ensō at the top centre while a focus session runs (shoji-zazen): it closes as the time
    passes, the minutes left sit inside it. Click-through; at the end it stops the session."""
    SIZE = 56
    STATE = RUN / "shoji-zazen.json"

    def __init__(self):
        self.win = layer_window("hypr-zazen", Layer.Layer.OVERLAY)
        Layer.set_anchor(self.win, Layer.Edge.TOP, True)
        Layer.set_margin(self.win, Layer.Edge.TOP, GAP)
        self.area = Gtk.DrawingArea()
        self.area.set_size_request(self.SIZE, self.SIZE)
        self.area.connect("draw", self.draw)
        self.win.add(self.area)
        self.area.show()
        self.win.connect("realize", click_through)
        self.state, self.ticking = None, False
        self.start()  # a session survives a hypr-widgets restart

    def start(self):
        try:
            self.state = json.loads(self.STATE.read_text())
        except (OSError, ValueError):
            self.state = None
            return
        self.win.show()
        if not self.ticking:
            self.ticking = True
            GLib.timeout_add_seconds(1, self.tick)

    def stop(self):
        self.state = None
        self.win.hide()

    def left(self):
        return self.state["minutes"] * 60 - (time.time() - self.state["start"])

    def tick(self):
        if not self.state:
            self.ticking = False
            return False
        if self.left() <= 0:
            self.ticking = False
            spawn(str(HOME / ".local/bin/shoji-zazen"), "stop", "--done")
            self.stop()
            return False
        self.area.queue_draw()
        return True

    def draw(self, _w, cr):
        if not self.state:
            return False
        t = theme()["tokens"]
        c = self.SIZE / 2
        cr.set_source_rgba(*rgba(t["base"], 0.82))
        cr.arc(c, c, c - 1, 0, 2 * math.pi)
        cr.fill_preserve()
        cr.set_source_rgba(*rgba(t["text"], 0.14))
        cr.set_line_width(1)
        cr.stroke()
        total = self.state["minutes"] * 60
        resting = self.state.get("phase") == "rest"  # the 休 after a session: quieter, no number
        enso(cr, c, c, c - 9, 1 - max(0, self.left()) / total, rgba(t["muted"] if resting else t["accent"]), 3.2,
             track=rgba(t["text"], 0.10))
        mins = "休" if resting else max(0, math.ceil(self.left() / 60))
        lay = PangoCairo.create_layout(cr)
        lay.set_markup(f'<span font_family="Kaisei Opti" weight="bold" size="12pt" foreground="{t["text"]}">{mins}</span>', -1)
        w, h = lay.get_pixel_size()
        cr.move_to(c - w / 2, c - h / 2)
        PangoCairo.show_layout(cr, lay)
        return False
