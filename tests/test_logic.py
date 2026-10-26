"""Logic tests for the parts of Shoji that decide something: seasons, contrast, meetings, the
player to show, zazen counts. Run from the repo: python3 -m unittest discover tests

The widget tests import the shoji_widgets package, which needs a GTK display (any Wayland or X
session); nothing is shown."""
import datetime
import importlib.machinery
import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "widgets"))


def load(name):
    return importlib.machinery.SourceFileLoader(name.replace("-", "_"), str(REPO / "bin" / name)).load_module()


shoji = load("shoji")
shoji.PREFS = Path(tempfile.gettempdir()) / "shoji-tests-no-prefs.json"  # tests never read your prefs


class Seasons(unittest.TestCase):
    def test_micro_season_boundaries(self):
        ms = shoji.micro_season
        self.assertEqual(ms(datetime.date(2026, 1, 1))[0], "雪下出麦")   # still last year's 候
        self.assertEqual(ms(datetime.date(2026, 1, 5))[0], "芹乃栄")
        self.assertEqual(ms(datetime.date(2026, 10, 23))[0], "霜始降")
        self.assertEqual(ms(datetime.date(2026, 12, 31))[0], "雪下出麦")
        self.assertEqual(len(shoji.KO), 72)
        self.assertEqual(shoji.KO, sorted(shoji.KO))

    def test_a_haiku_of_the_season_every_day(self):
        self.assertEqual(set(shoji.HAIKU), {"spring", "summer", "autumn", "winter"})
        seen = set()
        for n in range(366):
            d = datetime.date(2026, 1, 1) + datetime.timedelta(days=n)
            poem = shoji.haiku(d)
            self.assertIn(poem, shoji.HAIKU[shoji.season(d)[0]])
            seen.add(poem)
        self.assertEqual(len(seen), sum(len(v) for v in shoji.HAIKU.values()))   # every poem comes round

    def test_season_boundaries(self):
        self.assertEqual(shoji.season(datetime.date(2026, 2, 3))[0], "winter")
        self.assertEqual(shoji.season(datetime.date(2026, 2, 4))[0], "spring")
        self.assertEqual(shoji.season(datetime.date(2026, 11, 7))[0], "winter")

    def test_every_seasonal_accent_reads_on_every_palette(self):
        for pid, p in shoji.PALETTES.items():
            for _, sid, _, colour in shoji.SEASONS:
                acc, on = shoji.fit_accent(colour, p["bg"], p["text"], p["dark"])
                self.assertGreaterEqual(shoji.contrast(acc, p["bg"]), 3.2, (pid, sid))
                self.assertGreaterEqual(shoji.contrast(on, acc), 4.5, (pid, sid))

    def test_moon_phase(self):
        full = datetime.datetime(2026, 10, 26, 12, tzinfo=datetime.timezone.utc)   # a full moon
        self.assertLess(abs(shoji.moon_phase(full) - 0.5), 0.05)


class Palettes(unittest.TestCase):
    def test_text_muted_accent_pass(self):
        for pid in shoji.PALETTES:
            t = shoji.tokens(pid)
            for k in ("text", "muted"):
                self.assertGreaterEqual(shoji.contrast(t[k], t["base"]), 4.5, (pid, k))
            self.assertGreaterEqual(shoji.contrast(t["on_accent"], t["accent"]), 4.5, pid)


class YourOwnPalette(unittest.TestCase):
    def test_every_swatch_pair_passes(self):
        from shoji_widgets.popovers import ThemeManager
        for _, bg in ThemeManager.GROUNDS:
            for _, accent in ThemeManager.ACCENTS:
                p = shoji.complete_palette("t", bg, accent)
                self.assertGreaterEqual(shoji.contrast(p["text"], bg), 4.5, (bg, accent))
                self.assertGreaterEqual(shoji.contrast(p["muted"], bg), 4.5, (bg, accent))
                self.assertGreaterEqual(shoji.contrast(p["accent"], bg), 3.0, (bg, accent))
                self.assertGreaterEqual(shoji.contrast(p["on_accent"], p["accent"]), 4.5, (bg, accent))


class HighContrast(unittest.TestCase):
    def test_sumi_and_shiro_reach_aaa(self):
        for pid in ("sumi", "shiro"):
            t = shoji.tokens(pid)
            self.assertGreaterEqual(shoji.contrast(t["text"], t["base"]), 7, pid)
            self.assertGreaterEqual(shoji.contrast(t["muted"], t["base"]), 7, pid)
            self.assertGreaterEqual(shoji.contrast(t["on_accent"], t["accent"]), 7, pid)


