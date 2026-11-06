# Athens Airbnb Dashboard

Local Streamlit dashboard for the loaded airbnb_athens PostgreSQL database.

## Requirements

- Python 3.13
- PostgreSQL with the airbnb_athens database loaded

Create and activate a virtual environment from the project root:

    py -3.13 -m venv .venv
    .\.venv\Scripts\Activate.ps1
    python -m pip install -r requirements.txt

## Database access

The dashboard uses the restricted airbnb_dashboard_ro role. From PowerShell, run the setup SQL as a PostgreSQL administrator:

    psql -h 127.0.0.1 -U postgres -d airbnb_athens -f DB/create_dashboard_readonly.sql

Set a password interactively so it is not written into project files or shell history:

    psql -h 127.0.0.1 -U postgres -d airbnb_athens
    \password airbnb_dashboard_ro
    \q

Create the user-local Streamlit secrets file at:

    %USERPROFILE%\.streamlit\secrets.toml

Add the connection URL, replacing the placeholder with the role password:

    [connections.airbnb_db]
    url = "postgresql+psycopg://airbnb_dashboard_ro:YOUR_PASSWORD@127.0.0.1:5432/airbnb_athens"

Keep this secrets file outside the repository. The role has column-level SELECT access to dashboard fields only.

For the current Windows account in this workspace, the read-only role and user-local Streamlit connection secret have already been provisioned. The steps above are for re-creating the setup or configuring another user.

## Run

From the project root:

    streamlit run app.py --server.address 127.0.0.1

The dashboard shows the listing scrape date range stored in PostgreSQL. It uses the availability_365 summary field for the availability panel and does not load the larger daily calendar table.

## Definitions and limitations

- “Recent and frequently booked” means a review within six months of the latest listing scrape and at least 60 estimated booked nights in the last 365 days.
- The default minimum-night cutoff is fewer than 28 nights. The default high-availability cutoff is at least 180 available days. Both are adjustable analytic settings, not legal definitions.
- License data is shown only as value recorded or no value recorded.
- The top-host ranking is citywide and limited to the 20 hosts with the most listings. Marketwide single-listing and multi-listing counts remain citywide.
- Occupancy and revenue are estimates. Missing price or revenue values are excluded from averages, not treated as zero. Listing coordinates are approximate.
