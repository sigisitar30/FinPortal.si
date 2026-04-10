import json
import os
import sys
from datetime import datetime
from urllib.request import Request, urlopen


API_URL = "https://px.bsi.si/api/v1/sl/serije_slo/20_obrestne_mere/50_OBR_MERE_MFI_PG/i2_4_6as.px"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", ".."))
OUT_DIR = os.path.join(ROOT_DIR, "Podatki makro", "BS")
OUT_LATEST = os.path.join(OUT_DIR, "bs_mfi_obrestne_mere_posojila_latest.json")
OUT_LATEST_HH = os.path.join(
    OUT_DIR, "bs_mfi_obrestne_mere_posojila_gospodinjstva_latest.json")
ARCHIVE_DIR = os.path.join(OUT_DIR, "arhiv")


def _http_json(method: str, url: str, payload=None, timeout=30):
    data = None
    headers = {
        "Accept": "application/json",
        "User-Agent": "FinPortal.si scraper (contact: info@finportal.si)",
    }

    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = Request(url, data=data, headers=headers, method=method.upper())
    with urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8")
        return json.loads(raw)


def _get_meta():
    return _http_json("GET", API_URL)


def _build_query(meta, period: str):
    variables = {v.get("code"): v for v in (meta.get("variables") or [])}

    def sel_items(code: str, values):
        return {
            "code": code,
            "selection": {
                "filter": "item",
                "values": list(values),
            },
        }

    if "Datum" not in variables or "Frekvenca" not in variables or "Postavke" not in variables:
        raise ValueError(
            "PXWeb metadata missing one of required dimensions: Datum/Frekvenca/Postavke")

    date_vals = variables["Datum"].get("values") or []
    if period not in date_vals:
        raise ValueError(
            f"Requested period not available in metadata: {period}")

    freq_vals = variables["Frekvenca"].get("values") or []
    if not freq_vals:
        raise ValueError("PXWeb metadata has no Frekvenca values")

    post_vals = variables["Postavke"].get("values") or []
    if not post_vals:
        raise ValueError("PXWeb metadata has no Postavke values")

    return {
        "query": [
            sel_items("Datum", [period]),
            sel_items("Frekvenca", [freq_vals[0]]),
            sel_items("Postavke", post_vals),
        ],
        "response": {
            "format": "json-stat2"
        },
    }


def _parse_jsonstat2(doc):
    dim = (doc.get("dimension") or {})
    ids = doc.get("id") or []
    sizes = doc.get("size") or []
    values = doc.get("value") or []

    if not ids or not sizes:
        raise ValueError("Unexpected json-stat2 response: missing id/size")

    # Build per-dimension index->code/text
    dim_info = {}
    for code in ids:
        d = dim.get(code) or {}
        cat = d.get("category") or {}
        idx = cat.get("index") or {}
        labels = cat.get("label") or {}

        # idx is mapping code->position
        # create reverse mapping position->code
        pos_to_code = [None] * len(idx)
        for c, pos in idx.items():
            if isinstance(pos, int) and 0 <= pos < len(pos_to_code):
                pos_to_code[pos] = c

        dim_info[code] = {
            "pos_to_code": pos_to_code,
            "labels": labels,
        }

    # Calculate strides to decode flattened array
    strides = []
    for i in range(len(sizes)):
        stride = 1
        for s in sizes[i + 1:]:
            stride *= int(s)
        strides.append(stride)

    # We requested 1 period and 1 frekvenca, so we can focus on Postavke positions
    if "Postavke" not in ids:
        raise ValueError(
            "Unexpected json-stat2 response: missing Postavke dimension")

    post_i = ids.index("Postavke")
    post_size = int(sizes[post_i])
    post_stride = strides[post_i]

    post_pos_to_code = dim_info["Postavke"]["pos_to_code"]
    post_labels = dim_info["Postavke"]["labels"]

    rows = []
    for p in range(post_size):
        flat_index = p * post_stride
        v = values[flat_index] if flat_index < len(values) else None
        code = post_pos_to_code[p]
        text = post_labels.get(code, code)
        rows.append({
            "postavke_code": code,
            "postavke_text": text,
            "rate": v,
        })

    return rows


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    os.makedirs(ARCHIVE_DIR, exist_ok=True)

    meta = _get_meta()
    variables = {v.get("code"): v for v in (meta.get("variables") or [])}

    date_vals = (variables.get("Datum") or {}).get("values") or []
    if not date_vals:
        raise RuntimeError("No Datum values in metadata")

    latest_period = date_vals[-1]

    payload = _build_query(meta, latest_period)
    data = _http_json("POST", API_URL, payload=payload, timeout=60)

    rows = _parse_jsonstat2(data)

    hh_keep = {
        "Gospodinjstva, obstoječa stanovanjska posojila",
        "Gospodinjstva, obstoječa potrošniška posojila",
        "Gospodinjstva, obstoječa druga posojila",
        "Gospodinjstva, nova stanovanjska posojila",
        "Gospodinjstva, nova potrošniška posojila",
        "Gospodinjstva, nova druga posojila",
        "Gospodinjstva, okvirna, revolving in p. po kred. k.",
    }

    hh_rows = [r for r in rows if Stringify(r.get("postavke_text")) in hh_keep]

    out = {
        "dataset": "i2_4_6as.px",
        "title": meta.get("title"),
        "period": latest_period,
        "fetched_at": datetime.now().isoformat(timespec="seconds"),
        "source": "https://px.bsi.si/",
        "rows": rows,
    }

    with open(OUT_LATEST, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    out_hh = {
        "dataset": "i2_4_6as.px",
        "title": meta.get("title"),
        "period": latest_period,
        "fetched_at": out.get("fetched_at"),
        "source": "https://px.bsi.si/",
        "rows": hh_rows,
    }

    with open(OUT_LATEST_HH, "w", encoding="utf-8") as f:
        json.dump(out_hh, f, ensure_ascii=False, indent=2)

    stamp = datetime.today().strftime("%Y-%m-%d")
    out_archive = os.path.join(
        ARCHIVE_DIR, f"bs_mfi_obrestne_mere_posojila_{stamp}.json")
    try:
        with open(out_archive, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
    except PermissionError:
        pass

    out_archive_hh = os.path.join(
        ARCHIVE_DIR, f"bs_mfi_obrestne_mere_posojila_gospodinjstva_{stamp}.json")
    try:
        with open(out_archive_hh, "w", encoding="utf-8") as f:
            json.dump(out_hh, f, ensure_ascii=False, indent=2)
    except PermissionError:
        pass

    print(
        f"OK BS PXWeb fetched period={latest_period} rows={len(rows)} -> {OUT_LATEST}")
    print(
        f"OK BS PXWeb fetched period={latest_period} hh_rows={len(hh_rows)} -> {OUT_LATEST_HH}")


def Stringify(v):
    return "" if v is None else str(v)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"ERR BS scraper failed: {e}")
        sys.exit(1)