class Meetings(unittest.TestCase):
    def setUp(self):
        from shoji_widgets import overlays
        self.o, self.calls, self.dnd = overlays, [], {"on": False, "count": 3}
        self.saved = (overlays.sh, overlays.spawn, overlays.prefs)

        def sh(*a):
            self.calls.append(a)
            if a[:2] == ("swaync-client", "-D"):
                return "true" if self.dnd["on"] else "false"
            if a[:2] == ("swaync-client", "-c"):
                return str(self.dnd["count"])
            if a[:2] == ("swaync-client", "-dn"):
                self.dnd["on"] = True
            if a[:2] == ("swaync-client", "-df"):
                self.dnd["on"] = False
            return ""
        overlays.sh, overlays.spawn, overlays.prefs = sh, lambda *a: self.calls.append(("spawn",) + a), lambda: {}

    def tearDown(self):
        self.o.sh, self.o.spawn, self.o.prefs = self.saved

    def meetings(self, items):
        m = self.o.Meetings.__new__(self.o.Meetings)
        shown = []
        m.today = type("T", (), {"items": lambda _s: items})()
        m.reasons, m.ours, m.held_from, m.reminded = set(), False, 0, set()
        m.OURS = Path(tempfile.mkdtemp()) / "silent.json"
        m.card = type("C", (), {"show": lambda _s, i: shown.append(i["title"])})()
        m.shimai = type("S", (), {"resting": lambda _s: False, "tick": lambda _s, now: None})()
        m.batch = type("B", (), {"minutes": lambda _s: 0, "tick": lambda _s, now: None})()
        return m, shown

    def test_silent_during_an_event_and_one_reminder(self):
        now = datetime.datetime.now()
        hm = lambda d: (now + datetime.timedelta(minutes=d)).strftime("%H:%M")
        m, shown = self.meetings([
            {"uid": "a", "task": False, "when": hm(-5), "end": hm(20), "title": "Review", "url": ""},
            {"uid": "b", "task": False, "when": hm(8), "end": hm(30), "title": "Standup", "url": ""}])
        m.tick()
        m.tick()
        self.assertTrue(self.dnd["on"])
        self.assertEqual(shown, ["Standup"])

    def test_screen_share_holds_silent_and_the_note_counts(self):
        m, _ = self.meetings([])
        m.set("meeting", True)
        self.dnd["count"] = 7
        m.set("screen", True)
        m.set("meeting", False)
        self.assertTrue(self.dnd["on"])
        m.set("screen", False)
        self.assertFalse(self.dnd["on"])
        self.assertIn("4 notifications waited", self.calls[-1][-1])

    def test_a_restart_still_turns_our_silent_off(self):
        m, _ = self.meetings([])
        m.set("meeting", True)
        self.assertTrue(self.dnd["on"])
        again, _ = self.meetings([])   # hypr-widgets restarted mid-meeting, and the meeting ended
        again.OURS = m.OURS
        kept = json.loads(m.OURS.read_text())
        again.ours, again.held_from, again.reasons = kept["ours"], kept["held_from"], {"restart"}
        again.tick()
        self.assertFalse(self.dnd["on"])

    def test_silent_by_hand_is_left_alone(self):
        self.dnd["on"] = True
        m, _ = self.meetings([])
        m.set("meeting", True)
        m.set("meeting", False)
        self.assertTrue(self.dnd["on"])

    def test_call_links(self):
        from shoji_widgets.koyomi import MEETING_URL
        self.assertEqual(MEETING_URL.search("join https://meet.google.com/abc-defg-hij).").group(0),
                         "https://meet.google.com/abc-defg-hij")
        self.assertTrue(MEETING_URL.search("https://acme.zoom.us/j/123?pwd=x"))
        self.assertIsNone(MEETING_URL.search("https://example.com/meeting"))


class Weather(unittest.TestCase):
    def test_every_wmo_code_has_a_kanji(self):
        from shoji_widgets.koyomi import Weather
        codes = [c for group, _, _ in Weather.CODES for c in group]
        self.assertEqual(len(codes), len(set(codes)))
        for code in (0, 1, 2, 3, 45, 48, 51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 71, 73, 75, 77,
                     80, 81, 82, 85, 86, 95, 96, 99):
            self.assertIn(code, codes)


class Clipboard(unittest.TestCase):
    def test_image_entries_read_as_images(self):
        from shoji_widgets.popovers import Clipboard
        self.assertEqual(Clipboard.describe("[[ binary data 48 KiB png 1920x1080 ]]"), "Image · png · 1920×1080 · 48 KiB")
        self.assertEqual(Clipboard.describe("[[ binary data ]]"), "Image")


class Media(unittest.TestCase):
    def test_the_playing_player_wins(self):
        media = load("shoji-media")
        status = {"chromium.instance1": "Paused", "spotify": "Playing"}

        def playerctl(*a):
            if a == ("-l",):
                return "\n".join(status)
            if a[0] == "-p" and a[2] == "status":
                return status[a[1]]
            return ""
        media.playerctl = playerctl
        self.assertEqual(media.player(), "spotify")
        status["spotify"] = "Paused"
        self.assertEqual(media.player("spotify"), "spotify")      # the one shown stays
        status["chromium.instance1"] = "Playing"
        self.assertEqual(media.player("spotify"), "chromium.instance1")
        status.update({k: "Stopped" for k in status})
        self.assertIsNone(media.player())


