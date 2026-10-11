#!/usr/bin/env python3
"""Reproducible analysis for the UCI/DataCamp Online Retail transaction data."""

from __future__ import annotations

import argparse
from pathlib import Path
import re
import warnings

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from statsmodels.tsa.holtwinters import ExponentialSmoothing


REQUIRED_COLUMNS = {
    "invoiceno", "stockcode", "description", "quantity",
    "invoicedate", "unitprice", "customerid", "country",
}


def normalize_columns(frame: pd.DataFrame) -> pd.DataFrame:
    """Normalize dataset headers while retaining the expected UCI field names."""
    frame = frame.copy()
    frame.columns = [
        re.sub(r"[^a-z]", "", str(column).lower()) for column in frame.columns
    ]
    missing = REQUIRED_COLUMNS - set(frame.columns)
    if missing:
        raise ValueError(f"Dataset is missing required columns: {sorted(missing)}")
    return frame


def load_data(path: Path | None) -> pd.DataFrame:
    """Load a local Excel/CSV file, or fetch the public UCI dataset."""
    if path is not None:
        if not path.exists():
            raise FileNotFoundError(f"Input file not found: {path}")
        suffix = path.suffix.lower()
        if suffix in {".xlsx", ".xls"}:
            frame = pd.read_excel(path)
        elif suffix == ".csv":
            frame = pd.read_csv(path)
        else:
            raise ValueError("Input must be .xlsx, .xls, or .csv")
        return normalize_columns(frame)

    from ucimlrepo import fetch_ucirepo

    dataset = fetch_ucirepo(id=352)
    parts = [part for part in (dataset.data.features, dataset.data.targets) if part is not None]
    return normalize_columns(pd.concat(parts, axis=1))


def prepare_data(raw: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, int]]:
    """Parse fields, preserve returns, and flag suspicious records for review."""
    frame = raw.copy()
    frame["invoicedate"] = pd.to_datetime(frame["invoicedate"], errors="coerce")
    frame["quantity"] = pd.to_numeric(frame["quantity"], errors="coerce")
    frame["unitprice"] = pd.to_numeric(frame["unitprice"], errors="coerce")
    frame["invoiceno"] = frame["invoiceno"].astype("string").str.strip()
    frame["stockcode"] = frame["stockcode"].astype("string").str.strip()
    frame["country"] = frame["country"].astype("string").str.strip()
    frame["description"] = frame["description"].fillna("Unknown product").astype(str).str.strip()

    exact_duplicates = int(frame.duplicated().sum())
    frame = frame.drop_duplicates().copy()
    required = ["invoiceno", "stockcode", "invoicedate", "quantity", "unitprice", "country"]
    missing_required = int(frame[required].isna().any(axis=1).sum())
    frame = frame.dropna(subset=required).copy()
    frame["is_cancellation"] = frame["invoiceno"].str.upper().str.startswith("C", na=False)
    frame["is_return_or_reversal"] = frame["quantity"] < 0
    frame["is_zero_or_negative_price"] = frame["unitprice"] <= 0

    # Keep negative quantities with positive prices as revenue reversals.
    # Exclude non-positive prices from the sales measure and report their count.
    frame["revenue"] = np.where(frame["unitprice"] > 0, frame["quantity"] * frame["unitprice"], 0.0)
    frame["gross_sales"] = np.where(
        (frame["quantity"] > 0) & (frame["unitprice"] > 0),
        frame["quantity"] * frame["unitprice"],
        0.0,
    )
    frame["return_value"] = np.where(
        (frame["quantity"] < 0) & (frame["unitprice"] > 0),
        -frame["quantity"] * frame["unitprice"],
        0.0,
    )

    diagnostics = {
        "raw_rows": len(raw),
        "exact_duplicate_rows_removed": exact_duplicates,
        "rows_missing_required_fields_removed": missing_required,
        "negative_quantity_rows": int(frame["is_return_or_reversal"].sum()),
        "cancellation_invoice_rows": int(frame["is_cancellation"].sum()),
        "rows_with_nonpositive_unit_price": int(frame["is_zero_or_negative_price"].sum()),
        "rows_missing_customer_id": int(frame["customerid"].isna().sum()),
    }
    return frame, diagnostics


def monthly_series(frame: pd.DataFrame) -> pd.DataFrame:
    dated = frame.set_index("invoicedate").sort_index()
    monthly = dated[["revenue", "gross_sales", "return_value"]].resample("MS").sum()
    monthly = monthly.asfreq("MS", fill_value=0)
    monthly.index.name = "month"
    return monthly.reset_index()


