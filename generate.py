#!/usr/bin/env python3
"""
Generuje index.html z czytaniami liturgicznymi na dziś.
Po godzinie 18:00 (czas Europe/Warsaw) pokazywane jest czytanie na następny dzień.

Źródło: https://www.mateusz.pl/czytania/
"""
from __future__ import annotations

import html as htmllib
import re
import sys
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

WARSAW = ZoneInfo("Europe/Warsaw")
SOURCE_URL = "https://www.mateusz.pl/czytania/"
USER_AGENT = "Mozilla/5.0 (compatible; biblia-kindle/1.0)"

# Skróty ksiąg Ewangelii -> imiona Ewangelistów (dopełniacz)
GOSPEL_AUTHORS = {
    "Mt": "Mateusza",
    "Mk": "Marka",
    "Łk": "Łukasza",
    "J": "Jana",
}

POLISH_MONTHS = [
    "", "stycznia", "lutego", "marca", "kwietnia", "maja", "czerwca",
    "lipca", "sierpnia", "września", "października", "listopada", "grudnia",
]
POLISH_WEEKDAYS = [
    "Poniedziałek", "Wtorek", "Środa", "Czwartek", "Piątek", "Sobota", "Niedziela"
]


# --------------------------------------------------------------------------- #
# Logika daty docelowej
# --------------------------------------------------------------------------- #

def target_date(now: datetime | None = None) -> date:
    """Zwraca datę czytania: dzisiaj, ale od 18:00 — dzień następny."""
    if now is None:
        now = datetime.now(WARSAW)
    else:
        now = now.astimezone(WARSAW)
    if now.hour >= 18:
        now = now + timedelta(days=1)
    return now.date()


# --------------------------------------------------------------------------- #
# Pobieranie i parsowanie
# --------------------------------------------------------------------------- #

def fetch_readings(d: date) -> str:
    url = f"https://www.mateusz.pl/czytania/{d.year}/{d:%Y%m%d}.html"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=60) as resp:
        raw = resp.read()
    # Strona deklaruje utf-8
    return raw.decode("utf-8", errors="replace")


def _strip_tags(html_text: str, keep: tuple[str, ...] = ("br", "p", "small")) -> str:
    """Usuwa wszystkie tagi poza wymienionymi (zachowując zawartość)."""
    # Usuń linki (ale zachowaj tekst)
    html_text = re.sub(r"<a\b[^>]*>", "", html_text, flags=re.IGNORECASE)
    html_text = re.sub(r"</a\s*>", "", html_text, flags=re.IGNORECASE)
    # Usuń img, script, iframe (z zawartością)
    html_text = re.sub(r"<(script|iframe|aside|img)\b.*?</\1\s*>",
                       "", html_text, flags=re.IGNORECASE | re.DOTALL)
    html_text = re.sub(r"<(img|br)\b[^>]*/?>", lambda m: f"<{m.group(1).lower()}>"
                       if m.group(1).lower() in keep else "", html_text, flags=re.IGNORECASE)
    return html_text


def _clean_paragraph(p: str) -> str:
    """Czyści pojedynczy <p>: usuwa linki, normalizuje <br>, zachowuje <small>."""
    p = re.sub(r"<a\b[^>]*>|</a\s*>", "", p, flags=re.IGNORECASE)
    # Normalizuj <br> i <br/>
    p = re.sub(r"<br\s*/?>", "<br>", p, flags=re.IGNORECASE)
    # Usuń puste atrybuty na <small>
    p = re.sub(r"<small\b[^>]*>", "<small>", p, flags=re.IGNORECASE)
    p = re.sub(r"</small\s*>", "</small>", p, flags=re.IGNORECASE)
    return p.strip()


def _extract(text: str, pattern: str, group: int = 1) -> str:
    m = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
    if not m:
        return ""
    return htmllib.unescape(m.group(group)).strip()


