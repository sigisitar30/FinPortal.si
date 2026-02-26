import fs from "node:fs/promises";
import path from "node:path";

function parseCsvLine(line, delimiter) {
  const out = [];
  let cur = "";
  let inQuotes = false;

  for (let i = 0; i < line.length; i++) {
    const ch = line[i];

    if (inQuotes) {
      if (ch === '"') {
        if (line[i + 1] === '"') {
          cur += '"';
          i++;
        } else {
          inQuotes = false;
        }
      } else {
        cur += ch;
      }
      continue;
    }

    if (ch === '"') {
      inQuotes = true;
      continue;
    }

    if (ch === delimiter) {
      out.push(cur);
      cur = "";
      continue;
    }

    cur += ch;
  }

  out.push(cur);
  return out;
}

function guessDelimiter(headerLine) {
  const commaCount = (headerLine.match(/,/g) || []).length;
  const semiCount = (headerLine.match(/;/g) || []).length;
  return semiCount > commaCount ? ";" : ",";
}

function parseCsv(text) {
  const lines = text
    .replace(/\r\n/g, "\n")
    .replace(/\r/g, "\n")
    .split("\n")
    .filter((l) => l.trim() !== "");

  if (lines.length === 0) return [];

  const delimiter = guessDelimiter(lines[0]);
  const header = parseCsvLine(lines[0], delimiter).map((h) => h.trim());
  const rows = [];

  for (let i = 1; i < lines.length; i++) {
    const values = parseCsvLine(lines[i], delimiter);
    const row = {};
    for (let j = 0; j < header.length; j++) {
      row[header[j]] = (values[j] ?? "").trim();
    }
    rows.push(row);
  }

  return rows;
}

function toNumberOrNull(value) {
  if (value === undefined || value === null) return null;
  const s = String(value).trim();
  if (s === "") return null;

  // Supports:
  // - 500000.0 (dot decimal)
  // - 1.75 (dot decimal)
  // - 1.000.000 (dot thousands)
  // - 1.000.000,50 (dot thousands + comma decimal)
  // - 1000,5 (comma decimal)
  let cleaned = s.replace(/\s+/g, "");
  const hasComma = cleaned.includes(",");
  const dotCount = (cleaned.match(/\./g) || []).length;

  if (hasComma) {
    // Assume comma is decimal separator, dots are thousand separators.
    cleaned = cleaned.replace(/\./g, "").replace(/,/g, ".");
  } else {
    // No comma: if we have multiple dots, treat them as thousand separators.
    if (dotCount >= 2) {
      cleaned = cleaned.replace(/\./g, "");
    }
  }

  const n = Number(cleaned);
  return Number.isFinite(n) ? n : null;
}

function normalizeCurrency(value) {
  const v = String(value ?? "EUR").trim().toUpperCase();
  return v === "" ? "EUR" : v;
}

function normalizeDate(value) {
  const v = String(value ?? "").trim();
  if (v === "") {
    return new Date().toISOString().slice(0, 10);
  }
  return v;
}

