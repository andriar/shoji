#!/usr/bin/env python3
"""The live test's scenarios, run inside the test session by run.sh (its HOME, runtime dir, bus
and Hyprland instance). Each one drives Shoji the way a user would and checks what happened on
the screen or in the state files. Prints one line per check; exits 1 when any check failed."""
import datetime
import json
import os
import subprocess
import sys
import time
from pathlib import Path

HOME = Path(os.environ["HOME"])
RUN = Path(os.environ["XDG_RUNTIME_DIR"])
WORK = Path(os.environ["SHOJI_LIVE_WORK"])
SHOTS = WORK / "shots"
OUT = os.environ.get("SHOJI_LIVE_OUTPUT", "SHOJI")
BIN = HOME / ".local/bin"
results = []


def sh(*cmd, timeout=15):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout).stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        return ""


def hypr_eval(lua):
    return sh("hyprctl", "eval", lua)


def layers(output=None):
    """Layer namespaces on every output, or on one (the test's screen is OUT)."""
    try:
        data = json.loads(sh("hyprctl", "layers", "-j") or "{}")
    except ValueError:
        return []
    return [l["namespace"] for name, mon in data.items() if output in (None, name)
            for lv in mon["levels"].values() for l in lv]


def wait(pred, timeout, step=0.5):
    end = time.time() + timeout
    while time.time() < end:
        v = pred()
        if v:
            return v
        time.sleep(step)
    return pred()


def check(name, ok, detail=""):
    results.append({"check": name, "ok": bool(ok), "detail": detail})
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"  ({detail})" if detail else ""), flush=True)


def shot(name):
    sh("grim", "-o", OUT, str(SHOTS / f"{name}.png"))


def prefs(**kw):
    p = HOME / ".config/shoji/prefs.json"
    d = json.loads(p.read_text()) if p.exists() else {}
    d.update(kw)
    p.write_text(json.dumps(d, indent=1))


def dnd():
    return sh("swaync-client", "-D") == "true"


def widgets_pid():
    try:
        return int((RUN / "hypr-widgets.pid").read_text())
    except (OSError, ValueError):
        return 0


def restart_widgets():
    old = widgets_pid()
    if old:
        os.kill(old, 15)
        wait(lambda: not Path(f"/proc/{old}").exists(), 10)
    hypr_eval('hl.exec_cmd("~/.local/bin/hypr-widgets")')
    return wait(lambda: widgets_pid() not in (0, old) and widgets_pid(), 15)


def option(name):
    try:
        v = json.loads(sh("hyprctl", "getoption", name, "-j"))
    except ValueError:
        return None
    return v.get("float", v.get("int", v.get("bool")))


def atspi_click(name, timeout=40):
    """Press a button by its accessible name, the way a screen reader does (no input device here)."""
    code = r'''
import sys, gi
gi.require_version("Atspi", "2.0")
from gi.repository import Atspi
def walk(o, d=0):
    if o is None or d > 30: return None
    try:
        if o.get_role() == Atspi.Role.PUSH_BUTTON and o.get_name() == sys.argv[1]: return o
        for i in range(o.get_child_count()):
            r = walk(o.get_child_at_index(i), d + 1)
            if r: return r
    except Exception: return None
desk = Atspi.get_desktop(0)
for i in range(desk.get_child_count()):
    b = walk(desk.get_child_at_index(i))
    if b:
        print(b.get_action_iface().do_action(0)); break
'''
    return wait(lambda: sh(sys.executable, "-c", code, name) == "True", timeout, step=2)


def screen_alone():
    """`shoji apply` reloads Hyprland, which brings the hidden window's output back: switch it off
    again, so sizes and positions come from the test screen alone."""
    def alone():
        try:
            m = {x["name"]: x for x in json.loads(sh("hyprctl", "monitors", "-j"))}
        except ValueError:
            return False
        return set(m) == {OUT} and m[OUT]["width"] == 1600
    for _ in range(20):
        hypr_eval(f'hl.monitor({{ output = "{OUT}", mode = "1600x900@60", position = "4000x0", scale = 1 }})')
        hypr_eval('hl.monitor({ output = "WAYLAND-1", disabled = true })')
        if alone():
            break
        time.sleep(0.5)
    hypr_eval('hl.dispatch(hl.dsp.cursor.move({ x = 4800, y = 450 }))')
    sh("hyprctl", "dismissnotify")   # the debug-session notice
    return alone()


