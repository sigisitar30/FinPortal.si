from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import csv
from datetime import datetime
import time
import os
import re
import requests

URL = "https://www.gbkr.si/klasicni-depozit/"
PDF_URL = "https://www.gbkr.si/wp-content/uploads/2021/05/OM_PO_depoziti.pdf"

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

    try:
        r = requests.get(PDF_URL, headers={
                         "User-Agent": "Mozilla/5.0"}, timeout=30)
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

    amount_min_floor = _extract_min_amount_eur(text)
    if amount_min_floor is None or amount_min_floor < 100:
        amount_min_floor = EXPECTED_MIN_AMOUNT

    bank_id = 9
    bank_name = "Gorenjska banka d.d."
    today = datetime.today().strftime("%Y-%m-%d")

    results = []

    # Patterns for day/month ranges that commonly appear in PDFs.
    day_range_re = re.compile(
        r"\b(?:od|za)\s*(\d+)\s*(?:do|\-|–)\s*(\d+)\s*dni\b[^0-9%]{0,40}(\d+[\.,]\d+)\s*%",
        re.IGNORECASE,
    )
    month_range_re = re.compile(
        r"\b(?:od|za)\s*(\d+)\s*(?:do|\-|–)\s*(\d+)\s*mesecev\b[^0-9%]{0,40}(\d+[\.,]\d+)\s*%",
        re.IGNORECASE,
    )
    month_single_re = re.compile(
        r"\b(\d+)\s*mesecev\b[^0-9%]{0,40}(\d+[\.,]\d+)\s*%",
        re.IGNORECASE,
    )
    over_years_re = re.compile(
        r"\bnad\s*(\d+)\s*let[aio]?\b[^0-9%]{0,40}(\d+[\.,]\d+)\s*%",
        re.IGNORECASE,
    )

    for m in day_range_re.finditer(text):
        a = int(m.group(1))
        b = int(m.group(2))
        r_val = _to_float_rate(m.group(3))
        if r_val is None:
            continue
        results.append({
            "id": bank_id,
            "bank": bank_name,
            "product_name": f"Depozit {a}–{b} dni",
            "amount_min": amount_min_floor,
            "amount_max": EXPECTED_MAX_AMOUNT,
            "amount_currency": "EUR",
            "min_term": a,
            "max_term": b,
            "term_unit": "days",
            "rate_branch": r_val,
            "rate_klik_bonus": 0.0,
            "rate_klik_total": r_val,
            "url": PDF_URL,
            "last_updated": today,
            "notes": "scraped via PDF",
        })

    for m in month_range_re.finditer(text):
        a = int(m.group(1))
        b = int(m.group(2))
        r_val = _to_float_rate(m.group(3))
        if r_val is None:
            continue
        results.append({
            "id": bank_id,
            "bank": bank_name,
            "product_name": f"Depozit {a}–{b}M",
            "amount_min": amount_min_floor,
            "amount_max": EXPECTED_MAX_AMOUNT,
            "amount_currency": "EUR",
            "min_term": a,
            "max_term": b,
            "term_unit": "months",
            "rate_branch": r_val,
            "rate_klik_bonus": 0.0,
            "rate_klik_total": r_val,
            "url": PDF_URL,
            "last_updated": today,
            "notes": "scraped via PDF",
        })

    # 'X mesecev' rows (fallback). Use only if we have no explicit ranges.
    if not any(r.get("term_unit") == "months" for r in results):
        seen = set()
        for m in month_single_re.finditer(text):
            mo = int(m.group(1))
            if mo < 1 or mo > 360:
                continue
            if mo in seen:
                continue
            r_val = _to_float_rate(m.group(2))
            if r_val is None:
                continue
            seen.add(mo)
            results.append({
                "id": bank_id,
                "bank": bank_name,
                "product_name": f"Depozit {mo}M",
                "amount_min": amount_min_floor,
                "amount_max": EXPECTED_MAX_AMOUNT,
                "amount_currency": "EUR",
                "min_term": mo,
                "max_term": mo,
                "term_unit": "months",
                "rate_branch": r_val,
                "rate_klik_bonus": 0.0,
                "rate_klik_total": r_val,
                "url": PDF_URL,
                "last_updated": today,
                "notes": "scraped via PDF",
            })

    # 'nad X let' thresholds: convert to month intervals (X*12 .. next-1)
    thresholds = []
    for m in over_years_re.finditer(text):
        y = int(m.group(1))
        r_val = _to_float_rate(m.group(2))
        if r_val is None:
            continue
        thresholds.append((y * 12, r_val))

    if thresholds:
        thresholds = sorted({a: r for a, r in thresholds}.items())
        thr_list = [(int(a), float(r)) for a, r in thresholds]
        for i, (a, r_val) in enumerate(thr_list):
            b = (thr_list[i + 1][0] - 1) if i + 1 < len(thr_list) else None
            results.append({
                "id": bank_id,
                "bank": bank_name,
                "product_name": f"Depozit {a}M" if b is None else f"Depozit {a}–{b}M",
                "amount_min": amount_min_floor,
                "amount_max": EXPECTED_MAX_AMOUNT,
                "amount_currency": "EUR",
                "min_term": a,
                "max_term": b,
                "term_unit": "months",
                "rate_branch": r_val,
                "rate_klik_bonus": 0.0,
                "rate_klik_total": r_val,
                "url": PDF_URL,
                "last_updated": today,
                "notes": "scraped via PDF",
            })

    # If we parsed nothing, signal failure.
    if not results:
        return None

    # Deduplicate
    dedup = {}
    for row in results:
        key = (row.get("term_unit"), row.get("min_term"), row.get("max_term"), row.get(
            "amount_min"), row.get("amount_max"), row.get("rate_branch"))
        dedup[key] = row
    return list(dedup.values())