function slugify(value) {
  return String(value ?? "")
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

function requiredString(value, fieldName) {
  const v = String(value ?? "").trim();
  if (v === "") throw new Error(`Missing required field: ${fieldName}`);
  return v;
}

function buildDeposit(row) {
  const rawId = String(row.id ?? "").trim();
  const bank = requiredString(row.bank, "bank");

  const product_name = String(row.product_name ?? "Vezani depozit").trim() || "Vezani depozit";

  const rate_nominal = toNumberOrNull(row.rate_nominal);
  const term_months = toNumberOrNull(row.term_months);
  const min_amount = toNumberOrNull(row.min_amount);
  const max_amount = toNumberOrNull(row.max_amount);

  const label = rawId !== "" ? rawId : `${bank}:${product_name}`;

  if (rate_nominal === null) throw new Error(`Invalid rate_nominal for ${label}`);
  if (term_months === null) throw new Error(`Invalid term_months for ${label}`);
  if (min_amount === null) throw new Error(`Invalid min_amount for ${label}`);

  const stableId = rawId !== "" && /[a-zA-Z]/.test(rawId)
    ? rawId
    : `${slugify(bank)}-deposit-${term_months}m-${String(rate_nominal).replace(/\./g, "_")}-${String(min_amount)}`;

  return {
    id: stableId,
    bank,
    product_name,
    rate_nominal,
    term_months,
    term_unit: String(row.term_unit ?? "months").trim(),
    min_amount,
    max_amount,
    currency: normalizeCurrency(row.currency),
    url: String(row.url ?? "").trim(),
    last_updated: normalizeDate(row.last_updated),
    notes: String(row.notes ?? "").trim()
  };
}

function isAllBanksSchema(row) {
  return (
    Object.prototype.hasOwnProperty.call(row, "amount_min") ||
    Object.prototype.hasOwnProperty.call(row, "min_term") ||
    Object.prototype.hasOwnProperty.call(row, "rate_klik_total")
  );
}

function buildDepositsFromAllBanksRow(row) {
  const bank = requiredString(row.bank, "bank");
  const product_name = String(row.product_name ?? "Vezani depozit").trim() || "Vezani depozit";

  const rate_branch = toNumberOrNull(row.rate_branch ?? row.rate_nominal);
  const rate_special_bonus = toNumberOrNull(row.rate_klik_bonus);
  const rate_special = toNumberOrNull(row.rate_klik_total);

  const rate_nominal = rate_branch;
  if (rate_nominal === null) throw new Error(`Invalid rate_nominal for ${bank}:${product_name}`);

  const min_amount = toNumberOrNull(row.amount_min ?? row.min_amount);
  if (min_amount === null) throw new Error(`Invalid min_amount for ${bank}:${product_name}`);

  const max_amount = toNumberOrNull(row.amount_max ?? row.max_amount);

  const unit = String(row.term_unit ?? "months").trim().toLowerCase();
  const min_term = toNumberOrNull(row.min_term ?? row.term_months);
  const max_term = toNumberOrNull(row.max_term ?? row.term_months);

  if (min_term === null) throw new Error(`Invalid term for ${bank}:${product_name}`);

  // Frontend expects term_months. We expand ranges when unit=months.
  let termMonthsList = [];
  const daysMin = unit === "days" ? Math.round(min_term) : null;
  const daysMax = unit === "days" ? Math.round(max_term === null ? min_term : max_term) : null;
  if (unit === "months") {
    const a = Math.round(min_term);
    const b = max_term === null ? a : Math.round(max_term);
    const lo = Math.min(a, b);
    const hi = Math.max(a, b);
    const span = hi - lo;
    if (span <= 0) termMonthsList = [lo];
    else if (span <= 120) {
      for (let m = lo; m <= hi; m++) termMonthsList.push(m);
    } else {
      termMonthsList = [lo];
    }
  } else if (unit === "days") {
    const days = Math.round(min_term);
    const approxMonths = Math.max(1, Math.round(days / 30.4167));
    termMonthsList = [approxMonths];
  } else {
    termMonthsList = [Math.round(min_term)];
  }

  const currency = normalizeCurrency(row.amount_currency ?? row.currency);
  const url = String(row.url ?? "").trim();
  const last_updated = normalizeDate(row.last_updated);
  const notes = String(row.notes ?? "").trim();
  const rawId = String(row.id ?? "").trim();

  return termMonthsList.map((term_months) => {
    if (unit === "months" && term_months >= 12 && min_amount === 0) {
      console.warn("Suspicious min_amount=0 for long-term deposit", {
        bank,
        product_name,
        term_months,
        amount_min: row.amount_min,
        amount_max: row.amount_max,
        source_file: row.source_file,
        last_updated
      });
    }

    const stableId = rawId !== "" && /[a-zA-Z]/.test(rawId)
      ? `${rawId}-${term_months}m`
      : `${slugify(bank)}-deposit-${term_months}m-${String(rate_nominal).replace(/\./g, "_")}-${String(min_amount)}`;

    return {
      id: stableId,
      bank,
      product_name,
      rate_nominal,
      rate_special: Number.isFinite(rate_special) ? rate_special : null,
      rate_special_bonus: Number.isFinite(rate_special_bonus) ? rate_special_bonus : null,
      term_months,
      term_unit: unit,
      term_days_min: unit === "days" && Number.isFinite(daysMin) ? daysMin : null,
      term_days_max: unit === "days" && Number.isFinite(daysMax) ? daysMax : null,
      min_amount,
      max_amount,
      currency,
      url,
      last_updated,
      notes
    };
  });
}

async function main() {
  const args = process.argv.slice(2);
  const input = args[0];

  if (!input) {
    console.error("Usage: node scripts/generate-offers.mjs <csv_url_or_path> [output_path]");
    process.exit(1);
  }

  const outputPath = args[1] ? args[1] : path.resolve(process.cwd(), "offers.json");

  const csvText = input.startsWith("http://") || input.startsWith("https://")
    ? await (await fetch(input, { cache: "no-store" })).text()
    : await fs.readFile(path.resolve(process.cwd(), input), "utf-8");

  const rows = parseCsv(csvText);

  const depositsRaw = rows
    .filter((r) => String(r.bank ?? "").trim() !== "")
    .flatMap((r) => {
      if (isAllBanksSchema(r)) return buildDepositsFromAllBanksRow(r);
      return [buildDeposit(r)];
    });

  const usedIds = new Set();
  const deposits = depositsRaw.map((d) => {
    let id = d.id;
    let n = 2;
    while (usedIds.has(id)) {
      id = `${d.id}-${n}`;
      n++;
    }
    usedIds.add(id);
    return { ...d, id };
  });

  const json = {
    meta: {
      source: input,
      generated_at: new Date().toISOString(),
      currency: "EUR"
    },
    deposits
  };

  await fs.writeFile(outputPath, JSON.stringify(json, null, 2) + "\n", "utf-8");
  console.log(`Wrote ${deposits.length} deposits -> ${outputPath}`);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