def unlock():
    """SIGUSR1 unlocks hyprlock, but one still loading its pictures misses it: ask again each second."""
    for _ in range(12):
        pids = sh("pidof", "hyprlock").split()
        if not pids:
            return True
        for pid in pids:
            try:
                os.kill(int(pid), 10)
            except OSError:
                pass
        time.sleep(1)
    return not sh("pidof", "hyprlock")


# ------------------------------------------------------------------ scenarios
def boot():
    print("boot")
    check("hypr-widgets is up", wait(widgets_pid, 20))
    check("swaync answers", wait(lambda: sh("swaync-client", "-D") in ("true", "false"), 20))


def labels_on_screen():
    """GTK 3 doubles a label's height on screen (never offscreen) when letter-spacing >= 1px."""
    print("labels on screen")
    code = r'''
import sys
sys.path.insert(0, sys.argv[1])
from shoji_widgets.base import *
Gtk.StyleContext.add_provider_for_screen(Gdk.Screen.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_USER)
load_css()
win = Gtk.Window(); box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL); win.add(box)
ls = []
for cls in ("label-small", "season", "haiku", "key-head", "title", "muted", "mono", "wk", "display"):
    l = label("霜始降 · IN 3 MIN 18:10", cls); box.pack_start(l, False, False, 0); ls.append((cls, l))
win.show_all()
def done():
    def box_h(l):   # CSS padding and border are the label's own; only the text part is checked
        sc = l.get_style_context(); st = sc.get_state(); pd, bd = sc.get_padding(st), sc.get_border(st)
        return pd.top + pd.bottom + bd.top + bd.bottom
    print(",".join(f"{c}:{l.get_preferred_height()[0] - box_h(l)}:{l.get_layout().get_pixel_size()[1]}" for c, l in ls)); Gtk.main_quit()
GLib.timeout_add(800, done); Gtk.main()
'''
    out = sh(sys.executable, "-c", code, str(HOME / ".local/share/shoji/widgets"), timeout=20)
    rows = [r.split(":") for r in out.split(",") if r.count(":") == 2]
    tall = [f"{c} {p}>{l}" for c, p, l in rows if int(p) > int(l) + 2]
    check("labels ask for their text's height", rows and not tall, ", ".join(tall) or f"{len(rows)} classes")


def meeting_starts():
    print("a meeting runs")
    check("Silent turns on during the event", wait(dnd, 20))
    check("reminder card for the next event", wait(lambda: "hypr-card" in layers(), 20))
    shot("reminder-card")


def alt_tab():
    print("Alt+Tab")
    win = WORK / "window.py"   # a plain window whose app id is its first argument
    win.write_text('import gi, sys\ngi.require_version("Gtk", "3.0")\nfrom gi.repository import Gtk, GLib\n'
                   'GLib.set_prgname(sys.argv[1])\nw = Gtk.Window(title=sys.argv[1])\nw.show_all()\nGtk.main()\n')
    for app in ("live.first", "live.second"):
        hypr_eval(f'hl.exec_cmd("{sys.executable} {win} {app}")')
        wait(lambda a=app: a in sh("hyprctl", "clients"), 15)

    def focused():
        try:
            return next(c["class"] for c in json.loads(sh("hyprctl", "clients", "-j")) if c["focusHistoryID"] == 0)
        except (ValueError, StopIteration):
            return ""
    for app in ("live.first", "live.second"):
        hypr_eval(f'hl.dispatch(hl.dsp.focus({{ window = "class:{app}" }}))')
        wait(lambda a=app: focused() == a, 5)
    before = focused()
    hypr_eval('hl.exec_cmd("~/.local/bin/hypr-switch")')
    after = wait(lambda: focused() if focused() != before else "", 8)
    check("a quick Alt+Tab goes to the previous window", after == "live.first", f"{before} → {after or before}")
    sh("pkill", "-f", "live.first")
    sh("pkill", "-f", "live.second")


