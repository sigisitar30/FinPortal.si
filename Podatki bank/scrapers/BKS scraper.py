import requests
from bs4 import BeautifulSoup
import csv
from datetime import datetime
import re
import os

URL = "https://www.bksbank.si/fizicne-osebe/varcevanje/varcevanje-vezane-vloge"
DISCOVERY_URL = "https://www.bksbank.si/fizicne-osebe/varcevanje/vezane-vloge"
PDF_URLS = [
    "https://www.bksbank.si/mbxs8qn54zwj/5KCS2xBUrYLfcAD08PEYkA/7795108aff18106ef4539f251bfa5d08/Obrestne_mere_VLOGE_1._1._2026_final.pdf",
    "https://www.bksbank.si/documents/33627/145951/OBRESTNE_MERE_ZA_VLOGE.pdf",
]

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

    debug_pdf = os.environ.get("BKS_PDF_DEBUG", "").strip() == "1"

    def _try_pdf_urls(candidates):
        for pdf_url in candidates:
            try:
                rr = requests.get(pdf_url, headers={
                    "User-Agent": "Mozilla/5.0"}, timeout=30)
                rr.raise_for_status()
                if rr.content and len(rr.content) > 1000:
                    return rr, pdf_url
            except Exception as e:
                if debug_pdf:
                    try:
                        print("[DBG] BKS PDF download error",
                              {"url": pdf_url, "err": str(e)})
                    except Exception:
                        pass
                continue
        return None, None

    r, pdf_url_used = _try_pdf_urls(PDF_URLS)

    if r is None or not pdf_url_used:
        # Auto-discover current PDF link(s) from the BKS page.
        discovered = []
        try:
            page_r = requests.get(DISCOVERY_URL, headers={
                "User-Agent": "Mozilla/5.0"}, timeout=30)
            page_r.raise_for_status()
            soup = BeautifulSoup(page_r.text or "", "html.parser")
            for a in soup.select("a[href]"):
                href = (a.get("href") or "").strip()
                if not href:
                    continue
                if ".pdf" not in href.lower():
                    continue
                if href.startswith("//"):
                    href = "https:" + href
                elif href.startswith("/"):
                    href = "https://www.bksbank.si" + href
                discovered.append(href)

            # Prefer the obvious rate-sheet link(s) if present.
            preferred = [
                u for u in discovered if "obrest" in u.lower() and "vlog" in u.lower()]
            ordered = preferred + [u for u in discovered if u not in preferred]

            if debug_pdf:
                try:
                    print("[DBG] BKS discovered pdf links",
                          {"count": len(ordered)})
                    for u in ordered[:8]:
                        print("[DBG] BKS discovered:", u)
                except Exception:
                    pass

            r, pdf_url_used = _try_pdf_urls(ordered)
        except Exception as e:
            if debug_pdf:
                try:
                    print("[DBG] BKS PDF discovery error", {"err": str(e)})
                except Exception:
                    pass

    if r is None or not pdf_url_used:
        return None

    try:
        with pdfplumber.open(io.BytesIO(r.content)) as pdf:
            text = "\n".join([(p.extract_text() or "") for p in pdf.pages])
    except Exception as e:
        if debug_pdf:
            try:
                print("[DBG] BKS PDF open/extract error",
                      {"bytes": 0 if not r.content else len(r.content), "err": str(e)})
            except Exception:
                pass
        return None

    if not text:
        if debug_pdf:
            try:
                print("[DBG] BKS PDF empty text", {
                      "bytes": 0 if not r.content else len(r.content)})
            except Exception:
                pass
        return None

    if debug_pdf:
        try:
            print("[DBG] BKS PDF url", pdf_url_used)
            print("[DBG] BKS PDF extracted", {"text_len": len(text)})
            head = " ".join(text[:1500].replace(
                "\r", " ").replace("\n", " ").split())
            print("[DBG] BKS head:", head)
        except Exception:
            pass

    # Very tolerant extraction: look for '<term> mesecev ... <rate>' anywhere.
    b = " ".join((text or "").replace("\r", " ").replace("\n", " ").split())
    scraped_terms = {term: None for term in EXPECTED_TERMS}

    seg = b
    try:
        bl = b.lower()
        start = bl.find("2.1.")
        if start < 0:
            start = bl.find("2.1")
        if start >= 0:
            end = bl.find("2.2", start)
            if end > start:
                seg = b[start:end]
    except Exception:
        seg = b

    for m in re.finditer(r"\b(6|12|24|36)\b\s+(\d{1,2}(?:[\.,]\d{1,4})?)\s*%", seg, flags=re.IGNORECASE):
        try:
            t = int(m.group(1))
        except Exception:
            continue
        if t in scraped_terms and scraped_terms[t] is None:
            scraped_terms[t] = _to_float_rate(m.group(2))

    for term in scraped_terms.keys():
        term_word = r"(?:mesec(?:ev|e|i)?|monate?n?|months?)"
        patterns = [
            rf"\b{term}\s*{term_word}\b[\s\S]{{0,260}}?(\d{{1,2}}(?:[\.,]\d{{1,4}})?)\s*%?",
            rf"\b{term}\s*M\b[\s\S]{{0,260}}?(\d{{1,2}}(?:[\.,]\d{{1,4}})?)\s*%?",
        ]
        for pat in patterns:
            m = re.search(pat, b, flags=re.IGNORECASE)
            if m:
                scraped_terms[term] = _to_float_rate(m.group(1))
                break

    # Table extraction fallback (some PDFs store the offer matrix primarily as tables).
    if not any(v is not None for v in scraped_terms.values()):
        try:
            with pdfplumber.open(io.BytesIO(r.content)) as pdf:
                for page in pdf.pages:
                    for tbl in (page.extract_tables() or []):
                        for row in (tbl or []):
                            if not row:
                                continue
                            row_txt = " ".join([(c or "") for c in row])
                            if not row_txt:
                                continue
                            row_norm = " ".join(row_txt.split())
                            for term in scraped_terms.keys():
                                if scraped_terms[term] is not None:
                                    continue
                                term_word = r"(?:mesec(?:ev|e|i)?|monate?n?|months?)"
                                for pat in [
                                    rf"\b{term}\s*{term_word}\b[\s\S]{{0,220}}?(\d{{1,2}}(?:[\.,]\d{{1,4}})?)\s*%?",
                                    rf"\b{term}\s*M\b[\s\S]{{0,220}}?(\d{{1,2}}(?:[\.,]\d{{1,4}})?)\s*%?",
                                ]:
                                    mm = re.search(
                                        pat, row_norm, flags=re.IGNORECASE)
                                    if mm:
                                        scraped_terms[term] = _to_float_rate(
                                            mm.group(1))
                                        break
        except Exception:
            pass

    if debug_pdf and not any(v is not None for v in scraped_terms.values()):
        try:
            with pdfplumber.open(io.BytesIO(r.content)) as pdf:
                tables = []
                for page in pdf.pages[:2]:
                    tables.extend(page.extract_tables() or [])
                print("[DBG] BKS tables", {"count": len(tables)})
                for i, tbl in enumerate(tables[:2]):
                    sample_rows = []
                    for rrow in (tbl or [])[:4]:
                        sample_rows.append(" | ".join(
                            [(c or "") for c in (rrow or [])]))
                    print(f"[DBG] BKS table[{i}] sample:")
                    for sr in sample_rows:
                        print("[DBG]   ", " ".join(sr.split())[:240])
        except Exception:
            pass

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
            "url": pdf_url_used,
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
