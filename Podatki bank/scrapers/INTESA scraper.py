import requests
import pdfplumber
import re
import csv
from datetime import datetime
from io import BytesIO
import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

try:
    import certifi
except Exception:
    certifi = None

try:
    import urllib3
except Exception:
    urllib3 = None

PDF_URL = "https://www.intesasanpaolobank.si/document/documents/ISPSLOVENIA/dokumenti-splosni/Obrestne-mere_varcevanja-in-depoziti.pdf"

BANK_ID = 3
BANK_NAME = "Intesa Sanpaolo Bank"

SPECIAL_FROM_MONTH = 12
SPECIAL_RATE = 2.1

# 🔥 1:1 TABELA IZ PDF-JA (najbolj zanesljiv način)
INTEREST_TABLE = {
    # enotne stopnje
    1:  {"single": 0.01},
    2:  {"single": 0.01},
    3:  {"single": 0.01},
    4:  {"single": 0.01},
    5:  {"single": 0.01},

    # dvostopenjske
    6:  {"low": 0.8, "high": 1.0},
    7:  {"low": 0.8, "high": 1.0},
    8:  {"low": 0.8, "high": 1.0},
    9:  {"low": 0.8, "high": 1.0},
    10: {"low": 0.8, "high": 1.0},
    11: {"low": 0.8, "high": 1.0},

    # 12M – redna + posebna
    12: {"low": 1.2, "high": 1.4, "special": 2.1},

    # 13–23M
    **{m: {"low": 1.2, "high": 1.4} for m in range(13, 24)},

    # 24–36M
    **{m: {"low": 1.0, "high": 1.2} for m in range(24, 37)},
}


def extract_dynamic_breakpoint(lines):
    """Najde zneskovni prag (npr. 50.000 EUR) iz PDF-ja."""
    for line in lines:
        if "do vključno" in line and "EUR" in line:
            nums = re.findall(r"(\d{1,3}(?:\.\d{3})*(?:,\d{2})?)", line)
            if nums:
                raw = nums[0]  # npr. "50.000,00"
                raw = raw.replace(".", "").replace(",", ".")  # "50000.00"
                return int(float(raw))
    raise ValueError("Ne najdem zneskovnega praga v PDF-ju.")