def idle_ink_and_lock():
    """The shipped hypridle.conf, its minutes made seconds: ink, then the lock over the same picture."""
    print("idle → ink → lock")
    before = option("cursor:inactive_timeout")
    hypr_eval(f'hl.exec_cmd("hypridle -c {WORK}/hypridle.conf")')
    check("idle starts the ink screen", wait(lambda: "shoji-ink" in layers(), 20))
    check("the pointer hides over the ink", wait(lambda: option("cursor:inactive_timeout") == 1, 5))
    time.sleep(3)
    shot("ink")
    locked = wait(lambda: sh("pidof", "hyprlock"), 25)
    check("the lock follows", locked)
    check("the lock keeps the ink's picture", (HOME / ".cache/shoji/lock-ink.png").exists())
    time.sleep(2)
    shot("lock")
    check("unlocked", unlock())
    sh("pkill", "-x", "hypridle")
    check("the pointer setting is back", wait(lambda: option("cursor:inactive_timeout") == before, 5),
          f"{option('cursor:inactive_timeout')} vs {before}")


def meeting_ends(end_at):
    print("a restart mid-meeting, then the meeting ends")
    check("hypr-widgets restarted mid-meeting", restart_widgets())
    check("Silent stays on through the restart", wait(dnd, 10))
    wait_s = max(0, (end_at - datetime.datetime.now()).total_seconds()) + 45
    print(f"       (waiting up to {int(wait_s)} s for the event to end)", flush=True)
    check("Silent turns off after the event", wait(lambda: not dnd(), wait_s, step=2))


def batches():
    print("notification batches")
    prefs(batch=1)
    sh(sys.executable, str(HOME / ".config/shoji/gen_swaync.py"))
    sh("swaync-client", "-R")
    time.sleep(1)
    cards = layers().count("hypr-card")
    for app in ("Slack", "Slack", "Mail"):
        sh("notify-send", "-a", app, f"live {app}", "hello")
    sh("notify-send", "-u", "critical", "-a", "Pager", "live critical", "now")
    time.sleep(1)
    log = RUN / "shoji-batch.log"
    noted = log.read_text().splitlines() if log.exists() else []
    check("Silent holds while batching", wait(dnd, 35))
    check("batched notifications are noted, critical ones are not", [l.split("\t")[1] for l in noted] == ["Slack", "Slack", "Mail"],
          ",".join(l.split("\t")[1] for l in noted))
    check("the batch card comes at the next minute", wait(lambda: layers().count("hypr-card") > cards, 95, step=2))
    check("the log starts again", not log.read_text().strip())
    shot("batch-card")
    prefs(batch=0)
    sh(sys.executable, str(HOME / ".config/shoji/gen_swaync.py"))
    sh("swaync-client", "-R")


def end_of_day():
    print("仕舞い the end of the day")
    prefs(shimai=datetime.datetime.now().strftime("%H:%M"))
    restart_widgets()
    check("Done for today, pressed through AT-SPI", atspi_click("Done for today", 50))
    try:
        until = json.loads((RUN / "shoji-shimai.json").read_text())["until"]
    except (OSError, ValueError, KeyError):
        until = 0
    morning = datetime.datetime.combine(datetime.date.today() + datetime.timedelta(days=1), datetime.time(7))
    check("Silent until 07:00 tomorrow", abs(until - morning.timestamp()) < 1 and wait(dnd, 35),
          datetime.datetime.fromtimestamp(until).strftime("%a %H:%M") if until else "no state")
    (RUN / "shoji-shimai.json").unlink(missing_ok=True)
    prefs(shimai="")


def eye_rest():
    print("遠 rest your eyes")
    prefs(eye_rest=True)
    restart_widgets()
    check("the 遠 ensō shows after the set time", wait(lambda: "hypr-zazen" in layers(), 90, step=2))
    shot("eye-rest")
    check("and goes after 20 seconds", wait(lambda: "hypr-zazen" not in layers(), 35))
    prefs(eye_rest=False)