class Zazen(unittest.TestCase):
    def test_today_count(self):
        zazen = load("shoji-zazen")
        with tempfile.TemporaryDirectory() as d:
            zazen.LOG = Path(d) / "log"
            today = datetime.date.today().isoformat()
            zazen.LOG.write_text(f"{today} 09:00 25\n{today} 10:00 25\n2000-01-01 10:00 25\n")
            self.assertEqual(zazen.today_count(), 2)


class Language(unittest.TestCase):
    def tearDown(self):
        from shoji_widgets import base
        base.LANG["code"] = "en"

    def test_every_wrapped_string_has_both_translations(self):
        import re
        import string
        from shoji_widgets.base import STRINGS
        used = set()
        for f in (REPO / "widgets/shoji_widgets").glob("*.py"):
            used |= {m[1] for m in re.findall(r"""\bT\((["'])([^"'\n]+)\1\)""", f.read_text())}
        self.assertFalse(used - set(STRINGS), "wrapped in T() but missing from STRINGS")
        fields = lambda s: {f for _, f, _, _ in string.Formatter().parse(s) if f}
        for en, pair in STRINGS.items():
            self.assertEqual(len(pair), 2, en)
            for text in pair:
                self.assertTrue(text, en)
                self.assertEqual(fields(text), fields(en), en)

    def test_dates_and_fallback(self):
        from shoji_widgets import base
        d = datetime.date(2026, 10, 26)  # a Monday
        base.LANG["code"] = "id"
        self.assertEqual((base.day_name(d), base.day_month(d), base.month_year(d)), ("Senin", "26 Oktober", "Oktober 2026"))
        self.assertEqual(base.T("today"), "hari ini")
        base.LANG["code"] = "ja"
        self.assertEqual((base.day_month(d), base.month_year(d), base.short_day(d)), ("10月26日", "2026年10月", "10月26日（月）"))
        self.assertEqual(base.T("not a known string"), "not a known string")
        base.LANG["code"] = "fr"   # an unknown code reads as English
        self.assertEqual(base.T("today"), "today")


class Ink(unittest.TestCase):
    def setUp(self):
        self.ink = load("shoji-ink")

    def test_drops_are_seeded_and_fade_away(self):
        a, b = self.ink.Drops(seed=3), self.ink.Drops(seed=3)
        self.assertEqual([d["x"] for d in a.at(30, 1000, 600)], [d["x"] for d in b.at(30, 1000, 600)])
        late = a.at(300, 1000, 600)
        self.assertTrue(all(300 - d["born"] < self.ink.LIFE_S for d in late))
        self.assertLessEqual(len(late), self.ink.LIFE_S / (self.ink.EVERY_S * 0.7) + 1)

    def test_a_frame_paints_the_ground(self):
        import cairo
        surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, 64, 36)
        pal = {"bg": "#102030", "ink": "#ffffff", "muted": "#888888", "accent": "#eb6101", "dark": True}
        self.ink.paint(cairo.Context(surf), 64, 36, 60, [], pal)
        b, g, r, a = surf.get_data()[:4]
        self.assertEqual((r, g, b, a), (0x10, 0x20, 0x30, 255))

    def test_gtk_loads_in_a_fresh_process(self):
        import subprocess
        code = ("import importlib.machinery, sys; importlib.machinery.SourceFileLoader('ink', sys.argv[1])"
                ".load_module().gtk()")
        r = subprocess.run([sys.executable, "-c", code, str(REPO / "bin/shoji-ink")], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr[-300:])

    def test_lock_config_takes_the_ink_frame(self):
        conf = (REPO / "config/hypr/hyprlock.conf").read_text()
        out = self.ink.lock_config(conf)
        bg = out[out.index("background {"):out.index("}", out.index("background {"))]
        self.assertIn(f"path = {self.ink.LOCK_FRAME}", bg)
        self.assertIn("blur_passes = 0", bg)
        self.assertIn("brightness = 1.0", bg)
        self.assertEqual(out.count("\n"), conf.rstrip("\n").count("\n") + 1)   # nothing else moved
        self.assertIn("lock-enso.png", out)

    def test_the_pointer_setting_comes_back(self):
        from unittest import mock
        calls = []

        def run(cmd, **kw):
            calls.append(cmd)
            return type("R", (), {"stdout": '{"option": "cursor:inactive_timeout", "float": 5.0}'})()
        with tempfile.TemporaryDirectory() as d, mock.patch.object(self.ink, "CURSOR", Path(d) / "c"), \
                mock.patch.object(self.ink.subprocess, "run", run):
            self.ink.hide_cursor()
            self.ink.hide_cursor()   # a second start must not save its own 1 as the "before"
            self.ink.restore_cursor()
            self.assertFalse(self.ink.CURSOR.exists())
        evals = [c[2] for c in calls if c[1] == "eval"]
        self.assertEqual(evals[-1], "hl.config({ cursor = { inactive_timeout = 5 } })")

    def test_ink_off_in_prefs_never_starts(self):
        with tempfile.TemporaryDirectory() as d:
            self.ink.PREFS = Path(d) / "prefs.json"
            self.ink.PREFS.write_text('{"ink": false}')
            self.ink.PID = Path(d) / "ink.pid"
            from unittest import mock
            with mock.patch.object(self.ink.subprocess, "Popen") as popen, \
                    mock.patch.object(sys, "argv", ["shoji-ink", "start"]):
                self.ink.main()
            popen.assert_not_called()