def parse(html_text: str) -> dict:
    """Wyciąga z HTML-a mateusz.pl: datę, dzień, podtytuł, paragrafy czytań, info o Ewangelii."""
    # Pomocniczo: usuń pozostałe tagi HTML (np. <text class="holiday">) z pól tekstowych.
    def _plain(s: str) -> str:
        return re.sub(r"<[^>]+>", "", s).strip()

    date_str = _plain(_extract(html_text, r'<p\s+class="data">\s*(.+?)\s*</p>'))
    day = _plain(_extract(html_text, r"<h1>\s*(.+?)\s*</h1>"))
    subtitle = _plain(_extract(html_text, r'<p\s+class="subtitle">\s*(.+?)\s*</p>'))

    # Wyizoluj sekcję "Czytania"
    start = html_text.find('<a name="czytania">')
    if start < 0:
        section = html_text
    else:
        rest = html_text[start:]
        m = re.search(r'<a name="ewangeliarzOP">|<h2>\s*Rozwa', rest)
        section = rest[: m.start()] if m else rest

    # Usuń iframe/aside (np. embedy YouTube)
    section = re.sub(r"<aside\b.*?</aside\s*>", "", section, flags=re.DOTALL | re.IGNORECASE)
    section = re.sub(r"<iframe\b.*?</iframe\s*>", "", section, flags=re.DOTALL | re.IGNORECASE)
    section = re.sub(r"<script\b.*?</script\s*>", "", section, flags=re.DOTALL | re.IGNORECASE)

    # Wszystkie paragrafy
    raw_paragraphs = re.findall(r"<p\b[^>]*>(.*?)</p>", section, re.DOTALL | re.IGNORECASE)
    paragraphs: list[str] = []
    for raw in raw_paragraphs:
        cleaned = _clean_paragraph(raw)
        if cleaned:
            paragraphs.append(cleaned)

    # Znajdź Ewangelię: ostatni paragraf zaczynający się od "(Mt|Mk|Łk|J ...)"
    gospel_idx: int | None = None
    gospel_book: str | None = None
    gospel_ref: str | None = None
    book_pattern = re.compile(r"^\s*\((Mt|Mk|Łk|J)\s+([^)]+)\)", re.UNICODE)
    for i, p in enumerate(paragraphs):
        m = book_pattern.match(p)
        if m:
            gospel_idx = i
            gospel_book = m.group(1)
            gospel_ref = f"{m.group(1)} {m.group(2)}"

    return {
        "date_str": date_str,
        "day": day,
        "subtitle": subtitle,
        "paragraphs": paragraphs,
        "gospel_idx": gospel_idx,
        "gospel_author": GOSPEL_AUTHORS.get(gospel_book or "", ""),
        "gospel_ref": gospel_ref or "",
    }


# --------------------------------------------------------------------------- #
# Renderowanie HTML
# --------------------------------------------------------------------------- #

CSS = """\
* { box-sizing: border-box; margin: 0; padding: 0; }
html, body { margin: 0; padding: 0; background: #ffffff; color: #000000; }
body {
  font-family: "Caecilia", "Bookerly", Georgia, "Times New Roman", serif;
  font-size: 38px;
  line-height: 1.55;
  padding: 0.4em 0.5em 1em 0.5em;
  text-rendering: optimizeLegibility;
}
header { margin-bottom: 0.6em; padding-bottom: 0; }
.date { margin: 0 0 0.2em 0; font-size: 0.95em; }
h1 { margin: 0.1em 0 0.2em 0; font-size: 1.7em; font-weight: bold; }
.subtitle { margin: 0; font-style: italic; font-size: 1em; }

main p { margin: 0.6em 0 1em 0; text-align: justify; hyphens: auto; }

h2.gospel-heading {
  margin: 0.6em 0 0.4em 0;
  padding-top: 0.6em;
  border-top: 1px solid #888;
  font-size: 1.25em;
  font-weight: bold;
  text-align: center;
}
.gospel-ref {
  text-align: center;
  font-style: italic;
  margin: 0 0 0.8em 0;
  font-size: 0.95em;
}

footer {
  margin-top: 1.5em;
  padding-top: 0.4em;
  border-top: 1px solid #888;
  font-size: 0.8em;
  color: #333;
  text-align: center;
}
footer p { margin: 0.2em 0; }
a { color: #000; }
small { font-size: 0.85em; }
"""


