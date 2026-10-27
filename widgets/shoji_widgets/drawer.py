"""引出し The drawer: cards to read at a glance, sliding in from the right edge.

A card shows one thing in a few words (a number, a line or three) and opens the whole story on a
click; only the media card acts in place. Healthy cards stay quiet; colour is for trouble, like the
rest of Shoji. Cards come from Shoji (Homelab, Media) and from your popover plugins: a
~/.config/shoji/popovers/*.py may set CARDS = [Card subclasses] next to POPOVERS.

Open it with Super+grave, the bar's drawer button, `hypr-pop drawer`, or by resting the pointer on
the right screen edge (prefs "drawer_edge": false turns that off). ✎ edits like macOS: drag a card
to move it (or click it, then click where it goes; Alt+←/→ with the keyboard), S · M · L sets its
size, the eye hides it. Kept in prefs "drawer_order", "drawer_sizes", "drawer_hidden".
"""
import re

from shoji_widgets.popovers import *  # noqa: F401,F403

CARD_W, GAP = 170, 12            # two small cards and a gap fill the drawer's width
WIDTH = 2 * CARD_W + GAP + 28    # + the panel's padding (14 px each side)
HEIGHTS = {"small": 112, "medium": 112, "large": 236}
SIZE_LETTER = {"small": "S", "medium": "M", "large": "L"}
DND = [Gtk.TargetEntry.new("shoji/card", Gtk.TargetFlags.SAME_APP, 0)]


class Card:
    """One card. Subclasses set name, title, icon, size and opens (the popover a click opens), and
    write fill(box); level() colours the icon and the big number (ok | warn | bad); available()
    hides a card that has nothing to say here (no homelab set up, no player)."""
    name = ""
    title = ""
    icon = "square"
    size = "small"      # the default: small (half width) | medium (full width) | large (full, twice as tall)
    sizes = ("small", "medium")   # what ✎ offers (S · M · L); the drawer sets self.size from prefs
    LINES = {"small": 2, "medium": 3, "large": 7}
    opens = ""
    refresh = ()        # a command that refreshes the card's data, run when the drawer opens

    def __init__(self, drawer):
        self.drawer = drawer
        self.memo = {}

    def once(self, key, fn):
        """fn() once per drawer rebuild: available(), level() and fill() share one reading."""
        cycle = self.drawer.cycle
        if self.memo.get(key, (None,))[0] != cycle:
            self.memo[key] = (cycle, fn())
        return self.memo[key][1]

    def available(self):
        return True

    def level(self):
        return "ok"

    def compact(self):
        """Text for a one-line card when there is nothing worth a big number (readings appear only
        when they need you); None draws the full card. May be (text, widget) to keep a button."""
        return None

    def health(self):
        """(stale | failed, text) when the data behind the card is old or could not be fetched."""
        return None

    def fill(self, box):
        pass

    def opens_something(self):
        return bool(self.opens)

    def click(self):
        if self.opens:
            self.drawer.manager.toggle(self.opens, back="drawer")   # Esc there comes back here

    # ---- the few things a card is made of
    def lines(self):
        """How many lines of text this size has room for."""
        return self.LINES[self.size]

    def split(self, box):
        """(where the big number goes, where the lines go): one column when small; side by side,
        number left, when the card is wide."""
        if self.size == "small":
            return box, box
        row = Gtk.Box(spacing=16)
        left = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        right = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        right.set_valign(Gtk.Align.CENTER if self.size == "medium" else Gtk.Align.START)
        row.pack_start(left, False, False, 0)
        row.pack_start(right, True, True, 0)
        box.pack_start(row, False, False, 0)
        return left, right

    def listing(self, box, rows, empty):
        """Up to lines() rows of (text, level); "+N more" when they do not fit."""
        n = self.lines()
        shown = rows if len(rows) <= n else rows[:n - 1]
        for text, level in shown:
            self.text(box, text, level)
        if len(rows) > len(shown):
            self.text(box, T("+{n} more").format(n=len(rows) - len(shown)))
        if not rows:
            self.text(box, empty)

    @staticmethod
    def big(box, text):
        box.pack_start(label(text, "dc-big"), False, False, 0)

    @staticmethod
    def text(box, text, level="ok"):
        lab = label(text, "dc-line", level)
        lab.set_ellipsize(3)  # END
        box.pack_start(lab, False, False, 0)


