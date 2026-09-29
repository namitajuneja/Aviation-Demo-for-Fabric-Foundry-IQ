import argparse
import os
from pathlib import Path

import pandas as pd
import snowflake.connector
from snowflake.connector.pandas_tools import write_pandas


TABLE_PATHS = {
    "AIRCRAFT": "aircraft.parquet",
    "ROUTE": "route.parquet",
    "FLIGHT": "flight.parquet",
    "BOOKING": "booking",
    "CUSTOMER": "customer.parquet",
    "LOYALTY_TRANSACTION": "loyalty_transaction.parquet",
    "CARGO_SHIPMENT": "cargo_shipment.parquet",
    "MAINTENANCE_EVENT": "maintenance_event.parquet",
    "CREW_ROSTER": "crew_roster.parquet",
    "DISRUPTION_EVENT": "disruption_event.parquet",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Load generated demo data into Snowflake.")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def required_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def main() -> None:
    args = parse_args()
    root = Path(__file__).resolve().parents[1]
    ddl_path = root / "snowflake" / "01_create_objects.sql"
    raw_path = root / "data" / "raw"

    if args.dry_run:
        for table, relative_path in TABLE_PATHS.items():
            print(f"Would load {raw_path / relative_path} into AVIATION_DEMO.OPS.{table}")
        return

    password = os.environ.get("SNOWFLAKE_PASSWORD")
    connection = snowflake.connector.connect(
        account=required_env("SNOWFLAKE_ACCOUNT"),
        user=required_env("SNOWFLAKE_USER"),
        password=password,
        authenticator=os.environ.get(
            "SNOWFLAKE_AUTHENTICATOR", "snowflake" if password else "externalbrowser"
        ),
        role=os.environ.get("SNOWFLAKE_ROLE", "ACCOUNTADMIN"),
        warehouse=os.environ.get("SNOWFLAKE_WAREHOUSE", "COMPUTE_WH"),
    )
    try:
        with connection.cursor() as cursor:
            for statement in ddl_path.read_text(encoding="utf-8").split(";"):
                if statement.strip():
                    cursor.execute(statement)

            for table, relative_path in TABLE_PATHS.items():
                frame = pd.read_parquet(raw_path / relative_path)
                if table == "BOOKING":
                    frame = frame.drop(columns=["year_month"], errors="ignore")
                frame.columns = [column.upper() for column in frame.columns]
                cursor.execute(f"TRUNCATE TABLE AVIATION_DEMO.OPS.{table}")
                success, chunks, rows, _ = write_pandas(
                    connection,
                    frame,
                    table_name=table,
                    database="AVIATION_DEMO",
                    schema="OPS",
                    quote_identifiers=False,
                    auto_create_table=False,
                    overwrite=False,
                    bulk_upload_chunks=True,
                )
                if not success or rows != len(frame):
                    raise RuntimeError(
                        f"{table}: expected {len(frame)} rows, loaded {rows} across {chunks} chunks"
                    )
                print(f"{table}: {rows:,} rows")
    finally:
        connection.close()


if __name__ == "__main__":
    main()
