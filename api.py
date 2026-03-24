import sqlite3
import os
from datetime import datetime

import joblib
import numpy as np
import pandas as pd
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import Optional
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from config import DB_PATH, MODEL_PATH

CURRENT_YEAR = datetime.now().year

# ── Load model once at startup ────────────────────────────────────────────────
# Loads lazily so the app starts cleanly even before pipeline.joblib is uploaded
import os as _os
_pipeline = None

def get_pipeline():
    global _pipeline
    if _pipeline is None:
        if not _os.path.exists(MODEL_PATH):
            from fastapi import HTTPException
            raise HTTPException(status_code=503, detail="Model not loaded yet — upload pipeline.joblib to /data/")
        _pipeline = joblib.load(MODEL_PATH)
    return _pipeline

# ── Rate limiting ─────────────────────────────────────────────────────────────
limiter = Limiter(key_func=get_remote_address, default_limits=["200/hour"])

app = FastAPI(title="Car Price Predictor")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Confidence helper ─────────────────────────────────────────────────────────
def _spread(prices: list) -> float:
    """Std of log-prices ≈ coefficient of variation in % terms."""
    return float(np.std(np.log1p(prices))) * 100


def get_confidence(trim_id: Optional[str], make: str, model: str,
                   year: int, mileage: int,
                   fuel: Optional[str] = None,
                   power_kw: Optional[int] = None) -> dict:
    """
    Finds similar cars by progressively expanding year/mileage windows until
    MIN_SAMPLES is reached. Also filters by fuel type and power_kw range where
    available — electric vs petrol or base vs AMG are not comparable.
    """
    MIN_SAMPLES = 10
    YEAR_PCT    = 0.20
    MILEAGE_PCT = 0.20
    POWER_PCT   = 0.25   # ±25% power_kw window
    MULTIPLIERS = [1.0, 1.5, 2.5, 4.0, 8.0]  # expand until MIN_SAMPLES found

    car_age = CURRENT_YEAR - year
    con     = sqlite3.connect(DB_PATH)

    def _fetch(where: str, params: tuple) -> list:
        """Expand year/mileage window until MIN_SAMPLES found or max multiplier hit."""
        for mult in MULTIPLIERS:
            yw = max(1,      int(car_age * YEAR_PCT    * mult))
            mw = max(10_000, int(mileage * MILEAGE_PCT * mult))
            rows = con.execute(
                f"SELECT price FROM listings WHERE {where}"
                f" AND year BETWEEN ? AND ? AND mileage BETWEEN ? AND ?",
                params + (year - yw, year + yw, max(0, mileage - mw), mileage + mw)
            ).fetchall()
            if len(rows) >= MIN_SAMPLES:
                return [r[0] for r in rows]
        return [r[0] for r in rows]  # best we found

    # Build optional extra filters
    fuel_where  = " AND fuel=?"      if fuel    else ""
    fuel_param  = (fuel,)            if fuel    else ()
    power_where = " AND power_kw BETWEEN ? AND ?" if power_kw else ""
    power_param = (int(power_kw * (1 - POWER_PCT)), int(power_kw * (1 + POWER_PCT))) if power_kw else ()

    prices = None
    basis  = "model"

    # Strategy 1: trim_id + fuel + power
    if trim_id and trim_id != "Unknown":
        prices = _fetch(f"trim_id=?{fuel_where}{power_where}",
                        (trim_id,) + fuel_param + power_param)
        if len(prices) >= MIN_SAMPLES:
            basis = "trim"
        else:
            # Strategy 2: trim_id only (drop power/fuel filter)
            prices = _fetch("trim_id=?", (trim_id,))
            if len(prices) >= MIN_SAMPLES:
                basis = "trim"
            else:
                prices = None  # fall through to make/model

    # Strategy 3: make + model + fuel + power
    if prices is None or len(prices) < MIN_SAMPLES:
        prices = _fetch(f"make=? AND model=?{fuel_where}{power_where}",
                        (make, model) + fuel_param + power_param)
        if len(prices) < MIN_SAMPLES:
            # Strategy 4: make + model only
            prices = _fetch("make=? AND model=?", (make, model))

    con.close()

    if len(prices) < MIN_SAMPLES:
        return {"spread_pct": None, "sample_count": len(prices), "basis": basis,
                "level": "low", "label": "Not accurate"}

    spread_pct = round(_spread(prices), 1)

    if spread_pct < 12:
        level, label = "high",   "Very accurate"
    elif spread_pct < 22:
        level, label = "medium", "Accurate"
    else:
        level, label = "low",    "Not accurate"

    return {
        "spread_pct":   spread_pct,
        "sample_count": len(prices),
        "basis":        basis,
        "level":        level,
        "label":        label,
    }


