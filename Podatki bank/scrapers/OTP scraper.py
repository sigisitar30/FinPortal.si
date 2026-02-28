from playwright.sync_api import sync_playwright
from datetime import datetime
import csv
import re
import os
import requests
import io
import math


URL = "https://www.otpbanka.si/depozit"
URL_SHORT_RATES = "https://www.otpbanka.si/obrestne-mere-kratkorocni-depozit"
URL_LONG_SPECIAL_RATES = "https://www.otpbanka.si/obrestne-mere-dolgorocni-depoziti-s-fiksno-obrestno-mero-posebna-ponudba"
PDF_URL = "https://www.otpbanka.si/downloadfile.ashx?fileid=329074"


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


def scrape_otp_from_pdf():
    try:
        import pdfplumber  # type: ignore
    except Exception:
        return None

    try:
        r = requests.get(PDF_URL, headers={
                         "User-Agent": "Mozilla/5.0"}, timeout=45)
        r.raise_for_status()
    except Exception:
        return None

    try:
        with pdfplumber.open(io.BytesIO(r.content)) as pdf:
            text = "\n".join([(p.extract_text() or "") for p in pdf.pages])
    except Exception:
        return None

    if not text or len(text.strip()) < 100:
        return None

    debug_pdf = os.environ.get("OTP_PDF_DEBUG", "").strip() == "1"
    if debug_pdf:
        try:
            low = text.lower()
            print("[DBG] OTP PDF extracted", {"text_len": len(text)})
            for needle in ["mesec", "mesecev", "let", "leta", "leto", "dni", "%"]:
                print("[DBG] contains", needle, (needle in low))
            head = text[:2000].replace("\r", " ").replace("\n", " ")
            head = " ".join(head.split())
            print("[DBG] head:", head)
        except Exception:
            pass

    bank_id = 2
    bank_name = "OTP banka"
    today = datetime.today().strftime("%Y-%m-%d")

    min_floor = _extract_min_amount_eur(text)
    if min_floor is None or min_floor < 100:
        min_floor = 500

    results = []

    def _parse_amount_band(line):
        t = (line or "").lower().replace("\xa0", " ").strip()

        def _token_to_int(tok: str):
            s = (tok or "").strip()
            if not s:
                return None
            # Keep digits and separators only.
            s = re.sub(r"[^0-9\.,]", "", s)
            if not s:
                return None

            # If there are multiple separators (e.g. '15,000,01'), treat the last one as decimal
            # and remove the others.
            last_sep = max(s.rfind(","), s.rfind("."))
            if last_sep != -1 and len(s) - last_sep - 1 in (1, 2):
                dec = s[last_sep + 1:]
                whole = re.sub(r"[\.,]", "", s[:last_sep])
                s2 = f"{whole}.{dec}"
                try:
                    # Amount bands like '15.000,01' mean strictly above 15000 EUR;
                    # round up to the next integer EUR.
                    return int(math.ceil(float(s2)))
                except Exception:
                    pass

            # Otherwise assume integer with thousands separators.
            s2 = re.sub(r"[\.,]", "", s)
            try:
                return int(s2)
            except Exception:
                return None

        tokens = re.findall(r"\d[\d\.,]*", t)
        nums = []
        for tok in tokens:
            v = _token_to_int(tok)
            if v is None:
                continue
            nums.append(v)

        if not nums:
            return None, None

        if t.startswith("do") and len(nums) >= 1:
            return 0, nums[0]
        if t.startswith("od") and "do" in t and len(nums) >= 2:
            return nums[0], nums[1]
        if t.startswith("nad") and len(nums) >= 1:
            return nums[0], None
        return None, None

    def _structured_parse_poslovalnice(text_all):
        low = text_all.lower()
        if "poslovalnice" not in low:
            return []
        start = low.find("poslovalnice")
        end = low.find("digitalni kanali", start)
        if end == -1:
            end = len(text_all)
        block = text_all[start:end]
        b = " ".join(block.replace("\r", " ").replace("\n", " ").split())

        m = re.search(
            r"znesek\s+vezave\s+od\s+8\s+do\s+14\s+dni\s+od\s+15\s+do\s+30\s+dni\s+od\s+31\s+do\s+90\s+dni\s+od\s+91\s+do\s+180\s+dni\s+(.+?)\s+vezani\s+depoziti\s+s\s+fiksno\s+obrestno\s+mero\s*-\s+posebna\s+ponudba",
            b,
            flags=re.IGNORECASE,
        )
        if not m:
            return []
        body = m.group(1).strip()

        pat_row = re.compile(
            r"(do\s+[0-9\.,]+|od\s+[0-9\.,]+\s+do\s+[0-9\.,]+|nad\s+[0-9\.,]+)\s+(\d+[\.,]\d+)%\s+(\d+[\.,]\d+)%\s+(\d+[\.,]\d+)%\s+(\d+[\.,]\d+)%",
            re.IGNORECASE,
        )

        terms = [(8, 14), (15, 30), (31, 90), (91, 180)]
        out = []
        for mm in pat_row.finditer(body):
            band_txt = mm.group(1)
            a_min, a_max = _parse_amount_band(band_txt)
            if a_min is None:
                continue
            a_min = max(int(a_min), int(min_floor))
            if a_max is not None:
                try:
                    if int(a_max) < int(a_min):
                        a_max = None
                except Exception:
                    a_max = None
            for i, (d1, d2) in enumerate(terms):
                rate = _to_float_rate(mm.group(2 + i))
                if rate is None:
                    continue
                out.append({
                    "id": bank_id,
                    "bank": bank_name,
                    "product_name": f"Depozit {d1}-{d2} dni",
                    "amount_min": a_min,
                    "amount_max": int(a_max) if a_max is not None else None,
                    "amount_currency": "EUR",
                    "min_term": d1,
                    "max_term": d2,
                    "term_unit": "days",
                    "rate_branch": rate,
                    "rate_klik_bonus": 0.0,
                    "rate_klik_total": rate,
                    "url": PDF_URL,
                    "last_updated": today,
                    "notes": "scraped via PDF",
                })

        return out

    def _structured_parse_special_offer(text_all):
        low = text_all.lower()
        idx = low.find("posebna ponudba")
        if idx == -1:
            return []
        end = low.find("digitalni kanali", idx)
        if end == -1:
            end = len(text_all)
        block = text_all[idx:end]
        b = " ".join(block.replace("\r", " ").replace("\n", " ").split())

        out = []

        m = re.search(
            r"od\s*181\s*dni\s*do\s*12\s*mesec(?:ev|e|i)?\s*(\d+[\.,]\d+)%", b, re.IGNORECASE)
        if m:
            rate = _to_float_rate(m.group(1))
            if rate is not None:
                out.append({
                    "id": bank_id,
                    "bank": bank_name,
                    "product_name": "Depozit 181-365 dni",
                    "amount_min": int(min_floor),
                    "amount_max": None,
                    "amount_currency": "EUR",
                    "min_term": 181,
                    "max_term": 365,
                    "term_unit": "days",
                    "rate_branch": rate,
                    "rate_klik_bonus": 0.0,
                    "rate_klik_total": rate,
                    "url": PDF_URL,
                    "last_updated": today,
                    "notes": "scraped via PDF",
                })

        m = re.search(
            r"\b12\s*mesec(?:ev|e|i)?\s*(\d+[\.,]\d+)%", b, re.IGNORECASE)
        if m:
            rate = _to_float_rate(m.group(1))
            if rate is not None:
                out.append({
                    "id": bank_id,
                    "bank": bank_name,
                    "product_name": "Depozit 12M",
                    "amount_min": int(min_floor),
                    "amount_max": None,
                    "amount_currency": "EUR",
                    "min_term": 12,
                    "max_term": 12,
                    "term_unit": "months",
                    "rate_branch": rate,
                    "rate_klik_bonus": 0.0,
                    "rate_klik_total": rate,
                    "url": PDF_URL,
                    "last_updated": today,
                    "notes": "scraped via PDF",
                })

        m = re.search(
            r"nad\s*12\s*mesec(?:ev|e|i)?\s*(\d+[\.,]\d+)%\s*do\s*18\s*mesec(?:ev|e|i)?", b, re.IGNORECASE)
        if m:
            rate = _to_float_rate(m.group(1))
            if rate is not None:
                out.append({
                    "id": bank_id,
                    "bank": bank_name,
                    "product_name": "Depozit 12-18M",
                    "amount_min": int(min_floor),
                    "amount_max": None,
                    "amount_currency": "EUR",
                    "min_term": 12,
                    "max_term": 18,
                    "term_unit": "months",
                    "rate_branch": rate,
                    "rate_klik_bonus": 0.0,
                    "rate_klik_total": rate,
                    "url": PDF_URL,
                    "last_updated": today,
                    "notes": "scraped via PDF",
                })

        m = re.search(
            r"nad\s*18\s*mesec(?:ev|e|i)?\s*do\s*3\s*let\w*\s*(\d+[\.,]\d+)%", b, re.IGNORECASE)
        if m:
            rate = _to_float_rate(m.group(1))
            if rate is not None:
                out.append({
                    "id": bank_id,
                    "bank": bank_name,
                    "product_name": "Depozit 18-36M",
                    "amount_min": int(min_floor),
                    "amount_max": None,
                    "amount_currency": "EUR",
                    "min_term": 18,
                    "max_term": 36,
                    "term_unit": "months",
                    "rate_branch": rate,
                    "rate_klik_bonus": 0.0,
                    "rate_klik_total": rate,
                    "url": PDF_URL,
                    "last_updated": today,
                    "notes": "scraped via PDF",
                })

        m = re.search(
            r"nad\s*3\s*let\w*\s*do\s*5\s*let\w*\s*(\d+[\.,]\d+)%", b, re.IGNORECASE)
        if m:
            rate = _to_float_rate(m.group(1))
            if rate is not None:
                out.append({
                    "id": bank_id,
                    "bank": bank_name,
                    "product_name": "Depozit 36-60M",
                    "amount_min": int(min_floor),
                    "amount_max": None,
                    "amount_currency": "EUR",
                    "min_term": 36,
                    "max_term": 60,
                    "term_unit": "months",
                    "rate_branch": rate,
                    "rate_klik_bonus": 0.0,
                    "rate_klik_total": rate,
                    "url": PDF_URL,
                    "last_updated": today,
                    "notes": "scraped via PDF",
                })

        m = re.search(
            r"nad\s*5\s*let\w*\s*do\s*10\s*let\w*\s*(\d+[\.,]\d+)%", b, re.IGNORECASE)
        if m:
            rate = _to_float_rate(m.group(1))
            if rate is not None:
                out.append({
                    "id": bank_id,
                    "bank": bank_name,
                    "product_name": "Depozit 60-120M",
                    "amount_min": int(min_floor),
                    "amount_max": None,
                    "amount_currency": "EUR",
                    "min_term": 60,
                    "max_term": 120,
                    "term_unit": "months",
                    "rate_branch": rate,
                    "rate_klik_bonus": 0.0,
                    "rate_klik_total": rate,
                    "url": PDF_URL,
                    "last_updated": today,
                    "notes": "scraped via PDF",
                })

        return out

    structured = []
    structured.extend(_structured_parse_poslovalnice(text))
    structured.extend(_structured_parse_special_offer(text))
    if len(structured) >= 12:
        dedup = {}
        for row in structured:
            k = (
                row.get("term_unit"),
                row.get("min_term"),
                row.get("max_term"),
                row.get("amount_min"),
                row.get("amount_max"),
                row.get("rate_branch"),
            )
            dedup[k] = row
        return list(dedup.values())

    # Tolerant patterns for day/month ranges.
    # Examples we try to match (varies per PDF):
    # - "od 31 do 90 dni 0,50 %"
    # - "od 6 do 12 mesecev 1,20 %"
    day_range_re = re.compile(
        r"\bod\s*(\d+)\s*(?:do|\-|–)\s*(\d+)\s*dni\b[\s\S]{0,80}?(\d+[\.,]\d+)\s*%",
        re.IGNORECASE,
    )
    day_upto_re = re.compile(
        r"\bdo\s*(\d+)\s*dni\b[\s\S]{0,80}?(\d+[\.,]\d+)\s*%",
        re.IGNORECASE,
    )
    day_single_re = re.compile(
        r"\b(\d+)\s*dni\b[\s\S]{0,80}?(\d+[\.,]\d+)\s*%",
        re.IGNORECASE,
    )
    month_range_re = re.compile(
        r"\bod\s*(\d+)\s*(?:do|\-|–)\s*(\d+)\s*mesec(?:ev|e|i)?\b[\s\S]{0,80}?(\d+[\.,]\d+)\s*%",
        re.IGNORECASE,
    )
    month_single_re = re.compile(
        r"\b(\d+)\s*mesec(?:ev|e|i)?\b[\s\S]{0,80}?(\d+[\.,]\d+)\s*%",
        re.IGNORECASE,
    )
    year_range_re = re.compile(
        r"\bod\s*(\d+)\s*(?:do|\-|–)\s*(\d+)\s*(?:let|leta|leto)\b[\s\S]{0,80}?(\d+[\.,]\d+)\s*%",
        re.IGNORECASE,
    )
    year_upto_re = re.compile(
        r"\bdo\s*(\d+)\s*(?:let|leta|leto)\b[\s\S]{0,80}?(\d+[\.,]\d+)\s*%",
        re.IGNORECASE,
    )

    year_single_re = re.compile(
        r"\b(\d+)\s*(?:let|leta|leto)\b[\s\S]{0,80}?(\d+[\.,]\d+)\s*%",
        re.IGNORECASE,
    )

    for m in day_range_re.finditer(text):
        a = int(m.group(1))
        b = int(m.group(2))
        rate = _to_float_rate(m.group(3))
        if rate is None:
            continue
        results.append({
            "id": bank_id,
            "bank": bank_name,
            "product_name": f"Depozit {a}-{b} dni",
            "amount_min": int(min_floor),
            "amount_max": None,
            "amount_currency": "EUR",
            "min_term": a,
            "max_term": b,
            "term_unit": "days",
            "rate_branch": rate,
            "rate_klik_bonus": 0.0,
            "rate_klik_total": rate,
            "url": PDF_URL,
            "last_updated": today,
            "notes": "scraped via PDF",
        })

    # Single-year mentions (e.g. '1 leto ... %')
    for m in year_single_re.finditer(text):
        y = int(m.group(1))
        rate = _to_float_rate(m.group(2))
        if rate is None:
            continue
        if y < 1 or y > 50:
            continue
        mo = y * 12
        results.append({
            "id": bank_id,
            "bank": bank_name,
            "product_name": f"Depozit {mo}M",
            "amount_min": int(min_floor),
            "amount_max": None,
            "amount_currency": "EUR",
            "min_term": mo,
            "max_term": mo,
            "term_unit": "months",
            "rate_branch": rate,
            "rate_klik_bonus": 0.0,
            "rate_klik_total": rate,
            "url": PDF_URL,
            "last_updated": today,
            "notes": "scraped via PDF",
        })

    # Single-day mentions (rare): keep them only if they look like an actual offer line.
    for m in day_single_re.finditer(text):
        d = int(m.group(1))
        rate = _to_float_rate(m.group(2))
        if rate is None:
            continue
        if d < 1 or d > 3650:
            continue
        results.append({
            "id": bank_id,
            "bank": bank_name,
            "product_name": f"Depozit {d} dni",
            "amount_min": int(min_floor),
            "amount_max": None,
            "amount_currency": "EUR",
            "min_term": d,
            "max_term": d,
            "term_unit": "days",
            "rate_branch": rate,
            "rate_klik_bonus": 0.0,
            "rate_klik_total": rate,
            "url": PDF_URL,
            "last_updated": today,
            "notes": "scraped via PDF",
        })

    for m in day_upto_re.finditer(text):
        b = int(m.group(1))
        rate = _to_float_rate(m.group(2))
        if rate is None:
            continue
        results.append({
            "id": bank_id,
            "bank": bank_name,
            "product_name": f"Depozit do {b} dni",
            "amount_min": int(min_floor),
            "amount_max": None,
            "amount_currency": "EUR",
            "min_term": 1,
            "max_term": b,
            "term_unit": "days",
            "rate_branch": rate,
            "rate_klik_bonus": 0.0,
            "rate_klik_total": rate,
            "url": PDF_URL,
            "last_updated": today,
            "notes": "scraped via PDF",
        })

    for m in month_range_re.finditer(text):
        a = int(m.group(1))
        b = int(m.group(2))
        rate = _to_float_rate(m.group(3))
        if rate is None:
            continue
        results.append({
            "id": bank_id,
            "bank": bank_name,
            "product_name": f"Depozit {a}M",
            "amount_min": int(min_floor),
            "amount_max": None,
            "amount_currency": "EUR",
            "min_term": a,
            "max_term": b,
            "term_unit": "months",
            "rate_branch": rate,
            "rate_klik_bonus": 0.0,
            "rate_klik_total": rate,
            "url": PDF_URL,
            "last_updated": today,
            "notes": "scraped via PDF",
        })

    for m in year_range_re.finditer(text):
        a = int(m.group(1)) * 12
        b = int(m.group(2)) * 12
        rate = _to_float_rate(m.group(3))
        if rate is None:
            continue
        results.append({
            "id": bank_id,
            "bank": bank_name,
            "product_name": f"Depozit {a}M",
            "amount_min": int(min_floor),
            "amount_max": None,
            "amount_currency": "EUR",
            "min_term": a,
            "max_term": b,
            "term_unit": "months",
            "rate_branch": rate,
            "rate_klik_bonus": 0.0,
            "rate_klik_total": rate,
            "url": PDF_URL,
            "last_updated": today,
            "notes": "scraped via PDF",
        })

    for m in year_upto_re.finditer(text):
        b = int(m.group(1)) * 12
        rate = _to_float_rate(m.group(2))
        if rate is None:
            continue
        results.append({
            "id": bank_id,
            "bank": bank_name,
            "product_name": f"Depozit do {b}M",
            "amount_min": int(min_floor),
            "amount_max": None,
            "amount_currency": "EUR",
            "min_term": 12,
            "max_term": b,
            "term_unit": "months",
            "rate_branch": rate,
            "rate_klik_bonus": 0.0,
            "rate_klik_total": rate,
            "url": PDF_URL,
            "last_updated": today,
            "notes": "scraped via PDF",
        })

    if not any(r.get("term_unit") == "months" for r in results):
        seen = set()
        for m in month_single_re.finditer(text):
            mo = int(m.group(1))
            if mo < 1 or mo > 360:
                continue
            if mo in seen:
                continue
            rate = _to_float_rate(m.group(2))
            if rate is None:
                continue
            seen.add(mo)
            results.append({
                "id": bank_id,
                "bank": bank_name,
                "product_name": f"Depozit {mo}M",
                "amount_min": int(min_floor),
                "amount_max": None,
                "amount_currency": "EUR",
                "min_term": mo,
                "max_term": mo,
                "term_unit": "months",
                "rate_branch": rate,
                "rate_klik_bonus": 0.0,
                "rate_klik_total": rate,
                "url": PDF_URL,
                "last_updated": today,
                "notes": "scraped via PDF",
            })

    # Try table extraction as an additional source (some PDFs are primarily tables).
    try:
        with pdfplumber.open(io.BytesIO(r.content)) as pdf:
            for page in pdf.pages:
                for tbl in (page.extract_tables() or []):
                    for row in (tbl or []):
                        if not row or len(row) < 2:
                            continue
                        row_txt = " ".join([(c or "") for c in row])
                        if not row_txt or "%" not in row_txt:
                            continue
                        # Look for patterns inside the row text.
                        for rx, unit in [
                            (re.compile(
                                r"(\d+)\s*(?:do|\-|–)\s*(\d+)\s*dni.*?(\d+[\.,]\d+)\s*%", re.IGNORECASE), "days"),
                            (re.compile(
                                r"(\d+)\s*(?:do|\-|–)\s*(\d+)\s*mesec(?:ev|e|i)?.*?(\d+[\.,]\d+)\s*%", re.IGNORECASE), "months"),
                            (re.compile(
                                r"(\d+)\s*(?:do|\-|–)\s*(\d+)\s*(?:let|leta|leto).*?(\d+[\.,]\d+)\s*%", re.IGNORECASE), "years"),
                        ]:
                            mm = rx.search(row_txt)
                            if not mm:
                                continue
                            a = int(mm.group(1))
                            b = int(mm.group(2))
                            rate = _to_float_rate(mm.group(3))
                            if rate is None:
                                continue
                            if unit == "years":
                                a *= 12
                                b *= 12
                                unit2 = "months"
                            else:
                                unit2 = unit
                            results.append({
                                "id": bank_id,
                                "bank": bank_name,
                                "product_name": f"Depozit {a}M" if unit2 == "months" else f"Depozit {a}-{b} dni",
                                "amount_min": int(min_floor),
                                "amount_max": None,
                                "amount_currency": "EUR",
                                "min_term": a,
                                "max_term": b,
                                "term_unit": unit2,
                                "rate_branch": rate,
                                "rate_klik_bonus": 0.0,
                                "rate_klik_total": rate,
                                "url": PDF_URL,
                                "last_updated": today,
                                "notes": "scraped via PDF",
                            })
    except Exception:
        pass

    if not results:
        return None

    # Deduplicate
    dedup = {}
    for row in results:
        k = (
            row.get("term_unit"),
            row.get("min_term"),
            row.get("max_term"),
            row.get("amount_min"),
            row.get("amount_max"),
            row.get("rate_branch"),
        )
        dedup[k] = row
    return list(dedup.values())


