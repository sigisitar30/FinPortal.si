/* ============================================================
   FINPORTAL – SCRIPT.JS
   Tabs + 3 kalkulatorji (kredit, depozit, investicija)
   Slovenski format števil
============================================================ */

/* ============================
   FORMATIRANJE ŠTEVIL (sl-SI)
============================ */

function formatSI(num) {
    // Manual Slovenian formatting: dot for thousands, comma for decimals
    if (isNaN(num)) return "0,00 €";
    const formatted = num.toFixed(2);
    const parts = formatted.split('.');
    parts[0] = parts[0].replace(/\B(?=(\d{3})+(?!\d))/g, '.');
    return parts.join(',') + " €";
}

function escapeHtml(str) {
    const s = String(str ?? "");
    return s
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/\"/g, "&quot;")
        .replace(/'/g, "&#39;");
}

let depositTableSortKey = "rate";
let depositTableSortDir = "desc";

let fpLogoImgPromise = null;
async function loadFpLogoImg() {
    if (fpLogoImgPromise) return fpLogoImgPromise;
    fpLogoImgPromise = new Promise((resolve) => {
        const img = new Image();
        img.decoding = "async";
        img.src = "images/scit8.png";
        img.onload = () => resolve(img);
        img.onerror = () => resolve(null);
    });
    return fpLogoImgPromise;
}

function getShareConfig() {
    const path = String(window.location.pathname ?? "");
    let file = path.split("/").filter(Boolean).pop() || "";

    // Cloudflare Pages can serve pretty URLs (e.g., /depozitni-kalkulator) for a file
    // depozitni-kalkulator.html. Normalize so config lookup still works.
    if (!file) file = "index.html";
    if (!file.includes(".")) file = `${file}.html`;

    const cfgs = {
        "investicijski-kalkulator.html": {
            fields: ["inv-initial", "inv-monthly", "inv-years", "inv-return"],
            calcButtonId: "inv-calc-btn",
            primaryMetricId: "inv-earn",
            primaryMetricLabel: "Dobiček",
            chartCanvasId: "inv-chart",
            title: "Investicijski izračun"
        },
        "kreditni-kalkulator.html": {
            fields: [
                "loan-amount",
                "loan-years",
                "loan-rate-type",
                "loan-rate",
                "loan-euribor-tenor",
                "loan-margin",
                "loan-moratorium",
                "loan-intercalary-days",
                "loan-purpose",
                "loan-bank"
            ],
            calcButtonId: "loan-calc-btn",
            primaryMetricId: "loan-monthly",
            primaryMetricLabel: "Mesečni obrok",
            secondaryMetrics: [
                { id: "loan-total", label: "Skupaj za plačilo" },
                { id: "loan-interest", label: "Skupaj obresti" },
                { id: "loan-intercalary", label: "Interkalarne obresti" }
            ],
            chartCanvasId: "loan-amortization-chart",
            title: "Kreditni izračun"
        },
        "depozitni-kalkulator.html": {
            fields: ["interest-amount", "bank-select", "interest-months"],
            calcButtonId: "interest-calc-btn",
            primaryMetricId: "interest-total",
            primaryMetricLabel: "Končni znesek (neto)",
            secondaryMetrics: [
                { id: "interest-interest-gross", label: "Obresti (bruto)" },
                { id: "interest-tax", label: "Davek" },
                { id: "interest-interest", label: "Obresti (neto)" }
            ],
            title: "Depozitni izračun"
        },
        "izgubljene-obresti.html": {
            fields: [
                "lost-amount",
                "lost-time",
                "lost-unit",
                "lost-benchmark",
                "lost-rate",
                "lost-etf-return",
                "lost-etf-fee"
            ],
            calcButtonId: "lost-calc-btn",
            primaryMetricId: "lost-interest",
            primaryMetricLabel: "Zamujene obresti",
            chartCanvasId: "lost-compare-chart",
            title: "Izgubljene obresti"
        },
        "kreditna-sposobnost.html": {
            fields: [
                "cs-income",
                "cs-adults",
                "cs-children",
                "cs-existing",
                "cs-living-actual",
                "cs-rent",
                "cs-rate",
                "cs-dsti",
                "cs-min-adult",
                "cs-min-child",
                "cs-safety"
            ],
            calcButtonId: "cs-calc-btn",
            primaryMetricId: "cs-max-loan",
            primaryMetricLabel: "Ocena zneska kredita",
            secondaryMetrics: [
                { id: "cs-max-payment", label: "Največji mesečni obrok" },
                { id: "cs-limit-reason", label: "Omejitev" }
            ],
            title: "Kreditna sposobnost"
        },
        "eom-kalkulator.html": {
            fields: [
                "eom-amount",
                "eom-months",
                "eom-nominal-rate",
                "eom-upfront-percent",
                "eom-upfront-eur",
                "eom-monthly-fee"
            ],
            calcButtonId: "eom-calc-btn",
            primaryMetricId: "eom-apr",
            primaryMetricLabel: "EOM (letno)",
            title: "EOM izračun"
        },
        "menjalniski-kalkulator.html": {
            fields: [
                "fx-amount",
                "fx-from",
                "fx-to",
                "fx-spread",
                "fx-fee",
                "fx-manual-toggle",
                "fx-manual-rate"
            ],
            calcButtonId: "fx-calc-btn",
            primaryMetricId: "fx-result",
            primaryMetricLabel: "Prejmeš",
            title: "Menjalniški izračun"
        },
        "primerjava-depozitov.html": {
            fields: ["deposit-compare-amount", "deposit-compare-term", "deposit-compare-unit", "deposit-compare-special"],
            onApply: () => {
                if (typeof renderDepositTable === "function") renderDepositTable();
            },
            primaryMetricId: null,
            title: "Primerjava depozitov",
            tableContainerId: "deposit-table-container"
        }
    };

    return cfgs[file] ?? null;
}

function buildShareUrl(cfg) {
    const url = new URL(window.location.href);
    url.searchParams.set("fp_share", "1");

    (cfg.fields || []).forEach((id) => {
        const el = document.getElementById(id);
        if (!el) return;

        if (el.type === "checkbox") {
            url.searchParams.set(id, el.checked ? "1" : "0");
            return;
        }

        const v = String(el.value ?? "").trim();
        if (v === "") {
            url.searchParams.delete(id);
            return;
        }
        url.searchParams.set(id, v);
    });

    return url.toString();
}

function applyShareParams(cfg) {
    const url = new URL(window.location.href);
    if (!url.searchParams.has("fp_share")) return false;

    let changed = false;
    (cfg.fields || []).forEach((id) => {
        if (!url.searchParams.has(id)) return;
        const el = document.getElementById(id);
        if (!el) return;

        const raw = url.searchParams.get(id);
        if (el.type === "checkbox") {
            const next = raw === "1" || raw === "true";
            if (el.checked !== next) {
                el.checked = next;
                changed = true;
            }
            return;
        }

        if (String(el.value ?? "") !== raw) {
            el.value = raw;
            changed = true;
        }
    });

    return changed;
}

async function copyToClipboard(text) {
    try {
        if (navigator.clipboard && typeof navigator.clipboard.writeText === "function") {
            await navigator.clipboard.writeText(text);
            return true;
        }
    } catch {
        // ignore and fallback
    }

    try {
        const ta = document.createElement("textarea");
        ta.value = String(text ?? "");
        ta.setAttribute("readonly", "");
        ta.style.position = "fixed";
        ta.style.top = "-9999px";
        ta.style.left = "-9999px";
        ta.style.opacity = "0";
        document.body.appendChild(ta);
        ta.focus();
        ta.select();
        const ok = document.execCommand("copy");
        document.body.removeChild(ta);
        return !!ok;
    } catch {
        return false;
    }
}

function pressAnimate(el) {
    if (!el) return;
    try {
        if (typeof el.animate === "function") {
            el.animate(
                [
                    { transform: "scale(1)" },
                    { transform: "scale(0.98)" },
                    { transform: "scale(1)" },
                ],
                { duration: 140, easing: "ease-out" }
            );
            return;
        }
    } catch {
        // ignore
    }

    const prevTransition = el.style.transition;
    const prevTransform = el.style.transform;
    el.style.transition = "transform 140ms ease-out";
    el.style.transform = "scale(0.98)";
    setTimeout(() => {
        el.style.transform = "scale(1)";
        setTimeout(() => {
            el.style.transition = prevTransition;
            el.style.transform = prevTransform;
        }, 160);
    }, 60);
}

async function withTempButtonText(btn, nextText, fn, opts = {}) {
    if (!btn) return fn();

    const {
        successText = null,
        errorText = null,
        revertAfterMs = 1400,
        setBusy = false,
    } = opts;

    const prevText = btn.textContent;
    const prevDisabled = btn.disabled;
    const prevOpacity = btn.style.opacity;
    const prevCursor = btn.style.cursor;

    const setBusyUi = (busy) => {
        if (!setBusy) return;
        btn.disabled = busy ? true : prevDisabled;
        btn.style.opacity = busy ? "0.75" : prevOpacity;
        btn.style.cursor = busy ? "progress" : prevCursor;
    };

    try {
        pressAnimate(btn);
        if (nextText != null) btn.textContent = nextText;
        setBusyUi(true);

        const res = await fn();

        if (successText != null) btn.textContent = successText;
        if (successText != null) {
            setTimeout(() => {
                btn.textContent = prevText;
            }, revertAfterMs);
        }
        return res;
    } catch (e) {
        if (errorText != null) btn.textContent = errorText;
        if (errorText != null) {
            setTimeout(() => {
                btn.textContent = prevText;
            }, revertAfterMs);
        }
        throw e;
    } finally {
        setBusyUi(false);
        if (successText == null && errorText == null && nextText != null) {
            setTimeout(() => {
                btn.textContent = prevText;
            }, revertAfterMs);
        }
    }
}

function getPrimaryMetricText(cfg) {
    if (!cfg.primaryMetricId) return null;
    const el = document.getElementById(cfg.primaryMetricId);
    if (!el) return null;
    const t = String(el.textContent ?? "").trim();
    if (!t || t === "–" || t === "-") return null;
    return t;
}

function drawRoundedRect(ctx, x, y, w, h, r) {
    const radius = Math.max(0, Math.min(r, w / 2, h / 2));
    ctx.beginPath();
    ctx.moveTo(x + radius, y);
    ctx.arcTo(x + w, y, x + w, y + h, radius);
    ctx.arcTo(x + w, y + h, x, y + h, radius);
    ctx.arcTo(x, y + h, x, y, radius);
    ctx.arcTo(x, y, x + w, y, radius);
    ctx.closePath();
}

function getDepositCompareCaption() {
    const amountEl = document.getElementById("deposit-compare-amount");
    const termEl = document.getElementById("deposit-compare-term");
    const unitEl = document.getElementById("deposit-compare-unit");
    const specialEl = document.getElementById("deposit-compare-special");

    const amount = amountEl ? String(amountEl.value ?? "").trim() : "";
    const term = termEl ? String(termEl.value ?? "").trim() : "";
    const unit = unitEl ? String(unitEl.value ?? "months") : "months";
    const special = !!specialEl?.checked;

    const termLabel = term
        ? (unit === "days" ? `${term} dni` : `${term} mesecev`)
        : "";

    const left = amount ? `Znesek: ${amount} €` : "";
    const mid = termLabel ? `Doba: ${termLabel}` : "";
    const right = special ? "Akcijske: DA" : "Akcijske: NE";

    return [left, mid, right].filter(Boolean).join("  •  ");
}

async function buildShareTableImageDataUrl(cfg) {
    const containerId = cfg.tableContainerId;
    if (!containerId) return null;

    const container = document.getElementById(containerId);
    const table = container ? container.querySelector("table") : null;
    if (!table) return null;

    const getCleanCellText = (cell) => {
        if (!cell) return "";
        const clone = cell.cloneNode(true);
        if (clone && typeof clone.querySelectorAll === "function") {
            clone
                .querySelectorAll(".fp-help, .fp-help__icon, .fp-help__tooltip")
                .forEach((n) => n.remove());
        }
        return String(clone.textContent ?? "").replace(/\s+/g, " ").trim();
    };

    const rows = Array.from(table.querySelectorAll("tr")).map((tr) => {
        const cells = Array.from(tr.querySelectorAll("th,td")).map((cell) => getCleanCellText(cell));
        return cells;
    }).filter((r) => r.length);

    if (!rows.length) return null;

    const header = rows[0];
    const body = rows.slice(1);

    const W = 1200;
    const pad = 56;
    const titleH = 70;
    const captionH = 34;
    const topPad = 44;
    const headerRowH = 52;
    const rowH = 46;
    const footerH = 120;

    const canvas = document.createElement("canvas");
    const ctx = canvas.getContext("2d");
    if (!ctx) return null;

    const colCount = header.length;
    const colPadX = 16;

    const fitText = (text, maxW) => {
        const t = String(text ?? "");
        if (!t) return "";
        if (ctx.measureText(t).width <= maxW) return t;
        const ell = "…";
        if (ctx.measureText(ell).width > maxW) return "";
        let lo = 0;
        let hi = t.length;
        while (lo < hi) {
            const mid = Math.ceil((lo + hi) / 2);
            const cand = t.slice(0, mid) + ell;
            if (ctx.measureText(cand).width <= maxW) lo = mid;
            else hi = mid - 1;
        }
        return t.slice(0, lo) + ell;
    };

    const isNumericLike = (text) => {
        const s = String(text ?? "").trim();
        if (!s) return false;
        if (/%|€/.test(s)) return true;
        // digits with optional thousands/decimals (SI format)
        return /^-?[0-9.]+(,[0-9]+)?$/.test(s);
    };

    ctx.font = "600 20px Inter, system-ui, -apple-system, Segoe UI, Roboto, Arial";
    const colWidths = new Array(colCount).fill(0).map((_, i) => {
        const maxW = Math.max(
            ...[header[i], ...body.map((r) => r[i] ?? "")].map((t) => ctx.measureText(String(t ?? "")).width)
        );
        return Math.ceil(maxW + colPadX * 2);
    });

    const maxTableW = W - pad * 2;
    const sumW = colWidths.reduce((a, b) => a + b, 0);
    const scale = sumW > maxTableW ? (maxTableW / sumW) : 1;
    const scaledColWidths = colWidths.map((w) => Math.floor(w * scale));
    const tableW = scaledColWidths.reduce((a, b) => a + b, 0);

    const tableH = headerRowH + body.length * rowH;
    const H = Math.max(630, topPad + titleH + captionH + 26 + tableH + footerH);

    canvas.width = W;
    canvas.height = H;

    ctx.fillStyle = "#ffffff";
    ctx.fillRect(0, 0, W, H);

    const title = cfg.title || "Primerjava";
    const caption = getDepositCompareCaption();

    ctx.fillStyle = "#0B6B3A";
    ctx.font = "700 44px Inter, system-ui, -apple-system, Segoe UI, Roboto, Arial";
    ctx.fillText(title, pad, topPad + 44);

    if (caption) {
        ctx.fillStyle = "#374151";
        ctx.font = "500 22px Inter, system-ui, -apple-system, Segoe UI, Roboto, Arial";
        ctx.fillText(caption, pad, topPad + 44 + 44);
    }

    const tableX = pad;
    const tableY = topPad + titleH + captionH;

    ctx.fillStyle = "#f9fafb";
    ctx.strokeStyle = "#e5e7eb";
    ctx.lineWidth = 2;
    drawRoundedRect(ctx, tableX, tableY, tableW, tableH, 18);
    ctx.fill();
    ctx.stroke();

    let x = tableX;
    let y = tableY;

    ctx.save();
    ctx.beginPath();
    drawRoundedRect(ctx, tableX, tableY, tableW, tableH, 18);
    ctx.clip();

    ctx.fillStyle = "#111827";
    ctx.font = "700 18px Inter, system-ui, -apple-system, Segoe UI, Roboto, Arial";
    ctx.textBaseline = "alphabetic";
    header.forEach((text, i) => {
        const w = scaledColWidths[i];
        const maxW = Math.max(0, w - colPadX * 2);
        const t = fitText(text, maxW);
        ctx.textAlign = "left";
        ctx.fillText(t, x + colPadX, y + 34);
        x += w;
    });

    ctx.strokeStyle = "#e5e7eb";
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(tableX, y + headerRowH);
    ctx.lineTo(tableX + tableW, y + headerRowH);
    ctx.stroke();

    y += headerRowH;
    ctx.font = "600 18px Inter, system-ui, -apple-system, Segoe UI, Roboto, Arial";
    body.forEach((row, ri) => {
        if (ri % 2 === 0) {
            ctx.fillStyle = "#ffffff";
            ctx.fillRect(tableX, y, tableW, rowH);
        }

        ctx.fillStyle = "#111827";
        let cx = tableX;
        row.forEach((text, i) => {
            const w = scaledColWidths[i];
            const raw = String(text ?? "");
            const maxW = Math.max(0, w - colPadX * 2);
            const t = fitText(raw, maxW);
            if (isNumericLike(raw)) {
                ctx.textAlign = "right";
                ctx.fillText(t, cx + w - colPadX, y + 30);
            } else {
                ctx.textAlign = "left";
                ctx.fillText(t, cx + colPadX, y + 30);
            }
            cx += w;
        });

        ctx.strokeStyle = "#eef2f7";
        ctx.beginPath();
        ctx.moveTo(tableX, y + rowH);
        ctx.lineTo(tableX + tableW, y + rowH);
        ctx.stroke();

        y += rowH;
    });

    ctx.restore();

    const logo = await loadFpLogoImg();
    const brandLogoY = H - 116;
    const logoSize = 56;
    if (logo) ctx.drawImage(logo, pad, brandLogoY, logoSize, logoSize);
    ctx.fillStyle = "#111827";
    ctx.font = "800 26px Inter, system-ui, -apple-system, Segoe UI, Roboto, Arial";
    ctx.fillText("FinPortal.si", pad + logoSize + 14, brandLogoY + 4);

    ctx.fillStyle = "#374151";
    ctx.font = "500 20px Inter, system-ui, -apple-system, Segoe UI, Roboto, Arial";
    ctx.fillText("Izračunaj tudi ti na finportal.si", pad + logoSize + 14, brandLogoY + 34);

    return canvas.toDataURL("image/png");
}

async function buildShareImageDataUrl(cfg) {
    if (cfg && cfg.tableContainerId) {
        const t = await buildShareTableImageDataUrl(cfg);
        if (t) return t;
    }

    const W = 1200;
    const H = 630;

    const canvas = document.createElement("canvas");
    canvas.width = W;
    canvas.height = H;
    const ctx = canvas.getContext("2d");
    if (!ctx) return null;

    ctx.fillStyle = "#ffffff";
    ctx.fillRect(0, 0, W, H);

    const pad = 64;

    const logo = await loadFpLogoImg();

    const title = cfg.title || "Izračun";
    const metricLabel = cfg.primaryMetricLabel || "Rezultat";
    const metricValue = getPrimaryMetricText(cfg) || "";

    const cleanLabelText = (t) => {
        return String(t ?? "")
            .replace(/\?/g, "")
            .replace(/\*/g, "")
            .replace(/\s+/g, " ")
            .trim();
    };

    const getTextValue = (id) => {
        const el = document.getElementById(id);
        if (!el) return null;
        const t = String(el.textContent ?? "").trim();
        if (!t || t === "–" || t === "-") return null;
        return t;
    };

    const getControlValue = (id) => {
        const el = document.getElementById(id);
        if (!el) return null;

        if (el.type === "checkbox") {
            return el.checked ? "Da" : "Ne";
        }

        if (el.tagName === "SELECT") {
            const opt = el.options && el.selectedIndex >= 0 ? el.options[el.selectedIndex] : null;
            const t = String(opt ? opt.textContent : el.value ?? "").trim();
            return t || null;
        }

        const v = String(el.value ?? "").trim();
        return v || null;
    };

    const getControlLabel = (id) => {
        const el = document.getElementById(id);
        if (!el) return null;

        const forLabel = document.querySelector(`label[for="${CSS.escape(id)}"]`);
        if (forLabel) {
            const clone = forLabel.cloneNode(true);
            if (clone && typeof clone.querySelectorAll === "function") {
                clone
                    .querySelectorAll(".fp-help, .fp-help__icon, .fp-help__tooltip")
                    .forEach((n) => n.remove());
            }
            const t = cleanLabelText(clone.textContent ?? "");
            return t || null;
        }

        const parent = el.parentElement;
        if (parent) {
            const label = parent.querySelector("label");
            if (label) {
                const clone = label.cloneNode(true);
                if (clone && typeof clone.querySelectorAll === "function") {
                    clone
                        .querySelectorAll(".fp-help, .fp-help__icon, .fp-help__tooltip")
                        .forEach((n) => n.remove());
                }
                const t = cleanLabelText(clone.textContent ?? "");
                return t || null;
            }
        }

        return cleanLabelText(id);
    };

    const fitText = (text, maxWidth) => {
        const raw = String(text ?? "");
        if (!raw) return "";
        if (ctx.measureText(raw).width <= maxWidth) return raw;
        const ell = "…";
        let lo = 0;
        let hi = raw.length;
        while (lo < hi) {
            const mid = Math.ceil((lo + hi) / 2);
            const s = raw.slice(0, mid) + ell;
            if (ctx.measureText(s).width <= maxWidth) lo = mid;
            else hi = mid - 1;
        }
        return raw.slice(0, Math.max(0, lo)) + ell;
    };

    ctx.textBaseline = "top";

    ctx.fillStyle = "#0B6B3A";
    ctx.font = "700 44px Inter, system-ui, -apple-system, Segoe UI, Roboto, Arial";
    ctx.fillText(title, pad, 72);

    ctx.fillStyle = "#111827";
    ctx.font = "600 30px Inter, system-ui, -apple-system, Segoe UI, Roboto, Arial";
    ctx.fillText(metricLabel, pad, 140);

    ctx.fillStyle = "#0B6B3A";
    ctx.font = "800 64px Inter, system-ui, -apple-system, Segoe UI, Roboto, Arial";
    ctx.fillText(metricValue || "–", pad, 190);

    const chartId = cfg.chartCanvasId;
    if (chartId) {
        const chartCanvas = document.getElementById(chartId);
        if (chartCanvas && typeof chartCanvas.getContext === "function") {
            const chartW = 520;
            const chartH = 300;
            const chartX = W - pad - chartW;
            const chartY = 120;

            ctx.fillStyle = "#f9fafb";
            ctx.strokeStyle = "#e5e7eb";
            ctx.lineWidth = 2;
            drawRoundedRect(ctx, chartX, chartY, chartW, chartH, 24);
            ctx.fill();
            ctx.stroke();

            try {
                ctx.drawImage(chartCanvas, chartX + 16, chartY + 16, chartW - 32, chartH - 32);
            } catch {
                // ignore
            }
        }
    }

    const footerTop = H - 140;
    const leftX = pad;
    const leftW = (chartId ? (W - pad - (520 + pad)) : (W - pad - pad));
    const cardY = 290;
    const cardH = footerTop - cardY - 16;

    if (cardH > 80) {
        ctx.fillStyle = "#f9fafb";
        ctx.strokeStyle = "#e5e7eb";
        ctx.lineWidth = 2;
        drawRoundedRect(ctx, leftX, cardY, leftW, cardH, 24);
        ctx.fill();
        ctx.stroke();

        const innerPad = 24;
        const colX = leftX + innerPad;
        const colW = leftW - innerPad * 2;
        let cy = cardY + innerPad;

        ctx.textAlign = "left";
        ctx.fillStyle = "#111827";
        ctx.font = "700 22px Inter, system-ui, -apple-system, Segoe UI, Roboto, Arial";
        ctx.fillText("Vnos", colX, cy);
        cy += 34;

        ctx.fillStyle = "#374151";
        ctx.font = "500 18px Inter, system-ui, -apple-system, Segoe UI, Roboto, Arial";

        const inputLines = [];
        (cfg.fields || []).forEach((id) => {
            const val = getControlValue(id);
            if (!val) return;
            const label = getControlLabel(id);
            if (!label) return;
            inputLines.push({ label, value: val });
        });

        const maxInputLines = 6;
        const shownInputs = inputLines.slice(0, maxInputLines);
        const labelMaxW = Math.floor(colW * 0.62);
        const valueMaxW = colW - labelMaxW;
        shownInputs.forEach((it) => {
            if (cy + 24 > footerTop - 16) return;
            const l = fitText(String(it.label).replace(/\s*\(.*?\)\s*$/, "").replace(/\s*\*\s*$/, ""), labelMaxW);
            const v = fitText(it.value, valueMaxW);
            ctx.fillText(l, colX, cy);
            ctx.textAlign = "right";
            ctx.fillText(v, colX + colW, cy);
            ctx.textAlign = "left";
            cy += 24;
        });

        if (inputLines.length > shownInputs.length && cy + 24 <= footerTop - 16) {
            ctx.fillStyle = "#6b7280";
            ctx.fillText("…", colX, cy);
            cy += 24;
            ctx.fillStyle = "#374151";
        }

        const resultLines = [];
        (cfg.secondaryMetrics || []).forEach((m) => {
            if (!m || !m.id) return;
            const val = getTextValue(m.id);
            if (!val) return;
            resultLines.push({ label: m.label || m.id, value: val });
        });

        if (resultLines.length) {
            cy += 16;
            ctx.fillStyle = "#374151";
            ctx.font = "500 18px Inter, system-ui, -apple-system, Segoe UI, Roboto, Arial";

            const maxResultLines = 4;
            resultLines.slice(0, maxResultLines).forEach((it) => {
                if (cy + 24 > footerTop - 16) return;
                const l = fitText(it.label, labelMaxW);
                const v = fitText(it.value, valueMaxW);
                ctx.fillText(l, colX, cy);
                ctx.textAlign = "right";
                ctx.fillText(v, colX + colW, cy);
                ctx.textAlign = "left";
                cy += 24;
            });
        }

        ctx.textAlign = "left";
    }

    const brandLogoY = H - 116;
    const logoSize = 56;
    if (logo) ctx.drawImage(logo, pad, brandLogoY, logoSize, logoSize);
    ctx.fillStyle = "#111827";
    ctx.font = "800 26px Inter, system-ui, -apple-system, Segoe UI, Roboto, Arial";
    ctx.fillText("FinPortal.si", pad + logoSize + 14, brandLogoY + 4);

    ctx.fillStyle = "#374151";
    ctx.font = "500 20px Inter, system-ui, -apple-system, Segoe UI, Roboto, Arial";
    ctx.fillText("Izračunaj tudi ti na finportal.si", pad + logoSize + 14, brandLogoY + 34);

    return canvas.toDataURL("image/png");
}

async function downloadDataUrl(filename, dataUrl) {
    const a = document.createElement("a");
    a.href = dataUrl;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
}

function initShareUi() {
    const cfg = getShareConfig();
    if (!cfg) return;

    const applied = applyShareParams(cfg);

    const applyAndCalc = () => {
        if (typeof cfg.onApply === "function") {
            cfg.onApply();
            return;
        }

        const btn = cfg.calcButtonId ? document.getElementById(cfg.calcButtonId) : null;
        if (btn) {
            btn.click();
            return;
        }
    };

    if (applied) {
        setTimeout(applyAndCalc, 0);
    }

    const shareX = document.getElementById("fp-share-x");
    const shareFb = document.getElementById("fp-share-fb");
    const shareCopy = document.getElementById("fp-share-copy");
    const shareImg = document.getElementById("fp-share-img");

    const getShareText = () => {
        const metric = getPrimaryMetricText(cfg);
        if (metric) return `Moj izračun na FinPortal.si: ${cfg.primaryMetricLabel || "Rezultat"} ${metric}`;
        return `Moj izračun na FinPortal.si`;
    };

    const openPopup = (url) => {
        window.open(url, "_blank", "noopener,noreferrer");
    };

    if (shareX) {
        shareX.addEventListener("click", () => {
            pressAnimate(shareX);
            fpTrack("share_click", {
                method: "x",
                calculator: cfg.id || undefined,
            });
            const shareUrl = buildShareUrl(cfg);
            const intent = new URL("https://twitter.com/intent/tweet");
            intent.searchParams.set("text", getShareText());
            intent.searchParams.set("url", shareUrl);
            openPopup(intent.toString());
        });
    }

    if (shareFb) {
        shareFb.addEventListener("click", () => {
            pressAnimate(shareFb);
            fpTrack("share_click", {
                method: "facebook",
                calculator: cfg.id || undefined,
            });
            const shareUrl = buildShareUrl(cfg);
            const intent = new URL("https://www.facebook.com/sharer/sharer.php");
            intent.searchParams.set("u", shareUrl);
            openPopup(intent.toString());
        });
    }

    if (shareCopy) {
        shareCopy.addEventListener("click", async () => {
            const shareUrl = buildShareUrl(cfg);
            fpTrack("share_click", {
                method: "copy",
                calculator: cfg.id || undefined,
            });
            await withTempButtonText(
                shareCopy,
                null,
                async () => {
                    const ok = await copyToClipboard(shareUrl);
                    if (!ok) {
                        await withTempButtonText(shareCopy, null, async () => { }, {
                            errorText: "Ni uspelo",
                            revertAfterMs: 1600,
                        });
                    }
                    return ok;
                },
                {
                    successText: "Kopirano!",
                    revertAfterMs: 1400,
                }
            );
        });
    }

    if (shareImg) {
        shareImg.addEventListener("click", async () => {
            const shareUrl = buildShareUrl(cfg);
            fpTrack("share_click", {
                method: "image",
                calculator: cfg.id || undefined,
            });
            await withTempButtonText(
                shareImg,
                "Pripravljam...",
                async () => {
                    const dataUrl = await buildShareImageDataUrl(cfg);
                    if (!dataUrl) return false;
                    const file = (cfg.title || "izracun").toLowerCase().replace(/\s+/g, "-");
                    await downloadDataUrl(`${file}.png`, dataUrl);
                    await copyToClipboard(shareUrl);
                    return true;
                },
                {
                    successText: "Preneseno!",
                    revertAfterMs: 1400,
                    setBusy: true,
                }
            );
        });
    }
}

function syncDepositCompareTermBounds() {
    const termInput = document.getElementById("deposit-compare-term");
    const unitSelect = document.getElementById("deposit-compare-unit");
    if (!termInput || !unitSelect) return;

    const unit = String(unitSelect.value ?? "months");
    const max = unit === "days" ? 365 : 360;
    termInput.max = String(max);

    const v = Number(termInput.value);
    if (Number.isFinite(v) && v > max) {
        termInput.value = String(max);
    }
}

function getFxFlagSvg(currency) {
    const c = String(currency ?? "").trim().toUpperCase();
    // Simple inline SVGs (stylized flags) authored in-house; no external assets.
    const wrap = (inner) => `
        <svg width="20" height="14" viewBox="0 0 20 14" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
            ${inner}
            <rect x="0.5" y="0.5" width="19" height="13" rx="2" fill="none" stroke="#000000" stroke-width="0.5"/>
        </svg>
    `.trim();

    const triH = (a, b, d) => wrap(`
        <rect x="0" y="0" width="20" height="4.6667" fill="${a}"/>
        <rect x="0" y="4.6667" width="20" height="4.6667" fill="${b}"/>
        <rect x="0" y="9.3334" width="20" height="4.6666" fill="${d}"/>
    `);

    const triV = (a, b, d) => wrap(`
        <rect x="0" y="0" width="6.6667" height="14" fill="${a}"/>
        <rect x="6.6667" y="0" width="6.6666" height="14" fill="${b}"/>
        <rect x="13.3333" y="0" width="6.6667" height="14" fill="${d}"/>
    `);

    switch (c) {
        case "EUR":
            return wrap(`
                <rect x="0" y="0" width="20" height="14" rx="2" fill="#1d4ed8"/>
                <circle cx="10" cy="7" r="3.2" fill="none" stroke="#fbbf24" stroke-width="1.2" stroke-dasharray="0.1 2.4" stroke-linecap="round"/>
            `);
        case "USD":
            return wrap(`
                <rect x="0" y="0" width="20" height="14" rx="2" fill="#ffffff"/>
                <rect x="0" y="0" width="20" height="2" fill="#dc2626"/>
                <rect x="0" y="4" width="20" height="2" fill="#dc2626"/>
                <rect x="0" y="8" width="20" height="2" fill="#dc2626"/>
                <rect x="0" y="12" width="20" height="2" fill="#dc2626"/>
                <rect x="0" y="0" width="8.5" height="7" fill="#1e3a8a"/>
            `);
        case "CHF":
            return wrap(`
                <rect x="0" y="0" width="20" height="14" rx="2" fill="#dc2626"/>
                <rect x="8.5" y="3" width="3" height="8" fill="#ffffff"/>
                <rect x="6" y="5.5" width="8" height="3" fill="#ffffff"/>
            `);
        case "GBP":
            return wrap(`
                <rect x="0" y="0" width="20" height="14" rx="2" fill="#1e3a8a"/>
                <rect x="9" y="0" width="2" height="14" fill="#ffffff"/>
                <rect x="0" y="6" width="20" height="2" fill="#ffffff"/>
                <rect x="9.3" y="0" width="1.4" height="14" fill="#dc2626"/>
                <rect x="0" y="6.3" width="20" height="1.4" fill="#dc2626"/>
            `);
        case "JPY":
            return wrap(`
                <rect x="0" y="0" width="20" height="14" rx="2" fill="#ffffff"/>
                <circle cx="10" cy="7" r="3.2" fill="#dc2626"/>
            `);
        case "SEK":
            return wrap(`
                <rect x="0" y="0" width="20" height="14" rx="2" fill="#1d4ed8"/>
                <rect x="6" y="0" width="2.5" height="14" fill="#fbbf24"/>
                <rect x="0" y="5.5" width="20" height="2.5" fill="#fbbf24"/>
            `);
        case "NOK":
            return wrap(`
                <rect x="0" y="0" width="20" height="14" rx="2" fill="#dc2626"/>
                <rect x="6" y="0" width="3" height="14" fill="#ffffff"/>
                <rect x="0" y="5.5" width="20" height="3" fill="#ffffff"/>
                <rect x="6.6" y="0" width="1.8" height="14" fill="#1e3a8a"/>
                <rect x="0" y="6.1" width="20" height="1.8" fill="#1e3a8a"/>
            `);
        case "DKK":
            return wrap(`
                <rect x="0" y="0" width="20" height="14" rx="2" fill="#dc2626"/>
                <rect x="6" y="0" width="2.5" height="14" fill="#ffffff"/>
                <rect x="0" y="5.5" width="20" height="2.5" fill="#ffffff"/>
            `);
        case "PLN":
            return wrap(`
                <rect x="0" y="0" width="20" height="7" rx="2" fill="#ffffff"/>
                <rect x="0" y="7" width="20" height="7" rx="0" fill="#dc2626"/>
            `);
        case "HUF":
            return triH("#dc2626", "#ffffff", "#16a34a");
        case "CZK":
            return wrap(`
                <rect x="0" y="0" width="20" height="7" rx="2" fill="#ffffff"/>
                <rect x="0" y="7" width="20" height="7" fill="#dc2626"/>
                <polygon points="0,0 9,7 0,14" fill="#1e3a8a"/>
            `);
        default:
            return wrap(`<rect x="0" y="0" width="20" height="14" rx="2" fill="#9ca3af"/>`);
    }
}

function initFxCurrencyDropdown(selectId, mountId) {
    const select = document.getElementById(selectId);
    const mount = document.getElementById(mountId);
    if (!select || !mount) return;

    const options = Array.from(select.querySelectorAll("option")).map(opt => ({
        value: String(opt.value ?? "").trim().toUpperCase(),
        label: String(opt.textContent ?? "").trim()
    })).filter(o => o.value);

    const wrapper = document.createElement("div");
    wrapper.className = "relative";

    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "input w-full flex items-center justify-between gap-3";

    const left = document.createElement("div");
    left.className = "flex items-center gap-2";

    const flag = document.createElement("span");
    flag.className = "inline-flex";

    const text = document.createElement("span");
    text.className = "text-sm font-medium text-gray-900";

    left.appendChild(flag);
    left.appendChild(text);

    const chevron = document.createElement("span");
    chevron.className = "text-gray-500";
    chevron.textContent = "▾";

    btn.appendChild(left);
    btn.appendChild(chevron);

    const menu = document.createElement("div");
    menu.className = "absolute z-20 mt-2 w-full bg-white border border-gray-200 rounded-xl shadow-lg overflow-hidden hidden";

    const renderSelected = () => {
        const val = String(select.value ?? "").trim().toUpperCase();
        const opt = options.find(o => o.value === val) || options[0];
        flag.innerHTML = getFxFlagSvg(opt.value);
        text.textContent = opt.value;
    };

    const closeMenu = () => menu.classList.add("hidden");
    const openMenu = () => menu.classList.remove("hidden");

    btn.addEventListener("click", () => {
        if (menu.classList.contains("hidden")) openMenu();
        else closeMenu();
    });

    options.forEach(o => {
        const item = document.createElement("button");
        item.type = "button";
        item.className = "w-full px-3 py-2 text-left hover:bg-gray-50 flex items-center gap-2";
        item.innerHTML = `${getFxFlagSvg(o.value)}<span class="text-sm font-medium text-gray-900">${o.value}</span>`;
        item.addEventListener("click", () => {
            select.value = o.value;
            select.dispatchEvent(new Event("change", { bubbles: true }));
            renderSelected();
            closeMenu();
        });
        menu.appendChild(item);
    });

    document.addEventListener("click", (e) => {
        if (!wrapper.contains(e.target)) closeMenu();
    });

    wrapper.appendChild(btn);
    wrapper.appendChild(menu);
    mount.innerHTML = "";
    mount.appendChild(wrapper);

    renderSelected();
}

function formatMoney(amount, currency) {
    const n = Number(amount);
    const c = String(currency ?? "").trim().toUpperCase();
    if (!Number.isFinite(n)) return "–";
    if (c === "EUR" || c === "") return formatSI(n);
    const text = n.toLocaleString("sl-SI", { minimumFractionDigits: 2, maximumFractionDigits: 2, useGrouping: true });
    return `${text} ${c}`;
}

function formatSIWholeEuro(num) {
    if (!Number.isFinite(num)) return "—";
    const whole = Math.round(num);
    return `${String(whole).replace(/\B(?=(\d{3})+(?!\d))/g, '.')} €`;
}

function formatPercentSI(num) {
    const n = Number(num);
    if (!Number.isFinite(n)) return "—";
    return `${n.toFixed(2).replace(".", ",")}%`;
}

function enableGa4Analytics() {
    const measurementId = "G-1G82TV8KFZ";
    if (window.__fpGa4Enabled) return;
    window.__fpGa4Enabled = true;

    window.dataLayer = window.dataLayer || [];
    window.gtag = window.gtag || function () { window.dataLayer.push(arguments); };
    window.gtag('js', new Date());
    window.gtag('config', measurementId);

    const existing = document.querySelector(`script[src="https://www.googletagmanager.com/gtag/js?id=${measurementId}"]`);
    if (existing) return;

    const s = document.createElement('script');
    s.async = true;
    s.src = `https://www.googletagmanager.com/gtag/js?id=${measurementId}`;
    document.head.appendChild(s);
}

function disableGa4Analytics() {
    window.__fpGa4Enabled = false;
    if (typeof window.gtag === 'function') {
        try {
            window.gtag('consent', 'update', { analytics_storage: 'denied' });
        } catch (e) { }
    }
}

function fpHasAnalyticsConsent() {
    return document?.documentElement?.dataset?.cookieConsent === "accepted";
}

function fpTrack(eventName, params, opts) {
    if (!fpHasAnalyticsConsent()) return;
    if (!window.__fpGa4Enabled) return;
    if (typeof window.gtag !== "function") return;

    try {
        const p = params && typeof params === "object" ? params : {};
        const o = opts && typeof opts === "object" ? opts : {};
        window.gtag("event", eventName, { ...p, ...o });
    } catch (e) { }
}

function initCookieBanner() {
    const key = "finportal_cookie_consent";
    let existing = null;
    try { existing = localStorage.getItem(key); } catch (e) { }

    const ensureBanner = () => {
        let banner = document.getElementById("cookie-banner");
        if (banner) return banner;

        banner = document.createElement("div");
        banner.id = "cookie-banner";
        banner.className = "hidden";
        banner.style.position = "fixed";
        banner.style.left = "0";
        banner.style.right = "0";
        banner.style.bottom = "0";
        banner.style.zIndex = "9998";

        banner.innerHTML = `
            <div style="max-width: 80rem; margin: 0 auto; padding: 0 1.5rem 1.5rem;">
                <div style="background: #FFFBEB; border: 1px solid #FDE68A; border-radius: 1rem; box-shadow: 0 10px 20px rgba(0,0,0,0.12); padding: 1rem; display: flex; flex-direction: column; gap: 0.75rem;">
                    <div style="font-size: 0.875rem; color: #78350F;">
                        <div style="font-weight: 800; color: #78350F;">Piškotki</div>
                        <div>
                            Stran uporablja piškotke za pravilno delovanje in izboljšanje uporabniške izkušnje.
                            <a href="piskotki.html" style="text-decoration: underline; font-weight: 700; color: #78350F;">Več o piškotkih</a>.
                        </div>
                    </div>
                    <div style="display: flex; gap: 0.75rem; flex-wrap: wrap; justify-content: flex-end;">
                        <button id="cookie-reject" type="button" style="padding: 0.5rem 1rem; border-radius: 0.75rem; border: 1px solid #FCD34D; background: transparent; font-weight: 800; color: #78350F; cursor: pointer;">Zavrni</button>
                        <button id="cookie-accept" type="button" style="padding: 0.5rem 1rem; border-radius: 0.75rem; border: 1px solid #D97706; background: #D97706; color: #ffffff; font-weight: 800; cursor: pointer;">Sprejmi</button>
                    </div>
                </div>
            </div>
        `;

        document.body.appendChild(banner);
        return banner;
    };

    const banner = ensureBanner();
    const acceptBtn = document.getElementById("cookie-accept");
    const rejectBtn = document.getElementById("cookie-reject");
    if (!banner || !acceptBtn || !rejectBtn) return;

    const hide = () => { banner.classList.add("hidden"); banner.setAttribute("aria-hidden", "true"); };
    const show = () => { banner.classList.remove("hidden"); banner.removeAttribute("aria-hidden"); };
    const setConsent = (value) => {
        try { localStorage.setItem(key, value); } catch (e) { }
        document.documentElement.dataset.cookieConsent = value;
        if (value === "accepted") enableGa4Analytics();
        if (value === "rejected") disableGa4Analytics();
        hide();
    };

    if (existing === "accepted" || existing === "rejected") {
        document.documentElement.dataset.cookieConsent = existing;
        hide();
        if (existing === "accepted") enableGa4Analytics();
    } else {
        show();
    }

    acceptBtn.addEventListener("click", () => setConsent("accepted"));
    rejectBtn.addEventListener("click", () => setConsent("rejected"));
}

function initMobileMenu() {
    const header = document.querySelector("header");
    if (!header) return;

    const bar = header.querySelector("div.max-w-7xl");
    if (!bar) return;

    const existingBtn = header.querySelector("#fp-mobile-menu-btn");
    const existingOverlay = header.querySelector("#fp-mobile-menu-overlay");
    if (existingBtn || existingOverlay) return;

    const currentFile = String(window.location.pathname ?? "").split("/").pop() || "";
    const isIndex = currentFile === "" || currentFile === "index.html";
    const home = isIndex ? "#home" : "index.html#home";
    const kalkulatorji = isIndex ? "#kalkulatorji" : "index.html#kalkulatorji";
    const onas = isIndex ? "#onas" : "index.html#onas";
    const kontakt = isIndex ? "#kontakt" : "index.html#kontakt";

    const links = [
        { href: home, text: "Domov" },
        { href: kalkulatorji, text: "Kalkulatorji" },
        { href: "primerjava-depozitov.html", text: "Primerjava depozitov" },
        { href: onas, text: "O nas" },
        { href: kontakt, text: "Kontakt" },
    ];

    const btn = document.createElement("button");
    btn.id = "fp-mobile-menu-btn";
    btn.type = "button";
    btn.setAttribute("aria-label", "Odpri meni");
    btn.setAttribute("aria-expanded", "false");
    btn.style.display = "inline-flex";
    btn.style.alignItems = "center";
    btn.style.justifyContent = "center";
    btn.style.width = "44px";
    btn.style.height = "44px";
    btn.style.border = "1px solid rgba(229,231,235,1)";
    btn.style.borderRadius = "12px";
    btn.style.background = "rgba(255,255,255,0.85)";
    btn.style.backdropFilter = "blur(6px)";
    btn.style.cursor = "pointer";
    btn.style.marginLeft = "12px";
    btn.style.boxShadow = "0 1px 2px rgba(0,0,0,0.05)";
    btn.innerHTML = `
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
            <path d="M4 7h16" stroke="#111827" stroke-width="2" stroke-linecap="round"/>
            <path d="M4 12h16" stroke="#111827" stroke-width="2" stroke-linecap="round"/>
            <path d="M4 17h16" stroke="#111827" stroke-width="2" stroke-linecap="round"/>
        </svg>
    `;

    const overlay = document.createElement("div");
    overlay.id = "fp-mobile-menu-overlay";
    overlay.setAttribute("aria-hidden", "true");
    overlay.style.position = "fixed";
    overlay.style.inset = "0";
    overlay.style.zIndex = "9999";
    overlay.style.background = "rgba(17,24,39,0.45)";
    overlay.style.display = "none";
    overlay.style.padding = "18px";

    const panel = document.createElement("div");
    panel.style.maxWidth = "520px";
    panel.style.width = "100%";
    panel.style.margin = "64px auto 0";
    panel.style.background = "#ffffff";
    panel.style.borderRadius = "18px";
    panel.style.border = "1px solid rgba(229,231,235,1)";
    panel.style.boxShadow = "0 12px 40px rgba(0,0,0,0.18)";
    panel.style.overflow = "hidden";

    const panelHeader = document.createElement("div");
    panelHeader.style.display = "flex";
    panelHeader.style.alignItems = "center";
    panelHeader.style.justifyContent = "space-between";
    panelHeader.style.padding = "14px 16px";
    panelHeader.style.borderBottom = "1px solid rgba(229,231,235,1)";

    const panelTitle = document.createElement("div");
    panelTitle.textContent = "Meni";
    panelTitle.style.fontWeight = "800";
    panelTitle.style.fontSize = "16px";
    panelTitle.style.color = "#111827";

    const closeBtn = document.createElement("button");
    closeBtn.type = "button";
    closeBtn.setAttribute("aria-label", "Zapri meni");
    closeBtn.style.width = "40px";
    closeBtn.style.height = "40px";
    closeBtn.style.borderRadius = "12px";
    closeBtn.style.border = "1px solid rgba(229,231,235,1)";
    closeBtn.style.background = "#ffffff";
    closeBtn.style.cursor = "pointer";
    closeBtn.innerHTML = `
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
            <path d="M6 6l12 12" stroke="#111827" stroke-width="2" stroke-linecap="round"/>
            <path d="M18 6L6 18" stroke="#111827" stroke-width="2" stroke-linecap="round"/>
        </svg>
    `;

    panelHeader.appendChild(panelTitle);
    panelHeader.appendChild(closeBtn);

    const list = document.createElement("div");
    list.style.display = "flex";
    list.style.flexDirection = "column";
    list.style.padding = "10px";
    list.style.gap = "8px";

    links.forEach((l) => {
        const a = document.createElement("a");
        a.href = l.href;
        a.textContent = l.text;
        a.style.display = "block";
        a.style.padding = "12px 12px";
        a.style.borderRadius = "14px";
        a.style.border = "1px solid rgba(229,231,235,1)";
        a.style.color = "#111827";
        a.style.textDecoration = "none";
        a.style.fontWeight = "700";
        a.style.fontSize = "14px";
        a.addEventListener("click", () => {
            close();
        });
        list.appendChild(a);
    });

    const ctaWrap = document.createElement("div");
    ctaWrap.style.padding = "0 10px 12px";

    const cta = document.createElement("a");
    cta.href = "primerjava-depozitov.html";
    cta.textContent = "Začni primerjavo";
    cta.style.display = "block";
    cta.style.textAlign = "center";
    cta.style.padding = "12px 14px";
    cta.style.borderRadius = "14px";
    cta.style.background = "#0B6B3A";
    cta.style.color = "#ffffff";
    cta.style.fontWeight = "800";
    cta.style.textDecoration = "none";
    cta.addEventListener("click", () => close());

    ctaWrap.appendChild(cta);

    panel.appendChild(panelHeader);
    panel.appendChild(list);
    panel.appendChild(ctaWrap);
    overlay.appendChild(panel);

    const mq = window.matchMedia("(min-width: 768px)");
    const applyVisibility = () => {
        btn.style.display = mq.matches ? "none" : "inline-flex";
        if (mq.matches) close();
    };

    const open = () => {
        overlay.style.display = "block";
        overlay.setAttribute("aria-hidden", "false");
        btn.setAttribute("aria-expanded", "true");
        document.body.style.overflow = "hidden";
    };

    const close = () => {
        overlay.style.display = "none";
        overlay.setAttribute("aria-hidden", "true");
        btn.setAttribute("aria-expanded", "false");
        document.body.style.overflow = "";
    };

    btn.addEventListener("click", () => {
        if (overlay.style.display === "block") close();
        else open();
    });

    closeBtn.addEventListener("click", close);

    overlay.addEventListener("click", (e) => {
        if (e.target === overlay) close();
    });

    document.addEventListener("keydown", (e) => {
        if (e.key === "Escape") close();
    });

    if (typeof mq.addEventListener === "function") {
        mq.addEventListener("change", applyVisibility);
    } else {
        mq.addListener(applyVisibility);
    }

    bar.appendChild(btn);
    header.appendChild(overlay);
    applyVisibility();
}

/* ============================
   TAB SWITCHING
============================ */

function switchToTab(tabName) {
    const tabs = ['kredit', 'depozit', 'invest'];

    if (!tabs.includes(tabName)) return;

    // Update active tab
    tabs.forEach(name => {
        const tabEl = document.getElementById(`tab-${name}`);
        const panelEl = document.getElementById(`panel-${name}`);

        if (tabEl) {
            if (name === tabName) {
                tabEl.classList.add('active');
            } else {
                tabEl.classList.remove('active');
            }
        }

        if (panelEl) {
            if (name === tabName) {
                panelEl.classList.remove('hidden');
            } else {
                panelEl.classList.add('hidden');
            }
        }
    });
}

/* ============================
   KREDITNA SPOSOBNOST
============================ */

function maxPrincipalFromPayment(payment, months, annualNominalRate) {
    const A = Number(payment);
    const n = Number(months);
    const rA = Number(annualNominalRate);
    if (!Number.isFinite(A) || !Number.isFinite(n) || !Number.isFinite(rA) || A <= 0 || n <= 0) return NaN;

    const rM = rA / 12;
    if (Math.abs(rM) < 1e-12) return A * n;

    const denom = (rM * Math.pow(1 + rM, n)) / (Math.pow(1 + rM, n) - 1);
    if (!Number.isFinite(denom) || denom <= 0) return NaN;
    return A / denom;
}

function calculateCreditworthiness() {
    const income = getElementValue("cs-income");
    const adults = Math.max(1, Math.floor(getElementValue("cs-adults")));
    const children = Math.max(0, Math.floor(getElementValue("cs-children")));
    const existing = getElementValue("cs-existing");
    const livingActual = getElementValue("cs-living-actual");
    const rent = getElementValue("cs-rent");
    const years = getElementValue("cs-years");
    const rateAnnual = getElementValue("cs-rate") / 100;

    const dsti = getElementValue("cs-dsti") / 100;
    const minAdult = getElementValue("cs-min-adult");
    const minChild = getElementValue("cs-min-child");
    const safety = getElementValue("cs-safety") / 100;

    const months = Math.round(Number(years) * 12);
    if (!Number.isFinite(income) || income <= 0 || !Number.isFinite(months) || months <= 0 || !Number.isFinite(rateAnnual)) {
        setElementText("cs-max-payment", "–");
        setElementText("cs-max-loan", "–");
        setElementText("cs-limit-reason", "–");
        return;
    }

    const livingNorm = (Number.isFinite(minAdult) ? minAdult : 0) * adults + (Number.isFinite(minChild) ? minChild : 0) * children;
    const living = Number.isFinite(livingActual) && livingActual > 0 ? livingActual : livingNorm;
    const availableAfterBasics = income - living - (Number.isFinite(rent) ? rent : 0) - (Number.isFinite(existing) ? existing : 0);
    const dstiCapTotal = (Number.isFinite(dsti) ? dsti : 0) > 0 ? (income * dsti) : Infinity;
    const dstiCapNew = dstiCapTotal - (Number.isFinite(existing) ? existing : 0);

    let allowed = Math.min(availableAfterBasics, dstiCapNew);
    if (!Number.isFinite(allowed)) allowed = availableAfterBasics;

    const safetyMult = 1 - (Number.isFinite(safety) ? safety : 0);
    if (Number.isFinite(safetyMult) && safetyMult > 0 && safetyMult < 1) {
        allowed *= safetyMult;
    }

    const maxPayment = Math.max(0, allowed);
    setElementText("cs-max-payment", formatSIWholeEuro(maxPayment));

    const principal = maxPayment > 0 ? maxPrincipalFromPayment(maxPayment, months, rateAnnual) : 0;
    setElementText("cs-max-loan", formatSIWholeEuro(principal));

    const reasons = [];
    if (availableAfterBasics <= dstiCapNew) {
        reasons.push("Omejitev: razpoložljiv dohodek po stroških gospodinjstva in obveznostih");
    } else {
        reasons.push("Omejitev: DSTI limit (delež dohodka za obveznosti)");
    }

    if (Number.isFinite(livingActual) && livingActual > 0) {
        reasons.push("Uporabljeni dejanski stroški gospodinjstva");
    } else {
        reasons.push("Uporabljena normativna rezerva (odrasli/otroci)");
    }

    if (Number.isFinite(safety) && safety > 0) {
        reasons.push("Uporabljena varnostna rezerva");
    }
    setElementText("cs-limit-reason", reasons.join(". ") + ".");
}

function initCreditworthinessBindings() {
    const btn = document.getElementById("cs-calc-btn");
    if (btn) btn.addEventListener("click", calculateCreditworthiness);

    ["cs-rate", "cs-dsti", "cs-safety"].forEach((id) => {
        const el = document.getElementById(id);
        if (!el) return;
        el.addEventListener("blur", () => normalizeRateInput(id));
    });
}

// Initialize tabs
function initTabs() {
    const tabs = ['kredit', 'depozit', 'invest'];

    const hasAnyTab = tabs.some((tabName) => !!document.getElementById(`tab-${tabName}`));
    const hasAnyPanel = tabs.some((tabName) => !!document.getElementById(`panel-${tabName}`));
    if (!hasAnyTab && !hasAnyPanel) return;

    tabs.forEach(tabName => {
        const tabElement = document.getElementById(`tab-${tabName}`);
        if (tabElement) {
            tabElement.addEventListener('click', () => switchToTab(tabName));
        }
    });

    // Set default tab
    if (document.getElementById('tab-kredit') || document.getElementById('panel-kredit')) {
        switchToTab('kredit');
    }
}

/* ============================
   VALIDATION & ERROR HANDLING
============================ */

function validateInputs(...inputs) {
    return inputs.every(input =>
        !isNaN(input) &&
        isFinite(input) &&
        input >= 0
    );
}

function showError(message) {
    console.warn(message);
    // Could be extended to show user-friendly error messages in the UI
}

function getElementValue(id) {
    const element = document.getElementById(id);
    if (!element) return 0;

    const cleaned = element.value
        .replace(/\./g, "")   // odstrani tisočice
        .replace(",", ".");   // decimalna vejica → pika

    return parseFloat(cleaned) || 0;
}

function formatRateSI(num) {
    const n = Number(num);
    if (!Number.isFinite(n)) return "";
    return n.toFixed(2).replace(".", ",");
}

function normalizeRateInput(id) {
    const el = document.getElementById(id);
    if (!el) return;

    const n = getElementValue(id);
    if (!Number.isFinite(n) || n === 0 && String(el.value ?? "").trim() === "") return;
    el.value = formatRateSI(n);
}


function setElementText(id, text) {
    const element = document.getElementById(id);
    if (element) {
        element.textContent = text;
    }
}

/* ============================
   EOM / APR KALKULATOR
============================ */

function calcAnnuityPayment(principal, months, annualNominalRate) {
    const P = Number(principal);
    const n = Number(months);
    const rA = Number(annualNominalRate);
    if (!Number.isFinite(P) || !Number.isFinite(n) || !Number.isFinite(rA) || P <= 0 || n <= 0) return NaN;

    const rM = rA / 12;
    if (!Number.isFinite(rM)) return NaN;

    if (Math.abs(rM) < 1e-12) return P / n;

    const pow = Math.pow(1 + rM, n);
    return P * (rM * pow) / (pow - 1);
}

function npvFromMonthlyRate(netDisbursed, monthlyOutflow, months, rateM) {
    const net = Number(netDisbursed);
    const out = Number(monthlyOutflow);
    const n = Number(months);
    const r = Number(rateM);
    if (!Number.isFinite(net) || !Number.isFinite(out) || !Number.isFinite(n) || !Number.isFinite(r)) return NaN;
    if (n <= 0) return NaN;
    if (r <= -0.999999999) return NaN;

    let pv = net;
    for (let m = 1; m <= n; m++) {
        pv -= out / Math.pow(1 + r, m);
    }
    return pv;
}

function solveAprMonthlyRate(netDisbursed, monthlyOutflow, months) {
    const net = Number(netDisbursed);
    const out = Number(monthlyOutflow);
    const n = Number(months);
    if (!Number.isFinite(net) || !Number.isFinite(out) || !Number.isFinite(n) || n <= 0) return NaN;

    const f = (r) => npvFromMonthlyRate(net, out, n, r);

    let low = -0.99;
    let high = 1.0;
    let fLow = f(low);
    let fHigh = f(high);

    if (!Number.isFinite(fLow) || !Number.isFinite(fHigh)) return NaN;

    let guard = 0;
    while (fLow * fHigh > 0 && guard < 60) {
        high *= 2;
        fHigh = f(high);
        if (!Number.isFinite(fHigh)) return NaN;
        guard++;
    }

    if (fLow * fHigh > 0) return NaN;

    for (let i = 0; i < 120; i++) {
        const mid = (low + high) / 2;
        const fMid = f(mid);
        if (!Number.isFinite(fMid)) return NaN;

        if (Math.abs(fMid) < 1e-10) return mid;
        if (fLow * fMid <= 0) {
            high = mid;
            fHigh = fMid;
        } else {
            low = mid;
            fLow = fMid;
        }
    }

    return (low + high) / 2;
}

function calculateEom() {
    const amount = getElementValue("eom-amount");
    const months = getElementValue("eom-months");
    const nominalAnnual = getElementValue("eom-nominal-rate") / 100;
    const upfrontPercent = getElementValue("eom-upfront-percent") / 100;
    const upfrontEur = getElementValue("eom-upfront-eur");
    const monthlyFee = getElementValue("eom-monthly-fee");

    if (!Number.isFinite(amount) || amount <= 0 || !Number.isFinite(months) || months <= 0 || !Number.isFinite(nominalAnnual)) {
        setElementText("eom-apr", "–");
        return;
    }

    const payment = calcAnnuityPayment(amount, months, nominalAnnual);
    const upfrontFeeTotal = amount * (Number.isFinite(upfrontPercent) ? upfrontPercent : 0) + (Number.isFinite(upfrontEur) ? upfrontEur : 0);
    const netDisbursed = amount - upfrontFeeTotal;
    const monthlyOutflow = payment + (Number.isFinite(monthlyFee) ? monthlyFee : 0);

    setElementText("eom-monthly-payment", formatSIWholeEuro(payment));
    setElementText("eom-monthly-outflow", formatSIWholeEuro(monthlyOutflow));

    const rateM = solveAprMonthlyRate(netDisbursed, monthlyOutflow, months);
    if (!Number.isFinite(rateM)) {
        setElementText("eom-apr", "–");
        return;
    }

    const apr = Math.pow(1 + rateM, 12) - 1;
    setElementText("eom-apr", formatPercentSI(apr * 100));
}

function initEomUiBindings() {
    const btn = document.getElementById("eom-calc-btn");
    if (btn) {
        btn.addEventListener("click", calculateEom);
    }

    const ids = [
        "eom-amount",
        "eom-months",
        "eom-nominal-rate",
        "eom-upfront-percent",
        "eom-upfront-eur",
        "eom-monthly-fee",
    ];

    ids.forEach((id) => {
        const el = document.getElementById(id);
        if (!el) return;
        el.addEventListener("change", () => {
            if (id === "eom-nominal-rate" || id === "eom-upfront-percent") {
                normalizeRateInput(id);
            }
        });
    });
}

/* ============================
   LEASING VS KREDIT (VOZILA)
============================ */

function calculateLeasingVsLoan() {
    const price = getElementValue("lvk-price");
    const down = getElementValue("lvk-down");
    const months = getElementValue("lvk-months");

    const loanRate = getElementValue("lvk-loan-rate") / 100;
    const leasingRate = getElementValue("lvk-leasing-rate") / 100;

    const loanUpfront = getElementValue("lvk-loan-upfront");
    const loanMonthlyFee = getElementValue("lvk-loan-monthly-fee");
    const leasingUpfront = getElementValue("lvk-leasing-upfront");
    const leasingMonthlyFee = getElementValue("lvk-leasing-monthly-fee");
    const residual = getElementValue("lvk-residual");

    const winnerEl = document.getElementById("lvk-winner");
    const setDash = () => {
        setElementText("lvk-winner", "–");
        setElementText("lvk-loan-monthly", "–");
        setElementText("lvk-loan-total", "–");
        setElementText("lvk-loan-eom", "–");
        setElementText("lvk-leasing-monthly", "–");
        setElementText("lvk-leasing-total", "–");
        setElementText("lvk-leasing-eom", "–");
    };

    if (
        !Number.isFinite(price) || price <= 0 ||
        !Number.isFinite(down) || down < 0 || down >= price ||
        !Number.isFinite(months) || months <= 0 ||
        !Number.isFinite(loanRate) || loanRate < 0 ||
        !Number.isFinite(leasingRate) || leasingRate < 0
    ) {
        setDash();
        return;
    }

    const financed = price - down;

    // Loan: classic annuity + optional fees.
    const loanPayment = calcAnnuityPayment(financed, months, loanRate);
    const safeLoanMonthlyFee = Number.isFinite(loanMonthlyFee) ? loanMonthlyFee : 0;
    const loanMonthlyOutflow = Number.isFinite(loanPayment) ? (loanPayment + safeLoanMonthlyFee) : NaN;

    // Leasing: financed part is treated as annuity, and residual is paid at the end.
    // This is a simplification but works well for comparison.
    const leasingPayment = calcAnnuityPayment(financed, months, leasingRate);
    const safeLeasingMonthlyFee = Number.isFinite(leasingMonthlyFee) ? leasingMonthlyFee : 0;
    const leasingMonthlyOutflow = Number.isFinite(leasingPayment) ? (leasingPayment + safeLeasingMonthlyFee) : NaN;

    const safeLoanUpfront = Number.isFinite(loanUpfront) ? loanUpfront : 0;
    const safeLeasingUpfront = Number.isFinite(leasingUpfront) ? leasingUpfront : 0;
    const safeResidual = Number.isFinite(residual) ? residual : 0;

    if (!Number.isFinite(loanMonthlyOutflow) || !Number.isFinite(leasingMonthlyOutflow)) {
        setDash();
        return;
    }

    // Totals (include downpayment so user sees total cash spent)
    const loanTotal = down + safeLoanUpfront + loanMonthlyOutflow * months;
    const leasingTotal = down + safeLeasingUpfront + leasingMonthlyOutflow * months + safeResidual;

    setElementText("lvk-loan-monthly", formatSIWholeEuro(loanMonthlyOutflow));
    setElementText("lvk-loan-total", formatSIWholeEuro(loanTotal));

    setElementText("lvk-leasing-monthly", formatSIWholeEuro(leasingMonthlyOutflow));
    setElementText("lvk-leasing-total", formatSIWholeEuro(leasingTotal));

    // EOM approximation via APR solver:
    // Treat financed as net disbursed; fees reduce net; monthly outflow includes monthly fees.
    // For leasing, we include residual as an equivalent monthly spread to keep solver simple.
    const loanNet = financed - safeLoanUpfront;
    const loanRateM = solveAprMonthlyRate(loanNet, loanMonthlyOutflow, months);
    const loanApr = Number.isFinite(loanRateM) ? (Math.pow(1 + loanRateM, 12) - 1) : NaN;
    setElementText("lvk-loan-eom", Number.isFinite(loanApr) ? formatPercentSI(loanApr * 100) : "–");

    const leasingNet = financed - safeLeasingUpfront;
    const residualMonthly = safeResidual / months;
    const leasingRateM = solveAprMonthlyRate(leasingNet, leasingMonthlyOutflow + residualMonthly, months);
    const leasingApr = Number.isFinite(leasingRateM) ? (Math.pow(1 + leasingRateM, 12) - 1) : NaN;
    setElementText("lvk-leasing-eom", Number.isFinite(leasingApr) ? formatPercentSI(leasingApr * 100) : "–");

    // Winner
    const diff = leasingTotal - loanTotal;
    if (Number.isFinite(diff)) {
        if (Math.abs(diff) < 0.5) {
            setElementText("lvk-winner", "Izenačeno (≈)");
        } else if (diff > 0) {
            setElementText("lvk-winner", `Bančni kredit (≈ ${formatSIWholeEuro(diff)} ceneje)`);
        } else {
            setElementText("lvk-winner", `Leasing (≈ ${formatSIWholeEuro(Math.abs(diff))} ceneje)`);
        }
    } else {
        setElementText("lvk-winner", "–");
    }

    if (winnerEl) {
        winnerEl.classList.remove("text-red-600");
        winnerEl.classList.add("fp-result-value--primary");
    }

    fpTrack("calculator_used", {
        calculator: "leasing_vs_loan",
        currency: "EUR",
        price_eur: Math.round(price),
        down_eur: Math.round(down),
        months: Number(months),
        loan_rate_percent: Math.round((loanRate * 100) * 100) / 100,
        leasing_rate_percent: Math.round((leasingRate * 100) * 100) / 100,
    });
}

function initLeasingVsLoanBindings() {
    const btn = document.getElementById("lvk-calc-btn");
    if (btn) {
        btn.addEventListener("click", calculateLeasingVsLoan);
    }

    // Normalize percent inputs on change
    const rateIds = ["lvk-loan-rate", "lvk-leasing-rate"];
    rateIds.forEach((id) => {
        const el = document.getElementById(id);
        if (!el) return;
        el.addEventListener("change", () => normalizeRateInput(id));
    });
}

function formatPercentInputSI(val, decimals = 2) {
    const n = Number(val);
    if (!Number.isFinite(n)) return "";
    return n.toFixed(decimals).replace(".", ",");
}

function initLostInterestBenchmarkBindings() {
    const benchmarkEl = document.getElementById("lost-benchmark");
    if (!benchmarkEl) return;

    // Ensure EURIBOR cache is available for the dropdown on this page as well.
    // loadEuriborRates() is safe to call here; updateLoanRateUi() will no-op if loan UI isn't present.
    loadEuriborRates();

    const apply = () => applyLostInterestBenchmark(String(benchmarkEl.value ?? "manual"));
    benchmarkEl.addEventListener("change", apply);
    apply();
}

function applyLostInterestBenchmark(benchmark) {
    const rateEl = document.getElementById("lost-rate");
    const etfReturnEl = document.getElementById("lost-etf-return");
    const etfFeeEl = document.getElementById("lost-etf-fee");
    const infoEl = document.getElementById("lost-benchmark-info");

    if (!rateEl || !etfReturnEl || !etfFeeEl) return;

    if (infoEl) infoEl.textContent = "";

    const b = String(benchmark || "manual");

    if (b === "euribor_3m" || b === "euribor_6m") {
        const tenor = b === "euribor_6m" ? "6m" : "3m";
        const eur = euriborCache[tenor] || euriborCache["3m"];
        if (eur && Number.isFinite(eur.value)) {
            // EURIBOR values come as % (e.g. 3.85). Input expects percent.
            rateEl.value = formatPercentInputSI(eur.value, 2);
            normalizeRateInput("lost-rate");
            if (infoEl) {
                if (eur.period) {
                    infoEl.textContent = `Veljavni EURIBOR ${tenor.toUpperCase()} (${eur.period}): ${formatRateSI(eur.value)}%`;
                } else {
                    infoEl.textContent = `Veljavni EURIBOR ${tenor.toUpperCase()}: ${formatRateSI(eur.value)}%`;
                }
            }
        } else {
            if (infoEl) infoEl.textContent = `EURIBOR ${tenor.toUpperCase()} se nalaga...`;
        }
        return;
    }

    if (b === "etf_vwce") {
        // Typical long-term estimate + typical TER. User can still override.
        etfReturnEl.value = formatPercentInputSI(7.0, 2);
        etfFeeEl.value = formatPercentInputSI(0.22, 2);
        normalizeRateInput("lost-etf-return");
        normalizeRateInput("lost-etf-fee");
        return;
    }

    if (b === "etf_sp500") {
        etfReturnEl.value = formatPercentInputSI(9.0, 2);
        etfFeeEl.value = formatPercentInputSI(0.07, 2);
        normalizeRateInput("lost-etf-return");
        normalizeRateInput("lost-etf-fee");
        return;
    }
}

/* ============================
   MENJALNIŠKI KALKULATOR (ECB)
============================ */

let fxCache = {};

async function fetchLatestEcbFxVsEur(currency) {
    const cur = String(currency ?? "").trim().toUpperCase();
    if (!cur || cur === "EUR") return { currency: "EUR", rate: 1, period: null, source: "ECB" };

    const cached = fxCache[cur];
    if (cached && Number.isFinite(cached.rate) && cached.rate > 0) return cached;

    const url = `https://data-api.ecb.europa.eu/service/data/EXR/D.${cur}.EUR.SP00.A?lastNObservations=1`;
    const res = await fetch(url, { cache: "no-store" });
    if (!res.ok) throw new Error(`FX fetch failed: ${res.status}`);
    const xmlText = await res.text();

    const parser = new DOMParser();
    const doc = parser.parseFromString(xmlText, "application/xml");
    const obs = doc.getElementsByTagName("generic:Obs")[0] || doc.getElementsByTagName("Obs")[0];
    if (!obs) throw new Error("FX parse error: missing Obs");

    const dimEl = obs.getElementsByTagName("generic:ObsDimension")[0] || obs.getElementsByTagName("ObsDimension")[0];
    const valEl = obs.getElementsByTagName("generic:ObsValue")[0] || obs.getElementsByTagName("ObsValue")[0];

    const period = dimEl ? String(dimEl.getAttribute("value") ?? "").trim() : "";
    const rawValue = valEl ? String(valEl.getAttribute("value") ?? "").trim() : "";
    const rate = Number(rawValue);

    if (!Number.isFinite(rate) || rate <= 0) throw new Error("FX parse error: invalid value");
    const entry = { currency: cur, rate, period: period || null, source: "ECB" };
    fxCache[cur] = entry;
    return entry;
}

async function calculateFx() {
    const amount = getElementValue("fx-amount");
    const from = String(document.getElementById("fx-from")?.value ?? "EUR").trim().toUpperCase();
    const to = String(document.getElementById("fx-to")?.value ?? "EUR").trim().toUpperCase();
    const spread = Math.max(0, getElementValue("fx-spread") / 100);
    const feeEur = Math.max(0, getElementValue("fx-fee"));
    const manual = !!document.getElementById("fx-manual-toggle")?.checked;

    if (!Number.isFinite(amount) || amount <= 0 || !from || !to) {
        setElementText("fx-result", "–");
        setElementText("fx-rate-used", "–");
        setElementText("fx-cost", "–");
        return;
    }

    if (from === to) {
        setElementText("fx-result", formatMoney(amount, to));
        setElementText("fx-rate-used", "1,0000");
        setElementText("fx-cost", formatSI(0));
        return;
    }

    if (manual) {
        const baseRate = getElementValue("fx-manual-rate");
        if (!Number.isFinite(baseRate) || baseRate <= 0) {
            setElementText("fx-result", "–");
            setElementText("fx-rate-used", "–");
            setElementText("fx-cost", "–");
            return;
        }

        const effectiveRate = baseRate * (1 - spread);
        setElementText("fx-result", formatMoney(amount * effectiveRate, to));
        setElementText("fx-rate-used", `${baseRate.toFixed(4).replace(".", ",")} (ročno)`);
        setElementText("fx-cost", "–");
        return;
    }

    try {
        const currencies = Array.from(new Set([from, to].filter(c => c && c !== "EUR")));
        await Promise.all(currencies.map(c => fetchLatestEcbFxVsEur(c)));
    } catch (e) {
        console.warn("FX load failed", e);
    }

    const rFrom = from === "EUR" ? 1 : (fxCache[from] && Number.isFinite(fxCache[from].rate) ? fxCache[from].rate : NaN);
    const rTo = to === "EUR" ? 1 : (fxCache[to] && Number.isFinite(fxCache[to].rate) ? fxCache[to].rate : NaN);
    if (!Number.isFinite(rFrom) || !Number.isFinite(rTo) || rFrom <= 0 || rTo <= 0) {
        setElementText("fx-result", "–");
        setElementText("fx-rate-used", "ECB tečaj ni na voljo");
        setElementText("fx-cost", "–");
        return;
    }

    // ECB: tečaji so podani kot CUR na 1 EUR.
    // Pretvorba FROM -> EUR -> TO.
    const amountEur = from === "EUR" ? amount : (amount / rFrom);
    const eurAfterFee = Math.max(0, amountEur - feeEur);
    const eurAfterSpread = eurAfterFee * (1 - spread);
    const received = to === "EUR" ? eurAfterSpread : (eurAfterSpread * rTo);

    const costEur = Math.max(0, amountEur - eurAfterSpread);

    const baseCrossRate = rTo / rFrom; // 1 FROM = baseCrossRate TO
    const period = (fxCache[to] && fxCache[to].period) || (fxCache[from] && fxCache[from].period) || null;
    const periodSl = period ? formatDateSl(period) : "";
    const usedText = `${baseCrossRate.toFixed(4).replace(".", ",")} ${periodSl ? `(${periodSl})` : ""}`.trim();

    setElementText("fx-result", formatMoney(received, to));
    setElementText("fx-rate-used", usedText);
    setElementText("fx-cost", formatSI(costEur));
}

async function updateFxEcbInfo() {
    const info = document.getElementById("fx-ecb-info");
    if (!info) return;

    const manual = !!document.getElementById("fx-manual-toggle")?.checked;
    if (manual) {
        info.textContent = "Ročni tečaj je vklopljen.";
        return;
    }

    const from = String(document.getElementById("fx-from")?.value ?? "EUR").trim().toUpperCase();
    const to = String(document.getElementById("fx-to")?.value ?? "EUR").trim().toUpperCase();

    const currencies = Array.from(new Set([from, to].filter(c => c && c !== "EUR")));
    if (currencies.length === 0) {
        info.textContent = "ECB tečaj: 1 EUR = 1 EUR";
        return;
    }

    try {
        await Promise.all(currencies.map(c => fetchLatestEcbFxVsEur(c)));
        const parts = currencies.map(c => {
            const fx = fxCache[c];
            if (!fx || !Number.isFinite(fx.rate)) return null;
            return `1 EUR = ${fx.rate.toFixed(4).replace(".", ",")} ${c}`;
        }).filter(Boolean);
        info.textContent = parts.length ? `ECB tečaj: ${parts.join(" | ")}` : "ECB tečaj ni na voljo";
    } catch (e) {
        console.warn("FX load failed", e);
        info.textContent = "ECB tečaj ni na voljo";
    }
}

function initFxBindings() {
    initFxCurrencyDropdown("fx-from", "fx-from-ui");
    initFxCurrencyDropdown("fx-to", "fx-to-ui");

    const btn = document.getElementById("fx-calc-btn");
    if (btn) btn.addEventListener("click", calculateFx);

    const manualToggle = document.getElementById("fx-manual-toggle");
    const manualWrap = document.getElementById("fx-manual-wrapper");
    if (manualToggle) {
        const sync = () => {
            if (manualWrap) {
                if (manualToggle.checked) manualWrap.classList.remove("hidden");
                else manualWrap.classList.add("hidden");
            }
            updateFxEcbInfo();
        };
        manualToggle.addEventListener("change", sync);
        manualToggle.addEventListener("input", sync);
        sync();
    }

    const fromEl = document.getElementById("fx-from");
    const toEl = document.getElementById("fx-to");
    if (fromEl) {
        fromEl.addEventListener("change", updateFxEcbInfo);
        fromEl.addEventListener("input", updateFxEcbInfo);
    }
    if (toEl) {
        toEl.addEventListener("change", updateFxEcbInfo);
        toEl.addEventListener("input", updateFxEcbInfo);
    }

    const spreadEl = document.getElementById("fx-spread");
    if (spreadEl) {
        spreadEl.addEventListener("blur", () => normalizeRateInput("fx-spread"));
    }

    updateFxEcbInfo();
}

/* ============================
   IZGUBLJENE OBRESTI (TRR vs depozit)
============================ */

function calculateLostInterest() {
    const amount = getElementValue("lost-amount");
    const time = getElementValue("lost-time");
    const unit = String(document.getElementById("lost-unit")?.value ?? "months");
    const rateAnnual = getElementValue("lost-rate") / 100;
    const etfReturnAnnual = getElementValue("lost-etf-return") / 100;
    const etfFeeAnnual = getElementValue("lost-etf-fee") / 100;

    if (!Number.isFinite(amount) || amount <= 0 || !Number.isFinite(time) || time <= 0 || !Number.isFinite(rateAnnual)) {
        setElementText("lost-interest", "–");
        setElementText("lost-final", "–");
        setElementText("lost-etf-final", "–");
        setElementText("lost-etf-vs-deposit", "–");
        drawLostInterestChart(null);
        return;
    }

    const years = unit === "years" ? time : (time / 12);
    if (!Number.isFinite(years) || years <= 0) {
        setElementText("lost-interest", "–");
        setElementText("lost-final", "–");
        setElementText("lost-etf-final", "–");
        setElementText("lost-etf-vs-deposit", "–");
        drawLostInterestChart(null);
        return;
    }

    // Preprosta (linearno) obrestovanje kot privzet, TRR predpostavimo 0%.
    const interest = amount * rateAnnual * years;
    const finalAmount = amount + interest;

    setElementText("lost-interest", formatSIWholeEuro(interest));
    setElementText("lost-final", formatSIWholeEuro(finalAmount));

    // ETF alternativa (poenostavljeno): pričakovani donos minus letni stroški, z obrestno-obrestnim učinkom.
    const rEtfNet = (Number.isFinite(etfReturnAnnual) ? etfReturnAnnual : 0) - (Number.isFinite(etfFeeAnnual) ? etfFeeAnnual : 0);
    const etfFinal = amount * Math.pow(1 + rEtfNet, years);

    if (!Number.isFinite(etfFinal)) {
        setElementText("lost-etf-final", "–");
        setElementText("lost-etf-vs-deposit", "–");
        return;
    }

    setElementText("lost-etf-final", formatSIWholeEuro(etfFinal));
    setElementText("lost-etf-vs-deposit", formatSIWholeEuro(etfFinal - finalAmount));

    drawLostInterestChart(
        buildLostInterestSeries({
            amount,
            years,
            unit,
            time,
            rateAnnual,
            etfReturnAnnual,
            etfFeeAnnual,
        })
    );
}

let lostCompareChart = null;

function buildLostInterestSeries({ amount, years, unit, time, rateAnnual, etfReturnAnnual, etfFeeAnnual }) {
    const P = Number(amount);
    const y = Number(years);
    const t = Number(time);
    if (!Number.isFinite(P) || P <= 0 || !Number.isFinite(y) || y <= 0 || !Number.isFinite(t) || t <= 0) return null;

    const monthsTotal = unit === "years" ? Math.round(t * 12) : Math.round(t);
    if (!Number.isFinite(monthsTotal) || monthsTotal <= 0) return null;

    // TRR assumed 0%
    const labels = [];
    const trr = [];
    const deposit = [];
    const etf = [];

    const rEtfNet = (Number.isFinite(etfReturnAnnual) ? etfReturnAnnual : 0) - (Number.isFinite(etfFeeAnnual) ? etfFeeAnnual : 0);
    const rDepA = Number.isFinite(rateAnnual) ? rateAnnual : 0;

    for (let m = 0; m <= monthsTotal; m++) {
        const yM = m / 12;
        labels.push(m);

        trr.push(P);

        // Deposit: simple interest (consistent with calculator result)
        deposit.push(P + (P * rDepA * yM));

        // ETF: compound (consistent with calculator result)
        etf.push(P * Math.pow(1 + rEtfNet, yM));
    }

    return { labels, trr, deposit, etf };
}

function drawLostInterestChart(series) {
    const canvas = document.getElementById("lost-compare-chart");
    if (!canvas) return;

    const rateAnnualPct = getElementValue("lost-rate");
    const etfReturnPct = getElementValue("lost-etf-return");
    const etfFeePct = getElementValue("lost-etf-fee");
    const etfNetPct = (Number.isFinite(etfReturnPct) ? etfReturnPct : 0) - (Number.isFinite(etfFeePct) ? etfFeePct : 0);

    const formatNumberNoDecimals = (val) => {
        const n = Number(val);
        if (!Number.isFinite(n)) return "–";
        return n.toLocaleString("sl-SI", { maximumFractionDigits: 0, minimumFractionDigits: 0, useGrouping: true });
    };

    const formatEuro = (val) => `${formatNumberNoDecimals(val)} €`;

    if (!series) {
        if (lostCompareChart) {
            lostCompareChart.destroy();
            lostCompareChart = null;
        }
        return;
    }

    if (typeof Chart === "undefined") return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    if (lostCompareChart) {
        lostCompareChart.destroy();
        lostCompareChart = null;
    }

    const depositLabel = Number.isFinite(rateAnnualPct) ? `Depozit (${rateAnnualPct.toFixed(2)}% p.a.)` : "Depozit";
    const etfLabel = (Number.isFinite(etfReturnPct) || Number.isFinite(etfFeePct))
        ? `ETF (${(Number.isFinite(etfReturnPct) ? etfReturnPct : 0).toFixed(2)}% - ${(Number.isFinite(etfFeePct) ? etfFeePct : 0).toFixed(2)}% = ${etfNetPct.toFixed(2)}% p.a.)`
        : "ETF";

    lostCompareChart = new Chart(ctx, {
        type: "line",
        data: {
            labels: series.labels,
            datasets: [
                {
                    label: "TRR (0%)",
                    data: series.trr,
                    borderColor: "#9ca3af",
                    tension: 0.25,
                    pointRadius: 0,
                    borderWidth: 2,
                },
                {
                    label: depositLabel,
                    data: series.deposit,
                    borderColor: "#0B6B3A",
                    backgroundColor: "rgba(11, 107, 58, 0.10)",
                    tension: 0.25,
                    pointRadius: 0,
                    borderWidth: 2,
                },
                {
                    label: etfLabel,
                    data: series.etf,
                    borderColor: "#f97316",
                    backgroundColor: "rgba(249, 115, 22, 0.10)",
                    tension: 0.25,
                    pointRadius: 0,
                    borderWidth: 2,
                },
            ],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: { mode: "index", intersect: false },
            plugins: {
                legend: {
                    display: true,
                    position: "bottom",
                    labels: {
                        usePointStyle: true,
                        boxWidth: 10,
                    },
                },
                tooltip: {
                    callbacks: {
                        title: (items) => {
                            const first = Array.isArray(items) && items.length ? items[0] : null;
                            const m = first ? Number(first.label) : NaN;
                            if (!Number.isFinite(m)) return "";
                            if (m === 12) return "1 leto";
                            if (m % 12 === 0 && m > 0) return `${m / 12} leta`;
                            return `${m} mesecev`;
                        },
                        label: (ctx) => {
                            const v = ctx.parsed.y;
                            return `${ctx.dataset.label}: ${formatEuro(v)}`;
                        },
                    },
                },
            },
            scales: {
                x: {
                    title: { display: true, text: "Čas (meseci)" },
                    ticks: {
                        maxTicksLimit: 8,
                        callback: (value) => {
                            const m = Number(value);
                            if (!Number.isFinite(m)) return value;
                            if (m === 0) return "0";
                            if (m === 12) return "1L";
                            if (m % 12 === 0) return `${m / 12}L`;
                            return `${m}`;
                        },
                    },
                    grid: { color: "rgba(0,0,0,0.06)" },
                },
                y: {
                    title: { display: true, text: "Znesek (€)" },
                    grid: { color: "rgba(0,0,0,0.06)" },
                    ticks: { callback: (value) => formatNumberNoDecimals(value) },
                },
            },
        },
    });
}

function initLostInterestBindings() {
    const btn = document.getElementById("lost-calc-btn");
    if (btn) {
        btn.addEventListener("click", calculateLostInterest);
    }

    const ids = ["lost-amount", "lost-time", "lost-unit", "lost-rate", "lost-etf-return", "lost-etf-fee"];
    ids.forEach((id) => {
        const el = document.getElementById(id);
        if (!el) return;

        el.addEventListener("change", () => {
            if (id === "lost-rate" || id === "lost-etf-return" || id === "lost-etf-fee") {
                normalizeRateInput(id);
            }
        });
    });

    initLostInterestBenchmarkBindings();
}

let euriborCache = {
    "3m": { value: null, period: null, source: "ECB" },
    "6m": { value: null, period: null, source: "ECB" }
};

async function fetchLatestEuribor(tenor) {
    const t = String(tenor).toLowerCase();
    const series = t === "6m" ? "EURIBOR6MD_" : "EURIBOR3MD_";
    const url = `https://data-api.ecb.europa.eu/service/data/FM/M.U2.EUR.RT.MM.${series}.HSTA?lastNObservations=1`;

    const res = await fetch(url, { cache: "no-store" });
    if (!res.ok) throw new Error(`EURIBOR fetch failed: ${res.status}`);
    const xmlText = await res.text();

    const parser = new DOMParser();
    const doc = parser.parseFromString(xmlText, "application/xml");
    const obs = doc.getElementsByTagName("generic:Obs")[0] || doc.getElementsByTagName("Obs")[0];
    if (!obs) throw new Error("EURIBOR parse error: missing Obs");

    const dimEl = obs.getElementsByTagName("generic:ObsDimension")[0] || obs.getElementsByTagName("ObsDimension")[0];
    const valEl = obs.getElementsByTagName("generic:ObsValue")[0] || obs.getElementsByTagName("ObsValue")[0];

    const period = dimEl ? String(dimEl.getAttribute("value") ?? "").trim() : "";
    const rawValue = valEl ? String(valEl.getAttribute("value") ?? "").trim() : "";
    const value = Number(rawValue);

    if (!period || !Number.isFinite(value)) throw new Error("EURIBOR parse error: invalid value");
    return { value, period, source: "ECB" };
}

async function loadEuriborRates() {
    try {
        const [e3, e6] = await Promise.all([
            fetchLatestEuribor("3m"),
            fetchLatestEuribor("6m")
        ]);
        euriborCache = { "3m": e3, "6m": e6 };
    } catch (e) {
        console.warn("EURIBOR load failed", e);
    }

    updateLoanRateUi();
    // Also refresh lost-interest benchmark if EURIBOR is selected.
    const benchmarkEl = document.getElementById("lost-benchmark");
    if (benchmarkEl) {
        applyLostInterestBenchmark(String(benchmarkEl.value ?? "manual"));
    }
}

function updateLoanRateUi() {
    const typeEl = document.getElementById("loan-rate-type");
    const fixedWrap = document.getElementById("loan-fixed-wrapper");
    const eurWrap = document.getElementById("loan-euribor-wrapper");
    const tenorEl = document.getElementById("loan-euribor-tenor");
    const infoEl = document.getElementById("loan-euribor-info");

    if (!typeEl) return;
    const type = String(typeEl.value ?? "fixed");

    if (type === "euribor") {
        if (fixedWrap) fixedWrap.classList.add("hidden");
        if (eurWrap) eurWrap.classList.remove("hidden");

        const tenor = tenorEl ? String(tenorEl.value ?? "3m") : "3m";
        const eur = euriborCache[tenor] || euriborCache["3m"];
        if (infoEl) {
            if (eur && Number.isFinite(eur.value) && eur.period) {
                infoEl.textContent = `Veljavni EURIBOR ${tenor.toUpperCase()} (${eur.period}): ${formatRateSI(eur.value)}%`;
            } else {
                infoEl.textContent = "Nalaganje EURIBOR ...";
            }
        }
    } else {
        if (eurWrap) eurWrap.classList.add("hidden");
        if (fixedWrap) fixedWrap.classList.remove("hidden");
    }
}

function getLoanEffectiveAnnualRate() {
    const typeEl = document.getElementById("loan-rate-type");
    const type = typeEl ? String(typeEl.value ?? "fixed") : "fixed";

    if (type === "euribor") {
        const tenorEl = document.getElementById("loan-euribor-tenor");
        const tenor = tenorEl ? String(tenorEl.value ?? "3m") : "3m";
        const eur = euriborCache[tenor] || euriborCache["3m"];

        const margin = getElementValue("loan-margin");
        if (!Number.isFinite(margin)) return NaN;
        const eurVal = eur && Number.isFinite(eur.value) ? eur.value : NaN;
        if (!Number.isFinite(eurVal)) return NaN;
        return (eurVal + margin) / 100;
    }

    return getElementValue("loan-rate") / 100;
}

let loanAmortizationChart = null;
let investmentChart = null;

function buildLoanAmortizationSchedule(principal, months, annualRate, moratoriumMonths) {
    const P0 = Number(principal);
    const n = Number(months);
    const rA = Number(annualRate);
    const mor = Math.max(0, Math.min(Number(moratoriumMonths) || 0, n));
    if (!Number.isFinite(P0) || !Number.isFinite(n) || !Number.isFinite(rA) || P0 <= 0 || n <= 0 || rA < 0) return null;

    const rM = rA / 12;
    const amortMonths = Math.max(0, n - mor);
    const annuity = amortMonths > 0 ? calcAnnuityPayment(P0, amortMonths, rA) : 0;

    let balance = P0;
    let cumInterest = 0;

    const labels = [];
    const remainingPrincipal = [];
    const cumulativeInterest = [];

    for (let m = 1; m <= n; m++) {
        const interest = balance * rM;
        let principalPaid = 0;

        if (m > mor && amortMonths > 0) {
            principalPaid = annuity - interest;
            if (!Number.isFinite(principalPaid) || principalPaid < 0) principalPaid = 0;
            if (principalPaid > balance) principalPaid = balance;
            balance -= principalPaid;
        }

        cumInterest += interest;
        labels.push(m);
        remainingPrincipal.push(balance);
        cumulativeInterest.push(cumInterest);
    }

    return {
        labels,
        remainingPrincipal,
        cumulativeInterest,
        annuity,
        amortMonths,
        moratoriumMonths: mor,
    };
}

function drawLoanAmortizationChart(schedule) {
    const canvas = document.getElementById("loan-amortization-chart");
    if (!canvas) return;

    const formatNumberNoDecimals = (val) => {
        const n = Number(val);
        if (!Number.isFinite(n)) return "–";
        const text = n.toLocaleString("sl-SI", { maximumFractionDigits: 0, minimumFractionDigits: 0, useGrouping: true });
        return text;
    };

    if (!schedule) {
        if (loanAmortizationChart) {
            loanAmortizationChart.destroy();
            loanAmortizationChart = null;
        }
        return;
    }

    if (typeof Chart === "undefined") return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    if (loanAmortizationChart) {
        loanAmortizationChart.destroy();
        loanAmortizationChart = null;
    }

    loanAmortizationChart = new Chart(ctx, {
        type: "line",
        data: {
            labels: schedule.labels,
            datasets: [
                {
                    label: "Preostala glavnica",
                    data: schedule.remainingPrincipal,
                    borderColor: "#0B6B3A",
                    backgroundColor: "rgba(11, 107, 58, 0.12)",
                    tension: 0.25,
                    pointRadius: 0,
                    borderWidth: 2,
                },
                {
                    label: "Kumulativne obresti",
                    data: schedule.cumulativeInterest,
                    borderColor: "#6b7280",
                    backgroundColor: "rgba(107, 114, 128, 0.10)",
                    tension: 0.25,
                    pointRadius: 0,
                    borderWidth: 2,
                },
            ],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: { mode: "index", intersect: false },
            plugins: {
                legend: {
                    display: true,
                    position: "bottom",
                    labels: {
                        usePointStyle: true,
                        boxWidth: 10,
                    },
                },
                tooltip: {
                    callbacks: {
                        title: (items) => {
                            const first = Array.isArray(items) && items.length ? items[0] : null;
                            const label = first ? first.label : "";
                            const m = Number(label);
                            if (!Number.isFinite(m)) return "";
                            return `${m} mesecev`;
                        },
                        label: (ctx) => {
                            const v = ctx.parsed.y;
                            return `${ctx.dataset.label}: ${formatNumberNoDecimals(v)}`;
                        },
                    },
                },
            },
            scales: {
                x: {
                    title: { display: true, text: "Čas (meseci)" },
                    ticks: { maxTicksLimit: 12 },
                    grid: { color: "rgba(0,0,0,0.06)" },
                },
                y: {
                    title: { display: true, text: "Znesek (€)" },
                    grid: { color: "rgba(0,0,0,0.06)" },
                    ticks: {
                        callback: (value) => formatNumberNoDecimals(value),
                    },
                },
            },
        },
    });
}

function calculateLoan() {
    try {
        const amount = getElementValue("loan-amount");
        const years = getElementValue("loan-years");
        const rate = getLoanEffectiveAnnualRate();

        const purposeEl = document.getElementById("loan-purpose");
        const purpose = purposeEl ? String(purposeEl.value ?? "").trim() : "";

        const moratorium = getElementValue("loan-moratorium");
        const intercalaryDays = getElementValue("loan-intercalary-days");

        if (!Number.isFinite(rate)) {
            showError("EURIBOR trenutno ni na voljo – poskusite znova čez trenutek");
            return;
        }

        if (!validateInputs(amount, years, rate) || amount <= 0 || years <= 0 || rate < 0) {
            showError("Prosimo vnesite veljavne vrednosti za kreditni kalkulator");
            return;
        }

        const months = years * 12;
        const monthlyRate = rate / 12;

        const safeMoratorium = Math.min(moratorium, months);

        // 1) Interkalarne obresti
        const intercalaryInterest = amount * rate * (intercalaryDays / 365);

        // 2) Obresti v času moratorija (NE kapitalizirajo se)
        const moratoriumInterest = amount * monthlyRate * safeMoratorium;

        // 3) Anuiteta (moratorij ne podaljša ročnosti; v času moratorija se ne odplačuje glavnice)
        const amortMonths = Math.max(1, months - safeMoratorium);
        const monthlyPayment = calcAnnuityPayment(amount, amortMonths, rate);
        const annuityTotalPayment = monthlyPayment * amortMonths;

        // 4) Skupaj plačano
        const totalPayment = moratoriumInterest + annuityTotalPayment + intercalaryInterest;

        // 5) Skupne obresti
        const totalInterest = totalPayment - amount;

        updateLoanResults(
            monthlyPayment,
            totalInterest,
            totalPayment,
            intercalaryInterest,
            amount
        );

        drawLoanAmortizationChart(
            buildLoanAmortizationSchedule(amount, months, rate, safeMoratorium)
        );

        fpTrack("calculator_used", {
            calculator: "loan",
            currency: "EUR",
            amount_eur: Math.round(amount),
            years: Number(years),
            rate_percent: Math.round(rate * 10000) / 100,
            purpose: purpose || undefined,
        });

    } catch (error) {
        console.error("Error in calculateLoan:", error);
        showError("Napaka pri izračunu kredita");
    }
}



function updateLoanResults(monthlyPayment, totalInterest, totalPayment, intercalaryInterest, newPrincipal) {
    setElementText("loan-monthly", formatSI(monthlyPayment));
    setElementText("loan-interest", formatSI(totalInterest));
    setElementText("loan-total", formatSI(totalPayment));

    // Novi prikazi
    setElementText("loan-intercalary", formatSI(intercalaryInterest));
    setElementText("loan-principal-after", formatSI(newPrincipal));
}

function initNumberFormatting() {
    const formatThousandsSI = (num) => {
        const n = Number(num);
        if (!Number.isFinite(n)) return "";
        const sign = n < 0 ? "-" : "";
        const intPart = Math.trunc(Math.abs(n));
        return sign + String(intPart).replace(/\B(?=(\d{3})+(?!\d))/g, ".");
    };

    const formatEl = (el) => {
        if (!el) return;
        let raw = String(el.value ?? "").replace(/\./g, "").replace(/,/g, "");
        raw = raw.replace(/\s+/g, "");
        if (raw === "") return;
        if (!isNaN(raw)) {
            el.value = formatThousandsSI(raw);
        }
    };

    document.querySelectorAll(".format-number").forEach((input) => {
        if (input.classList.contains("no-format")) return;

        input.addEventListener("input", function () {
            formatEl(this);
        });
        input.addEventListener("change", function () {
            formatEl(this);
        });
        input.addEventListener("blur", function () {
            formatEl(this);
        });

        // Format initial value on page load
        formatEl(input);
    });
}

// Initialize application
document.addEventListener('DOMContentLoaded', function () {
    console.log("DOM loaded, initializing FinPortal.si");

    const safeInit = (name, fn) => {
        try {
            if (typeof fn === "function") fn();
        } catch (e) {
            console.warn(`${name} init failed`, e);
        }
    };

    safeInit("initShareUi", initShareUi);

    safeInit("initCookieBanner", initCookieBanner);
    safeInit("initMobileMenu", initMobileMenu);

    // Initialize tabs
    safeInit("initTabs", initTabs);

    // Header dropdown: direct links to calculator tabs
    safeInit("headerDropdownLinks", () => {
        document.querySelectorAll('a[data-calc-tab]').forEach((link) => {
            link.addEventListener('click', (e) => {
                e.preventDefault();

                const tabName = link.getAttribute('data-calc-tab');
                const target = document.getElementById('kalkulatorji');

                if (target) {
                    target.scrollIntoView({ behavior: 'smooth', block: 'start' });
                }

                if (tabName) {
                    switchToTab(tabName);
                }

                const details = link.closest('details');
                if (details) {
                    details.removeAttribute('open');
                }
            });
        });
    });

    // Setup calculator event listeners
    const calculators = [
        { id: "loan-calc-btn", handler: calculateLoan, name: "Loan" },
        { id: "interest-calc-btn", handler: calculateDeposit, name: "Interest" },
        { id: "inv-calc-btn", handler: calculateInvestment, name: "Investment" }
    ];

    calculators.forEach(calc => {
        const button = document.getElementById(calc.id);
        if (button) {
            button.addEventListener("click", calc.handler);
            console.log(`${calc.name} calculator button listener attached`);
        } else {
            console.warn(`${calc.name} calculator button not found: ${calc.id}`);
        }
    });

    // Setup special button effects
    safeInit("setupButtonEffects", setupButtonEffects);

    // Initialize deposit table + dropdown (fallback data), then try to load from latest.csv
    safeInit("renderDepositTable", renderDepositTable);
    safeInit("renderBankDropdown", renderBankDropdown);
    safeInit("initDepositUiBindings", initDepositUiBindings);
    safeInit("initLoanUiBindings", initLoanUiBindings);
    safeInit("initLeasingVsLoanBindings", initLeasingVsLoanBindings);
    safeInit("initEomUiBindings", initEomUiBindings);
    safeInit("initCreditworthinessBindings", initCreditworthinessBindings);
    safeInit("initLostInterestBindings", initLostInterestBindings);
    safeInit("initFxBindings", initFxBindings);
    safeInit("loadDepositOffersFromCsv", loadDepositOffersFromCsv);

    // Initialize formatting for numeric inputs
    safeInit("initNumberFormatting", initNumberFormatting);

    // Normalize rate inputs to two decimals + decimal comma
    normalizeRateInput("loan-rate");
    normalizeRateInput("interest-rate");
    normalizeRateInput("inv-return");
    normalizeRateInput("loan-margin");
    normalizeRateInput("eom-nominal-rate");
    normalizeRateInput("eom-upfront-percent");
    normalizeRateInput("cs-rate");
    normalizeRateInput("cs-dsti");
    normalizeRateInput("cs-safety");
    normalizeRateInput("lost-rate");
    normalizeRateInput("lost-etf-return");
    normalizeRateInput("lost-etf-fee");
    normalizeRateInput("fx-spread");

    safeInit("initShareUi", initShareUi);

    const csRateEl = document.getElementById("cs-rate");
    if (csRateEl) {
        csRateEl.addEventListener("blur", () => normalizeRateInput("cs-rate"));
    }

    const loanRateEl = document.getElementById("loan-rate");
    if (loanRateEl) {
        loanRateEl.addEventListener("blur", () => normalizeRateInput("loan-rate"));
    }

    const invReturnEl = document.getElementById("inv-return");
    if (invReturnEl) {
        invReturnEl.addEventListener("blur", () => normalizeRateInput("inv-return"));
    }

    const loanMarginEl = document.getElementById("loan-margin");
    if (loanMarginEl) {
        loanMarginEl.addEventListener("blur", () => normalizeRateInput("loan-margin"));
    }

    const loanRateTypeEl = document.getElementById("loan-rate-type");
    if (loanRateTypeEl) {
        loanRateTypeEl.addEventListener("change", updateLoanRateUi);
        loanRateTypeEl.addEventListener("input", updateLoanRateUi);
    }

    const loanEuriborTenorEl = document.getElementById("loan-euribor-tenor");
    if (loanEuriborTenorEl) {
        loanEuriborTenorEl.addEventListener("change", updateLoanRateUi);
        loanEuriborTenorEl.addEventListener("input", updateLoanRateUi);
    }

    if (loanMarginEl) {
        loanMarginEl.addEventListener("change", updateLoanRateUi);
        loanMarginEl.addEventListener("input", updateLoanRateUi);
    }

    if (loanRateTypeEl) {
        updateLoanRateUi();
        loadEuriborRates();
    }

    initDepositCompareBindings();

    const invSaveBtn = document.getElementById("inv-save-chart-btn");
    if (invSaveBtn) {
        invSaveBtn.addEventListener("click", () => {
            if (Array.isArray(invSavedSeries) && invSavedSeries.length >= 2) {
                invSavedSeries = null;
                invSavedMetrics = null;
                setDiffVisibility(false);
                setInvSaveButtonPressed(false);
                drawInvestmentChart(invLastSeries, null);
                return;
            }

            if (!Array.isArray(invLastSeries) || invLastSeries.length < 2) return;
            invSavedSeries = invLastSeries.map(p => ({ month: p.month, value: p.value }));
            if (invLastMetrics) {
                invSavedMetrics = { ...invLastMetrics };
            }
            setDiffVisibility(false);
            setInvSaveButtonPressed(true);
            // After saving, show only the baseline (gray). The new comparison (green) appears on the next calculation.
            drawInvestmentChart(null, invSavedSeries);
        });
    }

    console.log("FinPortal.si initialization complete");
});

function updateLoanOfferLink() {
    const bankSelect = document.getElementById("loan-bank");
    const offerLink = document.getElementById("loan-offer-link");

    if (!bankSelect || !offerLink) return;

    const bank = String(bankSelect.value ?? "").trim();
    if (!bank) {
        offerLink.classList.add("hidden");
        offerLink.setAttribute("aria-disabled", "true");
        offerLink.href = "#";
        return;
    }

    const purposeEl = document.getElementById("loan-purpose");
    const purposeVal = purposeEl ? String(purposeEl.value ?? "").trim() : "";
    const purposeText = purposeVal && purposeEl ? String(purposeEl.options?.[purposeEl.selectedIndex]?.text ?? "").trim() : "";
    const query = encodeURIComponent(`${bank}${purposeText ? ` ${purposeText}` : ""} ponudba`);
    offerLink.href = `https://www.google.com/search?q=${query}`;
    offerLink.classList.remove("hidden");
    offerLink.setAttribute("aria-disabled", "false");
}

function initLoanUiBindings() {
    const bankSelect = document.getElementById("loan-bank");
    if (bankSelect) {
        bankSelect.addEventListener("change", updateLoanOfferLink);
        bankSelect.addEventListener("input", updateLoanOfferLink);
    }

    const purposeEl = document.getElementById("loan-purpose");
    if (purposeEl) {
        purposeEl.addEventListener("change", updateLoanOfferLink);
        purposeEl.addEventListener("input", updateLoanOfferLink);
    }

    const offerLink = document.getElementById("loan-offer-link");
    if (offerLink) {
        offerLink.addEventListener("click", (e) => {
            const disabled = offerLink.getAttribute("aria-disabled") === "true";
            const href = String(offerLink.getAttribute("href") ?? "").trim();
            if (disabled || href === "" || href === "#") {
                e.preventDefault();
                return;
            }

            if (fpHasAnalyticsConsent() && window.__fpGa4Enabled && typeof window.gtag === "function") {
                e.preventDefault();

                let navigated = false;
                const navigate = () => {
                    if (navigated) return;
                    navigated = true;
                    window.location.href = href;
                };

                fpTrack(
                    "bank_offer_click",
                    { calculator: "loan", url: href },
                    {
                        transport_type: "beacon",
                        event_callback: navigate,
                    }
                );

                setTimeout(navigate, 450);
            }
        });
    }

    updateLoanOfferLink();
}

// Button effects setup
function setupButtonEffects() {
    // Pridobi ponudbo button glow effect
    document.querySelectorAll('.pridobi-btn').forEach((pridobiBtn) => {
        pridobiBtn.addEventListener('mouseenter', function () {
            this.style.boxShadow = '0 0 8px rgba(242, 201, 76, 0.45), 0 0 18px rgba(242, 201, 76, 0.7)';
            this.style.transform = 'translateY(-2px) scale(1.02)';
            this.style.borderColor = 'var(--highlight)';
            this.style.transition = 'all 0.28s cubic-bezier(0.4, 0, 0.2, 1)';
        });

        pridobiBtn.addEventListener('mouseleave', function () {
            this.style.boxShadow = 'none';
            this.style.transform = 'none';
            this.style.borderColor = 'inherit';
        });
    });

    if (document.querySelectorAll('.pridobi-btn').length > 0) {
        console.log("Pridobi ponudbo button effects attached");
    }
}

/* ============================
   DEPOZITNI KALKULATOR
============================ */

function calculateDeposit() {
    console.log("calculateDeposit called");
    const P = getElementValue("interest-amount");
    const monthsEl = document.getElementById("interest-months");
    const months = monthsEl ? parseFloat(monthsEl.value) : NaN;
    const years = Number.isFinite(months) ? months / 12 : NaN;
    const rate = getElementValue("interest-rate") / 100;

    console.log("Deposit inputs:", { P, months, years, rate });

    if (isNaN(P) || isNaN(months) || isNaN(years) || isNaN(rate) || P <= 0 || months <= 0 || rate < 0) {
        console.log("Invalid deposit inputs");
        return;
    }

    // letno obrestovanje
    const grossFinalAmount = P * Math.pow(1 + rate, years);
    const grossInterest = grossFinalAmount - P;

    // RS: obresti (depoziti) – oprostitev do 1.000 €, nad tem 25% davek
    const exemptInterest = 1000;
    const taxRate = 0.25;
    const taxableInterest = Math.max(0, grossInterest - exemptInterest);
    const tax = taxableInterest * taxRate;
    const netInterest = grossInterest - tax;
    const netFinalAmount = grossFinalAmount - tax;

    console.log("Deposit results:", { grossFinalAmount, grossInterest, tax, netInterest, netFinalAmount });

    const totalEl = document.getElementById("interest-total");
    if (totalEl) totalEl.textContent = formatSI(netFinalAmount);

    const interestGrossEl = document.getElementById("interest-interest-gross");
    if (interestGrossEl) interestGrossEl.textContent = formatSI(grossInterest);

    const taxEl = document.getElementById("interest-tax");
    if (taxEl) taxEl.textContent = formatSI(tax);

    const interestNetEl = document.getElementById("interest-interest");
    if (interestNetEl) interestNetEl.textContent = formatSI(netInterest);

    fpTrack("calculator_used", {
        calculator: "deposit",
        currency: "EUR",
        amount_eur: Math.round(P),
        months: Number(months),
        rate_percent: Math.round((rate * 100) * 100) / 100,
    });
}

/* ============================
   INVESTICIJSKI KALKULATOR
============================ */

let invLastSeries = null;
let invSavedSeries = null;
let invLastMetrics = null;
let invSavedMetrics = null;

function formatDeltaSI(delta) {
    const n = Number(delta);
    if (!Number.isFinite(n) || n === 0) return formatSI(0);
    const sign = n > 0 ? "+" : "-";
    return sign + formatSI(Math.abs(n));
}

function setDiffVisibility(visible) {
    const wrapper = document.getElementById("inv-diff-wrapper");
    if (!wrapper) return;
    if (visible) wrapper.classList.remove("hidden");
    else wrapper.classList.add("hidden");
}

function setInvSaveButtonPressed(pressed) {
    const btn = document.getElementById("inv-save-chart-btn");
    if (!btn) return;

    if (pressed) {
        btn.classList.remove("bg-gray-900", "text-white", "hover:bg-gray-800");
        btn.classList.add("bg-gray-300", "text-gray-900");
        btn.textContent = "IZBRIŠI IZRAČUN";
    } else {
        btn.classList.remove("bg-gray-300", "text-gray-900");
        btn.classList.add("bg-gray-900", "text-white", "hover:bg-gray-800");
        btn.textContent = "Shrani za primerjavo";
    }
}

function updateInvestmentDiff(currentMetrics) {
    if (!invSavedMetrics || !currentMetrics) {
        setDiffVisibility(false);
        return;
    }

    const setDelta = (id, delta) => {
        setElementText(id, formatDeltaSI(delta));
        const el = document.getElementById(id);
        if (!el) return;
        if (delta < 0) {
            el.classList.add("text-red-600");
        } else {
            el.classList.remove("text-red-600");
        }
    };

    setDiffVisibility(true);
    setDelta("inv-diff-final", currentMetrics.finalValue - invSavedMetrics.finalValue);
    setDelta("inv-diff-contrib", currentMetrics.contributed - invSavedMetrics.contributed);
    setDelta("inv-diff-earn", currentMetrics.earnings - invSavedMetrics.earnings);
}

function calculateInvestment() {
    console.log("calculateInvestment called");
    const initial = getElementValue("inv-initial");
    const monthly = getElementValue("inv-monthly");
    const years = parseFloat(document.getElementById("inv-years").value);
    const rate = getElementValue("inv-return") / 100;

    console.log("Investment inputs:", { initial, monthly, years, rate });

    if (isNaN(initial) || isNaN(monthly) || isNaN(years) || isNaN(rate) || initial < 0 || monthly < 0 || years <= 0 || rate < 0) {
        console.log("Invalid investment inputs");
        invLastSeries = null;
        invLastMetrics = null;
        updateInvestmentDiff(null);
        drawInvestmentChart(null, invSavedSeries);
        return;
    }

    // If a baseline exists, keep the save button visually pressed.
    setInvSaveButtonPressed(Array.isArray(invSavedSeries) && invSavedSeries.length >= 2);

    const months = years * 12;
    const monthlyRate = rate / 12;

    // prihodnost začetnega vložka
    const futureInitial = initial * Math.pow(1 + monthlyRate, months);

    // prihodnost mesečnih vložkov
    const futureMonthly =
        monthlyRate === 0
            ? monthly * months
            : monthly * ((Math.pow(1 + monthlyRate, months) - 1) / monthlyRate);

    const finalValue = futureInitial + futureMonthly;
    const contributed = initial + monthly * months;
    const earnings = finalValue - contributed;

    console.log("Investment results:", { finalValue, contributed, earnings });

    document.getElementById("inv-final").textContent = formatSI(finalValue);
    document.getElementById("inv-contrib").textContent = formatSI(contributed);
    document.getElementById("inv-earn").textContent = formatSI(earnings);

    invLastMetrics = { finalValue, contributed, earnings };
    updateInvestmentDiff(invLastMetrics);

    const series = buildInvestmentSeries(initial, monthly, months, monthlyRate);
    invLastSeries = series;
    drawInvestmentChart(series, invSavedSeries);

    fpTrack("calculator_used", {
        calculator: "investment",
        currency: "EUR",
        initial_eur: Math.round(initial),
        monthly_eur: Math.round(monthly),
        years: Number(years),
        rate_percent: Math.round((rate * 100) * 100) / 100,
    });
}

function buildInvestmentSeries(initial, monthly, months, monthlyRate) {
    const points = [];
    let value = 0;

    for (let m = 0; m <= months; m++) {
        if (m === 0) {
            value = initial;
        } else {
            value = value * (1 + monthlyRate) + monthly;
        }
        points.push({ month: m, value });
    }

    return points;
}

function formatAxisCurrency(val) {
    const n = Number(val);
    if (!Number.isFinite(n)) return "0";
    return n.toLocaleString("sl-SI", { maximumFractionDigits: 0, useGrouping: true });
}

function niceStep(rawStep) {
    const n = Number(rawStep);
    if (!Number.isFinite(n) || n <= 0) return 1;

    const exp = Math.floor(Math.log10(n));
    const base = Math.pow(10, exp);
    const frac = n / base;

    let niceFrac;
    if (frac <= 1) niceFrac = 1;
    else if (frac <= 2) niceFrac = 2;
    else if (frac <= 5) niceFrac = 5;
    else niceFrac = 10;

    return niceFrac * base;
}

function drawInvestmentChart(series, savedSeries) {
    const canvas = document.getElementById("inv-chart");
    if (!canvas) return;

    if (typeof Chart !== "undefined") {
        const formatNumberNoDecimals = (val) => {
            const n = Number(val);
            if (!Number.isFinite(n)) return "–";
            return n.toLocaleString("sl-SI", { maximumFractionDigits: 0, minimumFractionDigits: 0, useGrouping: true });
        };

        const hasCurrent = Array.isArray(series) && series.length >= 2;
        const hasSaved = Array.isArray(savedSeries) && savedSeries.length >= 2;

        if (!hasCurrent && !hasSaved) {
            if (investmentChart) {
                investmentChart.destroy();
                investmentChart = null;
            }
            return;
        }

        const seriesForX = hasCurrent ? series : savedSeries;
        const labels = seriesForX.map((p) => p.month);

        const datasets = [];
        if (hasSaved) {
            datasets.push({
                label: "1. izračun (shranjeno)",
                data: savedSeries.map((p) => p.value),
                borderColor: "#9ca3af",
                backgroundColor: "rgba(156, 163, 175, 0.10)",
                tension: 0.25,
                pointRadius: 0,
                borderWidth: 2,
            });
        }
        if (hasCurrent) {
            datasets.push({
                label: "2. izračun (trenutno)",
                data: series.map((p) => p.value),
                borderColor: "#0B6B3A",
                backgroundColor: "rgba(11, 107, 58, 0.12)",
                tension: 0.25,
                pointRadius: 0,
                borderWidth: 2,
            });
        }

        const ctx = canvas.getContext("2d");
        if (!ctx) return;

        if (investmentChart) {
            investmentChart.destroy();
            investmentChart = null;
        }

        investmentChart = new Chart(ctx, {
            type: "line",
            data: {
                labels,
                datasets,
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: { mode: "index", intersect: false },
                plugins: {
                    legend: {
                        display: true,
                        position: "bottom",
                        labels: {
                            usePointStyle: true,
                            boxWidth: 10,
                        },
                    },
                    tooltip: {
                        callbacks: {
                            title: (items) => {
                                const first = Array.isArray(items) && items.length ? items[0] : null;
                                const m = first ? Number(first.label) : NaN;
                                if (!Number.isFinite(m)) return "";
                                if (m === 12) return "1 leto";
                                if (m % 12 === 0 && m > 0) return `${m / 12} leta`;
                                return `${m} mesecev`;
                            },
                            label: (ctx) => {
                                const v = ctx.parsed.y;
                                return `${ctx.dataset.label}: ${formatNumberNoDecimals(v)} €`;
                            },
                        },
                    },
                },
                scales: {
                    x: {
                        title: { display: true, text: "Čas (meseci)" },
                        ticks: {
                            maxTicksLimit: 8,
                            callback: (value) => {
                                const m = Number(value);
                                if (!Number.isFinite(m)) return value;
                                if (m === 0) return "0";
                                if (m === 12) return "1L";
                                if (m % 12 === 0) return `${m / 12}L`;
                                return `${m}`;
                            },
                        },
                        grid: { color: "rgba(0,0,0,0.06)" },
                    },
                    y: {
                        title: { display: true, text: "Vrednost (€)" },
                        grid: { color: "rgba(0,0,0,0.06)" },
                        ticks: { callback: (value) => formatNumberNoDecimals(value) },
                    },
                },
            },
        });

        return;
    }

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const cssWidth = canvas.clientWidth || canvas.width;
    const cssHeight = canvas.clientHeight || 180;
    const dpr = window.devicePixelRatio || 1;
    const width = Math.max(1, Math.floor(cssWidth * dpr));
    const height = Math.max(1, Math.floor(cssHeight * dpr));

    if (canvas.width !== width) canvas.width = width;
    if (canvas.height !== height) canvas.height = height;

    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.scale(dpr, dpr);

    const w = width / dpr;
    const h = height / dpr;

    ctx.clearRect(0, 0, w, h);

    const hasCurrent = Array.isArray(series) && series.length >= 2;
    const hasSaved = Array.isArray(savedSeries) && savedSeries.length >= 2;
    if (!hasCurrent && !hasSaved) {
        return;
    }

    const seriesForX = hasCurrent ? series : savedSeries;
    const maxX = seriesForX[seriesForX.length - 1].month;
    const values = [];
    if (hasSaved) values.push(...savedSeries.map(p => p.value));
    if (hasCurrent) values.push(...series.map(p => p.value));
    const minY = 0;
    const maxYRaw = Math.max(...values);
    const gridLines = 4;
    const stepY = niceStep((maxYRaw - minY) / gridLines || 1);
    const maxY = Math.max(stepY, Math.ceil(maxYRaw / stepY) * stepY);

    // Dynamic left padding so long y-axis labels are not clipped
    ctx.font = "12px Inter, system-ui, sans-serif";
    let widest = 0;
    for (let i = 0; i <= gridLines; i++) {
        const yVal = maxY - i * stepY;
        const label = formatAxisCurrency(yVal);
        widest = Math.max(widest, ctx.measureText(label).width);
    }

    const padding = {
        left: Math.max(44, Math.ceil(widest + 52)),
        right: 12,
        top: 10,
        bottom: 52
    };
    const plotW = Math.max(1, w - padding.left - padding.right);
    const plotH = Math.max(1, h - padding.top - padding.bottom);

    const xToPx = (month) => padding.left + (maxX === 0 ? 0 : (month / maxX) * plotW);
    const yToPx = (val) => padding.top + (1 - (val - minY) / (maxY - minY || 1)) * plotH;

    // Tooltip + legend (consistent UX with other calculators)
    // Attach hover handlers once.
    if (!canvas.__invHoverBound) {
        canvas.__invHoverBound = true;

        const ensureTooltip = () => {
            const parent = canvas.parentElement;
            if (!parent) return null;
            if (getComputedStyle(parent).position === "static") parent.style.position = "relative";

            let tip = parent.querySelector("#inv-chart-tooltip");
            if (!tip) {
                tip = document.createElement("div");
                tip.id = "inv-chart-tooltip";
                tip.style.position = "absolute";
                tip.style.pointerEvents = "none";
                tip.style.display = "none";
                tip.style.zIndex = "20";
                tip.style.background = "rgba(17, 17, 17, 0.92)";
                tip.style.color = "#fff";
                tip.style.padding = "8px 10px";
                tip.style.borderRadius = "10px";
                tip.style.fontSize = "12px";
                tip.style.lineHeight = "1.2";
                tip.style.maxWidth = "240px";
                parent.appendChild(tip);
            }
            return tip;
        };

        const formatNumberNoDecimals = (val) => {
            const n = Number(val);
            if (!Number.isFinite(n)) return "–";
            return n.toLocaleString("sl-SI", { maximumFractionDigits: 0, minimumFractionDigits: 0, useGrouping: true });
        };

        const formatEuro = (val) => `${formatNumberNoDecimals(val)} €`;

        canvas.addEventListener("mouseleave", () => {
            const parent = canvas.parentElement;
            const tip = parent ? parent.querySelector("#inv-chart-tooltip") : null;
            if (tip) tip.style.display = "none";
        });

        canvas.addEventListener("mousemove", (ev) => {
            const state = canvas.__invChartState;
            if (!state) return;

            const rect = canvas.getBoundingClientRect();
            const x = ev.clientX - rect.left;
            const y = ev.clientY - rect.top;

            // Ignore hover outside plot area.
            if (x < state.padding.left || x > state.padding.left + state.plotW || y < state.padding.top || y > state.padding.top + state.plotH) {
                const tip = ensureTooltip();
                if (tip) tip.style.display = "none";
                return;
            }

            const rel = (x - state.padding.left) / (state.plotW || 1);
            const month = Math.max(0, Math.min(state.maxX, Math.round(rel * state.maxX)));

            const currentPoint = state.hasCurrent && Array.isArray(state.series) ? state.series[month] : null;
            const savedPoint = state.hasSaved && Array.isArray(state.savedSeries) ? state.savedSeries[month] : null;

            if (!currentPoint && !savedPoint) return;

            const tip = ensureTooltip();
            if (!tip) return;

            const title = month === 12 ? "1 leto" : (month > 0 && month % 12 === 0 ? `${month / 12} leta` : `${month} mesecev`);
            const lines = [];
            lines.push(`<div style="font-weight:600; margin-bottom:6px;">${title}</div>`);
            if (savedPoint) lines.push(`<div><span style="display:inline-block; width:10px; height:10px; border-radius:999px; background:#9ca3af; margin-right:8px;"></span>1. izračun: ${formatEuro(savedPoint.value)}</div>`);
            if (currentPoint) lines.push(`<div style="margin-top:4px;"><span style="display:inline-block; width:10px; height:10px; border-radius:999px; background:#0B6B3A; margin-right:8px;"></span>2. izračun: ${formatEuro(currentPoint.value)}</div>`);
            tip.innerHTML = lines.join("");

            const left = Math.min(Math.max(0, x + 14), rect.width - 10);
            const top = Math.min(Math.max(0, y + 14), rect.height - 10);
            tip.style.left = `${left}px`;
            tip.style.top = `${top}px`;
            tip.style.display = "block";
        });
    }

    // Ensure a consistent legend with circular markers.
    const legendParent = canvas.parentElement ? canvas.parentElement.parentElement : null;
    if (legendParent) {
        let legend = legendParent.querySelector("#inv-chart-legend");
        if (!legend) {
            legend = document.createElement("div");
            legend.id = "inv-chart-legend";
            legend.style.display = "flex";
            legend.style.flexWrap = "wrap";
            legend.style.gap = "12px";
            legend.style.marginTop = "10px";
            legend.style.justifyContent = "flex-start";
            legend.style.fontSize = "12px";
            legend.style.color = "#374151";
            legendParent.appendChild(legend);
        }

        const mkItem = (color, text) => {
            const item = document.createElement("div");
            item.style.display = "flex";
            item.style.alignItems = "center";
            item.style.gap = "8px";
            const dot = document.createElement("span");
            dot.style.width = "10px";
            dot.style.height = "10px";
            dot.style.borderRadius = "999px";
            dot.style.background = color;
            const label = document.createElement("span");
            label.textContent = text;
            item.appendChild(dot);
            item.appendChild(label);
            return item;
        };

        legend.innerHTML = "";
        if (hasSaved) legend.appendChild(mkItem("#9ca3af", "1. izračun (shranjeno)"));
        if (hasCurrent) legend.appendChild(mkItem("#0B6B3A", "2. izračun (trenutno)"));
    }

    ctx.fillStyle = "#111111";
    ctx.font = "12px Inter, system-ui, sans-serif";
    ctx.textAlign = "right";
    ctx.textBaseline = "middle";

    for (let i = 0; i <= gridLines; i++) {
        const t = i / gridLines;
        const yVal = maxY - i * stepY;
        const y = padding.top + t * plotH;

        // Grid lines (skip bottom line so the x-axis stays crisp/black)
        if (i !== gridLines) {
            ctx.strokeStyle = "#f3f4f6";
            ctx.beginPath();
            ctx.moveTo(padding.left, y);
            ctx.lineTo(padding.left + plotW, y);
            ctx.stroke();
        }

        const label = formatAxisCurrency(yVal);
        ctx.fillText(label, padding.left - 8, y);
    }

    // Axes (draw after grid so they stay dark)
    ctx.strokeStyle = "#111111";
    ctx.lineWidth = 1.25;
    ctx.beginPath();
    ctx.moveTo(padding.left, padding.top);
    ctx.lineTo(padding.left, padding.top + plotH);
    ctx.lineTo(padding.left + plotW, padding.top + plotH);
    ctx.stroke();

    if (hasSaved) {
        ctx.strokeStyle = "#9ca3af";
        ctx.lineWidth = 2;
        ctx.beginPath();
        for (let i = 0; i < savedSeries.length; i++) {
            const p = savedSeries[i];
            const x = xToPx(p.month);
            const y = yToPx(p.value);
            if (i === 0) ctx.moveTo(x, y);
            else ctx.lineTo(x, y);
        }
        ctx.stroke();
    }

    if (hasCurrent) {
        ctx.strokeStyle = "#0B6B3A";
        ctx.lineWidth = 2;
        ctx.beginPath();
        for (let i = 0; i < series.length; i++) {
            const p = series[i];
            const x = xToPx(p.month);
            const y = yToPx(p.value);
            if (i === 0) ctx.moveTo(x, y);
            else ctx.lineTo(x, y);
        }
        ctx.stroke();
    }

    ctx.strokeStyle = hasCurrent ? "rgba(11, 107, 58, 0.25)" : "rgba(156, 163, 175, 0.35)";
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(xToPx(maxX), padding.top);
    ctx.lineTo(xToPx(maxX), padding.top + plotH);
    ctx.stroke();

    // X-axis tick marks + labels
    const maxMonths = maxX;
    const desiredTicks = 6;
    const step = maxMonths <= 0 ? 1 : Math.max(1, Math.round(maxMonths / (desiredTicks - 1)));
    ctx.font = "12px Inter, system-ui, sans-serif";
    ctx.fillStyle = "#111111";
    ctx.textAlign = "center";
    ctx.textBaseline = "top";
    ctx.strokeStyle = "#111111";
    ctx.lineWidth = 1;

    const ticks = [];
    for (let m = 0; m <= maxMonths; m += step) ticks.push(m);
    if (maxMonths > 0 && ticks[ticks.length - 1] !== maxMonths) ticks.push(maxMonths);

    // Prevent overlap: if last tick is too close to previous tick, drop the previous
    if (ticks.length >= 2) {
        const last = ticks[ticks.length - 1];
        const prev = ticks[ticks.length - 2];
        const dx = xToPx(last) - xToPx(prev);
        if (dx < 24) {
            ticks.splice(ticks.length - 2, 1);
        }
    }

    for (let i = 0; i < ticks.length; i++) {
        const m = ticks[i];
        const isLast = i === ticks.length - 1;
        const x = xToPx(m);
        const y0 = padding.top + plotH;
        const y1 = y0 + 5;

        ctx.beginPath();
        ctx.moveTo(x, y0);
        ctx.lineTo(x, y1);
        ctx.stroke();

        // Right-align the last label so it doesn't clip/overlap at the chart edge
        if (isLast) {
            ctx.textAlign = "right";
            ctx.fillText(String(m), padding.left + plotW, y1 + 4);
            ctx.textAlign = "center";
        } else {
            ctx.fillText(String(m), x, y1 + 4);
        }
    }

    // Axis titles (draw after tick labels so we can place them below)
    ctx.fillStyle = "#111111";
    ctx.font = "12px Inter, system-ui, sans-serif";

    // X axis title (below tick labels)
    ctx.textAlign = "center";
    ctx.textBaseline = "top";
    ctx.fillText("Obdobje (meseci)", padding.left + plotW / 2, padding.top + plotH + 28);

    // Y axis title (rotated, placed left of y-axis labels)
    const yTitleX = Math.max(10, Math.floor(padding.left - widest - 40));
    ctx.save();
    ctx.translate(yTitleX, padding.top + plotH / 2);
    ctx.rotate(-Math.PI / 2);
    ctx.textAlign = "center";
    ctx.textBaseline = "top";
    ctx.fillText("Vrednost (€)", 0, 0);
    ctx.restore();

    ctx.textAlign = "right";
    ctx.fillStyle = "#0B6B3A";
    if (hasCurrent) {
        ctx.fillText(formatSI(series[series.length - 1].value), padding.left + plotW, padding.top + 2);
    } else if (hasSaved) {
        ctx.fillStyle = "#6b7280";
        ctx.fillText(formatSI(savedSeries[savedSeries.length - 1].value), padding.left + plotW, padding.top + 2);
    }

    // Store render state for hover tooltip.
    canvas.__invChartState = {
        hasCurrent,
        hasSaved,
        series,
        savedSeries,
        maxX,
        padding,
        plotW,
        plotH,
    };
}

/* ============================
   DEPOZITI – PODATKI
============================ */

const depositOffers = [
    { bank: "NLB", rate: 3.50, termMonths: 12, term: "12 mesecev (kratkoročni)", min: 1000, url: "" },
    { bank: "OTP banka", rate: 3.65, termMonths: 24, term: "24 mesecev (dolgoročni)", min: 1000, url: "" },
    { bank: "SKB", rate: 3.60, termMonths: 24, term: "24 mesecev (dolgoročni)", min: 1500, url: "" },
    { bank: "Addiko Bank", rate: 3.80, termMonths: 36, term: "36 mesecev (dolgoročni)", min: 1000, url: "" },
    { bank: "Sparkasse", rate: 3.45, termMonths: 12, term: "12 mesecev (kratkoročni)", min: 1000, url: "" },
    { bank: "UniCredit", rate: 3.40, termMonths: 12, term: "12 mesecev (kratkoročni)", min: 500, url: "" },
    { bank: "Deželna banka", rate: 3.55, termMonths: 18, term: "18 mesecev (dolgoročni)", min: 500, url: "" }
];

function termTypeLabel(termMonths) {
    const months = Number(termMonths);
    if (!Number.isFinite(months)) return "";
    return months >= 13 ? "dolgoročni" : "kratkoročni";
}

function formatTermLabel(termMonths) {
    const months = Number(termMonths);
    if (!Number.isFinite(months)) return "";
    const type = termTypeLabel(months);
    return `${months} mesecev (${type})`;
}

function getDepositCompareTermMonths() {
    const termEl = document.getElementById("deposit-compare-term");
    const unitEl = document.getElementById("deposit-compare-unit");
    const term = termEl ? Number(termEl.value) : NaN;
    const unit = unitEl ? String(unitEl.value ?? "months") : "months";

    if (!Number.isFinite(term) || term <= 0) return null;
    if (unit === "days") {
        // Map day input to the starting day-bucket for months:
        // 31–60d -> 1M, 61–90d -> 2M, 91–120d -> 3M, ...
        const days = Math.round(Number(term));
        if (!Number.isFinite(days) || days <= 0) return null;
        if (days < 30) return null;
        if (days < 31) return null;
        return Math.max(1, 1 + Math.floor((days - 31) / 30));
    }
    return term;
}

function getDepositCompareTermUnit() {
    const unitEl = document.getElementById("deposit-compare-unit");
    return unitEl ? String(unitEl.value ?? "months") : "months";
}

function detectDelimiter(headerLine) {
    const semicolons = (headerLine.match(/;/g) || []).length;
    const commas = (headerLine.match(/,/g) || []).length;
    return semicolons >= commas ? ";" : ",";
}

function parseDateFlexibleToUtcYmd(s) {
    const raw = String(s ?? "").trim();
    if (!raw) return "";

    // Supported inputs:
    // - YYYY-MM-DD
    // - DD/MM/YYYY
    // - DD.MM.YYYY
    // - ISO timestamps
    const mYmd = raw.match(/^(\d{4})-(\d{2})-(\d{2})$/);
    if (mYmd) {
        const [, y, mo, d] = mYmd;
        return `${y}-${mo}-${d}`;
    }

    const mDmySlash = raw.match(/^(\d{2})\/(\d{2})\/(\d{4})$/);
    if (mDmySlash) {
        const [, d, mo, y] = mDmySlash;
        return `${y}-${mo}-${d}`;
    }

    const mDmyDot = raw.match(/^(\d{2})\.(\d{2})\.(\d{4})$/);
    if (mDmyDot) {
        const [, d, mo, y] = mDmyDot;
        return `${y}-${mo}-${d}`;
    }

    const dt = new Date(raw);
    if (!isNaN(dt.getTime())) {
        return dt.toISOString().slice(0, 10);
    }
    return "";
}

function formatDateSl(s) {
    const ymd = parseDateFlexibleToUtcYmd(s);
    if (!ymd) return "";
    const m = ymd.match(/^(\d{4})-(\d{2})-(\d{2})$/);
    if (!m) return "";
    const [, y, mo, d] = m;
    return `${d}.${mo}.${y}`;
}

function parseCsvLineFrontend(line, delimiter) {
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

function toNumberSl(val) {
    if (val === null || val === undefined) return NaN;
    const s = String(val).trim();
    if (s === "") return NaN;

    // Support both SI-style numbers (1.234,56) and dot-decimal (1234.56).
    // Heuristic:
    // - if comma is present => comma is decimal separator, dots are thousands separators
    // - else if multiple dots are present => treat dots as thousands separators (e.g. 1.000.000)
    // - else keep dot as decimal separator (e.g. 1000.0, 1.35)
    const raw = s.replace(/\s+/g, "");
    const dotCount = (raw.match(/\./g) || []).length;
    const normalized = raw.includes(",")
        ? raw.replace(/\./g, "").replace(/,/g, ".")
        : (dotCount >= 2 ? raw.replace(/\./g, "") : raw);
    const n = Number(normalized);
    return Number.isFinite(n) ? n : NaN;
}

async function loadDepositOffersFromCsv() {
    try {
        // Prefer the daily generated all_banks.csv (stable filename, always newest), fallback to ./latest.csv.
        let res = await fetch("./Podatki%20bank/all_banks.csv", { cache: "no-store" });
        let sourceLabel = "all_banks.csv";
        if (!res.ok) {
            res = await fetch("./latest.csv", { cache: "no-store" });
            sourceLabel = "latest.csv";
        }
        if (!res.ok) {
            console.warn("deposit CSV fetch failed", { status: res.status, statusText: res.statusText });
            loadDepositOffersFromJson();
            return;
        }

        const lastModifiedHeader = res.headers.get("last-modified");
        const lastModifiedDate = lastModifiedHeader ? new Date(lastModifiedHeader) : null;
        const lastModifiedYmd = lastModifiedDate && !isNaN(lastModifiedDate.getTime())
            ? lastModifiedDate.toISOString().slice(0, 10)
            : "";
        const lastModifiedSl = lastModifiedYmd ? formatDateSl(lastModifiedYmd) : "";

        const text = await res.text();
        const lines = text.split(/\r?\n/).filter(l => l.trim() !== "");
        if (lines.length < 2) {
            console.warn(`${sourceLabel} empty`);
            loadDepositOffersFromJson();
            return;
        }

        const delimiter = detectDelimiter(lines[0]);
        const headers = parseCsvLineFrontend(lines[0], delimiter).map(h => h.trim());

        const idx = (name) => headers.findIndex(h => h.toLowerCase() === name.toLowerCase());
        const iBank = idx("bank");
        const iUpdated = idx("last_updated");

        // Two supported schemas:
        // 1) legacy/curated: rate_nominal, term_months, min_amount, max_amount
        // 2) all_banks export: rate_branch (regular), rate_klik_total (special/online), min_term, max_term, term_unit, amount_min, amount_max
        const isAllBanks = headers.some(h => h.toLowerCase() === "amount_min") || headers.some(h => h.toLowerCase() === "rate_klik_total");

        const iRateLegacy = idx("rate_nominal");
        const iTermLegacy = idx("term_months");
        const iMinLegacy = idx("min_amount");
        const iMaxLegacy = idx("max_amount");

        const iRateBranch = idx("rate_branch");
        const iRateKlikTotal = idx("rate_klik_total");
        const iRateKlikBonus = idx("rate_klik_bonus");
        const iMinTerm = idx("min_term");
        const iMaxTerm = idx("max_term");
        const iTermUnit = idx("term_unit");
        const iAmountMin = idx("amount_min");
        const iAmountMax = idx("amount_max");
        const iUrl = idx("url");
        const iProductName = idx("product_name");
        const iNotes = idx("notes");
        const iOfferType = idx("offer_type");
        const iSource = idx("source");

        if (iBank === -1 || iUpdated === -1) {
            console.warn(`${sourceLabel} missing required headers`, { headers });
            loadDepositOffersFromJson();
            return;
        }

        if (!isAllBanks && (iRateLegacy === -1 || iTermLegacy === -1 || iMinLegacy === -1)) {
            console.warn(`${sourceLabel} missing legacy deposit headers`, { headers });
            loadDepositOffersFromJson();
            return;
        }

        if (isAllBanks && (iRateBranch === -1 || iRateKlikTotal === -1 || iMinTerm === -1 || iMaxTerm === -1 || iTermUnit === -1 || iAmountMin === -1)) {
            console.warn(`${sourceLabel} missing all_banks headers`, { headers });
            loadDepositOffersFromJson();
            return;
        }

        const parsed = [];
        const seenDates = [];
        for (let li = 1; li < lines.length; li++) {
            const row = parseCsvLineFrontend(lines[li], delimiter);
            let bank = String(row[iBank] ?? "").trim();
            if (bank === "De�elna banka") bank = "Deželna banka";
            const updated = iUpdated !== -1 ? String(row[iUpdated] ?? "").trim() : "";

            const url = iUrl !== -1 ? String(row[iUrl] ?? "").trim() : "";

            const productName = iProductName !== -1 ? String(row[iProductName] ?? "").trim() : "";
            const notes = iNotes !== -1 ? String(row[iNotes] ?? "").trim() : "";
            const offerTypeRaw = iOfferType !== -1 ? String(row[iOfferType] ?? "").trim() : "";
            const offerType = offerTypeRaw.toLowerCase();
            const sourceRaw = iSource !== -1 ? String(row[iSource] ?? "").trim() : "";
            const source = sourceRaw.toLowerCase();
            const specialTxt = `${productName} ${notes}`.toLowerCase();
            const isSpecialOffer = offerType === "special"
                ? true
                : (offerType === "regular" ? false : (specialTxt.includes("posebna ponudba") || specialTxt.includes("akcij") || specialTxt.includes("promo")));

            let rate = NaN;
            let rateSpecial = null;
            let termMonths = NaN;
            let termUnit = "months";
            let termDaysMin = null;
            let termDaysMax = null;
            let termMonthsMin = null;
            let termMonthsMax = null;
            let min = NaN;
            let max = NaN;

            if (isAllBanks) {
                // Keep old behavior: base rate is the regular/branch rate.
                // Special/online rate is only used when user enables the checkbox.
                rate = toNumberSl(row[iRateBranch]);
                const totalKlik = toNumberSl(row[iRateKlikTotal]);
                const bonusKlik = iRateKlikBonus !== -1 ? toNumberSl(row[iRateKlikBonus]) : NaN;
                const hasSpecial = Number.isFinite(totalKlik)
                    && Number.isFinite(rate)
                    && Math.abs(totalKlik - rate) > 1e-9
                    && (!Number.isFinite(bonusKlik) || bonusKlik > 0);
                rateSpecial = hasSpecial ? totalKlik : null;
                const minTerm = toNumberSl(row[iMinTerm]);
                const maxTerm = toNumberSl(row[iMaxTerm]);
                termUnit = String(row[iTermUnit] ?? "").trim().toLowerCase() || "months";
                min = toNumberSl(row[iAmountMin]);
                max = iAmountMax !== -1 ? toNumberSl(row[iAmountMax]) : NaN;

                if (termUnit === "days") {
                    const a = Number.isFinite(minTerm) ? Math.round(minTerm) : NaN;
                    const b = Number.isFinite(maxTerm) ? Math.round(maxTerm) : NaN;
                    termDaysMin = Number.isFinite(a) ? a : null;
                    termDaysMax = Number.isFinite(b) ? b : null;
                    const approxMonths = Number.isFinite(b) ? Math.max(1, Math.round(b / 30.4167)) : NaN;
                    termMonths = approxMonths;
                } else {
                    // months
                    const a = Number.isFinite(minTerm) ? Math.round(minTerm) : NaN;
                    const b = Number.isFinite(maxTerm) ? Math.round(maxTerm) : NaN;
                    termMonthsMin = Number.isFinite(a) ? a : null;
                    termMonthsMax = Number.isFinite(b) ? b : null;
                    if (termMonthsMin !== null && termMonthsMax !== null && termMonthsMin === termMonthsMax) {
                        termMonths = termMonthsMin;
                    } else if (termMonthsMax !== null) {
                        // Keep a representative term for sorting/label, but rely on min/max for matching.
                        termMonths = termMonthsMax;
                    } else if (termMonthsMin !== null) {
                        termMonths = termMonthsMin;
                    }
                }
            } else {
                rate = toNumberSl(row[iRateLegacy]);
                termMonths = toNumberSl(row[iTermLegacy]);
                min = toNumberSl(row[iMinLegacy]);
                max = iMaxLegacy !== -1 ? toNumberSl(row[iMaxLegacy]) : NaN;
                termUnit = "months";
                if (Number.isFinite(termMonths)) {
                    termMonthsMin = Math.round(termMonths);
                    termMonthsMax = Math.round(termMonths);
                }
            }

            if (!bank) continue;
            if (!Number.isFinite(rate) || !Number.isFinite(termMonths) || !Number.isFinite(min)) continue;

            if (updated) {
                const updatedYmd = parseDateFlexibleToUtcYmd(updated);
                if (updatedYmd) seenDates.push(updatedYmd);
            }

            parsed.push({
                bank,
                rateBase: rate,
                rateSpecial,
                termMonths,
                termMonthsMin,
                termMonthsMax,
                term: formatTermLabel(termMonths),
                min,
                max: Number.isFinite(max) ? max : null,
                termUnit,
                termDaysMin,
                termDaysMax,
                url,
                productName,
                notes,
                offerType: offerType || null,
                source: source || null,
                isSpecialOffer
            });
        }

        if (parsed.length === 0) {
            console.warn(`${sourceLabel} loaded but contained 0 usable deposits`);
            loadDepositOffersFromJson();
            return;
        }

        depositOffers.length = 0;
        depositOffers.push(...parsed);

        const dateEl = document.getElementById("deposit-data-date");
        if (dateEl) {
            const maxDateYmd = seenDates.length
                ? seenDates.reduce((a, b) => (String(b) > String(a) ? b : a), seenDates[0])
                : "";
            const maxDateSl = maxDateYmd ? formatDateSl(maxDateYmd) : "";
            const parts = [];
            if (maxDateSl) parts.push(`Datum podatkov: ${maxDateSl}`);
            if (lastModifiedSl) parts.push(`Datoteka posodobljena: ${lastModifiedSl}`);
            dateEl.textContent = parts.join(" | ");
        }

        console.log(`${sourceLabel} loaded`, { deposits: parsed.length });
        renderDepositTable();
        renderBankDropdown();
        updateInterestRate();
    } catch (e) {
        console.warn(`${sourceLabel} load error`, e);
        loadDepositOffersFromJson();
    }
}

async function loadDepositOffersFromJson() {
    try {
        const res = await fetch("./offers.json", { cache: "no-store" });
        if (!res.ok) {
            console.warn("offers.json fetch failed", { status: res.status, statusText: res.statusText });
            loadDepositOffersFromLegacyCsv();
            return;
        }

        const lastModifiedHeader = res.headers.get("last-modified");
        const lastModifiedDate = lastModifiedHeader ? new Date(lastModifiedHeader) : null;
        const lastModifiedYmd = lastModifiedDate && !isNaN(lastModifiedDate.getTime())
            ? lastModifiedDate.toISOString().slice(0, 10)
            : "";

        const data = await res.json();
        if (!data || !Array.isArray(data.deposits)) {
            console.warn("offers.json invalid shape", data);
            loadDepositOffersFromLegacyCsv();
            return;
        }

        const dateEl = document.getElementById("deposit-data-date");
        if (dateEl) {
            const dates = data.deposits
                .map(d => (d && typeof d.last_updated === "string") ? d.last_updated.trim() : "")
                .filter(Boolean);
            const datesYmd = dates.map(parseDateFlexibleToUtcYmd).filter(Boolean);
            const maxDateYmd = datesYmd.length ? datesYmd.reduce((a, b) => (String(b) > String(a) ? b : a), datesYmd[0]) : "";
            const generatedAt = (data && data.meta && typeof data.meta.generated_at === "string")
                ? data.meta.generated_at.slice(0, 10)
                : "";
            const fileDate = lastModifiedYmd || generatedAt;
            const maxDateSl = maxDateYmd ? formatDateSl(maxDateYmd) : "";
            const fileDateSl = fileDate ? formatDateSl(fileDate) : "";
            const parts = [];
            if (maxDateSl) parts.push(`Datum podatkov: ${maxDateSl}`);
            if (fileDateSl) parts.push(`Datoteka posodobljena: ${fileDateSl}`);
            dateEl.textContent = parts.join(" | ");
        }

        const normalized = data.deposits
            .filter(d => d && typeof d.bank === "string")
            .map(d => {
                const termMonths = Number(d.term_months);
                const termDaysMinRaw = d.term_days_min;
                const termDaysMaxRaw = d.term_days_max;
                const termDaysMin = termDaysMinRaw === null || termDaysMinRaw === undefined ? null : Number(termDaysMinRaw);
                const termDaysMax = termDaysMaxRaw === null || termDaysMaxRaw === undefined ? null : Number(termDaysMaxRaw);
                const maxAmount = d.max_amount === null || d.max_amount === undefined ? null : Number(d.max_amount);
                const baseRate = Number(d.rate_nominal);
                const specialRate = d.rate_special === null || d.rate_special === undefined ? NaN : Number(d.rate_special);
                return {
                    bank: d.bank.trim(),
                    rateBase: baseRate,
                    rateSpecial: Number.isFinite(specialRate) ? specialRate : null,
                    termMonths: Number.isFinite(termMonths) ? termMonths : null,
                    term: Number.isFinite(termMonths) ? formatTermLabel(termMonths) : "",
                    min: Number(d.min_amount),
                    max: Number.isFinite(maxAmount) ? maxAmount : null,
                    termUnit: String(d.term_unit ?? "").trim().toLowerCase() || null,
                    termDaysMin: Number.isFinite(termDaysMin) ? termDaysMin : null,
                    termDaysMax: Number.isFinite(termDaysMax) ? termDaysMax : null,
                    url: typeof d.url === "string" ? d.url.trim() : ""
                };
            })
            .filter(d => Number.isFinite(d.rateBase) && Number.isFinite(d.min) && d.bank.trim() !== "");

        if (normalized.length === 0) {
            console.warn("offers.json loaded but contained 0 usable deposits");
            loadDepositOffersFromLegacyCsv();
            return;
        }

        depositOffers.length = 0;
        depositOffers.push(...normalized);

        console.log("offers.json loaded", { deposits: normalized.length });

        renderDepositTable();
        renderBankDropdown();

        // If user already selected a bank/term, re-evaluate the rate.
        updateInterestRate();
    } catch (e) {
        console.warn("offers.json load error", e);
        loadDepositOffersFromLegacyCsv();
    }
}

async function loadDepositOffersFromLegacyCsv() {
    try {
        const res = await fetch("./podatki_depoziti.csv", { cache: "no-store" });
        if (!res.ok) {
            console.warn("podatki_depoziti.csv fetch failed", { status: res.status, statusText: res.statusText });
            return;
        }

        const text = await res.text();
        const lines = text.split(/\r?\n/).filter(l => l.trim() !== "");
        if (lines.length < 2) {
            console.warn("podatki_depoziti.csv empty");
            return;
        }

        const delimiter = detectDelimiter(lines[0]);
        const headers = parseCsvLineFrontend(lines[0], delimiter).map(h => h.trim());

        const idx = (name) => headers.findIndex(h => h.toLowerCase() === name.toLowerCase());
        const iBank = idx("bank");
        const iRate = idx("rate_nominal");
        const iTerm = idx("term_months");
        const iMin = idx("min_amount");
        const iMax = idx("max_amount");
        const iUrl = idx("url");
        const iUpdated = idx("last_updated");

        if (iBank === -1 || iRate === -1 || iTerm === -1 || iMin === -1) {
            console.warn("podatki_depoziti.csv missing required headers", { headers });
            return;
        }

        const parsed = [];
        const seenDates = [];
        for (let li = 1; li < lines.length; li++) {
            const row = parseCsvLineFrontend(lines[li], delimiter);
            let bank = String(row[iBank] ?? "").trim();
            if (bank === "De�elna banka") bank = "Deželna banka";
            const url = iUrl !== -1 ? String(row[iUrl] ?? "").trim() : "";
            const rate = toNumberSl(row[iRate]);
            const termMonths = toNumberSl(row[iTerm]);
            const min = toNumberSl(row[iMin]);
            const max = iMax !== -1 ? toNumberSl(row[iMax]) : NaN;
            const updated = iUpdated !== -1 ? String(row[iUpdated] ?? "").trim() : "";

            if (!bank) continue;
            if (!Number.isFinite(rate) || !Number.isFinite(termMonths) || !Number.isFinite(min)) continue;

            if (updated) {
                seenDates.push(updated);
            }

            parsed.push({
                bank,
                rateBase: rate,
                rateSpecial: null,
                termMonths,
                term: formatTermLabel(termMonths),
                min,
                max: Number.isFinite(max) ? max : null,
                termUnit: "months",
                termDaysMin: null,
                termDaysMax: null,
                url
            });
        }

        if (parsed.length === 0) {
            console.warn("podatki_depoziti.csv loaded but contained 0 usable deposits");
            return;
        }

        depositOffers.length = 0;
        depositOffers.push(...parsed);

        const dateEl = document.getElementById("deposit-data-date");
        if (dateEl) {
            const seenDatesYmd = seenDates.map(parseDateFlexibleToUtcYmd).filter(Boolean);
            const maxDateYmd = seenDatesYmd.length
                ? seenDatesYmd.reduce((a, b) => (String(b) > String(a) ? b : a), seenDatesYmd[0])
                : "";
            const maxDateSl = maxDateYmd ? formatDateSl(maxDateYmd) : "";
            dateEl.textContent = maxDateSl ? `Datum podatkov: ${maxDateSl}` : "";
        }

        console.log("podatki_depoziti.csv loaded", { deposits: parsed.length });
        renderDepositTable();
        renderBankDropdown();
        updateInterestRate();
    } catch (e) {
        console.warn("podatki_depoziti.csv load error", e);
    }
}

/* ============================
   PRIKAZ TABELE DEPOZITOV
============================ */

function pickDepositOffer(offers, opts) {
    const amount = opts && Number.isFinite(opts.amount) ? Number(opts.amount) : NaN;
    const targetTermMonths = opts && opts.targetTermMonths !== undefined ? opts.targetTermMonths : null;
    const targetTermUnit = opts && typeof opts.targetTermUnit === "string" ? opts.targetTermUnit : "months";
    const showSpecial = !!(opts && opts.showSpecial);
    const selectedTermRaw = opts && opts.selectedTerm !== undefined ? opts.selectedTerm : NaN;
    const selectedTerm = Number(selectedTermRaw);

    const effRate = (o) => {
        if (!o) return NaN;
        if (showSpecial && Number.isFinite(o.rateSpecial)) return Number(o.rateSpecial);
        return Number(o.rateBase);
    };

    const monthRangeContains = (o, m) => {
        if (!o || !Number.isFinite(m)) return false;
        const aRaw = o.termMonthsMin;
        const bRaw = o.termMonthsMax;
        const a = aRaw === null || aRaw === undefined ? NaN : Number(aRaw);
        const b = bRaw === null || bRaw === undefined ? NaN : Number(bRaw);
        if (Number.isFinite(a) && Number.isFinite(b)) return m >= a && m <= b;
        if (Number.isFinite(a) && !Number.isFinite(b)) return m >= a;
        if (!Number.isFinite(a) && Number.isFinite(b)) return m <= b;
        return Number.isFinite(o.termMonths) ? Number(o.termMonths) === m : false;
    };

    const monthMin = (o) => {
        const v = o && o.termMonthsMin !== null && o.termMonthsMin !== undefined ? Number(o.termMonthsMin) : NaN;
        return Number.isFinite(v) ? v : Number(o.termMonths);
    };

    const pickMonthThreshold = (pool, targetMonths) => {
        const withTerms = pool.filter(o => Number.isFinite(monthMin(o)));
        if (withTerms.length === 0) return null;

        const minAvailable = withTerms.reduce((m, o) => {
            const mm = monthMin(o);
            return Number.isFinite(mm) && mm < m ? mm : m;
        }, monthMin(withTerms[0]));

        if (Number.isFinite(minAvailable) && targetMonths < minAvailable) {
            const minOffer = withTerms.find(o => monthMin(o) === minAvailable) || withTerms[0];
            return {
                ...minOffer,
                rateBase: NaN,
                rateSpecial: null,
                termMonths: null,
                term: ""
            };
        }

        const eligible = withTerms.filter(o => monthMin(o) <= targetMonths);
        if (eligible.length === 0) {
            const minOffer = withTerms.find(o => monthMin(o) === minAvailable) || withTerms[0];
            return {
                ...minOffer,
                rateBase: NaN,
                rateSpecial: null,
                termMonths: null,
                term: ""
            };
        }

        return eligible.reduce((best, cur) => {
            const bestMin = monthMin(best);
            const curMin = monthMin(cur);
            if (curMin !== bestMin) return curMin > bestMin ? cur : best;
            return (effRate(cur) ?? 0) > (effRate(best) ?? 0) ? cur : best;
        }, eligible[0]);
    };

    const pickDaysThreshold = (pool, targetDays) => {
        const withRanges = pool
            .map(o => ({ o, r: toDaysRange(o) }))
            .filter(x => x.o && x.r.a !== null && Number.isFinite(x.r.a));

        if (!Number.isFinite(targetDays) || targetDays <= 0) return null;
        if (withRanges.length === 0) return null;

        const byRange = withRanges.find(x => x.r.a !== null && x.r.b !== null && targetDays >= x.r.a && targetDays <= x.r.b);
        if (byRange) return byRange.o;

        const eligible = withRanges.filter(x => x.r.a !== null && x.r.a <= targetDays);
        if (eligible.length === 0) return null;

        return eligible.reduce((best, cur) => {
            const bestA = best.r.a;
            const curA = cur.r.a;
            if (curA !== bestA) return curA > bestA ? cur : best;
            return (effRate(cur.o) ?? 0) > (effRate(best.o) ?? 0) ? cur : best;
        }, eligible[0]).o;
    };

    const monthsToDayBucketStart = (months) => {
        const m = Number(months);
        if (!Number.isFinite(m) || m <= 0) return NaN;
        const whole = Math.floor(m);
        if (whole <= 0) return NaN;
        // Map 1M -> 31 days, 2M -> 61 days, 3M -> 91 days, ...
        return 30 * (whole - 1) + 31;
    };

    const daysToMonthBucket = (days) => {
        const d = Number(days);
        if (!Number.isFinite(d) || d <= 0) return NaN;
        const whole = Math.floor(d);
        if (whole < 31) return NaN;
        // Map 31–60d -> 1M, 61–90d -> 2M, 91–120d -> 3M, ...
        return Math.max(1, 1 + Math.floor((whole - 31) / 30));
    };

    const toDaysRange = (o) => {
        if (!o) return { a: null, b: null };
        const a = o.termDaysMin === null || o.termDaysMin === undefined ? null : Number(o.termDaysMin);
        const b = o.termDaysMax === null || o.termDaysMax === undefined ? null : Number(o.termDaysMax);
        return {
            a: Number.isFinite(a) ? a : null,
            b: Number.isFinite(b) ? b : null
        };
    };

    const typedOffers = Array.isArray(offers) ? offers : [];

    const pickFromPool = (pool) => {
        const offersByAmount = Number.isFinite(amount)
            ? pool.filter(o => {
                const minOk = !Number.isFinite(o.min) || amount >= Number(o.min);
                const maxOk = (o.max === null || o.max === undefined || !Number.isFinite(o.max)) ? true : amount <= Number(o.max);
                return minOk && maxOk;
            })
            : pool;

        const poolOffers = offersByAmount.length > 0 ? offersByAmount : pool;
        const validAll = poolOffers.filter(o => Number.isFinite(effRate(o)) && Number.isFinite(o.termMonths));
        const monthsOffers = validAll.filter(o => String(o.termUnit || "").toLowerCase() === "months");
        const daysOffers = validAll.filter(o => String(o.termUnit || "").toLowerCase() === "days");

        let valid = validAll;
        if (targetTermUnit === "months") {
            if (monthsOffers.length > 0) {
                const minMonthTerm = monthsOffers.reduce((m, o) => {
                    const mm = monthMin(o);
                    return Number.isFinite(mm) && mm < m ? mm : m;
                }, monthMin(monthsOffers[0]));
                const minDayMin = daysOffers
                    .map(o => toDaysRange(o).a)
                    .filter(n => Number.isFinite(n))
                    .reduce((m, n) => (m === null || n < m ? n : m), null);

                const targetDaysFromMonths = Number.isFinite(targetTermMonths)
                    ? Math.max(31, monthsToDayBucketStart(targetTermMonths))
                    : NaN;

                const allowMonthsToDaysFallback =
                    daysOffers.length > 0 &&
                    Number.isFinite(minMonthTerm) &&
                    Number.isFinite(minDayMin) &&
                    (
                        Number(minDayMin) <= 31 ||
                        (Number.isFinite(targetDaysFromMonths) && targetDaysFromMonths >= Number(minDayMin))
                    );
                if (allowMonthsToDaysFallback && Number.isFinite(targetTermMonths) && Number.isFinite(minMonthTerm) && targetTermMonths < minMonthTerm) {
                    let targetDays = targetDaysFromMonths;
                    if (Number.isFinite(minDayMin) && Number.isFinite(targetDays) && targetDays < minDayMin) {
                        targetDays = minDayMin;
                    }
                    const byThreshold = pickDaysThreshold(daysOffers, targetDays);
                    if (byThreshold) return byThreshold;
                    return null;
                }
                valid = monthsOffers;
            } else if (daysOffers.length > 0) {
                const targetDays = Number.isFinite(targetTermMonths)
                    ? Math.max(31, monthsToDayBucketStart(targetTermMonths))
                    : NaN;
                const byThreshold = pickDaysThreshold(daysOffers, targetDays);
                if (byThreshold) return byThreshold;
                return null;
            }
        } else if (targetTermUnit === "days") {
            if (daysOffers.length > 0) {
                const targetDays = Math.round(Number(selectedTerm));
                const byThreshold = pickDaysThreshold(daysOffers, targetDays);
                if (byThreshold) return byThreshold;
                return null;
            }

            const targetDays = Math.round(Number(selectedTerm));
            if (Number.isFinite(targetDays) && targetDays > 0 && targetDays <= 30) return null;
            if (monthsOffers.length === 0) return null;

            const targetMonths = Number.isFinite(targetDays) && targetDays > 0
                ? daysToMonthBucket(targetDays)
                : NaN;
            if (!Number.isFinite(targetMonths) || targetMonths <= 0) return null;

            const byThreshold = pickMonthThreshold(monthsOffers, targetMonths);
            if (byThreshold) return byThreshold;
            return null;
            const minTerm = withTerms.reduce((m, o) => (o.termMonths < m ? o.termMonths : m), withTerms[0].termMonths);
            if (Number.isFinite(minTerm) && targetMonths < minTerm) return null;

            const exactMatches = withTerms.filter(o => o.termMonths === targetMonths);
            if (exactMatches.length === 1) return exactMatches[0];
            if (exactMatches.length > 1) {
                return exactMatches.reduce((best, cur) => ((effRate(cur) ?? 0) > (effRate(best) ?? 0) ? cur : best), exactMatches[0]);
            }

            return pickMonthThreshold(withTerms, targetMonths);
        }

        if (valid.length === 0) return poolOffers[0] || null;

        if (targetTermMonths !== null) {
            const inRange = valid.filter(o => String(o.termUnit || "").toLowerCase() === "months" && monthRangeContains(o, targetTermMonths));
            if (inRange.length === 1) return inRange[0];
            if (inRange.length > 1) {
                return inRange.reduce((best, cur) => ((effRate(cur) ?? 0) > (effRate(best) ?? 0) ? cur : best), inRange[0]);
            }

            const exactMatches = valid.filter(o => o.termMonths === targetTermMonths);
            if (exactMatches.length === 1) return exactMatches[0];
            if (exactMatches.length > 1) {
                return exactMatches.reduce((best, cur) => ((effRate(cur) ?? 0) > (effRate(best) ?? 0) ? cur : best), exactMatches[0]);
            }

            return pickMonthThreshold(valid, targetTermMonths);
        }

        return valid.reduce((best, cur) => ((effRate(cur) ?? 0) > (effRate(best) ?? 0) ? cur : best), valid[0]);
    };

    const regularOffers = typedOffers.filter(o => o && !o.isSpecialOffer);
    const specialOffers = typedOffers.filter(o => o && o.isSpecialOffer);

    if (showSpecial) {
        const specialPick = specialOffers.length ? pickFromPool(specialOffers) : null;
        const specialIsRealMatch = !specialPick
            ? false
            : (targetTermMonths === null
                ? Number.isFinite(effRate(specialPick))
                : Number.isFinite(specialPick.termMonths) && Number.isFinite(effRate(specialPick)));
        if (specialIsRealMatch) return specialPick;
        const regularPick = regularOffers.length ? pickFromPool(regularOffers) : null;
        if (regularPick) return regularPick;
        return pickFromPool(typedOffers);
    }

    const regularPick = regularOffers.length ? pickFromPool(regularOffers) : null;
    if (regularPick) return regularPick;
    return pickFromPool(typedOffers);
}

function renderDepositTable() {
    const container = document.getElementById("deposit-table-container");

    if (!container) return;

    const amountInput = document.getElementById("deposit-compare-amount");
    const amount = amountInput ? getElementValue("deposit-compare-amount") : NaN;
    const targetTermMonths = getDepositCompareTermMonths();
    const targetTermUnit = getDepositCompareTermUnit();
    const showSpecial = !!document.getElementById("deposit-compare-special")?.checked;

    const termEl = document.getElementById("deposit-compare-term");
    const unitEl = document.getElementById("deposit-compare-unit");
    const selectedTerm = termEl ? Number(termEl.value) : NaN;
    const selectedUnit = unitEl ? String(unitEl.value ?? "months") : "months";

    const selectedTermLabel = Number.isFinite(selectedTerm) && selectedTerm > 0
        ? (selectedUnit === "days" ? `${selectedTerm} dni` : `${selectedTerm} mesecev`)
        : "";

    const years = Number.isFinite(selectedTerm) && selectedTerm > 0
        ? (selectedUnit === "days" ? selectedTerm / 365.25 : selectedTerm / 12)
        : NaN;

    const banks = Array.from(new Set(depositOffers.map(o => String(o.bank ?? "").trim()).filter(Boolean)))
        .sort((a, b) => a.localeCompare(b, "sl"));

    const effRate = (o) => {
        if (!o) return NaN;
        if (showSpecial && Number.isFinite(o.rateSpecial)) return Number(o.rateSpecial);
        return Number(o.rateBase);
    };

    const monthRangeContains = (o, m) => {
        if (!o || !Number.isFinite(m)) return false;
        const aRaw = o.termMonthsMin;
        const bRaw = o.termMonthsMax;
        const a = aRaw === null || aRaw === undefined ? NaN : Number(aRaw);
        const b = bRaw === null || bRaw === undefined ? NaN : Number(bRaw);
        if (Number.isFinite(a) && Number.isFinite(b)) return m >= a && m <= b;
        if (Number.isFinite(a) && !Number.isFinite(b)) return m >= a;
        if (!Number.isFinite(a) && Number.isFinite(b)) return m <= b;
        return Number.isFinite(o.termMonths) ? Number(o.termMonths) === m : false;
    };

    const pickOffer = (offers) => pickDepositOffer(offers, {
        amount,
        targetTermMonths,
        targetTermUnit,
        selectedTerm,
        showSpecial
    });

    const bankMinAmount = (offers) => {
        const mins = offers
            .map(o => Number(o?.min))
            .filter(n => Number.isFinite(n) && n > 0);
        return mins.length ? mins.reduce((a, b) => (b < a ? b : a), mins[0]) : NaN;
    };

    const bankMaxAmount = (offers) => {
        const maxs = offers
            .map(o => Number(o?.max))
            .filter(n => Number.isFinite(n) && n > 0);
        return maxs.length ? maxs.reduce((a, b) => (b > a ? b : a), maxs[0]) : null;
    };

    const rowsUnsorted = banks
        .map((bank) => {
            const offers = depositOffers.filter(o => String(o.bank ?? "").trim() === bank);
            const bankMin = bankMinAmount(offers);
            const bankMax = bankMaxAmount(offers);
            const chosen = pickOffer(offers);
            if (chosen) {
                if (!Number.isFinite(Number(chosen.min))) {
                    chosen.min = bankMin;
                }
                if (chosen.max === null || chosen.max === undefined || !Number.isFinite(Number(chosen.max))) {
                    chosen.max = bankMax;
                }
                return { ...chosen, bankMin, bankMax };
            }
            return {
                bank,
                rateBase: NaN,
                rateSpecial: null,
                termMonths: null,
                term: "",
                min: bankMin,
                max: bankMax,
                bankMin,
                bankMax,
                termUnit: null,
                url: "",
                offerType: null,
                source: null,
                productName: "",
                notes: ""
            };
        })
        ;

    const dirMul = depositTableSortDir === "asc" ? 1 : -1;
    const rows = rowsUnsorted
        .slice()
        .sort((a, b) => {
            if (depositTableSortKey === "bank") {
                const aa = String(a.bank ?? "").trim();
                const bb = String(b.bank ?? "").trim();
                return dirMul * aa.localeCompare(bb, "sl");
            }
            const ra = effRate(a);
            const rb = effRate(b);
            const va = Number.isFinite(ra) ? ra : -Infinity;
            const vb = Number.isFinite(rb) ? rb : -Infinity;
            if (va === vb) {
                const aa = String(a.bank ?? "").trim();
                const bb = String(b.bank ?? "").trim();
                return aa.localeCompare(bb, "sl");
            }
            return dirMul * (va - vb);
        });

    const sortIndicator = (key) => {
        if (depositTableSortKey !== key) return " ↕";
        return depositTableSortDir === "asc" ? " ▲" : " ▼";
    };

    let html = `
        <table class="table">
            <thead>
                <tr>
                    <th class="text-left w-56">
                        <span class="relative inline-block pr-4">
                            <button type="button" class="deposit-sort-btn font-semibold hover:underline cursor-pointer" data-sort="bank" title="Sortiraj po banki (A–Z / Z–A)">Banka${sortIndicator("bank")}</button>
                            <span class="fp-help fp-help--edge-left absolute -top-1 -right-1">
                                <span class="fp-help__icon" tabindex="0">?</span>
                                <span class="fp-help__tooltip">Namig: s klikom na ime banke odpreš ponudbo (če je na voljo).</span>
                            </span>
                        </span>
                    </th>
                    <th class="w-40"><button type="button" class="deposit-sort-btn font-semibold hover:underline cursor-pointer" data-sort="rate" title="Sortiraj po obrestni meri (naraščajoče/padajoče)">Letna o.m.${sortIndicator("rate")}</button></th>
                    <th class="w-32">Doba vezave</th>
                    <th class="w-40">Min. znesek</th>
                    <th class="w-40 whitespace-nowrap">Obresti</th>
                    <th class="w-44 whitespace-nowrap">Končni znesek</th>
                </tr>
            </thead>
            <tbody>
    `;

    rows.forEach(d => {
        const withinMin = Number.isFinite(amount) && Number.isFinite(d.min) ? amount >= Number(d.min) : Number.isFinite(amount);
        const withinMax = (d.max === null || d.max === undefined || !Number.isFinite(d.max)) ? true : (Number.isFinite(amount) ? amount <= Number(d.max) : true);
        const rateVal = effRate(d);
        const hasRate = Number.isFinite(rateVal) && rateVal > 0;
        const canCalc = Number.isFinite(amount) && Number.isFinite(years) && years > 0 && withinMin && withinMax && hasRate;
        const r = hasRate ? (rateVal / 100) : NaN;
        const finalAmount = canCalc ? (amount * Math.pow(1 + r, years)) : null;
        const interest = canCalc && finalAmount !== null ? (finalAmount - amount) : null;

        const bankMinValue = Number(d.bankMin);
        const fallbackMinValue = Number(d.min);
        const minToShow = (Number.isFinite(bankMinValue) && bankMinValue > 0) ? bankMinValue : fallbackMinValue;
        const minText = Number.isFinite(minToShow) && minToShow > 0 ? formatSIWholeEuro(minToShow) : "—";

        const url = String(d.url ?? "").trim();
        const offerTypeTxt = String(d.offerType ?? "").trim();
        const sourceTxt = String(d.source ?? "").trim();
        const productTxt = String(d.productName ?? "").trim();
        const notesTxt = String(d.notes ?? "").trim();
        const tipParts = [];
        if (productTxt) tipParts.push(productTxt);
        if (offerTypeTxt) tipParts.push(`offer_type=${offerTypeTxt}`);
        if (sourceTxt) tipParts.push(`source=${sourceTxt}`);
        if (selectedTermLabel) tipParts.push(selectedTermLabel);
        if (notesTxt) tipParts.push(notesTxt);
        const tooltip = tipParts.join(" | ");
        const bankCell = url
            ? `<button type="button" class="bank-offer-btn block w-full text-left font-semibold text-gray-900 hover:underline" data-url="${url}" data-bank="${escapeHtml(d.bank)}" title="${escapeHtml(tooltip)}">${d.bank}</button>`
            : `<button type="button" class="bank-offer-btn block w-full text-left font-semibold text-gray-900" data-url="" data-bank="${escapeHtml(d.bank)}" aria-disabled="true" title="${escapeHtml(tooltip)}">${d.bank}</button>`;

        const rateText = hasRate ? `${formatRateSI(rateVal)}%` : "—";

        html += `
            <tr class="table-row">
                <td class="text-left">${bankCell}</td>
                <td><strong>${rateText}</strong></td>
                <td>${selectedTermLabel || "—"}</td>
                <td>${minText}</td>
                <td class="whitespace-nowrap">${interest === null ? "—" : formatSI(interest)}</td>
                <td class="whitespace-nowrap">${finalAmount === null ? "—" : formatSI(finalAmount)}</td>
            </tr>
        `;
    });

    html += `
            </tbody>
        </table>
        <div class="mt-3 text-sm text-gray-600 leading-snug">
            <div>Opomba: prikazane obrestne mere so iz <strong>redne ponudbe</strong> bank (posebnih/akcijskih ponudb ta kalkulator privzeto ne upošteva). Pogoji se lahko spremenijo in lahko odstopajo od dejanske ponudbe banke.</div>
            <div class="mt-1">Če je prikazano <strong>—</strong>, banka za izbrano ročnost (ali znesek) nima ustrezne ponudbe.</div>
        </div>
    `;

    container.innerHTML = html;

    container.querySelectorAll(".deposit-sort-btn").forEach((btn) => {
        btn.addEventListener("click", () => {
            const key = String(btn.dataset.sort ?? "").trim();
            if (!key) return;
            if (depositTableSortKey === key) {
                depositTableSortDir = depositTableSortDir === "asc" ? "desc" : "asc";
            } else {
                depositTableSortKey = key;
                depositTableSortDir = key === "bank" ? "asc" : "desc";
            }
            fpTrack("compare_sort", {
                compare: "deposit",
                sort_key: depositTableSortKey,
                sort_dir: depositTableSortDir,
            });
            renderDepositTable();
        });
    });

    container.querySelectorAll(".bank-offer-btn").forEach((btn) => {
        btn.addEventListener("click", () => {
            container.querySelectorAll(".bank-offer-btn").forEach(b => {
                b.style.color = "";
            });
            btn.style.color = "#0B6B3A";

            const href = String(btn.dataset.url ?? "").trim();
            if (!href) return;

            const openOffer = () => {
                window.open(href, "_blank", "noopener,noreferrer");
            };

            if (fpHasAnalyticsConsent() && window.__fpGa4Enabled && typeof window.gtag === "function") {
                let opened = false;
                const safeOpen = () => {
                    if (opened) return;
                    opened = true;
                    openOffer();
                };

                const bank = String(btn.dataset.bank ?? "").trim();
                fpTrack(
                    "bank_offer_click",
                    { calculator: "deposit_compare", bank: bank || undefined, url: href },
                    {
                        transport_type: "beacon",
                        event_callback: safeOpen,
                    }
                );

                setTimeout(safeOpen, 450);
                return;
            }

            openOffer();
        });
    });
}

function initDepositCompareBindings() {
    const amountInput = document.getElementById("deposit-compare-amount");
    if (amountInput) {
        amountInput.addEventListener("input", () => { renderDepositTable(); });
        amountInput.addEventListener("change", () => { renderDepositTable(); });
    }

    const termInput = document.getElementById("deposit-compare-term");
    if (termInput) {
        termInput.addEventListener("input", () => { renderDepositTable(); });
        termInput.addEventListener("change", () => { renderDepositTable(); });
    }

    const unitSelect = document.getElementById("deposit-compare-unit");
    if (unitSelect) {
        unitSelect.addEventListener("input", () => { syncDepositCompareTermBounds(); renderDepositTable(); });
        unitSelect.addEventListener("change", () => { syncDepositCompareTermBounds(); renderDepositTable(); });
    }

    syncDepositCompareTermBounds();

    const specialCheckbox = document.getElementById("deposit-compare-special");
    if (specialCheckbox) {
        specialCheckbox.addEventListener("input", () => { renderDepositTable(); });
        specialCheckbox.addEventListener("change", () => { renderDepositTable(); });
    }
}

/* =======================
Generiraj dropdown bank
======================= */
function renderBankDropdown() {
    const select = document.getElementById("bank-select");
    const loanSelect = document.getElementById("loan-bank");

    if (!select && !loanSelect) return;

    const prevLoan = loanSelect ? String(loanSelect.value ?? "") : "";
    const prevDeposit = select ? String(select.value ?? "") : "";

    if (select) {
        select.innerHTML = "";
    }

    if (select) {
        // Dodaj ročni vnos
        const manualOption = document.createElement("option");
        manualOption.value = "manual";
        manualOption.textContent = "— Ročni vnos obrestne mere —";
        select.appendChild(manualOption);
    }

    // banke iz depositOffers (unikatno)
    const banks = Array.from(new Set(depositOffers.map(o => String(o.bank ?? "").trim()).filter(Boolean)))
        .sort((a, b) => a.localeCompare(b, "sl"));
    if (select) {
        banks.forEach((bank) => {
            const option = document.createElement("option");
            option.value = bank;
            option.textContent = bank;
            select.appendChild(option);
        });

        if (prevDeposit) {
            select.value = prevDeposit;
            if (select.value !== prevDeposit) {
                select.value = "manual";
            }
        } else {
            select.value = "manual";
        }
    }

    if (loanSelect) {
        loanSelect.innerHTML = "";
        const placeholder = document.createElement("option");
        placeholder.value = "";
        placeholder.textContent = "— Izberi banko (neobvezno) —";
        loanSelect.appendChild(placeholder);

        banks.forEach((bank) => {
            const option = document.createElement("option");
            option.value = bank;
            option.textContent = bank;
            loanSelect.appendChild(option);
        });

        if (prevLoan) {
            loanSelect.value = prevLoan;
            if (loanSelect.value !== prevLoan) {
                loanSelect.value = "";
            }
        }
    }
}

/* =======================
   POSODOBI OBRESTNO MERO
======================= */
function updateInterestRate() {
    const bankSelect = document.getElementById("bank-select");
    if (!bankSelect) return;

    const value = String(bankSelect.value ?? "");
    const rateInput = document.getElementById("interest-rate");
    const offerLink = document.getElementById("deposit-offer-link");

    if (!rateInput) return;

    const monthsEl = document.getElementById("interest-months");
    const months = monthsEl ? Number(monthsEl.value) : NaN;
    const targetTermMonths = Number.isFinite(months) ? months : null;

    const amount = getElementValue("interest-amount");

    // Privzeto vedno uporabljamo osnovno (redna) OM.
    // Posebna/akcijska OM se lahko uporabi samo, če obstaja checkbox (in je obkljukan).
    const showSpecial = !!document.getElementById("interest-special")?.checked;

    // če ni izbrana banka → ročni vnos
    if (value === "") {
        rateInput.removeAttribute("readonly");
        delete rateInput.dataset.autoRate;
        if (offerLink) offerLink.classList.add("hidden");
        return;
    }

    // če izberemo ročni vnos
    if (value === "manual") {
        rateInput.removeAttribute("readonly");
        rateInput.value = "";
        delete rateInput.dataset.autoRate;
        if (offerLink) offerLink.classList.add("hidden");
        return;
    }

    // če izberemo banko → OM se nastavi avtomatsko glede na banko + ročnost
    rateInput.setAttribute("readonly", "readonly");

    const bank = value.trim();
    const bankOffers = depositOffers.filter(o => String(o.bank ?? "").trim() === bank);

    // Link do ponudbe naj bo vedno viden, ko je izbrana banka.
    // Tudi če za izbrano ročnost ni ponudbe, naj uporabnik lahko odpre ponudbo banke.
    if (offerLink) {
        offerLink.classList.remove("hidden");
    }

    const fallbackUrl = bankOffers
        .map(o => String(o?.url ?? "").trim())
        .find(u => !!u);

    if (offerLink) {
        const href = String(fallbackUrl ?? "").trim();
        if (href) {
            offerLink.href = href;
            offerLink.setAttribute("aria-disabled", "false");
            offerLink.classList.remove("opacity-50", "pointer-events-none");
        } else {
            offerLink.href = "#";
            offerLink.setAttribute("aria-disabled", "true");
            offerLink.classList.add("opacity-50", "pointer-events-none");
        }
    }

    if (bankOffers.length === 0) {
        rateInput.value = "-";
        delete rateInput.dataset.autoRate;
        return;
    }

    const offerToUse = pickDepositOffer(bankOffers, {
        amount: Number.isFinite(amount) ? amount : NaN,
        targetTermMonths,
        targetTermUnit: "months",
        selectedTerm: months,
        showSpecial
    });

    if (Number.isFinite(targetTermMonths) && (!offerToUse || !Number.isFinite(offerToUse.termMonths))) {
        rateInput.value = "-";
        delete rateInput.dataset.autoRate;
        return;
    }

    const autoRate = Number(
        (showSpecial && offerToUse && offerToUse.rateSpecial !== undefined && offerToUse.rateSpecial !== null)
            ? offerToUse.rateSpecial
            : (offerToUse?.rateBase ?? offerToUse?.rate)
    );
    rateInput.value = Number.isFinite(autoRate) ? formatRateSI(autoRate) : "";
    rateInput.dataset.autoRate = Number.isFinite(autoRate) ? String(autoRate) : "";

    if (offerLink) {
        if (!offerToUse) {
            // Keep the link visible and rely on the fallback URL set earlier.
        } else {
            const href = String(offerToUse.url ?? "").trim();
            if (href) {
                offerLink.href = href;
                offerLink.setAttribute("aria-disabled", "false");
                offerLink.classList.remove("opacity-50", "pointer-events-none");
            } else {
                offerLink.href = "#";
                offerLink.setAttribute("aria-disabled", "true");
                offerLink.classList.add("opacity-50", "pointer-events-none");
            }
        }
    }
}

function initDepositUiBindings() {
    const bankSelect = document.getElementById("bank-select");
    if (bankSelect) {
        bankSelect.addEventListener("change", updateInterestRate);
        bankSelect.addEventListener("input", updateInterestRate);
    }

    const amountEl = document.getElementById("interest-amount");
    if (amountEl) {
        amountEl.addEventListener("change", updateInterestRate);
        amountEl.addEventListener("input", updateInterestRate);
        amountEl.addEventListener("keyup", updateInterestRate);
        amountEl.addEventListener("blur", updateInterestRate);
    }

    const monthsEl = document.getElementById("interest-months");
    if (monthsEl) {
        monthsEl.addEventListener("change", updateInterestRate);
        monthsEl.addEventListener("input", updateInterestRate);
        monthsEl.addEventListener("keyup", updateInterestRate);
        monthsEl.addEventListener("blur", updateInterestRate);
    }

    const rateEl = document.getElementById("interest-rate");
    if (rateEl) {
        rateEl.addEventListener("blur", () => normalizeRateInput("interest-rate"));
    }

    const specialEl = document.getElementById("interest-special");
    if (specialEl) {
        specialEl.addEventListener("change", updateInterestRate);
        specialEl.addEventListener("input", updateInterestRate);
    }

    const offerLink = document.getElementById("deposit-offer-link");
    if (offerLink) {
        offerLink.addEventListener("click", (e) => {
            const disabled = offerLink.getAttribute("aria-disabled") === "true";
            const href = String(offerLink.getAttribute("href") ?? "").trim();
            if (disabled || href === "" || href === "#") {
                e.preventDefault();
                return;
            }

            if (fpHasAnalyticsConsent() && window.__fpGa4Enabled && typeof window.gtag === "function") {
                e.preventDefault();

                let opened = false;
                const openOffer = () => {
                    if (opened) return;
                    opened = true;
                    window.open(href, "_blank", "noopener,noreferrer");
                };

                const bankSelect = document.getElementById("bank-select");
                const bank = bankSelect ? String(bankSelect.value ?? "").trim() : "";

                fpTrack(
                    "bank_offer_click",
                    { calculator: "deposit", bank: bank || undefined, url: href },
                    {
                        transport_type: "beacon",
                        event_callback: openOffer,
                    }
                );

                setTimeout(openOffer, 450);
            }
        });
    }
}

/* ============================================================
   END OF FILE
============================================================ */
