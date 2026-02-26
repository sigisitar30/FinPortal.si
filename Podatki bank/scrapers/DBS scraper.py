import requests
import pdfplumber
import re
import csv
from datetime import datetime
import os


PDF_URL = "https://www.dbs.si/document-download/196-obrestne-mere-fizicne-osebe"


def _to_float_rate(s):
    try:
        return float(s.replace("%", "").replace(",", ".").strip())
    except:
        return None


def _extract_min_amount_eur(text):
    if not text:
        return None

    t = (
        text.lower()
        .replace("\xa0", " ")
        .replace("\u202f", " ")
        .replace(".", "")
    )

    patterns = [
        r"(?:minimalni\s+znesek|minimalen\s+znesek|najmanj|min\.)\s*(\d[\d\s]*)\s*(?:eur|€)",
        r"(\d[\d\s]*)\s*(?:eur|€)\s*(?:minimalni\s+znesek|minimalen\s+znesek|najmanj|min\.)",
    ]

    vals = []
    for pat in patterns:
        for m in re.finditer(pat, t):
            raw = re.sub(r"\s+", "", m.group(1))
            try:
                val = int(raw)
                if 0 < val < 1_000_000:
                    vals.append(val)
            except:
                pass

    if not vals:
        return None

    return min(vals)


def scrape_dbs():
    bank_id = 11
    bank_name = "DBS d.d."

    headers = {"User-Agent": "Mozilla/5.0"}
    r = requests.get(PDF_URL, headers=headers)
    r.raise_for_status()

    pdf_path = "dbs.pdf"
    with open(pdf_path, "wb") as f:
        f.write(r.content)

    with pdfplumber.open(pdf_path) as pdf:
        all_text = "\n".join([(p.extract_text() or "") for p in pdf.pages])

    amount_min_floor = _extract_min_amount_eur(all_text)
    if amount_min_floor is None or amount_min_floor < 100:
        amount_min_floor = 100

    results = []
    month_thresholds = []

    # Fokus: Depoziti v DOMACI valuti (EUR): fiksne OM
    day_range_re = re.compile(
        r"Depoziti\s+vezani\s+od\s+(\d+)\s+do\s+(\d+)\s+dni\s+(\d+[\.,]\d+)",
        re.IGNORECASE,
    )
    year_over_re = re.compile(
        r"Depoziti\s+vezani\s+nad\s+(\d+)\s+let[aio]?m?\s+(\d+[\.,]\d+)",
        re.IGNORECASE,
    )

    for m in day_range_re.finditer(all_text):
        d1 = int(m.group(1))
        d2 = int(m.group(2))
        rate = _to_float_rate(m.group(3))
        if rate is None:
            continue

        results.append(
            {
                "id": bank_id,
                "bank": bank_name,
                "product_name": f"Depozit {d1}-{d2} dni",
                "amount_min": amount_min_floor,
                "amount_max": None,
                "amount_currency": "EUR",
                "min_term": d1,
                "max_term": d2,
                "term_unit": "days",
                "rate_branch": rate,
                "rate_klik_bonus": 0.0,
                "rate_klik_total": rate,
                "url": PDF_URL,
                "last_updated": datetime.today().strftime("%Y-%m-%d"),
                "notes": "scraped via pdfplumber; depoziti v DOMACI valuti (EUR)",
            }
        )

    for m in year_over_re.finditer(all_text):
        years = int(m.group(1))
        rate = _to_float_rate(m.group(2))
        if rate is None:
            continue

        months = years * 12
        month_thresholds.append((months, rate))

    # Pretvori pragove v intervale (X .. nextX-1), zadnji interval pa do 360M.
    # Razlog: frontend dela z "term_months" (točne ročnosti), zato max_term=None povzroči,
    # da se ponudba uporabi samo za točen mesec.
    if month_thresholds:
        MAX_MONTHS = 360
        thresholds = sorted({m for m, _ in month_thresholds})
        rate_by_threshold = {}
        for m, r in month_thresholds:
            # če se prag pojavi večkrat, preferiraj višjo OM (varovalka)
            rate_by_threshold[m] = max(
                rate_by_threshold.get(m, float("-inf")), r)

        for i, thr in enumerate(thresholds):
            min_m = thr
            max_m = (thresholds[i + 1] - 1) if i + \
                1 < len(thresholds) else MAX_MONTHS
            rate = rate_by_threshold.get(thr)
            if rate is None:
                continue
            if max_m < min_m:
                continue

            label = f"{min_m}M" if min_m == max_m else f"{min_m}-{max_m}M"
            results.append(
                {
                    "id": bank_id,
                    "bank": bank_name,
                    "product_name": f"Depozit {label}",
                    "amount_min": amount_min_floor,
                    "amount_max": None,
                    "amount_currency": "EUR",
                    "min_term": min_m,
                    "max_term": max_m,
                    "term_unit": "months",
                    "rate_branch": rate,
                    "rate_klik_bonus": 0.0,
                    "rate_klik_total": rate,
                    "url": PDF_URL,
                    "last_updated": datetime.today().strftime("%Y-%m-%d"),
                    "notes": "scraped via pdfplumber; depoziti v DOMACI valuti (EUR)",
                }
            )

    # dedup by term + unit
    dedup = {}
    for row in results:
        key = (
            row["term_unit"],
            row["min_term"],
            row["max_term"],
        )
        if key not in dedup:
            dedup[key] = row

    final = list(dedup.values())

    print(f"OK DBS: scrapano {len(final)} zapisov")
    return final


def save_to_csv(rows, filename="dbs_depoziti.csv"):
    if not rows:
        print("WRN Ni podatkov za zapis v CSV.")
        return

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    filename = os.path.join(base_dir, filename)

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
    ]

    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=";")
        writer.writeheader()
        writer.writerows(rows)

    print(f"OK CSV zapisan v: {filename}")


if __name__ == "__main__":
    data = scrape_dbs()
    save_to_csv(data)
