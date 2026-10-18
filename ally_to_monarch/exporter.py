"""Exports converted balances and transactions to disk."""

import os
import csv
from typing import Dict, List, Any
from ally_to_monarch.parser import AllyAccountHistory
from ally_to_monarch.converter import convert_balances_to_csv, convert_transactions_to_csv


class Exporter:
    """Exports Monarch CSV files and displays human-readable summary reports."""

    def __init__(self, output_dir: str = "output"):
        self.output_dir = output_dir

    def export_all(
        self, accounts: Dict[str, AllyAccountHistory], from_first_statement: bool = False
    ) -> Dict[str, Any]:
        """
        Export balance and transaction CSVs for all accounts.
        
        Args:
            accounts: Dictionary of AllyAccountHistory objects.
            from_first_statement: If True, balance history starts from the earliest verified statement date.
            
        Returns:
            Dict containing generated file paths and metrics.
        """
        os.makedirs(self.output_dir, exist_ok=True)
        results = {
            "balance_files": [],
            "transaction_files": [],
            "combined_transaction_file": None,
            "metrics": {},
        }

        all_transactions_rows = []

        print("\n" + "=" * 70)
        print("Ally Bank to Monarch Money Export Summary")
        print("=" * 70)

        for acct_num, acct in sorted(accounts.items(), key=lambda x: x[1].account_name):
            slug = acct.slug
            display_name = f"Ally - {acct.account_name} ({acct.account_number})"

            # 1. Compute and export daily balances
            daily_balances = acct.compute_daily_balances(from_first_statement=from_first_statement)
            bal_csv = convert_balances_to_csv(daily_balances)
            bal_file = os.path.join(self.output_dir, f"ally_balances_{slug}.csv")
            with open(bal_file, "w", encoding="utf-8") as f:
                f.write(bal_csv)
            results["balance_files"].append(bal_file)

            # 2. Export account transactions
            txn_csv = convert_transactions_to_csv(acct.transactions, display_name)
            txn_file = os.path.join(self.output_dir, f"ally_transactions_{slug}.csv")
            with open(txn_file, "w", encoding="utf-8") as f:
                f.write(txn_csv)
            results["transaction_files"].append(txn_file)

            # Read transaction rows for combined file
            reader = csv.reader(txn_csv.strip().splitlines())
            headers = next(reader, None)
            for r in reader:
                all_transactions_rows.append(r)

            first_bal_date = daily_balances[0]["date"] if daily_balances else "N/A"
            last_bal_date = daily_balances[-1]["date"] if daily_balances else "N/A"
            current_bal = daily_balances[-1]["balance"] if daily_balances else 0.0

            results["metrics"][acct_num] = {
                "name": acct.account_name,
                "number": acct.account_number,
                "product": acct.product,
                "open_date": acct.open_date,
                "statements_count": len(acct.statements),
                "transactions_count": len(acct.transactions),
                "daily_balance_days": len(daily_balances),
                "daily_balance_range": f"{first_bal_date} to {last_bal_date}",
                "current_balance": current_bal,
            }

            print(f"\nAccount: {acct.account_name} ({acct.account_number})")
            print(f"  Product:           {acct.product}")
            print(f"  Open Date:         {acct.open_date}")
            print(f"  Statements:        {len(acct.statements)}")
            print(f"  Transactions:      {len(acct.transactions)}")
            print(f"  Balance History:   {len(daily_balances):,} daily points ({first_bal_date} to {last_bal_date})")
            print(f"  Current Balance:   ${current_bal:,.2f}")
            print(f"  -> Balances CSV:     {bal_file}")
            print(f"  -> Transactions CSV: {txn_file}")

        # 3. Export combined transactions CSV
        if all_transactions_rows:
            # Sort combined transactions by Date (index 0)
            all_transactions_rows.sort(key=lambda r: r[0])
            combined_file = os.path.join(self.output_dir, "ally_transactions_all.csv")
            with open(combined_file, "w", encoding="utf-8", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["Date", "Merchant", "Category", "Account", "Original Statement", "Notes", "Amount"])
                writer.writerows(all_transactions_rows)
            results["combined_transaction_file"] = combined_file
            print(f"\nCombined Transactions CSV ({len(all_transactions_rows)} records):")
            print(f"  -> {combined_file}")

        print("\n" + "=" * 70)
        print("Export completed successfully.")
        print("=" * 70 + "\n")

        return results