class Greeter(unittest.TestCase):
    def test_files_parse(self):
        import contextlib
        import io
        import subprocess
        import tomllib
        with tempfile.TemporaryDirectory() as d:
            old, shoji.GREETER = shoji.GREETER, Path(d)
            try:
                with contextlib.redirect_stdout(io.StringIO()):
                    shoji.cmd_greeter()
            finally:
                shoji.GREETER = old
            conf = tomllib.loads((Path(d) / "regreet.toml").read_text())
            self.assertEqual(conf["background"]["path"], "/etc/greetd/shoji-background.png")
            self.assertIn("regreet", tomllib.loads((Path(d) / "config.toml").read_text())["default_session"]["command"])
            check = (  # GTK 4's own CSS parser, in its own process (these tests load GTK 3)
                "import gi, sys; gi.require_version('Gtk', '4.0'); from gi.repository import Gtk\n"
                "e = []; p = Gtk.CssProvider(); p.connect('parsing-error', lambda *a: e.append(a[2].message))\n"
                "p.load_from_string(open(sys.argv[1]).read()); print('|'.join(e))")
            r = subprocess.run([sys.executable, "-c", check, str(Path(d) / "regreet.css")], capture_output=True, text=True)
            if r.returncode:
                self.skipTest("GTK 4 is not installed")
            self.assertEqual(r.stdout.strip(), "")


class Shimai(unittest.TestCase):
    def make(self, prefs_value="17:00"):
        from unittest import mock
        from shoji_widgets import overlays
        s = object.__new__(overlays.Shimai)
        s.shown_on, s.timer = None, 0
        s.show_day = mock.Mock()
        s.STATE = Path(tempfile.mkdtemp()) / "shimai.json"
        self.patch = mock.patch.object(overlays, "prefs", return_value={"shimai": prefs_value})
        self.patch.start()
        self.addCleanup(self.patch.stop)
        return s

    def test_once_on_a_weekday_evening(self):
        s = self.make()
        monday = datetime.datetime(2026, 10, 26, 16, 59)
        s.tick(monday)
        s.show_day.assert_not_called()
        s.tick(monday.replace(hour=17, minute=0))
        s.tick(monday.replace(hour=17, minute=30))
        self.assertEqual(s.show_day.call_count, 1)

    def test_not_on_weekends_late_logins_or_when_off(self):
        s = self.make()
        s.tick(datetime.datetime(2026, 10, 31, 17, 5))     # Saturday
        s.tick(datetime.datetime(2026, 10, 26, 19, 30))    # two hours after: not the end of a day
        s.show_day.assert_not_called()
        s = self.make("")
        s.tick(datetime.datetime(2026, 10, 26, 17, 5))
        s.show_day.assert_not_called()

    def test_resting_until_the_morning(self):
        import time
        s = self.make()
        self.assertFalse(s.resting())
        s.STATE.write_text(json.dumps({"until": time.time() + 60}))
        self.assertTrue(s.resting())
        s.STATE.write_text(json.dumps({"until": time.time() - 1}))
        self.assertFalse(s.resting())


class Batch(unittest.TestCase):
    def test_note_skips_critical_and_the_card_comes_once_a_slot(self):
        import os
        import subprocess
        from unittest import mock
        from shoji_widgets import overlays
        run = Path(tempfile.mkdtemp())
        for app, urgency in (("Slack", "Normal"), ("Slack", "Low"), ("Mail", "Normal"), ("Pager", "Critical")):
            subprocess.run([str(REPO / "bin/shoji-batch"), "note"], check=True, env={
                **os.environ, "XDG_RUNTIME_DIR": str(run), "SWAYNC_APP_NAME": app, "SWAYNC_URGENCY": urgency})
        b = object.__new__(overlays.Batch)
        b.LOG, b.slot = run / "shoji-batch.log", None
        self.assertEqual(b.waiting(), {"Slack": 2, "Mail": 1})
        b.show_digest = mock.Mock()
        with mock.patch.object(overlays, "prefs", return_value={"batch": 30}):
            b.tick(datetime.datetime(2026, 10, 26, 10, 10))   # mid-slot start: nothing yet
            b.tick(datetime.datetime(2026, 10, 26, 10, 29))
            b.show_digest.assert_not_called()
            b.tick(datetime.datetime(2026, 10, 26, 10, 30))
            b.tick(datetime.datetime(2026, 10, 26, 10, 31))
        b.show_digest.assert_called_once_with({"Slack": 2, "Mail": 1})
        self.assertEqual(b.waiting(), {})


