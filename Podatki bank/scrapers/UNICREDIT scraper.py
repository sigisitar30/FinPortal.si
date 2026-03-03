from playwright.sync_api import sync_playwright
from datetime import datetime
import csv
import time
import json
import os
import re
import io

import requests

URL = "https://www.unicreditbank.si/si/prebivalstvo/nalozbe/klasicni-depozit.html"
PREVIOUS_FILE = "unicredit_previous.json"

PDF_URL = "https://www.unicreditbank.si/content/dam/cee2020-pws-si/SI-DOK/Tarife_in_obrestne_mere/Izvlecek_iz_tarife_PI/Izvle%C4%8Dek%20Sklepa%20o%20obrestnih%20merah%20banke%2001.03.2026.pdf"

EXPECTED_MIN_AMOUNT = 500
EXPECTED_MAX_AMOUNT = 100000


def _make_session():
    s = requests.Session()
    s.headers.update(
        {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Accept-Language": "sl-SI,sl;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
        }
    )
    return s


SESSION = _make_session()


def _absolute_url(base: str, href: str) -> str:
    href = str(href or "").strip()
    if not href:
        return ""
    if href.startswith("http://") or href.startswith("https://"):
        return href
    if href.startswith("//"):
        return "https:" + href
    if href.startswith("/"):
        m = re.match(r"^(https?://[^/]+)", base)
        return (m.group(1) + href) if m else href
    # relative
    if base.endswith("/"):
        return base + href
    return base.rsplit("/", 1)[0] + "/" + href


def discover_pdf_url(session: requests.Session) -> str:
    """Try to find the current UniCredit interest-rate PDF linked from the product page."""
    try:
        r = session.get(URL, timeout=30)
        r.raise_for_status()
        html = r.text or ""

        # Prefer a PDF that looks like the interest-rate decision/extract.
        candidates = []

        for m in re.finditer(r"href=\"([^\"]+\.pdf)\"", html, flags=re.IGNORECASE):
            u = _absolute_url(URL, m.group(1))
            if u:
                candidates.append(u)

        for m in re.finditer(r"(https?://[^\s'\"]+\.pdf)", html, flags=re.IGNORECASE):
            u = m.group(1)
            if u:
                candidates.append(u)

        # Keep order, de-dupe
        seen = set()
        uniq = []
        for u in candidates:
            if u not in seen:
                seen.add(u)
                uniq.append(u)

        preferred = []
        for u in uniq:
            low = u.lower()
            if "obrest" in low or "sklep" in low or "tarif" in low:
                preferred.append(u)

        return (preferred[0] if preferred else (uniq[0] if uniq else ""))
    except Exception:
        return ""


# -----------------------------
# FETCH RATE (tvoja funkcija)
# -----------------------------
def _extract_percent(text):
    matches = re.findall(r"(\d+(?:[\.,]\d+)?)\s*%", text)
    for m in matches:
        try:
            val = float(m.replace(",", "."))
            if 0 <= val <= 25:
                return val
        except:
            pass
    return None


def fetch_rate(page, amount, months):
    td_amount = "input[name='tdAmount']"
    try:
        cur_amount = page.input_value(td_amount)
    except:
        cur_amount = None
    if cur_amount is None or cur_amount.strip() != str(amount):
        page.fill(td_amount, str(amount))

    tenor_input = "#tenor_input"
    page.wait_for_selector(tenor_input)

    try:
        prev_rate_text = page.locator(
            "#depositAnnualInterestRate").first.inner_text(timeout=500)
    except:
        prev_rate_text = ""

    page.fill(tenor_input, str(months))
    page.dispatch_event(tenor_input, "input")
    page.dispatch_event(tenor_input, "change")

    try:
        page.wait_for_function(
            "(prev) => { const el = document.querySelector('#depositAnnualInterestRate'); return el && el.innerText && el.innerText.trim() !== '' && el.innerText.trim() !== (prev || '').trim(); }",
            arg=prev_rate_text,
            timeout=4000,
        )
    except:
        pass

    try:
        page.wait_for_selector("text=OSNOVNA OBRESTNA MERA", timeout=5000)
    except:
        pass

    rate_branch = None
    rate_online = None

    try:
        base_el = page.get_by_text("OSNOVNA OBRESTNA MERA", exact=False).first
        base_box = base_el.locator("xpath=ancestor::div[1]")
        base_text = base_box.inner_text()
        rate_branch = _extract_percent(base_text)
    except:
        rate_branch = None

    try:
        online_el = page.get_by_text(
            "OBRESTNA MERA ZA SKLENITEV PREK ONLINE", exact=False).first
        online_box = online_el.locator("xpath=ancestor::div[1]")
        online_text = online_box.inner_text()
        rate_online = _extract_percent(online_text)
    except:
        rate_online = None

    if rate_branch is None and rate_online is None:
        try:
            txt = page.inner_text("div.core-features")
            matches = re.findall(r"(\d+(?:[\.,]\d+)?)\s*%", txt)
            rates = []
            for m in matches:
                try:
                    rates.append(float(m.replace(",", ".")))
                except:
                    pass
            rates = [r for r in rates if 0 <= r <= 25]
            if rates:
                if len(rates) == 1:
                    return rates[0], rates[0]
                return min(rates), max(rates)
        except:
            pass

    if rate_branch is None:
        rate_branch = rate_online
    if rate_online is None:
        rate_online = rate_branch

    if rate_branch is None or rate_online is None:
        return None

    return rate_branch, rate_online


