# Athens Airbnb Data - Proposed PostgreSQL ERD v2: Review Analysis

This design is for the single download in this directory. It stores one row per listing and host, one row per listing/date in the calendar, one row per review, and one row per neighbourhood. There are no batch or snapshot tables.

## Entity relationship diagram

This version lists every typed column declared in the DDL. Raw source rows and neighbourhood geometry are not duplicated in the database.

```mermaid
erDiagram
    HOSTS ||--o{ LISTINGS : hosts
    LISTINGS ||--o{ LISTING_CALENDAR : has_dates
    LISTINGS ||--o{ REVIEWS : receives
    NEIGHBOURHOODS o|--o{ LISTINGS : contains
    REVIEWS ||--o| REVIEW_ANALYSIS : analyzed_as
    REVIEW_ANALYSIS ||--o{ REVIEW_TOPICS : identifies
    REVIEW_TOPIC_CATALOG ||--o{ REVIEW_TOPICS : defines

    NEIGHBOURHOODS {
        text neighbourhood_name PK
        text neighbourhood_group
    }

    HOSTS {
        text host_id PK
        text host_profile_id
        text host_name
        text host_url
        text host_profile_url
        date host_since
        numeric hosts_time_as_user_years
        numeric hosts_time_as_user_months
        numeric hosts_time_as_host_years
        numeric hosts_time_as_host_months
        text host_location
        text host_about
        text host_response_time
        numeric host_response_rate
        numeric host_acceptance_rate
        boolean host_is_superhost
        text host_thumbnail_url
        text host_picture_url
        text host_neighbourhood
        integer host_listings_count
        integer host_total_listings_count
        jsonb host_verifications
        boolean host_has_profile_pic
        boolean host_identity_verified
    }

    LISTINGS {
        text listing_id PK
        text host_id FK
        text listing_url
        text scrape_id
        date last_scraped
        text source
        text name
        text description
        text neighborhood_overview
        text picture_url
        text neighbourhood
        text neighbourhood_cleansed
        text neighbourhood_group
        text neighbourhood_group_cleansed
        text neighbourhood_fk FK
        numeric latitude
        numeric longitude
        text property_type
        text room_type
        smallint accommodates
        numeric bathrooms
        text bathrooms_text
        smallint bedrooms
        numeric beds
        jsonb amenities
        text price_raw
        numeric price_amount
        text price_currency
        date price_quote_checkin_date
        date price_quote_checkout_date
        numeric price_quote_total_price
        numeric price_quote_price_per_night
        text price_quote_raw
        integer minimum_nights
        integer maximum_nights
        integer minimum_minimum_nights
        integer maximum_minimum_nights
        integer minimum_maximum_nights
        integer maximum_maximum_nights
        numeric minimum_nights_avg_ntm
        numeric(7,2) maximum_nights_avg_ntm
        text calendar_updated
        boolean has_availability
        smallint availability_30
        smallint availability_60
        smallint availability_90
        smallint availability_365
        date calendar_last_scraped
        smallint availability_eoy
        integer number_of_reviews
        integer number_of_reviews_ltm
        integer number_of_reviews_l30d
        integer number_of_reviews_ly
        numeric estimated_occupancy_l365d
        numeric estimated_revenue_l365d
        date first_review
        date last_review
        numeric review_scores_rating
        numeric review_scores_accuracy
        numeric review_scores_cleanliness
        numeric review_scores_checkin
        numeric review_scores_communication
        numeric review_scores_location
        numeric review_scores_value
        text license
        boolean instant_bookable
        integer calculated_host_listings_count
        integer calculated_host_listings_count_entire_homes
        integer calculated_host_listings_count_private_rooms
        integer calculated_host_listings_count_shared_rooms
        numeric reviews_per_month
    }

    LISTING_CALENDAR {
        text listing_id PK, FK
        date calendar_date PK
        boolean available
        integer minimum_nights
        integer maximum_nights
    }

    REVIEWS {
        text review_id PK
        text listing_id FK
        date review_date
        text reviewer_id
        text reviewer_name
        text comments
    }

    REVIEW_TOPIC_CATALOG {
        text topic_code PK
        text display_name
        text definition
    }

    REVIEW_ANALYSIS {
        text review_id PK, FK
        text language_code
        text overall_sentiment
        numeric overall_confidence
        numeric sentiment_score
        text model_name
        text model_version
        text taxonomy_version
        text status
        timestamptz analyzed_at
        text error_message
    }

    REVIEW_TOPICS {
        text review_id PK, FK
        text topic_code PK, FK
        text sentiment
        numeric confidence
    }
```

The neighbourhood relationship is optional: a listing may have no matched neighbourhood name. `neighbourhood_cleansed` is the likely join field; retain the original neighbourhood text as well. The CSV and GeoJSON neighbourhood names match in this download.