class Slack(unittest.TestCase):
    def test_four_colours_in_slacks_order(self):
        import contextlib
        import io
        import shutil
        from unittest import mock
        out = io.StringIO()
        with mock.patch.object(shutil, "which", return_value=None), contextlib.redirect_stdout(out), \
                mock.patch.object(shoji, "CFG", Path(tempfile.mkdtemp())):   # no live palette: the saved one
            shoji.cmd_slack()
        first = out.getvalue().splitlines()[0]
        t = shoji.tokens(shoji.current())
        self.assertEqual(first, ", ".join(t[k].upper() for k in ("base", "accent", "ok", "alert")))


class EyeRest(unittest.TestCase):
    def make(self, on=True, away=False, reasons=()):
        from unittest import mock
        from shoji_widgets import overlays
        e = object.__new__(overlays.EyeRest)
        e.state, e.since = None, 0.0
        e.meetings = type("M", (), {"reasons": set(reasons)})()
        e.away = lambda: away
        for patch in (mock.patch.object(overlays, "prefs", return_value={"eye_rest": on}),
                      mock.patch.object(overlays.Zazen, "STATE", Path(tempfile.mkdtemp()) / "none.json")):
            patch.start()
            self.addCleanup(patch.stop)
        return e

    def test_after_twenty_minutes_at_the_screen(self):
        e = self.make()
        self.assertFalse(e.due(19 * 60))
        self.assertTrue(e.due(20 * 60))

    def test_time_away_starts_again_and_meetings_put_it_off(self):
        e = self.make(away=True)
        self.assertFalse(e.due(30 * 60))
        self.assertEqual(e.since, 30 * 60)
        self.assertFalse(self.make(reasons={"meeting"}).due(30 * 60))
        self.assertTrue(self.make(reasons={"batch"}).due(30 * 60))   # batches keep Silent on all day
        self.assertFalse(self.make(on=False).due(30 * 60))


class Homelab(unittest.TestCase):
    def setUp(self):
        self.hl = load("shoji-homelab")

    def test_a_container_is_well_only_running_and_not_unhealthy(self):
        lvl = lambda state, health="": self.hl.container_level({"state": state, "health": health})
        self.assertEqual([lvl("running"), lvl("running", "healthy"), lvl("running", "starting"),
                          lvl("running", "unhealthy"), lvl("paused"), lvl("exited"), lvl("restarting")],
                         ["ok", "ok", "warn", "bad", "warn", "bad", "bad"])

    def test_units(self):
        lvl = self.hl.unit_level
        self.assertEqual(lvl("timer", {"ActiveState": "active"}, {"Result": "success"})[0], "ok")
        self.assertEqual(lvl("timer", {"ActiveState": "active"}, {"Result": "exit-code"}),
                         ("bad", "last run: exit-code"))
        self.assertEqual(lvl("timer", {"ActiveState": "inactive"}, {})[0], "bad")
        self.assertEqual(lvl("service", {"ActiveState": "active", "SubState": "running"}, {})[0], "ok")
        self.assertEqual(lvl("service", {"ActiveState": "inactive", "Type": "oneshot", "Result": "success"}, {})[0], "ok")
        self.assertEqual(lvl("service", {"ActiveState": "inactive", "Type": "simple", "Result": "success"}, {})[0], "bad")
        self.assertEqual(lvl("service", {"ActiveState": "failed", "Result": "exit-code"}, {}),
                         ("bad", "failed (exit-code)"))
        self.assertEqual(self.hl.unit_cmd("system:docker.service"), (["systemctl"], "docker.service"))

    def test_changes_notify_only_the_difference(self):
        p = lambda key, level="bad": {"key": key, "level": level, "name": key, "why": ""}
        old = {"problems": [p("container:a"), p("unit:b"), p("host:swap", "warn")]}
        new = {"problems": [p("unit:b"), p("endpoint:c")]}
        down, back = self.hl.changes(old, new)
        self.assertEqual(([x["key"] for x in down], [x["key"] for x in back]), (["endpoint:c"], ["container:a"]))
        self.assertEqual(self.hl.changes(None, new), ([], []))   # the first collection says nothing

    def test_the_bar_stays_quiet_until_something_is_down(self):
        self.hl.lucide = lambda name: "S"
        base = {"containers": [{"state": "running"}, {"state": "exited"}], "problems": []}
        self.assertEqual(self.hl.bar(None)["text"], "")   # not set up: waybar hides the module
        self.assertEqual((self.hl.bar(base)["text"], self.hl.bar(base)["class"]), ("S", "ok"))   # the way in stays
        self.assertEqual(self.hl.count(base)["text"], "")
        self.assertEqual(self.hl.bar(base, stale=True)["class"], "warn")
        warn = dict(base, problems=[{"level": "warn", "name": "swap", "why": "95%"}])
        self.assertEqual((self.hl.bar(warn)["class"], self.hl.count(warn)["text"]), ("warn", ""))
        down = dict(base, problems=[{"level": "bad", "name": "a<b", "why": "exited"}])
        self.assertEqual((self.hl.bar(down)["text"], self.hl.bar(down)["class"]), ("S", "down"))
        self.assertEqual(self.hl.count(down)["text"], "1")   # its own label: one font, one centre
        self.assertIn("a&lt;b", self.hl.bar(down)["tooltip"])   # waybar reads the tooltip as markup
        self.assertIn("1/2 containers", self.hl.bar(down)["tooltip"])

    def test_span_and_docker_time(self):
        self.assertEqual([self.hl.span(s) for s in (5, 120, 7200, 3 * 86400)], ["5s", "2m", "2h", "3d"])
        self.assertEqual(self.hl.epoch("0001-01-01T00:00:00Z"), 0)
        self.assertEqual(self.hl.epoch("2026-10-27T00:00:00.123456789Z"), 1793059200)

    def test_backup_age(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(self.hl.backup({"name": "db", "path": d}, 0)["level"], "bad")   # nothing there
            f = Path(d) / "db.sql.gz"
            f.write_text("x")
            mtime = f.stat().st_mtime
            self.assertEqual(self.hl.backup({"name": "db", "path": d}, mtime + 3600)["level"], "ok")
            self.assertEqual(self.hl.backup({"name": "db", "path": d, "max_age_h": 1}, mtime + 7200)["level"], "bad")


class Plugins(unittest.TestCase):
    def test_your_own_popovers_load_and_a_broken_one_is_skipped(self):
        from shoji_widgets import popovers
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "mine.py").write_text(
                "from shoji_widgets.popovers import *\n"
                "class Mine(Listing):\n    name = 'mine'\n    def build(self):\n"
                "        self.header('Mine')\n"
                "        body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)\n"
                "        self.line(body, 'bad', 'thing', 'down', [('rotate-cw', 'Restart', lambda: None)])\n"
                "        self.scrolled(body)\n"
                "POPOVERS = [Mine]\n")
            (Path(d) / "broken.py").write_text("raise RuntimeError('nope')\n")
            old, popovers.PLUGINS = popovers.PLUGINS, Path(d)
            try:
                pops = popovers.Popovers()
            finally:
                popovers.PLUGINS = old
        self.assertIn("mine", pops.items)
        self.assertIn("homelab", pops.items)   # the plugin adds, never replaces the rest
        mine = pops.items["mine"]
        mine.clear()
        mine.build()
        from shoji_widgets.base import name_icons
        self.assertEqual(name_icons(mine.box), [])


