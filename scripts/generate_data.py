from __future__ import annotations

import argparse
import math
import random
import shutil
import string
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq


TARGETS = {
    "aircraft": 120,
    "route": 400,
    "flight": 250_000,
    "booking": 4_000_000,
    "customer": 500_000,
    "loyalty_transaction": 2_000_000,
    "cargo_shipment": 180_000,
    "maintenance_event": 40_000,
    "crew_roster": 350_000,
    "disruption_event": 20_000,
}

MINIMUMS = {
    "aircraft": 24,
    "route": 40,
    "flight": 1_000,
    "booking": 2_000,
    "customer": 1_000,
    "loyalty_transaction": 2_000,
    "cargo_shipment": 500,
    "maintenance_event": 200,
    "crew_roster": 1_000,
    "disruption_event": 100,
}

OPCO_AIRCRAFT = {
    "MAINLINE": [
        ("A320neo", 186, 3_400),
        ("A321neo", 220, 4_200),
        ("A350-1000", 331, 14_000),
        ("B787-9", 258, 12_500),
    ],
    "REGIONAL": [
        ("E190", 100, 1_800),
        ("A220-300", 145, 2_500),
    ],
    "CARGO": [
        ("B777F", 0, 102_000),
        ("B767F", 0, 52_000),
    ],
}

AIRPORTS = [
    "LHR", "LGW", "MAN", "EDI", "GLA", "BHD", "BHX", "BRS", "NCL", "DUB",
    "AMS", "CDG", "ORY", "FRA", "MUC", "MAD", "BCN", "LIS", "FCO", "MXP",
    "ZRH", "GVA", "CPH", "OSL", "ARN", "HEL", "BRU", "VIE", "PRG", "WAW",
    "ATH", "IST", "DXB", "DOH", "JED", "CAI", "JNB", "CPT", "NBO", "LOS",
    "DEL", "BOM", "BLR", "SIN", "HKG", "BKK", "NRT", "HND", "ICN", "SYD",
    "MEL", "AKL", "JFK", "EWR", "BOS", "IAD", "MIA", "ORD", "DFW", "LAX",
    "SFO", "SEA", "YYZ", "YVR", "MEX", "GRU", "GIG", "EZE",
]

AIRPORT_REGION = {
    **{code: "UKI" for code in ["LHR", "LGW", "MAN", "EDI", "GLA", "BHD", "BHX", "BRS", "NCL", "DUB"]},
    **{code: "EU" for code in [
        "AMS", "CDG", "ORY", "FRA", "MUC", "MAD", "BCN", "LIS", "FCO", "MXP",
        "ZRH", "GVA", "CPH", "OSL", "ARN", "HEL", "BRU", "VIE", "PRG", "WAW", "ATH",
    ]},
    **{code: "MEA" for code in ["IST", "DXB", "DOH", "JED", "CAI", "JNB", "CPT", "NBO", "LOS"]},
    **{code: "APAC" for code in [
        "DEL", "BOM", "BLR", "SIN", "HKG", "BKK", "NRT", "HND", "ICN", "SYD", "MEL", "AKL",
    ]},
    **{code: "AMER" for code in [
        "JFK", "EWR", "BOS", "IAD", "MIA", "ORD", "DFW", "LAX", "SFO", "SEA",
        "YYZ", "YVR", "MEX", "GRU", "GIG", "EZE",
    ]},
}

DISTANCE_RANGES = {
    ("UKI", "UKI"): (300, 800),
    ("UKI", "EU"): (450, 2_800),
    ("EU", "EU"): (400, 2_600),
    ("UKI", "MEA"): (3_000, 9_500),
    ("EU", "MEA"): (2_500, 9_000),
    ("UKI", "APAC"): (6_500, 17_000),
    ("EU", "APAC"): (6_000, 16_500),
    ("UKI", "AMER"): (5_000, 12_000),
    ("EU", "AMER"): (5_500, 12_500),
    ("MEA", "APAC"): (3_000, 12_000),
    ("MEA", "AMER"): (8_000, 14_000),
    ("APAC", "AMER"): (8_000, 14_500),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a reproducible aviation holding-group dataset.")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--scale",
        type=float,
        default=0.01,
        help="Fraction of target volume to generate (default: 0.01 for a small demo; use 1 for full scale).",
    )
    parser.add_argument("--end-date", type=date.fromisoformat, default=date.today())
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "data",
    )
    args = parser.parse_args()
    if not 0 < args.scale <= 1:
        parser.error("--scale must be greater than 0 and no more than 1")
    return args


