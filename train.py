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

NUMERIC   = ["car_age", "mileage", "power_kw", "range_km"]
HIGH_CARD = ["make", "model", "trim_id", "variant_id", "generation_id"]  # target-encoded
LOW_CARD  = ["fuel", "transmission", "seller_type", "body_type", "colour"] # ordinal-encoded


def load_and_clean() -> tuple[pd.DataFrame, pd.Series]:
    con = sqlite3.connect(DB_PATH)
    df = pd.read_sql("SELECT * FROM listings", con)
    con.close()
    print(f"Loaded {len(df)} rows")

    df = df.dropna(subset=["price", "year", "mileage", "make", "model"])
    print(f"After dropping essential nulls: {len(df)} rows")

    df["fuel"]          = df["fuel"].fillna("Unknown")
    df["transmission"]  = df["transmission"].fillna("Unknown")
    df["seller_type"]   = df["seller_type"].fillna("Unknown")
    df["body_type"]     = df["body_type"].fillna("Unknown")
    df["colour"]        = df["colour"].fillna("Unknown")
    df["trim_id"]       = df["trim_id"].fillna("Unknown")
    df["variant_id"]    = df["variant_id"].fillna("Unknown")
    df["generation_id"] = df["generation_id"].fillna("Unknown")
    df["car_age"]      = CURRENT_YEAR - df["year"]
    # range_km and power_kw stay as NaN — XGBoost handles missing numerics natively

    X = df[NUMERIC + HIGH_CARD + LOW_CARD]
    y = np.log1p(df["price"])  # log-transform: model learns % errors, not absolute
    return X, y


def build_pipeline() -> Pipeline:
    preprocessor = ColumnTransformer([
        ("target_enc",  TargetEncoder(smooth="auto"), HIGH_CARD),
        ("ordinal_enc", OrdinalEncoder(
            handle_unknown="use_encoded_value", unknown_value=-1
        ), LOW_CARD),
    ], remainder="passthrough")

    model = xgb.XGBRegressor(
        n_estimators=500,
        learning_rate=0.05,
        max_depth=6,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42,
        n_jobs=-1,
    )

    return Pipeline([("preprocessor", preprocessor), ("model", model)])


def evaluate(pipeline: Pipeline, X: pd.DataFrame, y: pd.Series):
    print("\nRunning 5-fold cross-validation...")
    kf = KFold(n_splits=5, shuffle=True, random_state=42)
    mae_list = []
    for train_idx, val_idx in kf.split(X):
        X_train, X_val = X.iloc[train_idx], X.iloc[val_idx]
        y_train, y_val = y.iloc[train_idx], y.iloc[val_idx]
        pipeline.fit(X_train, y_train)
        preds   = np.expm1(pipeline.predict(X_val))
        actuals = np.expm1(y_val)
        mae_list.append(np.abs(preds - actuals).mean())

    mae_scores   = np.array(mae_list)
    median_price = np.expm1(y).median()
    print(f"MAE:  {mae_scores.mean():,.0f} ± {mae_scores.std():,.0f} EUR")
    print(f"Median price in dataset: {median_price:,.0f} EUR")
    print(f"MAE as % of median: {mae_scores.mean() / median_price * 100:.1f}%")


def train_and_save(pipeline: Pipeline, X: pd.DataFrame, y: pd.Series):
    print("\nTraining on full dataset...")
    pipeline.fit(X, y)
    joblib.dump(pipeline, "pipeline.joblib")
    print("Saved pipeline.joblib")


def retrain():
    X, y = load_and_clean()
    pipeline = build_pipeline()
    evaluate(pipeline, X, y)
    train_and_save(pipeline, X, y)


if __name__ == "__main__":
    retrain()
