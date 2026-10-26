"""休 The rest card: when a zazen session ends, one thing to do away from the screen, over a dimmed
desktop (prefs "zazen_dim"). ✓ Done logs it and lets the screen be; ↻ Another asks for a different
one; ⏭ Skip ends the rest. Esc, or a click on the dimmed part, only puts the card away — the rest
goes on, its ensō at the top. A breathing suggestion gets a breathing ensō: in 4 · hold 4 · out 4 ·
hold 4 (still, with the numbers written, under reduced motion)."""
from shoji_widgets.base import *  # noqa: F401,F403
from shoji_widgets import rest

STATE = RUN / "shoji-zazen.json"
ZAZEN = str(HOME / ".local/bin/shoji-zazen")
BREATH = (("in", 4), ("hold", 4), ("out", 4), ("hold", 4))   # box breathing, seconds


class RestCard:
    WIDTH = 420
    ENSO = 170

    def __init__(self):
        self.win = layer_window("hypr-rest", Layer.Layer.OVERLAY, keyboard=True)
        self.win.connect("key-press-event", self.on_key)
        self.dim = Gtk.EventBox()   # the dimmed screen; a click on it puts the card away
        self.dim.set_visible_window(False)
        self.dim.connect("button-press-event", lambda *_: self.hide())
        self.dim.connect("draw", self.paint_dim)
        self.dim.set_app_paintable(True)
        self.win.add(self.dim)
        self.card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.card.get_style_context().add_class("panel")
        self.card.get_style_context().add_class("rest-card")
        self.card.set_size_request(self.WIDTH, -1)
        self.card.set_halign(Gtk.Align.CENTER)
        self.card.set_valign(Gtk.Align.CENTER)
        holder = Gtk.EventBox()   # clicks on the card stay on the card
        holder.set_visible_window(False)
        holder.add(self.card)
        holder.set_halign(Gtk.Align.CENTER)
        holder.set_valign(Gtk.Align.CENTER)
        holder.connect("button-press-event", lambda *_: True)
        self.dim.add(holder)
        self.suggestion, self.ticking, self.breath_t0 = None, False, 0
        self.left_label = None
        self.area = None

    # ---- placement: the whole screen when dimming, else just the card in the middle
    def place(self, dim):
        for edge in (Layer.Edge.TOP, Layer.Edge.BOTTOM, Layer.Edge.LEFT, Layer.Edge.RIGHT):
            Layer.set_anchor(self.win, edge, dim)
        Layer.set_exclusive_zone(self.win, -1 if dim else 0)
        self.dimmed = dim

    def paint_dim(self, w, cr):
        if getattr(self, "dimmed", False):
            t = theme()["tokens"]
            cr.set_source_rgba(*rgba(t["base"], 0.86))
            cr.paint()
        return False

    def state(self):
        try:
            return json.loads(STATE.read_text())
        except (OSError, ValueError):
            return None

    def left(self):
        st = self.state()
        return max(0, st["minutes"] * 60 - (time.time() - st["start"])) if st and st.get("phase") == "rest" else 0

    # ---- show / hide
    def show(self, last=None):
        st = self.state()
        if not st or st.get("phase") != "rest":
            return
        load_css()
        self.suggestion = rest.pick(st["minutes"], last=last, lang=LANG["code"])
        self.place(prefs().get("zazen_dim", True))
        self.build(st)
        self.win.show_all()
        self.win.present()
        if not self.ticking:
            self.ticking = True
            GLib.timeout_add_seconds(1, self.tick)

    def hide(self):
        self.win.hide()
        self.breath_t0 = 0

    def on_key(self, _w, ev):
        if ev.keyval == Gdk.KEY_Escape:
            self.hide()
            return True
        return False

    def tick(self):
        if not self.win.get_visible():
            self.ticking = False
            return False
        left = self.left()
        if left <= 0:
            self.hide()
            self.ticking = False
            return False
        if self.left_label:
            self.left_label.set_text(f"{int(left // 60)}:{int(left % 60):02d}")
        return True

    # ---- the card
    def build(self, st):
        for c in self.card.get_children():
            self.card.remove(c)
        s = self.suggestion
        head = Gtk.Box(spacing=8)
        head.pack_start(label("休", "seal", xalign=0.5), False, False, 0)
        head.pack_start(label(T("REST · {m} MIN").format(m=st["minutes"]), "label-small"), True, True, 0)
        self.left_label = label("", "mono")
        head.pack_start(self.left_label, False, False, 0)
        self.card.pack_start(head, False, False, 0)
        self.card.pack_start(label(s["title"], "rest-title"), False, False, 4)
        how = label(s["how"], "rest-how")
        how.set_line_wrap(True)
        how.set_max_width_chars(44)
        self.card.pack_start(how, False, False, 0)
        if s["breath"]:
            self.area = Gtk.DrawingArea()
            self.area.set_size_request(self.ENSO, self.ENSO)
            self.area.set_halign(Gtk.Align.CENTER)
            self.area.connect("draw", self.draw_breath)
            self.card.pack_start(self.area, False, False, 6)
            self.breath_t0 = time.monotonic()
            if not reduced():
                GLib.timeout_add(33, self.animate)
        row = Gtk.Box(spacing=6)
        for text, cls, fn, tip in ((T("Done"), ("chip", "on"), self.done, T("I did it")),
                                   (T("Another"), ("chip",), self.another, T("Something else")),
                                   (T("Skip rest"), ("link",), self.skip, T("End the rest now"))):
            b = Gtk.Button(label=text)
            for c in cls:
                b.get_style_context().add_class(c)
            b.set_tooltip_text(tip)
            b.connect("clicked", lambda *_, f=fn: f())
            (row.pack_end if cls == ("link",) else row.pack_start)(b, False, False, 0)
        self.card.pack_start(row, False, False, 6)
        self.tick()

    def done(self):
        rest.log(self.suggestion["id"], "done")
        self.hide()

    def another(self):
        rest.log(self.suggestion["id"], "another")
        self.show(last=self.suggestion["id"])

    def skip(self):
        rest.log(self.suggestion["id"], "skip")
        self.hide()
        spawn(ZAZEN, "stop")

    # ---- breathing
    def phase(self, t):
        """(word, seconds left in it, how open the ensō is 0..1) at t seconds into box breathing."""
        cycle = sum(n for _, n in BREATH)
        t %= cycle
        for i, (word, n) in enumerate(BREATH):
            if t < n:
                frac = t / n
                opening = {0: frac, 1: 1.0, 2: 1 - frac, 3: 0.0}[i]
                return word, math.ceil(n - t), opening
            t -= n
        return "in", 4, 0.0

    def animate(self):
        if not (self.area and self.win.get_visible() and self.suggestion and self.suggestion["breath"]):
            return False
        self.area.queue_draw()
        return True

    def draw_breath(self, w, cr):
        t = theme()["tokens"]
        size = w.get_allocated_width()
        c = size / 2
        if reduced():
            word, secs, opening = "4 · 4 · 4 · 4", 0, 1.0
        else:
            word, secs, opening = self.phase(time.monotonic() - self.breath_t0)
            word = T({"in": "breathe in", "hold": "hold", "out": "breathe out"}[word])
        r = (c - 8) * (0.55 + 0.45 * opening)
        enso(cr, c, c, r, 0.92, rgba(t["accent"]), 4, track=rgba(t["text"], 0.08))
        lay = PangoCairo.create_layout(cr)
        lay.set_markup(f'<span font_family="Kaisei Opti" size="10pt" foreground="{t["text"]}">{word}'
                       + (f"\n<span size=\'16pt\' weight=\'bold\'>{secs}</span>" if secs else "") + "</span>", -1)
        lay.set_alignment(Pango.Alignment.CENTER)
        lw, lh = lay.get_pixel_size()
        cr.move_to(c - lw / 2, c - lh / 2)
        PangoCairo.show_layout(cr, lay)
        return False
