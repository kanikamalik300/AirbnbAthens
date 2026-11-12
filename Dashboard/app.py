"""Streamlit dashboard backed by a packaged, read-only Athens snapshot."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from dashboard_queries import (
    get_activity_metrics,
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
    get_top_neighborhood,
)


APP_DIR = Path(__file__).resolve().parent
SNAPSHOT_PATH = APP_DIR / "athens_snapshot.sqlite"
GEOJSON_PATH = APP_DIR / "neighbourhoods.geojson"
MAP_CENTER = {"lat": 37.9708, "lon": 23.7383}
PLOT_COLORS = {
    "ink": "#26352F",
    "teal": "#1F665B",
    "terracotta": "#B96F52",
    "ochre": "#B89B63",
    "slate": "#667B89",
    "sage": "#91A194",
    "line": "#E5DFD4",
}
ROOM_TYPE_COLORS = {
    "Entire home/apt": PLOT_COLORS["teal"],
    "Private room": PLOT_COLORS["terracotta"],
    "Shared room": PLOT_COLORS["ochre"],
    "Hotel room": PLOT_COLORS["slate"],
    "Unknown": PLOT_COLORS["sage"],
}

st.set_page_config(
    page_title="Athens Airbnb market",
    page_icon=":material/apartment:",
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


def _date_value(value):
    if value is None or pd.isna(value):
        return None
    parsed = pd.to_datetime(value, errors="coerce")
    return None if pd.isna(parsed) else parsed.date()


def _style_figure(fig: go.Figure) -> go.Figure:
    fig.update_layout(
        font={"family": "Arial, sans-serif", "color": PLOT_COLORS["ink"], "size": 13},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        colorway=[
            PLOT_COLORS["teal"],
            PLOT_COLORS["terracotta"],
            PLOT_COLORS["ochre"],
            PLOT_COLORS["slate"],
            PLOT_COLORS["sage"],
        ],
        hoverlabel={
            "bgcolor": "#FCFAF5",
            "bordercolor": PLOT_COLORS["line"],
            "font": {"color": PLOT_COLORS["ink"]},
        },
        legend={"bgcolor": "rgba(0,0,0,0)", "font": {"color": PLOT_COLORS["ink"]}},
    )
    fig.update_xaxes(
        zeroline=False,
        linecolor=PLOT_COLORS["line"],
        gridcolor=PLOT_COLORS["line"],
        tickcolor=PLOT_COLORS["line"],
    )
    fig.update_yaxes(
        zeroline=False,
        linecolor=PLOT_COLORS["line"],
        gridcolor=PLOT_COLORS["line"],
        tickcolor=PLOT_COLORS["line"],
    )
    return fig


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
                    line={"color": PLOT_COLORS["slate"], "width": 1},
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
        color_discrete_map=ROOM_TYPE_COLORS,
        hover_name="name",
        hover_data={
            "neighborhood": True,
            "room_type": True,
            "price_label": True,
            "minimum_nights": True,
            "reviews_last_12_months": True,
            "estimated_booked_nights": True,
            "estimated_revenue_year": True,
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
        },
    )
    fig.update_traces(marker={"size": 7, "opacity": 0.68})
    _add_neighborhood_outlines(fig, geojson)
    fig.update_layout(
        margin={"l": 0, "r": 0, "t": 8, "b": 0},
        legend_title_text="Room type",
    )
    return _style_figure(fig)


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


st.caption("ATHENS  ·  INSIDE AIRBNB SNAPSHOT")
st.title("Athens Airbnb market", icon=":material/apartment:")
st.markdown(
    "A neighborhood view of listing supply, booking activity, prices, and host portfolios."
)

try:
    if not SNAPSHOT_PATH.is_file():
        raise FileNotFoundError("The packaged snapshot file is missing.")
    connection = SNAPSHOT_PATH
    metadata = _first_row(get_metadata(connection))
    if not metadata or metadata.get("listing_count") is None:
        st.error("The packaged Athens snapshot did not return listing data.")
        st.stop()
except Exception:
    st.error("Could not open the packaged Athens data snapshot.")
    st.info(
        "The snapshot file is missing or unreadable. See README.md for instructions "
        "to rebuild it from the local database."
    )
    st.stop()

snapshot_date = _date_value(metadata.get("latest_listing_scrape"))
first_scrape_date = _date_value(metadata.get("first_listing_scrape"))
if snapshot_date is None:
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
    st.error("Could not load the dashboard filter options from the snapshot.")
    st.stop()

with st.sidebar:
    st.header("Explore the market", icon=":material/tune:")
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
        "Short-term rental threshold (minimum nights)",
        min_value=1,
        max_value=60,
        value=28,
        help=(
            "Listings below this threshold meet the dashboard's short-term "
            "category. This is an analytic cutoff, not a legal definition."
        ),
    )
    st.caption("The short-term rental threshold is an analytic setting, not a legal definition.")

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
    top_neighborhood = _first_row(get_top_neighborhood(*common_args))
    activity_metrics = _first_row(get_activity_metrics(*common_args))
    occupancy_distribution = get_occupancy_distribution(*common_args)
    license_distribution = get_license_distribution(*common_args)
    minimum_nights_metrics = _first_row(
        get_minimum_nights_metrics(*common_args, cutoff=minimum_nights_cutoff)
    )
    minimum_nights_distribution = get_minimum_nights_distribution(*common_args)
    map_listings = get_map_listings(*common_args)
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
with st.container(border=True):
    metadata_cols = st.columns([1, 1.5, 1], gap="large")
    metadata_cols[0].caption("DATA SOURCE")
    metadata_cols[0].markdown("**Inside Airbnb · Athens**")
    metadata_cols[1].caption("LISTING SCRAPE PERIOD")
    metadata_cols[1].markdown(f"**{scrape_range}**")
    metadata_cols[2].caption("LISTINGS IN DATABASE")
    metadata_cols[2].markdown(f"**{_format_integer(metadata.get('listing_count'))}**")

tabs = st.tabs(
    ["Overview", "Activity & Pricing", "License", "Short-term Rentals", "Hosts"]
)

with tabs[0]:
    total_listings = _int_value(overview.get("listing_count"))
    entire_homes = _int_value(overview.get("entire_home_count"))
    license_recorded = _int_value(overview.get("license_value_recorded"))
    st.subheader("Listings and neighborhood distribution")
    with st.grid("auto", min_column_width=200, gap="small"):
        st.metric("Listings in selection", f"{total_listings:,}", border=True)
        st.metric("Entire homes/apartments", f"{entire_homes:,}", border=True)
        st.metric("License values recorded", f"{license_recorded:,}", border=True)
    if total_listings and top_neighborhood:
        entire_home_share = 100 * entire_homes / total_listings
        top_neighborhood_count = _int_value(top_neighborhood.get("listing_count"))
        top_neighborhood_share = 100 * top_neighborhood_count / total_listings
        st.markdown(
            "**Key insight:** Entire homes/apartments make up "
            f"{entire_home_share:.1f}% of this selection. "
            f"{top_neighborhood.get('neighborhood')} has the most listings, "
            f"with {top_neighborhood_count:,} ({top_neighborhood_share:.1f}%)."
        )

    chart_col, map_col = st.columns([1, 2], gap="large")
    with chart_col:
        st.markdown("#### Listing mix by room type")
        if not _show_empty(room_counts, "No listings match the selected filters."):
            room_mix = room_counts.copy()
            room_mix["room_type"] = room_mix["room_type"].fillna("Unknown")
            room_mix_total = int(room_mix["listing_count"].sum())
            room_mix["share_percent"] = (
                room_mix["listing_count"] / room_mix_total * 100
                if room_mix_total
                else 0
            )
            room_mix["count_and_share"] = room_mix.apply(
                lambda row: (
                    f"{int(row['listing_count']):,} "
                    f"({row['share_percent']:.1f}%)"
                ),
                axis=1,
            )
            room_fig = px.bar(
                room_mix,
                x="listing_count",
                y="room_type",
                color="room_type",
                color_discrete_map=ROOM_TYPE_COLORS,
                orientation="h",
                labels={
                    "listing_count": "Listings",
                    "room_type": "Room type",
                    "share_percent": "Share of selected listings (%)",
                },
                hover_data={"share_percent": ":.1f"},
                text="count_and_share",
            )
            max_count = int(room_mix["listing_count"].max())
            room_fig.update_traces(textposition="outside", cliponaxis=False)
            room_fig.update_layout(
                showlegend=False,
                yaxis={"categoryorder": "total ascending"},
                xaxis={"range": [0, max_count * 2]},
                margin={"l": 4, "r": 48, "t": 8, "b": 4},
            )
            _style_figure(room_fig)
            st.plotly_chart(
                room_fig,
                width="stretch",
                config={"displayModeBar": False},
                alt="Listings by room type, with counts and shares of the filtered selection",
            )
            st.caption("Counts and percentages reflect the current sidebar filters.")
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
    if occupancy_distribution.empty:
        known_occupancy_count = 0
        zero_occupancy_count = 0
    else:
        known_occupancy = occupancy_distribution.loc[
            occupancy_distribution["nights_bucket"] != "Unknown", "listing_count"
        ]
        known_occupancy_count = int(known_occupancy.sum())
        zero_occupancy_count = int(
            occupancy_distribution.loc[
                occupancy_distribution["nights_bucket"] == "0", "listing_count"
            ].sum()
        )
    zero_occupancy_share = (
        100 * zero_occupancy_count / known_occupancy_count
        if known_occupancy_count
        else 0
    )
    with st.grid("auto", min_column_width=190, gap="small"):
        st.metric(
            "Recent & frequent listings" if activity_only else "Listings in selection",
            f"{activity_listing_count:,}",
            border=True,
        )
        st.metric(
            "Average estimated nights booked",
            _format_integer(average_nights),
            border=True,
        )
        st.metric(
            "Average estimated occupancy",
            "—" if average_occupancy is None else f"{average_occupancy:.1f}%",
            border=True,
        )
        st.metric(
            "Average nightly price",
            _format_euro(activity_row.get("average_nightly_price_eur")),
            border=True,
            help=(
                f"Available for {price_count:,} listings; missing for "
                f"{max(0, activity_listing_count - price_count):,}."
            ),
        )
        st.metric(
            "Average estimated revenue / year",
            _format_euro(activity_row.get("average_estimated_revenue_eur")),
            border=True,
            help=(
                f"Available for {revenue_count:,} listings; missing for "
                f"{max(0, activity_listing_count - revenue_count):,}."
            ),
        )
    st.caption(
        "Revenue averages use rows with an estimate; missing values are excluded, not treated as zero."
    )
    if average_nights is not None and known_occupancy_count:
        occupancy_insight = (
            f"Listings average {float(average_nights):.1f} estimated booked nights per year "
            f"({average_occupancy:.1f}% occupancy); {zero_occupancy_count:,} of "
            f"{known_occupancy_count:,} with estimates ({zero_occupancy_share:.1f}%) are at zero."
        )
    else:
        occupancy_insight = "Occupancy estimates are unavailable for this selection."
    st.markdown(
        f"**Key insight:** {occupancy_insight} Average nightly price is "
        f"{_format_euro(activity_row.get('average_nightly_price_eur'))} across "
        f"{price_count:,} priced listings; estimated annual revenue averages "
        f"{_format_euro(activity_row.get('average_estimated_revenue_eur'))} "
        f"across {revenue_count:,} listings."
    )
    if not _show_empty(
        occupancy_distribution,
        "No activity estimates match the selected filters.",
    ):
        occupancy_mix = occupancy_distribution.copy()
        occupancy_total = int(occupancy_mix["listing_count"].sum())
        occupancy_mix["share_percent"] = (
            occupancy_mix["listing_count"] / occupancy_total * 100
            if occupancy_total
            else 0
        )
        occupancy_mix["count_and_share"] = occupancy_mix.apply(
            lambda row: (
                f"{int(row['listing_count']):,} "
                f"({row['share_percent']:.1f}%)"
            ),
            axis=1,
        )
        occupancy_fig = px.bar(
            occupancy_mix,
            x="nights_bucket",
            y="listing_count",
            color_discrete_sequence=[PLOT_COLORS["teal"]],
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
                "share_percent": "Share of selected listings (%)",
            },
            hover_data={"share_percent": ":.1f"},
            text="count_and_share",
        )
        max_occupancy_count = int(occupancy_mix["listing_count"].max())
        occupancy_fig.update_traces(textposition="outside", cliponaxis=False)
        occupancy_fig.update_layout(
            margin={"l": 4, "r": 4, "t": 32, "b": 4},
            xaxis_title="Estimated booked nights in last 365 days",
            yaxis={"range": [0, max_occupancy_count * 1.2]},
        )
        _style_figure(occupancy_fig)
        st.plotly_chart(
            occupancy_fig,
            width="stretch",
            config={"displayModeBar": False},
            alt="Listings by estimated booked-night range, with counts and percentages",
        )
        st.caption(
            "Percentages use all listings in the selected data, including listings without an occupancy estimate."
        )

with tabs[2]:
    st.subheader("License field values")
    license_row = (
        license_distribution.set_index("license_record")["listing_count"].to_dict()
        if not license_distribution.empty
        else {}
    )
    recorded_count = _int_value(license_row.get("Value recorded"))
    exempt_count = _int_value(license_row.get("Marked exempt"))
    blank_count = _int_value(license_row.get("Blank"))
    with st.grid("auto", min_column_width=200, gap="small"):
        st.metric("License value recorded", f"{recorded_count:,}", border=True)
        st.metric("Explicitly marked exempt", f"{exempt_count:,}", border=True)
        st.metric("Blank license field", f"{blank_count:,}", border=True)
    license_total = recorded_count + exempt_count + blank_count
    if license_total:
        st.markdown(
            "**Key insight:** "
            f"{recorded_count:,} listings ({100 * recorded_count / license_total:.1f}%) "
            f"have a non-exempt value recorded; {blank_count:,} "
            f"({100 * blank_count / license_total:.1f}%) are blank and {exempt_count:,} "
            f"({100 * exempt_count / license_total:.1f}%) are marked exempt."
        )
    st.caption(
        "“Marked exempt” counts only an explicit exempt marker in the raw field. "
        "A recorded value or marker does not verify legal status."
    )

    if not license_distribution.empty:
        license_fig = px.pie(
            license_distribution,
            names="license_record",
            values="listing_count",
            hole=0.52,
            color="license_record",
            color_discrete_map={
                "Value recorded": PLOT_COLORS["teal"],
                "Marked exempt": PLOT_COLORS["slate"],
                "Blank": PLOT_COLORS["ochre"],
            },
        )
        license_fig.update_layout(margin={"l": 4, "r": 4, "t": 8, "b": 4})
        _style_figure(license_fig)
        st.plotly_chart(
            license_fig,
            width="stretch",
            config={"displayModeBar": False},
            alt="Donut chart of license values recorded, explicitly marked exempt, or blank",
        )

with tabs[3]:
    st.subheader("Short-term rentals by minimum stay")
    minimum_total = _int_value(minimum_nights_metrics.get("listing_count"))
    minimum_valid = _int_value(
        minimum_nights_metrics.get("listings_with_minimum_nights")
    )
    below_cutoff = _int_value(minimum_nights_metrics.get("below_cutoff"))
    at_or_above_cutoff = max(0, minimum_valid - below_cutoff)
    missing_minimum = max(0, minimum_total - minimum_valid)
    below_share = 100 * below_cutoff / minimum_valid if minimum_valid else 0
    at_or_above_share = (
        100 * at_or_above_cutoff / minimum_valid if minimum_valid else 0
    )

    with st.grid("auto", min_column_width=210, gap="small"):
        st.metric(
            "Short-term rental",
            f"{below_share:.1f}%",
            delta=f"{below_cutoff:,} listings",
            delta_color="off",
            delta_arrow="off",
            border=True,
        )
        st.metric(
            "Long-term rental",
            f"{at_or_above_share:.1f}%",
            delta=f"{at_or_above_cutoff:,} listings",
            delta_color="off",
            delta_arrow="off",
            border=True,
        )
        st.metric("Missing minimum-night value", f"{missing_minimum:,}", border=True)
    if minimum_valid:
        minimum_nights_insight = (
            f"{below_cutoff:,} of {minimum_valid:,} listings with minimum-night data "
            f"({below_share:.1f}%) are below the {minimum_nights_cutoff}-night cutoff; "
            f"{at_or_above_cutoff:,} ({at_or_above_share:.1f}%) are at or above it, "
            f"and {missing_minimum:,} listings have no value."
        )
    else:
        minimum_nights_insight = (
            f"No listings in this selection have a minimum-night value; "
            f"all {missing_minimum:,} are missing one."
        )
    st.markdown(f"**Key insight:** {minimum_nights_insight}")
    st.caption(
        f"Percentages use the {minimum_valid:,} listings with a minimum-night value. "
        "This is an analytic threshold, not a legal classification or proof of actual stay length."
    )

    if not _show_empty(
        minimum_nights_distribution,
        "No minimum-night data matches the selected filters.",
    ):
        nights_data = minimum_nights_distribution.copy()
        nights_data["bucket_label"] = nights_data["minimum_nights_bucket"].map(
            lambda value: (
                "Unknown"
                if value < 0
                else "60+"
                if value >= 60
                else str(int(value))
            )
        )
        nights_data["cutoff_group"] = nights_data["minimum_nights_bucket"].map(
            lambda value: (
                "Unknown"
                if value < 0
                else "Under threshold"
                if value < minimum_nights_cutoff
                else "At or above threshold"
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
                "cutoff_group": "Threshold category",
            },
            color_discrete_map={
                "Under threshold": PLOT_COLORS["teal"],
                "At or above threshold": PLOT_COLORS["slate"],
                "Unknown": PLOT_COLORS["sage"],
            },
        )
        nights_fig.update_traces(
            hovertemplate="%{customdata[0]} nights<br>%{y:,} listings<extra></extra>"
        )
        nights_fig.add_vline(
            x=minimum_nights_cutoff,
            line_dash="dash",
            line_color=PLOT_COLORS["terracotta"],
            annotation_text="threshold",
        )
        nights_fig.update_layout(
            margin={"l": 4, "r": 4, "t": 22, "b": 4},
            xaxis={"tickmode": "linear", "dtick": 5},
        )
        _style_figure(nights_fig)
        st.plotly_chart(
            nights_fig,
            width="stretch",
            config={"displayModeBar": False},
            alt="Bar chart of listings by minimum nights and analytic threshold category",
        )

with tabs[4]:
    st.subheader("Host portfolio")
    host_row = host_summary
    with st.grid("auto", min_column_width=200, gap="small"):
        st.metric(
            "Hosts in dataset",
            _format_integer(host_row.get("host_count")),
            border=True,
        )
        st.metric(
            "Single-listing hosts",
            _format_integer(host_row.get("single_listing_hosts")),
            border=True,
        )
        st.metric(
            "Multi-listing hosts",
            _format_integer(host_row.get("multi_listing_hosts")),
            border=True,
        )
    st.caption(
        "Single- and multi-listing host totals cover the full dataset. The table covers the 20 hosts with the most listings."
    )
    if not _show_empty(top_hosts, "No host records are available."):
        host_count = _int_value(host_row.get("host_count"))
        single_listing_hosts = _int_value(host_row.get("single_listing_hosts"))
        single_host_share = (
            100 * single_listing_hosts / host_count if host_count else 0
        )
        top_20_listing_count = int(top_hosts["listing_count"].sum())
        citywide_listing_count = _int_value(metadata.get("listing_count"))
        top_20_listing_share = (
            100 * top_20_listing_count / citywide_listing_count
            if citywide_listing_count
            else 0
        )
        largest_host = top_hosts.iloc[0]
        st.markdown(
            f"**Key insight:** {single_listing_hosts:,} of {host_count:,} hosts "
            f"({single_host_share:.1f}%) have one listing. The top 20 hosts account "
            f"for {top_20_listing_count:,} listings ({top_20_listing_share:.1f}% of "
            f"citywide supply), led by {largest_host['host_name']} "
            f"with {int(largest_host['listing_count']):,}."
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
        st.dataframe(
            display_hosts,
            hide_index=True,
            width="stretch",
            alt="Top 20 Athens hosts and their listings by room type",
        )

st.caption(
    "Inside Airbnb source data: occupancy and revenue are estimates; locations are approximate. "
    "This local dashboard does not establish legal license status."
)
