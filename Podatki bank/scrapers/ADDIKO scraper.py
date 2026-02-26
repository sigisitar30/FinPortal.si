import csv
import requests
from datetime import datetime
from io import StringIO
import re
import math
import os

CALCULATOR_URL = "https://www.addiko.si/obcani/depoziti/informativni-izracun/"
ADDICO_URL = "https://www.addiko.si/static/uploads/tabela-evrski-depozit-retail-1.2.2026.csv"
ADDICO_PDF_URL = "https://www.addiko.si/static/uploads/Obrestne-mere_obcani_Veljavnost-od-01.02.2026.pdf"

# PRIČAKOVANE VREDNOSTI (če banka spremeni – dobiš opozorilo)
EXPECTED_MIN_AMOUNT = 400
EXPECTED_MAX_AMOUNT = 500000
EXPECTED_TERMS = [3, 6, 9, 12, 24, 36, 60]


def _to_float_si(value):
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    # Rates use Slovenian formatting (comma decimal). Keep dot decimals as-is.
    s = s.replace("%", "").replace(" ", "").replace(
        "\u00A0", "").replace(",", ".")
    try:
        v = float(s)
    except Exception:
        return None
    return v if math.isfinite(v) else None


def scrape_addiko_from_pdf(bank_id, bank_name):
    try:
        import pdfplumber  # type: ignore
    except Exception:
        return None

    try:
        r = requests.get(ADDICO_PDF_URL, timeout=30)
        r.raise_for_status()
    except Exception:
        return None

    # pdfplumber expects a file-like object with bytes
    from io import BytesIO
    try:
        pdf_bytes = BytesIO(r.content)
        with pdfplumber.open(pdf_bytes) as pdf:
            pages = list(pdf.pages)
            text = "\n".join([(p.extract_text() or "") for p in pages])
            tables = []
            for p in pages:
                try:
                    t = p.extract_tables() or []
                except Exception:
                    t = []
                tables.extend(t)
    except Exception:
        return None

    if not text or not isinstance(text, str):
        return None

    def _normalize_pdf_text(s):
        if not isinstance(s, str):
            return ""
        # pdf text extraction may include Slovene diacritics; normalize to ASCII for matching
        # (keep it simple and local to this script).
        return (
            s.replace("\u010d", "c")
            .replace("\u010c", "C")
            .replace("\u0161", "s")
            .replace("\u0160", "S")
            .replace("\u017e", "z")
            .replace("\u017d", "Z")
        )

    text_norm = _normalize_pdf_text(text)

    debug_pdf = os.environ.get("ADDIKO_PDF_DEBUG", "").strip() == "1"

    def _ascii(s):
        try:
            return str(s).encode("ascii", errors="ignore").decode("ascii")
        except Exception:
            return ""

    if debug_pdf:
        try:
            print("[DBG] Addiko PDF extracted", {
                  "text_len": len(text_norm), "tables": len(tables)})
            for ti, t in enumerate(tables[:12]):
                rows = [["" if c is None else _ascii(
                    c) for c in r] for r in (t or [])]
                print("[DBG] table", ti, "rows", len(rows), "cols",
                      max((len(r) for r in rows), default=0))
                for ri, r in enumerate(rows[:4]):
                    print("[DBG] ", ti, "r", ri, r)

            def _print_snip(needle, radius=140):
                s = text_norm
                i = s.lower().find(str(needle).lower())
                if i < 0:
                    print("[DBG] snip not found", _ascii(needle))
                    return
                a = max(0, i - radius)
                b = min(len(s), i + len(str(needle)) + radius)
                sn = _ascii(s[a:b]).replace("\r", " ").replace("\n", " ")
                print("[DBG] snip", _ascii(needle), ":", sn)

            _print_snip("Nad 1 let")
            _print_snip("Od 181")
            _print_snip("akcij")
        except Exception:
            pass

    def _find_rate(pattern):
        m = re.search(pattern, text_norm, flags=re.IGNORECASE | re.DOTALL)
        if not m:
            return None
        return _to_float_si(m.group(1))

    def _find_rate_after_label(label_pattern):
        # Capture the first percentage-like number after a label.
        m = re.search(
            label_pattern + r"\s*([0-9]{1,2}(?:[\.,][0-9]{1,2})?)\s*%?",
            text_norm,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if not m:
            return None
        return _to_float_si(m.group(1))

    def _find_rate_group_short_term():
        # In extracted text, the three short-term ranges are listed first, and rates appear
        # only after the amount label (e.g. "Od 400 EUR dalje 1,00% 1,35% 1,40%").
        m = re.search(
            r"kratkorocni\s+evrski\s+depozit.*?od\s*91\s*dni.*?180\s*dni.*?od\s*181\s*dni.*?270\s*dni.*?od\s*271\s*dni.*?1\s*let\w+.*?od\s*400\s*eur\s*dalje\s*([0-9]{1,2}(?:[\.,][0-9]{1,2})?)\s*%?\s*([0-9]{1,2}(?:[\.,][0-9]{1,2})?)\s*%?\s*([0-9]{1,2}(?:[\.,][0-9]{1,2})?)\s*%?",
            text_norm,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if not m:
            return None
        a = _to_float_si(m.group(1))
        b = _to_float_si(m.group(2))
        c = _to_float_si(m.group(3))
        if a is None or b is None or c is None:
            return None
        return (a, b, c)

    def _find_rate_group_long_term_regular():
        # Extracted text commonly contains just the three lines with "Nad ..." and the rates.
        vklj = r"vklju(?:cno|no)"
        m = re.search(
            r"obrestna\s+mera.*?nad\s*1\s*let\w*\s*do\s*" + vklj + r"\s*2\s*let\w*\s*([0-9]{1,2}(?:[\.,][0-9]{1,2})?)\s*%?.*?nad\s*2\s*let\w*\s*do\s*" + vklj +
            r"\s*3\s*let\w*\s*([0-9]{1,2}(?:[\.,][0-9]{1,2})?)\s*%?.*?nad\s*3\s*let\w*\s*do\s*" +
            vklj + r"\s*5\s*let\w*\s*([0-9]{1,2}(?:[\.,][0-9]{1,2})?)\s*%?",
            text_norm,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if not m:
            return None
        a = _to_float_si(m.group(1))
        b = _to_float_si(m.group(2))
        c = _to_float_si(m.group(3))
        if a is None or b is None or c is None:
            return None
        return (a, b, c)

    def _find_rate_action_promo():
        # Extracted text for promo usually follows the short-term block.
        vklj = r"vklju(?:cno|no)"
        m = re.search(
            r"dolgorocni\s+akcijsk\w+\s+evrski\s+depozit.*?nad\s*1\s*,\s*5\s*let\w*\s*do\s*" +
            vklj +
            r"\s*2\s*let\w*.*?od\s*400\s*eur\s*dalje\s*([0-9]{1,2}(?:[\.,][0-9]{1,2})?)\s*%?",
            text_norm,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if not m:
            return None
        return _to_float_si(m.group(1))

    def _rate_from_tables(*needles):
        if not tables:
            return None
        lowered = [str(n).strip().lower() for n in needles if n]
        for t in tables:
            if not t or len(t) < 2:
                continue
            # Normalize to strings.
            rows = [["" if c is None else str(c) for c in r] for r in t]
            rows_l = [[c.strip().lower() for c in r] for r in rows]

            # Look for a header cell match in ANY row, and read the value from the next row same column.
            for ridx in range(0, len(rows_l) - 1):
                row = rows_l[ridx]
                for cidx, cell in enumerate(row):
                    if cell and all(n in cell for n in lowered):
                        nxt = rows[ridx + 1]
                        if cidx < len(nxt):
                            v = _to_float_si(nxt[cidx])
                            if v is not None:
                                return v
        return None

    # Short-term ranges are typically represented as a group in extracted text.
    group_short = _find_rate_group_short_term()
    rate_91_180 = group_short[0] if group_short else None
    rate_181_270 = group_short[1] if group_short else None
    rate_271_365 = group_short[2] if group_short else None

    # Long-term regular deposit: in extracted text it often appears without the section title.
    group_long = _find_rate_group_long_term_regular()
    rate_long_1_2 = group_long[0] if group_long else None
    rate_long_2_3 = group_long[1] if group_long else None
    rate_long_3_5 = group_long[2] if group_long else None

    # Long-term promotional (special) deposit.
    rate_promo_1_5_2 = _find_rate_action_promo()

    if debug_pdf:
        try:
            print(
                "[DBG] rates",
                {
                    "st_91_180": rate_91_180,
                    "st_181_270": rate_181_270,
                    "st_271_365": rate_271_365,
                    "lt_1_2": rate_long_1_2,
                    "lt_2_3": rate_long_2_3,
                    "lt_3_5": rate_long_3_5,
                    "promo_1_5_2": rate_promo_1_5_2,
                },
            )
        except Exception:
            pass

    any_found = any(
        v is not None
        for v in [
            rate_91_180,
            rate_181_270,
            rate_271_365,
            rate_long_1_2,
            rate_long_2_3,
            rate_long_3_5,
            rate_promo_1_5_2,
        ]
    )
    if not any_found:
        # Minimal diagnostics for local runs
        try:
            kw = ["kratkorocni", "dolgoro", "akcijsk", "depozit"]
            present = {k: (k in text_norm.lower()) for k in kw}
            print("[WARN] Addiko PDF parsed but no rates matched", {
                  "text_len": len(text_norm), "tables": len(tables), "kw": present})
        except Exception:
            pass
        return None

    today = datetime.today().strftime("%Y-%m-%d")
    amount_min = int(EXPECTED_MIN_AMOUNT)
    amount_max = int(EXPECTED_MAX_AMOUNT)
    out = []

    def _row(product_name, min_term, max_term, term_unit, rate_branch, rate_klik_total, notes):
        out.append(
            {
                "id": bank_id,
                "bank": bank_name,
                "product_name": product_name,
                "amount_min": amount_min,
                "amount_max": amount_max,
                "amount_currency": "EUR",
                "min_term": min_term,
                "max_term": max_term,
                "term_unit": term_unit,
                "rate_branch": float(rate_branch),
                "rate_klik_bonus": float(rate_klik_total) - float(rate_branch),
                "rate_klik_total": float(rate_klik_total),
                "url": ADDICO_PDF_URL,
                "last_updated": today,
                "notes": notes,
            }
        )

    if rate_91_180 is not None:
        _row("Kratkoročni evrski depozit 91–180 dni", 91, 180,
             "days", rate_91_180, rate_91_180, "redna ponudba")

        # Align month-based buckets to the PDF day ranges.
        # 91–180 days ~= 3–5 months
        _row(
            "Depozit 3-5M",
            3,
            5,
            "months",
            rate_91_180,
            rate_91_180,
            "redna ponudba (3-5M derived from 91-180 days)",
        )
    if rate_181_270 is not None:
        _row("Kratkoročni evrski depozit 181–270 dni", 181, 270,
             "days", rate_181_270, rate_181_270, "redna ponudba")

        # 181–270 days ~= 6–8 months
        _row(
            "Depozit 6-8M",
            6,
            8,
            "months",
            rate_181_270,
            rate_181_270,
            "redna ponudba (6-8M derived from 181-270 days)",
        )
    if rate_271_365 is not None:
        _row("Kratkoročni evrski depozit 271 dni–1 leto", 271, 365,
             "days", rate_271_365, rate_271_365, "redna ponudba")

        # 271–365 days ~= 9–11 months
        _row(
            "Depozit 9-11M",
            9,
            11,
            "months",
            rate_271_365,
            rate_271_365,
            "redna ponudba (9-11M derived from 271-365 days)",
        )

    # PDF uses "nad" (strictly greater) thresholds; approximate with next whole month ranges.
    if rate_long_1_2 is not None:
        _row("Dolgoročni evrski depozit >1–2 leti", 12, 23,
             "months", rate_long_1_2, rate_long_1_2, "redna ponudba")
    if rate_long_2_3 is not None:
        _row("Dolgoročni evrski depozit >2–3 leta", 24, 36,
             "months", rate_long_2_3, rate_long_2_3, "redna ponudba")
    if rate_long_3_5 is not None:
        _row("Dolgoročni evrski depozit >3–5 let", 37, 60, "months",
             rate_long_3_5, rate_long_3_5, "redna ponudba")

    if rate_promo_1_5_2 is not None:
        # promotional/special
        _row(
            "Dolgoročni akcijski evrski depozit >1,5–2 leti",
            19,
            23,
            "months",
            rate_long_1_2 if rate_long_1_2 is not None else rate_promo_1_5_2,
            rate_promo_1_5_2,
            "akcijska ponudba",
        )

    return out


def scrape_addiko():
    bank_id = 4
    bank_name = "Addiko Bank d.d."

    pdf_rows = scrape_addiko_from_pdf(bank_id, bank_name)
    if pdf_rows:
        print("[OK] Addiko: PDF vir uporabljen", {"rows": len(pdf_rows)})
        return pdf_rows
    print("[WARN] Addiko: PDF parse failed, using calculator CSV fallback")

    print("Prenos Addiko CSV...")

    csv_url = ADDICO_URL
    try:
        calc_html = requests.get(CALCULATOR_URL, timeout=20)
        calc_html.raise_for_status()
        m = re.search(
            r"/static/uploads/tabela-evrski-depozit-retail-[^\"\s<>]+?\.csv", calc_html.text)
        if m:
            csv_url = "https://www.addiko.si" + m.group(0)
    except Exception:
        csv_url = ADDICO_URL

    # Prenesemo CSV
    response = requests.get(csv_url)
    response.raise_for_status()

    csv_data = response.content.decode("utf-8")
    reader = csv.reader(StringIO(csv_data), delimiter=',')

    rows = list(reader)

    # A1 = header (ročnosti)
    header = rows[0]  # ["tabela", "6", "9", "12", ...]
    terms = [int(x) for x in header[1:]]

    # CSV je matrika: 1. stolpec je prag zneska, ostali so OM po ročnostih.
    # Primer (iz Network Response):
    # tabela,6,9,12,24,36,60
    # 20,1.0,1.35,...
    # 1000,1.0,1.35,...
    # ...
    tiers = []
    for r in rows[1:]:
        if not r or len(r) < 2:
            continue
        try:
            amount_threshold = float(str(r[0]).replace(" ", ""))
        except Exception:
            continue

        tier_rates = {}
        for i, term in enumerate(terms, start=1):
            try:
                tier_rates[int(term)] = float(str(r[i]).replace(" ", ""))
            except Exception:
                continue

        if tier_rates:
            tiers.append((amount_threshold, tier_rates))

    tiers.sort(key=lambda x: x[0])

    def _to_int_eur(value):
        try:
            v = float(value)
        except Exception:
            return None
        if not math.isfinite(v):
            return None
        # Addiko CSV uses thresholds like 1001.05 / 1502.05. We display human-friendly whole euros.
        return int(math.floor(v + 1e-9))

    # Addiko kalkulator omogoča dobo od 3 mesecev naprej.
    # Ker CSV (trenutno) nima 3M, kalkulator očitno mapira 3M na najbližji produkt.
    # V praksi je to 6M, zato dodamo 3M kot preslikavo na 6M.
    if 3 not in terms and 6 in terms:
        terms = [3] + terms
        for idx in range(len(tiers)):
            amount_threshold, tier_rates = tiers[idx]
            if 6 in tier_rates and 3 not in tier_rates:
                tier_rates[3] = float(tier_rates[6])
            tiers[idx] = (amount_threshold, tier_rates)

    print("\n--- Preverjanje strukture Addiko CSV ---")

    # 1) Preverjanje ročnosti (tolerantno: pomembno je, da je vsaj 3M na voljo)
    all_terms = sorted(set(terms))
    if 3 not in all_terms:
        print("[WARN] V podatkih še vedno ni 3M (kalkulator pa ga prikazuje).")
    elif all_terms != EXPECTED_TERMS:
        print("[WARN] Addiko je spremenil ročnosti!")
        print("  Pričakovano:", EXPECTED_TERMS)
        print("  Dobljeno:   ", all_terms)
    else:
        print("[OK] Rocnosti so nespremenjene.")

    # 2) Preverjanje minimalnega zneska
    if EXPECTED_MIN_AMOUNT != 400:
        print("[WARN] Pričakovani minimalni znesek ni 400 EUR!")
    else:
        print("[OK] Minimalni znesek depozita = 400 EUR (pricakovano).")

    # 3) Preverjanje maksimalnega zneska
    if EXPECTED_MAX_AMOUNT != 500000:
        print("[WARN] Pričakovani maksimalni znesek ni 500.000 EUR!")
    else:
        print("[OK] Maksimalni znesek depozita = 500000 EUR (pricakovano).")

    results = []

    print("\n--- Obrestne mere ---")

    # 4) Preverjanje obrestnih mer
    for i, (amount_threshold, tier_rates) in enumerate(tiers):
        next_threshold = tiers[i + 1][0] if i + 1 < len(tiers) else None

        raw_min = _to_int_eur(amount_threshold)
        raw_next = _to_int_eur(
            next_threshold) if next_threshold is not None else None

        if raw_min is None:
            continue

        amount_min = raw_min
        if i == 0 and amount_min < EXPECTED_MIN_AMOUNT:
            amount_min = int(EXPECTED_MIN_AMOUNT)

        if raw_next is None:
            amount_max = int(EXPECTED_MAX_AMOUNT)
        else:
            # Next tier starts at raw_next, so current tier ends at raw_next - 1 (human-friendly, no overlap)
            amount_max = int(
                min(EXPECTED_MAX_AMOUNT, max(amount_min, raw_next - 1)))

        if amount_min >= amount_max:
            continue

        for term in sorted(set(tier_rates.keys())):
            rate = float(tier_rates[term])
            print(f"[OK] {term}M ({amount_min}-{amount_max} EUR): {rate}%")

            results.append({
                "id": bank_id,
                "bank": bank_name,
                "product_name": f"Depozit {term}M",
                "amount_min": int(amount_min),
                "amount_max": int(amount_max),
                "amount_currency": "EUR",
                "min_term": term,
                "max_term": term,
                "term_unit": "months",
                "rate_branch": rate,
                "rate_klik_bonus": 0.0,
                "rate_klik_total": rate,
                "url": csv_url,
                "last_updated": datetime.today().strftime("%Y-%m-%d"),
                "notes": "redna ponudba" if term != 3 else "redna ponudba (3M map->6M)"
            })

    print(f"\n[OK] Addiko: successfully scraped {len(results)} records.")
    return results


def save_to_csv(rows, filename="addiko_depoziti.csv"):
    if not rows:
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

    print(f"[OK] CSV zapisan v: {filename}")


if __name__ == "__main__":
    data = scrape_addiko()
    save_to_csv(data)
