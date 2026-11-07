# Athens Airbnb Dashboard — Local V1

## Summary

Build a private, interactive Streamlit dashboard with Plotly charts, using the loaded `airbnb_athens` PostgreSQL database and the questions in [dashboard_questions.md](C:/Users/kanik/Downloads/AirbnbAthens/dashboard_questions.md). V1 covers the core questions only; sentiment analysis and questions from `additional_dashboard_questions.md` stay out of scope.

## Implementation

- Create `app.py` for the dashboard and `dashboard_queries.py` for parameterized PostgreSQL queries. Use a shared neighborhood and room-type filter across the map and relevant panels.
- Organize the page into Overview, Activity & Pricing, License, Short-term Rentals, and Hosts sections. Use an interactive listing map with the local neighborhood GeoJSON, plus the chart types described in the question file.
- Use the existing `listings` and `hosts` tables. Do not fetch the 5.5M-row calendar table. Add a one-time setup script for an `airbnb_dashboard_ro` login with `SELECT` access only to required columns. PostgreSQL supports separate roles and column-level `SELECT` grants. [CREATE ROLE](https://www.postgresql.org/docs/18/sql-createrole.html) · [GRANT](https://www.postgresql.org/docs/18/sql-grant.html)
- Connect through Streamlit’s SQL connection, with credentials in a user-local secrets file outside the repo. Cache query results for five minutes. Streamlit’s SQL connection uses SQLAlchemy; Plotly figures render through `st.plotly_chart`, and `st.cache_data` is intended for caching query results. [SQL connections](https://docs.streamlit.io/develop/concepts/connections/connecting-to-data) · [Plotly charts](https://docs.streamlit.io/develop/api-reference/charts/st.plotly_chart) · [Caching](https://docs.streamlit.io/develop/concepts/architecture/caching)
- Start locally with `streamlit run app.py --server.address 127.0.0.1`. There will be no public API or public hosting in V1.

## Definitions and Data Handling

- Anchor the “recent” review window to the latest listing scrape date in the database—currently 25 September 2026—not the machine’s current date. Define “frequently booked” as at least 60 estimated nights in the last 365 days.
- Show license data as **value recorded / explicitly marked exempt / blank**. Count exemption only when the raw field contains an explicit marker; the loaded Athens snapshot has 160. This does not verify legal exemption or compliance.
- Make the minimum-night threshold adjustable, defaulting to **fewer than 28 nights**. Show counts and percentages below the threshold and at or above it, excluding missing minimum-night values from the percentage denominator. Label this as an analytic cutoff, not a legal definition.
- Keep the top-host breakdown to the **20 hosts with the most listings citywide**; show listing counts by room type. Keep any single-versus-multiple-host summary marketwide.
- Display missing-data counts alongside prices and estimated revenue; null values must not be treated as zero. Label estimated occupancy/revenue and approximate listing locations.

## Acceptance Checks

- The app starts locally and shows the latest database scrape date.
- Neighborhood and room-type filters update the relevant map and charts; the activity filter applies both the six-month review and 60-night criteria.
- Room-type counts and percentages use the same filtered listing total.
- Boundary cases behave as specified: minimum stay 27 vs. 28 nights and estimated nights 59 vs. 60.
- License labels remain limited to recorded, explicit exempt markers, and blank values; the top-host breakdown contains exactly the top 20 citywide hosts.
- The app handles null price, revenue, and rating values, and the database account has no write access. Verify these manually during implementation; no test suite is planned for V1.

## Assumptions and Defaults

- V1 uses the core question file only. The sentiment tables are empty, while `instant_bookable` and host response/acceptance fields have no populated values, so those views are excluded.
- The database remains a single loaded snapshot; refreshing data means reloading the database, not historical trend tracking.
- Runtime dependencies are declared in `requirements.txt`; the local Windows environment is managed with `uv`.
