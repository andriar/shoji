"""Constants, the one motion scale, palette and prefs helpers, GTK CSS, layer windows, Glide and
the ensō drawing that every surface shares."""
import calendar as cal_mod
import datetime
import importlib.machinery
import json
import math
import os
import shutil
import subprocess
import sys
import threading
import time
import urllib.parse
import urllib.request
from pathlib import Path

import cairo
import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("GtkLayerShell", "0.1")
gi.require_version("PangoCairo", "1.0")
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import Gdk, GdkPixbuf, GLib, Gio, Gtk, GtkLayerShell as Layer, Pango, PangoCairo  # noqa: E402

try:  # events and tasks for Koyomi come from Evolution Data Server (package gir1.2-ecal-2.0); optional
    gi.require_version("ECal", "2.0")
    gi.require_version("EDataServer", "1.2")
    gi.require_version("ICalGLib", "3.0")
    from gi.repository import ECal, EDataServer, ICalGLib  # noqa: E402
except (ValueError, ImportError):
    ECal = None

HOME = Path.home()
RUN = Path(os.environ.get("XDG_RUNTIME_DIR", "/tmp"))
FIFO = RUN / "hypr-osd.fifo"
PIDFILE = RUN / "hypr-widgets.pid"
COLORS = HOME / ".config/waybar/colors.css"
THEME = HOME / ".config/shoji/current.json"
PREFS = HOME / ".config/shoji/prefs.json"
SHOJI = str(HOME / ".local/bin/shoji")
LUCIDE = json.loads((HOME / ".local/share/fonts/Shoji/lucide-info.json").read_text())
CC_WIDTH = 420      # swaync control-center-width
GAP = 8
OSD_MS = 1400
# one motion scale for Shoji: state changes 150 ms, content that moves 180 ms (ease-out)
STATE_MS, CONTENT_MS = 150, 180
OSD_TWEEN_MS = CONTENT_MS
# reduced motion (hypr-motion, Super+Shift+M; prefs "reduced_motion"): no glides, slides, fades or
# tweens; states and positions change at once. Updated live through the FIFO ("motion<TAB>on|off").
MOTION = {"reduced": False}


def reduced():
    return MOTION["reduced"]
WEEK_K = "日月火水木金土"  # Sunday first, like the calendar grid
AGENDA_ROWS = 4     # agenda lines under the grid; the card keeps one height (gen_swaync CAL_HEIGHT)

# 七十二候 lives in shoji (stdlib only), so `shoji greet` can use it from a shell without GTK
_shoji = importlib.machinery.SourceFileLoader("shoji_ko", SHOJI).load_module()
KO, micro_season = _shoji.KO, _shoji.micro_season
haiku = getattr(_shoji, "haiku", lambda day=None: ("", ""))   # an older shoji: no poem, no crash


