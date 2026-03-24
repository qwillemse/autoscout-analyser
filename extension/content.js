// ── API endpoint ───────────────────────────────────────────────────────────────
const API_URL = "https://web-production-870f.up.railway.app";

// ── Extract car data from __NEXT_DATA__ ───────────────────────────────────────
function extractCarData() {
  const script = document.getElementById("__NEXT_DATA__");
  if (!script) return null;

  try {
    const data = JSON.parse(script.textContent);
    const props = data.props?.pageProps;
    if (!props) return null;

    const listing = props.listing ?? props.details ?? props.listingDetails;
    if (!listing) return null;

    const vehicle       = listing.vehicle ?? {};
    const trackingParams = listing.trackingParams ?? {};

    const year    = parseInt(vehicle.firstRegistrationDateRaw?.split("-")[0], 10);
    const mileage = vehicle.mileageInKmRaw;
    const price   = trackingParams.classified_price;

    if (!year || !price || !mileage || !vehicle.make || !vehicle.model) return null;

    // IDs from modelTaxonomy
    const taxonomy = trackingParams.modelTaxonomy ?? "";
    const _tax = (key) => { const m = taxonomy.match(new RegExp(key + ":(\\d+)")); return m ? m[1] : null; };
    const trim_id       = _tax("trim_id");
    const variant_id    = _tax("variant_id");
    const generation_id = _tax("generation_id");

    const body_type   = vehicle.variant        ?? null;
    const colour      = vehicle.colour         ?? null;
    const seller_type = listing.seller?.type   ?? null;

    let power_kw_parsed = null;
    let range_km = null;
    for (const detail of listing.vehicleDetails ?? []) {
      if (detail.ariaLabel === "Vermogen kW (PK)") {
        const match = detail.data?.match(/^(\d+)\s*kW/);
        if (match) power_kw_parsed = parseInt(match[1], 10);
      } else if (detail.ariaLabel === "actieradius") {
        const match = detail.data?.match(/^(\d+)/);
        if (match) range_km = parseInt(match[1], 10);
      }
    }

    return {
      listing_id:   listing.id ?? null,
      make:         vehicle.make,
      model:        vehicle.model,
      year,
      mileage,
      fuel:         vehicle.fuel         ?? vehicle.fuelCategory?.formatted ?? "Unknown",
      transmission: vehicle.transmission ?? vehicle.transmissionType        ?? "Unknown",
      power_kw:     vehicle.rawPowerInKw ?? power_kw_parsed,
      range_km,
      trim_id,
      variant_id,
      generation_id,
      body_type,
      colour,
      seller_type,
      actual_price: price,
    };
  } catch (e) {
    console.error("[AutoAnalyser] Failed to extract car data:", e);
    return null;
  }
}

// ── SPA listing data — populated by injected.js (main world) via CustomEvent ───
// Content scripts run in an isolated JS context: they cannot intercept the
// page's fetch() or access window.next. injected.js runs in the page's main
// world, intercepts /_next/data/ fetches, and relays data here via CustomEvent.
let _spaListings = null;
let _lastSearchUrl = null;

document.addEventListener("__as24_spa_listings__", (e) => {
  _spaListings = e.detail;
  // Delay slightly so React has time to render the new listing cards into the DOM
  if (window.location.pathname.startsWith("/lst")) {
    setTimeout(() => main(true), 400);
  }
});

