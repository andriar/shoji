"""Koyomi: the agenda from Evolution Data Server, the weather, today's cache for `shoji greet`,
and the calendar card with its toggles."""
from shoji_widgets.base import *  # noqa: F401,F403


# a video-call link in an event's location, description or title (Meet, Zoom, Teams, Jitsi, Whereby)
import re  # noqa: E402
MEETING_URL = re.compile(r"https://(?:meet\.google\.com|[\w.-]*zoom\.us|teams\.microsoft\.com|teams\.live\.com|"
                         r"meet\.jit\.si|whereby\.com)/[^\s<>\"')]+")


# ---------------------------------------------------------------- Koyomi agenda (EDS)
def local_zone():
    try:
        name = Path("/etc/timezone").read_text().strip()
    except OSError:
        name = os.path.realpath("/etc/localtime").partition("zoneinfo/")[2]
    return ICalGLib.Timezone.get_builtin_timezone(name) if name else None


def ical_when(t):
    """ICalGLib.Time -> date (all-day) or local naive datetime."""
    if t.is_date():
        return datetime.date(t.get_year(), t.get_month(), t.get_day())
    zone = t.get_timezone() or (ICalGLib.Timezone.get_utc_timezone() if t.is_utc() else None)
    if zone is None:  # floating time: already wall-clock
        return datetime.datetime(t.get_year(), t.get_month(), t.get_day(), t.get_hour(), t.get_minute())
    return datetime.datetime.fromtimestamp(t.as_timet_with_zone(zone))


def epoch(d):
    return int(datetime.datetime.combine(d, datetime.time()).timestamp())


class Agenda:
    """Events and open tasks per day from Evolution Data Server: the calendars GNOME Calendar
    shows (Google through Online Accounts, local, holidays) and task lists (Google Tasks).

    Each source is read in its own thread. EDS waits up to CONNECT_WAIT for an offline calendar
    before it answers from cache, and that wait must hold neither the other sources nor GTK.
    Results come back to the GTK thread through GLib.idle_add."""
    CONNECT_WAIT = 1

    def __init__(self, on_update):
        self.on_update = on_update
        self.registry = None
        self.zone = None
        self.clients = {}   # source uid -> ECal.Client, kept between reads
        self.busy = set()   # source uids with a read in flight
        self.range = None   # (first, last) day of the grid being shown
        self.items = {}     # source uid -> [item] for self.range

    def load(self, first, last):
        self.range = (first, last)
        self.items = {}
        if self.registry is None:
            try:
                self.registry = EDataServer.SourceRegistry.new_sync(None)
            except GLib.Error:
                return
            self.zone = local_zone()
        for ext, kind in ((EDataServer.SOURCE_EXTENSION_CALENDAR, ECal.ClientSourceType.EVENTS),
                          (EDataServer.SOURCE_EXTENSION_TASK_LIST, ECal.ClientSourceType.TASKS)):
            for src in self.registry.list_enabled(ext):
                sel = src.get_extension(ext)
                if sel.get_selected():  # hidden in GNOME Calendar = hidden here
                    self.read(src, kind, sel.get_color() or "#888888")

    def read(self, src, kind, color):
        uid = src.get_uid()
        if uid in self.busy:  # _done reads it again for the new range
            return
        self.busy.add(uid)
        threading.Thread(target=self._read, args=(src, kind, color, self.range), daemon=True).start()

    def _read(self, src, kind, color, rng):
        uid, items = src.get_uid(), []
        client = self.clients.get(uid)
        try:
            if client is None:
                client = ECal.Client.connect_sync(src, kind, self.CONNECT_WAIT, None)
                if self.zone:
                    client.set_default_timezone(self.zone)
            start, end = epoch(rng[0]), epoch(rng[1] + datetime.timedelta(days=1))
            if kind == ECal.ClientSourceType.EVENTS:
                def instance(comp, t0, t1, *_):
                    items.extend(self.event_items(comp, t0, t1, color))
                    return True
                client.generate_instances_sync(start, end, None, instance)
            else:
                query = (f'(and (due-in-time-range? (make-time "{ECal.isodate_from_time_t(start)}") '
                         f'(make-time "{ECal.isodate_from_time_t(end)}")) (not (is-completed?)))')
                for comp in client.get_object_list_as_comps_sync(query, None)[1]:
                    ic = comp.get_icalcomponent()
                    day = ical_when(ic.get_due())
                    day = day.date() if isinstance(day, datetime.datetime) else day
                    items.append({"uid": ic.get_uid(), "day": day, "when": "", "task": True,
                                  "title": ic.get_summary() or "(untitled)", "color": color})
        except GLib.Error as e:
            print("agenda:", src.get_display_name(), e.message, file=sys.stderr)
        GLib.idle_add(self._done, src, kind, color, client, rng, items)

    @staticmethod
    def event_items(comp, t0, t1, color):
        start, end = ical_when(t0), ical_when(t1)
        base = {"uid": comp.get_uid(), "task": False, "title": comp.get_summary() or "(untitled)",
                "color": color}
        if isinstance(start, datetime.datetime):
            end_at = end if isinstance(end, datetime.datetime) and end > start else start + datetime.timedelta(hours=1)
            end_at = end_at if end_at.date() == start.date() else datetime.datetime.combine(start.date(), datetime.time(23, 59))
            text = " ".join(filter(None, (comp.get_location(), comp.get_description(), comp.get_summary())))
            link = MEETING_URL.search(text)
            return [{**base, "day": start.date(), "when": start.strftime("%H:%M"),
                     "end": end_at.strftime("%H:%M"), "url": link.group(0) if link else ""}]
        days = max(1, ((end if isinstance(end, datetime.date) else start) - start).days)
        return [{**base, "day": start + datetime.timedelta(days=i), "when": "終日"} for i in range(days)]

    def _done(self, src, kind, color, client, rng, items):
        uid = src.get_uid()
        self.busy.discard(uid)
        if client is not None:
            self.clients[uid] = client
        if rng == self.range:
            self.items[uid] = items
            self.on_update()
        else:  # the grid moved while this source was busy
            self.read(src, kind, color)
        return False

    def day(self, d):
        seen, out = set(), []
        for it in (i for items in self.items.values() for i in items if i["day"] == d):
            key = (it["uid"], it["when"])  # the same holiday from two subscribed calendars
            if key not in seen:
                seen.add(key)
                out.append(it)
        return sorted(out, key=lambda i: (i["task"], i["when"] != "終日", i["when"], i["title"]))

    def days(self):
        return {i["day"] for items in self.items.values() for i in items}


