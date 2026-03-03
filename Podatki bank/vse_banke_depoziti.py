import subprocess
import pandas as pd
import os
from datetime import datetime
import shutil
import glob
import sys


REQUIRED_COLUMNS = [
    "id", "bank", "product_name",
    "amount_min", "amount_max", "amount_currency",
    "min_term", "max_term", "term_unit",
    "rate_branch", "rate_klik_bonus", "rate_klik_total",
    "url", "last_updated", "notes", "offer_type",
    "source"
]


def _validate_schema(df, source_file):
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        return [f"Manjkajo kolone: {missing}"], []
    return [], []


def _validate_invariants(df, source_file):
    errs = []
    warns = []

    numeric_cols = ["amount_min", "amount_max", "min_term",
                    "max_term", "rate_branch", "rate_klik_total"]
    for c in numeric_cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")

    if (df["amount_min"].isna()).any():
        errs.append("amount_min vsebuje prazne/neveljavne vrednosti")
    if (df["amount_min"] < 0).any():
        errs.append("amount_min < 0")

    if "amount_max" in df.columns:
        bad_max = df["amount_max"].notna() & (
            df["amount_max"] < df["amount_min"])
        if bad_max.any():
            errs.append("amount_max < amount_min")

    bad_unit = ~df["term_unit"].isin(["days", "months"])
    if bad_unit.any():
        errs.append(
            "term_unit ima neveljavne vrednosti (dovoljeno: days/months)")

    bad_term = df["min_term"].isna() | (df["max_term"].notna() &
                                        (df["min_term"] > df["max_term"]))
    if bad_term.any():
        errs.append("neveljaven interval roka (min_term/max_term)")

    bad_rate = df["rate_branch"].isna() | (
        df["rate_branch"] < 0) | (df["rate_branch"] > 25)
    if bad_rate.any():
        warns.append("sumljive vrednosti rate_branch (NaN ali izven 0-25)")

    if "offer_type" in df.columns:
        bad_offer = ~df["offer_type"].astype(
            str).str.lower().isin(["regular", "special"])
        if bad_offer.any():
            errs.append(
                "offer_type ima neveljavne vrednosti (dovoljeno: regular/special)")

    if "source" in df.columns:
        bad_source = ~df["source"].astype(
            str).str.lower().isin(["pdf", "web", "api"])
        if bad_source.any():
            errs.append(
                "source ima neveljavne vrednosti (dovoljeno: pdf/web/api)")

    if source_file == "otp_depoziti.csv":
        otp_months = df["term_unit"] == "months"
        if otp_months.any() and (df.loc[otp_months, "amount_min"] < 500).any():
            errs.append(
                "OTP: dolgoročni depoziti morajo imeti amount_min >= 500")

    if source_file == "gbkr_depoziti.csv":
        gbkr_days = df["term_unit"] == "days"
        gbkr_months = df["term_unit"] == "months"

        if not gbkr_days.any():
            errs.append("GBKR: manjkajo dnevne ročnosti (term_unit=days)")
        else:
            if (df.loc[gbkr_days, "min_term"] < 31).any() or (df.loc[gbkr_days, "max_term"] > 365).any():
                warns.append(
                    "GBKR: dnevne ročnosti izven pričakovanega območja (31–365)")

        if not gbkr_months.any():
            errs.append("GBKR: manjkajo mesečne ročnosti (term_unit=months)")
        else:
            if (df.loc[gbkr_months, "min_term"] < 13).any():
                warns.append(
                    "GBKR: mesečne ročnosti vsebujejo vrednosti < 13M")

    days_mask = df["term_unit"] == "days"
    if days_mask.any():
        try:
            day_rows = df.loc[days_mask].copy()
            day_rows["min_term"] = pd.to_numeric(
                day_rows["min_term"], errors="coerce")
            day_rows["max_term"] = pd.to_numeric(
                day_rows["max_term"], errors="coerce")

            covers_31 = ((day_rows["min_term"] <= 31) & (
                day_rows["max_term"].fillna(day_rows["min_term"]) >= 31)).any()
            covers_91 = ((day_rows["min_term"] <= 91) & (
                day_rows["max_term"].fillna(day_rows["min_term"]) >= 91)).any()
            if covers_31 and not covers_91:
                warns.append(
                    "day ročnosti pokrivajo ~1M (31d), ne pa 3M meje (91d); preveri, ali banka res nima 3M ali je scraper izpustil interval"
                )

            ends_90 = (day_rows["max_term"].fillna(
                day_rows["min_term"]) == 90).any()
            starts_le_91 = (day_rows["min_term"] <= 91).any()
            if ends_90 and not starts_le_91:
                warns.append(
                    "zaznan interval do 90 dni, vendar ni intervala, ki bi se začel pri 91 dni ali prej; preveri prehod 2M->3M"
                )
        except Exception:
            pass

    return errs, warns


