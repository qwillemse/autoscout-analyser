import json
import sqlite3
from datetime import datetime

import joblib
import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.compose import ColumnTransformer
from sklearn.model_selection import KFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OrdinalEncoder, TargetEncoder

from config import DB_PATH

CURRENT_YEAR = datetime.now().year

# ── Feature sets ─────────────────────────────────────────────────────────────
NUMERIC   = ["car_age", "mileage", "power_kw", "range_km",
             "mileage_per_year", "is_electric", "is_hybrid"]
HIGH_CARD = ["make", "model", "trim_id", "variant_id", "generation_id"]
LOW_CARD  = ["fuel", "transmission", "seller_type"]

# Colour is added dynamically if the column exists and has data


def load_and_clean() -> tuple[pd.DataFrame, pd.Series]:
    con = sqlite3.connect(DB_PATH)
    df = pd.read_sql("SELECT * FROM listings", con)
    con.close()
    print(f"Loaded {len(df)} rows")

    df = df.dropna(subset=["price", "year", "mileage", "make", "model"])

    # Remove year outliers (data entry errors like 2040)
    df = df[df["year"] <= CURRENT_YEAR + 1]
    print(f"After cleaning: {len(df)} rows")

    # Fill missing categoricals
    for c in ["fuel", "transmission", "seller_type",
              "trim_id", "variant_id", "generation_id"]:
        df[c] = df[c].fillna("Unknown")

    # Core features
    df["car_age"] = CURRENT_YEAR - df["year"]

    # Engineered features
    df["mileage_per_year"] = df["mileage"] / df["car_age"].clip(lower=1)
    df["is_electric"] = (df["fuel"] == "Elektrisch").astype(int)
    df["is_hybrid"]   = df["fuel"].str.contains("Elektro/", na=False).astype(int)

    # range_km and power_kw stay as NaN — XGBoost handles missing numerics

    # Dynamically include colour if the column exists and has real data
    low_card = list(LOW_CARD)
    if "colour" in df.columns and df["colour"].notna().sum() > 1000:
        df["colour"] = df["colour"].fillna("Unknown")
        low_card.append("colour")
        print("[Using colour feature]")
    else:
        print("[Skipping colour — not enough data]")

    X = df[NUMERIC + HIGH_CARD + low_card]
    y = np.log1p(df["price"])
    return X, y, low_card


def build_pipeline(low_card: list) -> Pipeline:
    preprocessor = ColumnTransformer([
        ("target_enc",  TargetEncoder(smooth="auto"), HIGH_CARD),
        ("ordinal_enc", OrdinalEncoder(
            handle_unknown="use_encoded_value", unknown_value=-1
        ), low_card),
    ], remainder="passthrough")

    # Optuna-tuned hyperparameters (50 trials, 5-fold CV on 209k listings)
    # Baseline MAE: €2,585 → Tuned MAE: €2,216 (14.3% improvement)
    model = xgb.XGBRegressor(
        n_estimators=1416,
        learning_rate=0.114,
        max_depth=9,
        subsample=0.80,
        colsample_bytree=0.56,
        min_child_weight=9,
        gamma=0.01,
        reg_alpha=0.011,
        reg_lambda=7.96,
        random_state=42,
        n_jobs=-1,
    )

    return Pipeline([("preprocessor", preprocessor), ("model", model)])


def evaluate(pipeline: Pipeline, X: pd.DataFrame, y: pd.Series):
    print("\nRunning 5-fold cross-validation...")
    kf = KFold(n_splits=5, shuffle=True, random_state=42)
    mae_list, mape_list = [], []

    for train_idx, val_idx in kf.split(X):
        X_train, X_val = X.iloc[train_idx], X.iloc[val_idx]
        y_train, y_val = y.iloc[train_idx], y.iloc[val_idx]
        pipeline.fit(X_train, y_train)
        preds   = np.expm1(pipeline.predict(X_val))
        actuals = np.expm1(y_val)
        mae_list.append(np.abs(preds - actuals).mean())
        mape_list.append((np.abs(preds - actuals) / actuals).mean() * 100)

    mae  = np.array(mae_list)
    mape = np.array(mape_list)
    median_price = np.expm1(y).median()

    print(f"MAE:  {mae.mean():,.0f} ± {mae.std():,.0f} EUR")
    print(f"MAPE: {mape.mean():.2f} ± {mape.std():.2f}%")
    print(f"Median price: {median_price:,.0f} EUR")
    print(f"MAE as % of median: {mae.mean() / median_price * 100:.1f}%")

    # Log results
    results = {
        "timestamp": datetime.now().isoformat(),
        "rows": len(X),
        "features": list(X.columns),
        "mae_mean": round(float(mae.mean())),
        "mae_std": round(float(mae.std())),
        "mape_mean": round(float(mape.mean()), 2),
        "mape_std": round(float(mape.std()), 2),
        "median_price": round(float(median_price)),
    }
    with open("train_results.json", "w") as f:
        json.dump(results, f, indent=2)
    print("Results saved to train_results.json")


def train_and_save(pipeline: Pipeline, X: pd.DataFrame, y: pd.Series):
    print("\nTraining on full dataset...")
    pipeline.fit(X, y)
    joblib.dump(pipeline, "pipeline.joblib")
    print("Saved pipeline.joblib")

    # Feature importance
    model = pipeline.named_steps["model"]
    all_features = HIGH_CARD + list(X.columns[len(NUMERIC + HIGH_CARD):len(NUMERIC + HIGH_CARD) + len([c for c in X.columns if c not in NUMERIC and c not in HIGH_CARD])]) + NUMERIC
    # Simpler: just use column names after transform
    imp = model.feature_importances_
    feature_names = HIGH_CARD + [c for c in X.columns if c not in NUMERIC and c not in HIGH_CARD] + NUMERIC
    if len(feature_names) == len(imp):
        pairs = sorted(zip(feature_names, imp), key=lambda x: -x[1])
        print("\nFeature importance (gain):")
        for name, score in pairs:
            print(f"  {name:20s} {score:.4f}")


def retrain():
    X, y, low_card = load_and_clean()
    pipeline = build_pipeline(low_card)
    evaluate(pipeline, X, y)
    train_and_save(pipeline, X, y)


if __name__ == "__main__":
    retrain()