def forecast_revenue(monthly: pd.DataFrame, horizon: int = 3) -> tuple[pd.DataFrame, dict[str, float]]:
    """Backtest damped Holt trend on the last three months, then refit all history."""
    series = monthly.set_index("month")["revenue"].astype(float).asfreq("MS", fill_value=0)
    if len(series) < 6:
        raise ValueError("Need at least six monthly observations for a three-month holdout.")

    test_size = min(3, max(1, len(series) // 4))
    train, test = series.iloc[:-test_size], series.iloc[-test_size:]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        fitted = ExponentialSmoothing(
            train, trend="add", damped_trend=True, seasonal=None,
            initialization_method="estimated",
        ).fit(optimized=True)
    predicted = fitted.forecast(len(test))
    naive = pd.Series(train.iloc[-1], index=test.index)
    mae = float(np.mean(np.abs(test.to_numpy() - predicted.to_numpy())))
    rmse = float(np.sqrt(np.mean((test.to_numpy() - predicted.to_numpy()) ** 2)))
    denominator = np.abs(test.to_numpy()) + np.abs(predicted.to_numpy())
    smape = float(np.mean(np.divide(
        200 * np.abs(test.to_numpy() - predicted.to_numpy()),
        denominator,
        out=np.zeros_like(denominator, dtype=float),
        where=denominator != 0,
    )))
    naive_mae = float(np.mean(np.abs(test.to_numpy() - naive.to_numpy())))

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        final_model = ExponentialSmoothing(
            series, trend="add", damped_trend=True, seasonal=None,
            initialization_method="estimated",
        ).fit(optimized=True)
    future = final_model.forecast(horizon).clip(lower=0)
    output = pd.DataFrame({
        "month": future.index,
        "forecast_net_revenue": future.to_numpy(),
        "model": "damped Holt trend",
    })
    metrics = {
        "holdout_months": float(test_size),
        "holdout_mae": mae,
        "holdout_rmse": rmse,
        "holdout_smape_percent": smape,
        "last_month_baseline_mae": naive_mae,
    }
    return output, metrics


def product_category(description: str) -> str:
    text = description.lower()
    groups = {
        "Home decor": ("candle", "lantern", "frame", "mirror", "light", "ornament", "holder"),
        "Kitchen & dining": ("mug", "cup", "plate", "bowl", "spoon", "teapot", "cutlery", "kitchen"),
        "Stationery": ("card", "notebook", "pen", "paper", "letter", "pencil", "writing"),
        "Textiles": ("bag", "towel", "cushion", "fabric", "apron", "blanket", "textile"),
        "Jewelry & accessories": ("necklace", "bracelet", "earring", "ring", "brooch", "jewelry"),
        "Toys & games": ("toy", "game", "doll", "puzzle", "toy"),
        "Garden": ("garden", "plant", "flower", "bird", "outdoor"),
        "Seasonal & gifts": ("christmas", "easter", "valentine", "gift", "party", "birthday"),
        "Storage & organization": ("box", "basket", "organizer", "storage", "tin"),
    }
    for category, terms in groups.items():
        if any(term in text for term in terms):
            return category
    return "Other / unclassified"


def product_summary(frame: pd.DataFrame) -> pd.DataFrame:
    products = frame.groupby(["stockcode", "description"], dropna=False).agg(
        units_sold=("quantity", lambda values: values.clip(lower=0).sum()),
        net_revenue=("revenue", "sum"),
        transactions=("invoiceno", "nunique"),
        average_unit_price=("unitprice", "mean"),
    ).reset_index()
    products["category"] = products["description"].map(product_category)
    # Broad unit-price bands add a second, transparent product characteristic.
    products["price_band"] = pd.cut(
        products["average_unit_price"],
        bins=[-np.inf, 2, 10, 25, 100, np.inf],
        labels=["under £2", "£2–£10", "£10–£25", "£25–£100", "over £100"],
    ).astype("string")
    return products.sort_values("net_revenue", ascending=False)


def customer_segments(frame: pd.DataFrame) -> pd.DataFrame:
    dated = frame.dropna(subset=["customerid"]).copy()
    sales = dated[dated["quantity"] > 0].copy()
    if sales.empty:
        return pd.DataFrame(columns=["customerid", "recency_days", "frequency", "monetary", "segment"])
    snapshot = dated["invoicedate"].max() + pd.Timedelta(days=1)
    rfm = sales.groupby("customerid").agg(
        last_purchase=("invoicedate", "max"),
        frequency=("invoiceno", "nunique"),
        monetary=("gross_sales", "sum"),
    ).reset_index()
    rfm["recency_days"] = (snapshot - rfm["last_purchase"]).dt.days
    rfm["r_score"] = pd.qcut(rfm["recency_days"].rank(method="first"), 4, labels=[4, 3, 2, 1]).astype(int)
    rfm["f_score"] = pd.qcut(rfm["frequency"].rank(method="first"), 4, labels=[1, 2, 3, 4]).astype(int)
    rfm["m_score"] = pd.qcut(rfm["monetary"].rank(method="first"), 4, labels=[1, 2, 3, 4]).astype(int)
    rfm["segment"] = np.select(
        [
            (rfm["r_score"] >= 3) & (rfm["f_score"] >= 3) & (rfm["m_score"] >= 3),
            (rfm["r_score"] <= 2) & (rfm["f_score"] >= 3),
            (rfm["r_score"] >= 3) & (rfm["f_score"] <= 2),
        ],
        ["Champions", "At risk loyal", "New / promising"],
        default="Core customers",
    )
    return rfm.drop(columns=["last_purchase", "r_score", "f_score", "m_score"])


def country_summary(frame: pd.DataFrame) -> pd.DataFrame:
    positive = frame[frame["gross_sales"] > 0]
    orders = positive.groupby(["country", "invoiceno"]).agg(
        order_value=("gross_sales", "sum"),
        items=("quantity", "sum"),
    ).reset_index()
    summary = orders.groupby("country").agg(
        orders=("invoiceno", "nunique"),
        gross_sales=("order_value", "sum"),
        average_order_value=("order_value", "mean"),
        median_order_value=("order_value", "median"),
        average_units_per_order=("items", "mean"),
    ).reset_index()
    return summary.sort_values("gross_sales", ascending=False)


def make_charts(monthly: pd.DataFrame, forecast: pd.DataFrame, countries: pd.DataFrame, products: pd.DataFrame, out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=(11, 5))
    ax.plot(monthly["month"], monthly["revenue"], marker="o", label="Observed net revenue")
    ax.plot(forecast["month"], forecast["forecast_net_revenue"], marker="o", linestyle="--", label="Damped Holt forecast")
    ax.set(title="Monthly net revenue and 3-month forecast", ylabel="Revenue (£)", xlabel="Month")
    ax.grid(alpha=.25)
    ax.legend()
    fig.tight_layout()
    fig.savefig(out / "monthly_revenue_forecast.png", dpi=160)
    plt.close(fig)

    top = countries.head(10).sort_values("average_order_value")
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.barh(top["country"], top["average_order_value"], color="#4472C4")
    ax.set(title="Average order value by country (top 10 by gross sales)", xlabel="Average order value (£)")
    fig.tight_layout()
    fig.savefig(out / "country_order_value.png", dpi=160)
    plt.close(fig)

    category = products.groupby("category", as_index=False)["net_revenue"].sum().sort_values("net_revenue")
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.barh(category["category"], category["net_revenue"], color="#70AD47")
    ax.set(title="Net revenue by rule-based product category", xlabel="Net revenue (£)")
    fig.tight_layout()
    fig.savefig(out / "product_category_revenue.png", dpi=160)
    plt.close(fig)


def run(input_path: Path | None, output_dir: Path, horizon: int) -> None:
    raw = load_data(input_path)
    frame, diagnostics = prepare_data(raw)
    monthly = monthly_series(frame)
    forecast, metrics = forecast_revenue(monthly, horizon=horizon)
    countries = country_summary(frame)
    products = product_summary(frame)
    customers = customer_segments(frame)

    output_dir.mkdir(parents=True, exist_ok=True)
    monthly.to_csv(output_dir / "monthly_sales.csv", index=False)
    forecast.to_csv(output_dir / "forecast.csv", index=False)
    countries.to_csv(output_dir / "country_summary.csv", index=False)
    products.to_csv(output_dir / "product_categories.csv", index=False)
    customers.to_csv(output_dir / "customer_segments.csv", index=False)
    make_charts(monthly, forecast, countries, products, output_dir)

    report = [
        "E-commerce sales forecast run",
        f"Input rows: {diagnostics['raw_rows']:,}",
        f"Rows after de-duplication and required-field cleaning: {len(frame):,}",
        f"Date range: {frame['invoicedate'].min()} to {frame['invoicedate'].max()}",
        f"Distinct products: {frame['stockcode'].nunique():,}",
        f"Distinct identified customers: {frame['customerid'].nunique():,}",
        f"Negative-quantity rows retained as reversals: {diagnostics['negative_quantity_rows']:,}",
        f"Cancellation invoice rows: {diagnostics['cancellation_invoice_rows']:,}",
        f"Non-positive unit-price rows excluded from revenue: {diagnostics['rows_with_nonpositive_unit_price']:,}",
        "",
        "Holdout evaluation (last observed months):",
        *[f"{key}: {value:.2f}" for key, value in metrics.items()],
        "",
        "Forecast values are in forecast.csv. The data spans about one year, so this trend-only forecast is an exploratory short-horizon baseline, not a seasonal or causal forecast.",
    ]
    (output_dir / "run_summary.txt").write_text("\n".join(report) + "\n", encoding="utf-8")
    print("\n".join(report))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, help="Local .xlsx/.xls/.csv; omitted fetches UCI dataset 352")
    parser.add_argument("--output", type=Path, default=Path("outputs"), help="Directory for CSVs, charts, and summary")
    parser.add_argument("--horizon", type=int, default=3, help="Forecast horizon in months (default: 3)")
    args = parser.parse_args()
    if args.horizon < 1:
        parser.error("--horizon must be at least 1")
    run(args.input, args.output, args.horizon)


if __name__ == "__main__":
    main()