def click_tab_by_text(driver, wait, text):
    try:
        # Najprej ciljamo element s tekstom (lahko je tudi span), potem kliknemo najbližji klikabilen ancestor.
        el = wait.until(
            EC.presence_of_element_located(
                (By.XPATH, f"//*[contains(translate(normalize-space(.), 'abcdefghijklmnopqrstuvwxyzčšž', 'ABCDEFGHIJKLMNOPQRSTUVWXYZČŠŽ'), '{text.upper()}')]"))
        )
        clickable = el
        try:
            clickable = el.find_element(
                By.XPATH,
                "ancestor-or-self::*[self::button or self::a or @role='button' or contains(@class,'button')][1]",
            )
        except:
            clickable = el

        driver.execute_script(
            "arguments[0].scrollIntoView({block: 'center', inline: 'center'});", clickable)
        driver.execute_script("arguments[0].click();", clickable)
        return True
    except:
        return False


def ensure_days_view(driver, wait, max_days_target=365):
    # Vrne (day_min, day_max) ali (None, None) če ne uspe preklopiti.
    for attempt in range(3):
        # Primarni način: klik na znane gumbe kalkulatorja
        try:
            driver.execute_script(
                "const el = document.getElementById('depositBindPeriodDays'); if (el) { el.scrollIntoView({block:'center'}); el.click(); }"
            )
        except:
            pass

        # Fallback: klik po tekstu
        click_tab_by_text(driver, wait, "PRIKAŽITE V DNEH")
        click_tab_by_text(driver, wait, "PRIKAŽITE V DNE")
        time.sleep(0.3)

        term_id, _ = detect_term_and_amount_inputs(driver, wait)
        day_min = None
        day_max = None
        if term_id is not None:
            try:
                el = driver.find_element(By.ID, term_id)
                day_min = int(float(el.get_attribute("min")))
                day_max = int(float(el.get_attribute("max")))
            except:
                day_min = None
                day_max = None

        try:
            if term_id is not None:
                print(
                    f"INFO days-detect term_id={term_id} min={day_min} max={day_max}")
        except:
            pass

        # Če max skoči na nekaj velikega, smo v dneh.
        if day_max is not None and day_max >= 300:
            return day_min, min(day_max, max_days_target)

        # JS fallback: poišči element, ki vsebuje tekst (textContent), in klikni klikabilen ancestor
        try:
            driver.execute_script(
                """
                const want = (arguments[0] || '').toUpperCase();
                const nodes = Array.from(document.querySelectorAll('button,a,[role=button],label,span,div'));
                const hit = nodes.find(n => ((n.textContent || '') + '').trim().toUpperCase().includes(want));
                if (!hit) return;
                const clickable = hit.closest('button,a,[role=button]') || hit;
                clickable.scrollIntoView({block:'center', inline:'center'});
                clickable.click();
                """,
                "PRIKAŽITE V DNEH",
            )
        except:
            pass

        time.sleep(0.5)

    return None, None