class HomelabCard(Card):
    name, title, icon, opens = "homelab", "Homelab", "server", "homelab"
    sizes = ("small", "medium", "large")
    refresh = (str(HOME / ".local/bin/shoji-homelab"), "collect")

    def data(self):
        return self.once("data", lambda: HL.read_cache() if HL else None)

    def health(self):
        d = self.data()
        if d and time.time() - d.get("at", 0) > 120:
            return "stale", T("checked {t} ago").format(t=HL.span(time.time() - d["at"]))
        return None

    def available(self):
        return bool(HL and HL.config() is not None)

    def level(self):
        d = self.data() or {"problems": []}
        levels = {p["level"] for p in d["problems"]}
        return "bad" if "bad" in levels else "warn" if "warn" in levels else "ok"

    def fill(self, box):
        d = self.data()
        if not d:
            self.text(box, "…")
            return
        cs = d["containers"]
        left, right = self.split(box)
        self.big(left, f"{sum(c['state'] == 'running' for c in cs)}/{len(cs)}")
        rows = [(f"{p['name']} · {p['why']}", p["level"]) for p in d["problems"] if p["level"] != "ok"]
        if self.size == "large":   # room for the rest: every endpoint and service, quietly
            rows += [(f"{e['name']} · {e['why']}", "ok") for e in d.get("endpoints", []) if e["level"] == "ok"]
        self.listing(right, rows, T("all well"))


class MediaCard(Card):
    """Now playing, and the one card that acts where it is: previous, play / pause, next."""
    name, title, icon, opens, size = "media", "Media", "music", "media", "medium"
    sizes = ("small", "medium", "large")
    MEDIA = str(HOME / ".local/bin/shoji-media")

    def info(self):
        def read():
            try:
                return json.loads(sh(self.MEDIA, "info") or "{}")
            except ValueError:
                return {}
        return self.once("info", read)

    def available(self):
        return bool(self.info().get("title"))

    def fill(self, box):
        i = self.info()
        row = Gtk.Box(spacing=12)
        cover = Media.cover(i.get("mpris:artUrl", "")) if i.get("mpris:artUrl") else None
        side = {"small": 0, "medium": 48, "large": 140}[self.size]
        if self.size == "large" and cover:   # a big cover above, the words and buttons below
            img = Gtk.Image.new_from_pixbuf(cover.scale_simple(side, side, GdkPixbuf.InterpType.BILINEAR))
            img.set_halign(Gtk.Align.START)
            box.pack_start(img, False, False, 2)
        elif cover and side:
            img = Gtk.Image.new_from_pixbuf(cover.scale_simple(side, side, GdkPixbuf.InterpType.BILINEAR))
            row.pack_start(img, False, False, 0)
        if self.size == "small":   # title above, buttons below
            row.set_orientation(Gtk.Orientation.VERTICAL)
        words = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        title = label(i.get("title", ""), "dc-title")
        title.set_ellipsize(3)
        words.pack_start(title, False, False, 0)
        self.text(words, i.get("artist", ""))
        row.pack_start(words, True, True, 0)
        buttons = Gtk.Box(spacing=0)
        for glyph, tip, cmd in (("skip-back", "Previous", "previous"),
                                ("pause" if i.get("status") == "Playing" else "play", "Play / pause", "toggle"),
                                ("skip-forward", "Next", "next")):
            b = Gtk.Button(label=icon(glyph))
            b.get_style_context().add_class("hl-act")
            b.set_valign(Gtk.Align.CENTER)
            b.set_tooltip_text(T(tip))
            b.connect("clicked", lambda *_, c=cmd: (sh(self.MEDIA, c), GLib.timeout_add(400, self.drawer.refresh_once)))
            (buttons if self.size == "small" else row).pack_start(b, False, False, 0)
        if self.size == "small":
            row.pack_start(buttons, False, False, 0)
        box.pack_start(row, False, False, 0)


