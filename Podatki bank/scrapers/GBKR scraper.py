import csv
from datetime import datetime
import os
import re
import requests

URL = "https://www.gbkr.si/klasicni-depozit/"
PDF_URLS = [
    "https://www.gbkr.si/wp-content/uploads/pdfs/obrestne-mere-za-depozite-za-prebivalstvo.pdf",
    "https://www.gbkr.si/wp-content/uploads/pdfs/obrestne-mere-za-depozite-za-prebivalstvo.pdf?ver=1758634926",
    "https://www.gbkr.si/wp-content/uploads/2024/08/Obrestne-mere-za-depozite-za-prebivalstvo.pdf",
    "https://www.gbkr.si/wp-content/uploads/2024/08/Obrestne-mere-za-depozite-za-prebivalstvo.pdf?ver=1751369650",
    "https://www.gbkr.si/wp-content/uploads/2021/05/OM_PO_depoziti.pdf",
]

# Gorenjska banka omogoča zneske 250–500000 EUR
EXPECTED_MIN_AMOUNT = 250
EXPECTED_MAX_AMOUNT = 500000

# Mesečni depozit je relevanten od 13M dalje; krajše ročnosti se prikazujejo v dneh.
CHECK_TERMS = list(range(13, 61))


def _to_float_rate(s):
    try:
        return float(str(s).replace("%", "").replace(",", ".").strip())
    except Exception:
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
            except Exception:
                pass

    if not vals:
        return None
    return min(vals)