def use_palette(palette):
    """Apply a palette sized on the test screen: wallpaper shown, panel placed, notices cleared."""
    (HOME / ".cache/shoji/lock.png").unlink(missing_ok=True)   # a fresh lock picture at this size
    screen_alone()
    sh(sys.executable, str(BIN / "shoji"), "apply", palette, timeout=60)
    check(f"the test screen alone after apply ({palette})", screen_alone())
    sh(sys.executable, str(BIN / "shoji"), "apply", palette, timeout=60)   # again, sized on this screen
    screen_alone()
    sh(sys.executable, str(HOME / ".config/shoji/gen_swaync.py"))   # the panel's margin for this width
    sh("swaync-client", "-R")
    sh(os.environ["SHOJI_LIVE_AWWW"], "img", str(HOME / f"Pictures/Wallpapers/shoji-{palette}.png"),
       "--transition-type", "none")
    sh("pkill", "-SIGUSR2", "-x", "waybar")
    restart_widgets()
    sh("swaync-client", "-C")   # the palette's own notice off the desktop


def fifo(line):
    """A line to hypr-widgets, the way hypr-pop and hypr-osd send them."""
    with open(RUN / "hypr-osd.fifo", "w") as f:
        f.write(line + "\n")


def demo_gif():
    """The README's demo.gif: Koyomi, now playing, the launcher, the volume ensō and zazen, about
    eighteen seconds recorded on the test screen and turned into a GIF with its own palette."""
    print("demo.gif")
    import threading
    repo = Path(os.environ["SHOJI_LIVE_REPO"])
    use_palette("aizome")
    hypr_eval(f'hl.exec_cmd("{sys.executable} {repo}/tests/live/fakeplayer.py {WORK}/cover.png")')
    check("the demo player plays", wait(lambda: sh("playerctl", "status") == "Playing", 15))
    # the meeting reminder (it comes a few seconds after hypr-widgets starts) would sit in the corner
    if wait(lambda: "hypr-card" in layers(OUT), 15):
        check("the reminder dismissed", atspi_click("Dismiss", 20) and wait(lambda: "hypr-card" not in layers(OUT), 5))
    for app, title, body in (("Mail", "Mei Tanaka", "Photos from the walk to the shrine"),
                             ("Builds", "Build finished", "web-app #142 passed in 3 min")):
        sh("notify-send", "-a", app, title, body)
    time.sleep(7)   # their toasts go; they stay in the panel
    time.sleep(3)   # the bar's now-playing title settles
    frames = WORK / "frames"
    frames.mkdir(exist_ok=True)
    stop, stamps = threading.Event(), []

    def record():
        while not stop.is_set():
            t0 = time.monotonic()
            sh("grim", "-o", OUT, "-s", "0.75", "-t", "ppm", str(frames / f"{len(stamps):05d}.ppm"))
            stamps.append(t0)
            time.sleep(max(0.0, 0.1 - (time.monotonic() - t0)))
    rec = threading.Thread(target=record)
    rec.start()
    time.sleep(1.5)
    sh("swaync-client", "-op")                      # Koyomi fades in beside the panel
    time.sleep(3.0)
    sh("swaync-client", "-cp")
    time.sleep(0.8)
    fifo("pop\tmedia")                              # now playing
    time.sleep(2.6)
    fifo("pop\tmedia")
    time.sleep(0.6)
    for k in range(1, 6):                           # the launcher, typed into
        fifo("pop\tlauncher\t" + "files"[:k])
        time.sleep(0.28)
    time.sleep(1.3)
    fifo("pop\tlauncher")
    time.sleep(0.6)
    for level in range(40, 78, 5):                  # the volume ensō glides
        fifo(f"\U000f057e\tVolume\t{level}\t0")   # as hypr-osd sends it: icon, title, percent, muted
        time.sleep(0.16)
    time.sleep(1.8)
    sh(sys.executable, str(BIN / "shoji-zazen"), "start")   # zazen dims everything
    time.sleep(2.8)
    sh(sys.executable, str(BIN / "shoji-zazen"), "stop")
    time.sleep(1.2)
    stop.set()
    rec.join()
    fps = round((len(stamps) - 1) / (stamps[-1] - stamps[0]), 2) if len(stamps) > 1 else 10
    out = repo / "docs/screenshots/demo.gif"
    sh("ffmpeg", "-y", "-loglevel", "error", "-framerate", str(fps), "-i", str(frames / "%05d.ppm"),
       "-vf", "split[a][b];[a]palettegen=max_colors=128:stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=4:diff_mode=rectangle",
       "-loop", "0", str(out), timeout=300)
    check("demo.gif written", out.exists() and out.stat().st_size > 100_000,
          f"{len(stamps)} frames at {fps} fps, {out.stat().st_size // 1024 if out.exists() else 0} KiB")


