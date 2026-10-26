"""休 What to do in a rest: one suggestion that fits the minutes you have, the hour, the weather,
the next meeting and what you tend to skip. Pure Python (no GTK), so tests and the rest card share
it: the card asks pick(), and logs what you did with log().

The log (~/.local/state/shoji-rest.log) is one line per answer: "YYYY-MM-DD HH:MM id done|skip|another".
A category you keep skipping comes up less (never never); one you do comes up a little more.
"""
import datetime
import json
import random
from pathlib import Path

HOME = Path.home()
LOG = HOME / ".local/state/shoji-rest.log"
TODAY = HOME / ".cache/shoji/today.json"       # Koyomi's agenda for today (when, title, task)
WEATHER = HOME / ".cache/shoji/weather.json"   # Koyomi's weather (kanji)
WET = set("雨雪雷霧")
MEETING_SOON_MIN = 15
LONG_MIN = 10   # a rest this long prefers the suggestions that need it

# id, category, minutes it needs, conditions, {lang: (title, how)}
# conditions: "day" 07–18 h · "morning" before 11 h · "caffeine" not after 19 h · "dry" no rain/snow/fog/storm
CATALOG = [
    ("neck", "body", 2, (), {
        "en": ("Loosen your neck", "Tilt your head to the left and right, 30 seconds each side. Then roll your shoulders back ten times."),
        "id": ("Lemaskan leher", "Miringkan kepala ke kiri dan kanan, 30 detik tiap sisi. Lalu putar bahu ke belakang sepuluh kali."),
        "ja": ("首をほぐす", "頭を左右に 30 秒ずつ傾け、肩を後ろへ 10 回まわします。")}),
    ("wrists", "body", 2, (), {
        "en": ("Rest your wrists", "Stretch each hand back, then forward, 20 seconds each. Shake them out; your fingers did a lot."),
        "id": ("Istirahatkan pergelangan", "Tekuk tiap tangan ke belakang lalu ke depan, 20 detik masing-masing. Goyangkan; jarimu sudah bekerja keras."),
        "ja": ("手首を休める", "手首を反らし、次に曲げて 20 秒ずつ。最後に軽く振ってほぐします。")}),
    ("reach", "body", 3, (), {
        "en": ("Stand up and reach", "Stand, reach both arms up high, then fold forward and let them hang for a few slow breaths."),
        "id": ("Berdiri dan meregang", "Berdiri, angkat kedua tangan tinggi-tinggi, lalu bungkukkan badan dan biarkan tangan menggantung beberapa napas."),
        "ja": ("立って伸びる", "立って両腕を高く伸ばし、前屈して腕を垂らしたまま数回ゆっくり呼吸します。")}),
    ("squats", "body", 3, (), {
        "en": ("Ten slow squats", "Feet shoulder-wide, ten slow squats. The blood comes back to your legs."),
        "id": ("Sepuluh squat pelan", "Kaki selebar bahu, sepuluh squat pelan. Darah kembali mengalir ke kaki."),
        "ja": ("ゆっくりスクワット 10 回", "足を肩幅に開き、ゆっくり 10 回。脚に血が戻ります。")}),
    ("far", "eyes", 1, (), {
        "en": ("Look far away", "Find the farthest thing you can see through a window and rest your eyes on it for a minute. Blink slowly."),
        "id": ("Lihat jauh", "Cari benda terjauh yang bisa kamu lihat dari jendela, tatap selama satu menit. Kedipkan mata pelan-pelan."),
        "ja": ("遠くを見る", "窓から見えるいちばん遠いものを 1 分眺めます。ゆっくりまばたきを。")}),
    ("palming", "eyes", 2, (), {
        "en": ("Palm your eyes", "Rub your hands warm, cup them over your closed eyes and breathe for one minute in the dark."),
        "id": ("Tutup mata dengan telapak", "Gosok tangan sampai hangat, tutupkan ke mata yang terpejam, bernapas satu menit dalam gelap."),
        "ja": ("手のひらで目を覆う", "手をこすって温め、閉じた目を覆って 1 分、暗闇で呼吸します。")}),
    ("box", "breath", 2, (), {
        "en": ("Box breathing", "Follow the ensō: in for 4, hold for 4, out for 4, hold for 4. Four rounds."),
        "id": ("Napas kotak", "Ikuti ensō: tarik 4, tahan 4, buang 4, tahan 4. Empat putaran."),
        "ja": ("ボックス呼吸", "円相に合わせて、吸う 4・止める 4・吐く 4・止める 4。4 回。")}),
    ("water", "water", 1, (), {
        "en": ("Drink a glass of water", "Fill a glass and drink it slowly, standing away from the desk."),
        "id": ("Minum segelas air", "Isi segelas air dan minum pelan-pelan, sambil berdiri jauh dari meja."),
        "ja": ("水を一杯", "グラスに水を注ぎ、机から離れて立ったままゆっくり飲みます。")}),
    ("tea", "water", 4, ("caffeine",), {
        "en": ("Make tea", "Boil water, make tea, and watch it steep. No phone while it does."),
        "id": ("Seduh teh", "Didihkan air, seduh teh, dan perhatikan sampai matang. Tanpa ponsel."),
        "ja": ("お茶を淹れる", "湯を沸かしてお茶を淹れ、蒸らしを眺めます。その間スマホは見ない。")}),
    ("nothing", "mind", 2, (), {
        "en": ("Do nothing at all", "Sit by a window and do nothing for two minutes. Let the thoughts pass like clouds."),
        "id": ("Tidak melakukan apa-apa", "Duduk di dekat jendela dan diam dua menit. Biarkan pikiran lewat seperti awan."),
        "ja": ("何もしない", "窓辺に座って 2 分間何もしない。考えは雲のように流します。")}),
    ("tidy", "tidy", 3, (), {
        "en": ("Clear one thing", "Put away one thing on the desk and wipe the surface. A clear desk, a clearer next session."),
        "id": ("Rapikan satu hal", "Simpan satu barang di meja dan lap permukaannya. Meja lega, sesi berikutnya lebih jernih."),
        "ja": ("ひとつ片づける", "机の上のものをひとつ片づけ、天板を拭きます。")}),
    ("walk", "walk", 5, (), {
        "en": ("Walk around", "Walk around the house or the building for five minutes. Leave the phone behind."),
        "id": ("Jalan-jalan sebentar", "Berjalan keliling rumah atau gedung lima menit. Tinggalkan ponselmu."),
        "ja": ("少し歩く", "家や建物の中を 5 分歩きます。スマホは置いて。")}),
    ("outside", "outside", 5, ("day", "dry"), {
        "en": ("Step outside", "Go outside for five minutes. Look at the sky and feel the air."),
        "id": ("Keluar sebentar", "Keluar rumah lima menit. Lihat langit, rasakan udaranya."),
        "ja": ("外に出る", "5 分外へ。空を見て、空気を感じます。")}),
    ("sun", "outside", 5, ("morning", "dry"), {
        "en": ("Morning light", "Stand in the morning sun for five minutes; it sets the day's clock."),
        "id": ("Sinar pagi", "Berdiri di bawah matahari pagi lima menit; itu menyetel jam tubuhmu."),
        "ja": ("朝の光", "朝日を 5 分浴びます。体内時計が整います。")}),
    ("floor", "body", 10, (), {
        "en": ("Stretch on the floor", "Lie on your back, knees to the chest, then a slow twist to each side. Breathe."),
        "id": ("Peregangan di lantai", "Berbaring telentang, tarik lutut ke dada, lalu putar pelan ke tiap sisi. Bernapas."),
        "ja": ("床でストレッチ", "仰向けで膝を胸に引き寄せ、左右にゆっくりひねります。呼吸を忘れずに。")}),
    ("meal", "meal", 15, (), {
        "en": ("Eat something real", "Make or get a proper snack or meal, and eat it away from the screen."),
        "id": ("Makan yang benar", "Siapkan camilan atau makanan yang layak, dan makan jauh dari layar."),
        "ja": ("ちゃんと食べる", "軽食か食事を用意して、画面から離れて食べます。")}),
    ("longwalk", "walk", 15, ("dry",), {
        "en": ("A longer walk", "Fifteen minutes around the block. Come back with fresh eyes."),
        "id": ("Jalan lebih jauh", "Lima belas menit keliling blok. Kembali dengan mata segar."),
        "ja": ("少し長い散歩", "近所を 15 分。新しい目で戻ってきます。")}),
]
PREP = {   # when a meeting starts within MEETING_SOON_MIN minutes, this comes first
    "en": ("Before {title}", "It starts at {when}. Drink some water, go to the toilet, and read its title once."),
    "id": ("Sebelum {title}", "Mulai pukul {when}. Minum air, ke toilet, dan baca judulnya sekali."),
    "ja": ("{title} の前に", "{when} 開始。水を飲み、トイレに行き、件名を一度読んでおきます。"),
}