// ── Call local API ─────────────────────────────────────────────────────────────
async function fetchPrediction(carData) {
  const { listing_id, ...payload } = carData;
  const res = await fetch(`${API_URL}/predict`, {
    method:  "POST",
    headers: { "Content-Type": "application/json" },
    body:    JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

// ── Check if car falls outside the model's training range ─────────────────────
function getOutOfRangeWarning(carData) {
  const reasons = [];
  if (carData.year < 2005)              reasons.push(`year ${carData.year} (model trained on 2005+)`);
  if (carData.mileage > 250_000)        reasons.push(`${carData.mileage.toLocaleString("nl-NL")} km (model trained up to 250,000 km)`);
  if (carData.actual_price > 150_000)   reasons.push(`asking price €${carData.actual_price.toLocaleString("nl-NL")} (model trained up to €150,000)`);
  return reasons.length ? reasons : null;
}

// ── Build sidebar ──────────────────────────────────────────────────────────────
function buildSidebar(carData, result, stats, detailCarData) {
  const { predicted_price, actual_price, diff_pct, diff_eur, verdict, confidence, final_verdict } = result;

  const verdictConfig = {
    underpriced: { bg: "#dcfce7", color: "#16a34a" },
    overpriced:  { bg: "#fee2e2", color: "#dc2626" },
    fair:        { bg: "#dbeafe", color: "#2563eb" },
  };
  const v = verdictConfig[verdict] ?? verdictConfig.fair;

  const fv    = final_verdict ?? { label: verdict ?? "Unknown", color: "#2563eb" };
  const fmt   = (n) => "€" + Math.abs(n).toLocaleString("nl-NL");
  const sign  = diff_eur > 0 ? "+" : "-";

  // Use detailCarData for display metadata (richer info on the detail page)
  const displayData = detailCarData ?? carData;

  const warnings = getOutOfRangeWarning(displayData);
  const warningHtml = warnings ? `
    <div class="as24-warning">
      ⚠️ Outside training range — prediction may be less accurate:<br>
      ${warnings.join("<br>")}
    </div>` : "";

  const sidebar = document.createElement("div");
  sidebar.id = "as24-analyser-sidebar";
  sidebar.innerHTML = `
    <div class="as24-header">
      <span class="as24-title">🔍 Price Analyser</span>
      <button class="as24-close" id="as24-close-btn">✕</button>
    </div>
    ${warningHtml}
    <div class="as24-verdict" style="background:${v.bg}; color:${fv.color};">
      <span class="as24-verdict-label">${fv.label}</span>
    </div>
    <div class="as24-rows">
      <div class="as24-row">
        <span class="as24-label">Predicted</span>
        <span class="as24-value">${fmt(predicted_price)}</span>
      </div>
      <div class="as24-row">
        <span class="as24-label">Asked</span>
        <span class="as24-value">${fmt(actual_price)}</span>
      </div>
      <div class="as24-row">
        <span class="as24-label">Difference</span>
        <span class="as24-value" style="color:${v.color};">${sign}${fmt(diff_eur)} (${diff_pct > 0 ? "+" : ""}${diff_pct}%)</span>
      </div>
      ${confidence ? (() => {
        const { spread_pct, sample_count, level, label } = confidence;
        const pctText = spread_pct !== null ? ` (±${spread_pct}%)` : "";
        return `<div class="as24-row">
          <span class="as24-label">Confidence</span>
          <span class="as24-value as24-confidence as24-confidence--${level}">${label}${pctText}
            <span class="as24-confidence-sub">${sample_count} similar cars</span>
          </span>
        </div>`;
      })() : ""}
    </div>
    ${detailCarData ? `<div class="as24-detail-btn-wrap">
      <button class="as24-detail-btn" id="as24-detail-btn">Detailed analysis</button>
    </div>` : ""}
    <div class="as24-meta">
      <div>${displayData.make} ${displayData.model} · ${displayData.year}</div>
      <div>${displayData.mileage.toLocaleString("nl-NL")} km${displayData.power_kw ? ` · ${displayData.power_kw} kW` : ""}</div>
      <div>${displayData.fuel} · ${displayData.transmission}</div>
    </div>
    <div class="as24-footer">Based on ${stats ? stats.listing_count.toLocaleString("nl-NL") : "~12k"} NL listings</div>
  `;

  document.body.appendChild(sidebar);

  document.getElementById("as24-close-btn").addEventListener("click", () => {
    sidebar.remove();
  });

  // "Detailed analysis" button — calls /predict with richer detail-page data
  const detailBtn = document.getElementById("as24-detail-btn");
  if (detailBtn && detailCarData) {
    detailBtn.addEventListener("click", async () => {
      detailBtn.textContent = "Analysing...";
      detailBtn.disabled = true;
      try {
        const detailResult = await fetchPrediction(detailCarData);
        document.getElementById("as24-analyser-sidebar")?.remove();
        buildSidebar(detailCarData, detailResult, stats, null);
      } catch {
        detailBtn.textContent = "Failed — try again";
        detailBtn.disabled = false;
      }
    });
  }
}

function buildErrorSidebar(message) {
  const sidebar = document.createElement("div");
  sidebar.id = "as24-analyser-sidebar";
  sidebar.innerHTML = `
    <div class="as24-header">
      <span class="as24-title">🔍 Price Analyser</span>
      <button class="as24-close" id="as24-close-btn">✕</button>
    </div>
    <div class="as24-error">${message}</div>
  `;
  document.body.appendChild(sidebar);
  document.getElementById("as24-close-btn").addEventListener("click", () => sidebar.remove());
}

// ── Parse a raw listings array into the shape the API expects ─────────────────
function parseListings(listings) {
  return listings.flatMap(item => {
    try {
      const price   = parseInt(item.tracking?.price, 10);
      const year    = parseInt(item.tracking?.firstRegistration?.split("-").pop(), 10);
      const mileage = parseInt(item.tracking?.mileage, 10);
      const vehicle = item.vehicle ?? {};
      if (!price || !year || !mileage || !vehicle.make || !vehicle.model) return [];

      let power_kw = null;
      let range_km = null;
      for (const detail of item.vehicleDetails ?? []) {
        if (detail.ariaLabel === "Vermogen kW (PK)") {
          const match = detail.data?.match(/^(\d+)\s*kW/);
          if (match) power_kw = parseInt(match[1], 10);
        } else if (detail.ariaLabel === "actieradius") {
          const match = detail.data?.match(/^(\d+)/);
          if (match) range_km = parseInt(match[1], 10);
        }
      }

      // IDs from modelTaxonomy e.g. "[make_id:74, variant_id:210, trim_id:621]"
      const taxonomy = item.tracking?.modelTaxonomy ?? "";
      const _tax = (key) => { const m = taxonomy.match(new RegExp(key + ":(\\d+)")); return m ? m[1] : null; };
      const trim_id       = _tax("trim_id");
      const variant_id    = _tax("variant_id");
      const generation_id = _tax("generation_id");

      const body_type   = vehicle.variant   ?? null;
      const colour      = vehicle.colour    ?? null;
      const seller_type = item.seller?.type ?? null;

      return [{
        id: item.id, make: vehicle.make, model: vehicle.model, year, mileage,
        fuel: vehicle.fuel ?? "Unknown", transmission: vehicle.transmission ?? "Unknown",
        power_kw, range_km, trim_id, variant_id, generation_id, body_type, colour, seller_type,
        actual_price: price,
      }];
    } catch { return []; }
  });
}

// ── Search page: extract listings from __NEXT_DATA__ or intercepted fetch ──────
function extractSearchListings(preferSPA = false) {
  // 1. SPA listings captured from intercepted /_next/data/ fetch
  if (preferSPA && _spaListings) {
    const result = parseListings(_spaListings);
    _spaListings = null;
    return result;
  }

  // 2. __NEXT_DATA__ — populated on full page load only
  if (!preferSPA) {
    try {
      const script = document.getElementById("__NEXT_DATA__");
      if (script) {
        const listings = JSON.parse(script.textContent)?.props?.pageProps?.listings ?? [];
        if (listings.length) return parseListings(listings);
      }
    } catch {}
  }

  return [];
}

// ── Inject badge into a search result card ────────────────────────────────────
function injectBadge(id, predicted_price, diff_pct, final_verdict) {
  const link = document.querySelector(`a[href*="${id}"]`);
  if (!link) return;
  const card = link.closest("article") ?? link.closest("[data-testid]") ?? link.parentElement;
  if (!card || card.querySelector(".as24-badge")) return;

  const fmt = (n) => "€" + n.toLocaleString("nl-NL");

  // Map final_verdict color to badge CSS class (green/red/blue)
  const GREEN_COLORS = new Set(["#16a34a", "#65a30d", "#84cc16"]);
  const RED_COLORS   = new Set(["#dc2626", "#ea580c", "#f97316"]);
  const fvColor = final_verdict?.color;
  const verdictClass = GREEN_COLORS.has(fvColor) ? "as24-badge--green"
                     : RED_COLORS.has(fvColor)   ? "as24-badge--red"
                     :                              "as24-badge--blue";

  const sign  = diff_pct > 0 ? "+" : "";
  const label = diff_pct !== undefined && diff_pct !== null
    ? `${sign}${diff_pct.toFixed(1)}%`
    : "Market value";

  // Inject after the "Vergelijken" button container so the badge sits below it
  const vergelijken = card.querySelector('[class*="compare"], [class*="Compare"], [class*="checkbox"], input[type="checkbox"]');
  const topRight = vergelijken?.closest("div") ?? vergelijken?.parentElement;

  const html = `
    <span class="as24-badge-label">Market value</span>
    <span class="as24-badge-price">${fmt(predicted_price)}</span>
    <span class="as24-badge-diff">${label}</span>
  `;

  if (topRight) {
    const badge = document.createElement("div");
    badge.className = `as24-badge ${verdictClass}`;
    badge.innerHTML = html;
    topRight.insertAdjacentElement("afterend", badge);
  } else {
    if (window.getComputedStyle(card).position === "static") card.style.position = "relative";
    const badge = document.createElement("div");
    badge.className = `as24-badge as24-badge-absolute ${verdictClass}`;
    badge.innerHTML = html;
    card.appendChild(badge);
  }
}

// ── Main ───────────────────────────────────────────────────────────────────────
async function main(isSPA = false) {
  const isSearchPage = window.location.pathname.startsWith("/lst");

  if (isSearchPage) {
    // Deduplicate: skip same URL re-runs on initial load, but always allow SPA navs
    const currentUrl = window.location.href;
    if (!isSPA && currentUrl === _lastSearchUrl) return;
    _lastSearchUrl = currentUrl;

    const listings = extractSearchListings(isSPA);
    if (!listings.length) return;
    try {
      const results = await fetch(`${API_URL}/predict/batch`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(listings),
      }).then(r => r.json());

      // Cache batch results + listing data so detail pages can reuse them
      const listingMap = Object.fromEntries(listings.map(l => [l.id, l]));
      for (const result of results) {
        injectBadge(result.id, result.predicted_price, result.diff_pct, result.final_verdict);
        try {
          sessionStorage.setItem(`as24_${result.id}`, JSON.stringify({
            carData: listingMap[result.id],
            result,
          }));
        } catch {}
      }
    } catch (e) {
      console.error("[AutoAnalyser] Batch predict failed:", e);
    }
    return;
  }

  // Listing detail page
  if (document.getElementById("as24-analyser-sidebar")) return;

  // Always extract detail-page data for display metadata and for the
  // "Detailed analysis" button.
  const detailCarData = extractCarData();

  // Use the listing ID from __NEXT_DATA__ (UUID) to look up the cached
  // batch result that was stored on the search page.
  const listingId = detailCarData?.listing_id ?? null;

  let cached = null;
  if (listingId) {
    try {
      const raw = sessionStorage.getItem(`as24_${listingId}`);
      if (raw) cached = JSON.parse(raw);
    } catch {}
  }

  if (!cached && !detailCarData) {
    buildErrorSidebar("Could not extract car data from this page.");
    return;
  }

  buildErrorSidebar("Analysing...");

  try {
    let carData, result, stats;

    if (cached) {
      // Use the same prediction the badge showed
      carData = cached.carData;
      const batch = cached.result;
      result = {
        predicted_price: batch.predicted_price,
        actual_price:    carData.actual_price,
        diff_pct:        batch.diff_pct,
        diff_eur:        carData.actual_price - batch.predicted_price,
        verdict:         batch.diff_pct > 15 ? "overpriced" : batch.diff_pct < -15 ? "underpriced" : "fair",
        confidence:      batch.confidence ?? null,
        final_verdict:   batch.final_verdict,
      };
      stats = await fetch(`${API_URL}/stats`).then(r => r.json()).catch(() => null);
    } else {
      // Direct navigation — no cached data, call /predict/batch with detail-page data
      carData = detailCarData;
      const { listing_id: _lid, ...carDataForApi } = carData;
      const batchItem = { ...carDataForApi, id: listingId ?? "detail" };
      const [batchResults, statsRes] = await Promise.all([
        fetch(`${API_URL}/predict/batch`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify([batchItem]),
        }).then(r => r.json()),
        fetch(`${API_URL}/stats`).then(r => r.json()).catch(() => null),
      ]);
      const batch = batchResults[0];
      result = {
        predicted_price: batch.predicted_price,
        actual_price:    carData.actual_price,
        diff_pct:        batch.diff_pct,
        diff_eur:        carData.actual_price - batch.predicted_price,
        verdict:         batch.diff_pct > 15 ? "overpriced" : batch.diff_pct < -15 ? "underpriced" : "fair",
        confidence:      batch.confidence ?? null,
        final_verdict:   batch.final_verdict,
      };
      stats = statsRes;
    }

    document.getElementById("as24-analyser-sidebar")?.remove();
    buildSidebar(carData, result, stats, detailCarData);
  } catch (e) {
    document.getElementById("as24-analyser-sidebar")?.remove();
    buildErrorSidebar("Could not reach the API. Please try again later.");
  }
}

main();