# ---- interface language: prefs "lang" = "en" (default), "id" (Bahasa Indonesia) or "ja" (日本語)
LANG = {"code": "en"}
STRINGS = {  # English text -> (Indonesian, Japanese)
    "Open in GNOME Calendar": ("Buka di GNOME Calendar", "GNOME Calendar で開く"),
    "today": ("hari ini", "今日"), "tomorrow": ("besok", "明日"), "yesterday": ("kemarin", "昨日"),
    "Nothing scheduled": ("Tidak ada jadwal", "予定なし"), "+{n} more": ("+{n} lagi", "他 {n} 件"),
    "Network": ("Jaringan", "ネットワーク"), "Bluetooth · right-click: devices": ("Bluetooth · klik kanan: perangkat", "Bluetooth · 右クリック：デバイス"),
    "Night light": ("Lampu malam", "夜間モード"), "Silent (do not disturb)": ("Senyap (jangan ganggu)", "通知オフ"),
    "Keep awake": ("Tetap menyala", "スリープしない"), "Theme": ("Tema", "テーマ"), "Power menu": ("Menu daya", "電源メニュー"),
    "Copied": ("Tersalin", "コピー済み"), "Open": ("Buka", "開く"), "Show in folder": ("Tampilkan di folder", "フォルダで表示"),
    "Delete": ("Hapus", "削除"), "in {m} min": ("{m} menit lagi", "あと {m} 分"), "Join": ("Gabung", "参加"),
    "Dismiss": ("Tutup", "閉じる"), "Mute": ("Bisukan", "ミュート"), "Unmute": ("Bunyikan", "ミュート解除"),
    "Sound": ("Suara", "サウンド"), "OUTPUT": ("KELUARAN", "出力"), "INPUT": ("MASUKAN", "入力"),
    "Sound settings…": ("Pengaturan suara…", "サウンド設定…"), "Network settings…": ("Pengaturan jaringan…", "ネットワーク設定…"),
    "Bluetooth settings…": ("Pengaturan Bluetooth…", "Bluetooth 設定…"), "No paired devices": ("Belum ada perangkat", "ペアリング済みデバイスなし"),
    "Bar, panels, launcher, lock screen, terminal, GTK apps and wallpaper.":
        ("Bar, panel, peluncur, layar kunci, terminal, aplikasi GTK, dan wallpaper.", "バー、パネル、ランチャー、ロック画面、ターミナル、GTK アプリ、壁紙。"),
    "in use": ("dipakai", "使用中"), "dark": ("gelap", "ダーク"), "light": ("terang", "ライト"),
    "Remove this palette": ("Hapus palet ini", "このパレットを削除"), "Your own": ("Buatanmu", "自分で作る"),
    "a ground and an accent": ("warna dasar dan aksen", "地色とアクセント"),
    "Follow the sun: light palette 06:00–18:00, your dark one after":
        ("Ikuti matahari: terang 06:00–18:00, palet gelapmu setelahnya", "太陽に合わせる：06:00–18:00 はライト、その後はダーク"),
    "Name it (e.g. Sumi)": ("Beri nama (mis. Sumi)", "名前（例：墨）"),
    "Cancel": ("Batal", "キャンセル"), "Save & apply": ("Simpan & pakai", "保存して適用"),
    "No battery": ("Tidak ada baterai", "バッテリーなし"), "POWER MODE": ("MODE DAYA", "電源モード"),
    "Power settings…": ("Pengaturan daya…", "電源設定…"), "Search apps": ("Cari aplikasi", "アプリを検索"),
    "FREQUENT · ALL APPS": ("SERING · SEMUA APLIKASI", "よく使う · すべてのアプリ"), "RESULTS": ("HASIL", "結果"),
    "No app matches": ("Tidak ada aplikasi yang cocok", "一致するアプリなし"), "Search shortcuts": ("Cari pintasan", "ショートカットを検索"),
    "Click one to run it · type to search": ("Klik untuk menjalankan · ketik untuk mencari", "クリックで実行 · 入力で検索"),
    "No shortcut matches": ("Tidak ada pintasan yang cocok", "一致するショートカットなし"),
    "Media": ("Media", "メディア"), "Nothing playing": ("Tidak ada yang diputar", "再生中なし"),
    "Search clipboard history": ("Cari riwayat clipboard", "クリップボード履歴を検索"), "Clear all": ("Hapus semua", "すべて消去"),
    "Sure? Clear": ("Yakin? Hapus", "本当に消去"), "Nothing copied yet": ("Belum ada yang disalin", "まだコピーなし"),
    "Delete from history": ("Hapus dari riwayat", "履歴から削除"), "No windows": ("Tidak ada jendela", "ウィンドウなし"),
    "↑↓ move · ↵ copy · Del delete · Esc close": ("↑↓ pindah · ↵ salin · Del hapus · Esc tutup", "↑↓ 移動 · ↵ コピー · Del 削除 · Esc 閉じる"),
    "Language": ("Bahasa", "言語"),
    "Preferences": ("Preferensi", "設定"), "Preferences…": ("Preferensi…", "設定…"),
    "Workspace numbers": ("Nomor workspace", "ワークスペース番号"),
    "Reduced motion": ("Kurangi gerak", "動きを減らす"),
    "Nothing animates anywhere (Super+Shift+M)": ("Tidak ada animasi di mana pun (Super+Shift+M)", "すべてのアニメーションを止める（Super+Shift+M）"),
    "Ink screen when idle": ("Layar tinta saat diam", "離席中の墨の画面"),
    "Ink blooms on the ground after 8 minutes; the lock follows": ("Tinta mekar setelah 8 menit; lalu layar terkunci", "8 分後に墨がにじみ、続いてロック"),
    "Quiet in meetings": ("Senyap saat rapat", "会議中は静かに"),
    "Silent while an event runs or the screen is shared": ("Senyap selama ada acara atau layar dibagikan", "予定の間と画面共有中は通知オフ"),
    "Rin bell": ("Lonceng rin", "鈴"),
    "A soft bell for critical notifications and reminders": ("Lonceng lembut untuk notifikasi penting dan pengingat", "重要な通知とリマインダーに小さな鈴"),
    "Terminal greeting": ("Sapaan terminal", "ターミナルのあいさつ"),
    "Today's 候 and what is next, in each new terminal": ("候 hari ini dan agenda berikutnya di tiap terminal baru", "新しいターミナルに今日の候と次の予定"),
    "End of the day": ("Akhir hari kerja", "仕舞い"), "Off": ("Mati", "オフ"),
    "{n} events": ("{n} acara", "予定 {n} 件"), "{n} in the panel": ("{n} di panel", "通知 {n} 件"),
    "Tomorrow {when} · {title}": ("Besok {when} · {title}", "明日 {when} · {title}"),
    "Nothing timed tomorrow": ("Besok tidak ada jadwal berjam", "明日は時間指定の予定なし"),
    "仕舞い · THE DAY IS DONE": ("仕舞い · HARI INI SELESAI", "仕舞い · 今日はここまで"),
    "Done for today": ("Selesai hari ini", "今日はおしまい"), "Silent until 07:00": ("Senyap sampai 07:00", "07:00 まで通知オフ"),
    "Not yet": ("Belum", "まだ"),
    "Notifications": ("Notifikasi", "通知"), "As they come": ("Langsung", "すぐに"),
    "Every 30 min": ("Tiap 30 menit", "30 分ごと"), "Hourly": ("Tiap jam", "1 時間ごと"),
    "通 · WHAT CAME IN": ("通 · YANG MASUK", "通 · 届いたもの"),
    "{n} notifications waited": ("{n} notifikasi menunggu", "通知 {n} 件が待っています"),
    "Open the panel": ("Buka panel", "パネルを開く"), "Later": ("Nanti", "あとで"),
    "Rest your eyes": ("Istirahatkan mata", "目を休める"),
    "Every 20 minutes, look at something far away for 20 seconds": ("Tiap 20 menit, lihat jauh selama 20 detik", "20 分ごとに 20 秒、遠くを見る"),
    "Previous month": ("Bulan sebelumnya", "前の月"), "Next month": ("Bulan berikutnya", "次の月"),
    "Close": ("Tutup", "閉じる"), "Previous": ("Sebelumnya", "前へ"), "Next": ("Berikutnya", "次へ"),
    "Play / pause": ("Putar / jeda", "再生 / 一時停止"),
    "Kept in ~/.config/shoji/prefs.json": ("Disimpan di ~/.config/shoji/prefs.json", "~/.config/shoji/prefs.json に保存"),
    "Fully charged": ("Terisi penuh", "充電完了"), "Charging": ("Mengisi daya", "充電中"),
    "Battery low": ("Baterai lemah", "バッテリー残量低下"), "On battery": ("Pakai baterai", "バッテリー駆動"),
    "Desktop on mains power": ("Desktop pakai listrik langsung", "AC 電源のデスクトップ"),
    "{n} zazen today": ("{n} zazen hari ini", "今日の坐禅 {n} 回"),
    "Seasonal accent: 紅梅 spring · 青竹 summer · 紅葉 autumn · 白群 winter (now {s})":
        ("Aksen musiman: 紅梅 semi · 青竹 panas · 紅葉 gugur · 白群 dingin (sekarang {s})",
         "季節のアクセント：紅梅 春 · 青竹 夏 · 紅葉 秋 · 白群 冬（今は {s}）"),
    "Same from a terminal: {cmd}": ("Dari terminal: {cmd}", "ターミナルから：{cmd}"),
    "↑↓ move · ↵ run it · Esc": ("↑↓ pindah · ↵ jalankan · Esc", "↑↓ 移動 · ↵ 実行 · Esc"),
    "Homelab": ("Homelab", "ホームラボ"), "Refresh": ("Muat ulang", "更新"),
    "Not set up yet: run {cmd}": ("Belum diatur: jalankan {cmd}", "未設定：{cmd} を実行"),
    "all well": ("semua sehat", "すべて正常"), "{n} down": ("{n} mati", "{n} 件停止"),
    "updated {t} ago": ("diperbarui {t} lalu", "{t} 前に更新"),
    "CONTAINERS": ("KONTAINER", "コンテナ"), "SERVICES": ("LAYANAN", "サービス"), "PUBLIC": ("PUBLIK", "公開"),
    "HOST": ("HOST", "ホスト"), "BACKUPS": ("CADANGAN", "バックアップ"),
    "Restart": ("Mulai ulang", "再起動"), "Stop": ("Hentikan", "停止"), "Start": ("Jalankan", "開始"),
    "Logs": ("Log", "ログ"), "Run now": ("Jalankan sekarang", "今すぐ実行"),
    "Restart all": ("Mulai ulang semua", "すべて再起動"), "Stop all": ("Hentikan semua", "すべて停止"),
    "Start all": ("Jalankan semua", "すべて開始"),
    "Edit config…": ("Ubah konfigurasi…", "設定を編集…"), "working…": ("memproses…", "処理中…"),
    "NEEDS YOU": ("PERLU DICEK", "要対応"),
    "Widgets": ("Widget", "ウィジェット"), "Done": ("Selesai", "完了"), "Edit widgets": ("Ubah widget", "ウィジェットを編集"),
    "No widgets: ✎ to add some": ("Belum ada widget: ✎ untuk menambah", "ウィジェットなし：✎ で追加"),
    "HIDDEN": ("TERSEMBUNYI", "非表示"), "Show": ("Tampilkan", "表示"), "Hide": ("Sembunyikan", "隠す"),
    "Move earlier": ("Geser ke depan", "前へ移動"), "Move later": ("Geser ke belakang", "後ろへ移動"),
    "Open {what}": ("Buka {what}", "{what} を開く"), "Start 25 min of focus": ("Mulai fokus 25 menit", "25 分集中する"),
    "{m} min today": ("{m} menit hari ini", "今日 {m} 分"), "Copy again": ("Salin lagi", "もう一度コピー"),
    "Image · {kind}": ("Gambar · {kind}", "画像 · {kind}"),
    "connecting…": ("menghubungkan…", "接続中…"), "done": ("selesai", "完了"), "failed": ("gagal", "失敗"),
    "click again to confirm": ("klik lagi untuk yakin", "もう一度クリックで実行"), "ATTENTION": ("PERHATIAN", "要確認"),
    "Click where it goes, or Esc": ("Klik tempat tujuannya, atau Esc", "置きたい場所をクリック、または Esc"),
    "Drag to move · S M L to resize": ("Seret untuk memindah · S M L untuk ukuran", "ドラッグで移動 · S M L でサイズ"),
    "Checking…": ("Memeriksa…", "確認中…"), "{n} of {total} running": ("{n} dari {total} jalan", "{total} 中 {n} 稼働"),
    "Small": ("Kecil", "小"), "Wide": ("Lebar", "横長"), "Large": ("Besar", "大"),
    "REST · {m} MIN": ("ISTIRAHAT · {m} MENIT", "休憩 · {m} 分"), "Another": ("Yang lain", "別のもの"),
    "Skip rest": ("Lewati istirahat", "休憩をやめる"), "I did it": ("Sudah kulakukan", "やりました"),
    "Something else": ("Saran lain", "ほかの提案"), "End the rest now": ("Akhiri istirahat sekarang", "休憩を終える"),
    "breathe in": ("tarik napas", "吸う"), "hold": ("tahan", "止める"), "breathe out": ("buang napas", "吐く"),
    "Dim the screen in a rest": ("Redupkan layar saat istirahat", "休憩中は画面を暗く"),
    "After zazen, one thing to do away from the screen, over a dimmed desktop":
        ("Setelah zazen, satu hal untuk dilakukan jauh dari layar, di atas desktop yang diredupkan",
         "坐禅のあと、画面から離れてすることをひとつ、暗くしたデスクトップの上に"),
    "Zazen: focus · rest": ("Zazen: fokus · istirahat", "坐禅：集中・休憩"), "Every 4th rest": ("Tiap istirahat ke-4", "4 回ごとの休憩"),
    "Same": ("Sama", "同じ"), "15 min": ("15 menit", "15 分"), "20 min": ("20 menit", "20 分"),
    "{n} rests taken": ("{n} istirahat diambil", "休憩 {n} 回"), "{n} rest taken": ("{n} istirahat diambil", "休憩 {n} 回"),
    "checked {t} ago": ("dicek {t} lalu", "{t} 前に確認"), "No focus yet today": ("Belum fokus hari ini", "今日はまだ集中なし"),
    "Expected: stop watching it": ("Memang dimatikan: jangan pantau", "停止は想定内：監視しない"), "disconnecting…": ("memutus…", "切断中…"),
    "could not connect": ("gagal terhubung", "接続できません"), "could not disconnect": ("gagal memutus", "切断できません"),
    "CONNECTED": ("TERHUBUNG", "接続中"), "{n} on": ("{n} aktif", "{n} 件オン"),
    "Focus": ("Fokus", "集中"), "Clipboard": ("Clipboard", "クリップボード"), "Machine": ("Mesin", "マシン"),
}
LANGS = {"en": "English", "id": "Indonesia", "ja": "日本語"}
ID_MONTHS = "Januari Februari Maret April Mei Juni Juli Agustus September Oktober November Desember".split()
ID_DAYS = "Senin Selasa Rabu Kamis Jumat Sabtu Minggu".split()
JA_DAYS = "月火水木金土日"


