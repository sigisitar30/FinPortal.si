import requests
import pdfplumber
import re
import csv
from datetime import datetime
import os

PDF_URL = "https://www.lon.si/sites/default/files/lbobrestne_mere_fo-letak-1-2026.pdf"

# Pričakovani razponi (po pravilni interpretaciji PDF-ja)
EXPECTED_INTERVALS = [
    (1, 3),
    (3, 6),
    (6, 12),
    (12, 24),
    (24, 36),
    (36, 60),
    (60, None),  # 60M+
]


def scrape_lon_pdf():
    bank_id = 10
    bank_name = "LON d.d."

    print("Prenos LON PDF...")

    headers = {"User-Agent": "Mozilla/5.0"}
    r = requests.get(PDF_URL, headers=headers)
    r.raise_for_status()

    with open("lon.pdf", "wb") as f:
        f.write(r.content)

    results = []
    scraped_raw = []

    # Popravljen regex – ujame: mesec, mesecev, mesece
    regex_single = re.compile(
        r"nad\s+(\d+)\s+mesec(?:ev|e)?\s+(\d+,\d+)\s*%",
        re.IGNORECASE
    )
    regex_range = re.compile(
        r"nad\s+(\d+)\s+mesec(?:ev|e)?\s+do\s+(\d+)\s+mesec(?:ev|e)?\s+(\d+,\d+)\s*%",
        re.IGNORECASE
    )

    with pdfplumber.open("lon.pdf") as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text:
                continue

            # iščemo samo blok klasičnih depozitov
            if "Depoziti do 250.000 €" not in text:
                continue

            # intervali tipa "nad X mesec do Y mesec"
            for m in regex_range.findall(text):
                min_m = int(m[0])
                max_m = int(m[1])
                rate = float(m[2].replace(",", "."))
                scraped_raw.append((min_m, max_m, rate))

            # intervali tipa "nad X mesec"
            for m in regex_single.findall(text):
                min_m = int(m[0])
                max_m = None
                rate = float(m[1].replace(",", "."))
                scraped_raw.append((min_m, max_m, rate))

    # Odstranimo duplikate
    unique = {}
    for min_m, max_m, rate in scraped_raw:
        key = (min_m, max_m)
        if key not in unique:
            unique[key] = rate

    scraped_raw = [(k[0], k[1], v) for k, v in unique.items()]

    # Pretvorimo PDF intervale v dejanske razpone
    def convert_interval(min_m, max_m):
        if min_m == 1:
            return (1, 3)
        if min_m == 3:
            return (3, 6)
        if min_m == 6:
            return (6, 12)
        if min_m == 12 and max_m == 24:
            return (12, 24)
        if min_m == 24:
            return (24, 36)
        if min_m == 36:
            return (36, 60)
        if min_m == 60:
            return (60, None)
        return None

    final_intervals = []

    print("\n--- Najdeni intervali (klasični depoziti) ---")

    for (min_m, max_m, rate) in scraped_raw:
        converted = convert_interval(min_m, max_m)
        if not converted:
            continue

        real_min, real_max = converted
        final_intervals.append((real_min, real_max, rate))

        if real_max:
            print(f"✓ {real_min}M – {real_max}M: {rate}%")
        else:
            print(f"✓ {real_min}M+: {rate}%")

        results.append({
            "id": bank_id,
            "bank": bank_name,
            "product_name": f"Depozit {real_min}M–{real_max}M" if real_max else f"Depozit {real_min}M+",
            "amount_min": 200,
            "amount_max": None,
            "amount_currency": "EUR",
            "min_term": real_min,
            "max_term": real_max,
            "term_unit": "months",
            "rate_branch": rate,
            "rate_klik_bonus": 0.0,
            "rate_klik_total": rate,
            "url": PDF_URL,
            "last_updated": datetime.today().strftime("%Y-%m-%d"),
            "notes": "klasični depozit; linearno obrestovanje; predčasna razvezava ni možna"
        })

    # preverjanje intervalov
    found_intervals = [(m, n) for (m, n, _) in final_intervals]
    expected = EXPECTED_INTERVALS

    if sorted(found_intervals) != sorted(expected):
        print("\n⚠ OPOZORILO: LON je spremenil intervale!")
        print("  Pričakovano:", expected)
        print("  Dobljeno:   ", found_intervals)
    else:
        print("\n✓ Intervali so nespremenjeni.")

    print(f"\n✓ LON: uspešno scrapano {len(results)} intervalov.")
    return results


def save_to_csv(rows, filename="lon_depoziti.csv"):
    if not rows:
        print("Ni podatkov za zapis v CSV.")
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

    print(f"✓ CSV zapisan v: {filename}")


if __name__ == "__main__":
    data = scrape_lon_pdf()
    save_to_csv(data)
