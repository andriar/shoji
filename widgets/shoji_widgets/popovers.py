"""The popovers under the bar: Sound, Network, Theme, Battery, Media, the launcher and the
shortcuts sheet."""
from shoji_widgets.base import *  # noqa: F401,F403
from shoji_widgets.koyomi import *  # noqa: F401,F403


# ---------------------------------------------------------------- popovers
class Backdrop:
    """Invisible full-screen layer under a popover: a click anywhere else closes it."""

    def __init__(self, on_click):
        self.win = layer_window("hypr-backdrop", Layer.Layer.TOP)
        for e in (Layer.Edge.TOP, Layer.Edge.BOTTOM, Layer.Edge.LEFT, Layer.Edge.RIGHT):
            Layer.set_anchor(self.win, e, True)
        Layer.set_exclusive_zone(self.win, -1)
        ev = Gtk.EventBox()
        ev.set_visible_window(False)
        ev.connect("button-press-event", lambda *_: on_click())
        self.win.add(ev)
        ev.show()


class Popover:
    name = ""
    width = 320

    def __init__(self, manager, anchor_right=True):
        self.manager = manager
        self.win = layer_window(f"hypr-pop", Layer.Layer.OVERLAY, keyboard=True)
        Layer.set_anchor(self.win, Layer.Edge.TOP, True)
        if anchor_right:
            Layer.set_anchor(self.win, Layer.Edge.RIGHT, True)
            Layer.set_margin(self.win, Layer.Edge.RIGHT, 10)
        Layer.set_margin(self.win, Layer.Edge.TOP, GAP)
        self.win.connect("key-press-event", self.on_key)
        self.box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.box.get_style_context().add_class("panel")
        self.box.set_size_request(self.width, -1)
        self.win.add(self.box)

    def on_key(self, _w, ev):
        if ev.keyval == Gdk.KEY_Escape:
            self.manager.close()
        return False

    def clear(self):
        for child in self.box.get_children():
            self.box.remove(child)

    def header(self, title, extra=None):
        h = Gtk.Box(spacing=8)
        h.pack_start(label(title, "title"), True, True, 0)
        if extra:
            h.pack_start(extra, False, False, 0)
        self.box.pack_start(h, False, False, 2)

    def row(self, ico, text, active, on_click, meta=""):
        b = Gtk.Button()
        b.get_style_context().add_class("row")
        if active:
            b.get_style_context().add_class("active")
        inner = Gtk.Box(spacing=10)
        inner.pack_start(label(ico, "icon"), False, False, 0)
        name = label(text)
        name.set_ellipsize(3)  # END
        inner.pack_start(name, True, True, 0)
        if meta:
            inner.pack_start(label(meta, "label-small"), False, False, 0)
        b.add(inner)
        b.connect("clicked", lambda *_: on_click())
        self.box.pack_start(b, False, False, 0)

    def footer(self, text, cmd):
        self.box.pack_start(sep(), False, False, 2)
        b = Gtk.Button(label=text)
        b.get_style_context().add_class("link")
        b.get_child().set_xalign(0)
        b.connect("clicked", lambda *_: (self.manager.close(), spawn(*cmd)))
        self.box.pack_start(b, False, False, 0)

    def show(self):
        load_css()
        self.clear()
        self.build()
        self.box.show_all()
        self.win.show()
        self.win.present()

    def hide(self):
        self.win.hide()


AUDIO = importlib.machinery.SourceFileLoader("audio_switch", str(HOME / ".local/bin/audio-switch")).load_module()


class Sound(Popover):
    name = "audio"

    def device_icon(self, dev, kind):
        n = dev["name"]
        if n.startswith("bluez_") or "usb" in n:
            return icon("headphones")
        if "hdmi" in n:
            return icon("monitor")
        return icon("mic") if kind == "in" else icon("speaker")

    def build(self):
        out_k, in_k = AUDIO.KINDS["out"], AUDIO.KINDS["in"]
        vol_line = sh("wpctl", "get-volume", "@DEFAULT_AUDIO_SINK@").split()
        vol = round(float(vol_line[1]) * 100) if len(vol_line) > 1 else 0
        muted = "[MUTED]" in vol_line

        mute = Gtk.Button(label="Unmute" if muted else "Mute")
        mute.get_style_context().add_class("chip")
        if muted:
            mute.get_style_context().add_class("on")
        mute.connect("clicked", lambda *_: (sh("wpctl", "set-mute", "@DEFAULT_AUDIO_SINK@", "toggle"), self.refresh()))
        self.header("Sound", mute)

        line = Gtk.Box(spacing=8)
        scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 100, 1)
        scale.set_draw_value(False)
        scale.set_value(vol)
        val = label(str(vol), "mono", xalign=1)
        val.set_size_request(28, -1)

        def changed(s):
            v = int(s.get_value())
            val.set_text(str(v))
            sh("wpctl", "set-volume", "@DEFAULT_AUDIO_SINK@", f"{v}%")
            sh("pkill", "-RTMIN+10", "-x", "waybar")
        scale.connect("value-changed", changed)
        line.pack_start(scale, True, True, 0)
        line.pack_start(val, False, False, 0)
        self.box.pack_start(line, False, False, 0)

        for kind, k, title in (("out", out_k, "OUTPUT"), ("in", in_k, "INPUT")):
            self.box.pack_start(label(title, "label-small"), False, False, 4)
            current = sh("pactl", k["get"])
            for dev in AUDIO.devices(k):
                self.row(self.device_icon(dev, kind), AUDIO.label(dev, kind)[3:], dev["name"] == current,
                         lambda d=dev, kd=kind: self.pick(d, kd))
        self.footer("Sound settings…", ["pavucontrol"])

    def pick(self, dev, kind):
        k = AUDIO.KINDS[kind]
        sh("pactl", k["set"], dev["name"])
        for stream in json.loads(sh("pactl", "-f", "json", "list", k["streams"]) or "[]"):
            sh("pactl", k["move"], str(stream["index"]), dev["name"])
        sh("pkill", "-RTMIN+10", "-x", "waybar")
        self.refresh()

    def refresh(self):
        self.clear()
        self.build()
        self.box.show_all()


class Network(Popover):
    name = "network"

    def build(self):
        radio = sh("nmcli", "radio", "wifi")
        has_wifi = any(l.split(":")[1] == "wifi" for l in sh("nmcli", "-t", "-f", "DEVICE,TYPE", "device").splitlines()
                       if ":" in l)
        sw = None
        if has_wifi:
            sw = Gtk.Switch(active=radio == "enabled")
            sw.set_valign(Gtk.Align.CENTER)
            sw.connect("notify::active", lambda s, _p: (sh("nmcli", "radio", "wifi", "on" if s.get_active() else "off"),
                                                         GLib.timeout_add(800, self.refresh_once)))
        self.header("Network", sw)
        for line in sh("nmcli", "-t", "-f", "NAME,TYPE,DEVICE", "connection", "show", "--active").splitlines():
            parts = line.split(":")
            if len(parts) < 3 or parts[1] in ("loopback", "bridge") or parts[2].startswith(("docker", "br-", "veth", "lo")):
                continue
            ico = icon("wifi") if "wireless" in parts[1] else icon("lock") if "vpn" in parts[1] or "tun" in parts[1] else icon("ethernet-port")
            self.row(ico, parts[0], True, lambda: None)
        if has_wifi and radio == "enabled":
            self.box.pack_start(label("WI-FI", "label-small"), False, False, 4)
            seen = set()
            for line in sh("nmcli", "-t", "-f", "IN-USE,SSID,SIGNAL,SECURITY", "device", "wifi", "list").splitlines()[:8]:
                inuse, ssid, signal, sec = (line.split(":") + ["", "", "", ""])[:4]
                if not ssid or ssid in seen:
                    continue
                seen.add(ssid)
                meta = f"{signal}%" + (" · secured" if sec else "")
                self.row(icon("wifi"), ssid, inuse == "*", lambda s=ssid, secured=bool(sec): self.connect_to(s, secured), meta)
        self.footer("Network settings…", ["nm-connection-editor"])

    def connect_to(self, ssid, secured):
        known = ssid in sh("nmcli", "-t", "-f", "NAME", "connection", "show").splitlines()
        if secured and not known:
            self.manager.close()
            spawn("nm-connection-editor")
            return
        spawn("nmcli", "device", "wifi", "connect", ssid)
        GLib.timeout_add(2500, self.refresh_once)

    def refresh_once(self):
        if self.win.get_visible():
            self.clear()
            self.build()
            self.box.show_all()
        return False


