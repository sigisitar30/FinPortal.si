import requests
from datetime import datetime
import csv
import os

import io
import re

import pdfplumber

# CONFIG ENDPOINT
CONFIG_URL = "https://www.nlb.si/content/nlbbanks/nlbsi/sl/osebno/varcevanja-in-nalozbe/izracun-varcevanja.savingsconfig.configName=depozit.json"

# BASE URL for calculation
BASE_CALC = "https://www.nlb.si/content/nlbbanks/nlbsi/sl/osebno/varcevanja-in-nalozbe/izracun-varcevanja.savingscalculate"

# Human-facing page (used to obtain cookies / pass basic bot checks)
CALC_PAGE_URL = "https://www.nlb.si/osebno/varcevanja-in-nalozbe/izracun-varcevanja"

PDF_URL = "https://www.nlb.si/content/dam/nlb/pdf-files/osebne-finance/varcevanja-in-nalozbe/NLB-Depoziti-in-varcevanja-obrestne-mere-in-tarifa-za-prebivalstvo.pdf"

# Slider meje z NLB strani (ročni vnos, produktna realnost)
SLIDER_MIN = 2000
SLIDER_MAX = 250000

# Pričakovane vrednosti (varovalke)
EXPECTED_API_MIN = 1500          # iz config API (min_znesek.EUR)
EXPECTED_MIN_AMOUNT = 1500       # min(amount) = min(API_min, SLIDER_MIN)
EXPECTED_MAX_AMOUNT = 250000     # max(amount) = SLIDER_MAX


