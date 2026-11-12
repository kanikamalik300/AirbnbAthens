"""Read-only, parameterized queries for the Athens Airbnb dashboard."""

from __future__ import annotations

from datetime import date
from typing import Any, Sequence


CACHE_TTL_SECONDS = 300
NEIGHBORHOOD_EXPR = (
    "COALESCE(n.neighbourhood_name, l.neighbourhood_fk, "
    "l.neighbourhood_cleansed, l.neighbourhood, '(unknown)')"
)


def _filters(
    neighborhoods: Sequence[str] | None = None,
    room_types: Sequence[str] | None = None,
    activity_only: bool = False,
    snapshot_date: date | None = None,
) -> tuple[str, dict[str, Any]]:
    """Build a WHERE clause with fixed SQL expressions and bound values."""
    clauses: list[str] = []
    params: dict[str, Any] = {}

    if neighborhoods:
        names = []
        for index, value in enumerate(neighborhoods):
            name = f"neighborhood_{index}"
            names.append(f":{name}")
            params[name] = value
        clauses.append(f"{NEIGHBORHOOD_EXPR} IN ({', '.join(names)})")

    if room_types:
        names = []
        for index, value in enumerate(room_types):
            name = f"room_type_{index}"
            names.append(f":{name}")
            params[name] = value
        clauses.append(f"l.room_type IN ({', '.join(names)})")

    if activity_only and snapshot_date is not None:
        clauses.append(
            "l.last_review >= CAST(:activity_anchor AS DATE) - INTERVAL '6 months'"
        )
        clauses.append("l.estimated_occupancy_l365d >= :frequent_nights")
        params["activity_anchor"] = snapshot_date
        params["frequent_nights"] = 60

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    return where, params


def _query(connection: Any, sql: str, params: dict[str, Any] | None = None):
    return connection.query(
        sql,
        params=params or {},
        ttl=CACHE_TTL_SECONDS,
        show_spinner=False,
    )


def get_metadata(connection: Any):
    return _query(
        connection,
        """
        SELECT
            COUNT(l.listing_id) AS listing_count,
            MIN(l.last_scraped) AS first_listing_scrape,
            MAX(l.last_scraped) AS latest_listing_scrape
        FROM public.listings AS l
        """,
    )


def get_neighborhood_options(connection: Any):
    return _query(
        connection,
        f"""
        SELECT DISTINCT {NEIGHBORHOOD_EXPR} AS neighborhood
        FROM public.listings AS l
        LEFT JOIN public.neighbourhoods AS n
          ON n.neighbourhood_name = l.neighbourhood_fk
        ORDER BY neighborhood
        """,
    )


def get_top_neighborhood(
    connection: Any,
    neighborhoods: Sequence[str] | None,
    room_types: Sequence[str] | None,
    activity_only: bool,
    snapshot_date: date | None,
):
    where, params = _filters(
        neighborhoods, room_types, activity_only, snapshot_date
    )
    return _query(
        connection,
        f"""
        SELECT {NEIGHBORHOOD_EXPR} AS neighborhood,
               COUNT(l.listing_id) AS listing_count
        FROM public.listings AS l
        LEFT JOIN public.neighbourhoods AS n
          ON n.neighbourhood_name = l.neighbourhood_fk
        {where}
        GROUP BY neighborhood
        ORDER BY listing_count DESC, neighborhood
        LIMIT 1
        """,
        params,
    )


def get_room_type_options(connection: Any):
    return _query(
        connection,
        """
        SELECT DISTINCT l.room_type
        FROM public.listings AS l
        WHERE l.room_type IS NOT NULL
        ORDER BY l.room_type
        """,
    )


def get_overview_counts(
    connection: Any,
    neighborhoods: Sequence[str] | None,
    room_types: Sequence[str] | None,
    activity_only: bool,
    snapshot_date: date | None,
):
    where, params = _filters(
        neighborhoods, room_types, activity_only, snapshot_date
    )
    return _query(
        connection,
        f"""
        SELECT
            COUNT(l.listing_id) AS listing_count,
            COUNT(l.listing_id) FILTER (
                WHERE l.room_type = 'Entire home/apt'
            ) AS entire_home_count,
            COUNT(l.listing_id) FILTER (
                WHERE l.license IS NOT NULL
                  AND BTRIM(l.license) <> ''
                  AND LOWER(BTRIM(l.license)) NOT IN ('exempt', 'exempted')
            ) AS license_value_recorded,
            COUNT(l.price_amount) AS listings_with_price
        FROM public.listings AS l
        LEFT JOIN public.neighbourhoods AS n
          ON n.neighbourhood_name = l.neighbourhood_fk
        {where}
        """,
        params,
    )


