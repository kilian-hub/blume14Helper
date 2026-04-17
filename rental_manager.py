#!/usr/bin/env python3
"""
Rental Property Management CLI Tool

A command-line application to manage rental properties with multiple tenants,
focusing on tax declaration and additional cost invoicing.

Usage:
    python rental_manager.py [command] [options]

Commands:
    load-data    Load and validate CSV data files
    process      Process transactions and calculate splits
    generate-reports  Generate tax reports and invoices
    export       Export processed data
"""

import argparse
import sys
from pathlib import Path

# Add current directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from rental_manager.core import RentalManager
from rental_manager.cli import setup_cli_parser


def main():
    """Main entry point for the rental property management CLI."""
    parser = setup_cli_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    # Initialize the rental manager
    manager = RentalManager()

    # Execute the requested command
    try:
        if args.command == 'load-data':
            manager.load_data(args.bank_csv, args.rental_csv, args.costs_csv if hasattr(args, 'costs_csv') and args.costs_csv else None)
            print("Data loaded successfully!")

        elif args.command == 'process':
            manager.process_data()
            print("Data processed successfully!")

        elif args.command == 'generate-reports':
            manager.generate_reports(args.output_dir)
            print(f"Reports generated in {args.output_dir}")

        elif args.command == 'export':
            manager.export_data(args.output_file, args.format)
            print(f"Data exported to {args.output_file}")

        elif args.command == 'show-tenants':
            manager.display_tenant_reports(args.reports_dir, args.tenant if hasattr(args, 'tenant') else None)

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()