def scaled_count(name: str, scale: float) -> int:
    return min(TARGETS[name], max(MINIMUMS[name], round(TARGETS[name] * scale)))


def season_weight(day: date) -> float:
    month = day.month
    if month in (6, 7, 8):
        return 1.28
    if month == 12:
        return 1.22 if day.day >= 15 else 1.08
    if month == 2:
        return 0.76
    if month in (4, 5, 9, 10):
        return 1.06
    return 0.94


def daterange(start: date, end: date) -> list[date]:
    return [start + timedelta(days=i) for i in range((end - start).days + 1)]


def random_dates(rng: random.Random, days: list[date], n: int) -> list[date]:
    weights = [season_weight(day) * (1.08 if day.weekday() in (4, 5, 6) else 1.0) for day in days]
    return rng.choices(days, weights=weights, k=n)


def clean_output(output_dir: Path) -> tuple[Path, Path]:
    raw_dir = output_dir / "raw"
    csv_dir = output_dir / "csv"
    for target in (raw_dir, csv_dir):
        if target.exists():
            shutil.rmtree(target)
        target.mkdir(parents=True, exist_ok=True)
    return raw_dir, csv_dir


def bytes_under(path: Path) -> int:
    if path.is_file():
        return path.stat().st_size
    return sum(item.stat().st_size for item in path.rglob("*") if item.is_file())


class OutputWriter:
    def __init__(self, raw_dir: Path, csv_dir: Path) -> None:
        self.raw_dir = raw_dir
        self.csv_dir = csv_dir
        self.summary: list[dict[str, object]] = []

    def write(self, name: str, frame: pd.DataFrame) -> None:
        raw_path = self.raw_dir / f"{name}.parquet"
        csv_path = self.csv_dir / f"{name}.csv"
        frame.to_parquet(raw_path, engine="pyarrow", compression="snappy", index=False)
        frame.head(50_000).to_csv(csv_path, index=False)
        self.summary.append(
            {
                "table": name,
                "rows": len(frame),
                "parquet_mb": bytes_under(raw_path) / 1_048_576,
                "csv_preview_mb": bytes_under(csv_path) / 1_048_576,
            }
        )

    def record_partitioned(self, name: str, rows: int) -> None:
        raw_path = self.raw_dir / name
        csv_path = self.csv_dir / f"{name}.csv"
        self.summary.append(
            {
                "table": name,
                "rows": rows,
                "parquet_mb": bytes_under(raw_path) / 1_048_576,
                "csv_preview_mb": bytes_under(csv_path) / 1_048_576,
            }
        )


def weighted_type(rng: random.Random, opco: str) -> tuple[str, int, int]:
    types = OPCO_AIRCRAFT[opco]
    weights = [0.30, 0.28, 0.20, 0.22] if opco == "MAINLINE" else None
    return rng.choices(types, weights=weights, k=1)[0]


def build_aircraft(rng: random.Random, count: int, start: date, end: date) -> pd.DataFrame:
    opcos = rng.choices(["MAINLINE", "REGIONAL", "CARGO"], weights=[0.58, 0.25, 0.17], k=count)
    required = [
        ("MAINLINE", "B787-9"),
        ("MAINLINE", "A320neo"),
        ("REGIONAL", "E190"),
        ("CARGO", "B777F"),
    ]
    rows = []
    for i, opco in enumerate(opcos):
        aircraft_type, seats, capacity = weighted_type(rng, opco)
        if i < len(required):
            opco, forced_type = required[i]
            aircraft_type, seats, capacity = next(item for item in OPCO_AIRCRAFT[opco] if item[0] == forced_type)
        delivery_start = date(2002, 1, 1)
        delivery_end = min(end - timedelta(days=90), date(2025, 12, 31))
        delivered = delivery_start + timedelta(days=rng.randrange((delivery_end - delivery_start).days + 1))
        rows.append(
            {
                "tail_number": f"G-AV{i + 1:03d}",
                "type": aircraft_type,
                "opco": opco,
                "seats": seats,
                "cargo_capacity_kg": capacity,
                "delivery_date": delivered,
            }
        )
    return pd.DataFrame(rows)