def _extract_pdf_text(pdf_bytes: bytes) -> str:
    try:
        from pypdf import PdfReader  # type: ignore
        reader = PdfReader(io.BytesIO(pdf_bytes))
        out = []
        for pg in reader.pages:
            try:
                t = pg.extract_text() or ""
            except Exception:
                t = ""
            if t:
                out.append(t)
        return "\n".join(out)
    except Exception:
        pass

    try:
        from PyPDF2 import PdfReader  # type: ignore
        reader = PdfReader(io.BytesIO(pdf_bytes))
        out = []
        for pg in reader.pages:
            try:
                t = pg.extract_text() or ""
            except Exception:
                t = ""
            if t:
                out.append(t)
        return "\n".join(out)
    except Exception:
        pass

    try:
        from pdfminer.high_level import extract_text  # type: ignore
        return extract_text(io.BytesIO(pdf_bytes)) or ""
    except Exception:
        return ""


def scrape_unicredit_from_pdf():
    print("Prenos UniCredit PDF ...")

    pdf_url = discover_pdf_url(SESSION) or PDF_URL

    # Prime cookies / WAF checks from main page first.
    try:
        SESSION.get(URL, timeout=30)
    except Exception:
        pass

    def _download_pdf_via_playwright(pdf_url_for_download: str):
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=["--disable-blink-features=AutomationControlled"],
            )
            context = browser.new_context(
                ignore_https_errors=True,
                locale="sl-SI",
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            )
            page = context.new_page()
            try:
                page.goto(URL, wait_until="domcontentloaded", timeout=60000)
            except Exception:
                pass

            # Use browser-context HTTP request (often passes WAF better than navigating to the PDF).
            pdf_headers = {
                "Accept": "application/pdf,application/octet-stream;q=0.9,*/*;q=0.8",
                "Accept-Language": "sl-SI,sl;q=0.9,en-US;q=0.8,en;q=0.7",
                "Referer": URL,
                "Upgrade-Insecure-Requests": "1",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "same-origin",
                "Sec-Fetch-User": "?1",
            }

            resp = page.request.get(
                pdf_url_for_download, headers=pdf_headers, timeout=60000)
            if resp.status == 403:
                # Retry through the context-level request API (sometimes behaves slightly differently).
                resp = context.request.get(
                    pdf_url_for_download, headers=pdf_headers, timeout=60000)
            if resp.status >= 400:
                raise RuntimeError(
                    f"Playwright PDF request failed: status={resp.status} url={resp.url}")
            pdf_data = resp.body()
            try:
                context.close()
            except Exception:
                pass
            try:
                browser.close()
            except Exception:
                pass
            return pdf_data

    r = SESSION.get(
        pdf_url,
        headers={
            "Accept": "application/pdf,application/octet-stream;q=0.9,*/*;q=0.8",
            "Accept-Language": "sl-SI,sl;q=0.9,en-US;q=0.8,en;q=0.7",
            "Referer": URL,
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-User": "?1",
        },
        timeout=30,
    )
    if r.status_code == 403:
        # Playwright request uses the currently discovered URL as well.
        pdf_bytes = _download_pdf_via_playwright(pdf_url)
    else:
        r.raise_for_status()
        pdf_bytes = r.content

    txt = _extract_pdf_text(pdf_bytes)
    if not txt or len(txt.strip()) < 200:
        raise RuntimeError("PDF text extraction failed")

    # Narrow to the relevant section if possible
    idx = txt.upper().find("A.3.2")
    if idx != -1:
        txt = txt[idx:]

    txt_norm = re.sub(r"\s+", " ", txt).strip()

    def _parse_amount_range():
        # Look for note like: "... veljajo za depozite v zneskih med 500,00 in 100.000,00 EUR"
        m = re.search(
            r"med\s*(\d[\d\s\.]*(?:[\.,]\d+)?)\s*in\s*(\d[\d\s\.]*(?:[\.,]\d+)?)\s*EUR",
            txt_norm,
            flags=re.IGNORECASE,
        )
        if not m:
            return None

        def _to_int(s: str):
            s = str(s)
            s = s.replace(" ", "")
            s = s.replace(".", "")
            s = s.replace(",", ".")
            try:
                return int(float(s))
            except Exception:
                return None

        a = _to_int(m.group(1))
        b = _to_int(m.group(2))
        if a is None or b is None or a <= 0 or b <= 0 or a > b:
            return None
        return a, b

    def _find_row_rates(label_pattern: str):
        # Try to capture the two percentage columns for a given row label.
        # PDF text extraction can insert arbitrary whitespace/words, so we match non-greedily.
        m = re.search(
            label_pattern
            + r".*?(\d+(?:[\.,]\d+)?)\s*%.*?(\d+(?:[\.,]\d+)?)\s*%",
            txt_norm,
            flags=re.IGNORECASE,
        )
        if not m:
            return None
        try:
            rb = float(m.group(1).replace(",", "."))
            ro = float(m.group(2).replace(",", "."))
            return rb, ro
        except Exception:
            return None

    def _find_rates_after(label_pattern: str, window: int = 220):
        m = re.search(label_pattern, txt_norm, flags=re.IGNORECASE)
        if not m:
            return None
        start = m.end()
        chunk = txt_norm[start:start + window]
        perc = re.findall(r"(\d+(?:[\.,]\d+)?)\s*%", chunk)
        if len(perc) < 2:
            # Sometimes PDF extraction duplicates only one column or merges columns; try a bigger window.
            chunk = txt_norm[start:start + (window * 3)]
            perc = re.findall(r"(\d+(?:[\.,]\d+)?)\s*%", chunk)
        if len(perc) < 2:
            return None
        try:
            # Prefer the last two tokens in the immediate window.
            # In some PDF extractions, the start of the chunk may still contain values from
            # preceding headers/rows; the row's own values tend to appear later.
            rb = float(perc[-2].replace(",", "."))
            ro = float(perc[-1].replace(",", "."))
            return rb, ro
        except Exception:
            return None

    def _find_row_rates_between(label_pattern: str, next_label_patterns, window: int = 320):
        m = re.search(label_pattern, txt_norm, flags=re.IGNORECASE)
        if not m:
            return None
        start = m.end()

        def _next_pos_after(pattern: str, after_pos: int):
            best = None
            for mm in re.finditer(pattern, txt_norm, flags=re.IGNORECASE):
                if mm.start() > after_pos and (best is None or mm.start() < best):
                    best = mm.start()
            return best

        end = None
        for nxt in next_label_patterns:
            pos = _next_pos_after(nxt, start)
            if pos is None:
                continue
            end = pos if end is None or pos < end else end

        chunk_full = txt_norm[start:end] if end is not None else txt_norm[start:]
        chunk = chunk_full[:window]
        perc = re.findall(r"(\d+(?:[\.,]\d+)?)\s*%", chunk)
        if len(perc) < 2:
            return None
        try:
            rb = float(perc[0].replace(",", "."))
            ro = float(perc[1].replace(",", "."))
            return rb, ro
        except Exception:
            return None

    lab_31_90 = r"Od\s*31\s*do\s*90\s*dni"
    lab_91_365 = r"Od\s*91\s*do\s*365\s*dni"
    lab_12_36 = r"Nad\s*12\s*do\s*36\s*mesecev"
    lab_36_60 = r"Nad\s*36\s*do\s*60\s*mesecev"

    def _to_float_token(s: str):
        try:
            return float(str(s).replace(",", "."))
        except Exception:
            return None

    def _try_parse_8_tokens_after(label_re: str, window: int = 1400):
        m = re.search(label_re, txt_norm, flags=re.IGNORECASE)
        if not m:
            return None
        chunk = txt_norm[m.end():m.end() + window]
        perc = re.findall(r"(\d+(?:[\.,]\d+)?)\s*%", chunk)
        if len(perc) < 8:
            return None
        vals = [_to_float_token(x) for x in perc[:8]]
        if any(v is None for v in vals):
            return None

        # Observed pattern in extracted text:
        # [base_31_90, base_91_365, base_12_36, base_36_60, online_31_90, online_91_365, online_12_36, online_36_60]
        base_31_90, base_91_365, base_12_36, base_36_60, on_31_90, on_91_365, on_12_36, on_36_60 = vals
        return {
            "31_90": (base_31_90, on_31_90),
            "91_365": (base_91_365, on_91_365),
            "12_36": (base_12_36, on_12_36),
            "36_60": (base_36_60, on_36_60),
        }

    parsed8 = _try_parse_8_tokens_after(lab_31_90)
    if parsed8:
        r_31_90 = parsed8["31_90"]
        r_91_365 = parsed8["91_365"]
        r_12_36 = parsed8["12_36"]
        r_36_60 = parsed8["36_60"]
    else:
        r_31_90 = None
        r_91_365 = None
        r_12_36 = None
        r_36_60 = None

    if not (r_31_90 and r_91_365 and r_12_36 and r_36_60):
        r_31_90 = (
            _find_row_rates_between(
                lab_31_90, [lab_91_365, lab_12_36, lab_36_60])
            or _find_row_rates(lab_31_90)
            or _find_rates_after(lab_31_90, window=800)
        )
        r_91_365 = (
            _find_row_rates_between(lab_91_365, [lab_12_36, lab_36_60])
            or _find_row_rates(lab_91_365)
            or _find_rates_after(lab_91_365, window=800)
        )
        r_12_36 = (
            _find_row_rates_between(lab_12_36, [lab_36_60])
            or _find_row_rates(lab_12_36)
            or _find_rates_after(lab_12_36, window=800)
        )
        r_36_60 = (
            _find_row_rates_between(lab_36_60, [])
            or _find_row_rates(lab_36_60)
            or _find_rates_after(lab_36_60, window=800)
        )

    def _diag(label_re: str, w: int = 700):
        m = re.search(label_re, txt_norm, flags=re.IGNORECASE)
        if not m:
            return None
        chunk = txt_norm[m.end():m.end() + w]
        perc = re.findall(r"(\d+(?:[\.,]\d+)?)\s*%", chunk)
        return {
            "label": label_re,
            "perc": perc[:16],
            "chunk": chunk[:260],
        }

    if r_31_90 and r_91_365 and r_12_36 and r_36_60:
        suspicious = False
        r31 = (round(float(r_31_90[0]), 4), round(float(r_31_90[1]), 4))
        r91 = (round(float(r_91_365[0]), 4), round(float(r_91_365[1]), 4))
        r12 = (round(float(r_12_36[0]), 4), round(float(r_12_36[1]), 4))
        r36 = (round(float(r_36_60[0]), 4), round(float(r_36_60[1]), 4))

        # 91–365D should not be identical to 31–90D (per bank table).
        if r91 == r31:
            suspicious = True
        # Long-term (37–60M) should be extremely low (often 0,01%) and definitely not close to short-term.
        try:
            if float(r_36_60[0]) >= 0.05:
                suspicious = True
        except Exception:
            pass

        if suspicious:
            print(
                "ERR UniCredit PDF: sumljiv parse OM (segmenti so verjetno pobrani iz napačne vrstice)")
            print(f"  31-90D   ={r31}")
            print(f"  91-365D  ={r91}")
            print(f"  12-36M   ={r12}")
            print(f"  36-60M   ={r36}")
            for lab in (lab_31_90, lab_91_365, lab_12_36, lab_36_60):
                d = _diag(lab)
                if d:
                    print("  diag:", d)
            raise RuntimeError("Sumljiv UniCredit PDF parse (OM segmenti)")

    if not (r_31_90 and r_91_365 and r_12_36 and r_36_60):
        print("ERR UniCredit PDF: ne najdem vseh OM segmentov")
        print(f"  31-90D found={bool(r_31_90)}")
        print(f"  91-365D found={bool(r_91_365)}")
        print(f"  12-36M found={bool(r_12_36)}")
        print(f"  36-60M found={bool(r_36_60)}")

        def _snippet(label_re: str):
            m = re.search(label_re, txt_norm, flags=re.IGNORECASE)
            if not m:
                return None
            a = max(0, m.start() - 80)
            b = min(len(txt_norm), m.end() + 180)
            return txt_norm[a:b]

        for lab in (
            r"Od\s*31\s*do\s*90\s*dni",
            r"Od\s*91\s*do\s*365\s*dni",
            r"Nad\s*12\s*do\s*36\s*mesecev",
            r"Nad\s*36\s*do\s*60\s*mesecev",
        ):
            sn = _snippet(lab)
            if sn:
                print("  snippet:", sn)
        raise RuntimeError("Ne najdem vseh obrestnih mer v PDF-ju")

    parsed_range = _parse_amount_range()
    if parsed_range:
        amount_min, amount_max = parsed_range
    else:
        amount_min, amount_max = EXPECTED_MIN_AMOUNT, EXPECTED_MAX_AMOUNT

    if amount_min != EXPECTED_MIN_AMOUNT or amount_max != EXPECTED_MAX_AMOUNT:
        print("WRN UniCredit: PDF zneskovni razpon se je spremenil")
        print(
            f"  Pričakovano: {EXPECTED_MIN_AMOUNT}–{EXPECTED_MAX_AMOUNT} EUR")
        print(f"  Dobljeno:    {amount_min}–{amount_max} EUR")
    today = datetime.today().strftime("%Y-%m-%d")

    results = []
    segments = [
        ("days", 31, 90, r_31_90, "Depozit 31–90D"),
        ("days", 91, 365, r_91_365, "Depozit 91–365D"),
        ("months", 12, 35, r_12_36, "Depozit 12–35M"),
        ("months", 36, 60, r_36_60, "Depozit 36–60M"),
    ]

    for unit, a, b, rate, name in segments:
        rb, ro = rate
        key = f"{a}-{b}-{unit}-{amount_min}-{amount_max}"
        results.append({
            "key": key,
            "id": 6,
            "bank": "UniCredit Banka Slovenija d.d.",
            "product_name": name,
            "amount_min": amount_min,
            "amount_max": amount_max,
            "amount_currency": "EUR",
            "min_term": a,
            "max_term": b,
            "term_unit": unit,
            "rate_branch": rb,
            "rate_klik_bonus": ro - rb,
            "rate_klik_total": ro,
            "offer_type": "regular",
            # Use the product page as the user-facing link (PDF URLs change often).
            "url": URL,
            "last_updated": today,
            "notes": f"scraped from UniCredit PDF: {pdf_url}",
        })

    print(f"OK UniCredit PDF: {len(results)} zapisov")
    return results


