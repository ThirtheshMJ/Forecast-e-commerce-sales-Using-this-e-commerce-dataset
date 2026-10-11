# Forecast e-commerce sales

A reproducible analysis of the Online Retail transaction dataset: data quality checks, revenue trends, country-level order comparisons, product grouping, customer segmentation, and a short-horizon sales forecast.

## Dataset

The project uses DataCamp's [E-Commerce Data dataset](https://www.datacamp.com/datalab/datasets/dataset-r-e-commerce), which describes an online gift retailer. For a self-contained local run, download the matching [UCI Online Retail dataset](https://archive.ics.uci.edu/dataset/352/online+retail) and save `Online Retail.xlsx` in the project root. The UCI version contains 541,909 transactions from 1 December 2010 through 9 December 2011 and is licensed CC BY 4.0. Please cite Chen (2015), UCI Machine Learning Repository, DOI: 10.24432/C5BW33.

The script can also fetch UCI dataset 352 directly if no local file is supplied. The full source data is not committed; the repository includes a 100-row DataCamp CSV sample for the dashboard.

## Run

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt

# Use a downloaded Excel file:
python src/forecast_sales.py --input "Online Retail.xlsx"

# Or fetch the public UCI dataset:
python src/forecast_sales.py
```

The run writes charts, CSV tables, and `run_summary.txt` to `outputs/`. Change the output folder and forecast horizon with `--output` and `--horizon`.

## What it produces

- Monthly gross sales, return value, and net revenue; returns and cancellation lines remain visible as negative revenue reversals.
- A three-month damped Holt trend forecast, evaluated against the final three observed months and a last-month-value baseline. The fitted forecast is clipped at zero for business-facing predictions.
- Country-level order counts, average and median order value, and average units per order, ranked by gross sales.
- A transparent keyword-based product category and unit-price band for each stock code/description pair.
- Customer RFM segments using positive-purchase transactions, when a customer ID is present.
- CSV exports and PNG charts for monthly revenue, country order size, and product-category revenue.

## Interpretation and limitations

The source covers roughly one year, with the final month incomplete. The script forecasts **net transaction revenue** (quantity × unit price, retaining negative-quantity reversals), while country order-size comparisons use positive sales only. It reports negative quantities, cancellations, missing IDs, duplicate rows, and non-positive prices instead of silently treating every row as a sale.

The forecast is intentionally trend-only: a single annual cycle is too little history to establish reliable yearly seasonality. Backtest metrics are based on only the last three months and should be treated as a sanity check, not proof of future accuracy. Product groups are heuristic labels based on descriptions; inspect the “Other / unclassified” group before using categories for decisions. Revenue is not profit because cost data is not provided.

## Source

- DataCamp: [E-Commerce Data](https://www.datacamp.com/datalab/datasets/dataset-r-e-commerce)
- Chen, D. (2015). [Online Retail](https://archive.ics.uci.edu/dataset/352/online+retail). UCI Machine Learning Repository. DOI: 10.24432/C5BW33. Licensed CC BY 4.0.


## Interactive dashboard

Open `index.html` locally, or enable GitHub Pages from the `main` branch and repository root. The dashboard loads `sales-data.csv` automatically when hosted; when opening the file locally, use **Import CSV** to load it. The included CSV is a small 100-row sample from December 2010, so it is not suitable for a meaningful multi-month forecast. The dashboard calculates transaction revenue from quantity × unit price and counts distinct invoices as orders. User-provided transaction data stays in the public repository as requested.

See `outputs/README.md` for details on the dashboard and the CSV format.