class Weather:
    """天気 for Koyomi, one kanji: 晴 clear (月 on a clear night), 曇 cloudy, 霧 fog, 雨 rain, 雪 snow,
    雷 thunder, plus the temperature. Open-Meteo (no key), every 30 minutes, in a thread. The place
    is the city of the system time zone (Asia/Jakarta → Jakarta), never your exact location; prefs
    "weather": {"place": "Bandung"} or {"lat": .., "lon": ..} picks another, false turns it off."""
    CACHE = HOME / ".cache/shoji/weather.json"
    CODES = [((0, 1), "晴", "Clear"), ((2, 3), "曇", "Cloudy"), ((45, 48), "霧", "Fog"),
             ((51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82), "雨", "Rain"),
             ((71, 73, 75, 77, 85, 86), "雪", "Snow"), ((95, 96, 99), "雷", "Thunder")]

    def __init__(self, on_update):
        self.on_update = on_update
        if prefs().get("weather", True) is False:
            return
        self.refresh()
        GLib.timeout_add_seconds(1800, self.refresh)

    def refresh(self):
        threading.Thread(target=self.fetch, daemon=True).start()
        return True

    @staticmethod
    def get(url):
        with urllib.request.urlopen(url, timeout=6) as r:
            return json.loads(r.read())

    def place(self):
        want = prefs().get("weather")
        want = want if isinstance(want, dict) else {}
        if "lat" in want and "lon" in want:
            return want["lat"], want["lon"], want.get("place", "")
        name = want.get("place")
        if not name:
            try:
                zone = Path("/etc/timezone").read_text().strip()
            except OSError:
                zone = os.path.realpath("/etc/localtime").partition("zoneinfo/")[2]
            name = zone.rsplit("/", 1)[-1].replace("_", " ")
        old = self.read() or {}
        if old.get("place") == name and "lat" in old:
            return old["lat"], old["lon"], name
        hit = self.get("https://geocoding-api.open-meteo.com/v1/search?count=1&name=" + urllib.parse.quote(name))
        r = hit["results"][0]
        return r["latitude"], r["longitude"], name

    def fetch(self):
        try:
            lat, lon, name = self.place()
            cur = self.get(f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
                           "&current=temperature_2m,weather_code,is_day&timezone=auto")["current"]
        except (OSError, ValueError, KeyError, IndexError):
            return
        kanji, text = next(((k, t) for codes, k, t in self.CODES if cur["weather_code"] in codes), ("曇", "Cloudy"))
        if kanji == "晴" and not cur.get("is_day", 1):
            kanji, text = "月", "Clear night"
        data = {"kanji": kanji, "text": text, "temp": round(cur["temperature_2m"]), "place": name,
                "lat": lat, "lon": lon, "at": time.time()}
        self.CACHE.parent.mkdir(parents=True, exist_ok=True)
        self.CACHE.write_text(json.dumps(data, ensure_ascii=False))
        GLib.idle_add(self.on_update)

    @classmethod
    def read(cls, fresh_s=None):
        try:
            data = json.loads(cls.CACHE.read_text())
        except (OSError, ValueError):
            return None
        if fresh_s and time.time() - data.get("at", 0) > fresh_s:
            return None
        return data