def _find_context_with_selector(page, selector, timeout_ms=60000, poll_ms=250):
    end = time.time() + (timeout_ms / 1000.0)
    last_err = None
    while time.time() < end:
        try:
            loc = page.locator(selector)
            if loc.count() > 0:
                return page
        except Exception as e:
            last_err = e

        try:
            for fr in page.frames:
                try:
                    loc = fr.locator(selector)
                    if loc.count() > 0:
                        return fr
                except Exception as e:
                    last_err = e
        except Exception as e:
            last_err = e

        time.sleep(poll_ms / 1000.0)

    if last_err:
        raise last_err
    return None


# -----------------------------
# LOAD PREVIOUS DATA
# -----------------------------
def load_previous():
    if not os.path.exists(PREVIOUS_FILE):
        return {}
    try:
        with open(PREVIOUS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}


# -----------------------------
# SAVE PREVIOUS DATA
# -----------------------------
def save_previous(data):
    with open(PREVIOUS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


# -----------------------------
# SCRAPE UNICREDIT (tvoja koda)
# -----------------------------
def scrape_unicredit():
    try:
        return scrape_unicredit_from_pdf()
    except Exception as e:
        print(f"WRN UniCredit PDF scrape failed: {type(e).__name__}: {e}")

    results = []
    test_terms = list(range(1, 13)) + [13, 18, 24, 36, 37, 60]

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"],
        )

        def _new_context(with_routing: bool):
            ctx = browser.new_context(
                ignore_https_errors=True,
                locale="sl-SI",
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            )
            if with_routing:
                ctx.route(
                    "**/*",
                    lambda route: route.abort()
                    if route.request.resource_type in ("image", "media", "font")
                    else route.continue_(),
                )
            return ctx

        context = _new_context(with_routing=True)
        page = context.new_page()

        def _goto_with_retries(pg):
            last_err = None
            for wait_until in ("domcontentloaded", "networkidle"):
                for _ in range(2):
                    try:
                        resp = pg.goto(
                            URL, wait_until=wait_until, timeout=60000)
                        if resp is not None:
                            try:
                                if resp.status >= 400:
                                    print(
                                        f"WRN UniCredit: goto status={resp.status} url={resp.url}")
                            except Exception:
                                pass
                        return True
                    except Exception as e:
                        last_err = e
                        try:
                            pg.wait_for_timeout(750)
                        except Exception:
                            pass
            if last_err is not None:
                try:
                    print(
                        f"WRN UniCredit: goto failed: {type(last_err).__name__}: {last_err}")
                except Exception:
                    pass
            return False

        ok = _goto_with_retries(page)
        if not ok:
            try:
                context.close()
            except Exception:
                pass
            # Retry without request routing (some sites rely on fonts/images to avoid JS failure).
            context = _new_context(with_routing=False)
            page = context.new_page()
            _goto_with_retries(page)

        # Cookie/consent overlay (best-effort)
        for txt in ("Sprejmi", "Strinjam", "Accept", "I agree"):
            try:
                btn = page.get_by_role("button", name=txt, exact=False).first
                if btn:
                    btn.click(timeout=1500)
                    break
            except:
                pass

        td_amount_sel = "input[name='tdAmount']"
        ctx = _find_context_with_selector(
            page, td_amount_sel, timeout_ms=30000)
        if ctx is None:
            page.goto(URL, wait_until="networkidle", timeout=60000)
            ctx = _find_context_with_selector(
                page, td_amount_sel, timeout_ms=60000)

        if ctx is None:
            try:
                print(
                    f"ERR UniCredit: ne najdem tdAmount. url={page.url} title={page.title()}")
            except:
                print("ERR UniCredit: ne najdem tdAmount (tudi po retry)")
            browser.close()
            return []

        ctx.wait_for_selector(td_amount_sel, state="attached", timeout=60000)
        min_amount = None
        max_amount = None
        try:
            a = ctx.locator(td_amount_sel).first.get_attribute("min")
            b = ctx.locator(td_amount_sel).first.get_attribute("max")
            if a is not None:
                min_amount = int(float(str(a).strip()))
            if b is not None:
                max_amount = int(float(str(b).strip()))
        except:
            min_amount = None
            max_amount = None

        if min_amount is None or min_amount <= 0:
            min_amount = 500

        test_amounts = [
            min_amount,
            1000,
            5000,
            10000,
            20000,
            50000,
            100000,
            200000,
            500000,
        ]
        if max_amount is not None and max_amount > 0:
            test_amounts = [x for x in test_amounts if x <= max_amount]
        test_amounts = sorted(
            set([x for x in test_amounts if x >= min_amount]))

        raw_rates_by_amount = {}

        for amount in test_amounts:
            ctx.fill(td_amount_sel, str(amount))
            per_term = {}
            for months in test_terms:
                rate = fetch_rate(ctx, amount, months)
                if rate is None:
                    print(f"ERR Ni podatkov za amount={amount} term={months}M")
                    continue
                rb, ro = rate
                print(
                    f"OK amount={amount} {months}M: poslovalnica {rb}%, online {ro}%")
                per_term[months] = (rb, ro)
            if per_term:
                raw_rates_by_amount[amount] = per_term

        browser.close()

    amounts_sorted = sorted(raw_rates_by_amount.keys())
    if not amounts_sorted:
        return []

    def _rate_for(amount, months):
        d = raw_rates_by_amount.get(amount) or {}
        return d.get(months)

    def _append_tiers(min_term, max_term, months_for_rate, name, notes):
        last_rate = None
        tier_start = None

        for i, amount in enumerate(amounts_sorted):
            rate = _rate_for(amount, months_for_rate)
            if rate is None:
                continue

            if last_rate is None:
                last_rate = rate
                tier_start = amount
                continue

            if rate != last_rate:
                # We only sample a discrete set of amounts, so the true threshold is somewhere
                # between amounts_sorted[i-1] and amounts_sorted[i]. We approximate it by ending
                # the previous tier at (current_amount - 1) to avoid overlap.
                amount_max = int(amount) - 1
                if amount_max is not None and tier_start is not None and amount_max >= tier_start:
                    rb, ro = last_rate
                    key = f"{min_term}-{max_term}-months-{tier_start}-{amount_max}"
                    results.append({
                        "key": key,
                        "id": 6,
                        "bank": "UniCredit Banka Slovenija d.d.",
                        "product_name": name,
                        "amount_min": tier_start,
                        "amount_max": amount_max,
                        "amount_currency": "EUR",
                        "min_term": min_term,
                        "max_term": max_term,
                        "term_unit": "months",
                        "rate_branch": rb,
                        "rate_klik_bonus": ro - rb,
                        "rate_klik_total": ro,
                        "offer_type": "regular",
                        "url": URL,
                        "last_updated": datetime.today().strftime("%Y-%m-%d"),
                        "notes": notes,
                    })

                tier_start = amount
                last_rate = rate

        if last_rate is not None and tier_start is not None:
            rb, ro = last_rate
            key = f"{min_term}-{max_term}-months-{tier_start}-max"
            results.append({
                "key": key,
                "id": 6,
                "bank": "UniCredit Banka Slovenija d.d.",
                "product_name": name,
                "amount_min": tier_start,
                "amount_max": None,
                "amount_currency": "EUR",
                "min_term": min_term,
                "max_term": max_term,
                "term_unit": "months",
                "rate_branch": rb,
                "rate_klik_bonus": ro - rb,
                "rate_klik_total": ro,
                "offer_type": "regular",
                "url": URL,
                "last_updated": datetime.today().strftime("%Y-%m-%d"),
                "notes": notes,
            })

    for m in range(1, 13):
        _append_tiers(m, m, m, f"Depozit {m}M",
                      "scraped via Playwright (amount tiers)")

    _append_tiers(13, 18, 13, "Depozit 13–18M",
                  "scraped via Playwright (amount tiers)")
    _append_tiers(24, 24, 24, "Depozit 24M",
                  "scraped via Playwright (amount tiers)")
    _append_tiers(36, 60, 60, "Depozit 36–60M",
                  "scraped via Playwright (amount tiers)")

    return results