# ── Verdict helper ───────────────────────────────────────────────────────────
def compute_final_verdict(diff_pct: float, confidence: dict) -> dict:
    """SNR-based verdict used by both /predict and /predict/batch."""
    spread = confidence.get("spread_pct") or 40  # None → conservative fallback
    snr = abs(diff_pct) / spread if spread > 0 else 0

    if abs(diff_pct) < 5:
        return {"label": "Fair price", "color": "#2563eb"}
    elif diff_pct < 0:  # underpriced signal
        if   snr > 2.0: return {"label": "Great deal",           "color": "#16a34a"}
        elif snr > 1.0: return {"label": "Likely underpriced",   "color": "#65a30d"}
        elif snr > 0.5: return {"label": "Possibly underpriced", "color": "#84cc16"}
        else:            return {"label": "Fair price",           "color": "#2563eb"}
    else:               # overpriced signal
        if   snr > 2.0: return {"label": "Overpriced",           "color": "#dc2626"}
        elif snr > 1.0: return {"label": "Likely overpriced",    "color": "#ea580c"}
        elif snr > 0.5: return {"label": "Possibly overpriced",  "color": "#f97316"}
        else:            return {"label": "Fair price",           "color": "#2563eb"}


# ── Feature builder (must match train.py features exactly) ────────────────────
def _build_features(car) -> dict:
    """Build feature dict matching the model's expected columns."""
    car_age = CURRENT_YEAR - car.year
    return {
        "car_age":         car_age,
        "mileage":         car.mileage,
        "power_kw":        car.power_kw,
        "range_km":        car.range_km,
        "mileage_per_year": car.mileage / max(1, car_age),
        "is_electric":     int(car.fuel == "Elektrisch"),
        "is_hybrid":       int("Elektro/" in (car.fuel or "")),
        "make":            car.make,
        "model":           car.model,
        "trim_id":         car.trim_id       or "Unknown",
        "variant_id":      car.variant_id    or "Unknown",
        "generation_id":   car.generation_id or "Unknown",
        "fuel":            car.fuel,
        "transmission":    car.transmission,
        "seller_type":     car.seller_type   or "Unknown",
    }


# ── Request schemas ───────────────────────────────────────────────────────────
class CarInput(BaseModel):
    make: str
    model: str
    year: int
    mileage: int
    fuel: str
    transmission: str
    power_kw:      Optional[int] = None
    range_km:      Optional[int] = None
    trim_id:       Optional[str] = None
    variant_id:    Optional[str] = None
    generation_id: Optional[str] = None
    body_type:     Optional[str] = None
    colour:        Optional[str] = None
    seller_type:   Optional[str] = None
    actual_price:  Optional[int] = None


class CarBatchItem(BaseModel):
    id: str
    make: str
    model: str
    year: int
    mileage: int
    fuel: str
    transmission: str
    power_kw:      Optional[int] = None
    range_km:      Optional[int] = None
    trim_id:       Optional[str] = None
    variant_id:    Optional[str] = None
    generation_id: Optional[str] = None
    body_type:     Optional[str] = None
    colour:        Optional[str] = None
    seller_type:   Optional[str] = None
    actual_price:  Optional[int] = None


