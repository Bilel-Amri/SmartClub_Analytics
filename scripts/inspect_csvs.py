"""
Inspect all CSV files in the SoccerMon dataset folder.
Usage:
    python scripts/inspect_csvs.py data/raw/soccermon/subjective
"""
import sys
import os
import csv

def inspect_folder(root_path):
    csv_files = []
    for dirpath, _, filenames in os.walk(root_path):
        for fname in filenames:
            if fname.lower().endswith('.csv'):
                csv_files.append(os.path.join(dirpath, fname))

    if not csv_files:
        print(f"[WARNING] No CSV files found under: {root_path}")
        return

    csv_files.sort()
    print(f"Found {len(csv_files)} CSV file(s) under: {root_path}\n")
    print("=" * 80)

    for fpath in csv_files:
        rel = os.path.relpath(fpath, root_path)
        print(f"\nFile : {rel}")
        print(f"Full : {fpath}")
        try:
            with open(fpath, encoding='utf-8', errors='replace') as f:
                reader = csv.reader(f)
                rows = list(reader)

            if not rows:
                print("  [EMPTY FILE]")
                continue

            header = rows[0]
            data_rows = rows[1:]
            print(f"Rows : {len(data_rows):,} (excluding header)")
            print(f"Cols : {len(header)}")
            print(f"Columns: {header}")
            print("First 3 rows:")
            for i, row in enumerate(data_rows[:3], 1):
                print(f"  [{i}] {row}")
        except Exception as e:
            print(f"  [ERROR reading file: {e}]")

    print("\n" + "=" * 80)
    print("Inspection complete.")

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python scripts/inspect_csvs.py <path_to_folder>")
        sys.exit(1)
    inspect_folder(sys.argv[1])
