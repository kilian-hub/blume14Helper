# Rental Property Management CLI Tool

A command-line application to manage rental properties with multiple tenants, focusing on tax declaration and additional cost invoicing for German tax purposes (Anlage V).

## Features

- Load and process bank transaction data
- Track rental income from multiple tenants
- Split additional costs among tenants
- Generate tax summaries for German income tax declaration
- Create invoices for additional costs to tenants

## Installation

1. Install Python dependencies:
```bash
pip install -r requirements.txt
```

## Quick Start

To test with your actual data:

```bash
python test_with_data.py
```

This will:
1. Load data from `../input/` directory
2. Process bank transactions and tenant information
3. Generate tax reports and tenant invoices
4. Display a summary

### CSV File Formats

#### Bank Transactions CSV (`../input/SparkasseFürth_Kontoumsatz_*.csv`)
German bank format with semicolon separation:
```csv
Buchungstag;Valuta;Name Gegenkonto;Verwendungszweck;IBAN Gegenkonto;Betrag;Waehrung
30.06.2025;30.06.2025;INFRA FUERTH GMBH;KD.-NR. 1105861649 AB0964753103 17;DE31762500000000000067;-17.00;EUR
```

#### Rental/Tenant List CSV (`../input/mieter_liste.csv`)
```csv
Namen,Miete Januar,Miete neu,Änderungsdatum Miete,Nebenkosten Jan,Nebenkosten neu,Änderungsdatum Nebenkosten
Giasar,375,,2025.10.01,250,280,2025.10.01
Gottwald; Neumann,600,,,235,235,2025.10.01
```

#### Additional Costs Split CSV (optional)
If not provided, costs are generated from tenant Nebenkosten:
```csv
cost_type,total_amount,tenant,share
Heating,600.00,Tenant A,60
Water,300.00,Tenant A,50
```

### Commands

#### 1. Load Data
```bash
python rental_manager.py load-data \
  --bank-csv ../input/SparkasseFürth_Kontoumsatz_2025_04-06.csv \
  --rental-csv ../input/mieter_liste.csv \
  --costs-csv ../input/cost_splits.csv
```

#### 2. Process Data
```bash
python rental_manager.py process
```

#### 3. Generate Reports
```bash
python rental_manager.py generate-reports --output-dir ./reports/
```

This creates:
- `tax_summary.json`: Tax-relevant income and expense summary
- `invoices/`: Individual invoice files for each tenant

#### 4. Export Data
```bash
python rental_manager.py export --output-file summary.xlsx --format xlsx
```

Supported formats: `csv`, `xlsx`, `json`

## Tax Declaration Support

The tool calculates:
- Total rental income
- Deductible expenses (including additional costs)
- Taxable income for German Anlage V

Note: This is a simplified calculation. Consult a tax professional for actual tax advice.

## Development

The code is organized as follows:
- `rental_manager.py`: Main CLI entry point
- `rental_manager/core.py`: Core business logic
- `rental_manager/cli.py`: Command-line argument parsing