def T(text):
    """text in the interface language (English when there is no translation)."""
    i = {"id": 0, "ja": 1}.get(LANG["code"])
    pair = STRINGS.get(text)
    return pair[i] if pair and i is not None else text


def day_name(d):
    return {"id": ID_DAYS[d.weekday()], "ja": JA_DAYS[d.weekday()] + "曜日"}.get(LANG["code"], d.strftime("%A"))


def day_month(d):
    """26 October · 26 Oktober · 10月26日"""
    return {"id": f"{d.day} {ID_MONTHS[d.month - 1]}", "ja": f"{d.month}月{d.day}日"}.get(LANG["code"], d.strftime("%-d %B"))


def month_year(d):
    return {"id": f"{ID_MONTHS[d.month - 1]} {d.year}", "ja": f"{d.year}年{d.month}月"}.get(LANG["code"], d.strftime("%B %Y"))


def short_day(d):
    """Mon · 26 Oct · Sen · 26 Okt · 10月26日（月）"""
    return {"id": f"{ID_DAYS[d.weekday()][:3]} · {d.day} {ID_MONTHS[d.month - 1][:3]}",
            "ja": f"{d.month}月{d.day}日（{JA_DAYS[d.weekday()]}）"}.get(LANG["code"], d.strftime("%a · %-d %b"))