def readme_shots():
    """The README's screenshots, on the demo data: the desktop in a dark and a light palette, Koyomi
    open, and the lock screen (hyprlock itself). Saved to docs/screenshots."""
    print("README screenshots")
    docs = Path(os.environ["SHOJI_LIVE_REPO"]) / "docs/screenshots"
    awww = os.environ["SHOJI_LIVE_AWWW"]
    hypr_eval(f'hl.exec_cmd("{awww}-daemon")')
    wait(lambda: "awww-daemon" in layers(), 15)
    hypr_eval('hl.exec_cmd("waybar")')
    check("the bar is up", wait(lambda: "waybar" in layers(), 20))
    for name, palette in (("desktop", "aizome"), ("desktop-light", "hiru")):
        use_palette(palette)
        time.sleep(3)
        shot(name)
        if palette == "aizome":
            sh(sys.executable, str(BIN / "shoji-zazen"), "start")
            check("zazen's ensō", wait(lambda: "hypr-zazen" in layers(OUT), 10))
            time.sleep(2)
            shot("zazen")
            sh(sys.executable, str(BIN / "shoji-zazen"), "stop")
            wait(lambda: "hypr-zazen" not in layers(OUT), 10)
            sh("swaync-client", "-C")
        for app, title, body in (("Mail", "Mei Tanaka", "Photos from the walk to the shrine"),
                                 ("Builds", "Build finished", "web-app #142 passed in 3 min")):
            sh("notify-send", "-a", app, title, body)   # demo notifications for the panel
        time.sleep(1)
        sh("swaync-client", "-op")
        check(f"the panel opens ({palette})", wait(lambda: "swaync-control-center" in layers(OUT), 10), ",".join(layers(OUT)))
        check(f"Koyomi beside it ({palette})", wait(lambda: "hypr-calendar" in layers(OUT), 10), ",".join(layers(OUT)))
        time.sleep(1.5)
        shot(f"{name}-koyomi")
        sh("swaync-client", "-cp")
        time.sleep(1)
        hypr_eval('hl.exec_cmd("hyprlock")')
        locked = wait(lambda: sh("pidof", "hyprlock"), 15)
        check(f"the lock screen shows ({palette})", locked)
        time.sleep(2.5)
        shot(f"lock-{palette}")
        check(f"unlocked ({palette})", unlock(), sh("pidof", "hyprlock"))
    for f in SHOTS.glob("*.png"):
        (docs / f.name).write_bytes(f.read_bytes())
    print(f"       copied {len(list(SHOTS.glob('*.png')))} screenshots to {docs}")


def main():
    end_at = datetime.datetime.fromisoformat(os.environ["SHOJI_LIVE_MEETING_END"])
    SHOTS.mkdir(parents=True, exist_ok=True)
    steps = (boot, labels_on_screen, meeting_starts, alt_tab, idle_ink_and_lock,
             lambda: meeting_ends(end_at), batches, end_of_day, eye_rest)
    if os.environ.get("SHOJI_LIVE_SHOTS") == "1":
        steps = (boot, readme_shots, demo_gif)
    for step in steps:
        try:
            step()
        except Exception as e:  # one broken scenario must not hide the others
            check(getattr(step, "__name__", "step"), False, f"{type(e).__name__}: {e}")
    (WORK / "results.json").write_text(json.dumps(results, indent=1, ensure_ascii=False))
    failed = [r for r in results if not r["ok"]]
    print(f"\n{len(results) - len(failed)}/{len(results)} checks passed · screenshots: {SHOTS}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
