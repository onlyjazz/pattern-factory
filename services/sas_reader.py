from sas7bdat import SAS7BDAT
import pandas as pd
import os

# Prompt user for input and output directories
input_dir = input("Enter the path to the input directory with .sas7bdat files: ").strip()
output_dir = input("Enter the path to the output directory for CSV files: ").strip()

# Expand ~ and create output directory if it doesn't exist
input_dir = os.path.expanduser(input_dir)
output_dir = os.path.expanduser(output_dir)
os.makedirs(output_dir, exist_ok=True)

# Loop through all files in the input directory
for file_name in os.listdir(input_dir):
    if file_name.lower().endswith(".sas7bdat"):
        sas_path = os.path.join(input_dir, file_name)
        csv_path = os.path.join(output_dir, file_name.replace(".sas7bdat", ".csv"))
    try:
        try:
            df = pd.read_sas(sas_path, format='sas7bdat', encoding='utf-8')
        except UnicodeDecodeError:
            df = pd.read_sas(sas_path, format='sas7bdat', encoding='latin1')
        df.to_csv(csv_path, index=False)
        print(f"Converted: {file_name} → {csv_path}")
    except Exception as e:
        print(f"Failed to convert {file_name}: {e}")