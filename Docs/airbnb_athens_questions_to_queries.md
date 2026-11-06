# Athens Airbnb Data — Questions and PostgreSQL Queries

This guide shows example questions you can ask of the one-download database and queries for answering them. It uses the table and column names from the proposed schema in **airbnb_athens_erd.md**.

The examples assume the tables are named **listings**, **hosts**, **listing_calendar**, **reviews**, and **neighbourhoods**. Replace example dates with dates in the calendar file, which covers **2026-09-23 through 2027-09-24**.

## Listings and neighbourhoods

### 1. How many listings are there by neighbourhood and room type?

~~~sql
SELECT
    COALESCE(neighbourhood_cleansed, neighbourhood, '(unknown)') AS neighbourhood,
    room_type,
    COUNT(*) AS listing_count
FROM listings
GROUP BY 1, 2
ORDER BY listing_count DESC, neighbourhood, room_type;
~~~

### 2. What is the median listed price by neighbourhood and room type?

This groups by currency so amounts in different currencies are not mixed. It omits listings without a parsed numeric price.

~~~sql
SELECT
    COALESCE(neighbourhood_cleansed, neighbourhood, '(unknown)') AS neighbourhood,
    room_type,
    price_currency,
    percentile_cont(0.5) WITHIN GROUP (ORDER BY price_amount) AS median_price
FROM listings
WHERE price_amount IS NOT NULL
  AND price_currency IS NOT NULL
GROUP BY 1, 2, 3
ORDER BY neighbourhood, room_type, price_currency;
~~~

### 3. Which well-reviewed listings have the lowest listed prices?

Change the rating and review-count thresholds to suit the analysis. Price comparisons are only meaningful when the currency is consistent.

~~~sql
SELECT
    listing_id,
    name,
    COALESCE(neighbourhood_cleansed, neighbourhood) AS neighbourhood,
    room_type,
    accommodates,
    price_amount,
    price_currency,
    review_scores_rating,
    number_of_reviews
FROM listings
WHERE price_amount IS NOT NULL
  AND price_currency IS NOT NULL
  AND review_scores_rating >= 4.8
  AND number_of_reviews >= 20
ORDER BY price_currency, price_amount
LIMIT 25;
~~~

### 4. How does average price vary with guest capacity?

This groups listings by guest capacity. Keep currencies separate.

~~~sql
SELECT
    price_currency,
    accommodates,
    COUNT(*) AS listing_count,
    ROUND(AVG(price_amount), 2) AS average_price,
    percentile_cont(0.5) WITHIN GROUP (ORDER BY price_amount) AS median_price
FROM listings
WHERE price_amount IS NOT NULL
  AND price_currency IS NOT NULL
  AND accommodates IS NOT NULL
GROUP BY price_currency, accommodates
ORDER BY price_currency, accommodates;
~~~

### 5. Which amenities are most common?

This assumes **amenities** was imported as a JSONB array of strings.

~~~sql
SELECT
    amenity,
    COUNT(DISTINCT l.listing_id) AS listing_count
FROM listings AS l
CROSS JOIN LATERAL jsonb_array_elements_text(
    COALESCE(l.amenities, '[]'::jsonb)
) AS a(amenity)
GROUP BY amenity
ORDER BY listing_count DESC, amenity
LIMIT 30;
~~~

### 6. How many listings have a license recorded in each neighbourhood?

This measures whether a value is present in the dataset. It does not establish whether a listing complies with local rules.

~~~sql
SELECT
    COALESCE(neighbourhood_cleansed, neighbourhood, '(unknown)') AS neighbourhood,
    COUNT(*) AS listing_count,
    COUNT(*) FILTER (
        WHERE license IS NOT NULL AND btrim(license) <> ''
    ) AS listings_with_license,
    ROUND(
        100.0 * COUNT(*) FILTER (
            WHERE license IS NOT NULL AND btrim(license) <> ''
        ) / NULLIF(COUNT(*), 0),
        1
    ) AS percent_with_license
FROM listings
GROUP BY 1
ORDER BY listing_count DESC;
~~~

## Calendar availability

### 7. How many listings are available on a particular date?

Change the example date to any date in the calendar range.

~~~sql
SELECT
    COUNT(*) AS listings_with_calendar_entry,
    COUNT(*) FILTER (WHERE available) AS available_listings,
    ROUND(
        100.0 * COUNT(*) FILTER (WHERE available)
        / NULLIF(COUNT(*), 0),
        1
    ) AS percent_available
FROM listing_calendar
WHERE calendar_date = DATE '2026-12-15';
~~~

### 8. Which neighbourhoods have the most calendar availability in a month?

The result counts available listing-days, so a listing available for 20 days contributes 20.