def ensure_months_view(driver, wait):
    # Vrne (term_min, term_max) za mesece ali (None, None) če ne uspe.
    for attempt in range(3):
        try:
            driver.execute_script(
                "const el = document.getElementById('depositBindPeriodMonths'); if (el) { el.scrollIntoView({block:'center'}); el.click(); }"
            )
        except:
            pass

        click_tab_by_text(driver, wait, "PRIKAŽITE V MESECIH")
        click_tab_by_text(driver, wait, "PRIKAŽITE V MESE")
        time.sleep(0.3)

        term_id, _ = detect_term_and_amount_inputs(driver, wait)
        if term_id is None:
            continue
        try:
            el = driver.find_element(By.ID, term_id)
            term_min = int(float(el.get_attribute("min")))
            term_max = int(float(el.get_attribute("max")))
        except:
            continue

        # Mesečni view ima ponavadi max v desetih (npr. 35)
        if term_max is not None and term_max <= 120:
            return term_min, term_max

    return None, None


def read_rate(driver, wait):
    rate_el = wait.until(
        EC.presence_of_element_located((By.ID, "depositAnnualInterestRate"))
    )
    rate_text = rate_el.text.strip().replace("%", "").replace(",", ".")
    return float(rate_text)


def set_slider_and_wait_rate(driver, wait, term_id, amount_id, term_value, amount_value, timeout_s=6.0):
    try:
        prev_text = driver.find_element(
            By.ID, "depositAnnualInterestRate").text.strip()
    except:
        prev_text = ""

    trigger_events(driver, term_id, term_value)
    trigger_events(driver, amount_id, amount_value)

    # V "dneh" načinu se OM pogosto ne spremeni med sosednjimi vrednostmi, zato ne smemo čakati
    # izključno na spremembo teksta. Namesto tega počakamo, da se kontrola nastavi in da se rezultat stabilizira.
    end = time.time() + timeout_s
    last_err = None
    stable_count = 0
    last_text = None
    while time.time() < end:
        try:
            try:
                term_el = driver.find_element(By.ID, term_id)
                term_now = (term_el.get_attribute("value") or "").strip()
            except:
                term_now = ""

            cur_el = driver.find_element(By.ID, "depositAnnualInterestRate")
            cur_text = (cur_el.text or "").strip()

            # če je rezultat prazen, še čakamo
            if not cur_text:
                stable_count = 0
                last_text = None
                time.sleep(0.12)
                continue

            # če smo dobili spremembo, lahko vrnemo takoj
            if prev_text and cur_text != prev_text and term_now == str(term_value):
                return float(cur_text.replace("%", "").replace(",", "."))

            # sicer čakamo, da je term nastavljen + rezultat stabilen 2 cikla
            if term_now == str(term_value):
                if last_text is not None and cur_text == last_text:
                    stable_count += 1
                else:
                    stable_count = 0
                last_text = cur_text

                if stable_count >= 1:
                    return float(cur_text.replace("%", "").replace(",", "."))

        except Exception as e:
            last_err = e

        time.sleep(0.12)

    try:
        return read_rate(driver, wait)
    except:
        if last_err:
            raise last_err
        raise