def icon(name):
    return chr(int(LUCIDE[name]["encodedCode"].lstrip("\\"), 16))


def is_glyph(text):
    """Lucide glyphs live in the Private Use Area: a screen reader would read them as nothing."""
    return bool(text) and all(0xE000 <= ord(ch) <= 0xF8FF for ch in text.strip())


def name_icons(root):
    """Every button that shows only a glyph takes its tooltip as its accessible name. Returns the
    ones that have no tooltip to give (the tests keep that list empty)."""
    unnamed = []
    stack = [root]
    while stack:
        w = stack.pop()
        if isinstance(w, Gtk.Button):
            child = w.get_child()
            text = child.get_text() if isinstance(child, Gtk.Label) else ""
            if is_glyph(text):
                tip = w.get_tooltip_text()
                if tip:
                    w.get_accessible().set_name(tip)
                else:
                    unnamed.append(w)
        if isinstance(w, Gtk.Container):
            stack.extend(w.get_children())
    return unnamed


def sh(*cmd):
    return subprocess.run(cmd, capture_output=True, text=True).stdout.strip()


def spawn(*cmd):
    subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)


def theme():
    try:
        return json.loads(THEME.read_text())
    except (OSError, ValueError):
        return {"tokens": {"base": "#111827", "text": "#e6e9f0", "muted": "#97a0b5", "accent": "#d9b05a",
                           "on_accent": "#17161b"}, "dark": True}