def _diff_metrics(df_now, df_prev, source_file=None):
    warns = []
    if df_prev is None or df_prev.empty:
        return warns

    if source_file == "gbkr_depoziti.csv":
        return warns

    if source_file == "dh_depoziti.csv":
        return warns

    if source_file == "otp_depoziti.csv":
        return warns

    now_rows = len(df_now)
    prev_rows = len(df_prev)
    if prev_rows > 0:
        ratio = now_rows / prev_rows
        if ratio < 0.7 or ratio > 1.3:
            warns.append(
                f"row_count odstopa (prej={prev_rows}, zdaj={now_rows})")

    key_cols = ["product_name", "min_term", "max_term",
                "term_unit", "amount_min", "amount_max"]
    for c in key_cols:
        if c not in df_now.columns or c not in df_prev.columns:
            return warns

    now_keys = set(tuple(x) for x in df_now[key_cols].fillna(-1).to_numpy())
    prev_keys = set(tuple(x) for x in df_prev[key_cols].fillna(-1).to_numpy())

    removed = prev_keys - now_keys
    added = now_keys - prev_keys

    if removed:
        warns.append(f"odstranjeni produkti: {min(len(removed), 5)} primerov")
    if added:
        warns.append(f"novi produkti: {min(len(added), 5)} primerov")

    try:
        now = df_now.copy()
        prev = df_prev.copy()

        for c in ["rate_branch", "rate_klik_total", "amount_min", "amount_max", "min_term", "max_term"]:
            if c in now.columns:
                now[c] = pd.to_numeric(now[c], errors="coerce")
            if c in prev.columns:
                prev[c] = pd.to_numeric(prev[c], errors="coerce")

        key_cols_rate = [
            "product_name",
            "min_term",
            "max_term",
            "term_unit",
            "amount_min",
            "amount_max",
        ]
        if all(c in now.columns for c in key_cols_rate) and all(c in prev.columns for c in key_cols_rate):
            now_merge = now[key_cols_rate +
                            ["rate_branch", "rate_klik_total"]].fillna(-1)
            prev_merge = prev[key_cols_rate +
                              ["rate_branch", "rate_klik_total"]].fillna(-1)

            merged = now_merge.merge(
                prev_merge,
                on=key_cols_rate,
                how="inner",
                suffixes=("_now", "_prev"),
            )

            if not merged.empty:
                merged["d_branch"] = (
                    merged["rate_branch_now"] - merged["rate_branch_prev"]).abs()
                merged["d_klik"] = (
                    merged["rate_klik_total_now"] - merged["rate_klik_total_prev"]).abs()

                threshold = 0.05
                changed = merged[(merged["d_branch"] > threshold)
                                 | (merged["d_klik"] > threshold)]
                if len(changed) > 0:
                    top = changed.sort_values(
                        ["d_branch", "d_klik"], ascending=False).head(3)
                    examples = []
                    for _, r in top.iterrows():
                        examples.append(
                            f"{r['product_name']} {r['min_term']}-{r['max_term']}{r['term_unit']} {r['amount_min']}-{r['amount_max']}"
                        )
                    warns.append(
                        f"spremenjene obrestne mere na obstoječih produktih (> {threshold}): {len(changed)} primerov; npr. {', '.join(examples)}"
                    )
    except Exception:
        pass

    return warns


