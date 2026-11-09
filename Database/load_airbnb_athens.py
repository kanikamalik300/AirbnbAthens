#!/usr/bin/env python3
"""Idempotently load the Athens Inside Airbnb download into PostgreSQL.

Requires Python 3's standard library, psql on PATH, and a libpq password file
entry for airbnb_athens. Each batch is a separate transaction; rerunning after
an interruption safely upserts the same source primary keys.
"""

from __future__ import annotations

import ast
import csv
import gzip
import json
import re
import subprocess
import sys
import tempfile
from collections import Counter
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Iterable, Iterator


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATA = ROOT / "Data"
PSQL = "psql"
HOST = "127.0.0.1"
DATABASE = "airbnb_athens"
DB_USER = "postgres"
CHUNK_SIZE = 50_000

# (database column, source column, PostgreSQL input type)
HOST_FIELDS = [
    ("host_id", "host_id", "text"),
    ("host_profile_id", "host_profile_id", "text"),
    ("host_name", "host_name", "text"),
    ("host_url", "host_url", "text"),
    ("host_profile_url", "host_profile_url", "text"),
    ("host_since", "host_since", "date"),
    ("hosts_time_as_user_years", "hosts_time_as_user_years", "numeric"),
    ("hosts_time_as_user_months", "hosts_time_as_user_months", "numeric"),
    ("hosts_time_as_host_years", "hosts_time_as_host_years", "numeric"),
    ("hosts_time_as_host_months", "hosts_time_as_host_months", "numeric"),
    ("host_location", "host_location", "text"),
    ("host_about", "host_about", "text"),
    ("host_response_time", "host_response_time", "text"),
    ("host_response_rate", "host_response_rate", "numeric"),
    ("host_acceptance_rate", "host_acceptance_rate", "numeric"),
    ("host_is_superhost", "host_is_superhost", "boolean"),
    ("host_thumbnail_url", "host_thumbnail_url", "text"),
    ("host_picture_url", "host_picture_url", "text"),
    ("host_neighbourhood", "host_neighbourhood", "text"),
    ("host_listings_count", "host_listings_count", "integer"),
    ("host_total_listings_count", "host_total_listings_count", "integer"),
    ("host_verifications", "host_verifications", "jsonb"),
    ("host_has_profile_pic", "host_has_profile_pic", "boolean"),
    ("host_identity_verified", "host_identity_verified", "boolean"),
]

