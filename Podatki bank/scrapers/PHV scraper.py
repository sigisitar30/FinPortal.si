import csv
import os
import re
import sys
from datetime import datetime

import requests
from bs4 import BeautifulSoup


URL = "https://phv.si/obrestne-mere/"


def _sanity_check_rows(rows):
    if not isinstance(rows, list) or len(rows) == 0:
        raise RuntimeError("PHV: sanity check failed: no rows")

    if len(rows) < 6:
        raise RuntimeError(
            f"PHV: sanity check failed: too few rows ({len(rows)})")

    required = [
        (15, 30, "days"),
        (31, 60, "days"),
        (12, 24, "months"),
        (24, 36, "months"),
    ]

    got = set()
    for r in rows:
        try:
            got.add((int(r.get("min_term")), int(
                r.get("max_term")), str(r.get("term_unit"))))
        except Exception:
            continue

    missing = [x for x in required if x not in got]
    if missing:
        raise RuntimeError(
            f"PHV: sanity check failed: missing buckets {missing}")


def _parse_float_rate(text: str):
    s = str(text or "").strip()
    if not s:
        return None
    s = s.replace("%", "").replace("\xa0", " ").strip()
    s = s.replace(".", "").replace(",", ".")
    try:
        return round(float(s), 4)
    except Exception:
        return None


def _extract_last_updated_iso(html_text: str) -> str:
    m = re.search(r"Veljavnost\s+od\s+(\d{2})\.(\d{2})\.(\d{4})", html_text)
    if not m:
        return datetime.today().strftime("%Y-%m-%d")
    dd, mm, yyyy = int(m.group(1)), int(m.group(2)), int(m.group(3))
    try:
        return datetime(yyyy, mm, dd).strftime("%Y-%m-%d")
    except Exception:
        return datetime.today().strftime("%Y-%m-%d")


def _parse_term(label: str):
    t = str(label or "").lower()
    t = t.replace("\xa0", " ")
    t = " ".join(t.split())

    if "dni" in t:
        # od X do Y dni
        m = re.search(r"od\s*(\d+)\s*do\s*(\d+)\s*dni", t)
        if m:
            return int(m.group(1)), int(m.group(2)), "days"

        # do Y dni
        m = re.search(r"do\s*(\d+)\s*dni", t)
        if m:
            return 1, int(m.group(1)), "days"

        # od X dni do N mesecev (pretvorimo v days)
        m = re.search(r"od\s*(\d+)\s*dni\s*do\s*(\d+)\s*mesecev", t)
        if m:
            a = int(m.group(1))
            mo = int(m.group(2))
            # PHV uporablja "12 mesecev" kot ~1 leto.
            b = 365 if mo == 12 else max(a, int(round(mo * 30.4167)))
            return a, b, "days"

    if "mesecev" in t or "mesec" in t:
        m = re.search(r"od\s*(\d+)\s*mesecev\s*do\s*(\d+)\s*mesecev", t)
        if m:
            return int(m.group(1)), int(m.group(2)), "months"

        m = re.search(r"od\s*(\d+)\s*mesecev\s*do\s*(\d+)\s*mesec", t)
        if m:
            return int(m.group(1)), int(m.group(2)), "months"

        m = re.search(r"do\s*(\d+)\s*mesecev", t)
        if m:
            return 1, int(m.group(1)), "months"

    return None, None, None


def scrape_phv_deposits_for_population():
    bank_id = 12
    bank_name = "Primorska hranilnica"

    r = requests.get(URL, headers={"User-Agent": "Mozilla/5.0"}, timeout=45)
    r.raise_for_status()
    html = r.text or ""

    soup = BeautifulSoup(html, "html.parser")

    last_updated = _extract_last_updated_iso(html)
    amount_min = 500

    # Find the section "2. OBRESTNE MERE ZA DEPOZITE IN VARČEVANJA" (fizične osebe)
    h2 = soup.find("h2", id="obrestne-pasivni-posli")
    if not h2:
        raise RuntimeError("PHV: section obrestne-pasivni-posli not found")

    # Find title "2.1.1" and its next table
    h3 = None
    for cand in h2.find_all_next("h3", class_="table-title"):
        txt = " ".join((cand.get_text(" ") or "").split())
        if "2.1.1" in txt:
            h3 = cand
            break
        # stop if we reached the next big section for PO
        if "2.2" in txt or "2. OBRESTNE MERE ZA DEPOZITE" in txt:
            break

    if not h3:
        raise RuntimeError("PHV: table title 2.1.1 not found")

    table = h3.find_next("table", class_="fixed-width-table")
    if not table:
        raise RuntimeError("PHV: table for 2.1.1 not found")

    rows = []
    for tr in table.find_all("tr"):
        tds = tr.find_all("td")
        if len(tds) < 2:
            continue

        label = " ".join((tds[0].get_text(" ") or "").split())
        rate_txt = " ".join((tds[1].get_text(" ") or "").split())

        if not label:
            continue

        # Exclude non-term passive products
        low = label.lower()
        if "stanje na transakcijskem računu" in low:
            continue
        if "odp" in low and "vloga" in low:
            continue

        rate = _parse_float_rate(rate_txt)
        if rate is None:
            continue

        min_term, max_term, term_unit = _parse_term(label)
        if term_unit is None or min_term is None:
            # Skip anything that does not encode a term.
            continue

        rows.append(
            {
                "id": bank_id,
                "bank": bank_name,
                "product_name": label,
                "amount_min": amount_min,
                "amount_max": "",
                "amount_currency": "EUR",
                "min_term": min_term,
                "max_term": max_term,
                "term_unit": term_unit,
                "rate_branch": rate,
                "rate_klik_bonus": 0,
                "rate_klik_total": rate,
                "url": URL,
                "last_updated": last_updated,
                "notes": "",
                "offer_type": "regular",
                "source": "web",
            }
        )

    if not rows:
        raise RuntimeError("PHV: 0 deposit rows parsed")

    return rows


def main():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out_path = os.path.join(base_dir, "phv_depoziti.csv")

    rows = scrape_phv_deposits_for_population()
    _sanity_check_rows(rows)

    fieldnames = [
        "id",
        "bank",
        "product_name",
        "amount_min",
        "amount_max",
        "amount_currency",
        "min_term",
        "max_term",
        "term_unit",
        "rate_branch",
        "rate_klik_bonus",
        "rate_klik_total",
        "url",
        "last_updated",
        "notes",
        "offer_type",
        "source",
    ]

    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, delimiter=";")
        w.writeheader()
        for r in rows:
            w.writerow(r)

    print(f"[OK] PHV: parsed {len(rows)} deposit rows -> {out_path}")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"[WARN] PHV scraper failed: {e}")
        sys.exit(1)
