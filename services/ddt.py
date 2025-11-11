import duckdb
import pdfplumber
import os
import re
from dotenv import load_dotenv

load_dotenv()

# Constants
PDF_PATH = "/Users/nathan/Downloads/define.pdf"
DUCKDB_PATH = os.getenv("DATABASE_LOCATION")
PROTOCOL_ID = "CO-101-001"
TABLE_NAME = "ddt_clovis"

# Connect to DuckDB
conn = duckdb.connect(DUCKDB_PATH)

# Cleaning function to normalize cell contents
def clean_cell(cell):
    if not cell:
        return ""
    return re.sub(r"\s+", " ", cell).strip()

# Collect parsed rows
rows = []
current_row = None

with pdfplumber.open(PDF_PATH) as pdf:
    for page in pdf.pages[2:79]:
        table = page.extract_table()
        if not table:
            continue

        for row in table[2:]:
            if not row:
                continue

            # Clean and pad the row
            row = [clean_cell(cell) for cell in row]
            while len(row) < 8:
                row.append("")

            # Skip headers or structural rows
            if (
                row[0].lower().startswith("dataset") or
                row[1].lower().startswith("parameter identifier") or
                row[2].lower().startswith("variable name") or
                row[3].lower().startswith("variable label") or
                row[4].lower().startswith("variable type") or
                row[5].lower().startswith("display format") or
                row[6].lower().startswith("codelist/controlled terms") or row[6].lower().startswith("term") or
                row[7].lower().startswith("source or derivation")
            ):
                continue

            # Continuation row logic – treat any row lacking a new dataset + variable as a continuation
            if (not row[0] or not row[2]) and current_row:
                # Append any non-empty pieces to the corresponding fields of the current row
                if row[3]:
                    current_row[2] += " " + clean_cell(row[3])
                if row[4]:
                    current_row[3] += " " + clean_cell(row[4])
                if row[6]:
                    current_row[4] += " " + clean_cell(row[6])
                continue

            # New full data row
            if row[0] and row[2]:
                dataset_name = row[0]
                variable_name = row[2]
                variable_label = row[3]
                variable_type = row[4]
                source_or_derivation = row[7]

                current_row = [
                    dataset_name,
                    variable_name,
                    variable_label,
                    variable_type,
                    source_or_derivation,
                ]
                rows.append(current_row)

# Create the table
conn.execute(f"DROP TABLE IF EXISTS {TABLE_NAME}")
conn.execute(f"""
    CREATE TABLE {TABLE_NAME} (
        dataset_name VARCHAR,
        variable_name VARCHAR,
        variable_label VARCHAR,
        variable_type VARCHAR,
        source_or_derivation VARCHAR
    )
""")

# Insert cleaned data
conn.executemany(f"INSERT INTO {TABLE_NAME} VALUES (?, ?, ?, ?, ?)", rows)

print(f"✅ Loaded {len(rows)} rows into `{TABLE_NAME}` with protocol_id = '{PROTOCOL_ID}'")