LISTING_FIELDS = [
    ("listing_id", "id", "text"),
    ("host_id", "host_id", "text"),
    ("listing_url", "listing_url", "text"),
    ("scrape_id", "scrape_id", "text"),
    ("last_scraped", "last_scraped", "date"),
    ("source", "source", "text"),
    ("name", "name", "text"),
    ("description", "description", "text"),
    ("neighborhood_overview", "neighborhood_overview", "text"),
    ("picture_url", "picture_url", "text"),
    ("neighbourhood", "neighbourhood", "text"),
    ("neighbourhood_cleansed", "neighbourhood_cleansed", "text"),
    ("neighbourhood_group_cleansed", "neighbourhood_group_cleansed", "text"),
    ("latitude", "latitude", "numeric"),
    ("longitude", "longitude", "numeric"),
    ("property_type", "property_type", "text"),
    ("room_type", "room_type", "text"),
    ("accommodates", "accommodates", "smallint"),
    ("bathrooms", "bathrooms", "numeric"),
    ("bathrooms_text", "bathrooms_text", "text"),
    ("bedrooms", "bedrooms", "smallint"),
    ("beds", "beds", "numeric"),
    ("amenities", "amenities", "jsonb"),
    ("price_raw", "price", "text"),
    ("price_amount", "__price_amount", "numeric"),
    ("price_currency", "__price_currency", "text"),
    ("price_quote_checkin_date", "price_quote_checkin_date", "date"),
    ("price_quote_checkout_date", "price_quote_checkout_date", "date"),
    ("price_quote_total_price", "price_quote_total_price", "numeric"),
    ("price_quote_price_per_night", "price_quote_price_per_night", "numeric"),
    ("price_quote_raw", "price_quote_raw", "text"),
    ("minimum_nights", "minimum_nights", "integer"),
    ("maximum_nights", "maximum_nights", "integer"),
    ("minimum_minimum_nights", "minimum_minimum_nights", "integer"),
    ("maximum_minimum_nights", "maximum_minimum_nights", "integer"),
    ("minimum_maximum_nights", "minimum_maximum_nights", "integer"),
    ("maximum_maximum_nights", "maximum_maximum_nights", "integer"),
    ("minimum_nights_avg_ntm", "minimum_nights_avg_ntm", "numeric"),
    ("maximum_nights_avg_ntm", "maximum_nights_avg_ntm", "numeric"),
    ("calendar_updated", "calendar_updated", "text"),
    ("has_availability", "has_availability", "boolean"),
    ("availability_30", "availability_30", "smallint"),
    ("availability_60", "availability_60", "smallint"),
    ("availability_90", "availability_90", "smallint"),
    ("availability_365", "availability_365", "smallint"),
    ("calendar_last_scraped", "calendar_last_scraped", "date"),
    ("availability_eoy", "availability_eoy", "smallint"),
    ("number_of_reviews", "number_of_reviews", "integer"),
    ("number_of_reviews_ltm", "number_of_reviews_ltm", "integer"),
    ("number_of_reviews_l30d", "number_of_reviews_l30d", "integer"),
    ("number_of_reviews_ly", "number_of_reviews_ly", "integer"),
    ("estimated_occupancy_l365d", "estimated_occupancy_l365d", "numeric"),
    ("estimated_revenue_l365d", "estimated_revenue_l365d", "numeric"),
    ("first_review", "first_review", "date"),
    ("last_review", "last_review", "date"),
    ("review_scores_rating", "review_scores_rating", "numeric"),
    ("review_scores_accuracy", "review_scores_accuracy", "numeric"),
    ("review_scores_cleanliness", "review_scores_cleanliness", "numeric"),
    ("review_scores_checkin", "review_scores_checkin", "numeric"),
    ("review_scores_communication", "review_scores_communication", "numeric"),
    ("review_scores_location", "review_scores_location", "numeric"),
    ("review_scores_value", "review_scores_value", "numeric"),
    ("license", "license", "text"),
    ("instant_bookable", "instant_bookable", "boolean"),
    ("calculated_host_listings_count", "calculated_host_listings_count", "integer"),
    ("calculated_host_listings_count_entire_homes", "calculated_host_listings_count_entire_homes", "integer"),
    ("calculated_host_listings_count_private_rooms", "calculated_host_listings_count_private_rooms", "integer"),
    ("calculated_host_listings_count_shared_rooms", "calculated_host_listings_count_shared_rooms", "integer"),
    ("reviews_per_month", "reviews_per_month", "numeric"),
]

SUMMARY_FIELDS = [
    ("listing_id", "id", "text"),
    ("name", "name", "text"),
    ("host_id", "host_id", "text"),
    ("neighbourhood_group", "neighbourhood_group", "text"),
    ("neighbourhood", "neighbourhood", "text"),
    ("latitude", "latitude", "numeric"),
    ("longitude", "longitude", "numeric"),
    ("room_type", "room_type", "text"),
    ("price_raw", "price", "text"),
    ("price_amount", "__price_amount", "numeric"),
    ("minimum_nights", "minimum_nights", "integer"),
    ("number_of_reviews", "number_of_reviews", "integer"),
    ("last_review", "last_review", "date"),
    ("reviews_per_month", "reviews_per_month", "numeric"),
    ("calculated_host_listings_count", "calculated_host_listings_count", "integer"),
    ("availability_365", "availability_365", "smallint"),
    ("number_of_reviews_ltm", "number_of_reviews_ltm", "integer"),
    ("license", "license", "text"),
]