# -----------------------------
# CHECK FOR CHANGES
# -----------------------------
def check_changes(new_data):
    previous = load_previous()

    for item in new_data:
        key = item["key"]

        if key not in previous:
            print(f"NOV PRODUKT: {item['product_name']}")
            continue

        old = previous[key]

        if old["min_term"] != item["min_term"] or old["max_term"] != item["max_term"]:
            print(f"WRN SPREMEMBA TERMINA: {item['product_name']}  "
                  f"{old['min_term']}-{old['max_term']} -> {item['min_term']}-{item['max_term']}")

        if old["rate_branch"] != item["rate_branch"]:
            print(f"WRN SPREMEMBA OBRESTNE MERE: {item['product_name']}  "
                  f"{old['rate_branch']} -> {item['rate_branch']}")

    save_previous({item["key"]: item for item in new_data})


# -----------------------------
# SAVE CSV
# -----------------------------
def save_to_csv(rows, filename="unicredit_depoziti.csv"):
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

    fieldnames = [k for k in rows[0].keys() if k != "key"]
    if "source" not in fieldnames:
        # Keep deterministic ordering: place source next to offer_type when possible.
        try:
            i = fieldnames.index("offer_type")
            fieldnames.insert(i + 1, "source")
        except Exception:
            fieldnames.append("source")

    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=";")
        writer.writeheader()
        for row in rows:
            row = {k: v for k, v in row.items() if k != "key"}
            writer.writerow(row)

    print(f"OK CSV zapisan v: {filename}")


# -----------------------------
# MAIN
# -----------------------------
if __name__ == "__main__":
    data = scrape_unicredit()
    if data:
        check_changes(data)
        save_to_csv(data)