def trigger_events(driver, element_id, value):
    driver.execute_script("""
        const el = document.getElementById(arguments[0]);
        if (!el) return;
        el.value = arguments[1];
        el.dispatchEvent(new Event('input', { bubbles: true }));
        el.dispatchEvent(new Event('change', { bubbles: true }));
    """, element_id, value)


def detect_term_and_amount_inputs(driver, wait):
    # Prefer range sliders if present, otherwise fall back to number inputs.
    # Na strani obstajata ločena gumba za preklop (Months/Days) in lahko tudi ločeni input ID-ji.
    term_candidates = [
        "depositBindPeriodDaysRange",
        "depositBindPeriodRange",
        "depositBindPeriod",
    ]
    amount_candidates = [
        "depositTiedAmountDaysRange",
        "depositTiedAmountRange",
        "depositTiedAmount",
    ]

    term_id = None
    amount_id = None

    def _pick_visible(candidates):
        # prefer elements that exist and are actually visible (active UI)
        for cid in candidates:
            try:
                els = driver.find_elements(By.ID, cid)
                if not els:
                    continue
                el = els[0]
                # Guard: button IDs exist on the page; we only want real input controls.
                if el.tag_name.lower() == "input" and el.is_displayed() and el.is_enabled():
                    return cid
            except:
                continue

        # fallback: first one that exists in DOM
        for cid in candidates:
            try:
                wait.until(EC.presence_of_element_located((By.ID, cid)))
                el = driver.find_element(By.ID, cid)
                if el.tag_name.lower() != "input":
                    continue
                return cid
            except:
                continue
        return None

    term_id = _pick_visible(term_candidates)
    amount_id = _pick_visible(amount_candidates)

    return term_id, amount_id


