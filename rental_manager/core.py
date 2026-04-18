"""
Core rental property management functionality.
"""

import pandas as pd
from pathlib import Path
from typing import Optional, Dict, List
import json
from datetime import datetime


class RentalManager:
    """Main class for managing rental property data and operations."""

    def __init__(self):
        self.bank_data: Optional[pd.DataFrame] = None
        self.rental_data: Optional[pd.DataFrame] = None
        self.costs_data: Optional[pd.DataFrame] = None
        self.processed_data: Optional[Dict] = None

    def load_data(self, bank_csv: Path, rental_csv: Path, costs_csv: Optional[Path]):
        """Load CSV data files."""
        try:
            # Load combined bank data (already harmonized)
            self.bank_data = pd.read_csv(bank_csv, sep=';', encoding='utf-8', decimal=',')
            
            # Ensure amount column is numeric
            if 'amount' in self.bank_data.columns:
                self.bank_data['amount'] = pd.to_numeric(self.bank_data['amount'], errors='coerce')
            
            # Ensure date column is parsed correctly
            if 'date' in self.bank_data.columns:
                try:
                    self.bank_data['date'] = pd.to_datetime(self.bank_data['date'], format='%Y-%m-%d', errors='coerce')
                except:
                    self.bank_data['date'] = pd.to_datetime(self.bank_data['date'], format='%d.%m.%Y', errors='coerce')

            # Load rental/tenant data
            self.rental_data = pd.read_csv(rental_csv, sep=',', encoding='utf-8')
            self.rental_data.columns = self.rental_data.columns.str.strip()
            
            # Convert numeric columns in rental data
            numeric_cols = ['Miete Januar', 'Miete neu', 'Nebenkosten Jan', 'Nebenkosten neu']
            for col in numeric_cols:
                if col in self.rental_data.columns:
                    self.rental_data[col] = pd.to_numeric(self.rental_data[col], errors='coerce')

            # Load costs data (if exists, otherwise create from rental data)
            if costs_csv and costs_csv.exists():
                self.costs_data = pd.read_csv(costs_csv, sep=',', encoding='utf-8')
            else:
                self.costs_data = self._generate_costs_from_rental_data()

            self._validate_data()

        except FileNotFoundError as e:
            raise ValueError(f"File not found: {e.filename}")
        except pd.errors.EmptyDataError:
            raise ValueError("One or more CSV files are empty")
        except Exception as e:
            raise ValueError(f"Error loading CSV files: {e}")

    def _validate_data(self):
        """Validate loaded data structure."""
        required_bank_cols = ['date', 'amount', 'description']
        if not all(col in self.bank_data.columns for col in required_bank_cols):
            raise ValueError(f"Bank CSV missing required columns: {required_bank_cols}")

        if 'Namen' not in self.rental_data.columns:
            raise ValueError("Rental CSV missing 'Namen' column")

        required_costs_cols = ['cost_type', 'total_amount', 'tenant', 'share']
        if not all(col in self.costs_data.columns for col in required_costs_cols):
            raise ValueError(f"Costs CSV missing required columns: {required_costs_cols}")

    def _get_change_month(self, change_date_str: str) -> int:
        """Extract month from change date string (format: YYYY.MM.DD)."""
        if pd.isna(change_date_str) or not change_date_str or str(change_date_str).strip() == '':
            return 13  # No change = use initial amount all year
        try:
            change_date_str = str(change_date_str).strip()
            parts = change_date_str.split('.')
            if len(parts) >= 2:
                return int(parts[1])
        except:
            pass
        return 13

    def _calculate_annual_amount(self, amount_jan: float, amount_neu: float, change_date_str: str) -> float:
        """Calculate annual amount considering mid-year changes."""
        if pd.isna(amount_jan):
            amount_jan = 0
        if pd.isna(amount_neu):
            amount_neu = 0
        
        amount_jan = float(amount_jan)
        amount_neu = float(amount_neu)
        
        change_month = self._get_change_month(change_date_str)
        
        if change_month > 12:
            return amount_jan * 12
        
        if change_month <= 1:
            return amount_neu * 12 if amount_neu > 0 else amount_jan * 12
        
        months_initial = change_month - 1
        months_new = 12 - months_initial
        
        return (amount_jan * months_initial) + (amount_neu * months_new if amount_neu > 0 else amount_jan * months_new)

    def _generate_costs_from_rental_data(self) -> pd.DataFrame:
        """Generate costs data from rental tenant data with support for mid-year changes."""
        costs_rows = []

        for _, row in self.rental_data.iterrows():
            tenant_name = row['Namen'].strip()
            nebenkosten_jan = row.get('Nebenkosten Jan', 0)
            nebenkosten_neu = row.get('Nebenkosten neu', 0)
            change_date_str = row.get('Änderungsdatum Nebenkosten', '')

            total_annual_cost = self._calculate_annual_amount(
                nebenkosten_jan, nebenkosten_neu, change_date_str
            )

            if total_annual_cost > 0:
                costs_rows.append({
                    'cost_type': 'Nebenkosten',
                    'total_amount': total_annual_cost,
                    'tenant': tenant_name,
                    'share': 100.0
                })

        if costs_rows:
            return pd.DataFrame(costs_rows)
        else:
            return pd.DataFrame(columns=['cost_type', 'total_amount', 'tenant', 'share'])

    def process_data(self):
        """Process the loaded data to calculate summaries and splits."""
        if any(data is None for data in [self.bank_data, self.rental_data, self.costs_data]):
            raise ValueError("Data must be loaded before processing")

        self.processed_data = {}
        self.processed_data['bank_summary'] = self._process_bank_data()
        self.processed_data['rental_summary'] = self._process_rental_data()
        self.processed_data['cost_splits'] = self._process_costs_data()
        self.processed_data['tax_summary'] = self._calculate_tax_summary()

    def _process_bank_data(self) -> Dict:
        """Process bank transaction data."""
        def categorize_transaction(row):
            desc = str(row['description']).lower()
            counterparty = str(row.get('counterparty', '')).lower()
            amount = row['amount']

            if ('nebenkosten abrechnung' in desc or 'nachzahlung' in desc) and amount > 0:
                return 'special_settlement'

            if 'miete' in desc or any(name.lower() in counterparty for name in self.rental_data['Namen'].str.lower()):
                return 'rental_income'
            elif amount < 0:
                if 'infra' in counterparty or 'gmbh' in counterparty:
                    return 'utilities'
                elif 'bundesagentur' in counterparty:
                    return 'benefits'
                elif 'miete' in desc:
                    return 'rent_payment'
                else:
                    return 'other_expense'
            else:
                return 'other_income'

        self.bank_data['category'] = self.bank_data.apply(categorize_transaction, axis=1)

        rental_income = self.bank_data[
            (self.bank_data['category'] == 'rental_income') & (self.bank_data['amount'] > 0)
        ]['amount'].sum()

        expenses = self.bank_data[self.bank_data['amount'] < 0]['amount'].abs().sum()
        other_income = self.bank_data[
            (self.bank_data['category'] == 'other_income') & (self.bank_data['amount'] > 0)
        ]['amount'].sum()

        return {
            'total_rental_income': float(rental_income),
            'total_expenses': float(expenses),
            'total_other_income': float(other_income),
            'net_flow': float(rental_income + other_income - expenses),
            'transaction_count': len(self.bank_data),
            'categories': self.bank_data['category'].value_counts().to_dict()
        }

    def _process_rental_data(self) -> Dict:
        """Process rental fee data with support for mid-year changes."""
        rental_rows = []

        for _, row in self.rental_data.iterrows():
            tenant_name = row['Namen'].strip()
            miete_jan = row.get('Miete Januar', 0)
            miete_neu = row.get('Miete neu', 0)
            change_date_str = row.get('Änderungsdatum Miete', '')

            change_month = self._get_change_month(change_date_str)
            
            for month in range(1, 13):
                if month < change_month:
                    amount = float(miete_jan) if pd.notna(miete_jan) and miete_jan > 0 else 0
                else:
                    if pd.notna(miete_neu) and miete_neu > 0:
                        amount = float(miete_neu)
                    else:
                        amount = float(miete_jan) if pd.notna(miete_jan) and miete_jan > 0 else 0
                
                if amount > 0:
                    rental_rows.append({
                        'tenant': tenant_name,
                        'amount': amount,
                        'period': f"2025-{month:02d}"
                    })

        if rental_rows:
            processed_rental_df = pd.DataFrame(rental_rows)
            total_rental_income = processed_rental_df['amount'].sum()
            tenants = processed_rental_df['tenant'].unique().tolist()

            tenant_summary = {}
            for tenant in tenants:
                tenant_data = processed_rental_df[processed_rental_df['tenant'] == tenant]
                tenant_summary[tenant] = {
                    'monthly_rent': float(tenant_data['amount'].iloc[0] if not tenant_data.empty else 0),
                    'annual_rent': float(tenant_data['amount'].sum()),
                    'payments': len(tenant_data)
                }
        else:
            total_rental_income = 0
            tenants = []
            tenant_summary = {}

        return {
            'total_rental_income': float(total_rental_income),
            'tenants': tenants,
            'tenant_summary': tenant_summary
        }

    def _process_costs_data(self) -> Dict:
        """Process additional costs split data."""
        cost_types = self.costs_data['cost_type'].unique().tolist()

        cost_summary = {}
        for cost_type in cost_types:
            cost_data = self.costs_data[self.costs_data['cost_type'] == cost_type]
            
            tenant_shares = {}
            total_cost = 0
            
            for _, row in cost_data.iterrows():
                tenant = row['tenant']
                amount = float(row['total_amount'])
                share = float(row['share'])
                
                if share == 100.0:
                    # Per-tenant cost (like individual Nebenkosten)
                    tenant_shares[tenant] = {
                        'share_percent': 100.0,
                        'amount': amount
                    }
                    total_cost += amount
                else:
                    # Shared cost
                    if not tenant_shares:
                        total_cost = amount
                    amount_for_tenant = amount * (share / 100)
                    tenant_shares[tenant] = {
                        'share_percent': share,
                        'amount': amount_for_tenant
                    }

            cost_summary[cost_type] = {
                'total_amount': float(total_cost),
                'tenant_shares': tenant_shares
            }

        return cost_summary

    def _calculate_tax_summary(self) -> Dict:
        """Calculate tax-relevant summaries."""
        rental_income = self.processed_data['bank_summary']['total_rental_income']
        other_income = self.processed_data['bank_summary']['total_other_income']
        bank_expenses = self.processed_data['bank_summary']['total_expenses']

        additional_costs = 0
        for cost_type, cost_info in self.processed_data['cost_splits'].items():
            if isinstance(cost_info, dict) and 'total_amount' in cost_info:
                additional_costs += cost_info['total_amount']

        total_income = rental_income + other_income
        deductible_expenses = bank_expenses + additional_costs

        taxable_income = max(0, total_income - deductible_expenses)

        return {
            'total_rental_income': float(rental_income),
            'total_other_income': float(other_income),
            'total_income': float(total_income),
            'deductible_expenses': float(deductible_expenses),
            'bank_expenses': float(bank_expenses),
            'additional_costs': float(additional_costs),
            'taxable_income': float(taxable_income),
            'tax_year': 2025
        }

    def generate_reports(self, output_dir: Path):
        """Generate tax reports and invoices."""
        if self.processed_data is None:
            raise ValueError("Data must be processed before generating reports")

        output_dir.mkdir(exist_ok=True)
        self._generate_tax_report(output_dir / 'tax_summary.json')
        self._generate_tenant_invoices(output_dir)
        self._generate_detailed_reports(output_dir)

    def _generate_tax_report(self, output_file: Path):
        """Generate tax summary report."""
        tax_data = self.processed_data['tax_summary']
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(tax_data, f, indent=2, default=str)

    def _get_expected_monthly(self, tenant: str) -> Dict:
        """Get expected monthly rent and Nebenkosten for a tenant, per month."""
        row = self.rental_data[self.rental_data['Namen'].str.strip() == tenant].iloc[0]

        miete_jan = float(row.get('Miete Januar', 0) or 0)
        miete_neu = float(row.get('Miete neu', 0) or 0) if pd.notna(row.get('Miete neu', 0)) else 0
        miete_change = self._get_change_month(row.get('Änderungsdatum Miete', ''))

        nk_jan = float(row.get('Nebenkosten Jan', 0) or 0)
        nk_neu = float(row.get('Nebenkosten neu', 0) or 0) if pd.notna(row.get('Nebenkosten neu', 0)) else 0
        nk_change = self._get_change_month(row.get('Änderungsdatum Nebenkosten', ''))

        monthly = {}
        for m in range(1, 13):
            rent = miete_neu if (m >= miete_change and miete_neu > 0) else miete_jan
            nk = nk_neu if (m >= nk_change and nk_neu > 0) else nk_jan
            monthly[m] = {'rent': rent, 'nebenkosten': nk}
        return monthly

    def _classify_payment(self, amount: float, expected_rent: float, expected_nk: float) -> Dict:
        """Classify a single payment as Miete, Nebenkosten, combined, or other."""
        tolerance = 30.0  # €30 tolerance for matching
        combined = expected_rent + expected_nk

        # Check Nebenkosten only
        if expected_nk > 0 and abs(amount - expected_nk) <= tolerance:
            return {'miete': 0, 'nebenkosten': amount, 'other': 0, 'nk_abrechnung': 0, 'category': 'Nebenkosten'}

        # Check rent only
        if expected_rent > 0 and abs(amount - expected_rent) <= tolerance:
            return {'miete': amount, 'nebenkosten': 0, 'other': 0, 'nk_abrechnung': 0, 'category': 'Miete'}

        # Check combined rent + Nebenkosten
        if combined > 0 and abs(amount - combined) <= tolerance:
            return {'miete': expected_rent, 'nebenkosten': amount - expected_rent, 'other': 0, 'nk_abrechnung': 0, 'category': 'Miete + Nebenkosten'}

        # Check if it's roughly a multiple (e.g. 2 months combined)
        if combined > 0 and abs(amount - 2 * combined) <= tolerance:
            return {'miete': 2 * expected_rent, 'nebenkosten': amount - 2 * expected_rent, 'other': 0, 'nk_abrechnung': 0, 'category': '2x Miete + Nebenkosten'}

        return None  # Could not classify individually

    def _is_nk_settlement(self, description: str, amount: float, expected_rent: float, expected_nk: float) -> bool:
        """Check if a transaction indicates a Nebenkosten settlement.
        
        Uses description keywords and amount patterns (non-round amounts
        that don't match expected rent/NK/combined are likely settlements).
        """
        desc = description.lower()
        settlement_keywords = [
            'abrechnung',
            'nachzahlung',
            'rückzahlung',
            'gutschrift nebenkost',
            'nk-abrechnung',
            'nk abrechnung',
        ]
        nk_keywords = ['nebenkost', 'nebenk']
        has_settlement = any(kw in desc for kw in settlement_keywords)
        has_nk = any(kw in desc for kw in nk_keywords)

        # Explicit settlement keywords + NK keyword
        if 'nebenkostenabrechnung' in desc or 'nebenkosten abrechnung' in desc:
            return True
        if 'nachzahlung' in desc and has_nk:
            return True
        if has_settlement and has_nk:
            return True

        # Non-round amount (has cents) → always a settlement
        # Regular rent/NK payments are always whole euro amounts
        is_uneven = round(amount % 1, 2) != 0
        if is_uneven:
            return True

        return False

    def _classify_month_payments(self, month_txns: List[Dict], expected_rent: float, expected_nk: float) -> List[Dict]:
        """Classify a group of transactions for one month, considering multi-payment patterns."""
        combined = expected_rent + expected_nk

        # First pass: separate out NK settlements by description
        results = []
        regular_txns = []
        for txn in month_txns:
            if self._is_nk_settlement(txn['description'], txn['amount'], expected_rent, expected_nk):
                txn.update({
                    'miete': 0, 'nebenkosten': 0, 'other': 0,
                    'nk_abrechnung': txn['amount'],
                    'category': 'NK-Abrechnung'
                })
                results.append(txn)
            else:
                regular_txns.append(txn)

        # Second pass: classify regular payments individually
        unclassified = []
        for txn in regular_txns:
            classified = self._classify_payment(txn['amount'], expected_rent, expected_nk)
            if classified is not None:
                txn.update(classified)
                results.append(txn)
            else:
                unclassified.append(txn)

        if not unclassified:
            return results

        # Use defined rent/NK amounts to distribute unclassified payments.
        # Detect if multiple months' payments arrived in the same calendar month
        total_regular = sum(t['amount'] for t in regular_txns)
        if combined > 0:
            months_factor = max(1, round(total_regular / combined))
        else:
            months_factor = 1

        # Calculate how much Miete/NK is already covered by classified payments.
        classified_miete = sum(t.get('miete', 0) for t in results if t.get('category') != 'NK-Abrechnung')
        classified_nk = sum(t.get('nebenkosten', 0) for t in results if t.get('category') != 'NK-Abrechnung')

        remaining_rent = max(0, expected_rent * months_factor - classified_miete)
        remaining_nk = max(0, expected_nk * months_factor - classified_nk)

        # Sort descending — larger payments fill rent first
        unclassified.sort(key=lambda t: t['amount'], reverse=True)

        for txn in unclassified:
            amt = txn['amount']
            if expected_nk == 0:
                # No Nebenkosten expected — entire amount is Miete
                miete = min(remaining_rent, amt)
                remaining_rent -= miete
            elif remaining_rent > 0 and amt > expected_nk:
                # Cap rent per payment at the defined monthly rent
                miete = min(expected_rent, remaining_rent, amt)
                remaining_rent -= miete
            else:
                miete = 0
            nk = amt - miete
            if nk > 0:
                remaining_nk = max(0, remaining_nk - nk)

            if miete > 0 and nk > 0:
                cat = 'Miete + Nebenkosten'
            elif miete > 0:
                cat = 'Miete'
            else:
                cat = 'Nebenkosten'
            txn.update({'miete': miete, 'nebenkosten': nk, 'other': 0, 'nk_abrechnung': 0, 'category': cat})

        results.extend(unclassified)
        return results

    def _assign_pair(self, txns: List[Dict], expected_rent: float, expected_nk: float):
        """For two unclassified payments that sum to rent+NK, assign the best match."""
        # Sort by amount descending — larger is likely rent
        txns.sort(key=lambda t: t['amount'], reverse=True)

        # Try all assignments, pick the one with smallest total error
        best_error = float('inf')
        best_assignment = None
        for i, txn in enumerate(txns):
            # Try this one as rent
            remaining = sum(t['amount'] for t in txns) - txn['amount']
            error = abs(txn['amount'] - expected_rent) + abs(remaining - expected_nk)
            if error < best_error:
                best_error = error
                best_assignment = i

        if best_assignment is not None:
            for i, txn in enumerate(txns):
                if i == best_assignment:
                    txn.update({'miete': txn['amount'], 'nebenkosten': 0, 'other': 0, 'nk_abrechnung': 0, 'category': 'Miete'})
                else:
                    txn.update({'miete': 0, 'nebenkosten': txn['amount'], 'other': 0, 'nk_abrechnung': 0, 'category': 'Nebenkosten'})

    def _get_tenant_payments(self, tenant: str) -> Dict:
        """Get actual payments from bank data for a specific tenant, classified."""
        bank = self.bank_data
        name_parts = [p.strip().lower() for p in tenant.split(';')]

        # Normalize ß→ss for matching
        def normalize(s):
            return s.replace('ß', 'ss')

        desc_norm = bank['description'].str.lower().apply(lambda x: normalize(x) if isinstance(x, str) else '')
        cp_norm = bank['counterparty'].str.lower().apply(lambda x: normalize(x) if isinstance(x, str) else '') if 'counterparty' in bank.columns else None

        mask = pd.Series(False, index=bank.index)
        for part in name_parts:
            part_norm = normalize(part)
            mask |= desc_norm.str.contains(part_norm, na=False)
            if cp_norm is not None:
                mask |= cp_norm.str.contains(part_norm, na=False)

        tenant_txns = bank[mask].copy()
        incoming = tenant_txns[tenant_txns['amount'] > 0]

        # Filter to 2025 only
        incoming = incoming[incoming['date'].astype(str).str[:4] == '2025']

        expected = self._get_expected_monthly(tenant)

        # Group transactions by month
        from collections import defaultdict
        monthly_txns = defaultdict(list)
        for _, row in incoming.iterrows():
            date_str = str(row['date'])[:10]
            amount = float(row['amount'])
            desc = str(row['description']).strip()
            month_key = date_str[:7]  # YYYY-MM
            monthly_txns[month_key].append({
                'date': date_str,
                'amount': amount,
                'description': desc
            })

        # Classify each month's payments together
        all_transactions = []
        total_miete = 0
        total_nk = 0
        total_nk_abrechnung = 0
        total_other = 0

        for month_key in sorted(monthly_txns.keys()):
            txns = monthly_txns[month_key]
            try:
                month_num = int(month_key[5:7])
            except (ValueError, IndexError):
                month_num = 1
            month_num = max(1, min(12, month_num))

            exp = expected[month_num]
            classified = self._classify_month_payments(txns, exp['rent'], exp['nebenkosten'])

            for txn in classified:
                total_miete += txn.get('miete', 0)
                total_nk += txn.get('nebenkosten', 0)
                total_nk_abrechnung += txn.get('nk_abrechnung', 0)
                total_other += txn.get('other', 0)
                all_transactions.append(txn)

        all_transactions.sort(key=lambda t: t['date'])

        return {
            'total_received': float(incoming['amount'].sum()),
            'total_miete': total_miete,
            'total_nebenkosten': total_nk,
            'total_nk_abrechnung': total_nk_abrechnung,
            'total_other': total_other,
            'transaction_count': len(incoming),
            'transactions': all_transactions
        }

    def _generate_tenant_invoices(self, output_dir: Path):
        """Generate invoices for each tenant."""
        invoices_dir = output_dir / 'tenant_invoices'
        invoices_dir.mkdir(exist_ok=True)

        rental_summary = self.processed_data['rental_summary']
        cost_splits = self.processed_data['cost_splits']

        for tenant in rental_summary.get('tenants', []):
            expected_rent = rental_summary['tenant_summary'].get(tenant, {}).get('annual_rent', 0)
            expected_costs = {}
            total_expected_costs = 0

            for cost_type, cost_info in cost_splits.items():
                if isinstance(cost_info, dict) and 'tenant_shares' in cost_info:
                    if tenant in cost_info['tenant_shares']:
                        amt = cost_info['tenant_shares'][tenant]['amount']
                        expected_costs[cost_type] = amt
                        total_expected_costs += amt

            total_expected = expected_rent + total_expected_costs
            actual = self._get_tenant_payments(tenant)
            total_received = actual['total_received']

            invoice_data = {
                'tenant': tenant,
                'year': 2025,
                'expected_rent': expected_rent,
                'expected_costs': expected_costs,
                'total_expected': total_expected,
                'actual_received': total_received,
                'actual_miete': actual['total_miete'],
                'actual_nebenkosten': actual['total_nebenkosten'],
                'actual_nk_abrechnung': actual['total_nk_abrechnung'],
                'actual_other': actual['total_other'],
                'diff_miete': actual['total_miete'] - expected_rent,
                'diff_nebenkosten': actual['total_nebenkosten'] - total_expected_costs,
                'difference': total_received - total_expected,
                'transaction_count': actual['transaction_count'],
                'transactions': actual['transactions']
            }

            invoice_file = invoices_dir / f"{tenant.replace('/', '_').replace(' ', '_')}_invoice.json"
            with open(invoice_file, 'w', encoding='utf-8') as f:
                json.dump(invoice_data, f, indent=2, default=str)

    def _generate_detailed_reports(self, output_dir: Path):
        """Generate detailed breakdown reports."""
        details_dir = output_dir / 'details'
        details_dir.mkdir(exist_ok=True)

        summaries = {
            'bank_summary': self.processed_data['bank_summary'],
            'rental_summary': self.processed_data['rental_summary'],
            'tax_summary': self.processed_data['tax_summary']
        }

        for report_name, report_data in summaries.items():
            report_file = details_dir / f"{report_name}.json"
            with open(report_file, 'w', encoding='utf-8') as f:
                json.dump(report_data, f, indent=2, default=str)

    def display_tenant_reports(self, reports_dir: Path, tenant_filter: Optional[str] = None):
        """Display tenant reports from generated invoice files."""
        invoices_dir = reports_dir if reports_dir.name == 'tenant_invoices' else reports_dir.parent / 'tenant_invoices'
        if not invoices_dir.exists():
            # Try common locations
            for candidate in [Path('reports/tenant_invoices'), reports_dir]:
                if candidate.exists():
                    invoices_dir = candidate
                    break
            else:
                raise FileNotFoundError(f"No tenant invoices found in {reports_dir} or reports/tenant_invoices/")

        invoice_files = sorted(invoices_dir.glob('*_invoice.json'))
        if not invoice_files:
            raise FileNotFoundError(f"No invoice files found in {invoices_dir}")

        # Grand totals for sum row
        sum_expected_rent = 0
        sum_expected_nk = 0
        sum_expected_total = 0
        sum_actual_miete = 0
        sum_actual_nk = 0
        sum_actual_nk_abr = 0
        sum_actual_other = 0
        sum_actual_received = 0

        found = False
        for invoice_file in invoice_files:
            with open(invoice_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            tenant_name = data.get('tenant', '')
            if tenant_filter and tenant_filter.lower() not in tenant_name.lower():
                continue

            found = True
            expected_rent = data.get('expected_rent', data.get('rental_income', 0))
            expected_costs = data.get('expected_costs', data.get('additional_costs', {}))
            total_expected_costs = sum(expected_costs.values()) if expected_costs else 0
            total_expected = data.get('total_expected', expected_rent)
            actual_received = data.get('actual_received', 0)
            actual_miete = data.get('actual_miete', 0)
            actual_nk = data.get('actual_nebenkosten', 0)
            actual_nk_abr = data.get('actual_nk_abrechnung', 0)
            actual_other = data.get('actual_other', 0)
            difference = data.get('difference', 0)
            diff_miete = data.get('diff_miete', 0)
            diff_nk = data.get('diff_nebenkosten', 0)

            # Accumulate grand totals
            sum_expected_rent += expected_rent
            sum_expected_nk += total_expected_costs
            sum_expected_total += total_expected
            sum_actual_miete += actual_miete
            sum_actual_nk += actual_nk
            sum_actual_nk_abr += actual_nk_abr
            sum_actual_other += actual_other
            sum_actual_received += actual_received

            print(f"\n{'=' * 72}")
            print(f"  Tenant: {tenant_name}")
            print(f"  Year:   {data.get('year', 'N/A')}")
            print(f"{'=' * 72}")
            print(f"  {'':30s} {'Expected':>12s} {'Received':>12s} {'Diff':>12s}")
            print(f"  {'─' * 66}")
            print(f"  {'Miete:':30s} €{expected_rent:>10,.2f} €{actual_miete:>10,.2f} €{diff_miete:>+10,.2f}")
            if expected_costs:
                for cost_type, amount in expected_costs.items():
                    print(f"  {cost_type + ':':30s} €{amount:>10,.2f} €{actual_nk:>10,.2f} €{diff_nk:>+10,.2f}")
            if actual_nk_abr > 0:
                print(f"  {'NK-Abrechnung:':30s} {'':>12s} €{actual_nk_abr:>10,.2f}")
            if actual_other > 0:
                print(f"  {'Sonstige:':30s} {'':>12s} €{actual_other:>10,.2f}")
            print(f"  {'─' * 66}")
            print(f"  {'Gesamt:':30s} €{total_expected:>10,.2f} €{actual_received:>10,.2f} €{difference:>+10,.2f}")

            # Show individual transactions with classification
            transactions = data.get('transactions', [])
            if transactions:
                print(f"\n  {'ZAHLUNGEN':40s}")
                print(f"  {'─' * 70}")
                print(f"  {'Datum':12s} {'Betrag':>9s}  {'Miete':>9s} {'Nebenk.':>9s} {'NK-Abr.':>9s} {'Sonst.':>9s}  {'Typ'}")
                print(f"  {'─' * 70}")
                for txn in transactions:
                    d = txn['date']
                    amt = txn['amount']
                    mi = txn.get('miete', 0)
                    nk = txn.get('nebenkosten', 0)
                    na = txn.get('nk_abrechnung', 0)
                    ot = txn.get('other', 0)
                    cat = txn.get('category', '')
                    mi_s = f"€{mi:>8,.2f}" if mi > 0 else f"{'':>9s}"
                    nk_s = f"€{nk:>8,.2f}" if nk > 0 else f"{'':>9s}"
                    na_s = f"€{na:>8,.2f}" if na > 0 else f"{'':>9s}"
                    ot_s = f"€{ot:>8,.2f}" if ot > 0 else f"{'':>9s}"
                    print(f"  {d}  €{amt:>8,.2f}  {mi_s} {nk_s} {na_s} {ot_s}  {cat}")
                print(f"  {'─' * 70}")
                t_amt = sum(t['amount'] for t in transactions)
                t_mi = sum(t.get('miete', 0) for t in transactions)
                t_nk = sum(t.get('nebenkosten', 0) for t in transactions)
                t_na = sum(t.get('nk_abrechnung', 0) for t in transactions)
                t_ot = sum(t.get('other', 0) for t in transactions)
                t_mi_s = f"€{t_mi:>8,.2f}" if t_mi > 0 else f"{'':>9s}"
                t_nk_s = f"€{t_nk:>8,.2f}" if t_nk > 0 else f"{'':>9s}"
                t_na_s = f"€{t_na:>8,.2f}" if t_na > 0 else f"{'':>9s}"
                t_ot_s = f"€{t_ot:>8,.2f}" if t_ot > 0 else f"{'':>9s}"
                print(f"  {'Summe':12s}  €{t_amt:>8,.2f}  {t_mi_s} {t_nk_s} {t_na_s} {t_ot_s}")
                e_mi_s = f"€{expected_rent:>8,.2f}"
                e_nk_s = f"€{total_expected_costs:>8,.2f}"
                print(f"  {'Erwartet':12s}  €{total_expected:>8,.2f}  {e_mi_s} {e_nk_s}")
                reg_count = sum(1 for t in transactions if t.get('category') != 'NK-Abrechnung')
                print(f"  Anzahl reguläre Zahlungen: {reg_count}")
            print()

        if not found:
            print(f"No tenant found matching '{tenant_filter}'")
            return

        # Print grand total
        sum_diff_miete = sum_actual_miete - sum_expected_rent
        sum_diff_nk = sum_actual_nk - sum_expected_nk
        sum_difference = sum_actual_received - sum_expected_total

        print(f"{'=' * 72}")
        print(f"  GESAMT ALLE MIETER")
        print(f"{'=' * 72}")
        print(f"  {'':30s} {'Expected':>12s} {'Received':>12s} {'Diff':>12s}")
        print(f"  {'─' * 66}")
        print(f"  {'Miete:':30s} €{sum_expected_rent:>10,.2f} €{sum_actual_miete:>10,.2f} €{sum_diff_miete:>+10,.2f}")
        print(f"  {'Nebenkosten:':30s} €{sum_expected_nk:>10,.2f} €{sum_actual_nk:>10,.2f} €{sum_diff_nk:>+10,.2f}")
        if sum_actual_nk_abr > 0:
            print(f"  {'NK-Abrechnung:':30s} {'':>12s} €{sum_actual_nk_abr:>10,.2f}")
        if sum_actual_other > 0:
            print(f"  {'Sonstige:':30s} {'':>12s} €{sum_actual_other:>10,.2f}")
        print(f"  {'─' * 66}")
        print(f"  {'Gesamt:':30s} €{sum_expected_total:>10,.2f} €{sum_actual_received:>10,.2f} €{sum_difference:>+10,.2f}")
        print()

    def get_summary(self) -> Dict:
        """Return the current processed data summary."""
        if self.processed_data is None:
            raise ValueError("Data must be processed first")
        
        return {
            'bank_summary': self.processed_data['bank_summary'],
            'rental_summary': self.processed_data['rental_summary'],
            'cost_summary': self.processed_data['cost_splits'],
            'tax_summary': self.processed_data['tax_summary']
        }
