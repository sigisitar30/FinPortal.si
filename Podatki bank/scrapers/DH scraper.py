from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import requests
import pdfplumber
import csv
from datetime import datetime
import time
import os
import io
import re

URL = "https://www.dh.si/varcevanja-in-nalozbe/depoziti/"
PDF_URL = "https://www.dh.si/doc/tarifa-in-obrestne-mere/sklep-o-obrestnih-merah-veljavnost-15012026.pdf"

# PRIČAKOVANE VREDNOSTI SLIDERJA
EXPECTED_MIN_AMOUNT = 100
EXPECTED_MAX_AMOUNT = 500000

# Preverjamo vse ročnosti 1–60M
CHECK_TERMS = list(range(1, 61))


def trigger_events(driver, element_id, value):
    driver.execute_script("""
        const el = document.getElementById(arguments[0]);
        if (!el) return;
        el.value = arguments[1];
        el.dispatchEvent(new Event('input', { bubbles: true }));
        el.dispatchEvent(new Event('change', { bubbles: true }));
    """, element_id, value)


def _to_float_rate(s: str):
    try:
        return float(str(s).replace("%", "").replace(",", ".").strip())
    except:
        return None


def _scrape_dh_from_pdf():
    bank_id = 7
    bank_name = "Delavska hranilnica d.d."
    today = datetime.today().strftime("%Y-%m-%d")

    print("INFO DH: branje PDF obrestnih mer...")
    try:
        r = requests.get(PDF_URL, timeout=30)
        r.raise_for_status()
        pdf_bytes = r.content
    except Exception as e:
        raise RuntimeError(f"PDF download failed: {e}")

    try:
        pdf = pdfplumber.open(io.BytesIO(pdf_bytes))
        text = (pdf.pages[0].extract_text() or "") if pdf.pages else ""
    except Exception as e:
        raise RuntimeError(f"PDF parse failed: {e}")
    finally:
        try:
            pdf.close()
        except:
            pass

    if not text:
        raise RuntimeError("PDF text empty")

    # Minimalni znesek (FO) se pojavi kot: "... v najnižjem znesku 100,00 EUR"
    parsed_min_amount = None
    try:
        m_min = re.search(
            r"najnižjem\s+znesku\s*([0-9\.\s]+(?:,[0-9]{1,2})?)\s*EUR",
            text,
            flags=re.IGNORECASE,
        )
        if m_min:
            raw = m_min.group(1)
            raw = raw.replace(".", "").replace(
                " ", "").replace("\u00a0", "").replace(",", ".")
            parsed_min_amount = int(float(raw))
    except:
        parsed_min_amount = None

    if parsed_min_amount is not None and parsed_min_amount != EXPECTED_MIN_AMOUNT:
        print(
            f"WRN DH: minimalni znesek v PDF se je spremenil (PDF={parsed_min_amount}, expected={EXPECTED_MIN_AMOUNT})")

    expiry_note = None
    try:
        # Najprej poskusimo najti datum v bližini fraze "posebna ponudba"
        m_exp = re.search(
            r"posebna\s+ponudba[\s\S]{0,120}?(\d{1,2})\s*\.\s*(\d{1,2})\s*\.\s*(\d{4})",
            text,
            flags=re.IGNORECASE,
        )
        if not m_exp:
            # Fallback: prvi datum v dokumentu
            m_exp = re.search(
                r"\b(\d{1,2})\s*\.\s*(\d{1,2})\s*\.\s*(\d{4})\b", text)
        if m_exp:
            d, m, y = m_exp.groups()
            expiry_note = f"posebna ponudba do {int(d)}.{int(m)}.{y} (ne upoštevamo)"
    except:
        expiry_note = None

    notes_text = "scraped via PDF" if not expiry_note else f"scraped via PDF; {expiry_note}"

    # Izluščimo samo del za fizične osebe → vezane vloge
    # PDF ima jasno označene razdelke: "1. VLOGE FIZIČNIH OSEB" / "1.2 VEZANE VLOGE" / "1.3 ..."
    t = text
    m_start = re.search(
        r"\b1\.\s*VLOGE\s+FIZI[ČC]NIH\s+OSEB\b", t, flags=re.IGNORECASE)
    m_vz = re.search(
        r"\b1\.\s*2\s*VEZANE\s+VLOGE\b|\b1\.2\s*VEZANE\s+VLOGE\b", t, flags=re.IGNORECASE)
    m_next = re.search(r"\b1\.\s*3\b|\b1\.3\b", t)

    if not m_vz:
        raise RuntimeError("PDF: section 'VEZANE VLOGE' not found")

    cut_from = m_vz.start()
    cut_to = m_next.start() if m_next and m_next.start() > cut_from else len(t)
    section = t[cut_from:cut_to]

    # Normalizacija
    section_norm = (
        section.replace("\u00a0", " ")
        .replace("\u202f", " ")
    )

    day_rates = []
    # npr: "od 31 do 90 dni 0,60 %"
    for a, b, rate_s in re.findall(r"od\s*(\d+)\s*do\s*(\d+)\s*dni\s*([0-9]+(?:[\.,][0-9]+)?)\s*%", section_norm, flags=re.IGNORECASE):
        rate = _to_float_rate(rate_s)
        if rate is None:
            continue
        day_rates.append((int(a), int(b), rate))

    month_ranges = []
    # "nad 12 mesecev 1,40 %"
    for mo, rate_s in re.findall(r"nad\s*(\d+)\s*mesecev\s*([0-9]+(?:[\.,][0-9]+)?)\s*%", section_norm, flags=re.IGNORECASE):
        rate = _to_float_rate(rate_s)
        if rate is None:
            continue
        month_ranges.append((int(mo), "months", rate))

    # "nad 2 leti 1,40 %" itd.
    for yrs, rate_s in re.findall(r"nad\s*(\d+)\s*let(?:a|i)?\s*([0-9]+(?:[\.,][0-9]+)?)\s*%", section_norm, flags=re.IGNORECASE):
        rate = _to_float_rate(rate_s)
        if rate is None:
            continue
        month_ranges.append((int(yrs) * 12, "years", rate))

    if not day_rates and not month_ranges:
        raise RuntimeError("PDF: no deposit rates parsed")

    # Znesek: PDF navaja minimalni znesek, zgornje meje za FO ne navaja eksplicitno.
    amount_min = parsed_min_amount if parsed_min_amount is not None else EXPECTED_MIN_AMOUNT
    amount_max = EXPECTED_MAX_AMOUNT

    results = []

    for a, b, rate in sorted(day_rates, key=lambda x: (x[0], x[1])):
        results.append(
            {
                "id": bank_id,
                "bank": bank_name,
                "product_name": f"Depozit {a}-{b} dni",
                "amount_min": amount_min,
                "amount_max": amount_max,
                "amount_currency": "EUR",
                "min_term": a,
                "max_term": b,
                "term_unit": "days",
                "rate_branch": rate,
                "rate_klik_bonus": 0.0,
                "rate_klik_total": rate,
                "url": PDF_URL,
                "last_updated": today,
                "notes": notes_text,
            }
        )

    # Iz 'nad X' naredimo intervale (X .. nextX-1) v mesecih.
    # Opomba: tukaj prag interpretiramo kot "od vključno X mesecev naprej" (12M vključeno).
    # V PDF-ju sta lahko 'nad 12 mesecev' in 'nad 2 leti' z isto OM; vseeno razmejimo intervale.
    thresholds = sorted({m for m, _, _ in month_ranges})
    rate_by_threshold = {}
    for m, _, r in month_ranges:
        # če se prag pojavi večkrat, preferiraj višjo OM (varovalka)
        rate_by_threshold[m] = max(rate_by_threshold.get(m, float("-inf")), r)

    for i, thr in enumerate(thresholds):
        min_m = thr
        max_m = (thresholds[i + 1] - 1) if i + 1 < len(thresholds) else None
        rate = rate_by_threshold.get(thr)
        if rate is None:
            continue

        max_term = int(max_m) if max_m is not None else None
        if max_term is not None and max_term < min_m:
            continue

        label = f"{min_m}M" if max_term is None else f"{min_m}-{max_term}M"
        results.append(
            {
                "id": bank_id,
                "bank": bank_name,
                "product_name": f"Depozit {label}",
                "amount_min": amount_min,
                "amount_max": amount_max,
                "amount_currency": "EUR",
                "min_term": min_m,
                "max_term": max_term,
                "term_unit": "months",
                "rate_branch": rate,
                "rate_klik_bonus": 0.0,
                "rate_klik_total": rate,
                "url": PDF_URL,
                "last_updated": today,
                "notes": notes_text,
            }
        )

    print(f"OK DH: PDF scrapano {len(results)} zapisov")
    return results


