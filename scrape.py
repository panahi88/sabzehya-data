import csv, os, re, time, requests
from datetime import datetime, timedelta
from difflib import SequenceMatcher
from zoneinfo import ZoneInfo
import jdatetime
from bs4 import BeautifulSoup

CHANNELS = ["noavaransabzehyaco", "samenwarehouse", "radstellbillet"]
COLS = ["id", "jalali_date", "time", "gregorian", "text"]
DAYS = 45  # فقط پیام‌های این تعداد روز اخیر در جدول قیمت‌ها می‌آید

DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")

SABZ_HEADERS = [
    "روغنی زیر ۲", "روغنی ۲ تا ۴", "کلافی روغنی", "گالوانیزه و روکشدار",
    "حلب نو بدون چاپ", "پولکی درجات فوق", "سوپر ویژه", "ویژه کوتاه",
    "درجه ۱ کوتاه", "ویژه بلند بالای ۶۰ سانت",
    "درجه ۱ بلند (در و پنجره و لوله بالای ۶۰ سانت)", "درجه ۲ (سبک بار)",
    "درجه ۳ (ریز بار)", "چدن ممتاز", "آلیاژی یکدست تمیز", "آلیاژی یکدست",
    "حلب کهنه کاملاً تمیز", "حلب کهنه یکدست",
]
SAMEN_HEADERS = [
    "روغنی نرمه", "روغنی ضخیم", "روغنی ریزبار و پولکی",
    "گالوانیزه و ورق روکشدار خودرویی", "سوپر ویژه", "کلاف", "ویژه", "حلب",
    "سنگین یک و دو (زیر ۵۰ سانت)، درب و پنجره", "سبک", "سفاله ریزبار",
    "سفاله پوشالی", "سفاله اتومات", "حلب قوطی فله", "آلیاژی", "چدن",
]
RAD_HEADERS = [
    "قراضه روغنی", "قراضه سوپر ویژه", "قراضه ویژه", "قراضه درب و پنجره",
    "قراضه سبک", "چدن و درهم", "حلب فله", "آلیاژی", "خودرو اسقاطی له", "پرس حلب",
]