def get_room_type_counts(
    connection: Any,
    neighborhoods: Sequence[str] | None,
    room_types: Sequence[str] | None,
    activity_only: bool,
    snapshot_date: date | None,
):
    where, params = _filters(
        neighborhoods, room_types, activity_only, snapshot_date
    )
    return _query(
        connection,
        f"""
        SELECT l.room_type, COUNT(l.listing_id) AS listing_count
        FROM public.listings AS l
        LEFT JOIN public.neighbourhoods AS n
          ON n.neighbourhood_name = l.neighbourhood_fk
        {where}
        GROUP BY l.room_type
        ORDER BY listing_count DESC, l.room_type
        """,
        params,
    )


def get_map_listings(
    connection: Any,
    neighborhoods: Sequence[str] | None,
    room_types: Sequence[str] | None,
    activity_only: bool,
    snapshot_date: date | None,
):
    where, params = _filters(
        neighborhoods, room_types, activity_only, snapshot_date
    )
    return _query(
        connection,
        f"""
        SELECT
            l.listing_id,
            l.name,
            {NEIGHBORHOOD_EXPR} AS neighborhood,
            l.room_type,
            l.latitude,
            l.longitude,
            l.price_amount AS nightly_price_eur,
            l.minimum_nights,
            l.number_of_reviews_ltm AS reviews_last_12_months,
            l.estimated_occupancy_l365d AS estimated_booked_nights,
            l.estimated_revenue_l365d AS estimated_revenue_year
        FROM public.listings AS l
        LEFT JOIN public.neighbourhoods AS n
          ON n.neighbourhood_name = l.neighbourhood_fk
        {where}
        ORDER BY l.listing_id
        """,
        params,
    )


def get_activity_metrics(
    connection: Any,
    neighborhoods: Sequence[str] | None,
    room_types: Sequence[str] | None,
    activity_only: bool,
    snapshot_date: date | None,
):
    where, params = _filters(
        neighborhoods, room_types, activity_only, snapshot_date
    )
    return _query(
        connection,
        f"""
        SELECT
            COUNT(l.listing_id) AS listing_count,
            AVG(l.estimated_occupancy_l365d) AS average_estimated_nights,
            AVG(l.price_amount) AS average_nightly_price_eur,
            COUNT(l.price_amount) AS listings_with_price,
            AVG(l.estimated_revenue_l365d) AS average_estimated_revenue_eur,
            COUNT(l.estimated_revenue_l365d) AS listings_with_revenue
        FROM public.listings AS l
        LEFT JOIN public.neighbourhoods AS n
          ON n.neighbourhood_name = l.neighbourhood_fk
        {where}
        """,
        params,
    )


def get_occupancy_distribution(
    connection: Any,
    neighborhoods: Sequence[str] | None,
    room_types: Sequence[str] | None,
    activity_only: bool,
    snapshot_date: date | None,
):
    where, params = _filters(
        neighborhoods, room_types, activity_only, snapshot_date
    )
    return _query(
        connection,
        f"""
        WITH bucketed AS (
            SELECT
                l.listing_id,
                CASE
                    WHEN l.estimated_occupancy_l365d IS NULL THEN 'Unknown'
                    WHEN l.estimated_occupancy_l365d = 0 THEN '0'
                    WHEN l.estimated_occupancy_l365d <= 30 THEN '1-30'
                    WHEN l.estimated_occupancy_l365d <= 60 THEN '31-60'
                    WHEN l.estimated_occupancy_l365d <= 90 THEN '61-90'
                    WHEN l.estimated_occupancy_l365d <= 120 THEN '91-120'
                    WHEN l.estimated_occupancy_l365d <= 180 THEN '121-180'
                    ELSE '181+'
                END AS nights_bucket,
                CASE
                    WHEN l.estimated_occupancy_l365d IS NULL THEN 99
                    WHEN l.estimated_occupancy_l365d = 0 THEN 0
                    WHEN l.estimated_occupancy_l365d <= 30 THEN 1
                    WHEN l.estimated_occupancy_l365d <= 60 THEN 2
                    WHEN l.estimated_occupancy_l365d <= 90 THEN 3
                    WHEN l.estimated_occupancy_l365d <= 120 THEN 4
                    WHEN l.estimated_occupancy_l365d <= 180 THEN 5
                    ELSE 6
                END AS bucket_order
            FROM public.listings AS l
            LEFT JOIN public.neighbourhoods AS n
              ON n.neighbourhood_name = l.neighbourhood_fk
            {where}
        )
        SELECT nights_bucket, COUNT(listing_id) AS listing_count,
               MIN(bucket_order) AS bucket_order
        FROM bucketed
        GROUP BY nights_bucket
        ORDER BY bucket_order
        """,
        params,
    )


