import csv, os, time, requests
from datetime import datetime
from zoneinfo import ZoneInfo
import jdatetime
from bs4 import BeautifulSoup

CHANNELS = ["noavaransabzehyaco", "samenwarehouse", "radstellbillet"]
COLS = ["id", "jalali_date", "time", "gregorian", "text"]


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


for ch in CHANNELS:
    try:
        update(ch)
    except Exception as e:
        print(ch, "خطا:", e)