class FocusCard(Card):
    """座 Today's zazen: sessions and minutes; the button starts 25 minutes (or stops a running one).
    The card itself opens Preferences, where the lengths are set."""
    name, title, icon, opens = "focus", "Focus", "timer", "prefs"
    sizes = ("small", "medium")
    ZAZEN = str(HOME / ".local/bin/shoji-zazen")
    LOG = HOME / ".local/state/shoji-zazen.log"   # one line per finished session: date minutes

    def today(self):
        day = datetime.date.today().isoformat()
        try:
            rows = [l.split() for l in self.LOG.read_text().splitlines() if l.startswith(day)]
        except OSError:
            return 0, 0
        return len(rows), sum(int(r[1]) for r in rows if len(r) > 1 and r[1].isdigit())

    def compact(self):
        n, _ = self.today()
        if n or self.state() != "off":
            return None
        b = Gtk.Button(label=icon("play"))
        b.get_style_context().add_class("hl-act")
        b.set_tooltip_text(T("Start 25 min of focus"))
        b.connect("clicked", lambda *_: (spawn(self.ZAZEN, "toggle"), self.drawer.manager.close()))
        return T("No focus yet today"), b

    def state(self):
        return self.once("state", lambda: sh(self.ZAZEN, "status"))

    def fill(self, box):
        n, minutes = self.today()
        state = self.state()
        left, right = self.split(box)
        row = Gtk.Box(spacing=8)
        row.pack_start(label(f"座 ×{n}", "dc-big"), True, True, 0)
        b = Gtk.Button(label=icon("square" if state != "off" else "play"))
        b.get_style_context().add_class("hl-act")
        b.set_valign(Gtk.Align.CENTER)
        b.set_tooltip_text(T("Stop") if state != "off" else T("Start 25 min of focus"))
        b.connect("clicked", lambda *_: (spawn(self.ZAZEN, "toggle"), self.drawer.manager.close()))
        row.pack_start(b, False, False, 0)
        left.pack_start(row, False, False, 0)
        from shoji_widgets import rest
        taken = rest.taken_today()
        if self.size == "small":
            self.text(right, state if state != "off" else T("{m} min today").format(m=minutes)
                      + (f" · 休 ×{taken}" if taken else ""))
        else:
            self.text(right, state if state != "off" else T("{m} min today").format(m=minutes))
            self.text(right, T("{n} rest taken" if taken == 1 else "{n} rests taken").format(n=taken))


class ClipboardCard(Card):
    """The last three things you copied; a click copies one back."""
    name, title, icon, opens, size = "clipboard", "Clipboard", "clipboard", "clipboard", "medium"
    sizes = ("medium", "large")

    def available(self):
        return bool(shutil.which("cliphist"))

    def items(self):
        return self.once("items", lambda: sh("cliphist", "list").splitlines()[:7])

    def compact(self):
        return None if self.items() else T("Nothing copied yet")

    def fill(self, box):
        for line in self.items()[:self.lines()]:
            cid, _, text = line.partition("\t")
            image = re.search(r"binary data.*?\b(png|jpe?g|gif|webp|bmp|svg)", text)   # cliphist's line for a picture
            b = Gtk.Button(label=T("Image · {kind}").format(kind=image[1]) if image else " ".join(text.split())[:60] or "…")
            b.get_style_context().add_class("link")
            b.get_child().set_xalign(0)
            b.get_child().set_ellipsize(3)
            b.set_tooltip_text(T("Copy again"))
            b.connect("clicked", lambda *_, l=line: self.copy(l))
            box.pack_start(b, False, False, 0)

    def copy(self, line):
        data = subprocess.run(["cliphist", "decode"], input=line.encode(), capture_output=True).stdout
        subprocess.Popen(["wl-copy"], stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, start_new_session=True).communicate(data, timeout=2)
        self.drawer.manager.close()