def scrape_gbkr():
    bank_id = 9
    bank_name = "Gorenjska banka d.d."

    pdf_rows = scrape_gbkr_from_pdf()
    if pdf_rows:
        print(f"[OK] GBKR: PDF vir uporabljen ({len(pdf_rows)} zapisov)")
        return pdf_rows
    print("[WARN] GBKR: PDF parse ni uspel, fallback na Selenium")

    print("Zaganjam GBKR scraper...")

    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")

    driver = webdriver.Chrome(options=chrome_options)
    driver.get(URL)

    wait = WebDriverWait(driver, 15)

    print("\n--- Preverjanje strukture GBKR ---")

    # Najprej prisilimo mesečni view (da dobimo pravilne mesečne meje)
    months_min, months_max = ensure_months_view(driver, wait)
    term_id, amount_id = detect_term_and_amount_inputs(driver, wait)
    if not term_id or not amount_id:
        print("⚠ OPOZORILO: Ne najdem vhodov za znesek/ročno ročnost (term/amount). Struktura strani se je spremenila.")
        driver.quit()
        return []

    try:
        amount_el = driver.find_element(By.ID, amount_id)
        duration_el = driver.find_element(By.ID, term_id)
        print(f"✓ Vhodi so prisotni. term_id={term_id}, amount_id={amount_id}")
    except:
        print("⚠ OPOZORILO: Vhodi niso najdeni! Struktura strani se je spremenila.")
        driver.quit()
        return []

    # preverimo min/max sliderja
    try:
        slider_min = int(float(amount_el.get_attribute("min")))
        slider_max = int(float(amount_el.get_attribute("max")))
    except:
        slider_min = None
        slider_max = None

    if slider_min != EXPECTED_MIN_AMOUNT:
        print(
            f"⚠ OPOZORILO: GBKR je spremenila minimalni znesek! Pričakovano {EXPECTED_MIN_AMOUNT}, dobili {slider_min}")
    else:
        print(f"✓ Minimalni znesek sliderja = {slider_min} EUR (pričakovano)")

    if slider_max != EXPECTED_MAX_AMOUNT:
        print(
            f"⚠ OPOZORILO: GBKR je spremenila maksimalni znesek! Pričakovano {EXPECTED_MAX_AMOUNT}, dobili {slider_max}")
    else:
        print(f"✓ Maksimalni znesek sliderja = {slider_max} EUR (pričakovano)")

    results = []
    scraped_terms = {}

    print("\n--- Obrestne mere (meseci) ---")

    if months_min is not None and months_max is not None:
        term_min = months_min
        term_max = months_max
    else:
        try:
            term_min = int(float(duration_el.get_attribute("min")))
            term_max = int(float(duration_el.get_attribute("max")))
        except:
            term_min = 13
            term_max = 60

    month_terms = [m for m in CHECK_TERMS if term_min <= m <= term_max]
    if not month_terms:
        month_terms = list(range(term_min, term_max + 1))

    for term in month_terms:
        rate = None

        for attempt in range(3):
            trigger_events(driver, term_id, term)
            time.sleep(0.3)

            trigger_events(driver, amount_id, EXPECTED_MIN_AMOUNT)
            time.sleep(0.3)

            try:
                rate_el = wait.until(
                    EC.presence_of_element_located(
                        (By.ID, "depositAnnualInterestRate"))
                )
                rate_text = rate_el.text.strip().replace("%", "").replace(",", ".")
                rate = float(rate_text)
                break
            except:
                continue

        if rate is None:
            print(f"– {term}M: ni veljavne ponudbe.")
            continue

        scraped_terms[term] = rate
        print(f"✓ {term}M: {rate}%")

        results.append({
            "id": bank_id,
            "bank": bank_name,
            "product_name": f"Depozit {term}M",
            "amount_min": EXPECTED_MIN_AMOUNT,
            "amount_max": EXPECTED_MAX_AMOUNT,
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

    print("\n--- Obrestne mere (dni) ---")

    day_min, day_max = ensure_days_view(driver, wait, max_days_target=365)
    if day_min is not None and day_max is not None:
        # po preklopu ponovno zaznamo aktivne inpute (v dneh so lahko drugi)
        term_id, amount_id = detect_term_and_amount_inputs(driver, wait)

        try:
            el = driver.find_element(By.ID, term_id)
            print(
                f"INFO days-active term_id={term_id} amount_id={amount_id} min={el.get_attribute('min')} max={el.get_attribute('max')}"
            )
        except:
            pass

    if day_min is None or day_max is None:
        print("⚠ OPOZORILO: Ne najdem dnevnega sliderja (min/max). Preskakujem dnevne ročnosti.")
    else:
        def get_rate_for_day(d):
            return set_slider_and_wait_rate(driver, wait, term_id, amount_id, d, EXPECTED_MIN_AMOUNT)

        # Ker so OM po dnevih kosovno konstantne, poiščemo meje segmentov učinkovito
        segments = []  # list of (start_day, end_day, rate)
        cur_day = day_min
        try:
            cur_rate = get_rate_for_day(cur_day)
        except:
            cur_rate = None

        if cur_rate is None:
            print(
                "⚠ OPOZORILO: Ne morem prebrati OM v dnevnem pogledu. Preskakujem dnevne ročnosti.")
        else:
            while cur_day <= day_max:
                # najdi prvi dan po cur_day, kjer se rate spremeni
                lo = cur_day
                hi = cur_day

                # eksponentno naprej dokler rate ostaja ista
                while True:
                    nxt = hi + 1
                    if nxt > day_max:
                        hi = day_max
                        break

                    step = max(1, (hi - lo + 1))
                    probe = min(day_max, hi + step)
                    try:
                        probe_rate = get_rate_for_day(probe)
                    except:
                        probe_rate = None

                    if probe_rate is None or abs(probe_rate - cur_rate) > 1e-9:
                        # sprememba je med hi+1 in probe
                        break
                    hi = probe

                    if hi >= day_max:
                        break

                if hi >= day_max:
                    segments.append((cur_day, day_max, cur_rate))
                    break

                # če se je sprememba zgodila takoj naslednji dan
                if hi == cur_day:
                    change_search_lo = cur_day + 1
                else:
                    change_search_lo = hi + 1
                change_search_hi = min(day_max, hi + max(1, (hi - lo + 1)))

                # binarno poiščemo prvi dan, kjer rate != cur_rate
                first_change = None
                left = change_search_lo
                right = change_search_hi
                while left <= right:
                    mid = (left + right) // 2
                    try:
                        mid_rate = get_rate_for_day(mid)
                    except:
                        mid_rate = None
                    if mid_rate is None or abs(mid_rate - cur_rate) > 1e-9:
                        first_change = mid
                        right = mid - 1
                    else:
                        left = mid + 1

                if first_change is None:
                    segments.append((cur_day, day_max, cur_rate))
                    break

                segments.append((cur_day, first_change - 1, cur_rate))
                cur_day = first_change
                try:
                    cur_rate = get_rate_for_day(cur_day)
                except:
                    break

            any_day_validation_warning = False

            for (a, b, r) in segments:
                print(f"✓ {a}–{b} dni: {r}%")

                # Validacija pričakovanih OM za dni (informativno opozorilo ob spremembi)
                expected = None
                if 31 <= a <= 90 and 31 <= b <= 90:
                    expected = 0.4
                elif 91 <= a <= 180 and 91 <= b <= 180:
                    expected = 0.6
                elif 181 <= a <= 365 and 181 <= b <= 365:
                    expected = 0.9

                if expected is not None:
                    if abs(float(r) - float(expected)) > 1e-9:
                        any_day_validation_warning = True
                        print(
                            f"⚠ OPOZORILO: OM za {a}–{b} dni je {r}%, pričakovano {expected}% (sprememba na strani?)")
                    else:
                        print(
                            f"OK Validacija dni {a}–{b}: {r}% (pričakovano {expected}%)")
                else:
                    any_day_validation_warning = True
                    print(
                        f"⚠ OPOZORILO: Najden interval dni {a}–{b} izven pričakovanih (31–90/91–180/181–365). Preveri kalkulator.")

                results.append({
                    "id": bank_id,
                    "bank": bank_name,
                    "product_name": f"Depozit {a}–{b} dni",
                    "amount_min": EXPECTED_MIN_AMOUNT,
                    "amount_max": EXPECTED_MAX_AMOUNT,
                    "amount_currency": "EUR",
                    "min_term": a,
                    "max_term": b,
                    "term_unit": "days",
                    "rate_branch": r,
                    "rate_klik_bonus": 0.0,
                    "rate_klik_total": r,
                    "url": URL,
                    "last_updated": datetime.today().strftime("%Y-%m-%d"),
                    "notes": "redna ponudba"
                })

            if any_day_validation_warning:
                print(
                    "⚠ OPOZORILO: GBKR dnevne OM niso skladne s pričakovanimi vrednostmi.")
            else:
                print("OK Validacija dnevnih OM: skladno s pričakovanimi vrednostmi.")

    driver.quit()

    found_terms = sorted(scraped_terms.keys())
    print("\n--- Povzetek najdenih ročnosti ---")
    print("Najdene ročnosti:", found_terms)

    print(f"\n✓ GBKR: uspešno scrapano {len(results)} zapisov.")
    return results


def save_to_csv(rows, filename="gbkr_depoziti.csv"):
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
    data = scrape_gbkr()
    save_to_csv(data)
