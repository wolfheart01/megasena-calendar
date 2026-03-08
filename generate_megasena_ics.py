import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta, timezone
import re

MEGASENA_URL = "https://www.megasena.com/calendario-de-sorteios"

# BRT is UTC-3 (no daylight savings currently)
BRT = timezone(timedelta(hours=-3))

def fetch_page():
    resp = requests.get(MEGASENA_URL, timeout=30)
    resp.raise_for_status()
    return resp.text

def parse_draws(html):
    """
    Returns a list of dicts:
    [
      {
        "contest": "2982",
        "date": datetime(2026, 3, 10, 12, 0, tzinfo=BRT)
      },
      ...
    ]
    """

    soup = BeautifulSoup(html, "html.parser")

    calendar_boxes = soup.select("div.calendar-box")
    if not calendar_boxes:
        return []

    month_map = {
        "janeiro": 1, "fevereiro": 2, "março": 3, "marco": 3,
        "abril": 4, "maio": 5, "junho": 6, "julho": 7,
        "agosto": 8, "setembro": 9, "outubro": 10,
        "novembro": 11, "dezembro": 12,
    }

    draws = []

    for box in calendar_boxes:
        # Each calendar-box contains one draw:
        #   <div class="date">Terça-feira, 10 de março de 2026</div>
        #   <div class="bottom">
        #       ...
        #       <div class="number">2982</div>
        #       ...
        #   </div>

        date_div = box.select_one("div.date")
        number_div = box.select_one("div.bottom div.number")

        if not date_div or not number_div:
            continue

        date_text = date_div.get_text(strip=True)
        contest_text = number_div.get_text(strip=True)

        # Extract contest number (e.g. "2982")
        contest_num_match = re.search(r"(\d+)", contest_text)
        if not contest_num_match:
            continue
        contest_num = contest_num_match.group(1)

        # Extract date from something like:
        # "Terça-feira, 10 de março de 2026"
        # We'll strip weekday and focus on "10 de março de 2026"
        # by finding the first digit and slicing from there.
        m = re.search(r"(\d{1,2}\s+de\s+[a-zçãé]+\s+de\s+\d{4})", date_text, re.IGNORECASE)
        if not m:
            continue

        date_core = m.group(1)  # "10 de março de 2026"
        parts = date_core.lower().split()
        # parts: ["10", "de", "março", "de", "2026"]
        try:
            day = int(parts[0])
            month_name = parts[2]
            year = int(parts[4])
        except (IndexError, ValueError):
            continue

        month = month_map.get(month_name)
        if not month:
            continue

        # 12:00 BRT
        local_dt = datetime(year, month, day, 12, 0, tzinfo=BRT)

        draws.append({
            "contest": contest_num,
            "date": local_dt
        })

    # Deduplicate by contest number (keep earliest date)
    unique = {}
    for d in draws:
        cnum = d["contest"]
        if cnum not in unique or d["date"] < unique[cnum]["date"]:
            unique[cnum] = d

    return sorted(unique.values(), key=lambda x: x["date"])

def to_utc(dt):
    return dt.astimezone(timezone.utc)

def format_ics_datetime(dt):
    # dt must be aware (with tzinfo)
    dt_utc = to_utc(dt)
    return dt_utc.strftime("%Y%m%dT%H%M%SZ")

def generate_ics(draws):
    lines = []
    lines.append("BEGIN:VCALENDAR")
    lines.append("VERSION:2.0")
    lines.append("PRODID:-//MegaSena//Dynamic Calendar//EN")
    lines.append("CALSCALE:GREGORIAN")
    lines.append("METHOD:PUBLISH")

    now_utc = datetime.now(timezone.utc)
    dtstamp = format_ics_datetime(now_utc)

    for d in draws:
        contest = d["contest"]
        start = d["date"]
        # 30-minute event window
        end = start + timedelta(minutes=30)

        uid = f"megasena-{contest}@megasena.com"
        dtstart = format_ics_datetime(start)
        dtend = format_ics_datetime(end)

        summary = f"Mega-Sena Concurso {contest}"

        lines.append("BEGIN:VEVENT")
        lines.append(f"UID:{uid}")
        lines.append(f"DTSTAMP:{dtstamp}")
        lines.append(f"DTSTART:{dtstart}")
        lines.append(f"DTEND:{dtend}")
        lines.append(f"SUMMARY:{summary}")
        lines.append("END:VEVENT")

    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"

def main():
    html = fetch_page()
    draws = parse_draws(html)
    ics_content = generate_ics(draws)

    with open("megasena.ics", "w", encoding="utf-8") as f:
        f.write(ics_content)

if __name__ == "__main__":
    main()