class MachineCard(Card):
    """This machine: the hottest sensor big, memory, swap and disks below; quiet until something
    runs hot (85 °C), full (disk 90 %) or swapping hard (90 %)."""
    name, title, icon = "machine", "Machine", "cpu"
    sizes = ("small", "medium")
    SENSORS = ("coretemp", "k10temp", "zenpower", "amdgpu", "nvme")

    def temps(self):
        out = {}
        for h in Path("/sys/class/hwmon").glob("hwmon*"):
            try:
                name = (h / "name").read_text().strip()
                if name in self.SENSORS:
                    out[name] = max(out.get(name, 0), int((h / "temp1_input").read_text()) // 1000)
            except (OSError, ValueError):
                pass
        return out

    def disks(self):
        cfg = HL.config() if HL else None
        return (cfg or {}).get("disks", ["/"])

    def readings(self):
        return self.once("readings", self.read)

    def read(self):
        info = dict(l.split(":", 1) for l in Path("/proc/meminfo").read_text().splitlines())
        kb = lambda k: int(info[k].split()[0])
        mem = round(100 * (1 - kb("MemAvailable") / kb("MemTotal")))
        swap = round(100 * (1 - kb("SwapFree") / kb("SwapTotal"))) if kb("SwapTotal") else 0
        disks = {}
        for d in self.disks():
            try:
                u = shutil.disk_usage(d)
                disks[d] = round(100 * u.used / u.total)
            except OSError:
                pass
        return mem, swap, disks, self.temps()

    def compact(self):
        if self.level() != "ok":
            return None
        mem, swap, disks, temps = self.readings()
        return " · ".join(x for x in (f"{max(temps.values())}°" if temps else "", f"mem {mem}%", f"swap {swap}%") if x)

    def level(self):
        mem, swap, disks, temps = self.readings()
        if any(v >= 90 for v in disks.values()):
            return "bad"
        return "warn" if swap >= 90 or mem >= 90 or any(t >= 85 for t in temps.values()) else "ok"

    def fill(self, box):
        mem, swap, disks, temps = self.readings()
        left, right = self.split(box)
        self.big(left, f"{max(temps.values())}°" if temps else f"{mem}%")
        self.text(right, f"mem {mem}% · swap {swap}%", "warn" if swap >= 90 or mem >= 90 else "ok")
        self.text(right, " · ".join(f"{d} {p}%" for d, p in disks.items()), "bad" if any(p >= 90 for p in disks.values()) else "ok")
        if self.size != "small" and temps:   # every sensor, named
            names = {"coretemp": "cpu", "k10temp": "cpu", "zenpower": "cpu", "amdgpu": "gpu", "nvme": "nvme"}
            self.text(right, " · ".join(f"{names.get(k, k)} {v}°" for k, v in temps.items()),
                      "warn" if any(v >= 85 for v in temps.values()) else "ok")


class Drawer(Popover):
    name = "drawer"
    namespace = "hypr-drawer"   # its own layer: Hyprland slides it in from the right
    width = WIDTH
    TICK_S = 5

    def __init__(self, manager, cards):
        super().__init__(manager)
        Layer.set_anchor(self.win, Layer.Edge.BOTTOM, True)
        Layer.set_margin(self.win, Layer.Edge.BOTTOM, 10)
        self.cycle = 0   # bumped on every rebuild; cards read their data once per cycle
        self.cards = [cls(self) for cls in cards]
        self.editing = False
        self.picked = None   # ✎ without a mouse drag: the card clicked first, waiting for where it goes
        self.ticking = False
        self.scroll = None
        # opened by the hot edge, the drawer slides in under a pointer that was aiming at something
        # else: for GUARD_MS a shield over the cards takes the click meant for the window below
        self.win.remove(self.box)
        over = Gtk.Overlay()
        over.add(self.box)
        self.shield = Gtk.EventBox()
        self.shield.set_visible_window(False)
        self.shield.set_no_show_all(True)
        self.shield.connect("button-press-event", lambda *_: True)
        self.shield.connect("button-release-event", lambda *_: True)
        over.add_overlay(self.shield)
        over.show()
        self.win.add(over)

    GUARD_MS = 600

    def guard(self):
        self.shield.show()
        GLib.timeout_add(self.GUARD_MS, lambda: self.shield.hide() or False)

    # ---- which cards, in which order, at which size
    def ordered(self):
        pr = prefs()
        order, hidden, sizes = pr.get("drawer_order", []), set(pr.get("drawer_hidden", [])), pr.get("drawer_sizes", {})
        cards = [c for c in self.cards if c.available()]
        for c in cards:
            want = sizes.get(c.name)
            c.size = want if want in c.sizes else type(c).size
        cards.sort(key=lambda c: order.index(c.name) if c.name in order else len(order))
        return [c for c in cards if c.name not in hidden], [c for c in cards if c.name in hidden]

    def save_order(self, names):
        rest = [n for n in prefs().get("drawer_order", []) if n not in names]
        save_prefs(drawer_order=names + rest)
        self.refresh_once()

    def move(self, card, step):
        names = [c.name for c in self.ordered()[0]]
        i = names.index(card.name)
        j = max(0, min(len(names) - 1, i + step))
        names[i], names[j] = names[j], names[i]
        self.save_order(names)

    def place(self, name, target, after=False):
        """Put card `name` where `target` is (just after it when dropped on its far half)."""
        names = [c.name for c in self.ordered()[0]]
        if name == target or name not in names or target not in names:
            return
        names.remove(name)
        names.insert(names.index(target) + (1 if after else 0), name)
        self.save_order(names)

    def resize(self, card, size):
        sizes = dict(prefs().get("drawer_sizes", {}))
        sizes[card.name] = size
        save_prefs(drawer_sizes=sizes)
        self.refresh_once()

    def hide_card(self, card, hide=True):
        hidden = set(prefs().get("drawer_hidden", []))
        hidden = hidden | {card.name} if hide else hidden - {card.name}
        save_prefs(drawer_hidden=sorted(hidden))
        self.refresh_once()

    # ---- showing
    def show(self):
        self.editing = False
        super().show()
        cmds = list(dict.fromkeys(tuple(c.refresh) for c in self.cards if c.refresh))   # one run each

        def work():
            for cmd in cmds:
                subprocess.run(list(cmd), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            GLib.idle_add(self.refresh_once)
        threading.Thread(target=work, daemon=True).start()
        if not self.ticking:
            self.ticking = True
            GLib.timeout_add_seconds(self.TICK_S, self.tick)

    def tick(self):
        if not self.win.get_visible():
            self.ticking = False
            return False
        if not self.editing:
            self.refresh_once()
        return True

    def refresh_once(self):
        if self.win.get_visible():
            at = self.scroll.get_vadjustment().get_value() if self.scroll else 0
            focused = self.win.get_focus()
            was = focused.get_name() if focused else ""
            self.clear()
            self.build()
            name_icons(self.box)
            self.box.show_all()
            again = Listing.find(self, was) if was.startswith(("card:", "act:")) else None
            if again:   # the 5 s refresh must not throw a keyboard user out of their card
                again.grab_focus()
            else:
                self.win.set_focus(None)
            GLib.idle_add(lambda: self.scroll and self.scroll.get_vadjustment().set_value(at))
        return False

    def build(self):
        self.cycle += 1
        edit = Gtk.Button(label=T("Done") if self.editing else icon("pencil"))
        edit.get_style_context().add_class("chip" if self.editing else "hl-act")
        edit.set_tooltip_text(T("Edit widgets"))
        edit.connect("clicked", lambda *_: (setattr(self, "editing", not self.editing), setattr(self, "picked", None),
                                            self.refresh_once()))
        self.header(T("Widgets"), edit)
        if self.editing:
            hint = T("Click where it goes, or Esc") if self.picked else T("Drag to move · S M L to resize")
            self.box.pack_start(label(hint, "mono"), False, False, 0)
        body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=GAP)
        shown, hidden = self.ordered()
        half = None   # a row holding one small card: the next small card fills it, even after a wide one
        for card in shown:
            w = self.card(card)
            if card.size != "small":
                body.pack_start(w, False, False, 0)
            elif half is None:
                half = Gtk.Box(spacing=GAP)
                half.pack_start(w, False, False, 0)
                body.pack_start(half, False, False, 0)
            else:
                half.pack_start(w, False, False, 0)
                half = None
        if not shown:
            body.pack_start(label(T("No widgets: ✎ to add some"), "muted"), False, False, 6)
        if self.editing and hidden:
            body.pack_start(label(T("HIDDEN"), "label-small", "hl-section"), False, False, 0)
            for card in hidden:
                row = Gtk.Box(spacing=8)
                row.pack_start(label(icon(card.icon), "dc-icon"), False, False, 0)
                row.pack_start(label(T(card.title)), True, True, 0)
                add = Gtk.Button(label=icon("plus"))
                add.get_style_context().add_class("hl-act")
                add.set_tooltip_text(T("Show"))
                add.connect("clicked", lambda *_, c=card: self.hide_card(c, False))
                row.pack_start(add, False, False, 0)
                body.pack_start(row, False, False, 0)
        self.scroll = Gtk.ScrolledWindow()
        self.scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.scroll.add(body)
        self.box.pack_start(self.scroll, True, True, 0)

    def card(self, card):
        """A card: focusable (Tab / arrows, Enter opens it), named for screen readers by its title and
        the line it shows, lit on hover only when a click leads somewhere."""
        ev = Gtk.EventBox()
        ev.set_visible_window(False)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        ctx = box.get_style_context()
        compact = None if self.editing else card.compact()
        text, extra = compact if isinstance(compact, tuple) else (compact, None)
        for cls in ("dcard", card.size, card.level(), *(["opens"] if card.opens_something() else []),
                    *(["compact"] if text else []), *(["editing"] if self.editing else []),
                    *(["picked"] if self.picked == card.name else [])):
            ctx.add_class(cls)
        box.set_size_request(CARD_W if card.size == "small" else 2 * CARD_W + GAP, 0 if text else HEIGHTS[card.size])
        head = Gtk.Box(spacing=6)
        head.pack_start(label(icon(card.icon), "dc-icon"), False, False, 0)
        head.pack_start(label(T(card.title), "label-small"), True, True, 0)
        box.pack_start(head, False, False, 0)
        if self.editing:   # like macOS: the sizes the card offers, and hide
            tools = Gtk.Box(spacing=2)
            for size in card.sizes if len(card.sizes) > 1 else ():   # one size: nothing to choose
                b = Gtk.Button(label=SIZE_LETTER[size])
                b.set_name(f"act:{card.name}:{size}")
                b.get_style_context().add_class("size-chip")
                if size == card.size:
                    b.get_style_context().add_class("on")
                b.set_tooltip_text(T({"small": "Small", "medium": "Wide", "large": "Large"}[size]))
                b.connect("clicked", lambda *_, z=size: self.resize(card, z))
                tools.pack_start(b, False, False, 0)
            hide = Gtk.Button(label=icon("eye-off"))
            hide.set_name(f"act:{card.name}:hide")
            hide.get_style_context().add_class("hl-act")
            hide.set_tooltip_text(T("Hide"))
            hide.connect("clicked", lambda *_: self.hide_card(card))
            tools.pack_end(hide, False, False, 0)
            box.pack_start(tools, False, False, 0)
        if text:
            line = Gtk.Box(spacing=6)
            lab = label(text, "dc-line")
            lab.set_ellipsize(3)
            line.pack_start(lab, True, True, 0)
            if extra:
                line.pack_start(extra, False, False, 0)
            box.pack_start(line, False, False, 0)
        else:
            card.fill(box)
        sick = card.health()
        if sick:   # old or failed data says so, instead of looking like a calm day
            Card.text(box, ("? " if sick[0] == "failed" else "") + sick[1], "warn")
        ev.add(box)
        ev.set_name(f"card:{card.name}")
        ev.set_can_focus(True)
        ev.get_accessible().set_name(", ".join(x for x in (T(card.title), text or "", sick[1] if sick else "") if x))
        ev.add_events(Gdk.EventMask.ENTER_NOTIFY_MASK | Gdk.EventMask.LEAVE_NOTIFY_MASK
                      | Gdk.EventMask.BUTTON_RELEASE_MASK | Gdk.EventMask.KEY_PRESS_MASK)
        ev.connect("enter-notify-event", lambda *_: ctx.add_class("hot"))
        ev.connect("leave-notify-event", lambda _w, e: e.detail == Gdk.NotifyType.INFERIOR or ctx.remove_class("hot"))
        ev.connect("focus-in-event", lambda *_: ctx.add_class("focus"))
        ev.connect("focus-out-event", lambda *_: ctx.remove_class("focus"))
        ev.connect("button-release-event", lambda _w, e: self.pick(card) if self.editing else card.click())
        ev.connect("key-press-event", lambda _w, e: self.on_card_key(card, e))
        if self.editing:
            self.draggable(ev, box, card)
        elif card.opens_something():
            ev.set_tooltip_text(T("Open {what}").format(what=T(card.title)))
        return ev

    # ---- ✎ moving cards: drag and drop, or click then click, or Alt+arrows
    def draggable(self, ev, box, card):
        ev.drag_source_set(Gdk.ModifierType.BUTTON1_MASK, DND, Gdk.DragAction.MOVE)
        ev.drag_dest_set(Gtk.DestDefaults.ALL, DND, Gdk.DragAction.MOVE)
        ctx = box.get_style_context()

        def begin(_w, dctx):   # the card itself follows the pointer
            alloc = box.get_allocation()
            surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, max(1, alloc.width), max(1, alloc.height))
            box.draw(cairo.Context(surf))
            Gtk.drag_set_icon_surface(dctx, surf)
            ctx.add_class("dragging")

        def after(w, x):
            return x > w.get_allocated_width() / 2

        def motion(w, _dctx, x, _y, _t):
            ctx.remove_class("drop-before" if after(w, x) else "drop-after")
            ctx.add_class("drop-after" if after(w, x) else "drop-before")
            return False

        ev.connect("drag-begin", begin)
        ev.connect("drag-end", lambda *_: ctx.remove_class("dragging"))
        ev.connect("drag-data-get", lambda _w, _c, data, _i, _t: data.set(data.get_target(), 8, card.name.encode()))
        ev.connect("drag-motion", motion)
        ev.connect("drag-leave", lambda *_: (ctx.remove_class("drop-before"), ctx.remove_class("drop-after")))
        ev.connect("drag-data-received", lambda w, _c, x, _y, data, _i, _t:
                   GLib.idle_add(self.place, data.get_data().decode(), card.name, after(w, x)))

    def pick(self, card):
        """Without dragging: click a card, then the card whose place it should take."""
        if self.picked and self.picked != card.name:
            name, self.picked = self.picked, None
            self.place(name, card.name)
        else:
            self.picked = None if self.picked == card.name else card.name
            self.refresh_once()
        return True

    def on_card_key(self, card, e):
        if e.keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter, Gdk.KEY_space):
            self.pick(card) if self.editing else card.click()
            return True
        if self.editing and e.state & Gdk.ModifierType.MOD1_MASK and e.keyval in (Gdk.KEY_Left, Gdk.KEY_Up,
                                                                                   Gdk.KEY_Right, Gdk.KEY_Down):
            self.move(card, -1 if e.keyval in (Gdk.KEY_Left, Gdk.KEY_Up) else 1)
            return True
        if e.keyval == Gdk.KEY_Escape and self.picked:
            self.picked = None
            self.refresh_once()
            return True
        return False