class LoadFailure(RuntimeError):
    pass


def source_file(data_dir: Path, name: str):
    path = data_dir / name
    return gzip.open(path, "rt", encoding="utf-8-sig", newline="") if name.endswith(".gz") else path.open("r", encoding="utf-8-sig", newline="")


def blank(value: str | None) -> bool:
    return value is None or value.strip() == ""


def jsonb_text(value: str | None, field: str, line_number: int) -> str | None:
    if blank(value) or value.strip().lower() in {"none", "null"}:
        return None
    try:
        obj = json.loads(value)
    except json.JSONDecodeError:
        try:
            obj = ast.literal_eval(value)
        except (ValueError, SyntaxError) as exc:
            raise LoadFailure(f"invalid JSON-style {field} at source row {line_number}: {exc}") from exc
    if obj is None:
        return None
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


def quote_currency(raw_quote: str | None) -> str | None:
    if blank(raw_quote):
        return None
    try:
        payload = json.loads(raw_quote)
        value = payload.get("quote", {}).get("currency")
    except (json.JSONDecodeError, AttributeError, TypeError):
        return None
    return value if isinstance(value, str) and re.fullmatch(r"[A-Z]{3}", value) else None


def price_amount(raw_price: str | None) -> str | None:
    if blank(raw_price):
        return None
    value = raw_price.strip().replace("\u00a0", "").replace(" ", "")
    value = re.sub(r"^[^0-9+\-]+|[^0-9]+$", "", value)
    if not value:
        return None
    if "," in value:
        if "." in value:
            value = value.replace(",", "")
        elif re.fullmatch(r"[+-]?\d{1,3}(?:,\d{3})+", value):
            value = value.replace(",", "")
        elif value.count(",") == 1 and re.fullmatch(r"[+-]?\d+,\d{1,2}", value):
            value = value.replace(",", ".")
        else:
            return None
    try:
        amount = Decimal(value)
    except InvalidOperation:
        return None
    return format(amount, "f")


def normalize(value: str | None, kind: str, field: str, line_number: int) -> str | None:
    if kind == "jsonb":
        return jsonb_text(value, field, line_number)
    if blank(value):
        return None
    raw = value.strip()
    if raw.lower() in {"nan", "null"}:
        return None
    try:
        if kind in {"numeric", "integer", "smallint"}:
            if field in {"host_response_rate", "host_acceptance_rate"}:
                raw = raw.removesuffix("%").strip()
            number = Decimal(raw)
            if kind in {"integer", "smallint"}:
                if number != number.to_integral_value():
                    raise ValueError("not an integer")
                return str(int(number))
            return format(number, "f")
        if kind == "date":
            return date.fromisoformat(raw).isoformat()
        if kind == "boolean":
            low = raw.lower()
            if low in {"t", "true", "1", "yes"}:
                return "true"
            if low in {"f", "false", "0", "no"}:
                return "false"
            raise ValueError(f"unrecognized boolean {raw!r}")
    except (InvalidOperation, ValueError) as exc:
        raise LoadFailure(f"invalid {kind} value for {field} at source row {line_number}: {raw!r} ({exc})") from exc
    return value


def map_record(source: dict[str, str], fields: list[tuple[str, str, str]], line_number: int) -> dict[str, str | None]:
    record: dict[str, str | None] = {}
    quote = source.get("price_quote_raw")
    for target, origin, kind in fields:
        if origin == "__price_amount":
            record[target] = price_amount(source.get("price"))
        elif origin == "__price_currency":
            record[target] = quote_currency(quote)
        else:
            record[target] = normalize(source.get(origin), kind, target, line_number)
    return record


def copy_csv(path: Path, columns: list[str], rows: Iterable[dict[str, str | None]]) -> int:
    count = 0
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream, quoting=csv.QUOTE_MINIMAL, lineterminator="\n")
        writer.writerow(columns)
        for row in rows:
            writer.writerow([row.get(col) for col in columns])
            count += 1
    return count


