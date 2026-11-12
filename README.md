# Athens Airbnb Dashboard

Streamlit dashboard for an Athens Airbnb data snapshot.

## Requirements

- Python 3.13
- PostgreSQL is needed only when refreshing the packaged snapshot

Create the `uv` environment from the project root and install the requirements:

    py -3.13 -m uv venv --python 3.13 .venv
    py -3.13 -m uv pip install --python .venv\Scripts\python.exe -r Dashboard\requirements.txt

## Packaged snapshot

The app runs from `Dashboard/athens_snapshot.sqlite`; it does not connect to PostgreSQL at runtime. The snapshot contains only the listing, host-name, and neighborhood fields used by the dashboard.

To rebuild the snapshot after refreshing the local database, run from the project root:

    .venv\Scripts\python.exe Database\export_dashboard_snapshot.py

The exporter reads the URL from `AIRBNB_DATABASE_URL` or `[connections.airbnb_db]` in the user-local Streamlit secrets file. It uses the read-only `airbnb_dashboard_ro` account and writes a compact SQLite file. Keep credentials outside the repository. Commit the refreshed SQLite file when you want the hosted dashboard to use a newer snapshot.

For a local PostgreSQL setup, run the role setup SQL as a PostgreSQL administrator:

    psql -h 127.0.0.1 -U postgres -d airbnb_athens -f Dashboard/Database/create_dashboard_readonly.sql

Set the read-only role password interactively:

    psql -h 127.0.0.1 -U postgres -d airbnb_athens
    \password airbnb_dashboard_ro
    \q

Create `%USERPROFILE%\.streamlit\secrets.toml` with this connection:

    [connections.airbnb_db]
    url = "postgresql+psycopg://airbnb_dashboard_ro:YOUR_PASSWORD@127.0.0.1:5432/airbnb_athens"

The role has column-level SELECT access to dashboard fields only. The local secret file is ignored by Git.

## Run

From the project root, start the app from `Dashboard` so Streamlit loads its theme configuration:

    Set-Location Dashboard
    ..\.venv\Scripts\python.exe -m streamlit run app.py --server.address 127.0.0.1

The dashboard shows the listing scrape date range embedded in the snapshot. The export omits the larger daily calendar table.

## Definitions and limitations

- “Recent and frequently booked” means a review within six months of the latest listing scrape and at least 60 estimated booked nights in the last 365 days.
- The default short-term threshold is fewer than 28 minimum nights. Listings at or above the threshold are shown as having a longer minimum stay. Percentages use only listings with a minimum-night value; this is an analytic category, not a legal definition or proof of actual stay length.
- License data is shown as value recorded, explicitly marked exempt, or blank. “Marked exempt” only reflects an explicit marker in the raw field and does not verify legal status.
- The loaded Athens file has 160 explicit exempt markers, 14,463 other recorded values, and 511 blank values.
- The top-host ranking is citywide and limited to the 20 hosts with the most listings. Marketwide single-listing and multi-listing counts remain citywide.
- Occupancy and revenue are estimates. Missing price or revenue values are excluded from averages, not treated as zero. Listing coordinates are approximate.
