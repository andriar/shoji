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
        m.card = type("C", (), {"show": lambda _s, i: shown.append(i["title"])})()
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


if __name__ == "__main__":
    unittest.main()