class Drawer(unittest.TestCase):
    def make(self, pr):
        from shoji_widgets import drawer, popovers
        from gi.repository import Gtk
        drawer.prefs = lambda: pr
        drawer.save_prefs = lambda **kw: pr.update(kw)

        class Small(drawer.Card):
            size = "small"

        cards = [type(f"C{n}", (Small,), {"name": n, "size": size})
                 for n, size in (("a", "small"), ("wide", "medium"), ("b", "small"), ("c", "small"))]

        class M:
            open = None

        d = drawer.Drawer(M(), cards)
        d.win.get_visible = lambda: False   # no rebuild from move()/hide_card() in a test
        return d, Gtk

    def test_order_and_hidden_come_from_prefs(self):
        pr = {"drawer_order": ["c", "a"], "drawer_hidden": ["b"]}
        d, _ = self.make(pr)
        shown, hidden = d.ordered()
        self.assertEqual(([c.name for c in shown], [c.name for c in hidden]), (["c", "a", "wide"], ["b"]))
        d.move(shown[1], -1)
        self.assertEqual(pr["drawer_order"][:3], ["a", "c", "wide"])
        d.hide_card(hidden[0], hide=False)
        self.assertEqual(pr["drawer_hidden"], [])

    def test_sizes_come_from_prefs_within_what_a_card_offers(self):
        pr = {"drawer_sizes": {"a": "medium", "b": "large", "wide": "small"}}
        d, _ = self.make(pr)
        for c in d.cards:
            c.sizes = ("small", "medium")
        shown, _ = d.ordered()
        self.assertEqual({c.name: c.size for c in shown},
                         {"a": "medium", "b": "small", "wide": "small", "c": "small"})   # b cannot be large
        d.resize(shown[0], "small")
        self.assertEqual(pr["drawer_sizes"]["a"], "small")

    def test_drop_puts_a_card_before_or_after_another(self):
        pr = {"drawer_order": ["a", "wide", "b", "c"]}
        d, _ = self.make(pr)
        d.place("c", "a")
        self.assertEqual(pr["drawer_order"][:4], ["c", "a", "wide", "b"])
        d.place("c", "b", after=True)
        self.assertEqual(pr["drawer_order"][:4], ["a", "wide", "b", "c"])
        d.place("a", "a")   # onto itself: nothing moves
        self.assertEqual(pr["drawer_order"][:4], ["a", "wide", "b", "c"])

    def test_click_then_click_moves_without_dragging(self):
        pr = {"drawer_order": ["a", "wide", "b", "c"]}
        d, _ = self.make(pr)
        cards = {c.name: c for c in d.cards}
        d.editing = True
        d.pick(cards["c"])
        self.assertEqual(d.picked, "c")
        d.pick(cards["a"])
        self.assertEqual((d.picked, pr["drawer_order"][:2]), (None, ["c", "a"]))

    def test_a_small_card_fills_the_half_row_left_before_a_wide_one(self):
        d, Gtk = self.make({})
        d.clear()
        d.build()
        body = d.scroll.get_child().get_child()   # ScrolledWindow > Viewport > Box
        rows = [len(r.get_children()) if isinstance(r, Gtk.Box) and r.get_orientation() == Gtk.Orientation.HORIZONTAL
                else "wide" for r in body.get_children()]
        self.assertEqual(rows, [2, "wide", 1])   # a+b, the wide card, c