def route_distance(rng: random.Random, origin: str, destination: str) -> int:
    pair = tuple(sorted((AIRPORT_REGION[origin], AIRPORT_REGION[destination])))
    bounds = DISTANCE_RANGES.get(pair)
    if bounds is None:
        bounds = (2_000, 11_000)
    return rng.randint(*bounds)


def build_routes(rng: random.Random, count: int) -> pd.DataFrame:
    anchors = [
        ("LHR", "HKG"),
        ("LHR", "JFK"),
        ("LHR", "DXB"),
        ("LHR", "EDI"),
        ("MAN", "AMS"),
        ("FRA", "SIN"),
    ]
    pairs = set(anchors)
    while len(pairs) < count:
        origin, destination = rng.sample(AIRPORTS, 2)
        pairs.add((origin, destination))
    rows = []
    for i, (origin, destination) in enumerate(sorted(pairs)):
        distance = route_distance(rng, origin, destination)
        rows.append(
            {
                "route_id": f"R{i + 1:04d}",
                "origin_iata": origin,
                "dest_iata": destination,
                "distance_km": distance,
                "haul_type": "SHORT" if distance < 3_500 else "LONG",
            }
        )
    return pd.DataFrame(rows)


def choose_route_ids(
    rng: random.Random,
    routes: pd.DataFrame,
    opco: str,
    n: int,
) -> list[str]:
    if opco == "REGIONAL":
        pool = routes.loc[routes["haul_type"] == "SHORT", "route_id"].tolist()
    elif opco == "CARGO":
        pool = routes["route_id"].tolist()
        anomaly_id = routes.loc[
            (routes["origin_iata"] == "LHR") & (routes["dest_iata"] == "HKG"), "route_id"
        ].iloc[0]
        return rng.choices(pool + [anomaly_id], weights=[1] * len(pool) + [max(10, len(pool) // 3)], k=n)
    else:
        pool = routes["route_id"].tolist()
    return rng.choices(pool, k=n)


def build_flights(
    rng: random.Random,
    count: int,
    days: list[date],
    aircraft: pd.DataFrame,
    routes: pd.DataFrame,
) -> pd.DataFrame:
    opcos = rng.choices(["MAINLINE", "REGIONAL", "CARGO"], weights=[0.55, 0.30, 0.15], k=count)
    flight_dates = random_dates(rng, days, count)
    aircraft_by_opco = {
        opco: aircraft.loc[aircraft["opco"] == opco, "tail_number"].tolist()
        for opco in ("MAINLINE", "REGIONAL", "CARGO")
    }
    route_ids: list[str] = [""] * count
    for opco in ("MAINLINE", "REGIONAL", "CARGO"):
        positions = [i for i, value in enumerate(opcos) if value == opco]
        selected = choose_route_ids(rng, routes, opco, len(positions))
        for position, route_id in zip(positions, selected):
            route_ids[position] = route_id

    reason_codes = ["WEATHER", "ATC", "TECHNICAL", "CREW", "ROTATIONAL"]
    reason_weights = [0.18, 0.24, 0.14, 0.10, 0.34]
    rows = []
    daily_sequence: dict[tuple[date, str], int] = defaultdict(int)
    for i in range(count):
        opco = opcos[i]
        flight_date = flight_dates[i]
        daily_sequence[(flight_date, opco)] += 1
        prefix = {"MAINLINE": "ML", "REGIONAL": "RG", "CARGO": "CG"}[opco]
        flight_no = f"{prefix}{100 + daily_sequence[(flight_date, opco)] % 8900:04d}"
        scheduled = datetime.combine(flight_date, datetime.min.time()) + timedelta(
            minutes=rng.randrange(5 * 60, 23 * 60, 5)
        )
        cancelled = rng.random() < (0.012 if opco != "CARGO" else 0.018)
        delayed = not cancelled and rng.random() >= 0.78
        if delayed:
            delay = max(5, min(720, round(rng.lognormvariate(3.15, 0.85))))
            reason = rng.choices(reason_codes, weights=reason_weights, k=1)[0]
        else:
            delay = 0
            reason = None
        load_base = 0.73 if opco == "CARGO" else 0.79
        load_factor = load_base + (season_weight(flight_date) - 1) * 0.22
        load_factor += 0.035 if flight_date.weekday() in (4, 5, 6) else 0
        load_factor = max(0.42, min(0.99, load_factor + rng.gauss(0, 0.075)))
        rows.append(
            {
                "flight_no": flight_no,
                "date": flight_date,
                "tail_number": rng.choice(aircraft_by_opco[opco]),
                "route_id": route_ids[i],
                "opco": opco,
                "scheduled_dep": scheduled,
                "actual_dep": None if cancelled else scheduled + timedelta(minutes=delay),
                "delay_minutes": None if cancelled else delay,
                "delay_reason_code": "CANCELLED" if cancelled else reason,
                "cancelled_flag": cancelled,
                "load_factor": round(load_factor, 4),
            }
        )
    return pd.DataFrame(rows).sort_values(["date", "flight_no"]).reset_index(drop=True)


def build_customers(rng: random.Random, count: int, start: date, end: date) -> pd.DataFrame:
    tiers = rng.choices(["BLUE", "BRONZE", "SILVER", "GOLD"], weights=[0.54, 0.23, 0.16, 0.07], k=count)
    rows = []
    join_start = date(2005, 1, 1)
    for i in range(count):
        joined = join_start + timedelta(days=rng.randrange((end - join_start).days + 1))
        rows.append(
            {
                "customer_id": f"C{i + 1:09d}",
                "home_airport": rng.choices(AIRPORTS, weights=[5 if a in ("LHR", "LGW", "MAN") else 1 for a in AIRPORTS], k=1)[0],
                "tier": tiers[i],
                "opco_affinity": rng.choices(["MAINLINE", "REGIONAL", "CARGO", "LOYALTY"], weights=[0.58, 0.19, 0.02, 0.21], k=1)[0],
                "joined_date": joined,
            }
        )
    return pd.DataFrame(rows)


def booking_batch(
    rng: random.Random,
    passenger_flights: pd.DataFrame,
    customer_ids: list[str],
    start_sequence: int,
    count: int,
) -> pd.DataFrame:
    sampled = passenger_flights.sample(n=count, replace=True, random_state=rng.randrange(2**32 - 1)).reset_index(drop=True)
    fare_classes = []
    revenues = []
    ancillaries = []
    channels = []
    for row in sampled.itertuples(index=False):
        is_weekend = row.date.weekday() in (4, 5, 6)
        if row.haul_type == "LONG":
            fare = rng.choices(["ECONOMY", "PREMIUM", "BUSINESS", "FIRST"], [0.66, 0.17, 0.14, 0.03], k=1)[0]
            ranges = {"ECONOMY": (300, 900), "PREMIUM": (700, 1_500), "BUSINESS": (1_800, 5_500), "FIRST": (4_500, 9_000)}
        else:
            fare = rng.choices(["ECONOMY", "FLEX", "BUSINESS"], [0.74 if is_weekend else 0.65, 0.18, 0.08 if is_weekend else 0.17], k=1)[0]
            ranges = {"ECONOMY": (55, 240), "FLEX": (160, 420), "BUSINESS": (350, 900)}
        low, high = ranges[fare]
        fare_classes.append(fare)
        revenues.append(round(rng.uniform(low, high), 2))
        ancillaries.append(round(max(0, rng.gauss(34 if fare == "ECONOMY" else 15, 18)), 2))
        channels.append(rng.choices(["WEB", "MOBILE", "CORPORATE", "TRAVEL_AGENT"], [0.42, 0.31, 0.15, 0.12], k=1)[0])
    return pd.DataFrame(
        {
            "booking_ref": [f"B{start_sequence + i:011d}" for i in range(count)],
            "flight_no": sampled["flight_no"],
            "date": sampled["date"],
            "customer_id": rng.choices(customer_ids, k=count),
            "fare_class": fare_classes,
            "revenue_gbp": revenues,
            "ancillary_gbp": ancillaries,
            "channel": channels,
        }
    )


def write_bookings(
    rng: random.Random,
    count: int,
    flights: pd.DataFrame,
    routes: pd.DataFrame,
    customers: pd.DataFrame,
    writer: OutputWriter,
) -> None:
    passenger = flights.loc[flights["opco"].isin(["MAINLINE", "REGIONAL"])].merge(
        routes[["route_id", "haul_type"]], on="route_id", how="left"
    )
    passenger["year_month"] = pd.to_datetime(passenger["date"]).dt.strftime("%Y-%m")
    month_counts = passenger["year_month"].value_counts(normalize=True).sort_index()
    allocations = {month: round(count * share) for month, share in month_counts.items()}
    allocations[next(iter(allocations))] += count - sum(allocations.values())
    target = writer.raw_dir / "booking"
    target.mkdir(parents=True, exist_ok=True)
    csv_path = writer.csv_dir / "booking.csv"
    csv_written = 0
    sequence = 1
    for month, month_count in allocations.items():
        month_flights = passenger.loc[passenger["year_month"] == month]
        batch = booking_batch(rng, month_flights, customers["customer_id"].tolist(), sequence, month_count)
        partition = target / f"year_month={month}"
        partition.mkdir(parents=True, exist_ok=True)
        batch.to_parquet(partition / "part-00000.parquet", engine="pyarrow", compression="snappy", index=False)
        if csv_written < 50_000:
            preview = batch.head(50_000 - csv_written)
            preview.to_csv(csv_path, mode="a", header=csv_written == 0, index=False)
            csv_written += len(preview)
        sequence += month_count
    writer.record_partitioned("booking", count)


def write_loyalty_transactions(
    rng: random.Random,
    count: int,
    days: list[date],
    customers: pd.DataFrame,
    writer: OutputWriter,
) -> None:
    path = writer.raw_dir / "loyalty_transaction.parquet"
    csv_path = writer.csv_dir / "loyalty_transaction.csv"
    parquet_writer = None
    customer_ids = customers["customer_id"].tolist()
    written = 0
    csv_written = 0
    while written < count:
        size = min(250_000, count - written)
        transaction_dates = random_dates(rng, days, size)
        rows = []
        for i in range(size):
            redemption = rng.random() < 0.24
            rows.append(
                {
                    "customer_id": rng.choice(customer_ids),
                    "points_earned": 0 if redemption else rng.choices([250, 500, 750, 1_500, 3_000, 8_000], [20, 24, 18, 18, 14, 6], k=1)[0],
                    "points_redeemed": rng.choices([2_500, 5_000, 10_000, 25_000, 50_000], [28, 28, 23, 15, 6], k=1)[0] if redemption else 0,
                    "partner": rng.choices(["MAINLINE", "REGIONAL", "HOTEL", "CAR_RENTAL", "CREDIT_CARD", "RETAIL"], [0.39, 0.14, 0.11, 0.07, 0.20, 0.09], k=1)[0],
                    "date": transaction_dates[i],
                }
            )
        frame = pd.DataFrame(rows)
        table = pa.Table.from_pandas(frame, preserve_index=False)
        if parquet_writer is None:
            parquet_writer = pq.ParquetWriter(path, table.schema, compression="snappy")
        parquet_writer.write_table(table)
        if csv_written < 50_000:
            preview = frame.head(50_000 - csv_written)
            preview.to_csv(csv_path, mode="a", header=csv_written == 0, index=False)
            csv_written += len(preview)
        written += size
    if parquet_writer is not None:
        parquet_writer.close()
    writer.summary.append(
        {
            "table": "loyalty_transaction",
            "rows": count,
            "parquet_mb": bytes_under(path) / 1_048_576,
            "csv_preview_mb": bytes_under(csv_path) / 1_048_576,
        }
    )


def build_cargo_shipments(
    rng: random.Random,
    count: int,
    flights: pd.DataFrame,
    routes: pd.DataFrame,
    end: date,
) -> pd.DataFrame:
    cargo = flights.loc[flights["opco"] == "CARGO"].merge(
        routes[["route_id", "origin_iata", "dest_iata"]], on="route_id", how="left"
    )
    anomaly = cargo.loc[(cargo["origin_iata"] == "LHR") & (cargo["dest_iata"] == "HKG")]
    forced_count = max(1, round(count * 0.12))
    sampled = pd.concat(
        [
            anomaly.sample(n=forced_count, replace=True, random_state=rng.randrange(2**32 - 1)),
            cargo.sample(n=count - forced_count, replace=True, random_state=rng.randrange(2**32 - 1)),
        ],
        ignore_index=True,
    ).sample(frac=1, random_state=rng.randrange(2**32 - 1)).reset_index(drop=True)
    degradation_start = end - timedelta(weeks=8)
    rows = []
    for i, flight in enumerate(sampled.itertuples(index=False)):
        lane = f"{flight.origin_iata}-{flight.dest_iata}"
        weight = max(50, round(rng.lognormvariate(7.0, 0.85), 1))
        chargeable = round(weight * rng.uniform(1.0, 1.22), 1)
        base_yield = rng.uniform(2.35, 3.25)
        if lane == "LHR-HKG" and flight.date >= degradation_start:
            progress = (flight.date - degradation_start).days / max(1, (end - degradation_start).days)
            base_yield *= 1 - 0.30 * progress
        rows.append(
            {
                "awb_number": f"125-{i + 1:08d}",
                "flight_no": flight.flight_no,
                "date": flight.date,
                "weight_kg": weight,
                "chargeable_weight_kg": chargeable,
                "lane": lane,
                "yield_gbp_per_kg": round(base_yield, 3),
                "commodity": rng.choices(["GENERAL", "PHARMA", "PERISHABLE", "EXPRESS", "AUTOMOTIVE", "LIVE_ANIMALS"], [0.38, 0.13, 0.15, 0.19, 0.11, 0.04], k=1)[0],
                "shipper_id": f"S{rng.randint(1, max(1000, count // 6)):07d}",
            }
        )
    return pd.DataFrame(rows)


def build_maintenance(
    rng: random.Random,
    count: int,
    days: list[date],
    aircraft: pd.DataFrame,
    end: date,
) -> pd.DataFrame:
    joined = aircraft[["tail_number", "type"]]
    sampled = joined.sample(n=count, replace=True, random_state=rng.randrange(2**32 - 1)).reset_index(drop=True)
    event_dates = random_dates(rng, days, count)
    rise_start = end - timedelta(weeks=12)
    rows = []
    for i, item in enumerate(sampled.itertuples(index=False)):
        event_date = event_dates[i]
        base_aog = 0.075
        if item.type == "B787-9" and event_date >= rise_start:
            progress = (event_date - rise_start).days / max(1, (end - rise_start).days)
            base_aog = 0.10 + 0.32 * progress
        aog = rng.random() < base_aog
        downtime = rng.uniform(18, 96) if aog else rng.uniform(1, 18)
        rows.append(
            {
                "tail_number": item.tail_number,
                "event_date": event_date,
                "ata_chapter": rng.choices(["21", "24", "27", "29", "32", "34", "36", "49", "52", "71"], [9, 13, 11, 8, 14, 10, 6, 8, 7, 14], k=1)[0],
                "part_number": f"PN-{rng.choice(string.ascii_uppercase)}{rng.randint(10000, 99999)}",
                "downtime_hours": round(downtime, 2),
                "cost_gbp": round(downtime * rng.uniform(1_200, 4_800) + rng.uniform(500, 15_000), 2),
                "aog_flag": aog,
            }
        )
    return pd.DataFrame(rows)


def build_crew_roster(rng: random.Random, count: int, flights: pd.DataFrame) -> pd.DataFrame:
    sampled = flights.sample(n=count, replace=True, random_state=rng.randrange(2**32 - 1)).reset_index(drop=True)
    roles = ["CAPTAIN", "FIRST_OFFICER", "CABIN_MANAGER", "CABIN_CREW", "LOADMASTER"]
    rows = []
    for i, flight in enumerate(sampled.itertuples(index=False)):
        role_pool = ["CAPTAIN", "FIRST_OFFICER", "LOADMASTER"] if flight.opco == "CARGO" else roles[:-1]
        role = rng.choice(role_pool)
        base = rng.choice(["LHR", "LGW", "MAN", "EDI", "FRA", "AMS"])
        rows.append(
            {
                "crew_id": f"CR{rng.randint(1, max(5_000, count // 3)):07d}",
                "opco": flight.opco,
                "base": base,
                "duty_date": flight.date,
                "flight_no": flight.flight_no,
                "role": role,
                "duty_hours": round(rng.uniform(3.5, 13.8), 2),
                "standby_flag": rng.random() < 0.06,
            }
        )
    return pd.DataFrame(rows)


def build_disruptions(rng: random.Random, count: int, flights: pd.DataFrame) -> pd.DataFrame:
    affected = flights.loc[
        flights["cancelled_flag"] | flights["delay_minutes"].fillna(0).ge(45)
    ].copy()
    if affected.empty:
        affected = flights
    sampled = affected.sample(n=count, replace=len(affected) < count, random_state=rng.randrange(2**32 - 1))
    rows = []
    for flight in sampled.itertuples(index=False):
        if flight.cancelled_flag:
            event_type, severity = "CANCELLATION", "CRITICAL"
        elif (flight.delay_minutes or 0) >= 180:
            event_type, severity = "LONG_DELAY", "HIGH"
        else:
            event_type, severity = rng.choice(["MISCONNECT", "DELAY", "BAGGAGE"]), rng.choice(["MEDIUM", "HIGH"])
        pax = 0 if flight.opco == "CARGO" else rng.randint(20, 280)
        eligible = pax if event_type in ("CANCELLATION", "LONG_DELAY") else round(pax * rng.uniform(0.05, 0.35))
        rows.append(
            {
                "flight_no": flight.flight_no,
                "date": flight.date,
                "event_type": event_type,
                "severity": severity,
                "pax_affected": pax,
                "rebook_cost_gbp": round(pax * rng.uniform(35, 210), 2),
                "compensation_gbp": round(eligible * rng.choice([0, 220, 350, 520]), 2),
            }
        )
    return pd.DataFrame(rows)


def print_summary(summary: list[dict[str, object]], output_dir: Path) -> None:
    frame = pd.DataFrame(summary)
    frame["rows"] = frame["rows"].map(lambda value: f"{int(value):,}")
    frame["parquet_mb"] = frame["parquet_mb"].map(lambda value: f"{float(value):,.2f}")
    frame["csv_preview_mb"] = frame["csv_preview_mb"].map(lambda value: f"{float(value):,.2f}")
    print("\nGenerated aviation demo data")
    print(frame.to_string(index=False))
    print(f"\nOutput: {output_dir.resolve()}")


def main() -> None:
    args = parse_args()
    rng = random.Random(args.seed)
    end = args.end_date
    start = end - timedelta(days=548)
    days = daterange(start, end)
    raw_dir, csv_dir = clean_output(args.output_dir)
    writer = OutputWriter(raw_dir, csv_dir)

    aircraft = build_aircraft(rng, scaled_count("aircraft", args.scale), start, end)
    routes = build_routes(rng, scaled_count("route", args.scale))
    flights = build_flights(rng, scaled_count("flight", args.scale), days, aircraft, routes)
    customers = build_customers(rng, scaled_count("customer", args.scale), start, end)

    writer.write("aircraft", aircraft)
    writer.write("route", routes)
    writer.write("flight", flights)
    writer.write("customer", customers)

    write_bookings(
        rng,
        scaled_count("booking", args.scale),
        flights,
        routes,
        customers,
        writer,
    )
    write_loyalty_transactions(
        rng,
        scaled_count("loyalty_transaction", args.scale),
        days,
        customers,
        writer,
    )

    cargo = build_cargo_shipments(
        rng,
        scaled_count("cargo_shipment", args.scale),
        flights,
        routes,
        end,
    )
    maintenance = build_maintenance(
        rng,
        scaled_count("maintenance_event", args.scale),
        days,
        aircraft,
        end,
    )
    crew = build_crew_roster(rng, scaled_count("crew_roster", args.scale), flights)
    disruptions = build_disruptions(rng, scaled_count("disruption_event", args.scale), flights)

    writer.write("cargo_shipment", cargo)
    writer.write("maintenance_event", maintenance)
    writer.write("crew_roster", crew)
    writer.write("disruption_event", disruptions)
    print_summary(writer.summary, args.output_dir)


if __name__ == "__main__":
    main()
