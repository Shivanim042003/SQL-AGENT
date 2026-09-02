import sys
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine


# Add project root to Python path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(PROJECT_ROOT))

from config import DATABASE_URL, RAW_DATA_DIR


CHUNK_SIZE = 10_000


# Date columns for each dataset file
DATE_COLUMNS = {
    "events": [
        "created_at",
    ],
    "inventory_items": [
        "created_at",
        "sold_at",
    ],
    "orders": [
        "created_at",
        "returned_at",
        "shipped_at",
        "delivered_at",
    ],
    "order_items": [
        "created_at",
        "shipped_at",
        "delivered_at",
        "returned_at",
    ],
    "users": [
        "created_at",
    ],
}


def convert_date_columns(df: pd.DataFrame, table_name: str) -> pd.DataFrame:
    """Convert configured date columns to datetime."""

    date_columns = DATE_COLUMNS.get(table_name, [])

    for column in date_columns:
        if column in df.columns:
            df[column] = pd.to_datetime(
                df[column],
                errors="coerce",
                utc=True
            )

    return df


def load_csv(file_path: Path, engine) -> None:
    """Load one CSV file into PostgreSQL in chunks."""

    table_name = file_path.stem

    print("\n" + "=" * 80)
    print(f"LOADING: {file_path.name}")
    print(f"TABLE: {table_name}")
    print("=" * 80)

    total_rows = 0
    first_chunk = True

    # Read the CSV in chunks to avoid loading large files
    # entirely into memory.
    for chunk in pd.read_csv(file_path, chunksize=CHUNK_SIZE):

        # Convert date columns before loading into PostgreSQL
        chunk = convert_date_columns(chunk, table_name)

        chunk.to_sql(
            name=table_name,
            con=engine,
            if_exists="replace" if first_chunk else "append",
            index=False,
            chunksize=CHUNK_SIZE
        )

        total_rows += len(chunk)
        first_chunk = False

        print(f"Loaded {total_rows:,} rows...", end="\r")

    print(f"\nSuccessfully loaded {total_rows:,} rows into '{table_name}'.")


def main() -> None:
    """Load all CSV files from the active dataset into PostgreSQL."""

    print("=" * 80)
    print("THELOOK DATASET LOADER")
    print("=" * 80)

    print(f"Dataset: {RAW_DATA_DIR.name}")
    print(f"Source:  {RAW_DATA_DIR}")

    csv_files = sorted(RAW_DATA_DIR.glob("*.csv"))

    if not csv_files:
        print("\nNo CSV files found.")
        return

    # Create PostgreSQL connection
    engine = create_engine(DATABASE_URL)

    try:
        print(f"\nFound {len(csv_files)} CSV files.")

        for file_path in csv_files:
            load_csv(file_path, engine)

        print("\n" + "=" * 80)
        print("DATA LOADING COMPLETE")
        print("=" * 80)

    finally:
        engine.dispose()
        print("\nDatabase connection closed.")


if __name__ == "__main__":
    main()