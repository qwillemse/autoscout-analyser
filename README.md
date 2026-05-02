# AutoScout24 Price Analyser

> See instantly if a car on AutoScout24 is a good deal.
> An end-to-end ML pipeline — scraper → SQLite → XGBoost → FastAPI → Chrome extension — trained weekly on **700,000+ listings** across NL, DE, and BE.

![promo](store-assets/promo-marquee-1400x560.png)

[![Chrome Web Store](https://img.shields.io/badge/Chrome%20Web%20Store-AutoScout24%20Price%20Analyser-4285F4?logo=googlechrome&logoColor=white)](https://chromewebstore.google.com/detail/pimekakenahncahcbeckihhcdceldkfi)
[![Weekly scrape](https://github.com/qwillemse/autoscout-analyser/actions/workflows/weekly-scrape.yml/badge.svg)](https://github.com/qwillemse/autoscout-analyser/actions/workflows/weekly-scrape.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## What it does

When you browse [autoscout24.nl](https://www.autoscout24.nl/), [.de](https://www.autoscout24.de/), or [.be](https://www.autoscout24.be/), the extension overlays each listing with:

- **Predicted market value** based on a machine-learning model trained on all current listings
- **Deal verdict** — Great deal · Likely underpriced · Fair price · Likely overpriced · Overpriced — derived from a signal-to-noise ratio against the model's typical error band
- **Confidence range** — e.g. *"€19,200 – €25,000 (80% of similar cars fall within this range)"*, computed from per-trim residuals
- **Similar cars ranked by best deal**, with live-checked links to the top 3 still-active listings
- **AI-generated insight** explaining *why* the price might be high or low, reading the seller's description for warnings (replaced odometer, undisclosed damage, missing inspection)

## Results

| Metric | Value |
|---|---|
| Listings in training set | **700,215** (after cleaning) |
| Mean Absolute Error | **€2,125** |
| Mean Absolute Percentage Error | **10.26%** |
| Median listing price | €21,900 |
| MAE as % of median | **9.7%** |
| Cross-validation | 5-fold, std ±€7 |
| Countries covered | NL, DE, BE (live) — AT/FR/IT/ES/LU manifest-ready |

## How it works

```
                 ┌──────────────────────┐
                 │  GitHub Actions      │  Sunday 02:00 UTC
                 │  (matrix: NL/DE/BE)  │  parallel scrape jobs
                 └──────────┬───────────┘
                            │ scraped JSON → SQLite shards
                            ▼
                 ┌──────────────────────┐
                 │  Merge + Retrain     │  XGBoost (Optuna-tuned)
                 │  → pipeline.joblib   │  + per-trim range lookup
                 └──────────┬───────────┘
                            │ curl POST to Railway
                            ▼
                 ┌──────────────────────┐         ┌──────────────────┐
                 │  FastAPI on Railway  │ ←───────│  Chrome Extension│
                 │  /predict /explain   │  HTTPS  │  content script  │
                 │  /similar-cars       │ ───────→│  injects badges  │
                 └──────────────────────┘         └──────────────────┘
```

**Scraper** ([scraper.py](scraper.py))
Walks AutoScout24's `__NEXT_DATA__` JSON across configured makes × year-bands × countries. Year-band slicing bypasses the per-search 4,000-listing cap. Multilingual normalization for fuel/transmission across NL/DE/FR/IT/ES.

**Model** ([train.py](train.py))
- **Target:** `log(1 + price)` — gives uniform percentage errors across €500–€150k
- **Features (16):** car_age, mileage, mileage_per_year, power_kw, range_km, is_electric, is_hybrid, plus `make / model / trim_id / variant_id / generation_id` (target encoding) and `fuel / transmission / seller_type / country` (ordinal)
- **Estimator:** `XGBRegressor` — 1,416 trees, depth 9, Optuna-tuned (50 trials, +14% MAE improvement over defaults)
- **Range lookup:** post-training, computes the 80th-percentile error per trim → make+model → make → global. The extension reads this for confidence ranges.

**API** ([api.py](api.py)) — FastAPI on [Railway](https://railway.app/), rate-limited
- `POST /predict` — single car prediction with verdict + confidence
- `POST /predict/batch` — batch up to 30 cards on a search page in one request
- `POST /similar-cars` — finds and re-ranks comparable listings, returns top 30 by diff%
- `POST /explain` — GPT-4o-mini call with country-specific market context + listing details

**Extension** ([extension/](extension/)) — Chrome MV3
- `injected.js` runs in MAIN world to capture AutoScout's Next.js page data before render
- `content.js` reads the captured data, batches predict calls, injects badges
- pushState SPA navigation handling so badges re-render on in-place URL changes
- Multi-country detail-path matching (`/aanbod/`, `/angebote/`, `/annonce/`, `/anuncio/`, …)

## Tech stack

`Python 3.11` · `XGBoost` · `scikit-learn` · `pandas` · `Optuna` (offline tuning) · `FastAPI` · `slowapi` (rate limiting) · `OpenAI gpt-4o-mini` · `SQLite` · `Railway` · `GitHub Actions` · `Chrome MV3` · `BeautifulSoup`

## Repository layout

```
.
├── extension/             Chrome MV3 extension (manifest, content, injected, css, icons)
├── store-assets/          Chrome Web Store promo images
├── .github/workflows/     Weekly scrape + retrain + deploy
├── scraper.py             AutoScout24 search-page scraper
├── main.py                Scrape orchestrator (CLI: --scrape, --train, --countries)
├── train.py               XGBoost training pipeline + range lookup builder
├── api.py                 FastAPI prediction & explanation server
├── db.py                  SQLite schema, upsert + price-history tracking
├── countries.py           Per-country domain, language, and label config
├── config.py              MAKES, YEAR_BANDS, scrape filter params
├── PLAN.md                Living roadmap
└── privacy-policy.md      Privacy policy (also served at /privacy)
```

## Running it locally

```bash
pip install -r requirements.txt

# scrape one country (~1–4 hours depending on country size)
python main.py --scrape --countries NL

# retrain on whatever's in cars.db
python train.py

# serve the API
uvicorn api:app --reload
```

The Chrome extension talks to the Railway-deployed API by default; point `extension/content.js` at `http://localhost:8000` to run end-to-end locally.

## License

MIT — see [LICENSE](LICENSE).