def scrape_gbkr_from_pdf():
    try:
        import pdfplumber  # type: ignore
        import io
    except Exception:
        return None

    debug_pdf = os.environ.get("GBKR_PDF_DEBUG", "").strip() == "1"

    r = None
    pdf_url_used = None
    text = None
    for pdf_url in PDF_URLS:
        rr = None
        try:
            rr = requests.get(pdf_url, headers={
                "User-Agent": "Mozilla/5.0"}, timeout=30)
            rr.raise_for_status()
            if not rr.content or len(rr.content) <= 1000:
                if debug_pdf:
                    print("[DBG] GBKR PDF skip (too small)", {
                          "url": pdf_url, "bytes": 0 if not rr.content else len(rr.content)})
                continue
        except Exception:
            if debug_pdf:
                print("[DBG] GBKR PDF skip (download error)", {"url": pdf_url})
            continue

        t = None
        try:
            with pdfplumber.open(io.BytesIO(rr.content)) as pdf:
                t = "\n".join([(p.extract_text() or "") for p in pdf.pages])
        except Exception:
            t = None

        if not t or len(t.strip()) < 100:
            if debug_pdf:
                print("[DBG] GBKR PDF skip (no text)", {
                      "url": pdf_url, "text_len": 0 if not t else len(t)})
            continue

        low_all = t.lower()

        # This PDF is known to sometimes be a corporate summary ("Povzetek za podjetja")
        # and may not contain month-based retail deposit terms. In that case, do not use it.
        if ("podjetja" in low_all) and ("mesec" not in low_all):
            if debug_pdf:
                print("[DBG] GBKR PDF skip (corporate summary)",
                      {"url": pdf_url})
            continue

        if "izvleček" in low_all and "obrestn" in low_all:
            if debug_pdf:
                head = " ".join(t[:220].replace(
                    "\r", " ").replace("\n", " ").split())
                print("[DBG] GBKR PDF note (izvlecek summary)",
                      {"url": pdf_url, "head": head})

        r = rr
        pdf_url_used = pdf_url
        text = t
        break

    if r is None or not pdf_url_used or not text:
        if debug_pdf:
            print("[DBG] GBKR PDF no suitable document found",
                  {"tried": len(PDF_URLS)})
        return None

    amount_min_floor = _extract_min_amount_eur(text)
    if amount_min_floor is None or amount_min_floor < 100:
        amount_min_floor = EXPECTED_MIN_AMOUNT

    bank_id = 9
    bank_name = "Gorenjska banka d.d."
    today = datetime.today().strftime("%Y-%m-%d")

    results = []

    if debug_pdf:
        try:
            print("[DBG] GBKR PDF url", pdf_url_used)
            print("[DBG] GBKR PDF extracted", {"text_len": len(text)})
            low = text.lower()
            for needle in ["mesec", "mesecev", "nad", "dni", "%"]:
                print("[DBG] contains", needle, (needle in low))
            snip = text[:1800].replace("\r", " ")
            print("[DBG] head:", snip)
        except Exception:
            pass

    # Patterns for day/month ranges that commonly appear in PDFs.
    # Some PDFs may separate the '%' symbol into another column; tolerate missing '%'.
    day_range_re = re.compile(
        r"\b(?:od|za)\s*(\d+)\s*(?:do|\-|–)\s*(\d+)\s*dni\b[\s\S]{0,800}?(\d+[\.,]\d+)\s*%?",
        re.IGNORECASE,
    )
    day_dash_range_re = re.compile(
        r"\b(\d+)\s*(?:\-|–)\s*(\d+)\s*dni\b[\s\S]{0,800}?(\d+[\.,]\d+)\s*%?",
        re.IGNORECASE,
    )
    day_upto_re = re.compile(
        r"\bdo\s*(\d+)\s*dni\b[\s\S]{0,800}?(\d+[\.,]\d+)\s*%?",
        re.IGNORECASE,
    )
    day_single_re = re.compile(
        r"\b(\d+)\s*dni\b[\s\S]{0,800}?(\d+[\.,]\d+)\s*%?",
        re.IGNORECASE,
    )
    month_range_re = re.compile(
        r"\b(?:od|za)\s*(\d+)\s*(?:do|\-|–)\s*(\d+)\s*mesec(?:ev|e|i)?\b[\s\S]{0,800}?(\d+[\.,]\d+)\s*%?",
        re.IGNORECASE,
    )
    month_single_re = re.compile(
        r"\b(\d+)\s*mesec(?:ev|e|i)?\b[\s\S]{0,800}?(\d+[\.,]\d+)\s*%?",
        re.IGNORECASE,
    )
    over_months_re = re.compile(
        r"\bnad\s*(\d+)\s*mesec(?:ev|e|i)?\b[\s\S]{0,800}?(\d+[\.,]\d+)\s*%?",
        re.IGNORECASE,
    )
    over_years_re = re.compile(
        r"\bnad\s*(\d+)\s*(?:let|leta|leto|let\w*)\b[\s\S]{0,800}?(\d+[\.,]\d+)\s*%?",
        re.IGNORECASE,
    )

    if debug_pdf:
        try:
            hits = []
            for ln in text.splitlines():
                l = (ln or "").strip()
                if not l:
                    continue
                low_ln = l.lower()
                if ("od" in low_ln and "dni" in low_ln) or ("mesec" in low_ln) or ("mesecev" in low_ln):
                    hits.append(l)
                if len(hits) >= 12:
                    break
            if hits:
                print("[DBG] GBKR PDF lines sample:")
                for h in hits[:12]:
                    print("[DBG]   ", h)
        except Exception:
            pass

    b = " ".join(text.replace("\r", " ").replace("\n", " ").split())
    structured_days_added = False
    structured_months_added = False
    m = re.search(
        r"od\s*31\s*do\s*60\s*dni\s+od\s*61\s*do\s*90\s*dni\s+od\s*91\s*do\s*180\s*dni\s+od\s*181\s*do\s*270\s*dni\s+od\s*271\s*do\s*365\s*dni[\s\S]{0,220}?([0-9]+[\.,][0-9]+)\s+([0-9]+[\.,][0-9]+)\s+([0-9]+[\.,][0-9]+)\s+([0-9]+[\.,][0-9]+)\s+([0-9]+[\.,][0-9]+)",
        b,
        flags=re.IGNORECASE,
    )
    if m:
        structured_days_added = True
        terms = [(31, 60), (61, 90), (91, 180), (181, 270), (271, 365)]
        for i, (a, bb) in enumerate(terms):
            r_val = _to_float_rate(m.group(1 + i))
            if r_val is None:
                continue
            results.append({
                "id": bank_id,
                "bank": bank_name,
                "product_name": f"Depozit {a}–{bb} dni",
                "amount_min": amount_min_floor,
                "amount_max": EXPECTED_MAX_AMOUNT,
                "amount_currency": "EUR",
                "min_term": a,
                "max_term": bb,
                "term_unit": "days",
                "rate_branch": r_val,
                "rate_klik_bonus": 0.0,
                "rate_klik_total": r_val,
                "offer_type": "regular",
                "source": "pdf",
                "url": pdf_url_used,
                "last_updated": today,
                "notes": "scraped via PDF",
            })

    for mm in re.finditer(
        r"\bod\s+vklju\w*\s*(\d+)\s*do\s*(\d+)\s*mesec\w*\s+([0-9]+[\.,][0-9]+)",
        b,
        flags=re.IGNORECASE,
    ):
        a = int(mm.group(1))
        bb = int(mm.group(2))
        if (a, bb) not in [(13, 23), (24, 35)]:
            continue
        r_val = _to_float_rate(mm.group(3))
        if r_val is None:
            continue
        structured_months_added = True
        results.append({
            "id": bank_id,
            "bank": bank_name,
            "product_name": f"Depozit {a}–{bb}M",
            "amount_min": amount_min_floor,
            "amount_max": EXPECTED_MAX_AMOUNT,
            "amount_currency": "EUR",
            "min_term": a,
            "max_term": bb,
            "term_unit": "months",
            "rate_branch": r_val,
            "rate_klik_bonus": 0.0,
            "rate_klik_total": r_val,
            "offer_type": "regular",
            "source": "pdf",
            "url": pdf_url_used,
            "last_updated": today,
            "notes": "scraped via PDF",
        })

    if not results:
        return None

    if debug_pdf:
        try:
            n_days = sum(1 for rr in results if rr.get("term_unit") == "days")
            n_months = sum(1 for rr in results if rr.get(
                "term_unit") == "months")
            print("[DBG] GBKR PDF parsed counts", {
                  "days": n_days, "months": n_months, "total": len(results)})
        except Exception:
            pass

    if not any(r.get("term_unit") == "months" for r in results):
        return None
    if not any(r.get("term_unit") == "days" for r in results):
        return None

    dedup = {}
    for row in results:
        key = (
            row.get("term_unit"),
            row.get("min_term"),
            row.get("max_term"),
            row.get("amount_min"),
            row.get("amount_max"),
            row.get("rate_branch"),
        )
        dedup[key] = row
    return list(dedup.values())


def scrape_gbkr():
    pdf_rows = scrape_gbkr_from_pdf()
    if pdf_rows:
        print(f"[OK] GBKR: PDF vir uporabljen ({len(pdf_rows)} zapisov)")
        return pdf_rows

    print("[WARN] GBKR: PDF parse ni uspel")
    return []


def save_to_csv(rows, filename="gbkr_depoziti.csv"):
    if not rows:
        print("Ni podatkov za zapis v CSV.")
        return

    for r in rows:
        if isinstance(r, dict) and not r.get("offer_type"):
            r["offer_type"] = "regular"
        if isinstance(r, dict) and not r.get("source"):
            u = str(r.get("url") or "").lower()
            r["source"] = "pdf" if (
                ".pdf" in u or "downloadfile" in u or "fileid" in u) else "web"

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
        "offer_type",
        "source",
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
    data = scrape_gbkr()
    save_to_csv(data)