def update(channel):
    file = channel + ".csv"
    rows = {}
    last_id = 0
    if os.path.exists(file):
        with open(file, encoding="utf-8-sig", newline="") as f:
            for r in csv.DictReader(f):
                rows[int(r["id"])] = r
        if rows:
            last_id = max(rows)

    before = None
    while True:
        url = f"https://t.me/s/{channel}"
        if before:
            url += f"?before={before}"
        html = requests.get(url, timeout=30).text
        posts = BeautifulSoup(html, "html.parser").select("div.tgme_widget_message")
        if not posts:
            break
        ids = []
        for p in posts:
            mid = int(p["data-post"].split("/")[1])
            ids.append(mid)
            if mid <= last_id:
                continue
            t = p.select_one("div.tgme_widget_message_text")
            d = p.select_one("time[datetime]")
            if not t or not d:
                continue
            dt = datetime.fromisoformat(d["datetime"]).astimezone(ZoneInfo("Asia/Tehran"))
            j = jdatetime.datetime.fromgregorian(datetime=dt)
            rows[mid] = {
                "id": mid,
                "jalali_date": j.strftime("%Y/%m/%d"),
                "time": dt.strftime("%H:%M"),
                "gregorian": dt.strftime("%Y-%m-%d"),
                "text": t.get_text("\n"),
            }
        if min(ids) <= last_id or min(ids) <= 1:
            break
        before = min(ids)
        time.sleep(1)

    with open(file, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        w.writeheader()
        for k in sorted(rows):
            w.writerow(rows[k])
    print(channel, ":", len(rows), "پیام در فایل است")


# ---------- جدول قیمت‌ها ----------

def date_key(text):
    m = re.search(r"(\d{4})\s*/\s*(\d{1,2})\s*/\s*(\d{1,2})", text)
    if not m:
        return None
    return int(m.group(1)) * 10000 + int(m.group(2)) * 100 + int(m.group(3))


def norm(s):
    s = s.translate(DIGITS)
    for a, b in (("ي", "ی"), ("ى", "ی"), ("ك", "ک"), ("ة", "ه"), ("ۀ", "ه"),
                 ("أ", "ا"), ("إ", "ا"), ("ؤ", "و")):
        s = s.replace(a, b)
    s = re.sub(r"[\u200c\u200d\u200e\u200f\u0640\u064b-\u065f]", "", s)
    return re.sub(r"[^\w]", "", s)


def best_match(name, candidates):
    n = norm(name)
    scored = sorted(((SequenceMatcher(None, n, norm(c)).ratio(), c) for c in candidates),
                    reverse=True)
    if not scored:
        return None
    top = scored[0]
    second = scored[1][0] if len(scored) > 1 else 0
    if top[0] >= 0.99 or (top[0] >= 0.85 and top[0] - second >= 0.05):
        return top[1]
    return None


LINE = re.compile(r"^\W*?(\d{1,2})\s*[-–.)]\s*(.+?)[\s:：]*(\d{4,7})\s*(?:ریال|تومان)?\s*$")


def parse_sabz(text, factor):
    t = text.translate(DIGITS)
    if "عبارتند از" not in t:
        return None
    head, body = t.split("عبارتند از", 1)
    key = date_key(head)
    if key is None:
        return None
    body = body.lstrip(": \n").split("پرداخت", 1)[0]
    vals = re.findall(r":\s*(\d+(?:\s*کمتر)?)", body)
    if len(vals) != 18:
        print("هشدار سبز احیا: پیام تاریخ", key, "تعداد قیمت", len(vals), "بود و رد شد")
        return None
    out = {}
    prev = None
    for h, v in zip(SABZ_HEADERS, vals):
        if "کمتر" in v:
            n = int(re.sub(r"\D", "", v))
            out[h] = prev - n * factor if prev is not None else ""
        else:
            out[h] = int(v) * factor
        if isinstance(out[h], int):
            prev = out[h]
    return key, out


def parse_named(text, fixed, factor):
    t = text.translate(DIGITS)
    key = date_key(t)
    if key is None:
        return None
    items = {}
    extras = {}
    for line in t.splitlines():
        m = LINE.match(line.strip())
        if not m:
            continue
        name = re.sub(r"\s+", " ", m.group(2)).strip(" :-")
        price = int(m.group(3)) * factor
        hit = best_match(name, fixed)
        if hit:
            items.setdefault(hit, price)
        else:
            hit2 = best_match(name, list(extras))
            extras.setdefault(hit2 or name, price)
    if len(items) + len(extras) < 3:
        return None
    items.update(extras)
    return key, items


def write_table(out_file, fixed, results):
    extra_cols = []
    for _, vals in results:
        for k in vals:
            if k not in fixed and k not in extra_cols:
                extra_cols.append(k)
    cols = fixed + extra_cols
    with open(out_file, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["date_key"] + cols)
        for key, vals in results:
            w.writerow([key] + [vals.get(c, "") for c in cols])
    print(out_file, ":", len(results), "روز،", len(extra_cols), "ستون اضافه")


def build(channel, out_file, fixed, parser):
    src = channel + ".csv"
    if not os.path.exists(src):
        return
    limit = (datetime.now(ZoneInfo("Asia/Tehran")) - timedelta(days=DAYS)).strftime("%Y-%m-%d")
    with open(src, encoding="utf-8-sig", newline="") as f:
        rows = sorted(csv.DictReader(f), key=lambda r: int(r["id"]))
    table = {}
    for r in rows:
        if r["gregorian"] < limit:
            continue
        res = parser(r["text"])
        if res:
            table[res[0]] = res[1]
    write_table(out_file, fixed, [(k, table[k]) for k in sorted(table)])


def build_all():
    build("noavaransabzehyaco", "prices.csv", SABZ_HEADERS,
          lambda t: parse_sabz(t, 10))
    build("samenwarehouse", "prices_samen.csv", SAMEN_HEADERS,
          lambda t: parse_named(t, SAMEN_HEADERS, 10))
    build("radstellbillet", "prices_rad.csv", RAD_HEADERS,
          lambda t: parse_named(t, RAD_HEADERS, 1))


if __name__ == "__main__":
    for ch in CHANNELS:
        try:
            update(ch)
        except Exception as e:
            print(ch, "خطا:", e)
    try:
        build_all()
    except Exception as e:
        print("خطا در ساخت جدول قیمت‌ها:", e)