def _make_session():
    s = requests.Session()
    s.headers.update(
        {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Accept-Language": "sl-SI,sl;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept": "application/json, text/plain, */*",
            "DNT": "1",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
        }
    )
    return s


SESSION = _make_session()


def fetch_config():
    """Prebere konfiguracijo depozitov (ročnosti, min znesek)."""
    # Prime cookies / basic bot checks by visiting the human page first.
    try:
        SESSION.get(
            CALC_PAGE_URL,
            headers={
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"},
            timeout=20,
        )
    except Exception:
        # If this fails, we still try config directly.
        pass

    headers = {
        "Accept": "application/json, text/plain, */*",
        "Referer": CALC_PAGE_URL,
        "X-Requested-With": "XMLHttpRequest",
    }

    r = SESSION.get(CONFIG_URL, headers=headers, timeout=20)
    r.raise_for_status()
    return r.json()


def fetch_rate(amount, term):
    """Pokliče API endpoint in vrne (poslovalnica, klik_pribitek, klik_total)."""

    url = (
        f"{BASE_CALC}."
        f"storitve=depozit."
        f"znesek={amount}."
        f"anuiteta=0."
        f"rocnost={term}.json"
    )

    headers = {
        "Accept": "application/json",
        "Referer": CALC_PAGE_URL,
        "X-Requested-With": "XMLHttpRequest",
    }

    r = SESSION.get(url, headers=headers, timeout=20)
    if r.status_code == 403:
        return None, None, None

    try:
        data = r.json()
    except:
        return None, None, None

    try:
        izracun = data[0]["izracuni"][0]
        om = izracun.get("om")
        if not om:
            return None, None, None

        poslovalnica = om.get("value", 0) or 0
        klik_pribitek = om.get("klik", 0) or 0

        poslovalnica = round(float(poslovalnica), 2)
        klik_pribitek = round(float(klik_pribitek), 2)
        klik_total = round(poslovalnica + klik_pribitek, 2)

        return poslovalnica, klik_pribitek, klik_total

    except:
        return None, None, None


def _to_float_rate(s: str):
    try:
        return float(str(s).replace("%", "").replace(" ", "").replace("\u00a0", "").replace(",", "."))
    except:
        return None


def _scrape_nlb_from_pdf():
    bank_id = 1
    bank_name = "NLB d.d."
    today = datetime.today().strftime("%Y-%m-%d")

    print("INFO NLB: branje PDF obrestnih mer...")

    r = requests.get(PDF_URL, timeout=30)
    r.raise_for_status()

    with pdfplumber.open(io.BytesIO(r.content)) as pdf:
        lines = []
        for page in pdf.pages:
            t = page.extract_text() or ""
            if t:
                lines.extend(t.split("\n"))

    text = "\n".join(lines)
    if not text:
        raise RuntimeError("PDF text empty")

    # Izreži samo sekcijo: 1.1 Depoziti v EUR
    m_start = re.search(r"\b1\.1\.?\s*Depoziti\s+v\s+EUR\b",
                        text, flags=re.IGNORECASE)
    if not m_start:
        raise RuntimeError("PDF: section 'Depoziti v EUR' not found")

    m_end = re.search(r"\b1\.2\.?\s*Depoziti\s+v\s+CHF\b",
                      text, flags=re.IGNORECASE)
    section = text[m_start.start(): (
        m_end.start() if m_end and m_end.start() > m_start.start() else len(text))]

    # Minimalni znesek (pričakovano 1.500)
    amount_min = EXPECTED_MIN_AMOUNT
    try:
        m_min = re.search(
            r"od\s*([0-9\.]+),(\d{2})\s*dalje", section, flags=re.IGNORECASE)
        if m_min:
            amount_min = int(
                float(m_min.group(1).replace(".", "") + "." + m_min.group(2)))
    except:
        amount_min = EXPECTED_MIN_AMOUNT

    amount_max = EXPECTED_MAX_AMOUNT

    # Tabela ima dve stopnji: NLB Klik (preko Klik) in poslovalnica/KC.
    # V vrstici sta običajno navedeni obe OM, npr:
    # "od 31 do vključno 365 dni 0,5500 % 0,4500 %"
    # Interpretacija: najprej Klik, nato poslovalnica.
    rows = []
    pat_days = re.compile(
        r"od\s*(\d+)\s*do\s*vklju\u010dno\s*(\d+)\s*dni\s*([0-9]+,[0-9]+)\s*%\s*([0-9]+,[0-9]+)\s*%",
        flags=re.IGNORECASE,
    )
    pat_months = re.compile(
        r"od\s*(\d+)\s*do\s*vklju\u010dno\s*(\d+)\s*mesecev\*?\s*([0-9]+,[0-9]+)\s*%\s*([0-9]+,[0-9]+)\s*%",
        flags=re.IGNORECASE,
    )

    for a, b, klik_s, branch_s in pat_days.findall(section):
        klik = _to_float_rate(klik_s)
        branch = _to_float_rate(branch_s)
        if klik is None or branch is None:
            continue
        rows.append(("days", int(a), int(b), branch, klik))

    for a, b, klik_s, branch_s in pat_months.findall(section):
        klik = _to_float_rate(klik_s)
        branch = _to_float_rate(branch_s)
        if klik is None or branch is None:
            continue
        rows.append(("months", int(a), int(b), branch, klik))

    if not rows:
        raise RuntimeError("PDF: no EUR deposit rates parsed")

    results = []
    for unit, a, b, branch, klik_total in rows:
        klik_bonus = round(float(klik_total) - float(branch), 4)
        results.append(
            {
                "id": bank_id,
                "bank": bank_name,
                "product_name": f"Depozit {a}-{b} {'dni' if unit == 'days' else 'M'}",
                "amount_min": amount_min,
                "amount_max": amount_max,
                "amount_currency": "EUR",
                "min_term": a,
                "max_term": b,
                "term_unit": unit,
                "rate_branch": round(float(branch), 4),
                "rate_klik_bonus": klik_bonus,
                "rate_klik_total": round(float(klik_total), 4),
                "url": PDF_URL,
                "last_updated": today,
                "notes": "scraped via PDF",
            }
        )

    print(f"OK NLB: PDF scrapano {len(results)} zapisov")
    return results


def scrape_nlb():
    try:
        return _scrape_nlb_from_pdf()
    except Exception as e:
        print(
            f"WRN NLB: PDF scrape ni uspel ({e}) → fallback na API kalkulator")
        return _scrape_nlb_from_api()


def _scrape_nlb_from_api():
    print("→ Nalagam konfiguracijo...")

    config = fetch_config()

    # ročnosti za EUR depozit
    terms = config["rocnosti"]["nespremenljiva"]["EUR"]

    # sortiramo ročnosti (1D, 7D, 1M, 3M, ...)
    terms_sorted = sorted(terms, key=lambda x: (x.endswith("D"), int(x[:-1])))

    # API minimalni znesek
    api_min = config["min_znesek"]["EUR"]

    # izračun amount_min/amount_max
    amount_min = min(api_min, SLIDER_MIN)
    amount_max = SLIDER_MAX

    # pričakovane ročnosti (varovalka)
    EXPECTED_TERMS = terms_sorted.copy()

    results = []
    bank_id = 1
    bank_name = "NLB d.d."

    print("→ Pridobivam obrestne mere...")

    for term in terms_sorted:
        poslovalnica, klik_pribitek, klik = fetch_rate(amount_min, term)

        if poslovalnica is None:
            print(f"✗ Preskočeno (API ni vrnil OM): {term}")
            continue

        # pretvorba ročnosti
        if term.endswith("D"):
            min_term = max_term = int(term.replace("D", ""))
            unit = "days"
        else:
            min_term = max_term = int(term.replace("M", ""))
            unit = "months"

        row = {
            "id": bank_id,
            "bank": bank_name,
            "product_name": f"Depozit {term}",
            "amount_min": amount_min,
            "amount_max": amount_max,
            "amount_currency": "EUR",
            "min_term": min_term,
            "max_term": max_term,
            "term_unit": unit,
            "rate_branch": poslovalnica,
            "rate_klik_bonus": klik_pribitek,
            "rate_klik_total": klik,
            "url": BASE_CALC,
            "last_updated": datetime.today().strftime("%Y-%m-%d"),
            "notes": "scraped from NLB API (Klik obrestna mera)"
        }

        results.append(row)
        print(f"✓ {term}: poslovalnica {poslovalnica}%, Klik {klik}%")

    # preverjanje ročnosti
    print("\n→ Preverjam spremembe ročnosti...")

    if terms_sorted != EXPECTED_TERMS:
        print("⚠ OPOZORILO: NLB je spremenila ročnosti!")
        print("  Pričakovano:", EXPECTED_TERMS)
        print("  Dobljeno:   ", terms_sorted)
    else:
        print("✓ Ročnosti so nespremenjene.")

    # preverjanje min/max zneska
    print("\n→ Preverjam min/max znesek...")

    if api_min != EXPECTED_API_MIN:
        print(
            f"⚠ OPOZORILO: API min_znesek se je spremenil! API vrne: {api_min}, pričakovano: {EXPECTED_API_MIN}")

    if amount_min != EXPECTED_MIN_AMOUNT:
        print(
            f"⚠ OPOZORILO: amount_min se je spremenil! Trenutno: {amount_min}, pričakovano: {EXPECTED_MIN_AMOUNT}")

    if amount_max != EXPECTED_MAX_AMOUNT:
        print(
            f"⚠ OPOZORILO: amount_max se je spremenil! Trenutno: {amount_max}, pričakovano: {EXPECTED_MAX_AMOUNT}")

    print(f"\n✓ NLB: uspešno scrapano {len(results)} zapisov.")
    return results


def save_to_csv(rows, filename="nlb_depoziti.csv"):
    if not rows:
        print("⚠ Ni podatkov za zapis v CSV.")
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
    data = scrape_nlb()
    save_to_csv(data)
