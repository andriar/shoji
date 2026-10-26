"""A pretend MPRIS player for the live test's demo recordings: one track, playing, with a
generated cover (written to the path given as the first argument). Only the test's session bus
sees it."""
import sys, time
import cairo
from gi.repository import Gio, GLib

COVER = sys.argv[1]
s = cairo.ImageSurface(cairo.FORMAT_RGB24, 640, 640); c = cairo.Context(s)
g = cairo.LinearGradient(0, 0, 0, 640); g.add_color_stop_rgb(0, 0.80, 0.36, 0.26); g.add_color_stop_rgb(1, 0.45, 0.14, 0.12)
c.set_source(g); c.paint()
c.set_source_rgba(0.98, 0.93, 0.85, 0.9); c.set_line_width(26); c.set_line_cap(cairo.LINE_CAP_ROUND)
c.arc(320, 300, 170, 2.3, 2.3 + 5.4); c.stroke()
c.select_font_face("Kaisei Opti", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD); c.set_font_size(54)
c.move_to(214, 590); c.show_text("紅 葉 の 道")
s.write_to_png(COVER)

XML = """<node>
<interface name="org.mpris.MediaPlayer2">
 <method name="Raise"/><method name="Quit"/>
 <property name="Identity" type="s" access="read"/><property name="CanQuit" type="b" access="read"/>
 <property name="CanRaise" type="b" access="read"/><property name="HasTrackList" type="b" access="read"/>
 <property name="SupportedUriSchemes" type="as" access="read"/><property name="SupportedMimeTypes" type="as" access="read"/>
</interface>
<interface name="org.mpris.MediaPlayer2.Player">
 <method name="PlayPause"/><method name="Play"/><method name="Pause"/><method name="Stop"/>
 <method name="Next"/><method name="Previous"/>
 <method name="Seek"><arg name="Offset" type="x" direction="in"/></method>
 <method name="SetPosition"><arg name="TrackId" type="o" direction="in"/><arg name="Position" type="x" direction="in"/></method>
 <property name="PlaybackStatus" type="s" access="read"/><property name="Metadata" type="a{sv}" access="read"/>
 <property name="Position" type="x" access="read"/><property name="Volume" type="d" access="readwrite"/>
 <property name="Rate" type="d" access="read"/><property name="MinimumRate" type="d" access="read"/><property name="MaximumRate" type="d" access="read"/>
 <property name="CanGoNext" type="b" access="read"/><property name="CanGoPrevious" type="b" access="read"/>
 <property name="CanPlay" type="b" access="read"/><property name="CanPause" type="b" access="read"/>
 <property name="CanSeek" type="b" access="read"/><property name="CanControl" type="b" access="read"/>
</interface></node>"""
start = time.monotonic() - 83
LENGTH = 241_000_000
def props(iface, name):
    if name == "Identity": return GLib.Variant("s", "Demo player")
    if name in ("CanQuit", "CanRaise", "HasTrackList"): return GLib.Variant("b", False)
    if name in ("SupportedUriSchemes", "SupportedMimeTypes"): return GLib.Variant("as", [])
    if name == "PlaybackStatus": return GLib.Variant("s", "Playing")
    if name == "Metadata":
        return GLib.Variant("a{sv}", {
            "mpris:trackid": GLib.Variant("o", "/demo/track/1"), "mpris:length": GLib.Variant("x", LENGTH),
            "mpris:artUrl": GLib.Variant("s", "file://" + COVER), "xesam:title": GLib.Variant("s", "Momiji no Michi"),
            "xesam:artist": GLib.Variant("as", ["Kōyō Trio"]), "xesam:album": GLib.Variant("s", "Shoji Sessions")})
    if name == "Position": return GLib.Variant("x", int((time.monotonic() - start) * 1e6) % LENGTH)
    if name in ("Volume", "Rate", "MinimumRate", "MaximumRate"): return GLib.Variant("d", 1.0)
    return GLib.Variant("b", True)
node = Gio.DBusNodeInfo.new_for_xml(XML)
def on_bus(conn, name):
    for iface in node.interfaces:
        conn.register_object("/org/mpris/MediaPlayer2", iface,
                             lambda *a: a[-1].return_value(None),
                             lambda c, s, p, i, n: props(i, n), None)
Gio.bus_own_name(Gio.BusType.SESSION, "org.mpris.MediaPlayer2.demo", Gio.BusNameOwnerFlags.NONE, on_bus, None, None)
GLib.MainLoop().run()
