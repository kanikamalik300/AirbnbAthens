"""Create a compact SQLite snapshot for the hosted Streamlit dashboard.

The exporter reads only fields granted to the airbnb_dashboard_ro role and
stores them in Dashboard/athens_snapshot.sqlite. It gets the connection URL
from AIRBNB_DATABASE_URL or the existing local Streamlit secrets file.
"""

from __future__ import annotations

import os
import sqlite3
import sys
import tempfile
import tomllib
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_PATH = ROOT / "Dashboard" / "athens_snapshot.sqlite"

LISTINGS_SQL = """
SELECT
    l.listing_id,
    l.host_id,
    l.name,
    l.neighbourhood,
    l.neighbourhood_cleansed,
    l.neighbourhood_fk,
    l.latitude::double precision AS latitude,
    l.longitude::double precision AS longitude,
    l.room_type,
    l.price_amount::double precision AS price_amount,
    l.minimum_nights,
    l.number_of_reviews_ltm,
    l.estimated_occupancy_l365d::double precision
        AS estimated_occupancy_l365d,
    l.estimated_revenue_l365d::double precision
        AS estimated_revenue_l365d,
    l.last_review::text AS last_review,
    l.license,
    l.last_scraped::text AS last_scraped
FROM public.listings AS l
"""

HOSTS_SQL = """
SELECT h.host_id, h.host_name
FROM public.hosts AS h
WHERE EXISTS (
    SELECT 1 FROM public.listings AS l WHERE l.host_id = h.host_id
)
"""

NEIGHBORHOODS_SQL = """
SELECT neighbourhood_name
FROM public.neighbourhoods
"""


def database_url() -> str:
    value = os.environ.get("AIRBNB_DATABASE_URL")
    if value:
        return value

    candidates = (
        Path.home() / ".streamlit" / "secrets.toml",
        ROOT / ".streamlit" / "secrets.toml",
        ROOT / "Dashboard" / ".streamlit" / "secrets.toml",
    )
    for path in candidates:
        if not path.is_file():
            continue
        try:
            secrets = tomllib.loads(path.read_text(encoding="utf-8"))
            value = secrets["connections"]["airbnb_db"]["url"]
        except (OSError, KeyError, tomllib.TOMLDecodeError):
            continue
        if value:
            return value

    raise RuntimeError(
        "Set AIRBNB_DATABASE_URL or configure [connections.airbnb_db] in a local secrets file."
    )


def read_table(engine, query: str) -> pd.DataFrame:
    with engine.connect() as connection:
        return pd.read_sql_query(text(query), connection)


def main() -> int:
    temporary_path = None
    engine = None
    try:
        url = database_url()
        engine = create_engine(url, connect_args={"connect_timeout": 5})
        listings = read_table(engine, LISTINGS_SQL)
        hosts = read_table(engine, HOSTS_SQL)
        neighborhoods = read_table(engine, NEIGHBORHOODS_SQL)

        OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            prefix="athens_snapshot_",
            suffix=".sqlite",
            dir=OUTPUT_PATH.parent,
            delete=False,
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)

        database = sqlite3.connect(temporary_path)
        try:
            listings.to_sql("listings", database, if_exists="replace", index=False)
            hosts.to_sql("hosts", database, if_exists="replace", index=False)
            neighborhoods.to_sql(
                "neighbourhoods", database, if_exists="replace", index=False
            )
            database.executescript(
                """
                CREATE INDEX listings_host_id_idx ON listings(host_id);
                CREATE INDEX listings_neighbourhood_fk_idx
                    ON listings(neighbourhood_fk);
                CREATE INDEX listings_room_type_idx ON listings(room_type);
                CREATE INDEX listings_last_review_idx ON listings(last_review);
                CREATE INDEX hosts_host_id_idx ON hosts(host_id);
                """
            )
            database.commit()
        finally:
            database.close()

        os.replace(temporary_path, OUTPUT_PATH)
        temporary_path = None
        print(
            f"Wrote {len(listings):,} listings, {len(hosts):,} hosts, and "
            f"{len(neighborhoods):,} neighborhoods to {OUTPUT_PATH}"
        )
        return 0
    except Exception as exc:
        print(
            f"Snapshot export failed ({type(exc).__name__}); connection details were redacted.",
            file=sys.stderr,
        )
        return 1
    finally:
        if engine is not None:
            engine.dispose()
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


if __name__ == "__main__":
    raise SystemExit(main())