class Vpn(unittest.TestCase):
    def test_lists_nm_vpns_and_tailscale(self):
        from shoji_widgets import popovers
        out = {("nmcli",): "Office\\: AWS:1111:vpn:no\nHome wifi:2222:802-11-wireless:yes\nwg0:3333:wireguard:yes\n",
               ("tailscale",): '{"BackendState": "Stopped"}'}
        old_sh, old_which = popovers.sh, popovers.shutil.which
        popovers.sh = lambda *cmd: out[(cmd[0],)]
        popovers.shutil.which = lambda name: "/usr/bin/" + name
        try:
            vpns = popovers.Vpn.all()
        finally:
            popovers.sh, popovers.shutil.which = old_sh, old_which
        self.assertEqual([(v["name"], v["kind"], v["on"]) for v in vpns],
                         [("Office: AWS", "nm", False), ("wg0", "nm", True), ("Tailscale", "tailscale", False)])


class Outcomes(unittest.TestCase):
    """A row says what happened to it; an action on many asks twice; Esc goes back to the drawer."""

    def make(self):
        from shoji_widgets import popovers

        class L(popovers.Listing):
            name = "l"

            def build(self):
                pass

        class M:
            open = None
        lst = L(M())
        lst.refresh_once = lambda: False
        return lst, popovers

    def test_status_meta(self):
        lst, _ = self.make()
        self.assertEqual(lst.status("k", "up 2h"), ("up 2h", None))
        lst.busy.add("k")
        self.assertEqual(lst.status("k")[0], "working…")
        lst.busy.clear()
        lst.outcome["k"] = (False, "Error: no such container")
        self.assertEqual(lst.status("k"), ("✗ Error: no such container", "bad"))
        lst.outcome["k"] = (True, "")
        self.assertEqual(lst.status("k")[0], "✓ done")

    def test_confirm_runs_on_the_second_click_only(self):
        lst, _ = self.make()
        ran = []
        lst.confirm("all", lambda: ran.append(1))
        self.assertEqual((ran, lst.status("all")[1]), ([], "warn"))
        lst.confirm("all", lambda: ran.append(1))
        self.assertEqual(ran, [1])
        self.assertNotIn("all", lst.armed)

    def test_background_keeps_the_exit_status(self):
        import time as _t
        from gi.repository import GLib
        lst, _ = self.make()
        lst.background(["sh", "-c", "echo boom >&2; exit 3"], key="x")
        ctx = GLib.MainContext.default()
        end = _t.time() + 5
        while "x" not in lst.outcome and _t.time() < end:
            ctx.iteration(False)
            _t.sleep(0.02)
        self.assertEqual(lst.outcome.get("x"), (False, "boom"))

    def test_escape_returns_to_where_it_came_from(self):
        _, popovers = self.make()
        mgr = popovers.Popovers.__new__(popovers.Popovers)
        opened = []

        class P:
            def show(self):
                pass

            def hide(self):
                pass

        mgr.items = {"drawer": P(), "homelab": P()}
        mgr.backdrop = type("B", (), {"win": type("W", (), {"show": lambda s: None, "hide": lambda s: None})()})()
        mgr.open, mgr.back = None, None
        mgr.toggle("homelab", back="drawer")
        mgr.escape()
        self.assertEqual((mgr.open, mgr.back), ("drawer", None))
        mgr.escape()
        self.assertIsNone(mgr.open)