def _extract_min_floor_from_text(text):
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


# -----------------------------
# PARSE INTERVAL
# -----------------------------
def parse_interval(text):
    text = text.lower()
    nums = re.findall(r"\d+", text)

    if len(nums) == 1:
        return int(nums[0]), int(nums[0]), ("months" if "mesec" in text else "days")

    if len(nums) >= 2:
        a, b = map(int, nums[:2])
        return a, b, ("months" if "mesec" in text else "days")

    print(f"ERR Neveljaven interval: {text}")
    return None, None, None


# -----------------------------
# PARSE AMOUNT
# -----------------------------
def parse_amount(text):
    clean = (
        text.lower()
        .replace("\xa0", " ")
        .replace(".", "")
        .replace(",", "")
        .strip()
    )
    nums = [int(n) for n in re.findall(r"\d+", clean)]

    if not nums:
        return 0, None

    if "nad" in clean:
        if len(nums) >= 2 and ("do" in clean or "-" in clean or "–" in clean):
            return nums[0], nums[1]
        return nums[0], None

    if "od" in clean and "do" in clean and len(nums) >= 2:
        return nums[0], nums[1]

    if "do" in clean and len(nums) == 1:
        return 0, nums[0]

    if len(nums) >= 2 and ("-" in clean or "–" in clean):
        return nums[0], nums[1]

    if len(nums) == 1:
        if "min" in clean or "najmanj" in clean or "vsaj" in clean or "od" in clean:
            return nums[0], None
        return nums[0], nums[0]

    return 0, None


