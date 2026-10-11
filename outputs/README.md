# Meridian Sales Dashboard

A self-contained e-commerce sales dashboard. It runs as a static website and does not need a server, package installation, or account. The included figures are illustrative sample data.

## Run it on your computer

1. Download or open `index.html` from the `outputs` folder.
2. Double-click the file, or right-click and choose your browser.
3. Select **Import CSV** to load your own sales data. The file is read locally in your browser.

Use a CSV with a header row. A minimal example:

```csv
date,revenue,orders,category,product
2026-01-05,125.50,1,Home,Ceramic mug
2026-01-06,89.00,1,Beauty,Face cream
```

The date column is required. For sales, provide either revenue or sales, or both quantity and unit price; the dashboard calculates revenue as quantity × unit price when needed. Invoice/order number is optional and lets the dashboard count distinct orders. Category (or country) and product (or description) are optional.

The provided `sales-data.csv` is the attached DataCamp export. When served as a website alongside the CSV, the dashboard loads it automatically. When opening `index.html` directly from your computer, choose **Import CSV** and select `sales-data.csv`. It contains 100 transaction rows from December 2010, so it is a small sample and cannot support a meaningful multi-month forecast by itself.

## Publish it as a website

This is a static site, so the only file to publish is `index.html`.

### GitHub Pages

1. Create a GitHub repository and add `index.html` at the repository root.
2. In the repository, open **Settings → Pages**.
3. Under the build and deployment section, choose **Deploy from a branch**, select the `main` branch and `/ (root)`, then save.
4. Open the published address shown in the Pages settings after the deployment completes.

### Any static hosting provider

Create a new static site, upload `index.html` as the site entry page, and use the public address provided by the host. No build command or output folder is needed.

## Notes

- Imported data is processed in the browser and is not uploaded by this page.
- The forecast is a simple straight-line trend over the selected months. Treat it as a directional estimate; it does not model seasonality, promotions, inventory, or external events.
- The interface uses an optional Google Fonts stylesheet. If unavailable, it falls back to system fonts.

