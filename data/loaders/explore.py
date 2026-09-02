import sys
from pathlib import Path

import pandas as pd


# Add project root to Python path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(PROJECT_ROOT))

from config import RAW_DATA_DIR


CHUNK_SIZE = 100_000


def explore_csv(file_path: Path) -> None:
    """Print useful information about one CSV file."""

    print("\n" + "=" * 80)
    print(f"FILE: {file_path.name}")
    print("=" * 80)

    total_rows = 0
    null_counts = None
    sample_df = None
    dtypes = None

    # Read the CSV in chunks
    for chunk in pd.read_csv(file_path, chunksize=CHUNK_SIZE):

        # Save schema information from the first chunk
        if dtypes is None:
            dtypes = chunk.dtypes
            sample_df = chunk.head(3)

        # Count rows
        total_rows += len(chunk)

        # Count missing values
        chunk_nulls = chunk.isnull().sum()

        if null_counts is None:
            null_counts = chunk_nulls
        else:
            null_counts += chunk_nulls

    print(f"\nRows: {total_rows}")
    print(f"Columns: {len(dtypes)}")

    # Column names
    print("\nCOLUMN NAMES:")
    for column in dtypes.index:
        print(f"  - {column}")

    # Data types
    print("\nDATA TYPES:")
    print(dtypes)

    # Missing values
    print("\nMISSING VALUES:")

    null_pct = (null_counts / total_rows * 100).round(2)

    has_missing = False

    for column in null_counts.index:
        if null_counts[column] > 0:
            has_missing = True
            print(
                f"  {column}: "
                f"{null_counts[column]} "
                f"({null_pct[column]}%)"
            )

    if not has_missing:
        print("  (no missing values)")

    # Sample data
    print("\nSAMPLE DATA:")
    print(sample_df.to_string(index=False))


def main() -> None:
    """Explore all CSV files in the active dataset."""

    print("=" * 80)
    print(f"EXPLORING DATASET: {RAW_DATA_DIR.name}")
    print(f"LOCATION: {RAW_DATA_DIR}")
    print("=" * 80)

    csv_files = sorted(RAW_DATA_DIR.glob("*.csv"))

    if not csv_files:
        print("\nNo CSV files found.")
        return

    for file_path in csv_files:
        explore_csv(file_path)

    print("\n" + "=" * 80)
    print("DATASET EXPLORATION COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    main()