def scrape_intesa():
    print("Prenos PDF...")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123 Safari/537.36",
    }
    verify = certifi.where() if certifi is not None else True
    try:
        r = requests.get(PDF_URL, headers=headers, timeout=45, verify=verify)
    except requests.exceptions.SSLError:
        if urllib3 is not None:
            try:
                urllib3.disable_warnings(
                    urllib3.exceptions.InsecureRequestWarning)
            except Exception:
                pass
        r = requests.get(PDF_URL, headers=headers, timeout=45, verify=False)
    r.raise_for_status()
    print("OK PDF prenesen.")

    pdf_bytes = BytesIO(r.content)

    # --- PREBERI PDF VRSTICE ---
    with pdfplumber.open(pdf_bytes) as pdf:
        lines = []
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                lines.extend(text.split("\n"))

    pdf_text = "\n".join(lines)

    # --- PREVERJANJE MIN/MAX ZNESKOV ---
    if "300,00 EUR" not in pdf_text:
        raise ValueError("PDF ne vsebuje minimalnega zneska 300 EUR.")

    if "100.000,00 EUR" not in pdf_text:
        raise ValueError("PDF ne vsebuje maksimalnega zneska 100.000 EUR.")

    print("OK Preverjeni minimalni in maksimalni zneski (300-100000 EUR).")

    # --- DINAMIČNI ZNESKOVNI PRAG ---
    AMOUNT_BREAKPOINT = extract_dynamic_breakpoint(lines)
    print(f"OK Dinamicni zneskovni prag: {AMOUNT_BREAKPOINT} EUR")

    # --- GENERIRANJE CSV ---
    results = []

    for month in range(1, 37):
        if month not in INTEREST_TABLE:
            continue

        entry = INTEREST_TABLE[month]

        # enotna stopnja (1–5M)
        if "single" in entry:
            results.append({
                "id": BANK_ID,
                "bank": BANK_NAME,
                "product_name": f"Depozit {month}M",
                "amount_min": 300,
                "amount_max": 100000,
                "amount_currency": "EUR",
                "min_term": month,
                "max_term": month,
                "term_unit": "months",
                "rate_branch": entry["single"],
                "rate_klik_bonus": 0.0,
                "rate_klik_total": entry["single"],
                "offer_type": "regular",
                "source": "pdf",
                "url": PDF_URL,
                "last_updated": datetime.today().strftime("%d/%m/%Y"),
                "notes": "redna ponudba"
            })
            continue

        # razponi (6–36M)
        if "low" in entry:
            base_rate = entry["low"]
            special_rate = SPECIAL_RATE if month >= SPECIAL_FROM_MONTH else entry.get(
                "special")
            klik_total = special_rate if special_rate is not None else base_rate
            klik_bonus = (
                klik_total - base_rate) if special_rate is not None else 0.0

            results.append({
                "id": BANK_ID,
                "bank": BANK_NAME,
                "product_name": f"Depozit {month}M",
                "amount_min": 300,
                "amount_max": AMOUNT_BREAKPOINT,
                "amount_currency": "EUR",
                "min_term": month,
                "max_term": month,
                "term_unit": "months",
                "rate_branch": base_rate,
                "rate_klik_bonus": klik_bonus,
                "rate_klik_total": klik_total,
                "offer_type": "regular",
                "source": "pdf",
                "url": PDF_URL,
                "last_updated": datetime.today().strftime("%d/%m/%Y"),
                "notes": "redna ponudba"
            })

            if special_rate is not None and abs(float(special_rate) - float(base_rate)) > 1e-9:
                results.append({
                    "id": BANK_ID,
                    "bank": BANK_NAME,
                    "product_name": f"POSEBNA PONUDBA - Depozit {month}M",
                    "amount_min": 300,
                    "amount_max": AMOUNT_BREAKPOINT,
                    "amount_currency": "EUR",
                    "min_term": month,
                    "max_term": month,
                    "term_unit": "months",
                    "rate_branch": float(special_rate),
                    "rate_klik_bonus": 0.0,
                    "rate_klik_total": float(special_rate),
                    "offer_type": "special",
                    "source": "pdf",
                    "url": PDF_URL,
                    "last_updated": datetime.today().strftime("%d/%m/%Y"),
                    "notes": "posebna ponudba",
                })

            if "high" in entry:
                base_rate = entry["high"]
                special_rate = SPECIAL_RATE if month >= SPECIAL_FROM_MONTH else entry.get(
                    "special")
                klik_total = special_rate if special_rate is not None else base_rate
                klik_bonus = (
                    klik_total - base_rate) if special_rate is not None else 0.0

                results.append({
                    "id": BANK_ID,
                    "bank": BANK_NAME,
                    "product_name": f"Depozit {month}M",
                    "amount_min": AMOUNT_BREAKPOINT,
                    "amount_max": 100000,
                    "amount_currency": "EUR",
                    "min_term": month,
                    "max_term": month,
                    "term_unit": "months",
                    "rate_branch": base_rate,
                    "rate_klik_bonus": klik_bonus,
                    "rate_klik_total": klik_total,
                    "offer_type": "regular",
                    "source": "pdf",
                    "url": PDF_URL,
                    "last_updated": datetime.today().strftime("%d/%m/%Y"),
                    "notes": "redna ponudba"
                })

                if special_rate is not None and abs(float(special_rate) - float(base_rate)) > 1e-9:
                    results.append({
                        "id": BANK_ID,
                        "bank": BANK_NAME,
                        "product_name": f"POSEBNA PONUDBA - Depozit {month}M",
                        "amount_min": AMOUNT_BREAKPOINT,
                        "amount_max": 100000,
                        "amount_currency": "EUR",
                        "min_term": month,
                        "max_term": month,
                        "term_unit": "months",
                        "rate_branch": float(special_rate),
                        "rate_klik_bonus": 0.0,
                        "rate_klik_total": float(special_rate),
                        "offer_type": "special",
                        "source": "pdf",
                        "url": PDF_URL,
                        "last_updated": datetime.today().strftime("%d/%m/%Y"),
                        "notes": "posebna ponudba",
                    })

    print(f"OK Najdenih zapisov: {len(results)}")
    return results


def save_to_csv(rows, filename="intesa_depoziti.csv"):
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    filename = os.path.join(base_dir, filename)

    fieldnames = [
        "id", "bank", "product_name",
        "amount_min", "amount_max", "amount_currency",
        "min_term", "max_term", "term_unit",
        "rate_branch", "rate_klik_bonus", "rate_klik_total",
        "offer_type", "source", "url", "last_updated", "notes"
    ]

    for r in rows:
        if isinstance(r, dict) and not r.get("offer_type"):
            r["offer_type"] = "special" if "posebna" in str(
                r.get("notes") or "").lower() else "regular"
        if isinstance(r, dict) and not r.get("source"):
            u = str(r.get("url") or "").lower()
            r["source"] = "pdf" if (
                ".pdf" in u or "downloadfile" in u or "fileid" in u) else "web"

    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=";")
        writer.writeheader()
        writer.writerows(rows)

    print(f"OK CSV zapisan v: {filename}")


if __name__ == "__main__":
    data = scrape_intesa()
    save_to_csv(data)