# -----------------------------
# SCRAPE OTP
# -----------------------------
def scrape_otp():
    results = []

    pdf_rows = scrape_otp_from_pdf()
    # OTP PDF parsing is best-effort.
    # Only use the non-PDF Playwright fallback if the PDF is missing or very incomplete.
    MIN_PDF_ROWS = 7
    if pdf_rows and len(pdf_rows) >= MIN_PDF_ROWS:
        print(f"[OK] OTP: PDF vir uporabljen ({len(pdf_rows)} zapisov)")
        return pdf_rows
    if not pdf_rows:
        print("[WARN] OTP: PDF parse ni uspel → fallback na Playwright (ne-PDF)")
    else:
        print(
            f"[WARN] OTP: PDF vir je vrnil premalo zapisov ({len(pdf_rows)} < {MIN_PDF_ROWS}) → poskusim Playwright fallback"
        )

    def _prepare_rates_page(page):
        # Some OTP pages lazy-load the actual deposit tables below the fold and behind a tab.
        try:
            tab = page.locator("text=FIZIČNE OSEBE")
            if tab.count() > 0:
                tab.first.click(timeout=4000, force=True)
                page.wait_for_timeout(300)
        except:
            pass

        # Scroll to trigger lazy-loading.
        try:
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(400)
            page.evaluate("window.scrollTo(0, 0)")
            page.wait_for_timeout(200)
        except:
            pass

    def _parse_rate_cells(cells):
        vals = []
        for c in cells:
            try:
                t = c.inner_text().strip()
            except:
                continue
            if not t:
                continue
            m = re.search(r"(\d+(?:[\.,]\d+)?)\s*%?", t)
            if not m:
                continue
            try:
                vals.append(float(m.group(1).replace(",", ".")))
            except:
                pass
        if not vals:
            return None
        if len(vals) == 1:
            return vals[0], 0.0, vals[0]
        # assume first = branch, second = online/klik
        rb, rt = vals[0], vals[1]
        return rb, max(0.0, rt - rb), rt

    def _scrape_visible_tables(page, min_floor, debug_label=""):
        out = []
        html_debug = os.environ.get("OTP_HTML_DEBUG", "").strip() == "1"
        try:
            # Wait for the *deposit* rate table, not the navigation/table-of-tabs.
            page.wait_for_selector(
                "table:has-text('Obdobje'):has-text('Znesek')",
                state="attached",
                timeout=15000,
            )
        except:
            # OTP sometimes renders tables without these exact header tokens;
            # do not abort, just attempt to scan all tables.
            pass

        tables = page.query_selector_all("table")
        if debug_label or html_debug:
            print(f"INFO OTP[{debug_label}]: najdenih <table>: {len(tables)}")

        if html_debug and len(tables) > 0:
            try:
                for i, t in enumerate(tables[:3]):
                    sample = (t.text_content() or "").strip().replace(
                        "\n", " ")
                    print(
                        f"INFO OTP[{debug_label}]: table[{i}] sample={sample[:240]}")
            except:
                pass
        for table in tables:
            # Filter only deposit offer tables. OTP page can contain unrelated tables (e.g. cookie/technical).
            try:
                # Some OTP tables don't have the header in the very first <tr>.
                # Using table text is more robust across layouts.
                header_txt = (table.text_content() or "").strip().lower()
            except:
                header_txt = ""

            # Heuristic: accept if it looks like a deposit-offer table.
            # OTP changes wording; tolerate both "obdobje" and "ročnost".
            looks_like_deposit = (
                ("znes" in header_txt or "eur" in header_txt)
                and (
                    "obdob" in header_txt
                    or "roč" in header_txt
                    or "dovoljeno" in header_txt
                )
                and (
                    "obrest" in header_txt
                    or "%" in header_txt
                    or "fiks" in header_txt
                )
            )

            if not looks_like_deposit:
                continue

            if debug_label:
                try:
                    row_count = len(table.query_selector_all("tr"))
                except:
                    row_count = -1
                snippet = " ".join(header_txt.split())
                print(
                    f"INFO OTP[{debug_label}]: deposit table match rows={row_count} txt={snippet[:140]}")

            try:
                rows = table.query_selector_all("tr")
            except:
                continue
            if len(rows) < 2:
                continue

            for row in rows[1:]:
                cells = row.query_selector_all("td")
                if len(cells) < 3:
                    continue

                interval = cells[0].inner_text().strip()
                amount = cells[1].inner_text().strip()

                # Skip non-data rows.
                if not interval or not any(ch.isdigit() for ch in interval):
                    continue

                # rates can be 1 or 2 columns (or more) depending on the table
                parsed_rates = _parse_rate_cells(cells[2:])
                if parsed_rates is None:
                    continue
                rate_branch, rate_klik_bonus, rate_klik_total = parsed_rates

                min_term, max_term, unit = parse_interval(interval)
                if min_term is None:
                    continue

                amount_min, amount_max = parse_amount(amount)
                if amount_min is None:
                    amount_min = 0

                amount_min = max(int(amount_min), int(min_floor))
                if amount_max is not None and amount_min > amount_max:
                    amount_max = None

                if unit == "months":
                    product_name = f"Depozit {min_term}M"
                else:
                    product_name = f"Depozit {min_term}-{max_term} dni"

                out.append({
                    "id": 2,
                    "bank": "OTP banka",
                    "product_name": product_name,
                    "amount_min": amount_min,
                    "amount_max": amount_max,
                    "amount_currency": "EUR",
                    "min_term": min_term,
                    "max_term": max_term,
                    "term_unit": unit,
                    "rate_branch": rate_branch,
                    "rate_klik_bonus": rate_klik_bonus,
                    "rate_klik_total": rate_klik_total,
                    "url": URL,
                    "last_updated": datetime.today().strftime("%Y-%m-%d"),
                    "notes": "scraped via Playwright",
                })

        if debug_label and len(out) == 0 and len(tables) > 0:
            try:
                sample = (tables[0].inner_text()
                          or "").strip().replace("\n", " ")
                print(
                    f"INFO OTP[{debug_label}]: sample table text: {sample[:220]}")
            except:
                pass
        return out

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        context = browser.new_context(
            permissions=[],
            locale="sl-SI",
            ignore_https_errors=True,
        )

        page = context.new_page()
        page.goto(URL, wait_until="domcontentloaded")

        # COOKIE POPUP
        try:
            page.click("#cookiesettingconfirmall", timeout=3000)
            print("OK Cookie popup zaprt")
        except:
            print("WRN Cookie popup ni bil najden")

        min_floor = 500
        try:
            body_txt = page.inner_text("body")
            detected_floor = _extract_min_floor_from_text(body_txt)
            if detected_floor is not None:
                min_floor = detected_floor
        except:
            pass

        # Prefer dedicated interest-rate pages (stable HTML tables) over the /depozit accordion.
        try:
            page.goto(URL_LONG_SPECIAL_RATES, wait_until="domcontentloaded")
            page.wait_for_timeout(800)
            print("OK OTP odprta stran: dolgoročni depoziti (posebna ponudba)")
            _prepare_rates_page(page)
            try:
                tab = page.locator("text=EUR - Fiksna obrestna mera")
                if tab.count() > 0:
                    tab.first.click(timeout=4000, force=True)
                    page.wait_for_timeout(500)
            except:
                pass
            before = len(results)
            results.extend(_scrape_visible_tables(
                page, min_floor, debug_label="long"))
            print(f"INFO OTP[long]: dodanih vrstic={len(results) - before}")
        except Exception as e:
            print(
                f"WRN OTP: ni uspelo prebrati dolgoročnih obrestnih mer ({URL_LONG_SPECIAL_RATES}): {e}")

        try:
            page.goto(URL_SHORT_RATES, wait_until="domcontentloaded")
            page.wait_for_timeout(800)
            print("OK OTP odprta stran: kratkoročni depozit")
            _prepare_rates_page(page)
            try:
                tab = page.locator("text=EUR - Fiksna obrestna mera")
                if tab.count() > 0:
                    tab.first.click(timeout=4000, force=True)
                    page.wait_for_timeout(500)
            except:
                pass
            before = len(results)
            results.extend(_scrape_visible_tables(
                page, min_floor, debug_label="short"))
            print(f"INFO OTP[short]: dodanih vrstic={len(results) - before}")
        except Exception as e:
            print(
                f"WRN OTP: ni uspelo prebrati kratkoročnih obrestnih mer ({URL_SHORT_RATES}): {e}")

        # 3) Deduplicate (same interval + amount + unit)
        dedup = {}
        for r in results:
            k = (
                r.get("term_unit"),
                r.get("min_term"),
                r.get("max_term"),
                r.get("amount_min"),
                r.get("amount_max"),
                r.get("rate_branch"),
                r.get("rate_klik_total"),
            )
            dedup[k] = r
        results = list(dedup.values())

        browser.close()

    if len(results) == 0 and pdf_rows:
        print(
            f"[WARN] OTP: Playwright fallback ni vrnil zapisov (0) → vračam PDF rezultate ({len(pdf_rows)})"
        )
        return pdf_rows

    print(f"OK Skupaj scrapano {len(results)} zapisov")
    return results


# -----------------------------
# SAVE CSV
# -----------------------------
def save_to_csv(rows, filename="otp_depoziti.csv"):
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    filename = os.path.join(base_dir, filename)
    if os.path.exists(filename):
        try:
            os.remove(filename)
        except:
            print("ERR CSV je odprt v Excelu — zapri ga!")
            return

    fieldnames = [
        "id", "bank", "product_name",
        "amount_min", "amount_max", "amount_currency",
        "min_term", "max_term", "term_unit",
        "rate_branch", "rate_klik_bonus", "rate_klik_total",
        "url", "last_updated", "notes"
    ]

    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=";")
        writer.writeheader()
        writer.writerows(rows)

    print(f"OK CSV zapisan v: {filename}")


# -----------------------------
# MAIN
# -----------------------------
if __name__ == "__main__":
    data = scrape_otp()
    save_to_csv(data)
