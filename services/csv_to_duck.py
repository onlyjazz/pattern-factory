import duckdb
import os
from dotenv import load_dotenv

load_dotenv()

# Configuration
csv_dir = "/Users/nathan/clinical-trial-data-review/csv_from_sas/clovis"
duckdb_path = os.getenv("DATABASE_LOCATION")
protocol_id = "CO-101-001"

# Connect to DuckDB
conn = duckdb.connect(duckdb_path)

# Get all CSV files
csv_files = [f for f in os.listdir(csv_dir) if f.endswith(".csv")]

for file in csv_files:
    table_base = os.path.splitext(file)[0].lower()
    table_name = f"{table_base}_clovis"
    crf = os.path.splitext(file)[0].upper()
    csv_path = os.path.join(csv_dir, file)

    print(f"Processing {file} → {table_name}")

    try:
        # Drop table if it already exists
        conn.execute(f"DROP TABLE IF EXISTS {table_name}")

        # Create the table from CSV
        conn.execute(f"""
            CREATE TABLE {table_name} AS 
            SELECT *, '{crf}' AS crf,
            FROM read_csv_auto('{csv_path}', HEADER=TRUE)
        """)

        print(f"✅ Successfully loaded {file} into {table_name}")
    except Exception as e:
        print(f"❌ Error processing {file}: {e}")
