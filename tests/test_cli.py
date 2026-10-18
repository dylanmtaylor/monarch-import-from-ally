"""Unit tests for Exporter and CLI argument handling."""

import unittest
import tempfile
import os
import glob
from ally_to_monarch.parser import AllyAccountHistory
from ally_to_monarch.exporter import Exporter


class TestCLIAndExporter(unittest.TestCase):
    """Test suite for exporter and CLI flows."""

    def test_exporter_creates_files(self):
        """Test exporter writes balance and transaction CSVs to output directory."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            exporter = Exporter(output_dir=tmp_dir)

            acct1 = AllyAccountHistory(
                account_name="Savings Account",
                account_number="xxxxxx9999",
                product="Savings Account",
                open_date="01/01/2023",
            )
            acct1.add_statement({
                "statement_date": "01/31/2023",
                "beg_date": "01/01/2023",
                "beg_bal": 100.0,
                "end_date": "01/31/2023",
                "end_bal": 200.0,
                "transactions": [
                    {
                        "date": "01/15/2023",
                        "description": "Interest Paid",
                        "credits": 100.0,
                        "debits": 0.0,
                        "amount": 100.0,
                        "balance": 200.0,
                    }
                ],
            })

            accounts = {"xxxxxx9999": acct1}
            results = exporter.export_all(accounts)

            self.assertEqual(len(results["balance_files"]), 1)
            self.assertEqual(len(results["transaction_files"]), 1)
            self.assertTrue(os.path.exists(results["balance_files"][0]))
            self.assertTrue(os.path.exists(results["transaction_files"][0]))
            self.assertTrue(os.path.exists(results["combined_transaction_file"]))

            # Verify contents of generated files
            with open(results["balance_files"][0], "r") as f:
                lines = f.readlines()
                self.assertIn("Date,Balance\n", lines)
                self.assertGreater(len(lines), 1)

            with open(results["combined_transaction_file"], "r") as f:
                lines = f.readlines()
                self.assertIn("Date,Merchant,Category,Account,Original Statement,Notes,Amount\n", lines)
                self.assertEqual(len(lines), 2)  # Header + 1 txn


if __name__ == "__main__":
    unittest.main()
