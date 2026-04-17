"""
Command-line interface setup for the rental manager.
"""

import argparse
from pathlib import Path


def setup_cli_parser():
    """Set up the command-line argument parser."""
    parser = argparse.ArgumentParser(
        description="Rental Property Management CLI Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Load data from CSV files
  python rental_manager.py load-data --bank-csv ../input/SparkasseFürth_Kontoumsatz_2025_04-06.csv --rental-csv ../input/mieter_liste.csv --costs-csv ../input/cost_splits.csv

  # Process the loaded data
  python rental_manager.py process

  # Generate reports
  python rental_manager.py generate-reports --output-dir ./reports/

  # Display tenant reports in terminal
  python rental_manager.py show-tenants
  python rental_manager.py show-tenants --tenant "Gottwald"

  # Export processed data
  python rental_manager.py export --output-file summary.xlsx --format xlsx
        """
    )

    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    # Load data command
    load_parser = subparsers.add_parser('load-data', help='Load CSV data files')
    load_parser.add_argument('--bank-csv', required=True, type=Path,
                           help='Path to combined bank transactions CSV file')
    load_parser.add_argument('--rental-csv', required=True, type=Path,
                           help='Path to rental/tenant list CSV file')
    load_parser.add_argument('--costs-csv', type=Path,
                           help='Path to additional costs split CSV file (optional - will be generated from rental data if not provided)')

    # Process command
    process_parser = subparsers.add_parser('process', help='Process loaded data')

    # Generate reports command
    reports_parser = subparsers.add_parser('generate-reports', help='Generate tax reports and invoices')
    reports_parser.add_argument('--output-dir', type=Path, default=Path('./reports'),
                              help='Output directory for reports (default: ./reports)')

    # Export command
    export_parser = subparsers.add_parser('export', help='Export processed data')
    export_parser.add_argument('--output-file', required=True, type=Path,
                             help='Output file path')
    export_parser.add_argument('--format', choices=['csv', 'xlsx', 'json'], default='xlsx',
                             help='Export format (default: xlsx)')

    # Show tenant reports command
    show_parser = subparsers.add_parser('show-tenants', help='Display tenant reports in terminal')
    show_parser.add_argument('--tenant', type=str,
                           help='Specific tenant name to display (optional - shows all if not specified)')
    show_parser.add_argument('--reports-dir', type=Path, default=Path('./reports/invoices'),
                           help='Directory containing tenant report files (default: ./reports/invoices)')

    return parser