def _latest_archive_for(csv_filename, today_str):
    stem = csv_filename.replace(".csv", "")
    pattern = os.path.join("archive", f"{stem}_*.csv")
    candidates = []
    for path in glob.glob(pattern):
        base = os.path.basename(path)
        if not base.startswith(stem + "_"):
            continue
        date_part = base[len(stem) + 1: -4]
        if date_part == today_str:
            continue
        candidates.append((date_part, path))
    if not candidates:
        return None
    candidates.sort(key=lambda x: x[0])
    return candidates[-1][1]


# 1) Seznam scraperjev z dejanskimi imeni datotek
SCRAPERS = [
    "ADDIKO scraper.py",
    "BKS scraper.py",
    "DBS scraper.py",
    "DH scraper.py",
    "GBKR scraper.py",
    "LON scraper.py",
    "NLB scraper.py",
    "OTP scraper.py",
    "INTESA scraper.py",
    "SPARKASSE scraper.py",
    "UNICREDIT scraper.py"
]

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SCRAPERS_DIR = os.path.join(BASE_DIR, "scrapers")

# Ensure all relative paths below (archive/, CSV files, etc.) resolve correctly
os.chdir(BASE_DIR)

print(f"INFO BASE_DIR={BASE_DIR}")
print(f"INFO CWD={os.getcwd()}")


def _resolve_existing_filename(name, base_dir, scrapers_dir):
    def _resolve_in_dir(dir_path: str):
        if not os.path.isdir(dir_path):
            return None
        target = os.path.join(dir_path, name)
        if os.path.exists(target):
            return target
        want = name.lower()
        for cand in os.listdir(dir_path):
            if cand.lower() == want:
                return os.path.join(dir_path, cand)
        return None

    # Prefer dedicated scrapers folder, fallback to BASE_DIR for backwards compatibility.
    return _resolve_in_dir(scrapers_dir) or _resolve_in_dir(base_dir)


# 2) CSV datoteke, ki jih želimo združiti
CSV_FILES = [
    "addiko_depoziti.csv",
    "bks_depoziti.csv",
    "dh_depoziti.csv",
    "dbs_depoziti.csv",
    "gbkr_depoziti.csv",
    "intesa_depoziti.csv",
    "lon_depoziti.csv",
    "nlb_depoziti.csv",
    "otp_depoziti.csv",
    "sparkasse_depoziti.csv",
    "unicredit_depoziti.csv"
]

# 3) Datum za arhiviranje
today = datetime.today().strftime("%Y-%m-%d")

# 4) Ustvarimo mapo archive, če še ne obstaja
if not os.path.exists("archive"):
    os.makedirs("archive")

print("Zaganjam vse scraperje...")

processes = []

subprocess_env = os.environ.copy()
subprocess_env["PYTHONUTF8"] = "1"
subprocess_env["PYTHONIOENCODING"] = "utf-8"

# 5) Poženemo vse scraperje istočasno
for scraper in SCRAPERS:
    resolved = _resolve_existing_filename(scraper, BASE_DIR, SCRAPERS_DIR)
    if resolved is None:
        print(f"WRN Opozorilo: Datoteka {scraper} ne obstaja!")
        continue

    p = subprocess.Popen(
        [sys.executable, resolved],
        cwd=BASE_DIR,
        env=subprocess_env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        shell=False,
    )
    processes.append((os.path.basename(resolved), p))

# 6) Počakamo, da vsi scraperji končajo
scraper_statuses = []
for scraper, p in processes:
    out, err = p.communicate()
    scraper_statuses.append((scraper, p.returncode, out, err))

    # Even on success, surface important source-selection messages (PDF vs fallback).
    try:
        otp_html_debug = os.environ.get("OTP_HTML_DEBUG", "").strip() == "1"
        otp_pdf_debug = os.environ.get("OTP_PDF_DEBUG", "").strip() == "1"
        bks_pdf_debug = os.environ.get("BKS_PDF_DEBUG", "").strip() == "1"
        if out and out.strip():
            for line in out.splitlines():
                s = line.strip()
                if not s:
                    continue
                if "[WARN]" in s or "[OK]" in s:
                    print(s)
                elif otp_html_debug and s.startswith("INFO OTP["):
                    print(s)
                elif otp_pdf_debug and s.startswith("INFO OTP["):
                    print(s)
                elif bks_pdf_debug and s.startswith("INFO BKS["):
                    print(s)
    except Exception:
        pass


