"""Local, read-only Streamlit dashboard for the Athens Airbnb snapshot."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from dashboard_queries import (
    get_activity_metrics,
    get_availability_distribution,
    get_availability_metrics,
    get_host_summary,
    get_license_distribution,
    get_map_listings,
    get_metadata,
    get_minimum_nights_distribution,
    get_minimum_nights_metrics,
    get_neighborhood_options,
    get_occupancy_distribution,
    get_overview_counts,
    get_room_type_counts,
    get_room_type_options,
    get_top_hosts,
)


ROOT = Path(__file__).resolve().parent
GEOJSON_PATH = ROOT / "Data" / "neighbourhoods.geojson"
MAP_CENTER = {"lat": 37.9708, "lon": 23.7383}

st.set_page_config(
    page_title="Athens Airbnb Dashboard",
    page_icon="🏠",
    layout="wide",
)


def _first_row(frame: pd.DataFrame) -> dict:
    if frame is None or frame.empty:
        return {}
    return frame.iloc[0].to_dict()


def _int_value(value, default: int = 0) -> int:
    if value is None or pd.isna(value):
        return default
    return int(value)


def _float_value(value, default: float = 0.0) -> float:
    if value is None or pd.isna(value):
        return default
    return float(value)


@st.cache_data(ttl=3600, show_spinner=False)
def _read_geojson(path: str) -> dict:
    with open(path, "r", encoding="utf-8-sig") as source:
        return json.load(source)


def _add_neighborhood_outlines(fig: go.Figure, geojson: dict) -> go.Figure:
    for feature in geojson.get("features", []):
        geometry = feature.get("geometry") or {}
        geometry_type = geometry.get("type")
        coordinates = geometry.get("coordinates") or []
        polygons = [coordinates] if geometry_type == "Polygon" else coordinates
        if geometry_type not in {"Polygon", "MultiPolygon"}:
            continue

        for polygon in polygons:
            if not polygon:
                continue
            ring = polygon[0]
            if len(ring) < 2:
                continue
            fig.add_trace(
                go.Scattermap(
                    lon=[point[0] for point in ring],
                    lat=[point[1] for point in ring],
                    mode="lines",
                    line={"color": "#64748b", "width": 1},
                    hoverinfo="skip",
                    showlegend=False,
                )
            )
    return fig


def _map_figure(listings: pd.DataFrame, geojson: dict) -> go.Figure | None:
    data = listings.dropna(subset=["latitude", "longitude"]).copy()
    if data.empty:
        return None

    data["price_label"] = data["nightly_price_eur"].map(
        lambda value: "Not available" if pd.isna(value) else f"€{value:,.0f}"
    )
    fig = px.scatter_map(
        data,
        lat="latitude",
        lon="longitude",
        color="room_type",
        hover_name="name",
        hover_data={
            "neighborhood": True,
            "room_type": True,
            "price_label": True,
            "minimum_nights": True,
            "reviews_last_12_months": True,
            "estimated_booked_nights": True,
            "estimated_revenue_year": True,
            "available_days_next_365": True,
            "latitude": False,
            "longitude": False,
        },
        map_style="carto-positron",
        center=MAP_CENTER,
        zoom=11,
        height=650,
        labels={
            "price_label": "Nightly price",
            "minimum_nights": "Minimum stay",
            "reviews_last_12_months": "Reviews in last 12 months",
            "estimated_booked_nights": "Estimated booked nights",
            "estimated_revenue_year": "Estimated revenue (last 365 days)",
            "available_days_next_365": "Available days (next 365)",
        },
    )
    fig.update_traces(marker={"size": 7, "opacity": 0.68})
    _add_neighborhood_outlines(fig, geojson)
    fig.update_layout(
        margin={"l": 0, "r": 0, "t": 8, "b": 0},
        legend_title_text="Room type",
    )
    return fig


def _show_empty(frame: pd.DataFrame, message: str) -> bool:
    if frame is None or frame.empty:
        st.info(message)
        return True
    return False


def _format_integer(value) -> str:
    if value is None or pd.isna(value):
        return "—"
    return f"{int(value):,}"


def _format_euro(value) -> str:
    if value is None or pd.isna(value):
        return "—"
    return f"€{float(value):,.0f}"


st.title("Athens Airbnb Dashboard")
st.caption(
    "Explore the loaded Inside Airbnb snapshot. Occupancy and revenue are estimates; "
    "listing locations are approximate."
)

try:
    connection = st.connection("airbnb_db", type="sql")
    metadata = _first_row(get_metadata(connection))
    if not metadata or metadata.get("listing_count") is None:
        st.error("The airbnb_athens database did not return listing data.")
        st.stop()
except Exception:
    st.error("Could not connect to the local airbnb_athens database.")
    st.info(
        "Configure the airbnb_db connection in your user-local Streamlit secrets "
        "file, then start the app again. See README.md for setup steps."
    )
    st.stop()

snapshot_date = metadata.get("latest_listing_scrape")
first_scrape_date = metadata.get("first_listing_scrape")
if snapshot_date is None or pd.isna(snapshot_date):
    snapshot_date = None
    st.warning(
        "The database has no listing scrape date; recent-activity filtering is unavailable."
    )

try:
    neighborhoods = (
        get_neighborhood_options(connection)["neighborhood"].dropna().tolist()
    )
    room_type_options = (
        get_room_type_options(connection)["room_type"].dropna().tolist()
    )
except Exception:
    st.error("Could not load the dashboard filter options from PostgreSQL.")
    st.stop()

with st.sidebar:
    st.header("Filters")
    selected_neighborhoods = st.multiselect(
        "Neighborhoods",
        options=neighborhoods,
        default=[],
        help="Leave empty to include every neighborhood.",
    )
    selected_room_types = st.multiselect(
        "Room types",
        options=room_type_options,
        default=[],
        help="Leave empty to include every room type.",
    )
    activity_only = st.checkbox(
        "Only recent and frequently booked",
        value=False,
        help=(
            "Requires a review within six months of the latest listing scrape "
            "and at least 60 estimated booked nights in the last 365 days."
        ),
    )
    minimum_nights_cutoff = st.slider(
        "Minimum-night cutoff",
        min_value=1,
        max_value=60,
        value=28,
        help="Highlights listings with a minimum stay below this analytic cutoff.",
    )
    high_availability_cutoff = st.slider(
        "High-availability cutoff (days)",
        min_value=0,
        max_value=365,
        value=180,
        help="Highlights listings available for at least this many days.",
    )
    st.caption("Both cutoffs are exploratory settings, not legal definitions.")

common_args = (
    connection,
    selected_neighborhoods,
    selected_room_types,
    activity_only,
    snapshot_date,
)

try:
    overview = _first_row(get_overview_counts(*common_args))
    room_counts = get_room_type_counts(*common_args)
    activity_metrics = _first_row(get_activity_metrics(*common_args))
    occupancy_distribution = get_occupancy_distribution(*common_args)
    license_distribution = get_license_distribution(*common_args)
    minimum_nights_metrics = _first_row(
        get_minimum_nights_metrics(*common_args, cutoff=minimum_nights_cutoff)
    )
    minimum_nights_distribution = get_minimum_nights_distribution(*common_args)
    map_listings = get_map_listings(*common_args)
    availability_metrics = _first_row(
        get_availability_metrics(*common_args, cutoff=high_availability_cutoff)
    )
    availability_distribution = get_availability_distribution(*common_args)
    host_summary = _first_row(get_host_summary(connection))
    top_hosts = get_top_hosts(connection)
except Exception:
    st.error("A dashboard query failed. Check the database connection and read-only grants.")
    st.stop()

scrape_range = (
    f"{first_scrape_date:%d %b %Y} – {snapshot_date:%d %b %Y}"
    if first_scrape_date is not None and snapshot_date is not None
    else "date unavailable"
)
st.caption(
    f"Database: airbnb_athens · listing scrape dates: {scrape_range} · "
    f"{_format_integer(metadata.get('listing_count'))} listings"
)

tabs = st.tabs(
    ["Overview", "Activity & Pricing", "License & Minimum Nights", "Hosts", "Availability"]
)

with tabs[0]:
    total_listings = _int_value(overview.get("listing_count"))
    entire_homes = _int_value(overview.get("entire_home_count"))
    license_recorded = _int_value(overview.get("license_value_recorded"))
    st.subheader("Listings and neighborhood distribution")
    metric_cols = st.columns(3)
    metric_cols[0].metric("Listings in selection", f"{total_listings:,}")
    metric_cols[1].metric("Entire homes/apartments", f"{entire_homes:,}")
    metric_cols[2].metric("License values recorded", f"{license_recorded:,}")

    chart_col, map_col = st.columns([1, 2], gap="large")
    with chart_col:
        st.markdown("#### Listing mix by room type")
        if not _show_empty(room_counts, "No listings match the selected filters."):
            room_fig = px.bar(
                room_counts,
                x="listing_count",
                y="room_type",
                color="room_type",
                orientation="h",
                labels={"listing_count": "Listings", "room_type": "Room type"},
                text="listing_count",
            )
            room_fig.update_layout(
                showlegend=False,
                yaxis={"categoryorder": "total ascending"},
                margin={"l": 4, "r": 4, "t": 8, "b": 4},
            )
            st.plotly_chart(
                room_fig,
                width="stretch",
                config={"displayModeBar": False},
                alt="Horizontal bar chart of listings by room type",
            )
    with map_col:
        st.markdown("#### Approximate listing locations")
        if map_listings.empty:
            st.info("No listings match the selected filters.")
        else:
            try:
                neighborhood_geojson = _read_geojson(str(GEOJSON_PATH))
                map_fig = _map_figure(map_listings, neighborhood_geojson)
                if map_fig is None:
                    st.info("No listings with coordinates match the selected filters.")
                else:
                    st.plotly_chart(
                        map_fig,
                        width="stretch",
                        config={"scrollZoom": False},
                        alt="Map of approximate listing locations in Athens",
                    )
            except Exception:
                st.warning("The neighborhood boundary file could not be displayed.")

with tabs[1]:
    st.subheader("Booking activity, prices, and estimated income")
    activity_row = activity_metrics
    average_nights = activity_row.get("average_estimated_nights")
    average_occupancy = (
        _float_value(average_nights) / 365 * 100
        if average_nights is not None and not pd.isna(average_nights)
        else None
    )
    activity_listing_count = _int_value(activity_row.get("listing_count"))
    price_count = _int_value(activity_row.get("listings_with_price"))
    revenue_count = _int_value(activity_row.get("listings_with_revenue"))
    activity_cols = st.columns(5)
    activity_cols[0].metric(
        "Recent & frequent listings" if activity_only else "Listings in selection",
        f"{activity_listing_count:,}",
    )
    activity_cols[1].metric(
        "Average estimated nights booked",
        _format_integer(average_nights),
    )
    activity_cols[2].metric(
        "Average estimated occupancy",
        "—" if average_occupancy is None else f"{average_occupancy:.1f}%",
    )
    activity_cols[3].metric(
        "Average nightly price",
        _format_euro(activity_row.get("average_nightly_price_eur")),
        help=(
            f"Available for {price_count:,} listings; missing for "
            f"{max(0, activity_listing_count - price_count):,}."
        ),
    )
    activity_cols[4].metric(
        "Average estimated revenue / year",
        _format_euro(activity_row.get("average_estimated_revenue_eur")),
        help=(
            f"Available for {revenue_count:,} listings; missing for "
            f"{max(0, activity_listing_count - revenue_count):,}."
        ),
    )
    st.caption(
        "Revenue averages use rows with an estimate; missing values are excluded, not treated as zero."
    )
    if not _show_empty(
        occupancy_distribution,
        "No activity estimates match the selected filters.",
    ):
        occupancy_fig = px.bar(
            occupancy_distribution,
            x="nights_bucket",
            y="listing_count",
            category_orders={
                "nights_bucket": [
                    "0",
                    "1-30",
                    "31-60",
                    "61-90",
                    "91-120",
                    "121-180",
                    "181+",
                    "Unknown",
                ]
            },
            labels={
                "nights_bucket": "Estimated booked nights in last 365 days",
                "listing_count": "Listings",
            },
            text="listing_count",
        )
        occupancy_fig.update_layout(
            margin={"l": 4, "r": 4, "t": 8, "b": 4},
            xaxis_title="Estimated booked nights in last 365 days",
        )
        st.plotly_chart(
            occupancy_fig,
            width="stretch",
            config={"displayModeBar": False},
            alt="Bar chart showing listings by estimated booked-night range",
        )

with tabs[2]:
    st.subheader("Recorded license values and minimum stays")
    license_row = (
        license_distribution.set_index("license_record")["listing_count"].to_dict()
        if not license_distribution.empty
        else {}
    )
    recorded_count = _int_value(license_row.get("Value recorded"))
    missing_count = _int_value(license_row.get("No value recorded"))
    below_cutoff = _int_value(minimum_nights_metrics.get("below_cutoff"))
    policy_cols = st.columns(3)
    policy_cols[0].metric("License value recorded", f"{recorded_count:,}")
    policy_cols[1].metric("No license value recorded", f"{missing_count:,}")
    policy_cols[2].metric(
        f"Minimum stay below {minimum_nights_cutoff} nights",
        f"{below_cutoff:,}",
    )
    st.caption(
        "A recorded value does not verify a license or establish legal status. "
        "The minimum-night cutoff is an analytic setting."
    )

    license_col, nights_col = st.columns(2, gap="large")
    with license_col:
        st.markdown("#### License field coverage")
        if not license_distribution.empty:
            license_fig = px.pie(
                license_distribution,
                names="license_record",
                values="listing_count",
                hole=0.52,
                color="license_record",
                color_discrete_map={
                    "Value recorded": "#2d806d",
                    "No value recorded": "#d49a4d",
                },
            )
            license_fig.update_layout(margin={"l": 4, "r": 4, "t": 8, "b": 4})
            st.plotly_chart(
                license_fig,
                width="stretch",
                config={"displayModeBar": False},
                alt="Donut chart of listings with and without a recorded license value",
            )
    with nights_col:
        st.markdown("#### Listings by minimum nights")
        if not _show_empty(
            minimum_nights_distribution,
            "No minimum-night data matches the selected filters.",
        ):
            nights_data = minimum_nights_distribution.copy()
            nights_data["bucket_label"] = nights_data[
                "minimum_nights_bucket"
            ].map(
                lambda value: (
                    "Unknown"
                    if value < 0
                    else "60+"
                    if value >= 60
                    else str(int(value))
                )
            )
            nights_data["cutoff_group"] = nights_data[
                "minimum_nights_bucket"
            ].map(
                lambda value: (
                    "Unknown"
                    if value < 0
                    else "Below cutoff"
                    if value < minimum_nights_cutoff
                    else "At or above cutoff"
                )
            )
            nights_fig = px.bar(
                nights_data,
                x="minimum_nights_bucket",
                y="listing_count",
                color="cutoff_group",
                custom_data=["bucket_label"],
                labels={
                    "minimum_nights_bucket": "Minimum nights",
                    "listing_count": "Listings",
                    "cutoff_group": "Analytic cutoff",
                },
                color_discrete_map={
                    "Below cutoff": "#2d806d",
                    "At or above cutoff": "#52647b",
                    "Unknown": "#a0a0a0",
                },
            )
            nights_fig.update_traces(
                hovertemplate="%{customdata[0]} nights<br>%{y:,} listings<extra></extra>"
            )
            nights_fig.add_vline(
                x=minimum_nights_cutoff,
                line_dash="dash",
                line_color="#b45309",
                annotation_text="cutoff",
            )
            nights_fig.update_layout(
                margin={"l": 4, "r": 4, "t": 22, "b": 4},
                xaxis={"tickmode": "linear", "dtick": 5},
            )
            st.plotly_chart(
                nights_fig,
                width="stretch",
                config={"displayModeBar": False},
                alt="Bar chart of listing counts by minimum nights",
            )

with tabs[3]:
    st.subheader("Host portfolio")
    host_row = host_summary
    host_cols = st.columns(3)
    host_cols[0].metric("Hosts in dataset", _format_integer(host_row.get("host_count")))
    host_cols[1].metric(
        "Single-listing hosts",
        _format_integer(host_row.get("single_listing_hosts")),
    )
    host_cols[2].metric(
        "Multi-listing hosts",
        _format_integer(host_row.get("multi_listing_hosts")),
    )
    st.caption(
        "The marketwide host counts and the top-20 ranking are citywide and do not change with sidebar filters."
    )
    if not _show_empty(top_hosts, "No host records are available."):
        host_chart = top_hosts.copy()
        host_chart["host_label"] = host_chart.apply(
            lambda row: f"{row['host_name']} · {str(row['host_id'])[-5:]}",
            axis=1,
        )
        sorted_hosts = host_chart.sort_values("listing_count", ascending=True)
        host_fig = px.bar(
            sorted_hosts,
            x="listing_count",
            y="host_label",
            orientation="h",
            labels={"listing_count": "Listings", "host_label": "Host"},
            text="listing_count",
        )
        host_fig.update_layout(
            yaxis={"categoryorder": "array", "categoryarray": sorted_hosts["host_label"].tolist()},
            margin={"l": 4, "r": 4, "t": 8, "b": 4},
        )
        st.plotly_chart(
            host_fig,
            width="stretch",
            config={"displayModeBar": False},
            alt="Horizontal bar chart of the 20 hosts with the most Athens listings",
        )
        st.markdown("#### Listing mix for the top 20 hosts")
        display_hosts = top_hosts.rename(
            columns={
                "host_name": "Host",
                "listing_count": "Listings",
                "entire_home_count": "Entire homes",
                "private_room_count": "Private rooms",
                "shared_room_count": "Shared rooms",
                "hotel_room_count": "Hotel rooms",
            }
        )[
            [
                "Host",
                "Listings",
                "Entire homes",
                "Private rooms",
                "Shared rooms",
                "Hotel rooms",
            ]
        ]
        st.dataframe(display_hosts, hide_index=True, width="stretch")

with tabs[4]:
    st.subheader("Availability")
    availability_row = availability_metrics
    available_count = _int_value(availability_row.get("listings_with_availability"))
    high_count = _int_value(availability_row.get("high_availability_count"))
    high_share = 100 * high_count / available_count if available_count else 0
    availability_cols = st.columns(3)
    availability_cols[0].metric(
        "Listings with availability data",
        f"{available_count:,}",
    )
    availability_cols[1].metric(
        f"Available at least {high_availability_cutoff} days",
        f"{high_count:,}",
    )
    availability_cols[2].metric("Share of listings with data", f"{high_share:.1f}%")
    st.caption(
        "Availability comes from the listing snapshot’s availability_365 field; it is not booking history."
    )
    availability_data = availability_distribution.dropna(subset=["available_days"])
    if not _show_empty(
        availability_data,
        "No availability data matches the selected filters.",
    ):
        availability_fig = px.bar(
            availability_data,
            x="available_days",
            y="listing_count",
            labels={
                "available_days": "Available days in next 365",
                "listing_count": "Listings",
            },
        )
        availability_fig.add_vline(
            x=high_availability_cutoff,
            line_dash="dash",
            line_color="#b45309",
            annotation_text="high-availability cutoff",
        )
        availability_fig.update_layout(
            margin={"l": 4, "r": 4, "t": 22, "b": 4},
            xaxis={"tickmode": "linear", "dtick": 30, "range": [0, 365]},
        )
        st.plotly_chart(
            availability_fig,
            width="stretch",
            config={"displayModeBar": False},
            alt="Bar chart showing listings by available days in the next 365",
        )

st.divider()
st.caption(
    "Inside Airbnb source data: occupancy and revenue are estimates; locations are approximate. "
    "This local dashboard does not establish legal license status."
)