~~~sql
SELECT
    COALESCE(l.neighbourhood_cleansed, l.neighbourhood, '(unknown)') AS neighbourhood,
    COUNT(*) AS listing_days_in_calendar,
    COUNT(*) FILTER (WHERE c.available) AS available_listing_days,
    ROUND(AVG(c.available::int) * 100, 1) AS percent_of_listing_days_available
FROM listing_calendar AS c
JOIN listings AS l USING (listing_id)
WHERE c.calendar_date >= DATE '2026-12-01'
  AND c.calendar_date <  DATE '2027-01-01'
GROUP BY 1
ORDER BY available_listing_days DESC;
~~~

### 9. Which listings appear available for every night of a five-night stay?

This checks the five nights from December 10 through 14; checkout is December 15. It also checks that the calendar has an entry for every night and that the listed minimum/maximum stay rules allow five nights.

~~~sql
SELECT
    l.listing_id,
    l.name,
    COALESCE(l.neighbourhood_cleansed, l.neighbourhood) AS neighbourhood,
    l.accommodates,
    l.price_amount,
    l.price_currency
FROM listing_calendar AS c
JOIN listings AS l USING (listing_id)
WHERE c.calendar_date >= DATE '2026-12-10'
  AND c.calendar_date <  DATE '2026-12-15'
GROUP BY
    l.listing_id, l.name, l.neighbourhood_cleansed, l.neighbourhood,
    l.accommodates, l.price_amount, l.price_currency
HAVING COUNT(*) = 5
   AND COUNT(*) FILTER (WHERE c.available IS TRUE) = 5
   AND COUNT(c.minimum_nights) = 5
   AND COUNT(c.maximum_nights) = 5
   AND MAX(c.minimum_nights) <= 5
   AND MIN(c.maximum_nights) >= 5
ORDER BY l.price_amount NULLS LAST
LIMIT 100;
~~~

Availability does not guarantee a booking can be completed: this dataset does not include a live booking check, fees, or a date-specific price quote for this exact stay.

## Reviews and ratings

### 10. How has review volume changed by month?

~~~sql
SELECT
    date_trunc('month', review_date)::date AS review_month,
    COUNT(*) AS review_count
FROM reviews
WHERE review_date IS NOT NULL
GROUP BY 1
ORDER BY 1;
~~~

### 11. Which neighbourhoods have the highest average listing ratings?

The minimum review threshold helps avoid ranking listings with very few reviews. This averages listing-level ratings, rather than individual review text.

~~~sql
SELECT
    COALESCE(neighbourhood_cleansed, neighbourhood, '(unknown)') AS neighbourhood,
    COUNT(*) AS qualifying_listings,
    ROUND(AVG(review_scores_rating), 2) AS average_listing_rating
FROM listings
WHERE review_scores_rating IS NOT NULL
  AND number_of_reviews >= 10
GROUP BY 1
ORDER BY average_listing_rating DESC, qualifying_listings DESC;
~~~

### 12. What are the average category scores by room type?

~~~sql
SELECT
    room_type,
    COUNT(review_scores_rating) AS listings_with_overall_rating,
    ROUND(AVG(review_scores_cleanliness), 2) AS cleanliness,
    ROUND(AVG(review_scores_checkin), 2) AS checkin,
    ROUND(AVG(review_scores_communication), 2) AS communication,
    ROUND(AVG(review_scores_location), 2) AS location,
    ROUND(AVG(review_scores_value), 2) AS value
FROM listings
GROUP BY room_type
ORDER BY listings_with_overall_rating DESC;
~~~

### 13. How often do review comments mention selected topics?

This simple example counts occurrences of selected terms. For serious text analysis, use a dedicated text-search or language-analysis workflow.

~~~sql
SELECT
    COUNT(*) FILTER (WHERE comments ILIKE '%clean%') AS reviews_mentioning_clean,
    COUNT(*) FILTER (WHERE comments ILIKE '%location%') AS reviews_mentioning_location,
    COUNT(*) FILTER (WHERE comments ILIKE '%host%') AS reviews_mentioning_host
FROM reviews
WHERE comments IS NOT NULL;
~~~

## Hosts and estimates

### 14. Which hosts have the most listings in this Athens dataset?

~~~sql
SELECT
    h.host_id,
    h.host_name,
    COUNT(l.listing_id) AS listings_in_dataset,
    h.host_is_superhost
FROM hosts AS h
JOIN listings AS l USING (host_id)
GROUP BY h.host_id, h.host_name, h.host_is_superhost
ORDER BY listings_in_dataset DESC
LIMIT 25;
~~~

### 15. How do listing ratings and prices compare for superhosts and other hosts?

The averages are across listings, not across hosts. Price is separated by currency.

