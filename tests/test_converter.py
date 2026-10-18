"""Unit tests for Monarch Money CSV converters."""

import unittest
import csv
from ally_to_monarch.converter import (
    clean_merchant_name,
    infer_category,
    convert_balances_to_csv,
    convert_transactions_to_csv,
)


class TestConverter(unittest.TestCase):
    """Test suite for Monarch CSV conversions."""

    def test_clean_merchant_name(self):
        """Test merchant cleaning and extraction."""
        self.assertEqual(clean_merchant_name("Interest Paid"), "Ally Bank Interest")
        self.assertEqual(
            clean_merchant_name("NOW Withdrawal Requested transfer to Jane (TRUIST BANK Checking 1234)"),
            "Truist Bank Transfer",
        )
        self.assertEqual(
            clean_merchant_name("ACH Withdrawal Requested transfer to JANE (BLUE RIDGE BANK, NA Checking 0000) $TRANSFER"),
            "Blue Ridge Bank Transfer",
        )
        self.assertEqual(
            clean_merchant_name("Withdrawal Requested transfer to PRIMIS BANK DDA account 9999"),
            "Primis Bank Transfer",
        )
        self.assertEqual(
            clean_merchant_name("ACH Deposit Requested transfer from JANE Ally Bank Transfer JANE P2P"),
            "Ally P2P Transfer",
        )
        self.assertEqual(
            clean_merchant_name("Transfer from John Smith Ally Bank Transfer"),
            "Transfer from John Smith",
        )

    def test_infer_category(self):
        """Test category inference."""
        self.assertEqual(infer_category("Interest Paid", 5.25), "Interest")
        self.assertEqual(infer_category("ACH Withdrawal", -100.00), "Transfer")
        self.assertEqual(infer_category("ACH Deposit", 500.00), "Transfer")
        self.assertEqual(infer_category("Monthly Maintenance Fee", -10.00), "Bank Fee")

    def test_convert_balances_to_csv(self):
        """Test balance history CSV formatting."""
        daily_balances = [
            {"date": "2023-01-01", "balance": 1500.0},
            {"date": "2023-01-02", "balance": 1525.5},
        ]
        csv_str = convert_balances_to_csv(daily_balances)
        reader = list(csv.reader(csv_str.strip().splitlines()))

        self.assertEqual(reader[0], ["Date", "Balance"])
        self.assertEqual(reader[1], ["2023-01-01", "1500.00"])
        self.assertEqual(reader[2], ["2023-01-02", "1525.50"])

    def test_convert_transactions_to_csv(self):
        """Test transaction CSV formatting."""
        transactions = [
            {
                "date": "03/15/2023",
                "description": "Interest Paid",
                "amount": 12.34,
            },
            {
                "date": "2023-03-20",
                "description": "NOW Withdrawal Requested transfer to (TRUIST BANK Checking 1234)",
                "amount": -500.00,
            },
        ]
        csv_str = convert_transactions_to_csv(transactions, "Ally - Savings Account (xxxxxx1234)")
        reader = list(csv.reader(csv_str.strip().splitlines()))

        self.assertEqual(
            reader[0],
            ["Date", "Merchant", "Category", "Account", "Original Statement", "Notes", "Amount"],
        )
        # Row 1
        self.assertEqual(reader[1][0], "2023-03-15")
        self.assertEqual(reader[1][1], "Ally Bank Interest")
        self.assertEqual(reader[1][2], "Interest")
        self.assertEqual(reader[1][3], "Ally - Savings Account (xxxxxx1234)")
        self.assertEqual(reader[1][6], "12.34")

        # Row 2
        self.assertEqual(reader[2][0], "2023-03-20")
        self.assertEqual(reader[2][1], "Truist Bank Transfer")
        self.assertEqual(reader[2][2], "Transfer")
        self.assertEqual(reader[2][6], "-500.00")


if __name__ == "__main__":
    unittest.main()