class Bluetooth(Popover):
    """Paired devices with their battery (BlueZ's Battery Percentage, e.g. headphones), connected
    first; click connects or disconnects. Opened by right-clicking Bluetooth in Koyomi."""
    name = "bluetooth"
    ICONS = {"audio-headset": "headphones", "audio-headphones": "headphones", "audio-card": "speaker",
             "input-mouse": "mouse", "input-keyboard": "keyboard", "input-gaming": "gamepad-2",
             "phone": "smartphone", "computer": "laptop", "printer": "printer"}

    @staticmethod
    def devices():
        out = []
        for line in sh("bluetoothctl", "devices", "Paired").splitlines():
            parts = line.split(" ", 2)
            if len(parts) < 3 or parts[0] != "Device":
                continue
            info = dict(l.strip().split(": ", 1) for l in sh("bluetoothctl", "info", parts[1]).splitlines()
                        if ": " in l)
            battery = info.get("Battery Percentage", "")
            out.append({"mac": parts[1], "name": info.get("Alias") or parts[2], "icon": info.get("Icon", ""),
                        "connected": info.get("Connected") == "yes",
                        "battery": battery.rsplit("(", 1)[-1].rstrip(")") if "(" in battery else ""})
        return sorted(out, key=lambda d: (not d["connected"], d["name"].lower()))

    def build(self):
        on = "Powered: yes" in sh("bluetoothctl", "show")
        sw = Gtk.Switch(active=on)
        sw.set_valign(Gtk.Align.CENTER)
        sw.connect("notify::active", lambda s, _p: (spawn("bluetoothctl", "power", "on" if s.get_active() else "off"),
                                                     GLib.timeout_add(900, self.refresh_once)))
        self.header("Bluetooth", sw)
        if on:
            devices = self.devices()
            if not devices:
                self.box.pack_start(label("No paired devices", "muted"), False, False, 6)
            for d in devices:
                meta = (f"{d['battery']}%" if d["battery"] else "") if d["connected"] else ""
                self.row(icon(self.ICONS.get(d["icon"], "bluetooth")), d["name"], d["connected"],
                         lambda dev=d: self.toggle(dev), meta)
        self.footer("Bluetooth settings…", ["blueman-manager"])

    def toggle(self, dev):
        spawn("bluetoothctl", "disconnect" if dev["connected"] else "connect", dev["mac"])
        GLib.timeout_add(2500, self.refresh_once)

    def refresh_once(self):
        if self.win.get_visible():
            self.clear()
            self.build()
            self.box.show_all()
        return False


