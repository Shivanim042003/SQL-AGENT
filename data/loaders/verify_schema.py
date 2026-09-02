import sys
from pathlib import Path

import pandas as pd


# Add project root to Python path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(PROJECT_ROOT))

from config import RAW_DATA_DIR


def check_ids() -> None:
    """Check uniqueness and null values for likely primary keys."""

    checks = {
        "distribution_centers.csv": "id",
        "users.csv": "id",
        "products.csv": "id",
        "inventory_items.csv": "id",
        "orders.csv": "order_id",
        "order_items.csv": "id",
        "events.csv": "id",
    }

    print("\n" + "=" * 80)
    print("PRIMARY KEY CHECKS")
    print("=" * 80)

    for filename, column in checks.items():

        file_path = RAW_DATA_DIR / filename

        df = pd.read_csv(
            file_path,
            usecols=[column],
        )

        total_rows = len(df)
        null_count = df[column].isna().sum()
        duplicate_count = df[column].duplicated().sum()

        print(f"\n{filename}")
        print(f"  Rows:       {total_rows}")
        print(f"  Null IDs:   {null_count}")
        print(f"  Duplicates: {duplicate_count}")


def check_date_columns() -> None:
    """Inspect non-null values from important date columns."""

    checks = {
        "orders.csv": [
            "created_at",
            "returned_at",
            "shipped_at",
            "delivered_at",
        ],
        "order_items.csv": [
            "created_at",
            "shipped_at",
            "delivered_at",
            "returned_at",
        ],
    }

    print("\n" + "=" * 80)
    print("DATE COLUMN CHECKS")
    print("=" * 80)

    for filename, columns in checks.items():

        print(f"\n{filename}")

        df = pd.read_csv(
            RAW_DATA_DIR / filename,
            usecols=columns,
        )

        for column in columns:

            non_null = df[column].dropna()

            print(f"\n  {column}")

            if non_null.empty:
                print("    No non-null values")
            else:
                print(f"    Non-null count: {len(non_null)}")
                print(f"    Sample: {non_null.iloc[0]}")


def main() -> None:

    check_ids()
    check_date_columns()

    print("\n" + "=" * 80)
    print("SCHEMA VERIFICATION COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    main()