## Table responsibilities

| Table | One row per | Key and relationship |
|---|---|---|
| hosts | Airbnb host | host_id primary key. One host can have many listings. |
| listings | Airbnb listing | listing_id primary key; host_id references hosts. Stores typed listing attributes. |
| listing_calendar | Listing and calendar date | Composite primary key (listing_id, calendar_date); listing_id references listings. |
| reviews | Individual review | review_id primary key; listing_id references listings. |
| neighbourhoods | Neighbourhood name | neighbourhood_name primary key; provides the name lookup for listings. Polygon geometry remains in the source GeoJSON file. |
| review_topic_catalog | Topic definition | topic_code primary key; defines the fixed topic labels used by the analysis. |
| review_analysis | Current analysis of one review | review_id primary key and foreign key to reviews; stores one current sentiment result and its model metadata. |
| review_topics | One topic result for one review | Composite primary key (review_id, topic_code); links to review_analysis and review_topic_catalog. |
## Suggested PostgreSQL DDL

IDs are stored as text because Airbnb IDs are identifiers rather than quantities. The relational tables contain the fields used for analysis; original CSV and GeoJSON files remain in the Data folder rather than being duplicated in JSONB.

```sql
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
```

Neighbourhood boundaries are not loaded into PostgreSQL in this design. The source GeoJSON remains in the Data folder; listing latitude and longitude are still available for ordinary map plotting.

## Import and validation notes

- Load listings.csv.gz into listings and hosts. Use listings.csv for validation or enrichment; do not create duplicate listing rows.
- Load calendar.csv.gz into listing_calendar. Its key is (listing_id, calendar_date).
- Load reviews.csv.gz into reviews. reviews.csv is a reduced projection and should not be loaded as duplicate reviews.
- Load neighbourhood names and groups from neighbourhoods.csv into neighbourhoods. Keep neighbourhoods.geojson as a raw source file; this schema does not store polygon geometry.
- Populate listings.neighbourhood_fk only when the cleansed name matches the neighbourhood lookup; keep the source neighbourhood text in its typed columns.
- Convert CSV t/f values to booleans and blanks to NULL. Parse amenities and host_verifications as JSONB arrays.
- Keep price_raw and populate price_amount and price_currency only after confirming parsing and currency.
- The typed tables do not duplicate the source rows as JSONB. The original files remain in Data if raw values need to be checked.

## Useful indexes

```sql
CREATE INDEX listings_neighbourhood_idx
    ON listings (neighbourhood_cleansed);

CREATE INDEX listing_calendar_date_availability_idx
    ON listing_calendar (calendar_date, available);

CREATE INDEX reviews_listing_date_idx
    ON reviews (listing_id, review_date);
```



## Review topic and sentiment analysis

These tables store one current analysis per review. They do not retain earlier model runs; rerunning the analysis replaces the current result for each review. The original review comment remains in reviews.

A review can mention multiple topics. This design stores one consolidated sentiment per topic per review; use mixed when a review expresses both positive and negative opinions about the same topic.

### Suggested PostgreSQL DDL

~~~sql
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

CREATE INDEX review_topics_by_topic_idx
    ON review_topics (topic_code, sentiment);

CREATE INDEX review_analysis_by_language_idx
    ON review_analysis (language_code);
~~~

A starter taxonomy could include cleanliness, location, check_in, communication, value, accuracy, amenities, noise, comfort, and transport. Give each topic a clear definition in review_topic_catalog.

### Example analysis question

How many reviews express negative sentiment about cleanliness in each neighbourhood?

~~~sql
SELECT
    COALESCE(l.neighbourhood_cleansed, l.neighbourhood, '(unknown)') AS neighbourhood,
    COUNT(DISTINCT rt.review_id) AS negative_cleanliness_reviews
FROM review_topics AS rt
JOIN reviews AS r USING (review_id)
JOIN listings AS l USING (listing_id)
WHERE rt.topic_code = 'cleanliness'
  AND rt.sentiment = 'negative'
GROUP BY 1
ORDER BY negative_cleanliness_reviews DESC;
~~~

### Population outline

1. Load the detailed review file into reviews first.
2. Insert the selected topic definitions into review_topic_catalog.
3. Analyze non-empty comments in batches, using review_id and comment text. Do not send reviewer names or IDs to the classifier.
4. Insert one result per review into review_analysis and one row per identified topic into review_topics. Save model name/version, taxonomy version, and status with the review result.
5. Manually inspect a sample across languages and sentiment classes before relying on aggregated results.
6. If the analysis is run again, update the current result rows; this design does not preserve prior outputs.

Use a multilingual classifier for the Athens review corpus. The model and topic definitions are choices for this analysis, not fields supplied by the Airbnb CSV files.
