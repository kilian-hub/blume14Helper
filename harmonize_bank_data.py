#!/usr/bin/env python3
"""
Script to read, harmonize and combine the three bank transaction CSV files.
"""

import pandas as pd
from pathlib import Path
import sys

def load_bank_file(bank_csv: Path) -> pd.DataFrame:
    """Load a single bank CSV file, handling different formats."""
    print(f"Loading {bank_csv.name}...")

    try:
        # Read first few lines to detect format
        with open(bank_csv, 'r', encoding='utf-8') as f:
            first_line = f.readline().strip()
        
        print(f"  First line: '{first_line}'")
        
        # Detect C24 format (contains "Transaktionstyp")
        if 'Transaktionstyp' in first_line:
            print("  Detected C24 format")
            # C24 format: comma separated, German decimal format
            df = pd.read_csv(bank_csv, sep=',', encoding='utf-8', decimal=',')
            print(f"  Read {len(df)} rows")

            # Rename columns to standard format
            c24_mapping = {
                'Buchungsdatum': 'date',
                'Betrag': 'amount',
                'Zahlungsempfänger': 'counterparty',
                'Verwendungszweck': 'description',
                'IBAN': 'iban'
            }
            df = df.rename(columns=c24_mapping)

            # Convert amount from string with € symbol
            if 'amount' in df.columns:
                df['amount'] = df['amount'].str.replace(' €', '').str.replace('.', '').str.replace(',', '.').astype(float)

        # Detect Sparkasse format (starts with "Buchungstag" or "Datum")
        elif first_line.startswith('Buchungstag') or first_line.startswith('Datum'):
            print("  Detected Sparkasse format")
            # Sparkasse format: semicolon separated
            df = pd.read_csv(bank_csv, sep=';', encoding='utf-8', decimal=',')
            print(f"  Read {len(df)} rows")
            
            # Strip whitespace from column names
            df.columns = df.columns.str.strip()
            
            # Handle different column names
            sparkasse_mapping = {
                'Buchungstag': 'date',
                'Datum': 'date',
                'Valuta': 'value_date',
                'Name Gegenkonto': 'counterparty',
                'Empfänger/Auftraggeber': 'counterparty',
                'Verwendungszweck': 'description',
                'IBAN Gegenkonto': 'iban',
                'Betrag': 'amount',
                'Waehrung': 'currency',
                'Währung': 'currency'
            }
            df = df.rename(columns=sparkasse_mapping)
        else:
            print(f"  Unknown format - first line: '{first_line}'")
            raise ValueError(f"Unknown bank CSV format in file: {bank_csv}")

        # Ensure required columns exist
        required_cols = ['date', 'amount', 'description']
        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            print(f"  Available columns: {list(df.columns)}")
            raise ValueError(f"Bank CSV {bank_csv} missing required columns: {missing_cols}")

        # Add source file info for debugging
        df['source_file'] = bank_csv.name

        print(f"  Loaded {len(df)} transactions")
        return df
        
    except Exception as e:
        print(f"  Error in load_bank_file: {e}")
        import traceback
        traceback.print_exc()
        return None
def main():
    """Main function to load and harmonize bank data."""
    input_dir = Path("input")  # Changed from "../input" to "input"

    # List of bank files
    bank_files = [
        input_dir / "C24_kontoumsatz_2025.csv",
        input_dir / "SparkasseFürth_Kontoumsatz_2024_12-2025_03.csv",
        input_dir / "SparkasseFürth_Kontoumsatz_2025_04-06.csv"
    ]

    # Load and combine all bank data
    bank_data_frames = []

    for bank_file in bank_files:
        if bank_file.exists():
            try:
                df = load_bank_file(bank_file)
                print(f"  DataFrame shape: {df.shape}")
                print(f"  Columns: {list(df.columns)}")
                bank_data_frames.append(df)
            except Exception as e:
                print(f"Error loading {bank_file}: {e}")
        else:
            print(f"File not found: {bank_file}")

    print(f"\nLoaded {len(bank_data_frames)} dataframes")

    # Combine all dataframes
    if bank_data_frames:
        combined_df = pd.concat(bank_data_frames, ignore_index=True)

        # Sort by date
        if 'date' in combined_df.columns:
            try:
                # Strip whitespace from date strings before parsing
                combined_df['date'] = combined_df['date'].astype(str).str.strip()
                combined_df['date'] = pd.to_datetime(combined_df['date'], format='%d.%m.%Y', errors='coerce')
                combined_df = combined_df.sort_values('date').reset_index(drop=True)
            except Exception as e:
                print(f"Warning: Could not parse dates: {e}, keeping original order")

        print(f"\nCombined dataframe shape: {combined_df.shape}")
        print(f"Date range: {combined_df['date'].min()} to {combined_df['date'].max()}")
        print(f"Total transactions: {len(combined_df)}")

        # Show summary by source file
        print("\nTransactions by source file:")
        print(combined_df['source_file'].value_counts())

        # Show sample data
        print("\nSample of combined data:")
        print(combined_df[['date', 'amount', 'counterparty', 'description', 'source_file']].head(10))

        # Save combined data
        output_file = input_dir / "combined_bank_transactions.csv"
        combined_df.to_csv(output_file, index=False, sep=';', decimal=',', encoding='utf-8')
        print(f"\nSaved combined data to: {output_file}")

        return combined_df
    else:
        print("No data could be loaded")
        return None

if __name__ == '__main__':
    main()