def context(now=None):
    """What the rest can know: the weather kanji and the next timed event, from Koyomi's caches."""
    now = now or datetime.datetime.now()
    ctx = {"weather": "", "meeting": None}
    try:
        ctx["weather"] = json.loads(WEATHER.read_text()).get("kanji", "")
    except (OSError, ValueError):
        pass
    try:
        today = json.loads(TODAY.read_text())
        if today.get("day") == now.date().isoformat():
            soon = (now + datetime.timedelta(minutes=MEETING_SOON_MIN)).strftime("%H:%M")
            hm = now.strftime("%H:%M")
            nxt = sorted((i for i in today.get("items", []) if not i.get("task") and ":" in i.get("when", "")
                          and hm <= i["when"] <= soon), key=lambda i: i["when"])
            ctx["meeting"] = nxt[0] if nxt else None
    except (OSError, ValueError):
        pass
    return ctx


def history(days=14, now=None):
    """{category: (done, skipped)} over the last `days`."""
    now = now or datetime.datetime.now()
    since = (now - datetime.timedelta(days=days)).strftime("%Y-%m-%d")
    cats = {sid: cat for sid, cat, *_ in CATALOG}
    out = {}
    try:
        lines = LOG.read_text().splitlines()
    except OSError:
        return out
    for line in lines:
        parts = line.split()
        if len(parts) != 4 or parts[0] < since or parts[2] not in cats:
            continue
        done, skip = out.get(cats[parts[2]], (0, 0))
        out[cats[parts[2]]] = (done + (parts[3] == "done"), skip + (parts[3] in ("skip", "another")))
    return out


