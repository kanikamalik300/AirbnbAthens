-- Athens Airbnb PostgreSQL schema
-- Run this file while connected to the PostgreSQL database where these tables should live.
-- This creates tables and indexes; it does not create the database or load the CSV data.
-- Designed for the single download: no import snapshots, raw-row JSONB copies, or spatial extension.

BEGIN;

CREATE TABLE neighbourhoods (
    neighbourhood_name  text PRIMARY KEY,
    neighbourhood_group text
);

CREATE TABLE hosts (
    host_id                     text PRIMARY KEY,
    host_profile_id             text,
    host_name                   text,
    host_url                    text,
    host_profile_url            text,
    host_since                  date,
    hosts_time_as_user_years    numeric(5,2),
    hosts_time_as_user_months   numeric(6,2),
    hosts_time_as_host_years    numeric(5,2),
    hosts_time_as_host_months   numeric(6,2),
    host_location               text,
    host_about                  text,
    host_response_time          text,
    host_response_rate          numeric(5,2),
    host_acceptance_rate        numeric(5,2),
    host_is_superhost            boolean,
    host_thumbnail_url          text,
    host_picture_url            text,
    host_neighbourhood          text,
    host_listings_count         integer,
    host_total_listings_count   integer,
    host_verifications          jsonb,
    host_has_profile_pic        boolean,
    host_identity_verified      boolean
);

CREATE TABLE listings (
    listing_id                   text PRIMARY KEY,
    host_id                      text REFERENCES hosts(host_id),
    listing_url                  text,
    scrape_id                    text,
    last_scraped                 date,
    source                       text,
    name                         text,
    description                  text,
    neighborhood_overview        text,
    picture_url                  text,

    -- Keep each source neighbourhood field distinct. Populate the FK only
    -- when the cleansed source name matches the neighbourhood lookup.
    neighbourhood                text,
    neighbourhood_cleansed       text,
    neighbourhood_group          text,
    neighbourhood_group_cleansed text,
    neighbourhood_fk             text REFERENCES neighbourhoods(neighbourhood_name),
    latitude                     numeric(9,6),
    longitude                    numeric(9,6),

    property_type                text,
    room_type                    text,
    accommodates                 smallint,
    bathrooms                    numeric(4,1),
    bathrooms_text               text,
    bedrooms                     smallint,
    beds                         numeric(5,1),
    amenities                    jsonb,

    -- Preserve raw price text; only fill numeric/currency fields after parsing.
    price_raw                    text,
    price_amount                 numeric(12,2),
    price_currency               text,
    price_quote_checkin_date     date,
    price_quote_checkout_date    date,
    price_quote_total_price      numeric(12,2),
    price_quote_price_per_night  numeric(12,2),
    price_quote_raw              text,

    minimum_nights               integer,
    maximum_nights               integer,
    minimum_minimum_nights       integer,
    maximum_minimum_nights       integer,
    minimum_maximum_nights       integer,
    maximum_maximum_nights       integer,
    minimum_nights_avg_ntm       numeric(6,2),
    maximum_nights_avg_ntm       numeric(7,2),
    calendar_updated             text,
    has_availability             boolean,
    availability_30              smallint,
    availability_60              smallint,
    availability_90              smallint,
    availability_365             smallint,
    calendar_last_scraped        date,
    availability_eoy             smallint,

    number_of_reviews            integer,
    number_of_reviews_ltm        integer,
    number_of_reviews_l30d       integer,
    number_of_reviews_ly         integer,
    estimated_occupancy_l365d    numeric(7,2),
    estimated_revenue_l365d      numeric(12,2),
    first_review                 date,
    last_review                  date,
    review_scores_rating         numeric(3,2),
    review_scores_accuracy       numeric(3,2),
    review_scores_cleanliness    numeric(3,2),
    review_scores_checkin        numeric(3,2),
    review_scores_communication  numeric(3,2),
    review_scores_location       numeric(3,2),
    review_scores_value          numeric(3,2),

    license                      text,
    instant_bookable             boolean,
    calculated_host_listings_count integer,
    calculated_host_listings_count_entire_homes integer,
    calculated_host_listings_count_private_rooms integer,
    calculated_host_listings_count_shared_rooms integer,
    reviews_per_month            numeric(7,2)

);

CREATE TABLE listing_calendar (
    listing_id      text NOT NULL REFERENCES listings(listing_id),
    calendar_date   date NOT NULL,
    available       boolean,
    minimum_nights  integer,
    maximum_nights  integer,
    PRIMARY KEY (listing_id, calendar_date)
);

CREATE TABLE reviews (
    review_id       text PRIMARY KEY,
    listing_id      text NOT NULL REFERENCES listings(listing_id),
    review_date     date,
    reviewer_id     text,
    reviewer_name   text,
    comments        text
);

CREATE TABLE review_topic_catalog (
    topic_code   text PRIMARY KEY,
    display_name text NOT NULL UNIQUE,
    definition   text NOT NULL
);

CREATE TABLE review_analysis (
    review_id          text PRIMARY KEY REFERENCES reviews(review_id),
    language_code      text,
    overall_sentiment  text
        CHECK (overall_sentiment IN ('positive', 'neutral', 'negative', 'mixed')),
    overall_confidence numeric(5,4)
        CHECK (overall_confidence BETWEEN 0 AND 1),
    sentiment_score    numeric(6,5)
        CHECK (sentiment_score BETWEEN -1 AND 1),
    model_name         text NOT NULL,
    model_version      text NOT NULL,
    taxonomy_version   text NOT NULL,
    status             text NOT NULL DEFAULT 'complete'
        CHECK (status IN ('complete', 'skipped_empty', 'needs_review', 'failed')),
    analyzed_at        timestamptz NOT NULL DEFAULT now(),
    error_message      text
);

CREATE TABLE review_topics (
    review_id   text NOT NULL REFERENCES review_analysis(review_id),
    topic_code  text NOT NULL REFERENCES review_topic_catalog(topic_code),
    sentiment   text NOT NULL
        CHECK (sentiment IN ('positive', 'neutral', 'negative', 'mixed')),
    confidence  numeric(5,4)
        CHECK (confidence BETWEEN 0 AND 1),
    PRIMARY KEY (review_id, topic_code)
);

CREATE INDEX listings_neighbourhood_idx
    ON listings (neighbourhood_cleansed);

CREATE INDEX listing_calendar_date_availability_idx
    ON listing_calendar (calendar_date, available);

CREATE INDEX reviews_listing_date_idx
    ON reviews (listing_id, review_date);

CREATE INDEX review_topics_by_topic_idx
    ON review_topics (topic_code, sentiment);

CREATE INDEX review_analysis_by_language_idx
    ON review_analysis (language_code);

COMMIT;
