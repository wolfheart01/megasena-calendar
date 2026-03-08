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
        "contest": "2981",
        "date": datetime(2026, 3, 10, 12, 0, tzinfo=BRT)
      },
      ...
    ]
    """
    soup = BeautifulSoup(html, "html.parser")

    # This part depends on the actual HTML structure.
    # We’ll be conservative and search text blocks that contain both
    # a date in Portuguese and "Concurso".
    # You may refine selectors later if needed.

    text = soup.get_text(" ", strip=True)

    # Example patterns we expect:
    # "Concurso 2981 - Terça-feira, 10 de março de 2026"
    # or similar variants.
    # We'll look for "Concurso <number>" and a nearby date.

    # Regex for contest number
    contest_pattern = re.compile(r"Concurso\s+(\d+)", re.IGNORECASE)

    # Regex for date in Portuguese, e.g. "10 de março de 2026"
    date_pattern = re.compile(
        r"(\d{1,2})\s+de\s+([a-zçãé]+)\s+de\s+(\d{4})",
        re.IGNORECASE
    )

    # Map Portuguese month names to numbers
    month_map = {
        "janeiro": 1,
        "fevereiro": 2,
        "março": 3,
        "marco": 3,
        "abril": 4,
        "maio": 5,
        "junho": 6,
        "julho": 7,
        "agosto": 8,
        "setembro": 9,
        "outubro": 10,
        "novembro": 11,
        "dezembro": 12,
    }

    draws = []

    # Strategy:
    # 1. Find all contest numbers.
    # 2. For each, look ahead in the text for the next date.
    # This is approximate but robust enough for a structured page.

    contests = list(contest_pattern.finditer(text))
    dates = list(date_pattern.finditer(text))

    # Helper: find the first date that appears after a given index
    def find_next_date(start_idx):
        for d in dates:
            if d.start() > start_idx:
                return d
        return None

    for c in contests:
        contest_num = c.group(1)
        dmatch = find_next_date(c.end())
        if not dmatch:
            continue

        day = int(dmatch.group(1))
        month_name = dmatch.group(2).lower()
        year = int(dmatch.group(3))

        month = month_map.get(month_name)
        if not month:
            continue

        # Draw time: 12:00 BRT
        local_dt = datetime(year, month, day, 12, 0, tzinfo=BRT)

        draws.append({
            "contest": contest_num,
            "date": local_dt
        })

    # Remove duplicates by contest number (keep earliest date)
    unique = {}
    for d in draws:
        cnum = d["contest"]
        if cnum not in unique or d["date"] < unique[cnum]["date"]:
            unique[cnum] = d

    # Sort by date
    result = sorted(unique.values(), key=lambda x: x["date"])
    return result

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