def identifier(name: str) -> str:
    if not re.fullmatch(r"[a-z_][a-z0-9_]*", name):
        raise ValueError(f"unsafe SQL identifier: {name}")
    return name


class PsqlBatchLoader:
    def __init__(self, temp_dir: Path):
        self.temp_dir = temp_dir
        self.batch_number = 0

    def load(self, table: str, stage_columns: list[str], target_columns: list[str],
             row_batch: list[dict[str, str | None]], types: dict[str, str],
             conflict_columns: list[str], fill_missing: bool = False,
             derived_neighbourhood_fk: bool = False) -> None:
        if not row_batch:
            return
        self.batch_number += 1
        batch_tag = f"{self.batch_number:05d}"
        csv_path = self.temp_dir / f"batch_{batch_tag}.csv"
        sql_path = self.temp_dir / f"batch_{batch_tag}.sql"
        copy_csv(csv_path, stage_columns, row_batch)

        stage_name = identifier("stage_" + batch_tag)
        stage_def = ", ".join(f"{identifier(col)} text" for col in stage_columns)
        select_exprs: list[str] = []
        for col in target_columns:
            if col == "neighbourhood_fk" and derived_neighbourhood_fk:
                select_exprs.append("n.neighbourhood_name")
            else:
                kind = types[col]
                select_exprs.append(f"NULLIF(s.{identifier(col)}, '')::{kind}")
        from_clause = f"FROM {stage_name} s"
        if derived_neighbourhood_fk:
            from_clause += " LEFT JOIN neighbourhoods n ON n.neighbourhood_name = NULLIF(s.neighbourhood_cleansed, '')"

        conflict = ", ".join(identifier(col) for col in conflict_columns)
        keyset = set(conflict_columns)
        if fill_missing:
            assignments = [f"{identifier(col)} = COALESCE({identifier(table)}.{identifier(col)}, EXCLUDED.{identifier(col)})"
                           for col in target_columns if col not in keyset]
        else:
            assignments = [f"{identifier(col)} = COALESCE(EXCLUDED.{identifier(col)}, {identifier(table)}.{identifier(col)})"
                           for col in target_columns if col not in keyset]
        assignment_sql = ",\n    ".join(assignments)
        csv_filename = str(csv_path.resolve()).replace("\\", "/").replace("'", "''")
        sql = (
            "\\set ON_ERROR_STOP on\n"
            "BEGIN;\n"
            f"CREATE TEMP TABLE {stage_name} ({stage_def}) ON COMMIT DROP;\n"
            f"\\copy {stage_name} ({', '.join(identifier(c) for c in stage_columns)}) FROM '{csv_filename}' WITH (FORMAT csv, HEADER true, NULL '')\n"
            f"INSERT INTO {identifier(table)} ({', '.join(identifier(c) for c in target_columns)})\n"
            f"SELECT {', '.join(select_exprs)}\n{from_clause}\n"
            f"ON CONFLICT ({conflict}) DO UPDATE SET\n    {assignment_sql};\n"
            "COMMIT;\n"
        )
        sql_path.write_text(sql, encoding="utf-8")
        result = subprocess.run(
            [PSQL, "-X", "-q", "-h", HOST, "-U", DB_USER, "-d", DATABASE,
             "-v", "ON_ERROR_STOP=1", "-f", str(sql_path)],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
        if result.returncode != 0:
            detail = (result.stderr or result.stdout).strip()
            raise LoadFailure(f"{table} batch {batch_tag} failed; earlier committed batches are safe to rerun.\n{detail}")
        csv_path.unlink(missing_ok=True)
        sql_path.unlink(missing_ok=True)


def type_map(fields: list[tuple[str, str, str]]) -> dict[str, str]:
    return {target: kind for target, _, kind in fields}


def load_stream(loader: PsqlBatchLoader, table: str, fields: list[tuple[str, str, str]],
                records: Iterable[dict[str, str | None]], key_columns: list[str],
                chunk_size: int, fill_missing: bool = False,
                derived_neighbourhood_fk: bool = False) -> tuple[int, int, int]:
    stage_columns = [target for target, _, _ in fields]
    target_columns = stage_columns.copy()
    types = type_map(fields)
    if derived_neighbourhood_fk:
        target_columns.insert(target_columns.index("latitude"), "neighbourhood_fk")
        types["neighbourhood_fk"] = "text"
    pending: dict[tuple[str | None, ...], dict[str, str | None]] = {}
    source_rows = loaded_rows = dropped_keys = batch_duplicates = 0
    batches = 0

    def flush() -> None:
        nonlocal loaded_rows, batches
        if pending:
            loader.load(table, stage_columns, target_columns, list(pending.values()), types,
                        key_columns, fill_missing=fill_missing,
                        derived_neighbourhood_fk=derived_neighbourhood_fk)
            loaded_rows += len(pending)
            batches += 1
            if batches % 10 == 0 or table in {"neighbourhoods", "hosts"}:
                print(f"{table}: committed {loaded_rows:,} rows in {batches:,} batches", flush=True)
            pending.clear()

    for record in records:
        source_rows += 1
        key = tuple(record.get(col) for col in key_columns)
        if any(blank(part) for part in key):
            dropped_keys += 1
            continue
        if key in pending:
            batch_duplicates += 1
        pending[key] = record
        if len(pending) >= chunk_size:
            flush()
    flush()
    print(f"{table}: source_rows={source_rows:,}, attempted_unique_rows={loaded_rows:,}, "
          f"missing_keys={dropped_keys:,}, within_batch_duplicate_rows={batch_duplicates:,}", flush=True)
    return source_rows, loaded_rows, dropped_keys


def main() -> int:
    data_dir = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else DEFAULT_DATA
    if not data_dir.is_dir():
        print(f"Data directory not found: {data_dir}", file=sys.stderr)
        return 2
    listing_path = data_dir / "listings.csv.gz"
    for required in [listing_path, data_dir / "calendar.csv.gz", data_dir / "reviews.csv.gz",
                     data_dir / "neighbourhoods.csv", data_dir / "listings.csv"]:
        if not required.is_file():
            print(f"Required source file not found: {required}", file=sys.stderr)
            return 2

    # Collect host profiles and detailed listing keys before loading. For
    # repeated host records, keep the first nonblank value for each profile field.
    host_profiles: dict[str, dict[str, str | None]] = {}
    detailed_listing_ids: set[str] = set()
    detail_rows = 0
    with source_file(data_dir, "listings.csv.gz") as stream:
        for line_number, row in enumerate(csv.DictReader(stream), start=2):
            detail_rows += 1
            listing_id = normalize(row.get("id"), "text", "listing_id", line_number)
            if listing_id:
                detailed_listing_ids.add(listing_id)
            host_record = map_record(row, HOST_FIELDS, line_number)
            host_id = host_record.get("host_id")
            if not host_id:
                continue
            current = host_profiles.setdefault(host_id, host_record.copy())
            for col, _, _ in HOST_FIELDS:
                if current.get(col) is None and host_record.get(col) is not None:
                    current[col] = host_record[col]

    with tempfile.TemporaryDirectory(prefix="airbnb_athens_loader_") as temp_name:
        loader = PsqlBatchLoader(Path(temp_name))

        # Neighbourhood lookup rows first, then host records required by listings.
        def neighbourhood_records() -> Iterator[dict[str, str | None]]:
            with source_file(data_dir, "neighbourhoods.csv") as stream:
                for line_number, row in enumerate(csv.DictReader(stream), start=2):
                    yield {
                        "neighbourhood_group": normalize(row.get("neighbourhood_group"), "text", "neighbourhood_group", line_number),
                        "neighbourhood_name": normalize(row.get("neighbourhood"), "text", "neighbourhood_name", line_number),
                    }

        neighbourhood_fields = [("neighbourhood_group", "neighbourhood_group", "text"),
                                ("neighbourhood_name", "neighbourhood_name", "text")]
        load_stream(loader, "neighbourhoods", neighbourhood_fields,
                    neighbourhood_records(), ["neighbourhood_name"], CHUNK_SIZE)

        host_records = (profile for profile in host_profiles.values())
        load_stream(loader, "hosts", HOST_FIELDS, host_records, ["host_id"], CHUNK_SIZE)
        print(f"detailed_listings_source_rows={detail_rows:,}; distinct_host_ids={len(host_profiles):,}; "
              f"distinct_listing_ids={len(detailed_listing_ids):,}", flush=True)

        def detailed_records() -> Iterator[dict[str, str | None]]:
            with source_file(data_dir, "listings.csv.gz") as stream:
                for line_number, row in enumerate(csv.DictReader(stream), start=2):
                    yield map_record(row, LISTING_FIELDS, line_number)

        load_stream(loader, "listings", LISTING_FIELDS, detailed_records(), ["listing_id"],
                    CHUNK_SIZE, derived_neighbourhood_fk=True)

        # Summary listings can fill null fields on already-imported detailed
        # listings, but cannot create a listing absent from the detailed file.
        summary_matched = summary_unmatched = 0

        def summary_records() -> Iterator[dict[str, str | None]]:
            nonlocal summary_matched, summary_unmatched
            with source_file(data_dir, "listings.csv") as stream:
                for line_number, row in enumerate(csv.DictReader(stream), start=2):
                    mapped = map_record(row, SUMMARY_FIELDS, line_number)
                    listing_id = mapped.get("listing_id")
                    if listing_id not in detailed_listing_ids:
                        summary_unmatched += 1
                        continue
                    summary_matched += 1
                    yield mapped

        load_stream(loader, "listings", SUMMARY_FIELDS, summary_records(), ["listing_id"],
                    CHUNK_SIZE, fill_missing=True)
        print(f"summary_listings_matched_existing={summary_matched:,}; "
              f"summary_listing_ids_without_detailed_match={summary_unmatched:,}", flush=True)

        calendar_fields = [("listing_id", "listing_id", "text"),
                           ("calendar_date", "date", "date"),
                           ("available", "available", "boolean"),
                           ("minimum_nights", "minimum_nights", "integer"),
                           ("maximum_nights", "maximum_nights", "integer")]

        def calendar_records() -> Iterator[dict[str, str | None]]:
            with source_file(data_dir, "calendar.csv.gz") as stream:
                for line_number, row in enumerate(csv.DictReader(stream), start=2):
                    yield map_record(row, calendar_fields, line_number)

        load_stream(loader, "listing_calendar", calendar_fields, calendar_records(),
                    ["listing_id", "calendar_date"], CHUNK_SIZE)

        review_fields = [("review_id", "id", "text"),
                         ("listing_id", "listing_id", "text"),
                         ("review_date", "date", "date"),
                         ("reviewer_id", "reviewer_id", "text"),
                         ("reviewer_name", "reviewer_name", "text"),
                         ("comments", "comments", "text")]

        def review_records() -> Iterator[dict[str, str | None]]:
            with source_file(data_dir, "reviews.csv.gz") as stream:
                for line_number, row in enumerate(csv.DictReader(stream), start=2):
                    yield map_record(row, review_fields, line_number)

        load_stream(loader, "reviews", review_fields, review_records(), ["review_id"], CHUNK_SIZE)

    print("Bulk source load complete. Validate row counts and FK integrity with the companion SQL checks.", flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except LoadFailure as exc:
        print(f"LOAD FAILED: {exc}", file=sys.stderr)
        raise SystemExit(1)
