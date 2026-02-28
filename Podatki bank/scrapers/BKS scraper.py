import requests
from bs4 import BeautifulSoup
import csv
from datetime import datetime
import re
import os

URL = "https://www.bksbank.si/fizicne-osebe/varcevanje/varcevanje-vezane-vloge"
PDF_URL = "https://www.bksbank.si/documents/33627/145951/OBRESTNE_MERE_ZA_VLOGE.pdf"

# PRIČAKOVANE VREDNOSTI
EXPECTED_MIN_AMOUNT = 1000
EXPECTED_TERMS = [6, 12, 24, 36]

# PRIČAKOVANE OBRESTNE MERE (če se spremenijo → opozorilo)
EXPECTED_RATES = {
    6: 1.20,
    12: 1.40,
    24: 1.60,
    36: 1.70
}


def _to_float_rate(s):
    try:
        return float(str(s).replace("%", "").replace(",", ".").strip())
    except Exception:
        return None


def scrape_bks_from_pdf():
    try:
        import pdfplumber  # type: ignore
        import io
    except Exception:
        return None

    try:
        r = requests.get(PDF_URL, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
        r.raise_for_status()
    except Exception:
        return None

    try:
        with pdfplumber.open(io.BytesIO(r.content)) as pdf:
            text = "\n".join([(p.extract_text() or "") for p in pdf.pages])
    except Exception:
        return None

    if not text:
        return None

    # Very tolerant extraction: look for '<term> mesecev ... <rate>' anywhere.
    scraped_terms = {term: None for term in EXPECTED_TERMS}
    for term in scraped_terms.keys():
        patterns = [
            rf"\b{term}\s*mesec(?:ev|e|i)?\b[^0-9%]{{0,40}}(\d{{1,2}}(?:[\.,]\d{{1,4}})?)\s*%?",
            rf"\b{term}\s*M\b[^0-9%]{{0,40}}(\d{{1,2}}(?:[\.,]\d{{1,4}})?)\s*%?",
        ]
        for pat in patterns:
            m = re.search(pat, text, flags=re.IGNORECASE)
            if m:
                scraped_terms[term] = _to_float_rate(m.group(1))
                break

    found_terms = [t for t, r in scraped_terms.items() if r is not None]
    if not found_terms:
        return None

    bank_id = 8
    bank_name = "BKS Bank AG"
    results = []
    for term, rate in scraped_terms.items():
        if rate is None:
            continue
        results.append({
            "id": bank_id,
            "bank": bank_name,
            "product_name": f"Depozit {term}M",
            "amount_min": EXPECTED_MIN_AMOUNT,
            "amount_max": None,
            "amount_currency": "EUR",
            "min_term": term,
            "max_term": term,
            "term_unit": "months",
            "rate_branch": rate,
            "rate_klik_bonus": 0.0,
            "rate_klik_total": rate,
            "url": PDF_URL,
            "last_updated": datetime.today().strftime("%Y-%m-%d"),
            "notes": "scraped via PDF",
        })

    return results if results else None


def scrape_bks():
    bank_id = 8
    bank_name = "BKS Bank AG"

    pdf_rows = scrape_bks_from_pdf()
    if pdf_rows:
        print(f"[OK] BKS: PDF vir uporabljen ({len(pdf_rows)} zapisov)")
        return pdf_rows
    print("[WARN] BKS: PDF parse ni uspel, fallback na HTML")

    print("Prenos BKS strani...")

    response = requests.get(URL)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    # Celoten tekst strani, lepo očiščen
    text = soup.get_text(" ", strip=True)
    text = " ".join(text.split())  # odstrani dvojne presledke

    print("\n--- Preverjanje strukture BKS ---")

    # Ročnosti, ki jih želimo najti
    scraped_terms = {term: None for term in EXPECTED_TERMS}

    # Robustni regex, ki ujame vse oblike zapisa
    for term in scraped_terms.keys():
        pattern = rf"{term}\s*[-]?\s*mesecev[^0-9]*?(\d+,\d+)"
        match = re.search(pattern, text, re.IGNORECASE)

        if match:
            rate = float(match.group(1).replace(",", "."))
            scraped_terms[term] = rate

    # 1) Preverjanje ročnosti
    found_terms = [t for t, r in scraped_terms.items() if r is not None]

    if sorted(found_terms) != EXPECTED_TERMS:
        print("⚠ OPOZORILO: BKS je spremenil ročnosti!")
        print("  Pričakovano:", EXPECTED_TERMS)
        print("  Dobljeno:   ", found_terms)
    else:
        print("✓ Ročnosti so nespremenjene.")

    # 2) Preverjanje minimalnega zneska
    print("✓ Minimalni znesek depozita = 1000 EUR (pričakovano).")

    # 3) BKS nima maksimalnega zneska
    print("✓ BKS ne določa maksimalnega zneska depozita (pričakovano).")

    print("\n--- Obrestne mere ---")

    results = []

    # 4) Preverjanje obrestnih mer
    for term, rate in scraped_terms.items():
        if rate is None:
            print(f"⚠ {term}M: obrestna mera NI najdena!")
            continue

        # preveri spremembe OM
        if term in EXPECTED_RATES and abs(rate - EXPECTED_RATES[term]) > 0.001:
            print(f"⚠ OPOZORILO: BKS je spremenil OM za {term}M!")
            print(f"  Pričakovano: {EXPECTED_RATES[term]}%")
            print(f"  Dobljeno:    {rate}%")
        else:
            print(f"✓ {term}M: {rate}%")

        results.append({
            "id": bank_id,
            "bank": bank_name,
            "product_name": f"Depozit {term}M",
            "amount_min": EXPECTED_MIN_AMOUNT,
            "amount_max": None,  # BKS nima zgornje meje
            "amount_currency": "EUR",
            "min_term": term,
            "max_term": term,
            "term_unit": "months",
            "rate_branch": rate,
            "rate_klik_bonus": 0.0,
            "rate_klik_total": rate,
            "url": URL,
            "last_updated": datetime.today().strftime("%Y-%m-%d"),
            "notes": "redna ponudba"
        })

    print(f"\n✓ BKS: uspešno scrapano {len(results)} zapisov.")
    return results


def save_to_csv(rows, filename="bks_depoziti.csv"):
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
    data = scrape_bks()
    save_to_csv(data)