# ── Privacy policy ────────────────────────────────────────────────────────────
@app.get("/privacy", response_class=HTMLResponse)
def privacy():
    return """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Privacy Policy — AutoScout24 Price Analyser</title>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
           max-width: 680px; margin: 60px auto; padding: 0 24px;
           color: #1a1a1a; line-height: 1.7; }
    h1 { font-size: 1.6rem; margin-bottom: 0.25rem; }
    h2 { font-size: 1.1rem; margin-top: 2rem; }
    p, ul { margin: 0.5rem 0; }
    ul { padding-left: 1.4rem; }
    a { color: #e84118; }
    .updated { color: #888; font-size: 0.9rem; }
  </style>
</head>
<body>
  <h1>Privacy Policy</h1>
  <p class="updated">AutoScout24 Price Analyser &mdash; last updated March 2026</p>

  <h2>What data is collected</h2>
  <p>The extension reads car listing data (make, model, year, mileage, fuel type,
  transmission, power, and asking price) directly from AutoScout24 pages you visit.
  This data is sent to our prediction API solely to calculate an estimated market value.</p>
  <p>We do <strong>not</strong> collect:</p>
  <ul>
    <li>Any personally identifiable information</li>
    <li>Your browsing history</li>
    <li>Any data unrelated to the car listings on the current page</li>
  </ul>

  <h2>How data is used</h2>
  <p>Car listing data is sent to this API to generate a price prediction. The data is used
  only to produce the prediction shown to you and is not stored, logged, or shared.</p>

  <h2>Third parties</h2>
  <p>No data is shared with any third party. The prediction API is operated by the extension developer.</p>

  <h2>Contact</h2>
  <p>Questions? Open an issue at
  <a href="https://github.com/qwillemse/autoscout-analyser">github.com/qwillemse/autoscout-analyser</a>.</p>
</body>
</html>"""


# ── Stats endpoint ────────────────────────────────────────────────────────────
@app.get("/stats")
def stats():
    try:
        con = sqlite3.connect(DB_PATH)
        count = con.execute("SELECT COUNT(*) FROM listings").fetchone()[0]
        con.close()
        return {"listing_count": count, "status": "ok"}
    except Exception:
        return {"listing_count": 0, "status": "db_not_loaded"}


# ── Batch predict endpoint ────────────────────────────────────────────────────
@app.post("/predict/batch")
@limiter.limit("20/minute")
def predict_batch(request: Request, cars: list[CarBatchItem]):
    if not cars:
        return []

    # Single predict call for all cars at once — much faster than looping
    features = pd.DataFrame([_build_features(car) for car in cars])

    predicted_prices = np.expm1(get_pipeline().predict(features)).astype(int)

    results = []
    for car, predicted_price in zip(cars, predicted_prices):
        result = {"id": car.id, "predicted_price": int(predicted_price)}
        if car.actual_price:
            diff_pct = (car.actual_price - predicted_price) / predicted_price * 100
            result["diff_pct"] = round(float(diff_pct), 1)
            confidence = get_confidence(car.trim_id, car.make, car.model,
                                        car.year, car.mileage,
                                        fuel=car.fuel, power_kw=car.power_kw)
            result["confidence"]    = confidence
            result["final_verdict"] = compute_final_verdict(diff_pct, confidence)
        results.append(result)
    return results


# ── Predict endpoint ──────────────────────────────────────────────────────────
@app.post("/predict")
@limiter.limit("60/minute")
def predict(request: Request, car: CarInput):
    features = pd.DataFrame([_build_features(car)])

    predicted_price = int(np.expm1(get_pipeline().predict(features)[0]))
    confidence = get_confidence(car.trim_id, car.make, car.model, car.year, car.mileage,
                               fuel=car.fuel, power_kw=car.power_kw)

    response = {
        "predicted_price": predicted_price,
        "confidence": confidence,
    }

    if car.actual_price is not None:
        diff_pct = (car.actual_price - predicted_price) / predicted_price * 100
        response["actual_price"] = car.actual_price
        response["diff_pct"]     = round(diff_pct, 1)
        response["diff_eur"]     = car.actual_price - predicted_price
        # Simple verdict for backwards compatibility
        if diff_pct > 15:
            response["verdict"] = "overpriced"
        elif diff_pct < -15:
            response["verdict"] = "underpriced"
        else:
            response["verdict"] = "fair"
        response["final_verdict"] = compute_final_verdict(diff_pct, confidence)

    return response
