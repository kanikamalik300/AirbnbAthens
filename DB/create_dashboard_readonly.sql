-- Run while connected to airbnb_athens as a PostgreSQL administrator.
-- The dashboard role receives column-level SELECT access only.

BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_roles WHERE rolname = 'airbnb_dashboard_ro'
    ) THEN
        CREATE ROLE airbnb_dashboard_ro
            LOGIN
            NOSUPERUSER
            NOCREATEDB
            NOCREATEROLE
            NOREPLICATION
            NOBYPASSRLS
            NOINHERIT;
    END IF;
END
$$;

GRANT CONNECT ON DATABASE airbnb_athens TO airbnb_dashboard_ro;
GRANT USAGE ON SCHEMA public TO airbnb_dashboard_ro;

GRANT SELECT (
    listing_id,
    host_id,
    name,
    neighbourhood,
    neighbourhood_cleansed,
    neighbourhood_fk,
    latitude,
    longitude,
    room_type,
    price_amount,
    minimum_nights,
    availability_365,
    number_of_reviews_ltm,
    estimated_occupancy_l365d,
    estimated_revenue_l365d,
    last_review,
    license,
    last_scraped
) ON TABLE public.listings TO airbnb_dashboard_ro;

GRANT SELECT (host_id, host_name)
    ON TABLE public.hosts TO airbnb_dashboard_ro;

GRANT SELECT (neighbourhood_name)
    ON TABLE public.neighbourhoods TO airbnb_dashboard_ro;

COMMIT;