def get_license_distribution(
    connection: Any,
    neighborhoods: Sequence[str] | None,
    room_types: Sequence[str] | None,
    activity_only: bool,
    snapshot_date: date | None,
):
    where, params = _filters(
        neighborhoods, room_types, activity_only, snapshot_date
    )
    return _query(
        connection,
        f"""
        SELECT
            CASE
                WHEN LOWER(BTRIM(l.license)) IN ('exempt', 'exempted')
                    THEN 'Marked exempt'
                WHEN l.license IS NULL OR BTRIM(l.license) = ''
                    THEN 'Blank'
                ELSE 'Value recorded'
            END AS license_record,
            COUNT(l.listing_id) AS listing_count
        FROM public.listings AS l
        LEFT JOIN public.neighbourhoods AS n
          ON n.neighbourhood_name = l.neighbourhood_fk
        {where}
        GROUP BY license_record
        ORDER BY license_record
        """,
        params,
    )


def get_minimum_nights_metrics(
    connection: Any,
    neighborhoods: Sequence[str] | None,
    room_types: Sequence[str] | None,
    activity_only: bool,
    snapshot_date: date | None,
    cutoff: int,
):
    where, params = _filters(
        neighborhoods, room_types, activity_only, snapshot_date
    )
    params["minimum_nights_cutoff"] = cutoff
    return _query(
        connection,
        f"""
        SELECT
            COUNT(l.listing_id) AS listing_count,
            COUNT(l.minimum_nights) AS listings_with_minimum_nights,
            COUNT(l.listing_id) FILTER (
                WHERE l.minimum_nights < :minimum_nights_cutoff
            ) AS below_cutoff
        FROM public.listings AS l
        LEFT JOIN public.neighbourhoods AS n
          ON n.neighbourhood_name = l.neighbourhood_fk
        {where}
        """,
        params,
    )


def get_minimum_nights_distribution(
    connection: Any,
    neighborhoods: Sequence[str] | None,
    room_types: Sequence[str] | None,
    activity_only: bool,
    snapshot_date: date | None,
):
    where, params = _filters(
        neighborhoods, room_types, activity_only, snapshot_date
    )
    return _query(
        connection,
        f"""
        WITH bucketed AS (
            SELECT
                l.listing_id,
                CASE
                    WHEN l.minimum_nights IS NULL THEN -1
                    WHEN l.minimum_nights >= 60 THEN 60
                    ELSE l.minimum_nights
                END AS minimum_nights_bucket
            FROM public.listings AS l
            LEFT JOIN public.neighbourhoods AS n
              ON n.neighbourhood_name = l.neighbourhood_fk
            {where}
        )
        SELECT minimum_nights_bucket, COUNT(listing_id) AS listing_count
        FROM bucketed
        GROUP BY minimum_nights_bucket
        ORDER BY minimum_nights_bucket
        """,
        params,
    )


def get_host_summary(connection: Any):
    return _query(
        connection,
        """
        WITH host_counts AS (
            SELECT l.host_id, COUNT(l.listing_id) AS listing_count
            FROM public.listings AS l
            WHERE l.host_id IS NOT NULL
            GROUP BY l.host_id
        )
        SELECT
            COUNT(host_id) AS host_count,
            COUNT(host_id) FILTER (WHERE listing_count = 1) AS single_listing_hosts,
            COUNT(host_id) FILTER (WHERE listing_count > 1) AS multi_listing_hosts
        FROM host_counts
        """,
    )


def get_top_hosts(connection: Any):
    return _query(
        connection,
        """
        WITH host_rollup AS (
            SELECT
                l.host_id,
                COUNT(l.listing_id) AS listing_count,
                COUNT(l.listing_id) FILTER (
                    WHERE l.room_type = 'Entire home/apt'
                ) AS entire_home_count,
                COUNT(l.listing_id) FILTER (
                    WHERE l.room_type = 'Private room'
                ) AS private_room_count,
                COUNT(l.listing_id) FILTER (
                    WHERE l.room_type = 'Shared room'
                ) AS shared_room_count,
                COUNT(l.listing_id) FILTER (
                    WHERE l.room_type = 'Hotel room'
                ) AS hotel_room_count
            FROM public.listings AS l
            WHERE l.host_id IS NOT NULL
            GROUP BY l.host_id
            ORDER BY COUNT(l.listing_id) DESC, l.host_id
            LIMIT 20
        )
        SELECT
            COALESCE(NULLIF(BTRIM(h.host_name), ''), r.host_id) AS host_name,
            r.host_id,
            r.listing_count,
            r.entire_home_count,
            r.private_room_count,
            r.shared_room_count,
            r.hotel_room_count
        FROM host_rollup AS r
        LEFT JOIN public.hosts AS h ON h.host_id = r.host_id
        ORDER BY r.listing_count DESC, r.host_id
        """,
    )
