import requests
from bs4 import BeautifulSoup
import csv
from datetime import datetime
import re
import json
import html
import os

URL = "https://www.sparkasse.si/sl/prebivalstvo/ceniki-in-obrestne-mere/varcevanja"
PREVIOUS_FILE = "sparkasse_previous.json"


# -----------------------------
# PARSE TERM RANGE
# -----------------------------
def parse_term_range(text):
    text = text.lower().strip()
    text = re.sub(r"\s+", " ", text)

    if re.match(r"^\d+\s*[-–]\s*\d+$", text):
        a, b = re.split(r"[-–]", text)
        return int(a), int(b), "days"

    if text.startswith("nad"):
        nums = re.findall(r"\d+", text)
        if len(nums) == 2:
            return int(nums[0]), int(nums[1]), "months"
        if len(nums) == 1:
            return int(nums[0]), None, "months"

    return None


# -----------------------------
# CLEAN RATE
# -----------------------------
def clean_rate(val):
    val = val.strip()
    if not val:
        return None
    val = val.replace("%", "").replace(",", ".")
    try:
        return float(val)
    except:
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
# SCRAPE SPARKASSE (TVOJA KODA)
# -----------------------------
def scrape_sparkasse():
    bank_id = 5
    bank_name = "Sparkasse"

    resp = requests.get(URL, headers={"User-Agent": "Mozilla/5.0"})
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    script = soup.find("script", {
        "type": "application/gem+json",
        "class": "js-gem-json-config",
        "data-cid": "7ff615",
    })

    if not script:
        print("Ni našel GEM JSON skripta.")
        return []

    cfg = json.loads(script.text)
    table_html = html.unescape(cfg["text"])

    table_soup = BeautifulSoup(table_html, "html.parser")
    table = table_soup.find("table")
    rows = table.find_all("tr")[1:]  # preskočimo header

    results = []

    for row in rows:
        cols = [c.get_text(strip=True) for c in row.find_all("td")]

        term_months = cols[0] if len(cols) > 0 else ""
        term_days = cols[1] if len(cols) > 1 else ""
        rate_branch = cols[2] if len(cols) > 2 else ""
        rate_online = cols[3] if len(cols) > 3 else ""

        parsed = parse_term_range(term_months) or parse_term_range(term_days)
        if not parsed:
            continue

        min_term, max_term, unit = parsed

        rb = clean_rate(rate_branch)
        ro = clean_rate(rate_online)
        if rb is None and ro is None:
            continue
        if rb is None:
            rb = ro
        if ro is None:
            ro = rb

        key = f"{min_term}-{max_term or min_term}-{unit}"

        if max_term is None:
            product_name = f"Depozit {min_term}+ {unit}"
        else:
            product_name = f"Depozit {min_term}-{max_term} {unit}"

        results.append({
            "key": key,
            "id": bank_id,
            "bank": bank_name,
            "product_name": product_name,
            "amount_min": 500,
            "amount_max": None,
            "amount_currency": "EUR",
            "min_term": min_term,
            "max_term": max_term,
            "term_unit": unit,
            "rate_branch": rb,
            "rate_klik_bonus": ro - rb,
            "rate_klik_total": ro,
            "url": URL,
            "last_updated": datetime.today().strftime("%Y-%m-%d"),
            "notes": "scraped from Sparkasse GEM JSON tabela",
        })

    print(f"✓ Sparkasse: uspešno scrapano {len(results)} zapisov.")
    return results


# -----------------------------
# CHECK FOR CHANGES (kot Intesa/OTP)
# -----------------------------
def check_changes(new_data):
    previous = load_previous()

    for item in new_data:
        key = item["key"]

        if key not in previous:
            print(f"🆕 NOV PRODUKT: {item['product_name']}")
            continue

        old = previous[key]

        if old["min_term"] != item["min_term"] or old["max_term"] != item["max_term"]:
            print(f"⚠ SPREMEMBA TERMINA: {item['product_name']}  "
                  f"{old['min_term']}-{old['max_term']} → {item['min_term']}-{item['max_term']}")

        if old["rate_branch"] != item["rate_branch"]:
            print(f"⚠ SPREMEMBA OBRESTNE MERE (POSLOŽNICA): {item['product_name']}  "
                  f"{old['rate_branch']} → {item['rate_branch']}")

        if old["rate_klik_total"] != item["rate_klik_total"]:
            print(f"⚠ SPREMEMBA OBRESTNE MERE (ONLINE): {item['product_name']}  "
                  f"{old['rate_klik_total']} → {item['rate_klik_total']}")

    save_previous({item["key"]: item for item in new_data})


# -----------------------------
# SAVE CSV
# -----------------------------
def save_to_csv(rows, filename="sparkasse_depoziti.csv"):
    if not rows:
        print("Ni podatkov za zapis v CSV.")
        return

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    filename = os.path.join(base_dir, filename)

    fieldnames = [k for k in rows[0].keys() if k != "key"]

    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=";")
        writer.writeheader()
        for row in rows:
            row = {k: v for k, v in row.items() if k != "key"}
            writer.writerow(row)

    print(f"✓ CSV zapisan v: {filename}")


# -----------------------------
# MAIN
# -----------------------------
if __name__ == "__main__":
    data = scrape_sparkasse()
    if data:
        check_changes(data)
        save_to_csv(data)