def allowed(cond, hour, weather):
    return {"day": 7 <= hour < 18, "morning": 6 <= hour < 11, "caffeine": hour < 19,
            "dry": not (set(weather) & WET)}.get(cond, True)


def pick(minutes, now=None, last=None, ctx=None, rng=None, lang="en"):
    """One suggestion: {id, cat, title, how, breath}. A meeting about to start wins; a long rest
    prefers what needs the time; never the same one twice in a row."""
    now = now or datetime.datetime.now()
    ctx = context(now) if ctx is None else ctx
    rng = rng or random.Random()
    if ctx.get("meeting") and last != "prep":
        m = ctx["meeting"]
        title, how = PREP.get(lang, PREP["en"])
        return {"id": "prep", "cat": "prep", "title": title.format(title=m.get("title", "")),
                "how": how.format(when=m.get("when", "")), "breath": False}
    seen = history(now=now)
    choices, weights = [], []
    for sid, cat, need, conds, text in CATALOG:
        if need > minutes or sid == last or not all(allowed(c, now.hour, ctx.get("weather", "")) for c in conds):
            continue
        done, skip = seen.get(cat, (0, 0))
        w = min(2.0, max(0.2, (1 + 0.15 * done) / (1 + 0.5 * skip)))
        if minutes >= LONG_MIN:
            w *= 3 if need >= LONG_MIN else 0.5
        choices.append((sid, cat, text))
        weights.append(w)
    sid, cat, text = rng.choices(choices, weights=weights)[0]
    title, how = text.get(lang, text["en"])
    return {"id": sid, "cat": cat, "title": title, "how": how, "breath": cat == "breath"}


def log(sid, outcome, now=None):
    now = now or datetime.datetime.now()
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a") as f:
        f.write(f"{now.strftime('%Y-%m-%d %H:%M')} {sid} {outcome}\n")


def taken_today(now=None):
    """How many rests today you answered with "done"."""
    day = (now or datetime.datetime.now()).strftime("%Y-%m-%d")
    try:
        return sum(1 for line in LOG.read_text().splitlines() if line.startswith(day) and line.endswith(" done"))
    except OSError:
        return 0
