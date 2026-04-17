#!/usr/bin/env python3
"""
Quick test script to run the rental manager with actual data.
"""

import sys
from pathlib import Path

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

from rental_manager.core import RentalManager

def main():
    """Test the rental manager with actual data."""
    manager = RentalManager()

    try:
        # Load data from input directory
        input_dir = Path(__file__).parent / "input"
        bank_csv = input_dir / "combined_bank_transactions.csv"
        rental_csv = input_dir / "mieter_liste.csv"

        print("Loading data...")
        manager.load_data(bank_csv, rental_csv, None)
        print("✓ Data loaded successfully!")

        print("\nProcessing data...")
        manager.process_data()
        print("✓ Data processed successfully!")

        print("\nGenerating reports...")
        reports_dir = Path(__file__).parent / "reports"
        manager.generate_reports(reports_dir)
        print(f"✓ Reports generated in {reports_dir}")

        # Print summary
        tax_summary = manager.processed_data['tax_summary']
        print("\n" + "="*50)
        print("TAX SUMMARY (2025)")
        print("="*50)
        print(f"Total Rental Income: €{tax_summary['total_rental_income']:.2f}")
        print(f"Total Other Income: €{tax_summary['total_other_income']:.2f}")
        print(f"Total Income: €{tax_summary['total_income']:.2f}")
        print(f"Deductible Expenses: €{tax_summary['deductible_expenses']:.2f}")
        print(f"Bank Expenses: €{tax_summary['bank_expenses']:.2f}")
        print(f"Additional Costs: €{tax_summary['additional_costs']:.2f}")
        print(f"Taxable Income: €{tax_summary['taxable_income']:.2f}")

        print("\nTenant Summary:")
        for tenant, data in manager.processed_data['rental_summary']['tenant_summary'].items():
            print(f"  {tenant}: €{data['annual_rent']:.2f} annual rent")

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == '__main__':
    main()