class TodayCache:
    """Today's agenda in ~/.cache/shoji/today.json every 15 minutes, for `shoji greet` (a shell must
    not wait on Evolution Data Server)."""
    OUT = HOME / ".cache/shoji/today.json"

    def __init__(self):
        self.agenda = Agenda(self.write) if ECal else None
        if self.agenda:
            self.refresh()
            GLib.timeout_add_seconds(900, self.refresh)

    def refresh(self):
        today = datetime.date.today()
        self.agenda.load(today, today + datetime.timedelta(days=1))  # tomorrow too, for 仕舞い
        return True

    def items(self):
        return self.agenda.day(datetime.date.today()) if self.agenda else []

    def tomorrow(self):
        return self.agenda.day(datetime.date.today() + datetime.timedelta(days=1)) if self.agenda else []

    def write(self):
        items = [{"when": i["when"], "title": i["title"], "task": i["task"]} for i in self.items()]
        self.OUT.parent.mkdir(parents=True, exist_ok=True)
        self.OUT.write_text(json.dumps({"day": datetime.date.today().isoformat(), "items": items},
                                       ensure_ascii=False))


# ---------------------------------------------------------------- Koyomi calendar
class Calendar:
    """Left half of the Koyomi panel: it ends at the screen's centre line and the swaync panel
    (notifications) starts there (gen_swaync), same height, so the two read as one container.
    The quick toggles live here, not in swaync, because swaync 0.9 buttons cannot show a state."""
    WIDTH = CC_WIDTH

    def __init__(self):
        # keyboard on demand: a click gives Koyomi the keys (arrows, PgUp/PgDn, Home, Enter, Esc)
        self.win = layer_window("hypr-calendar", Layer.Layer.OVERLAY, keyboard=True)
        self.win.connect("key-press-event", self.on_key)
        Layer.set_anchor(self.win, Layer.Edge.TOP, True)
        Layer.set_anchor(self.win, Layer.Edge.LEFT, True)
        Layer.set_margin(self.win, Layer.Edge.TOP, GAP)
        self.win.set_size_request(self.WIDTH, -1)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.get_style_context().add_class("panel")
        box.get_style_context().add_class("koyomi")
        head = Gtk.Box(spacing=6)  # one line: the date, and beside it the weekday over the 候
        self.date = label("", "display")
        self.date.set_valign(Gtk.Align.CENTER)
        head.pack_start(self.date, True, True, 0)
        right = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        right.set_valign(Gtk.Align.CENTER)
        self.weekday = label("", "muted", xalign=1)
        self.yw = label("", "season", xalign=1)  # 候 of today; the week number is in its tooltip
        right.pack_start(self.weekday, False, False, 0)
        right.pack_start(self.yw, False, False, 0)
        head.pack_start(right, False, False, 0)
        box.pack_start(head, False, False, 0)
        nav = Gtk.Box(spacing=4)
        self.month = label("", "title")
        nav.pack_start(self.month, True, True, 0)
        for name, step, tip in (("chevron-left", -1, "Previous month"), ("chevron-right", 1, "Next month")):
            b = Gtk.Button(label=icon(name))
            b.set_tooltip_text(T(tip))
            b.get_style_context().add_class("nav")
            b.connect("clicked", lambda _b, s=step: self.shift(s))
            nav.pack_start(b, False, False, 0)
        box.pack_start(nav, False, False, 0)
        # the weekday row stays; two month pages in a stack below it slide one out and the next in
        month = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)  # same rhythm as the day rows
        weekdays = Gtk.Grid(column_homogeneous=True)
        for i, k in enumerate(WEEK_K):
            weekdays.attach(label(k, "wk", xalign=0.5), i, 0, 1, 1)
        month.pack_start(weekdays, False, False, 0)
        self.grid_pages = [Gtk.Grid(column_homogeneous=True, row_spacing=2) for _ in range(2)]
        self.grid_stack = Gtk.Stack(transition_duration=CONTENT_MS, hhomogeneous=True, vhomogeneous=True)
        for i, g in enumerate(self.grid_pages):
            self.grid_stack.add_named(g, f"m{i}")
        month.pack_start(self.grid_stack, False, False, 0)
        box.pack_start(month, False, False, 0)
        self.grid = self.grid_pages[0]
        self.slide = 0   # -1 / +1 while the next fill() should slide to the previous / next month
        self.fade = False  # the next fill_agenda() crossfades (a new day was picked)
        self.agenda = Agenda(self.fill_agenda) if ECal else None
        if self.agenda:
            box.get_style_context().add_class("agenda")
            box.pack_start(sep(), False, False, 0)
            head = Gtk.Box(spacing=4)
            self.sel_label = label("", "label-small")
            head.pack_start(self.sel_label, True, True, 0)
            self.zazen_count = label("", "label-small")  # 座 ×N: focus sessions finished today
            head.pack_start(self.zazen_count, False, False, 6)
            if shutil.which("gnome-calendar"):
                b = Gtk.Button(label=icon("external-link"))
                b.get_style_context().add_class("nav")
                b.set_tooltip_text(T("Open in GNOME Calendar"))
                b.connect("clicked", lambda _b: self.open_day())
                head.pack_start(b, False, False, 0)
            box.pack_start(head, False, False, 0)
            self.row_pages = [Gtk.Box(orientation=Gtk.Orientation.VERTICAL) for _ in range(2)]
            self.row_stack = Gtk.Stack(transition_duration=CONTENT_MS, vhomogeneous=True,
                                       transition_type=Gtk.StackTransitionType.CROSSFADE)
            for i, r in enumerate(self.row_pages):
                r.set_size_request(-1, AGENDA_ROWS * 24)
                self.row_stack.add_named(r, f"a{i}")
            box.pack_start(self.row_stack, False, False, 0)
            self.rows = self.row_pages[0]
        box.pack_start(sep(), False, False, 0)
        self.toggles = {}
        row = Gtk.Box(spacing=6, homogeneous=True)
        for key, tip in self.TOGGLES:
            b = Gtk.Button(label=icon(self.ICONS[key][0]))
            b.get_style_context().add_class("toggle")
            b.set_tooltip_text(T(tip))
            b.connect("clicked", lambda _b, k=key: self.press(k))
            b.connect("button-press-event", lambda _b, ev, k=key: self.press(k, alt=True) if ev.button == 3 else False)
            row.pack_start(b, True, True, 0)
            self.toggles[key] = b
        box.pack_start(row, False, False, 0)
        self.win.add(box)
        box.show_all()
        self.view = datetime.date.today().replace(day=1)
        self.selected = datetime.date.today()
        self.weather = Weather(lambda: self.win.get_visible() and self.paint_header())

    def shift(self, step):
        y, m = self.view.year, self.view.month + step
        if m == 0:
            y, m = y - 1, 12
        elif m == 13:
            y, m = y + 1, 1
        self.view = datetime.date(y, m, 1)
        today = datetime.date.today()
        self.selected = today if (today.year, today.month) == (y, m) else self.view
        self.slide, self.fade = step, True
        self.load()

    def weeks(self):
        weeks = cal_mod.Calendar(firstweekday=6).monthdatescalendar(self.view.year, self.view.month)  # Sunday first
        while len(weeks) < 6:  # always 6 rows: the card keeps one height, the panel under it never moves
            weeks.append([d + datetime.timedelta(days=7) for d in weeks[-1]])
        return weeks

    def load(self):
        """Draw the month, then ask EDS for its events; fill_agenda redraws as sources answer."""
        if self.agenda:
            weeks = self.weeks()
            self.agenda.load(weeks[0][0], weeks[-1][-1])
        self.fill_agenda()

    def on_key(self, _w, ev):
        """← → a day, ↑ ↓ a week, PgUp/PgDn a month, Home today, Enter opens the day, Esc closes."""
        step = {Gdk.KEY_Left: -1, Gdk.KEY_Right: 1, Gdk.KEY_Up: -7, Gdk.KEY_Down: 7}.get(ev.keyval)
        if step:
            self.pick(self.selected + datetime.timedelta(days=step))
        elif ev.keyval in (Gdk.KEY_Page_Up, Gdk.KEY_Page_Down):
            self.shift(-1 if ev.keyval == Gdk.KEY_Page_Up else 1)
        elif ev.keyval == Gdk.KEY_Home:
            self.pick(datetime.date.today())
        elif ev.keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter):
            self.open_day()
        elif ev.keyval == Gdk.KEY_Escape:
            spawn("swaync-client", "-cp")
        else:
            return False
        return True

    def pick(self, d):
        self.fade = d != self.selected
        self.selected = d
        if (d.year, d.month) != (self.view.year, self.view.month):
            self.slide = 1 if d > self.view else -1
            self.view = d.replace(day=1)
            self.load()
        else:
            self.fill_agenda()

    def fill(self):
        if self.slide:  # build the month on the hidden page, then slide to it
            self.grid = self.grid_pages[1 - self.grid_pages.index(self.grid)]
        for child in self.grid.get_children():
            self.grid.remove(child)
        today = datetime.date.today()
        marked = self.agenda.days() if self.agenda else set()
        self.month.set_text(month_year(self.view))
        for r, week in enumerate(self.weeks()):
            for col, d in enumerate(week):
                b = Gtk.Button()
                b.set_halign(Gtk.Align.CENTER)
                ctx = b.get_style_context()
                ctx.add_class("day")
                if d.month != self.view.month:
                    ctx.add_class("other")
                elif d < today:
                    ctx.add_class("past")
                if d == today:
                    ctx.add_class("today")
                if d == self.selected and self.agenda:
                    ctx.add_class("sel")
                over = Gtk.Overlay()
                over.add(label(str(d.day), "num", xalign=0.5))
                if d in marked:
                    mark = Gtk.Box(halign=Gtk.Align.CENTER, valign=Gtk.Align.END)
                    mark.get_style_context().add_class("mark")
                    over.add_overlay(mark)
                b.add(over)
                b.connect("clicked", lambda _b, d=d: self.pick(d))
                self.grid.attach(b, col, r, 1, 1)
        self.grid.show_all()
        if self.slide:
            self.grid_stack.set_transition_duration(0 if reduced() else CONTENT_MS)
            self.grid_stack.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT if self.slide > 0
                                                else Gtk.StackTransitionType.SLIDE_RIGHT)
            self.grid_stack.set_visible_child(self.grid)
            self.slide = 0

    def fill_agenda(self):
        self.fill()
        if not self.agenda:
            return
        d = self.selected
        near = {0: "today", 1: "tomorrow", -1: "yesterday"}.get((d - datetime.date.today()).days)
        self.sel_label.set_text((T(near) if near else short_day(d)).upper())
        sat = self.zazen_today() if near == "today" else 0
        self.zazen_count.set_text(f"座 ×{sat}" if sat else "")
        self.zazen_count.set_tooltip_text(T("{n} zazen today").format(n=sat) if sat else None)
        fade, self.fade = self.fade, False
        if fade:  # a new day: write its agenda on the hidden page and crossfade to it
            self.rows = self.row_pages[1 - self.row_pages.index(self.rows)]
        for child in self.rows.get_children():
            self.rows.remove(child)
        items = self.agenda.day(d)
        if not items:
            poem, poet = haiku(d)   # a free day keeps its space for a poem (間)
            free = label(f"{poem}　— {poet}", "haiku")
            free.set_tooltip_text(T("Nothing scheduled"))
            self.rows.pack_start(free, False, False, 6)
        shown = items if len(items) <= AGENDA_ROWS else items[:AGENDA_ROWS - 1]
        for it in shown:
            b = Gtk.Button()
            b.get_style_context().add_class("agenda-row")
            row = Gtk.Box(spacing=8)
            tick = Gtk.Label(xalign=0.5)
            tick.get_style_context().add_class("tick")
            glyph = icon("circle") if it["task"] else "●"
            tick.set_markup(f'<span foreground="{it["color"]}">{GLib.markup_escape_text(glyph)}</span>')
            row.pack_start(tick, False, False, 0)
            when = label(it["when"], "when")
            when.set_width_chars(5)
            row.pack_start(when, False, False, 0)
            title = label(it["title"])
            title.set_ellipsize(Pango.EllipsizeMode.END)
            row.pack_start(title, True, True, 0)
            b.add(row)
            b.set_tooltip_text(it["title"])
            b.connect("clicked", lambda _b: self.open_day())
            self.rows.pack_start(b, False, False, 0)
        if len(items) > len(shown):
            more = Gtk.Button()
            more.add(label(T("+{n} more").format(n=len(items) - len(shown))))
            for c in ("agenda-row", "more"):
                more.get_style_context().add_class(c)
            more.connect("clicked", lambda _b: self.open_day())
            self.rows.pack_start(more, False, False, 0)
        self.rows.show_all()
        if fade:
            self.row_stack.set_transition_duration(0 if reduced() else CONTENT_MS)
            self.row_stack.set_visible_child(self.rows)
        # a GTK window grows with its content but never shrinks back on its own; the card must keep
        # the swaync panel's height (sources answering one by one briefly made it taller)
        self.win.resize(self.WIDTH, 1)

    TOGGLES = [("network", "Network"), ("bluetooth", "Bluetooth · right-click: devices"),
               ("night", "Night light"), ("silent", "Silent (do not disturb)"), ("awake", "Keep awake"),
               ("theme", "Theme"), ("power", "Power menu")]
    ICONS = {"network": ("wifi", "wifi-off"), "bluetooth": ("bluetooth", "bluetooth-off"),
             "night": ("moon", "moon"), "silent": ("bell-off", "bell"), "awake": ("coffee", "coffee"),
             "theme": ("palette", "palette"), "power": ("power", "power")}

    @staticmethod
    def toggle_states():
        """Runs in a thread: a few small commands, read fresh each time the panel opens."""
        dev = sh("nmcli", "-t", "-f", "TYPE,STATE", "device")
        net = "wifi" if "wifi:connected" in dev else "ethernet-port" if "ethernet:connected" in dev else None
        def on(cmd):
            try:
                return json.loads(sh(*cmd) or "{}").get("class") == "on"
            except ValueError:
                return False
        return {"network": net,
                "bluetooth": "Powered: yes" in sh("bluetoothctl", "show"),
                "night": on([str(HOME / ".local/bin/hypr-nightlight"), "status"]),
                "silent": sh("swaync-client", "-D") == "true",
                "awake": on([str(HOME / ".local/bin/keep-awake"), "status"])}

    def refresh_toggles(self):
        threading.Thread(target=lambda: GLib.idle_add(self.paint_toggles, self.toggle_states()),
                         daemon=True).start()
        return False

    def paint_toggles(self, st):
        tips = dict(self.TOGGLES)
        for key, b in self.toggles.items():
            b.set_tooltip_text(T(tips[key]))  # the language may have changed since the card was built
            ctx, state = b.get_style_context(), st.get(key)
            ctx.remove_class("on")
            ctx.remove_class("off-alert")
            if key == "network":
                b.set_label(icon(state or "wifi-off"))
                if not state:
                    ctx.add_class("off-alert")
            elif key in st:
                b.set_label(icon(self.ICONS[key][0 if state else 1]))
                if state:
                    ctx.add_class("on")
        return False

    def press(self, key, alt=False):
        bin_ = str(HOME / ".local/bin")
        if key == "bluetooth" and not alt:
            on = "Powered: yes" in sh("bluetoothctl", "show")
            spawn("bluetoothctl", "power", "off" if on else "on")
        elif key == "night":
            spawn(f"{bin_}/hypr-nightlight", "toggle")
        elif key == "silent":
            spawn("swaync-client", "-d", "-sw")
        elif key == "awake":
            spawn(f"{bin_}/keep-awake", "toggle")
        else:  # these open something else: close the panel first
            spawn("swaync-client", "-cp")
            spawn(*{"network": [f"{bin_}/hypr-pop", "network"], "bluetooth": [f"{bin_}/hypr-pop", "bluetooth"],
                    "theme": [f"{bin_}/hypr-pop", "theme"],
                    "power": ["wlogout", "-b", "4", "-p", "layer-shell"]}[key])
            return True
        GLib.timeout_add(400, self.refresh_toggles)
        return True

    def open_day(self):
        """GNOME Calendar on the picked day; --date is parsed with the locale's %x, like strftime."""
        if shutil.which("gnome-calendar"):
            spawn("swaync-client", "-cp")
            spawn("gnome-calendar", "--date", self.selected.strftime("%x"))

    def show(self):
        load_css()
        name_icons(self.win)
        today = datetime.date.today()
        self.view = today.replace(day=1)
        kanji_day = f"{WEEK_K[(today.weekday() + 1) % 7]}曜日"
        self.weekday.set_text(kanji_day if LANG["code"] == "ja" else f"{day_name(today)} · {kanji_day}")
        self.date.set_text(day_month(today))
        self.paint_header()
        self.selected = today
        self.load()
        self.refresh_toggles()
        # no output set: Hyprland puts the card on the focused monitor, where swaync opens too. The
        # card sits against the panel's left edge: swaync keeps one right margin on every monitor
        # (set for the primary one by gen_swaync), so on a narrower or scaled screen the pair still
        # touches instead of drifting apart around a centre line
        Layer.set_margin(self.win, Layer.Edge.LEFT,
                         max(0, self.focused_width() - self.panel_margin() - CC_WIDTH - self.WIDTH))
        self.win.show()

    def hide(self):
        self.win.hide()

    @staticmethod
    def zazen_today():
        try:
            day = datetime.date.today().isoformat()
            return sum(1 for line in (HOME / ".local/state/shoji-zazen.log").read_text().splitlines()
                       if line.startswith(day))
        except OSError:
            return 0

    def paint_header(self):
        """The 候 of today, then the weather when it is fresh (under two hours old)."""
        today = datetime.date.today()
        kanji, english = micro_season(today)
        poem, poet = haiku(today)
        tip = f"{english} · {today.year} · w{today.isocalendar()[1]}\n{poem}　— {poet}"
        w = Weather.read(fresh_s=7200)
        if w:
            kanji += f" · {w['kanji']} {w['temp']}°"
            tip = f"{english} · {w['text']} {w['temp']}°C in {w['place']} · {today.year} · w{today.isocalendar()[1]}\n{poem}　— {poet}"
        self.yw.set_text(kanji)
        self.yw.set_tooltip_text(tip)
        return False

    @staticmethod
    def panel_margin():
        try:
            return int(json.loads((HOME / ".config/swaync/config.json").read_text())["control-center-margin-right"])
        except (OSError, ValueError, KeyError):
            return 0

    @staticmethod
    def focused_width():
        """Logical width of the focused monitor (the same one gen_swaync measures)."""
        try:
            mons = json.loads(sh("hyprctl", "monitors", "-j") or "[]")
            m = next((m for m in mons if m.get("focused")), mons[0])
            return round(m["width"] / m.get("scale", 1))
        except (ValueError, IndexError, KeyError):
            return 2560