def _fmt_mtime(path: str):
    try:
        ts = os.path.getmtime(path)
        return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return None


failed_scrapers = [s for s, code, _,
                   _ in scraper_statuses if code not in (0, None)]
if failed_scrapers:
    print("ERR Nekateri scraperji so koncali z napako:")
    for s, code, out, err in scraper_statuses:
        if code not in (0, None):
            print(f" - {s}: exit code={code}")
            if out and out.strip():
                print("   --- stdout ---")
                print(out.rstrip())
            if err and err.strip():
                print("   --- stderr ---")
                print(err.rstrip())
    sys.exit(1)

print("OK Vsi scraperji so koncali.")

# 7) Združimo CSV-je
dfs = []

print("Najdeni CSV-ji:")
for file in CSV_FILES:
    if os.path.exists(file):
        mt = _fmt_mtime(file)
        if mt:
            print(" -", file, f"(mtime={mt})")
        else:
            print(" -", file)
    else:
        print(" -", file, "(NE OBSTAJA)")
    csv_path = os.path.join(BASE_DIR, file)
    if os.path.exists(csv_path):
        df = pd.read_csv(csv_path, delimiter=";")
        schema_errs, schema_warns = _validate_schema(df, file)
        inv_errs, inv_warns = _validate_invariants(df, file)

        prev_path = _latest_archive_for(file, today)
        diff_warns = []
        if prev_path is not None and os.path.exists(prev_path):
            df_prev = pd.read_csv(prev_path, delimiter=";")
            diff_warns = _diff_metrics(df, df_prev, source_file=file)

        if schema_errs or inv_errs:
            print(f"ERR Validacija FAIL za {file}:")
            for msg in (schema_errs + inv_errs):
                print(f" - {msg}")
            sys.exit(1)

        all_warns = schema_warns + inv_warns + diff_warns
        if all_warns:
            print(f"WRN Validacija WARN za {file}:")
            for msg in all_warns:
                print(f" - {msg}")
        else:
            print(f"OK Validacija OK za {file}")

        df["source_file"] = file
        dfs.append(df)
    else:
        print(f"WRN CSV {file} ne obstaja in bo preskocen.")

# 8) Ustvarimo master CSV
if dfs:
    combined = pd.concat(dfs, ignore_index=True)
    combined.to_csv(os.path.join(BASE_DIR, "all_banks.csv"),
                    sep=";", index=False)
    print("OK all_banks.csv uspesno ustvarjen.")
else:
    print("WRN Ni CSV datotek za zdruziti.")
    sys.exit(1)

# 9) Arhiviranje master CSV-ja
archive_master = f"archive/all_banks_{today}.csv"
all_banks_path = os.path.join(BASE_DIR, "all_banks.csv")
if os.path.exists(all_banks_path):
    try:
        shutil.copy(all_banks_path, archive_master)
        print(f"OK Arhiviran master CSV -> {archive_master}")
    except PermissionError:
        print(
            f"ERR Ni mogoce zapisati v {archive_master} (datoteka je verjetno odprta v Excelu)")
        sys.exit(1)
    except Exception as e:
        print(f"ERR Napaka pri arhiviranju master CSV ({archive_master}): {e}")
        sys.exit(1)
else:
    print("ERR all_banks.csv ne obstaja, arhiviranje preskoceno")
    sys.exit(1)

# 10) Arhiviranje posameznih bank
for file in CSV_FILES:
    if os.path.exists(file):
        archive_file = f"archive/{file.replace('.csv', '')}_{today}.csv"
        try:
            shutil.copy(file, archive_file)
            print(f"OK Arhivirano -> {archive_file}")
        except PermissionError:
            print(
                f"ERR Ni mogoce zapisati v {archive_file} (datoteka je verjetno odprta v Excelu)")
            sys.exit(1)
        except Exception as e:
            print(f"ERR Napaka pri arhiviranju {file} ({archive_file}): {e}")
            sys.exit(1)

print("OK Dnevno arhiviranje zakljuceno.")