~~~sql
SELECT
    h.host_is_superhost,
    l.price_currency,
    COUNT(*) AS listing_count,
    ROUND(AVG(l.review_scores_rating), 2) AS average_rating,
    ROUND(AVG(l.price_amount), 2) AS average_price
FROM listings AS l
JOIN hosts AS h USING (host_id)
WHERE l.price_amount IS NOT NULL
  AND l.price_currency IS NOT NULL
GROUP BY h.host_is_superhost, l.price_currency
ORDER BY h.host_is_superhost, l.price_currency;
~~~

### 16. Which listings have the highest estimated revenue?

These are source estimates for the last 365 days, not verified booking revenue.

~~~sql
SELECT
    listing_id,
    name,
    COALESCE(neighbourhood_cleansed, neighbourhood) AS neighbourhood,
    estimated_occupancy_l365d,
    estimated_revenue_l365d
FROM listings
WHERE estimated_revenue_l365d IS NOT NULL
ORDER BY estimated_revenue_l365d DESC
LIMIT 25;
~~~

### 17. What are the average estimated booked nights, nightly price, and annual income?

Use the supplied `estimated_occupancy_l365d` and `estimated_revenue_l365d` fields for the last 365 days. The nightly price column is the listing price captured in this download, not a historical price series. The query reports the simple average listing price and a revenue-weighted implied amount per estimated booked night.

~~~sql
WITH priced_estimates AS (
    SELECT
        estimated_occupancy_l365d::numeric AS estimated_booked_nights,
        price_amount,
        estimated_revenue_l365d
    FROM listings
    WHERE estimated_occupancy_l365d IS NOT NULL
      AND price_amount IS NOT NULL
      AND estimated_revenue_l365d IS NOT NULL
)
SELECT
    (SELECT COUNT(*)
     FROM listings
     WHERE estimated_occupancy_l365d IS NOT NULL
    ) AS listings_with_nights_estimate,
    (SELECT ROUND(AVG(estimated_occupancy_l365d), 2)
     FROM listings
     WHERE estimated_occupancy_l365d IS NOT NULL
    ) AS avg_estimated_nights_all_listings,
    (SELECT percentile_disc(0.5) WITHIN GROUP (
         ORDER BY estimated_occupancy_l365d
     )
     FROM listings
     WHERE estimated_occupancy_l365d IS NOT NULL
    ) AS median_estimated_nights_all_listings,
    COUNT(*) AS listings_with_price_and_income_estimates,
    ROUND(AVG(estimated_booked_nights), 2) AS avg_estimated_nights_complete_subset,
    ROUND(AVG(price_amount), 2) AS avg_current_listed_price_per_night,
    percentile_disc(0.5) WITHIN GROUP (
        ORDER BY price_amount
    ) AS median_current_listed_price_per_night,
    ROUND(AVG(estimated_revenue_l365d), 2) AS avg_estimated_income_last_365d,
    percentile_disc(0.5) WITHIN GROUP (
        ORDER BY estimated_revenue_l365d
    ) AS median_estimated_income_last_365d,
    ROUND(
        SUM(estimated_revenue_l365d)
        / NULLIF(SUM(estimated_booked_nights), 0),
        2
    ) AS weighted_estimated_income_per_booked_night
FROM priced_estimates;
~~~

Interpret `avg_estimated_income_last_365d` as the average among listings with both price and income estimates. In this download, 920 listings lack those values. The source uses an occupancy model based on reviews and assumptions about the review rate and length of stay; it is an estimate, not actual booking or payout data. The model uses a 50% review rate, a city-specific average stay when available (otherwise three nights), raises the assumed stay to the minimum-night rule when that is higher, and caps occupancy at 70% of the year. See [Inside Airbnb's data assumptions](https://insideairbnb.com/data-assumptions/).

## Geographic output

### 18. Which listings can I plot on a map?

This returns coordinates and a few fields for a mapping tool. The neighbourhood polygons remain in the raw Data/neighbourhoods.geojson file; this schema does not load them into PostgreSQL.

~~~sql
SELECT
    listing_id,
    name,
    latitude,
    longitude,
    room_type,
    price_amount,
    price_currency,
    neighbourhood_cleansed
FROM listings
WHERE latitude IS NOT NULL
  AND longitude IS NOT NULL;
~~~

## Interpretation notes

- Calendar availability is a downloaded snapshot, not booking history. A date marked unavailable may be booked, blocked, or otherwise unavailable.
- The calendar only covers the date range noted above.
- **price_amount** should be populated only after parsing **price_raw**; compare prices within the same currency.
- Ratings and review counts in **listings** are listing-level summary metrics. **reviews** contains individual review records.
- Estimated occupancy and revenue are source estimates, not observed transactions.
- A license value being present or absent is only a property of this dataset; it does not by itself establish legal status.
- Blank source values should be stored as SQL **NULL**.