class VpnCard(Card):
    """VPNs with their switches, right in the drawer (like the media card, it acts in place)."""
    name, title, icon, opens, size = "vpn", "VPN", "lock", "network", "medium"
    sizes = ("medium",)   # a row per VPN with its switch needs the width

    def available(self):
        return bool(self.once("vpns", Vpn.all))

    def fill(self, box):
        Vpn.rows(box, self.drawer.refresh_once, row_spacing=0)


BUILT_IN = [HomelabCard, MediaCard, VpnCard, MachineCard, FocusCard, ClipboardCard]


class EdgeTrigger:
    """The right screen edge opens the drawer: rest the pointer still on it for DWELL_MS. One strip
    per monitor (kept in step when monitors come and go), on the middle 40 % of the edge. A strip
    sits over the right edge of a maximised window, its scroll bar included, so a pass does not
    count: any movement starts the wait again, a held button (dragging, scrolling the bar) cancels
    it, and a fullscreen window (a game, a film) never opens it."""
    DWELL_MS = 500
    SHARE = 0.4

    def __init__(self, manager):
        self.manager, self.timer, self.wins = manager, 0, []
        display = Gdk.Display.get_default()
        display.connect("monitor-added", lambda *_: self.build())
        display.connect("monitor-removed", lambda *_: self.build())
        self.build()

    def build(self):
        for w in self.wins:
            w.destroy()
        self.wins = []
        if not prefs().get("drawer_edge", True):
            return
        display = Gdk.Display.get_default()
        for i in range(display.get_n_monitors()):
            mon = display.get_monitor(i)
            win = layer_window("hypr-edge", Layer.Layer.OVERLAY)
            Layer.set_monitor(win, mon)
            Layer.set_anchor(win, Layer.Edge.RIGHT, True)
            Layer.set_exclusive_zone(win, -1)
            win.set_size_request(1, int(mon.get_geometry().height * self.SHARE))
            win.add_events(Gdk.EventMask.ENTER_NOTIFY_MASK | Gdk.EventMask.LEAVE_NOTIFY_MASK
                           | Gdk.EventMask.POINTER_MOTION_MASK)
            win.connect("enter-notify-event", self.wait)
            win.connect("motion-notify-event", self.wait)
            win.connect("leave-notify-event", self.cancel)
            win.show()
            self.wins.append(win)

    @staticmethod
    def held(ev):
        return ev.state & (Gdk.ModifierType.BUTTON1_MASK | Gdk.ModifierType.BUTTON2_MASK | Gdk.ModifierType.BUTTON3_MASK)

    def wait(self, _w, ev):
        """(Re)start the wait: the pointer has to stay still on the edge for the whole DWELL_MS."""
        self.cancel()
        if not self.held(ev):
            self.timer = GLib.timeout_add(self.DWELL_MS, self.fire)

    def cancel(self, *_):
        if self.timer:
            GLib.source_remove(self.timer)
            self.timer = 0

    def fire(self):
        self.timer = 0
        try:
            full = json.loads(sh("hyprctl", "activewindow", "-j") or "{}").get("fullscreen", 0)
        except ValueError:
            full = 0
        if not full and self.manager.open != "drawer":
            self.manager.toggle("drawer")
            self.manager.items["drawer"].guard()
        return False
