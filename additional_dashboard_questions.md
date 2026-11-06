# Additional Questions for the Athens Dashboard

These questions extend the current dashboard topics using fields and tables in the project database. Check field completeness in the loaded data before building each view.

## Guest experience

**Question:** Which neighborhoods and room types have the lowest cleanliness, check-in, communication, location, or value scores?

**Suggested visual:** Heatmap by neighborhood and score category, with room type as a filter. A minimum review-count threshold can reduce noise from listings with very few reviews.

**Data:** Listing-level review score fields in `listings`.

## Calendar availability patterns

**Question:** How does calendar availability vary by month, neighborhood, and room type?

**Suggested visual:** Calendar heatmap or time series, with filters for neighborhood and room type.

**Data:** Date-level rows in `listing_calendar`, joined to `listings`.

**Interpretation:** Calendar availability is a snapshot. An unavailable date may be booked, blocked, or otherwise unavailable; it is not a measure of actual bookings.

## Price and listing size

**Question:** How does the median nightly price vary by guest capacity, bedroom count, room type, and neighborhood?

**Suggested visual:** Box plots by capacity or room type, with neighborhood filters.

**Data:** `price_amount`, `price_currency`, `accommodates`, `bedrooms`, and listing/neighborhood fields.

**Interpretation:** Keep currencies separate. Median and distribution are more informative than a single average when prices are skewed.

## Amenities

**Questions:** Which amenities are most common? How do listings with different amenities compare on price or ratings?

**Suggested visual:** Ranked horizontal bar chart for amenity prevalence, followed by price or rating comparisons for selected amenities.

**Data:** The `amenities` JSONB field, nightly price, and listing-level rating fields.

**Interpretation:** These comparisons show associations; they do not prove an amenity causes a price or rating difference.

## Booking ease and host service

**Questions:** What share of listings are instant-bookable? How do response rate, acceptance rate, or Superhost status relate to listing ratings?

**Suggested visual:** Stacked bars for instant-bookable share by room type or neighborhood; grouped bars or box plots for rating comparisons by host-service measures.

**Data:** `instant_bookable` on listings; host response rate, acceptance rate, and Superhost status in `hosts`; listing ratings in `listings`.

**Interpretation:** Treat rating differences as associations, not evidence that a host attribute caused the rating.

## Review topics and sentiment — conditional

**Questions:** Which topics receive the most negative guest feedback? Do negative topic sentiments vary by neighborhood or room type?

**Suggested visual:** Heatmap of topic sentiment by neighborhood or room type, with review counts shown for context.

**Data:** `review_analysis`, `review_topics`, and `review_topic_catalog`, joined to `reviews` and `listings`.

**Prerequisite:** The schema defines these analysis tables, but the current source loader loads raw reviews without populating the sentiment/topic tables. This view depends on those analysis results being generated and loaded.

## Data boundaries to keep in view

- The database stores a raw license value. It can answer which listings have a value recorded, but that alone does not establish legal compliance or exemption status.
- The project has a single listing snapshot, so it cannot show historical changes in total listing supply.
- Occupancy and revenue fields are estimates; calendar availability is not booking history.