class ThemeManager(Popover):
    name = "theme"
    width = 720

    def __init__(self, manager):
        super().__init__(manager, anchor_right=False)
        Layer.set_margin(self.win, Layer.Edge.TOP, 90)

    def palettes(self):
        sys.path.insert(0, str(HOME / ".local/bin"))
        mod = importlib.machinery.SourceFileLoader("shoji_mod", SHOJI).load_module()
        return mod.PALETTES

    def preview(self, p):
        area = Gtk.DrawingArea()
        area.set_size_request(-1, 104)

        def draw(w, cr):
            W, H = w.get_allocated_width(), w.get_allocated_height()
            # rounded clip
            r = 8
            cr.new_sub_path()
            cr.arc(W - r, r, r, -math.pi / 2, 0)
            cr.arc(W - r, H - r, r, 0, math.pi / 2)
            cr.arc(r, H - r, r, math.pi / 2, math.pi)
            cr.arc(r, r, r, math.pi, 3 * math.pi / 2)
            cr.close_path()
            cr.clip()
            g = cairo.LinearGradient(0, 0, 0, H)
            g.add_color_stop_rgba(0, *rgba(p["sky"][0]))
            g.add_color_stop_rgba(1, *rgba(p["sky"][1]))
            cr.set_source(g)
            cr.paint()
            cr.set_source_rgba(*rgba(p["accent"], 0.9))
            cr.arc(W * 0.73, H * 0.36, H * 0.14, 0, 2 * math.pi)
            cr.fill()
            for pts, col in (([(0, .67), (.12, .56), (.25, .63), (.37, .48), (.5, .62), (.62, .52), (.75, .63), (.87, .54), (1, .62)], p["hills"][0]),
                             ([(0, .85), (.2, .77), (.42, .85), (.62, .77), (.83, .87), (1, .81)], p["hills"][1])):
                cr.move_to(0, H)
                for x, y in pts:
                    cr.line_to(x * W, y * H)
                cr.line_to(W, H)
                cr.close_path()
                cr.set_source_rgba(*rgba(col))
                cr.fill()
            # mini bar + window
            cr.set_source_rgba(*rgba(p["bg"], 0.72))
            cr.rectangle(6, 6, W - 12, 10)
            cr.fill()
            cr.set_source_rgba(*rgba(p["accent"]))
            cr.rectangle(10, 8, 6, 6)
            cr.fill()
            cr.set_source_rgba(*rgba(p["bg"], 0.92))
            cr.rectangle(6, 22, W * 0.45, H - 30)
            cr.fill()
            for i, (wf, col) in enumerate(((0.6, p["text"]), (0.8, p["muted"]), (0.4, p["accent"]))):
                cr.set_source_rgba(*rgba(col))
                cr.rectangle(13, 30 + i * 8, W * 0.45 * wf - 14, 3)
                cr.fill()
            return False
        area.connect("draw", draw)
        return area

    def build(self):
        cur = sh(SHOJI, "status")
        pals = self.palettes()
        head = Gtk.Box(spacing=12)
        seal = label("色", "seal", xalign=0.5)
        head.pack_start(seal, False, False, 0)
        tb = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        tb.pack_start(label("Theme", "title"), False, False, 0)
        tb.pack_start(label("Bar, panels, launcher, lock screen, terminal, GTK apps and wallpaper.", "muted"), False, False, 0)
        head.pack_start(tb, True, True, 0)
        close = Gtk.Button(label=icon("x"))
        close.get_style_context().add_class("nav")
        close.connect("clicked", lambda *_: self.manager.close())
        head.pack_start(close, False, False, 0)
        self.box.pack_start(head, False, False, 4)

        grid = Gtk.Grid(column_homogeneous=True, column_spacing=12, row_spacing=12)
        for i, (pid, p) in enumerate(pals.items()):
            b = Gtk.Button()
            b.get_style_context().add_class("card")
            if pid == cur:
                b.get_style_context().add_class("active")
            v = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
            v.pack_start(self.preview(p), False, False, 0)
            line = Gtk.Box(spacing=6)
            line.pack_start(label(f"{p['kanji']} {p['name']}", "name"), False, False, 0)
            line.pack_start(label(p["note"], "label-small"), False, False, 0)
            line.pack_end(label("in use" if pid == cur else ("dark" if p["dark"] else "light"), "label-small", xalign=1), False, False, 0)
            v.pack_start(line, False, False, 0)
            b.add(v)
            b.connect("clicked", lambda *_, n=pid: self.apply(n))
            grid.attach(b, i % 3, i // 3, 1, 1)
        self.box.pack_start(grid, False, False, 4)

        opts = Gtk.Box(spacing=10)
        pr = prefs()
        sw = Gtk.Switch(active=bool(pr.get("follow_sun")))
        sw.set_valign(Gtk.Align.CENTER)
        sw.connect("notify::active", lambda s, _p: (save_prefs(follow_sun=s.get_active()), self.manager.sun_tick(force=True)))
        opts.pack_start(sw, False, False, 0)
        opts.pack_start(label("Follow the sun: light palette 06:00–18:00, your dark one after", "muted"), False, False, 0)
        num = Gtk.Button(label="一二三 → 123" if pr.get("numerals", "kanji") == "kanji" else "123 → 一二三")
        num.get_style_context().add_class("chip")
        num.connect("clicked", lambda *_: self.toggle_numerals())
        opts.pack_end(num, False, False, 0)
        self.box.pack_start(opts, False, False, 4)
        season = (sh(SHOJI, "season").split() + ["", "", ""])[:3]
        seas = Gtk.Box(spacing=10)
        sw2 = Gtk.Switch(active=bool(pr.get("seasonal")))
        sw2.set_valign(Gtk.Align.CENTER)
        sw2.connect("notify::active", lambda s, _p: self.set_seasonal(s.get_active(), season[0]))
        seas.pack_start(sw2, False, False, 0)
        seas.pack_start(label(f"Seasonal accent: 紅梅 spring · 青竹 summer · 紅葉 autumn · 白群 winter "
                              f"(now {season[1]})", "muted"), False, False, 0)
        self.box.pack_start(seas, False, False, 0)
        self.box.pack_start(label(f"Same from a terminal: shoji apply {cur} · shoji list · Super+Shift+T", "mono"), False, False, 2)

    def apply(self, name):
        p = self.palettes()[name]
        if p["dark"]:
            save_prefs(dark=name)
        subprocess.run([SHOJI, "apply", name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.show()

    def set_seasonal(self, on, season_id):
        save_prefs(seasonal=on, season=season_id)
        subprocess.run([SHOJI, "apply"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.show()

    def toggle_numerals(self):
        save_prefs(numerals="arabic" if prefs().get("numerals", "kanji") == "kanji" else "kanji")
        subprocess.run([sys.executable, str(HOME / ".config/shoji/gen_waybar.py")], stdout=subprocess.DEVNULL)
        sh("pkill", "-SIGUSR2", "-x", "waybar")
        self.show()


class Battery(Popover):
    """Battery + power mode (power-profiles-daemon). Also useful on a desktop for the power mode."""
    name = "battery"
    width = 300
    MODES = (("power-saver", "Saver", "Lower performance, longer battery. The screen dims sooner."),
             ("balanced", "Balanced", "Full speed when needed, quiet when idle."),
             ("performance", "Performance", "Fans may spin up. Best on power."))

    def battery(self):
        bats = sorted(Path("/sys/class/power_supply").glob("BAT*"))
        if not bats:
            return None
        b = bats[0]
        cap = int((b / "capacity").read_text().strip())
        status = (b / "status").read_text().strip()
        info = sh("upower", "-i", sh("upower", "-e").split("\n")[0]) if sh("which", "upower") else ""
        when = ""
        for line in info.splitlines():
            if "time to empty" in line or "time to full" in line:
                when = line.split(":", 1)[1].strip()
        return cap, status, when

    def build(self):
        t = theme()["tokens"]
        bat = self.battery()
        top = Gtk.Box(spacing=14)
        ring = Gtk.DrawingArea()
        ring.set_size_request(64, 64)
        cap = bat[0] if bat else 0
        charging = bool(bat) and bat[1] in ("Charging", "Full")
        low = bool(bat) and not charging and cap <= 20
        col = rgba(t["ok"] if charging else t["alert"] if low else t["text"])

        def draw(_w, cr):
            enso(cr, 32, 32, 25, cap / 100, col, 5, track=rgba(t["text"], 0.12))
            lay = ring.create_pango_layout("")
            lay.set_markup(f'<span font_family="Kaisei Opti" weight="bold" size="13pt" foreground="{t["text"]}">'
                           f'{cap if bat else "–"}</span>', -1)
            w, h = lay.get_pixel_size()
            cr.move_to(32 - w / 2, 32 - h / 2)
            PangoCairo.show_layout(cr, lay)
            return False
        ring.connect("draw", draw)
        top.pack_start(ring, False, False, 0)
        words = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        words.set_valign(Gtk.Align.CENTER)
        if bat:
            head = ("Fully charged" if bat[1] == "Full" else "Charging") if charging else \
                   ("Battery low" if low else "On battery")
            detail = (f"{'Full' if charging else 'Empty'} in about {bat[2]}" if bat[2] else bat[1].lower())
        else:
            head, detail = "No battery", "Desktop on mains power"
        words.pack_start(label(head, "title"), False, False, 0)
        words.pack_start(label(detail, "muted"), False, False, 0)
        top.pack_start(words, True, True, 0)
        self.box.pack_start(top, False, False, 2)

        current = sh("powerprofilesctl", "get")
        if current:
            self.box.pack_start(label("POWER MODE", "label-small"), False, False, 4)
            seg = Gtk.Box(spacing=4, homogeneous=True)
            for mode, name, _hint in self.MODES:
                b = Gtk.Button(label=name)
                b.get_style_context().add_class("chip")
                if mode == current:
                    b.get_style_context().add_class("on")
                b.connect("clicked", lambda _b, m=mode: (sh("powerprofilesctl", "set", m), self.refresh()))
                seg.pack_start(b, True, True, 0)
            self.box.pack_start(seg, False, False, 0)
            hint = next((h for m, _n, h in self.MODES if m == current), "")
            hl = label(hint, "muted")
            hl.set_line_wrap(True)
            self.box.pack_start(hl, False, False, 2)
        self.footer("Power settings…", ["gnome-control-center", "power"])

    def refresh(self):
        self.clear()
        self.build()
        self.box.show_all()


def app_shortcuts():
    """desktop id -> "Super K" for every hyprland.lua key that starts an app with gtk-launch."""
    found = {}
    try:
        lines = (HOME / ".cache/hypr-actions.tsv").read_text().splitlines()
    except OSError:
        return found
    for line in lines:
        parts = line.split("\t", 4)
        if len(parts) == 5 and parts[3] == "cmd" and "gtk-launch " in parts[4]:
            app_id = parts[4].split("gtk-launch ", 1)[1].split()[0].removesuffix(".desktop")
            found.setdefault(app_id, " ".join(Keys.NAMES.get(k, k) for k in parts[0].split(" + ")))
    return found


class Launcher(Popover):
    """探 Search apps: frequent apps first, typed text matches name, generic name, keywords."""
    name = "launcher"
    width = 560
    ROWS = 8
    STATE = HOME / ".local/state/shoji-launcher.json"  # ~/.local/state/shoji is the palette file

    def __init__(self, manager):
        super().__init__(manager, anchor_right=False)
        Layer.set_margin(self.win, Layer.Edge.TOP, 120)
        Layer.set_keyboard_mode(self.win, Layer.KeyboardMode.EXCLUSIVE)
        self.entry = Gtk.Entry(placeholder_text="Search apps")
        self.entry.get_style_context().add_class("search")
        self.entry.connect("changed", lambda *_: self.refilter())
        self.entry.connect("activate", lambda *_: self.launch_selected())
        self.listbox = Gtk.ListBox()
        self.listbox.set_selection_mode(Gtk.SelectionMode.BROWSE)
        self.listbox.set_activate_on_single_click(True)
        self.listbox.connect("row-activated", lambda _l, row: self.launch(row.app))
        self.listbox.connect("row-selected", self.on_selected)
        self.subtitle = None
        self.listbox.set_filter_func(lambda row: row.score > 0)
        self.listbox.set_sort_func(lambda a, b: (b.score > a.score) - (b.score < a.score) or
                                   (a.app.get_display_name().lower() > b.app.get_display_name().lower()) - 
                                   (a.app.get_display_name().lower() < b.app.get_display_name().lower()))
        self.scroll = Gtk.ScrolledWindow()
        self.scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.scroll.set_size_request(-1, self.ROWS * 44)
        self.scroll.add(self.listbox)
        self.glide = Glide(self.scroll)
        self.section = label("", "label-small")
        self.empty = label("", "muted")
        self.rows = []

    def keep(self):
        """Widgets made once and packed again on every show."""
        return (self.entry, self.section, self.scroll, self.empty)

    def clear(self):
        # Lift them out first: destroying the old box would destroy them too, and a destroyed entry
        # keeps showing typed text but no longer emits "changed" (search) or "activate" (Enter).
        for w in self.keep():
            parent = w.get_parent()
            if parent:
                parent.remove(w)
        super().clear()

    def counts(self):
        try:
            return json.loads(self.STATE.read_text())
        except (OSError, ValueError):
            return {}

    def build(self):
        head = Gtk.Box(spacing=10)
        head.get_style_context().add_class("searchbar")
        head.pack_start(label(icon("search"), "icon", xalign=0.5), False, False, 0)
        head.pack_start(self.entry, True, True, 0)
        esc = label("Esc", "kbd")
        esc.set_valign(Gtk.Align.CENTER)
        head.pack_start(esc, False, False, 0)
        self.box.pack_start(head, False, False, 0)
        self.box.pack_start(self.section, False, False, 2)
        self.box.pack_start(self.scroll, False, False, 0)
        self.box.pack_start(self.empty, False, False, 0)
        self.box.pack_start(label("↑↓ move · ↵ open or focus · Shift+↵ new window", "mono"), False, False, 2)
        self.load_apps()

    def load_apps(self):
        for row in self.listbox.get_children():
            self.listbox.remove(row)
        self.rows = []
        counts = self.counts()
        shortcuts = app_shortcuts()
        for app in Gio.AppInfo.get_all():
            if not app.should_show():
                continue
            row = Gtk.ListBoxRow()
            row.get_style_context().add_class("app-row")
            row.app, row.uses = app, counts.get(app.get_id() or "", 0)
            line = Gtk.Box(spacing=12)
            img = Gtk.Image.new_from_gicon(app.get_icon() or Gio.ThemedIcon.new("application-x-executable"),
                                           Gtk.IconSize.DND)
            img.set_pixel_size(24)
            line.pack_start(img, False, False, 0)
            text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            text.set_valign(Gtk.Align.CENTER)
            text.pack_start(label(app.get_display_name(), "app-name"), False, False, 0)
            desc = app.get_description() or (app.get_generic_name() if hasattr(app, "get_generic_name") else "") or ""
            row.subtitle = None
            if desc:  # shown under the selected row only (on_selected); the row keeps its height
                d = label(desc, "desc")
                d.set_ellipsize(3)
                d.set_no_show_all(True)
                text.pack_start(d, False, False, 0)
                row.subtitle = d
            line.pack_start(text, True, True, 0)
            hint = shortcuts.get((app.get_id() or "").removesuffix(".desktop"))
            if hint:
                k = label(hint, "kbd")
                k.set_valign(Gtk.Align.CENTER)
                line.pack_start(k, False, False, 0)
            row.add(line)
            keys = [app.get_display_name(), app.get_name() or ""]
            if isinstance(app, Gio.DesktopAppInfo):
                keys += [app.get_generic_name() or "", " ".join(app.get_keywords() or []),
                         (app.get_executable() or "").split("/")[-1]]
            row.keys = [k.lower() for k in keys if k]
            row.score = 1
            self.listbox.add(row)
            self.rows.append(row)

    def on_selected(self, _listbox, row):
        if self.subtitle is not None:
            self.subtitle.hide()
        self.subtitle = getattr(row, "subtitle", None) if row else None
        if self.subtitle is not None:
            self.subtitle.show()

    @staticmethod
    def match(q, keys):
        best = 0
        for i, k in enumerate(keys):
            w = 1.0 if i < 2 else 0.6  # the name counts more than keywords
            if k.startswith(q):
                best = max(best, 100 * w)
            elif any(part.startswith(q) for part in k.replace("-", " ").split()):
                best = max(best, 80 * w)
            elif q in k:
                best = max(best, 60 * w)
            elif i < 2 and len(q) >= 3:  # loose letters-in-order only on the app name
                it = iter(k)
                if all(ch in it for ch in q):
                    best = max(best, 25 * w)
        return best

    def refilter(self):
        q = self.entry.get_text().strip().lower()
        for row in self.rows:
            base = self.match(q, row.keys) if q else 1
            row.score = base + min(row.uses, 40) * (0.5 if q else 1) if base else 0
        self.listbox.invalidate_filter()
        self.listbox.invalidate_sort()
        visible = [r for r in self.rows if r.score > 0]
        self.section.set_text("FREQUENT · ALL APPS" if not q else f"RESULTS · {len(visible)}")
        self.empty.set_text(f"No app matches “{q}”." if q and not visible else "")
        self.empty.set_visible(bool(q and not visible))
        if visible:
            first = min(visible, key=lambda r: (-r.score, r.app.get_display_name().lower()))
            self.listbox.select_row(first)
            self.glide.jump(0)

    def on_key(self, w, ev):
        if ev.keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter) and ev.state & Gdk.ModifierType.SHIFT_MASK:
            self.launch_selected(new_window=True)
            return True
        if ev.keyval in (Gdk.KEY_Down, Gdk.KEY_Up, Gdk.KEY_Tab, Gdk.KEY_ISO_Left_Tab):
            down = ev.keyval in (Gdk.KEY_Down, Gdk.KEY_Tab)
            visible = sorted((r for r in self.rows if r.score > 0), key=lambda r: r.get_index())
            cur = self.listbox.get_selected_row()
            if visible:
                i = visible.index(cur) if cur in visible else -1
                nxt = visible[max(0, min(len(visible) - 1, i + (1 if down else -1)))]
                self.listbox.select_row(nxt)
                a = nxt.get_allocation()
                adj = self.scroll.get_vadjustment()
                view = self.glide.target if self.glide.tick else adj.get_value()
                if a.y < view:
                    self.glide.to(a.y)
                elif a.y + a.height > view + adj.get_page_size():
                    self.glide.to(a.y + a.height - adj.get_page_size())
            return True
        return super().on_key(w, ev)

    def launch_selected(self, new_window=False):
        row = self.listbox.get_selected_row()
        if row and row.score > 0:
            self.launch(row.app, new_window)

    @staticmethod
    def window_for(app):
        """An open window of this app (Hyprland client), or None."""
        names = {(app.get_id() or "").removesuffix(".desktop").lower()}
        names.add(next(iter(names)).split(".")[-1])
        if isinstance(app, Gio.DesktopAppInfo):
            names.add((app.get_startup_wm_class() or "").lower())
            names.add(Path(app.get_executable() or "").name.lower())
        names.discard("")
        try:
            clients = json.loads(sh("hyprctl", "clients", "-j") or "[]")
        except ValueError:
            return None
        hits = [c for c in clients if {c.get("class", "").lower(), c.get("initialClass", "").lower()} & names]
        return min(hits, key=lambda c: c.get("focusHistoryID", 99)) if hits else None

    def launch(self, app, new_window=False):
        """Enter focuses the app if it is already open; Shift+Enter always opens a new one."""
        self.manager.close()
        win = None if new_window else self.window_for(app)
        if win:
            sh("hyprctl", "dispatch", f'hl.dsp.focus({{ window = "address:{win["address"]}" }})')
        else:
            ctx = Gdk.Display.get_default().get_app_launch_context()
            try:
                app.launch([], ctx)
            except GLib.Error as e:
                print("launch:", e, file=sys.stderr, flush=True)
                return
        # usage counts only rank the list; they must never stop an app from opening
        try:
            counts = self.counts()
            key = app.get_id() or app.get_name()
            counts[key] = counts.get(key, 0) + 1
            self.STATE.parent.mkdir(parents=True, exist_ok=True)
            self.STATE.write_text(json.dumps(counts))
        except OSError as e:
            print("launcher: could not save usage:", e, file=sys.stderr, flush=True)

    def show(self):
        load_css()
        self.clear()
        self.build()
        self.entry.set_text("")
        self.refilter()
        self.box.show_all()
        self.empty.set_visible(False)
        self.win.show()
        self.win.present()
        self.entry.grab_focus()


class Keys(Launcher):
    """鍵 Every shortcut from hyprland.lua on one sheet, in columns by group; typing filters a list."""
    name = "keys"
    width = 1480
    COLUMNS = 4
    ROWS = 11
    TSV = HOME / ".cache/hypr-actions.tsv"  # written by hyprland.lua at each (re)load
    ORDER = ["Apps", "Windows", "Workspaces", "System", "Tools", "Media", "Help"]
    NAMES = {"SUPER": "Super", "SHIFT": "Shift", "ALT": "Alt", "CTRL": "Ctrl", "slash": "/",
             "Return": "Enter", "Escape": "Esc", "Print": "PrtSc", "period": ".", "Space": "Space",
             "XF86AudioRaiseVolume": "Vol +", "XF86AudioLowerVolume": "Vol −", "XF86AudioMute": "Mute",
             "XF86AudioMicMute": "Mic mute", "XF86AudioPlay": "Play", "XF86AudioNext": "Next",
             "XF86AudioPrev": "Prev", "left": "←", "right": "→", "up": "↑", "down": "↓",
             "bracketleft": "[", "bracketright": "]"}
    # rows that differ only by one key collapse into one line (keys, description)
    FOLD = {"Go to workspace": "1 … 0", "Move window to workspace": "1 … 0",
            "Focus window": "←↑→↓", "Move / swap window": "←↑→↓", "Move window": "←↑→↓"}

    def __init__(self, manager):
        super().__init__(manager)
        self.entry.set_placeholder_text("Search shortcuts")
        self.listbox.set_sort_func(lambda a, b: (b.score > a.score) - (b.score < a.score) or a.order - b.order)
        self.listbox.set_header_func(self.head)
        self.sheet = Gtk.Box(spacing=18, homogeneous=True)
        self.info = label("", "mono")

    def keep(self):
        return super().keep() + (self.sheet, self.info)

    def lines(self):
        try:
            return self.TSV.read_text().splitlines()
        except OSError:
            return self.from_binds()

    def actions(self):
        rows, folded = [], set()
        for line in self.lines():
            parts = line.split("\t", 4)
            if len(parts) < 5:
                continue
            keys, group, desc, kind, payload = parts
            caps = [self.NAMES.get(k, k) for k in keys.split(" + ")]
            for stem, last in self.FOLD.items():
                tail = desc[len(stem):].strip()
                if desc.startswith(stem) and (tail.isdigit() or tail in ("left", "right", "up", "down")):
                    if stem in folded:
                        caps = None
                    else:
                        folded.add(stem)
                        caps, desc, kind = caps[:-1] + [last], stem, ""
                    break
            if caps:
                rows.append(dict(caps=caps, group=group, desc=desc, kind=kind, payload=payload))
        rank = {g: i for i, g in enumerate(self.ORDER)}
        rows.sort(key=lambda r: rank.get(r["group"], len(self.ORDER)))
        return rows

    @staticmethod
    def from_binds():
        """Without the hyprland.lua table: every bind that has a description ("Group: what it does")."""
        try:
            binds = json.loads(sh("hyprctl", "binds", "-j") or "[]")
        except ValueError:
            return []
        lines = []
        for bnd in binds:
            if not bnd.get("has_description") or bnd.get("mouse") or bnd["key"].startswith("mouse"):
                continue
            mods = [m for bit, m in ((64, "SUPER"), (4, "CTRL"), (8, "ALT"), (1, "SHIFT")) if bnd["modmask"] & bit]
            group, _, desc = bnd["description"].rpartition(": ")
            kind = "cmd" if bnd["dispatcher"] == "exec" else ""
            lines.append("\t".join([" + ".join(mods + [bnd["key"]]), group or "Other", desc, kind, bnd["arg"]]))
        return lines

    def build(self):
        head = Gtk.Box(spacing=10)
        head.get_style_context().add_class("searchbar")
        head.pack_start(label(icon("keyboard"), "icon", xalign=0.5), False, False, 0)
        head.pack_start(self.entry, True, True, 0)
        esc = label("Esc", "kbd")
        esc.set_valign(Gtk.Align.CENTER)
        head.pack_start(esc, False, False, 0)
        self.box.pack_start(head, False, False, 0)
        self.box.pack_start(self.sheet, False, False, 6)
        self.box.pack_start(self.scroll, False, False, 0)
        self.box.pack_start(self.empty, False, False, 0)
        self.box.pack_start(self.info, False, False, 2)
        self.load_apps()
        self.fill_sheet()

    def fill_sheet(self):
        """Groups go, in order, into whichever column is shortest so far."""
        for c in self.sheet.get_children():
            self.sheet.remove(c)
        groups = {}
        for a in self.actions():
            groups.setdefault(a["group"], []).append(a)
        cols = [Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1) for _ in range(self.COLUMNS)]
        sizes = [0] * self.COLUMNS
        # caps share a width per column, so every description in a column starts at one edge
        widths = [Gtk.SizeGroup(mode=Gtk.SizeGroupMode.HORIZONTAL) for _ in range(self.COLUMNS)]
        for group, acts in groups.items():
            i = sizes.index(min(sizes))
            sizes[i] += len(acts) + 2
            cols[i].pack_start(label(group.upper(), "key-head"), False, False, 0)
            for a in acts:
                b = Gtk.Button()
                b.get_style_context().add_class("sheet-row")
                line = Gtk.Box(spacing=10)
                caps = Gtk.Box(spacing=2)
                widths[i].add_widget(caps)
                for c in a["caps"]:
                    cap = label(c, "cap", xalign=0.5)
                    cap.set_valign(Gtk.Align.CENTER)
                    caps.pack_start(cap, False, False, 0)
                line.pack_start(caps, False, False, 0)
                d = label(a["desc"], "desc")
                d.set_ellipsize(3)
                line.pack_start(d, True, True, 0)
                b.add(line)
                b.set_sensitive(bool(a["kind"]))
                b.set_tooltip_text(a["desc"])
                b.connect("clicked", lambda _b, a=a: self.launch(a))
                cols[i].pack_start(b, False, False, 0)
        for c in cols:
            self.sheet.pack_start(c, True, True, 0)

    def apply_mode(self):
        searching = bool(self.entry.get_text().strip())
        self.sheet.set_visible(not searching)
        self.scroll.set_visible(searching)
        if not searching:
            self.empty.set_visible(False)
        self.info.set_text("↑↓ move · ↵ run it · Esc" if searching
                           else "Click one to run it · type to search")

    def load_apps(self):
        for row in self.listbox.get_children():
            self.listbox.remove(row)
        self.rows = []
        for i, a in enumerate(self.actions()):
            row = Gtk.ListBoxRow()
            row.get_style_context().add_class("key-row")
            row.app, row.order, row.score = a, i, 1
            line = Gtk.Box(spacing=12)
            caps = Gtk.Box(spacing=4)
            caps.set_size_request(170, -1)
            for c in a["caps"]:
                cap = label(c, "cap", xalign=0.5)
                cap.set_valign(Gtk.Align.CENTER)
                caps.pack_start(cap, False, False, 0)
            line.pack_start(caps, False, False, 0)
            d = label(a["desc"], "desc")
            d.set_ellipsize(3)
            line.pack_start(d, True, True, 0)
            row.group = label(a["group"], "group")
            row.group.set_no_show_all(True)  # only search results name their group
            line.pack_start(row.group, False, False, 0)
            row.add(line)
            row.keys = [a["desc"].lower(), " ".join(a["caps"]).lower(), a["group"].lower()]
            self.listbox.add(row)
            self.rows.append(row)

    def head(self, row, before):
        """Group titles only while browsing; search results are one ranked list."""
        if self.entry.get_text().strip() or (before and before.app["group"] == row.app["group"]):
            row.set_header(None)
            return
        row.set_header(label(row.app["group"].upper(), "key-head"))

    def refilter(self):
        q = self.entry.get_text().strip().lower()
        for row in self.rows:
            row.score = (self.match(q, row.keys) if q else 1) or 0
            row.group.set_visible(bool(q))
        self.listbox.invalidate_filter()
        self.listbox.invalidate_sort()
        self.listbox.invalidate_headers()
        visible = [r for r in self.rows if r.score > 0]
        self.empty.set_text(f"No shortcut matches “{q}”." if q and not visible else "")
        self.empty.set_visible(bool(q and not visible))
        if visible:
            self.listbox.select_row(min(visible, key=lambda r: (-r.score, r.order)))
            self.glide.jump(0)
        if self.sheet.get_parent():
            self.apply_mode()

    def show(self):
        try:  # hyprland.lua rewrites the TSV on every reload: pick up new or changed binds
            mtime = self.TSV.stat().st_mtime
        except OSError:
            mtime = None
        if mtime != getattr(self, "tsv_mtime", None) or mtime is None:
            self.load_apps()
            self.fill_sheet()
        self.tsv_mtime = mtime
        # 1480 px fits a 2560 screen; on a narrower or scaled one, fit the screen (long lines ellipsize)
        fit = min(self.width, Calendar.focused_width() - 32)
        self.box.set_size_request(fit, -1)
        self.win.resize(fit, 1)
        super().show()
        self.apply_mode()

    def launch(self, a, new_window=False):
        if not a["kind"]:
            return  # a folded row (1 … 0, arrows) needs the real key
        self.manager.close()
        if a["kind"] == "cmd":
            subprocess.Popen(["setsid", "-f", "sh", "-c", a["payload"]])
        else:
            sh("hyprctl", "dispatch", a["payload"])


class Clipboard(Popover):
    """写 Clipboard history (cliphist): newest first, type to search, Enter or a click puts an entry
    back on the clipboard. Each row has a delete button (or press Delete on the selected one);
    "Clear all" asks once more before it wipes the history. Images show as small thumbnails."""
    name = "clipboard"
    width = 560
    ROWS = 8
    THUMBS = 24  # decode at most this many images per open

    def __init__(self, manager):
        super().__init__(manager, anchor_right=False)
        Layer.set_margin(self.win, Layer.Edge.TOP, 120)
        Layer.set_keyboard_mode(self.win, Layer.KeyboardMode.EXCLUSIVE)
        self.confirm = 0

    def entries(self):
        return [line for line in sh("cliphist", "list").splitlines() if "\t" in line]

    def build(self):
        self.entry = Gtk.Entry(placeholder_text="Search clipboard history")
        self.entry.get_style_context().add_class("search")
        self.entry.connect("changed", lambda *_: self.listbox.invalidate_filter())
        self.entry.connect("activate", lambda *_: self.paste(self.listbox.get_selected_row()))
        bar = Gtk.Box(spacing=8)
        bar.get_style_context().add_class("searchbar")
        bar.pack_start(label(icon("clipboard"), "icon"), False, False, 0)
        bar.pack_start(self.entry, True, True, 0)
        self.wipe = Gtk.Button(label="Clear all")
        self.wipe.get_style_context().add_class("chip")
        self.wipe.set_valign(Gtk.Align.CENTER)
        self.wipe.connect("clicked", lambda *_: self.clear_all())
        bar.pack_start(self.wipe, False, False, 0)
        self.box.pack_start(bar, False, False, 0)
        self.listbox = Gtk.ListBox()
        self.listbox.set_selection_mode(Gtk.SelectionMode.BROWSE)
        self.listbox.set_activate_on_single_click(True)
        self.listbox.connect("row-activated", lambda _l, row: self.paste(row))
        self.listbox.set_filter_func(self.matches)
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_size_request(-1, self.ROWS * 44)
        scroll.add(self.listbox)
        self.glide = Glide(scroll)
        self.box.pack_start(scroll, False, False, 0)
        lines = self.entries()
        if not lines:
            self.box.pack_start(label("Nothing copied yet", "muted"), False, False, 8)
        thumbs = 0
        for line in lines:
            ident, preview = line.split("\t", 1)
            row = Gtk.ListBoxRow()
            row.get_style_context().add_class("app-row")
            row.line, row.text = line, preview.lower()
            box = Gtk.Box(spacing=10)
            image = preview.startswith("[[ binary data")
            if image and thumbs < self.THUMBS:
                thumbs += 1
                pix = self.thumbnail(ident)
                box.pack_start(Gtk.Image.new_from_pixbuf(pix) if pix else label(icon("image"), "icon"), False, False, 0)
            else:
                box.pack_start(label(icon("image" if image else "type"), "icon"), False, False, 0)
            text = label(self.describe(preview) if image else " ".join(preview.split())[:200])
            text.set_ellipsize(Pango.EllipsizeMode.END)
            box.pack_start(text, True, True, 0)
            trash = Gtk.Button(label=icon("trash-2"))
            trash.get_style_context().add_class("nav")
            trash.set_tooltip_text("Delete from history")
            trash.connect("clicked", lambda _b, r=row: self.delete(r))
            box.pack_start(trash, False, False, 0)
            row.add(box)
            self.listbox.add(row)
        first = self.listbox.get_row_at_index(0)
        if first:
            self.listbox.select_row(first)
        self.box.pack_start(label("↑↓ move · ↵ copy · Del delete · Esc close", "mono"), False, False, 2)

    @staticmethod
    def describe(preview):
        """"[[ binary data 48 KiB png 1920x1080 ]]" -> "Image · png · 1920×1080 · 48 KiB"."""
        words = preview.strip("[] ").split()[2:]  # 48 KiB png 1920x1080
        if len(words) >= 4:
            return f"Image · {words[2]} · {words[3].replace('x', '×')} · {words[0]} {words[1]}"
        return "Image"

    @staticmethod
    def thumbnail(ident):
        try:
            data = subprocess.run(["cliphist", "decode", ident], capture_output=True, timeout=2).stdout
            loader = GdkPixbuf.PixbufLoader()
            loader.write(data)
            loader.close()
            pix = loader.get_pixbuf()
            scale = 28 / max(pix.get_width(), pix.get_height())
            return pix.scale_simple(max(1, round(pix.get_width() * scale)), max(1, round(pix.get_height() * scale)),
                                    GdkPixbuf.InterpType.BILINEAR)
        except (GLib.Error, OSError, subprocess.TimeoutExpired, ZeroDivisionError):
            return None

    def matches(self, row):
        q = self.entry.get_text().strip().lower()
        return not q or all(word in row.text for word in q.split())

    def paste(self, row):
        if row is None:
            return
        ident = row.line.split("\t", 1)[0]
        subprocess.Popen(["sh", "-c", f"cliphist decode {int(ident)} | wl-copy"], start_new_session=True)
        self.manager.close()

    def delete(self, row):
        subprocess.run(["cliphist", "delete"], input=row.line, text=True, timeout=3)
        index = row.get_index()
        self.listbox.remove(row)
        nxt = self.listbox.get_row_at_index(index) or self.listbox.get_row_at_index(index - 1)
        if nxt:
            self.listbox.select_row(nxt)

    def clear_all(self):
        if not self.confirm:  # a second click within 3 s really wipes
            self.wipe.set_label("Sure? Clear")
            self.wipe.get_style_context().add_class("on")
            self.confirm = GLib.timeout_add(3000, self.unconfirm)
            return
        GLib.source_remove(self.confirm)
        self.confirm = 0
        sh("cliphist", "wipe")
        self.manager.close()

    def unconfirm(self):
        self.confirm = 0
        self.wipe.set_label("Clear all")
        self.wipe.get_style_context().remove_class("on")
        return False

    def on_key(self, w, ev):
        rows = [r for r in self.listbox.get_children() if r.get_child_visible() and self.matches(r)]
        cur = self.listbox.get_selected_row()
        if ev.keyval == Gdk.KEY_Delete and cur is not None:
            self.delete(cur)
            return True
        if ev.keyval in (Gdk.KEY_Down, Gdk.KEY_Up) and rows:
            i = rows.index(cur) if cur in rows else -1
            nxt = rows[max(0, min(len(rows) - 1, i + (1 if ev.keyval == Gdk.KEY_Down else -1)))]
            self.listbox.select_row(nxt)
            a, adj = nxt.get_allocation(), self.glide.adj
            view = self.glide.target if self.glide.tick else adj.get_value()
            if a.y < view:
                self.glide.to(a.y)
            elif a.y + a.height > view + adj.get_page_size():
                self.glide.to(a.y + a.height - adj.get_page_size())
            return True
        return super().on_key(w, ev)

    def show(self):
        if self.confirm:
            GLib.source_remove(self.confirm)
            self.confirm = 0
        super().show()
        self.entry.grab_focus()


class Media(Popover):
    """Now playing, opened from the bar's cover: big cover on a wash of its own colour (the way
    Spotify tints its player), title, artist, a seek bar and prev / play / next."""
    name = "media"
    ART = 292  # popover width minus the panel padding

    def __init__(self, manager):
        super().__init__(manager)
        self.tint = Gtk.CssProvider()
        self.box.get_style_context().add_provider(self.tint, Gtk.STYLE_PROVIDER_PRIORITY_USER + 1)
        self.box.get_style_context().add_class("media")
        self.ticking = False

    @staticmethod
    def info():
        try:
            return json.loads(sh(str(HOME / ".local/bin/shoji-media"), "info") or "{}")
        except ValueError:
            return {}

    @staticmethod
    def cover(url):
        if url.startswith("file://"):
            path = Path(GLib.filename_from_uri(url)[0])
        else:
            import hashlib
            path = HOME / ".cache/shoji/covers" / hashlib.sha1(url.encode()).hexdigest()
        try:
            return GdkPixbuf.Pixbuf.new_from_file(str(path))
        except (GLib.Error, TypeError):
            return None

    @staticmethod
    def wash(pix):
        """The cover's most vivid colour (24x24 average weighted by saturation x brightness), made
        vivid enough to read as a colour, like Spotify does with dull covers."""
        import colorsys
        small = pix.scale_simple(24, 24, GdkPixbuf.InterpType.BILINEAR)
        data, n, stride = small.get_pixels(), small.get_n_channels(), small.get_rowstride()
        acc, total = [0.0, 0.0, 0.0], 0.0
        for y in range(24):
            for x in range(24):
                r, g, b = (data[y * stride + x * n + i] / 255 for i in range(3))
                hi, lo = max(r, g, b), min(r, g, b)
                w = (hi - lo) * hi + 0.02
                acc = [acc[0] + r * w, acc[1] + g * w, acc[2] + b * w]
                total += w
        h, sat, val = colorsys.rgb_to_hsv(*(c / total for c in acc))
        sat = sat if sat < 0.12 else max(sat, 0.45)  # a grey cover stays grey; a dull colour gets vivid
        r, g, b = colorsys.hsv_to_rgb(h, sat, min(max(val, 0.55), 0.8))
        return "#%02x%02x%02x" % (round(r * 255), round(g * 255), round(b * 255))

    def build(self):
        t = self.info()
        if t.get("status") not in ("Playing", "Paused"):
            self.tint.load_from_data(b"")
            self.header("Media")
            self.box.pack_start(label("Nothing playing", "muted"), False, False, 6)
            return
        self.player = t.get("player", "")
        pix = self.cover(t.get("mpris:artUrl", ""))
        wash = self.wash(pix) if pix else None
        self.tint.load_from_data(
            (f".media {{ background-image: linear-gradient(to bottom, alpha({wash}, 0.5), alpha({wash}, 0.04) 80%); }}"
             if wash else "").encode())
        if pix:
            w, h = pix.get_width(), pix.get_height()
            square = 0.85 < w / h < 1.15
            if square:  # album art
                side = min(w, h)
                pix = pix.new_subpixbuf((w - side) // 2, (h - side) // 2, side, side)
                w = h = side
            size = (self.ART, self.ART if square else round(self.ART * h / w))
            if w >= self.ART * 0.8:  # big enough (Spotify sends 640 px): fill the frame
                front, back = pix.scale_simple(*size, GdkPixbuf.InterpType.HYPER), None
            else:  # a browser thumbnail (Chrome hands over ~150 px): sharp at its own size,
                # over a blurred copy of itself instead of one blown-up, soft image
                front = pix
                back = pix.scale_simple(12, max(1, round(12 * h / w)), GdkPixbuf.InterpType.BILINEAR) \
                          .scale_simple(*size, GdkPixbuf.InterpType.BILINEAR)
            art = Gtk.DrawingArea()
            art.set_size_request(*size)
            art.connect("draw", self.draw_art, front, back)
            self.box.pack_start(art, False, False, 0)
        title = label(t.get("title") or "Unknown", "media-title")
        title.set_ellipsize(Pango.EllipsizeMode.END)
        self.box.pack_start(title, False, False, 0)
        if t.get("artist"):
            artist = label(t["artist"], "muted")
            artist.set_ellipsize(Pango.EllipsizeMode.END)
            self.box.pack_start(artist, False, False, 0)
        length = int(t.get("mpris:length") or 0) / 1e6
        if length > 0:
            self.seek = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, length, 1)
            self.seek.set_draw_value(False)
            self.seek.set_value(float(t.get("position") or 0))
            self.seek.connect("change-value", lambda _s, _scroll, v: (sh("playerctl", "-p", self.player, "position", str(max(0, v))),
                                                                      self.anchor(max(0, v)), False)[-1])
            # the bar runs on the frame clock between the once-a-second reads (no 1 s steps)
            self.anchor(float(t.get("position") or 0))
            self.seek.add_tick_callback(self.glide_seek)
            self.box.pack_start(self.seek, False, False, 4)
            times = Gtk.Box()
            self.pos = label(self.clock(self.seek.get_value()), "mono")
            times.pack_start(self.pos, True, True, 0)
            times.pack_start(label(self.clock(length), "mono", xalign=1), False, False, 0)
            self.box.pack_start(times, False, False, 0)
        else:
            self.seek = None
        self.playing = t["status"] == "Playing"
        controls = Gtk.Box(spacing=18, halign=Gtk.Align.CENTER)
        for name, cmd, cls in (("skip-back", "previous", "nav"),
                               ("pause" if t["status"] == "Playing" else "play", "toggle", "play"),
                               ("skip-forward", "next", "nav")):
            b = Gtk.Button(label=icon(name))
            b.get_style_context().add_class(cls)
            b.get_style_context().add_class("media-btn")
            b.set_valign(Gtk.Align.CENTER)
            b.connect("clicked", lambda b, c=cmd: self.control(b, c))
            controls.pack_start(b, False, False, 0)
        self.box.pack_start(controls, False, False, 6)

    @staticmethod
    def clock(sec):
        sec = int(sec)
        return f"{sec // 3600}:{sec % 3600 // 60:02d}:{sec % 60:02d}" if sec >= 3600 else f"{sec // 60}:{sec % 60:02d}"

    @staticmethod
    def rounded(cr, x0, y0, w, h, r):
        cr.new_sub_path()
        for x, y, a in ((x0 + w - r, y0 + r, -math.pi / 2), (x0 + w - r, y0 + h - r, 0),
                        (x0 + r, y0 + h - r, math.pi / 2), (x0 + r, y0 + r, math.pi)):
            cr.arc(x, y, r, a, a + math.pi / 2)
        cr.close_path()

    def draw_art(self, widget, cr, front, back):
        w, h = widget.get_allocated_width(), widget.get_allocated_height()
        self.rounded(cr, 0, 0, w, h, 12)
        cr.clip()
        if back is None:
            Gdk.cairo_set_source_pixbuf(cr, front, (w - front.get_width()) / 2, 0)
            cr.paint()
            return False
        Gdk.cairo_set_source_pixbuf(cr, back, 0, 0)
        cr.paint()
        cr.set_source_rgba(0, 0, 0, 0.25)
        cr.paint()
        fw, fh = front.get_width(), front.get_height()
        x, y = round((w - fw) / 2), round((h - fh) / 2)
        cr.set_source_rgba(0, 0, 0, 0.35)  # a soft drop under the sharp picture
        self.rounded(cr, x + 1, y + 3, fw, fh, 6)
        cr.fill()
        self.rounded(cr, x, y, fw, fh, 6)
        cr.save()
        cr.clip()
        Gdk.cairo_set_source_pixbuf(cr, front, x, y)
        cr.paint()
        cr.restore()
        return False

    def control(self, button, cmd):
        sh(str(HOME / ".local/bin/shoji-media"), cmd)
        if cmd == "toggle":  # only the icon changes: no rebuild, no flicker
            self.playing = not self.playing
            button.set_label(icon("pause" if self.playing else "play"))
            if self.seek is not None:
                self.anchor(self.seek.get_value())
        else:  # another track: its cover, title and length
            GLib.timeout_add(300, self.refresh_open)

    def anchor(self, pos):
        self.base_pos, self.base_time = pos, time.monotonic()

    def glide_seek(self, scale, _clock):
        if self.playing:
            pos = min(scale.get_adjustment().get_upper(), self.base_pos + time.monotonic() - self.base_time)
            scale.set_value(pos)
            text = self.clock(pos)
            if self.pos.get_text() != text:
                self.pos.set_text(text)
        return True

    def refresh_open(self):
        if self.win.get_visible():
            self.clear()
            self.build()
            self.box.show_all()
        return False

    def tick(self):
        """Once a second, re-read the player's position (the frame clock moves the bar between)."""
        if not self.win.get_visible():
            self.ticking = False
            return False
        if self.seek is not None:
            try:
                pos = float(sh("playerctl", "-p", self.player, "position") or 0)
            except ValueError:
                pos = 0
            self.anchor(pos)
        return True

    def show(self):
        super().show()
        if not self.ticking:
            self.ticking = True
            GLib.timeout_add_seconds(1, self.tick)


class Popovers:
    def __init__(self):
        self.backdrop = Backdrop(self.close)
        self.items = {cls.name: cls(self) for cls in (Sound, Network, Bluetooth, Battery)}
        self.items["theme"] = ThemeManager(self)
        self.items["launcher"] = Launcher(self)
        self.items["keys"] = Keys(self)
        self.items["media"] = Media(self)
        self.items["clipboard"] = Clipboard(self)
        self.open = None
        GLib.timeout_add_seconds(300, self.sun_tick)

    def toggle(self, name):
        if name not in self.items:
            return
        if self.open == name:
            self.close()
            return
        self.close()
        self.backdrop.win.show()
        self.items[name].show()
        self.open = name

    def open_with(self, name, query):
        if self.open != name:
            self.toggle(name)
        self.items[name].entry.set_text(query)
        self.items[name].entry.set_position(-1)

    def close(self):
        if self.open:
            self.items[self.open].hide()
        self.backdrop.win.hide()
        self.open = None

    def sun_tick(self, force=False):
        """Follow the sun: switch to the light palette at 06:00 and the dark one at 18:00.

        Only at the change of period (or when the switch is turned on), so a palette picked
        by hand stays until the next sunrise or sunset."""
        pr = prefs()
        today = datetime.date.today().isoformat()
        if pr.get("moon_day") != today:  # the wallpaper's moon follows the real phase, once a day
            save_prefs(moon_day=today)
            spawn(SHOJI, "moon")
        if pr.get("seasonal"):  # a new season (立春, 立夏, 立秋, 立冬): re-apply for its accent
            sid = (sh(SHOJI, "season").split() or [""])[0]
            if sid and pr.get("season") != sid:
                save_prefs(season=sid)
                spawn(SHOJI, "apply")
        if not pr.get("follow_sun"):
            return True
        period = "day" if 6 <= datetime.datetime.now().hour < 18 else "night"
        if force or pr.get("sun_period") != period:
            dark = pr.get("dark", "aizome")
            want = {"aizome": "yuki"}.get(dark, "hiru") if period == "day" else dark
            save_prefs(sun_period=period)
            if sh(SHOJI, "status") != want:
                spawn(SHOJI, "apply", want)
        return True