def prefs():
    try:
        return json.loads(PREFS.read_text())
    except (OSError, ValueError):
        return {}


def save_prefs(**kw):
    p = prefs()
    p.update(kw)
    PREFS.write_text(json.dumps(p, indent=1) + "\n")


def rgba(h, a=1.0):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)) + (a,)


# letter-spacing stays under 1px: from 1px up, GTK 3 asks twice the text's height for the label in an
# on-screen window (offscreen it does not), which pushed card text down; 0.99px looks the same
CSS = b"""
* { font-family: "Zen Kaku Gothic New", "lucide", "JetBrainsMono Nerd Font"; font-size: 12px; }
.panel {
  background: @elev2;
  border: 1px solid @edge;
  border-radius: 16px;
  padding: 14px;
  color: @text;
}
/* every state change eases (hover, selection, a toggle turning on): STATE_MS */
button, .row, .app-row, .key-row, .sheet-row, .chip, .toggle, .day, .agenda-row, .nav, .card, .link {
  transition: background-color 150ms ease-out, color 150ms ease-out, box-shadow 150ms ease-out,
              border-color 150ms ease-out;
}
.muted { color: @muted; }
.label-small { color: @muted; font-size: 10.5px; letter-spacing: 0.99px; }
.mono { font-family: "JetBrainsMono Nerd Font"; font-size: 11px; color: @muted; }
.display { font-family: "Kaisei Opti"; font-weight: 700; font-size: 22px; color: @text; }
.title { font-size: 13px; font-weight: 700; }
.sep { background: @edge; min-height: 1px; }

/* koyomi */
.wk { font-family: "Kaisei Opti"; font-size: 10.5px; color: @muted; }
.day { min-width: 30px; min-height: 22px; border-radius: 4px; font-size: 12px; color: @text; }
.day.other { color: alpha(@text, 0.32); }
.day.past { color: alpha(@text, 0.6); }
.season { font-family: "Kaisei Opti"; font-size: 12px; color: @muted; letter-spacing: 0.99px; }
.haiku { font-family: "Kaisei Opti"; font-size: 12px; color: @muted; letter-spacing: 0.99px; }
.day.today { background: @accent; color: @on_accent; font-weight: 700; }
button.day { padding: 0; border: none; box-shadow: none; background-image: none; }
.agenda button.day { min-height: 25px; }  /* room for the event dot */
.agenda .day .num { margin-bottom: 4px; }
button.day:not(.today) { background: transparent; }
button.day:not(.today):hover { background: @hover; }
.day.sel { box-shadow: inset 0 0 0 1px @accent; }
.day .mark { min-width: 4px; min-height: 4px; border-radius: 2px; background: @accent; margin-bottom: 1px; }
.day.today .mark { background: @on_accent; }
.day.other .mark { opacity: 0.4; }
.agenda-row { background: transparent; background-image: none; border: none; box-shadow: none;
              border-radius: 8px; padding: 0 8px; min-height: 24px; color: @text; }
.agenda-row:hover { background: @hover; }
/* quick toggles at the foot of Koyomi: accent = on */
.toggle { background: @group; background-image: none; border: none; box-shadow: none; border-radius: 8px;
          min-height: 36px; padding: 0; color: @text; }
.toggle label { font-family: "lucide"; font-size: 15px; }
.toggle:hover { background: @hover; }
.toggle.on { background: @accent; color: @on_accent; }
.toggle.off-alert { color: @alert; }
/* Koyomi + the swaync panel read as one container: square inner corners, one hairline between */
.panel.koyomi { border-top-right-radius: 0; border-bottom-right-radius: 0; border-right-width: 0; }
.agenda-row .when { font-family: "JetBrainsMono Nerd Font"; font-size: 11px; color: @muted; }
.agenda-row .tick { font-family: "lucide"; font-size: 11px; }
.agenda-row.more { color: @muted; }
.nav { background: transparent; border: none; box-shadow: none; color: @muted; min-width: 24px; min-height: 22px;
       padding: 0; border-radius: 4px; font-family: "lucide"; }
.nav:hover { background: @hover; color: @text; }

/* rows inside popovers */
.row { background: transparent; border: none; box-shadow: none; border-radius: 8px; padding: 0 10px;
       min-height: 34px; color: @muted; }
.row:hover { background: @hover; color: @text; }
.row.active { background: alpha(@text, 0.10); color: @text; }
.row .icon { font-family: "lucide"; font-size: 14px; }
.chip { background: @group; border: none; box-shadow: none; border-radius: 8px; padding: 2px 10px;
        color: @text; font-size: 10.5px; min-height: 22px; }
.chip:hover { background: @hover; }
.chip.on { background: @accent; color: @on_accent; }
.chip.armed { background: alpha(@warn, 0.28); color: @text; }   /* "click again" for an action on many */
.link { background: transparent; border: none; box-shadow: none; color: @muted; padding: 2px 10px;
        border-radius: 8px; min-height: 26px; }
.link:hover { background: @hover; color: @text; }
scale trough { min-height: 4px; border-radius: 2px; background: @track; border: none; }
scale highlight { min-height: 4px; border-radius: 2px; background: @accent; border: none; }
scale slider { min-width: 14px; min-height: 14px; margin: -5px; border-radius: 7px; background: @text;
               border: none; box-shadow: none; }

/* theme manager */
.card { background: @group; border: 2px solid transparent; border-radius: 12px; padding: 8px;
        box-shadow: none; color: @text; }
.card:hover { background: @hover; }
.card.active { border-color: @accent; }
.swatch { background: transparent; background-image: none; border: none; box-shadow: none; padding: 2px;
          border-radius: 13px; }
.swatch.on { box-shadow: inset 0 0 0 2px @text; }
.card .name { font-family: "Kaisei Opti"; font-weight: 700; font-size: 13px; }
/* media: glass. A thinner pane than the other panels, so the blurred desktop and the cover's
   colour wash show through; a hairline and a top highlight give the glass an edge */
.panel.media { background-color: alpha(@base, 0.42); border: 1px solid alpha(@text, 0.16);
               box-shadow: inset 0 1px alpha(@text, 0.10); }
.media-title { font-size: 15px; font-weight: 700; color: @text; }
.media-btn { min-width: 40px; min-height: 40px; padding: 0; }
.media-btn label { font-family: "lucide"; font-size: 18px; }
.play { background: @text; color: @base; border: none; box-shadow: none; background-image: none;
        border-radius: 20px; min-width: 44px; min-height: 44px; }
.play label { font-size: 20px; }
.play:hover { background: @accent; color: @on_accent; }
.seal { background: @accent; color: @on_accent; border-radius: 4px; min-width: 28px; min-height: 28px;
        font-family: "Kaisei Opti"; font-weight: 700; font-size: 15px; }
switch { background: alpha(@text, 0.18); border: none; border-radius: 10px; min-height: 18px; }
switch:checked { background: @accent; }
switch slider { background: @text; border: none; border-radius: 8px; min-width: 14px; min-height: 14px; margin: 2px; }
switch:checked slider { background: @on_accent; }

/* launcher */
.searchbar { background: @group; border-radius: 12px; padding: 2px 10px; }
.searchbar .icon { font-family: "lucide"; font-size: 15px; color: @muted; }
entry.search { background: transparent; border: none; box-shadow: none; color: @text; font-size: 15px;
               min-height: 38px; caret-color: @accent; }
entry.search selection { background: alpha(@accent, 0.35); }
.kbd { font-family: "JetBrainsMono Nerd Font"; font-size: 10.5px; color: @muted; border: 1px solid @edge;
       border-radius: 4px; padding: 1px 5px; }
list { background: transparent; }
.app-row { background: transparent; border-radius: 8px; padding: 6px 10px; min-height: 36px; }
.app-row:hover { background: @hover; }
.app-row:selected { background: alpha(@text, 0.10); }
.app-row .app-name { font-size: 13px; color: @text; }
/* Alt+Tab cards: the selected one sealed with an accent ring */
.switch-card { background: @group; background-image: none; border: none; box-shadow: none; border-radius: 12px;
               min-width: 92px; padding: 10px 8px; }
.switch-card:hover { background: @hover; }
.switch-card.sel { box-shadow: inset 0 0 0 2px @accent; background: alpha(@text, 0.10); }
.switch-card .desc { font-size: 10.5px; color: @muted; }
.app-row .desc { font-size: 10.5px; color: @muted; }

/* shortcuts sheet */
.key-row { background: transparent; border-radius: 8px; padding: 5px 10px; min-height: 30px; }
.key-row:hover { background: @hover; }
.key-row:selected { background: alpha(@text, 0.10); }
.key-row .desc { font-size: 13px; color: @text; }
.key-row .group { font-size: 10.5px; color: @muted; }
.cap { font-family: "JetBrainsMono Nerd Font"; font-size: 11px; color: @text; background: @group;
       border: 1px solid @edge; border-bottom-width: 2px; border-radius: 4px; padding: 1px 7px; min-width: 12px; }
.key-row:selected .cap { border-color: alpha(@accent, 0.6); }
.key-head { font-size: 10.5px; letter-spacing: 0.99px; color: @muted; padding: 18px 10px 4px; }
.sheet-row { background: transparent; border: none; box-shadow: none; border-radius: 8px; padding: 3px 8px;
             min-height: 26px; }
.sheet-row:hover { background: @hover; }
.sheet-row:disabled { opacity: 1; }
.sheet-row .desc { font-size: 12px; color: @text; }
.sheet-row .cap { font-size: 10.5px; padding: 1px 5px; border: none; }
/* Homelab: healthy is muted, never green; the accent is not used at all */
.hl-line { border-radius: 8px; }
.hl-line.hot { background: @hover; }
.hl-main { background: transparent; background-image: none; border: none; box-shadow: none; border-radius: 8px;
           padding: 0 10px; min-height: 30px; }
.hl-line.sub .hl-main { padding-left: 26px; min-height: 28px; }
.hl-line .name { color: @muted; }
.hl-line.hot .name, .hl-line.bad .name, .hl-line.warn .name, .hl-line.accent .name { color: @text; }
.hl-line .meta { color: @muted; }
.hl-line.bad .meta, .hl-line .meta.bad { color: @alert; }
.hl-line.warn .meta, .hl-line .meta.warn { color: @warn; }
.hl-line.accent .meta { color: @accent_text; }
.hl-line .icon { font-family: "lucide"; font-size: 12px; color: @muted; }
.hl-dot { min-width: 6px; min-height: 6px; border-radius: 3px; background: alpha(@muted, 0.5); }
.hl-dot.warn { background: @warn; }
.hl-dot.bad { background: @alert; }
.hl-dot.accent { background: @accent; }   /* waits for you (unread-like); red stays for trouble */
.hl-act { background: transparent; background-image: none; border: none; box-shadow: none; border-radius: 6px;
          min-width: 26px; min-height: 26px; padding: 0; color: alpha(@muted, 0.75); }   /* 3:1 on light palettes too */
.hl-line.hot .hl-act, .hl-line.bad .hl-act, .hl-line.warn .hl-act, .hl-line.accent .hl-act { color: @muted; }
/* the keyboard's place: a ring on whatever has focus in a list or the drawer */
.hl-main:focus, .hl-act:focus, .chip:focus, .link:focus, .dcard.focus { box-shadow: inset 0 0 0 1px alpha(@accent, 0.85); }
.hl-act:hover { background: @hover; color: @text; }
.hl-act.on { color: @accent; }
.vpn-row { padding: 0 10px; min-height: 34px; }
.vpn-row .icon { font-family: "lucide"; font-size: 14px; color: @muted; }
.vpn-row .icon.on { color: @text; }   /* the mode that is on (you are here) */
.hl-act label { font-family: "lucide"; font-size: 12px; }
.hl-section { padding: 14px 10px 4px; }
.hl-section.first { padding-top: 4px; }
.hl-summary.bad { color: @alert; }
/* drawer cards: quiet when well, the icon and the number take the colour of trouble */
.dcard { background: @group; border-radius: 12px; padding: 10px 12px; }
.dcard.opens.hot { background: @hover; }   /* only a card that opens something lights up */
.dcard.compact { padding: 8px 12px; }
/* edit mode: cards look movable; the one picked or being dragged, and where it would land */
.dcard.editing { box-shadow: inset 0 0 0 1px alpha(@text, 0.16); }
.dcard.picked, .dcard.dragging { box-shadow: inset 0 0 0 2px @accent; opacity: 0.7; }
.dcard.drop-before { box-shadow: inset 3px 0 0 0 @accent; }
.dcard.drop-after { box-shadow: inset -3px 0 0 0 @accent; }
.size-chip { background: @group; background-image: none; border: none; box-shadow: none; border-radius: 6px;
             min-width: 22px; min-height: 20px; padding: 0 4px; font-size: 10.5px; color: @muted; }
.size-chip:hover { background: @hover; color: @text; }
.size-chip.on { background: @accent; color: @on_accent; }
/* the rest card */
.rest-card { padding: 20px 22px; }
.rest-title { font-family: "Kaisei Opti"; font-weight: 700; font-size: 22px; color: @text; }
.rest-how { font-size: 13px; color: mix(@muted, @text, 0.35); }
.dcard .dc-icon, .dc-icon { font-family: "lucide"; font-size: 13px; color: @muted; }
.dcard.warn .dc-icon, .dcard.warn .dc-big { color: @warn; }
.dcard.bad .dc-icon, .dcard.bad .dc-big { color: @alert; }
.dcard.accent .dc-icon, .dcard.accent .dc-big { color: @accent; }   /* waits for you, like unread */
.dc-big { font-family: "Kaisei Opti"; font-weight: 700; font-size: 24px; color: @text; }
.dc-title { font-size: 12.5px; font-weight: 700; color: @text; }
.dc-line { font-size: 11.5px; color: mix(@muted, @text, 0.35); }   /* 4.5:1 on hiru / yuki cards */
.dc-line.strong { color: @text; }
.dc-line.warn { color: @warn; }
.dc-line.bad { color: @alert; }
.hl-stale { color: @warn; }
"""