def scrape_dh():
    try:
        return _scrape_dh_from_pdf()
    except Exception as e:
        print(f"WRN DH: PDF scrape ni uspel ({e}) → fallback na Selenium")
        return _scrape_dh_with_selenium_impl()


def _scrape_dh_with_selenium_impl():
    bank_id = 7
    bank_name = "Delavska hranilnica d.d."

    print("Zaganjam DH scraper...")

    chrome_options = Options()
    chrome_options.add_argument("--start-maximized")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument(
        "--disable-blink-features=AutomationControlled")

    driver = webdriver.Chrome(options=chrome_options)
    driver.get(URL)

    wait = WebDriverWait(driver, 20)

    # scroll do kalkulatorja
    driver.execute_script("window.scrollTo(0, 1800);")
    time.sleep(2)

    print("\n--- Preverjanje strukture DH ---")

    try:
        amount_slider = wait.until(
            EC.presence_of_element_located(
                (By.ID, "varcevanje_depozit-amount-slider"))
        )
        duration_slider = wait.until(
            EC.presence_of_element_located(
                (By.ID, "varcevanje_depozit-duration-slider"))
        )
        print("✓ Sliderji so prisotni.")
    except:
        print("⚠ OPOZORILO: Sliderji niso najdeni! Struktura strani se je spremenila.")
        driver.quit()
        return []

    # preverimo min/max sliderja
    try:
        slider_min = int(amount_slider.get_attribute("min"))
        slider_max = int(amount_slider.get_attribute("max"))
    except:
        slider_min = None
        slider_max = None

    if slider_min != EXPECTED_MIN_AMOUNT:
        print(
            f"⚠ OPOZORILO: DH je spremenila minimalni znesek! Pričakovano {EXPECTED_MIN_AMOUNT}, dobili {slider_min}")
    else:
        print(f"✓ Minimalni znesek sliderja = {slider_min} EUR (pričakovano)")

    if slider_max != EXPECTED_MAX_AMOUNT:
        print(
            f"⚠ OPOZORILO: DH je spremenila maksimalni znesek! Pričakovano {EXPECTED_MAX_AMOUNT}, dobili {slider_max}")
    else:
        print(f"✓ Maksimalni znesek sliderja = {slider_max} EUR (pričakovano)")

    results = []
    scraped_terms = {}

    print("\n--- Obrestne mere (1–60M) ---")

    for term in CHECK_TERMS:
        rate = None

        for attempt in range(3):
            trigger_events(driver, "varcevanje_depozit-duration-slider", term)
            time.sleep(0.3)

            trigger_events(
                driver, "varcevanje_depozit-amount-slider", EXPECTED_MIN_AMOUNT)
            time.sleep(0.3)

            try:
                calc_btn = wait.until(
                    EC.element_to_be_clickable(
                        (By.XPATH, "//button[contains(text(), 'Izračunaj')]")
                    )
                )
                driver.execute_script(
                    "arguments[0].scrollIntoView({block: 'center'});", calc_btn)
                time.sleep(0.2)
                driver.execute_script("arguments[0].click();", calc_btn)
            except:
                continue

            time.sleep(0.7)

            try:
                rate_el = wait.until(
                    EC.presence_of_element_located((
                        By.XPATH,
                        "//div[@class='name' and contains(text(),'Obrestna mera')]/following-sibling::div[@class='value']"
                    ))
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

    driver.quit()

    found_terms = sorted(scraped_terms.keys())
    print("\n--- Povzetek najdenih ročnosti ---")
    print("Najdene ročnosti:", found_terms)

    print(f"\n✓ DH: uspešno scrapano {len(results)} zapisov.")
    return results


def save_to_csv(rows, filename="dh_depoziti.csv"):
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
    data = scrape_dh()
    save_to_csv(data)
