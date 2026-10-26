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


if __name__ == "__main__":
    unittest.main()
