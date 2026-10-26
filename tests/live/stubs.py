#!/usr/bin/env python3
"""Stand-ins on the live test's PATH, so nothing in the test session reaches your own.

pkill, pgrep and pidof only see processes whose HOME is the test's (SHOJI_LIVE_HOME): Shoji calls
`pkill -x waybar` and the like, and those would otherwise signal your session too. Every other
name (loginctl, xdg-open, nmcli, ...) only writes the call to stub-calls.log: `loginctl
lock-session` would lock your real screen, and `xdg-open` hands URLs to your running browser.

  stubs.py install DIR     write the stand-ins into DIR (put DIR first on PATH)
  stubs.py killall         end every process of the test session (its HOME), for cleanup
"""
import os
import subprocess
import sys
from pathlib import Path

LOGGED = ["loginctl", "systemctl", "systemd-inhibit", "nmcli", "bluetoothctl", "rfkill", "powerprofilesctl",
          "brightnessctl", "wpctl", "pactl", "pw-play", "paplay", "xdg-open", "gio", "gtk-launch", "code",
          "spicetify", "google-chrome", "google-chrome-stable", "chromium", "firefox", "wlogout", "reboot",
          "poweroff", "shutdown", "hyprsunset", "wf-recorder", "pavucontrol", "nm-connection-editor",
          "blueman-manager", "gnome-calendar", "gnome-control-center", "thunar", "ghostty",
          "gsettings", "dconf", "awww", "hyprpaper", "swaybg"]
FILTERED = ["pkill", "pgrep", "pidof"]
REAL_PGREP, REAL_KILL = "/usr/bin/pgrep", "/usr/bin/kill"


def ours(pid):
    try:
        env = Path(f"/proc/{pid}/environ").read_bytes().split(b"\0")
    except OSError:
        return False
    return f"HOME={os.environ['SHOJI_LIVE_HOME']}".encode() in env and pid != os.getpid()


def pgrep(args):
    out = subprocess.run([REAL_PGREP, *args], capture_output=True, text=True).stdout.split()
    return [int(p) for p in out if ours(int(p))]


def main():
    name = os.path.basename(sys.argv[0])
    args = sys.argv[1:]
    if name == "stubs.py":
        if args[:1] == ["install"]:
            d = Path(args[1])
            d.mkdir(parents=True, exist_ok=True)
            log = d.parent / "stub-calls.log"
            for n in LOGGED:
                (d / n).write_text(f'#!/bin/sh\necho "{n} $*" >> "{log}"\nexit 0\n')
                (d / n).chmod(0o755)
            for n in FILTERED:
                (d / n).unlink(missing_ok=True)
                (d / n).symlink_to(Path(__file__).resolve())
        elif args[:1] == ["killall"]:
            mine = [p for p in (int(x) for x in os.listdir("/proc") if x.isdigit()) if ours(p)]
            for p in mine:
                try:
                    os.kill(p, 9)
                except OSError:
                    pass
            print(len(mine))
        return
    if name == "pgrep":
        pids = pgrep(args)
        print("\n".join(map(str, pids))) if pids else None
        sys.exit(0 if pids else 1)
    if name == "pidof":
        pids = [p for n in args if not n.startswith("-") for p in pgrep(["-x", n])]
        print(" ".join(map(str, pids))) if pids else None
        sys.exit(0 if pids else 1)
    if name == "pkill":
        sig = next((a for a in args if a.startswith("-") and (a[1:2].isupper() or a[1:2].isdigit())), "-TERM")
        rest = [a for a in args if a != sig]
        pids = pgrep(rest)
        for p in pids:
            subprocess.run([REAL_KILL, sig, str(p)], capture_output=True)
        sys.exit(0 if pids else 1)


if __name__ == "__main__":
    main()