provider = Gtk.CssProvider()


def load_css():
    LANG["code"] = prefs().get("lang", "en")  # every surface loads CSS when it shows
    try:
        colors = COLORS.read_bytes()
    except OSError:
        colors = b""
    still = b"* { transition: none; animation: none; }\n" if reduced() else b""
    try:
        provider.load_from_data(colors + CSS + still)
    except GLib.Error as e:
        print("css:", e, file=sys.stderr)


def layer_window(namespace, layer, keyboard=False):
    win = Gtk.Window()
    win.set_app_paintable(True)
    visual = win.get_screen().get_rgba_visual()
    if visual:
        win.set_visual(visual)
    Layer.init_for_window(win)
    Layer.set_namespace(win, namespace)
    Layer.set_layer(win, layer)
    Layer.set_keyboard_mode(win, Layer.KeyboardMode.ON_DEMAND if keyboard else Layer.KeyboardMode.NONE)
    win.connect("draw", clear_bg)
    return win


def clear_bg(_w, cr):
    cr.set_operator(cairo.OPERATOR_SOURCE)
    cr.set_source_rgba(0, 0, 0, 0)
    cr.paint()
    cr.set_operator(cairo.OPERATOR_OVER)
    return False


class Glide:
    """Eases a scrolled window's vertical position, like Shoji's swaync patch: a wheel notch or a
    keyboard step moves a target, the view follows in 180 ms (ease-out cubic), and quick notches add
    up instead of restarting. Touchpads keep GTK's own scrolling, which is already smooth."""
    STEP, MS = 96, CONTENT_MS

    def __init__(self, scrolled):
        self.sw, self.adj = scrolled, scrolled.get_vadjustment()
        self.tick, self.target, self.start, self.origin = 0, 0.0, 0, 0.0
        scrolled.connect("scroll-event", self.on_scroll)

    def on_scroll(self, _w, ev):
        dev = ev.get_source_device()
        if dev is not None and dev.get_source() == Gdk.InputSource.TOUCHPAD:
            return False
        if ev.direction == Gdk.ScrollDirection.SMOOTH:
            dy = ev.get_scroll_deltas()[2]
        else:
            dy = {Gdk.ScrollDirection.UP: -1, Gdk.ScrollDirection.DOWN: 1}.get(ev.direction, 0)
        if not dy:
            return False
        self.to((self.target if self.tick else self.adj.get_value()) + dy * self.STEP)
        return True

    def to(self, value):
        adj = self.adj
        self.target = max(adj.get_lower(), min(adj.get_upper() - adj.get_page_size(), value))
        if reduced():
            self.jump(self.target)
            return
        self.origin = adj.get_value()
        clock = self.sw.get_frame_clock()
        if clock is None:
            adj.set_value(self.target)
            return
        self.start = clock.get_frame_time()
        if not self.tick:
            self.tick = self.sw.add_tick_callback(self.frame)

    def jump(self, value):
        if self.tick:
            self.sw.remove_tick_callback(self.tick)
            self.tick = 0
        self.adj.set_value(value)

    def frame(self, _w, clock):
        t = (clock.get_frame_time() - self.start) / (self.MS * 1000)
        if t >= 1:
            self.adj.set_value(self.target)
            self.tick = 0
            return False
        self.adj.set_value(self.origin + (self.target - self.origin) * (1 - (1 - t) ** 3))
        return True


def click_through(win):
    win.input_shape_combine_region(cairo.Region())


def label(text, *classes, xalign=0.0):
    w = Gtk.Label(label=text, xalign=xalign)
    for c in classes:
        w.get_style_context().add_class(c)
    return w


def sep():
    s = Gtk.Box()
    s.get_style_context().add_class("sep")
    return s


def enso(cr, cx, cy, r, frac, color, width, track=None):
    start = -math.pi / 2 - math.radians(6)
    sweep = 2 * math.pi * 0.94
    cr.set_line_cap(cairo.LINE_CAP_ROUND)
    if track:
        cr.set_source_rgba(*track)
        cr.set_line_width(width * 0.7)
        cr.arc(cx, cy, r, start, start + sweep)
        cr.stroke()
    if frac > 0:
        cr.set_source_rgba(*color)
        cr.set_line_width(width)
        cr.arc(cx, cy, r, start, start + sweep * frac)
        cr.stroke()
        if frac > 0.08:
            cr.set_source_rgba(color[0], color[1], color[2], 0.5)
            cr.set_line_width(max(1.2, width * 0.24))
            cr.arc(cx, cy, r - width * 0.72, start + 0.07, start + sweep * frac * 0.78)
            cr.stroke()