class Rest(unittest.TestCase):
    """休 one suggestion per rest, fitting the moment."""

    def setUp(self):
        import random
        from shoji_widgets import rest
        self.rest, self.random = rest, random
        self.tmp = tempfile.TemporaryDirectory()
        rest.LOG = Path(self.tmp.name) / "rest.log"

    def tearDown(self):
        self.tmp.cleanup()

    def pick(self, minutes=5, hour=14, weather="晴", meeting=None, last=None, seed=1):
        now = datetime.datetime(2026, 10, 27, hour, 0)
        return self.rest.pick(minutes, now=now, last=last, ctx={"weather": weather, "meeting": meeting},
                              rng=self.random.Random(seed))

    def ids(self, **kw):
        return {self.pick(seed=n, **kw)["id"] for n in range(300)}

    def test_a_meeting_about_to_start_comes_first(self):
        s = self.pick(meeting={"when": "14:10", "title": "Standup"})
        self.assertEqual((s["id"], s["title"]), ("prep", "Before Standup"))
        self.assertNotEqual(self.pick(meeting={"when": "14:10", "title": "x"}, last="prep")["id"], "prep")

    def test_it_fits_the_minutes_the_hour_and_the_weather(self):
        short = self.ids(minutes=2)
        self.assertFalse(short & {"walk", "meal", "tea", "outside"})   # they need more than 2 minutes
        self.assertNotIn("tea", self.ids(hour=21))                       # no caffeine at night
        self.assertNotIn("outside", self.ids(weather="雨"))              # not into the rain
        self.assertNotIn("outside", self.ids(hour=22))                   # nor into the dark
        long_ = [self.pick(minutes=15, seed=n)["id"] for n in range(300)]
        self.assertGreater(sum(i in ("meal", "longwalk", "floor") for i in long_), 150)   # a long rest, long things

    def test_never_twice_in_a_row(self):
        self.assertNotIn("box", self.ids(last="box"))

    def test_what_you_skip_comes_up_less(self):
        base = [self.pick(seed=n)["cat"] for n in range(600)].count("body")
        for _ in range(8):
            self.rest.log("neck", "skip", now=datetime.datetime(2026, 10, 26, 10, 0))
        after = [self.pick(seed=n)["cat"] for n in range(600)].count("body")
        self.assertLess(after, base * 0.6)
        self.rest.log("box", "done", now=datetime.datetime(2026, 10, 27, 9, 0))
        self.assertEqual(self.rest.taken_today(now=datetime.datetime(2026, 10, 27, 12, 0)), 1)

    def test_every_suggestion_speaks_every_language(self):
        for sid, _cat, _need, _conds, text in self.rest.CATALOG:
            self.assertEqual(set(text), {"en", "id", "ja"}, sid)

    def test_breathing_phases(self):
        from shoji_widgets.restcard import RestCard
        card = RestCard.__new__(RestCard)
        self.assertEqual(card.phase(0)[0], "in")
        self.assertAlmostEqual(card.phase(2)[2], 0.5)       # half way in, half open
        self.assertEqual(card.phase(5)[:2], ("hold", 3))
        self.assertEqual(card.phase(10)[0], "out")
        self.assertEqual(card.phase(16)[0], "in")           # round again


class ZazenLengths(unittest.TestCase):
    def test_prefs_and_the_long_rest(self):
        z = load("shoji-zazen")
        with tempfile.TemporaryDirectory() as d:
            z.PREFS = Path(d) / "prefs.json"
            self.assertEqual(z.lengths(), (25, 5, 15))
            z.PREFS.write_text('{"zazen": "50/10", "zazen_long": 20}')
            self.assertEqual(z.lengths(), (50, 10, 20))
            self.assertEqual([z.rest_minutes(n) for n in (1, 3, 4, 8)], [10, 10, 20, 20])
            z.PREFS.write_text('{"zazen": "50/10", "zazen_long": 0}')
            self.assertEqual(z.rest_minutes(4), 10)


class Css(unittest.TestCase):
    def test_the_stylesheet_parses(self):
        """One unclosed comment makes GTK drop rules from there on; every surface would lose its look."""
        from shoji_widgets import base
        from gi.repository import Gtk, GLib
        colors = base.COLORS.read_bytes() if base.COLORS.exists() else b""
        try:
            Gtk.CssProvider().load_from_data(colors + base.CSS)
        except GLib.Error as e:
            self.fail(f"CSS: {e}")

    def test_letter_spacing_stays_under_one_pixel(self):
        """From 1px, GTK 3 doubles a label's height in an on-screen window (not offscreen, so no
        rendering test sees it): the cards' text sat 8 px low."""
        import re
        for f in (REPO / "widgets/shoji_widgets").glob("*.py"):
            for value in re.findall(r"letter-spacing:\s*([0-9.]+)px", f.read_text()):
                self.assertLess(float(value), 1.0, f.name)


class Accessibility(unittest.TestCase):
    def test_glyph_buttons_take_their_tooltip_as_name(self):
        from shoji_widgets import base
        from gi.repository import Gtk
        box = Gtk.Box()
        named = Gtk.Button(label=base.icon("x"))
        named.set_tooltip_text("Close")
        silent = Gtk.Button(label=base.icon("plus"))
        words = Gtk.Button(label="Save & apply")   # a text button already reads fine
        for b in (named, silent, words):
            box.pack_start(b, False, False, 0)
        self.assertEqual(base.name_icons(box), [silent])
        self.assertEqual(named.get_accessible().get_name(), "Close")
        self.assertFalse(base.is_glyph("Save"))


if __name__ == "__main__":
    unittest.main()