def render_html(data: dict, generated_at: datetime, target: date) -> str:
    """Renderuje stronę z samą Ewangelią (data + autor + tekst)."""
    # Zawsze wyliczamy dzień tygodnia z daty docelowej (mateusz.pl nie zawsze go podaje).
    weekday = POLISH_WEEKDAYS[target.weekday()]

    # Subtitle: łączymy to co mateusz.pl dał w <h1> i <p class="subtitle">,
    # ale tylko jeśli <h1> nie jest po prostu nazwą dnia tygodnia (wtedy byłoby redundantne).
    raw_day = data["day"]
    raw_subtitle = data["subtitle"]
    if raw_day in POLISH_WEEKDAYS:
        subtitle = raw_subtitle
    else:
        # <h1> zawiera nazwę święta — użyjemy jej jako subtitle
        subtitle = raw_day if not raw_subtitle else f"{raw_day}. {raw_subtitle}" if raw_day != raw_subtitle else raw_day

    parts: list[str] = []
    gospel_idx = data["gospel_idx"]
    if gospel_idx is not None:
        author = data["gospel_author"] or ""
        ref = data["gospel_ref"] or ""
        heading = (
            f'<h2 class="gospel-heading">Ewangelia wg św. {htmllib.escape(author)}</h2>'
            if author
            else '<h2 class="gospel-heading">Ewangelia</h2>'
        )
        parts.append(heading)
        if ref:
            parts.append(f'<p class="gospel-ref">({htmllib.escape(ref)})</p>')
        # Usuń z paragrafu sam początek "(Skrót ...)<br>" — nagłówek już go zawiera
        gospel_text = re.sub(
            r"^\s*\((Mt|Mk|Łk|J)\s+[^)]+\)\s*(<br\s*/?>)?\s*",
            "",
            data["paragraphs"][gospel_idx],
            count=1,
        )
        parts.append(f"<p>{gospel_text}</p>")

    body = "\n".join(parts) if parts else "<p><em>Brak Ewangelii na ten dzień.</em></p>"

    # Tytuł strony zawiera datę, żeby Kindle pokazywał ją w pasku tytułu
    title = f"Czytanie — {data['date_str']}" if data["date_str"] else "Czytanie na dziś"

    return f"""<!DOCTYPE html>
<html lang="pl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{htmllib.escape(title)}</title>
<meta name="description" content="Czytania liturgiczne na dziś (Kindle).">
<meta http-equiv="refresh" content="3600">
<style>
{CSS}
</style>
</head>
<body>
<header>
<p class="date">{htmllib.escape(data['date_str'])}</p>
<h1>{htmllib.escape(weekday)}</h1>
<p class="subtitle">{htmllib.escape(subtitle)}</p>
</header>
<main>
{body}
</main>
<footer>
<p>Zaktualizowano: {generated_at.strftime('%Y-%m-%d %H:%M')} (Europe/Warsaw)</p>
<p>Źródło: <a href="https://www.mateusz.pl/czytania/{target.year}/{target:%Y%m%d}.html">mateusz.pl</a></p>
</footer>
</body>
</html>
"""


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #

def main(argv: list[str]) -> int:
    # Opcjonalnie pozwala wymusić datę z CLI: python generate.py 2026-05-21
    forced: date | None = None
    if len(argv) >= 2:
        try:
            forced = datetime.strptime(argv[1], "%Y-%m-%d").date()
        except ValueError:
            print(f"Nieprawidłowa data: {argv[1]} (oczekiwany format YYYY-MM-DD)", file=sys.stderr)
            return 2

    now = datetime.now(WARSAW)
    target = forced or target_date(now)
    print(f"Pobieram czytania na {target} (czas warszawski: {now:%Y-%m-%d %H:%M})")

    try:
        html_text = fetch_readings(target)
    except Exception as e:  # noqa: BLE001
        print(f"OSTRZEŻENIE: nie udało się pobrać czytań: {e}", file=sys.stderr)
        # Nie nadpisujemy istniejącego pliku
        return 0

    data = parse(html_text)
    if data["gospel_idx"] is None:
        print("OSTRZEŻENIE: nie udało się znaleźć Ewangelii w pobranej stronie; pomijam zapis.", file=sys.stderr)
        return 0

    output = render_html(data, now, target)
    out_path = Path(__file__).parent / "index.html"

    # Pomiń zapis, jeśli zmienił się tylko stempel czasowy (a treść jest taka sama).
    # Dzięki temu github-actions nie commituje pustych zmian co 30 minut.
    timestamp_re = re.compile(r"<p>Zaktualizowano:[^<]*</p>\s*", re.IGNORECASE)
    if out_path.exists():
        existing = out_path.read_text(encoding="utf-8")
        if timestamp_re.sub("", existing) == timestamp_re.sub("", output):
            print("Bez zmian (poza stemplem czasowym) — pomijam zapis.")
            return 0

    out_path.write_text(output, encoding="utf-8")
    print(f"Zapisano: {out_path} ({len(output)} bajtów)")
    print(f"  Data: {data['date_str']} | {data['day']}")
    print(f"  Ewangelia: św. {data['gospel_author']} ({data['gospel_ref']})")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
