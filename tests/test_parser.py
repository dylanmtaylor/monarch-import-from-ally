"""Unit tests for balance history computation and statement aggregation."""

import unittest
from datetime import date
from ally_to_monarch.parser import (
    parse_date,
    AllyAccountHistory,
    aggregate_statements,
)


class TestParser(unittest.TestCase):
    """Test suite for date parsing and balance history computation."""

    def test_parse_date_formats(self):
        """Test parsing ISO and MM/DD/YYYY date formats."""
        self.assertEqual(parse_date("2023-05-15"), date(2023, 5, 15))
        self.assertEqual(parse_date("2023-05-15T12:00:00.000Z"), date(2023, 5, 15))
        self.assertEqual(parse_date("05/15/2023"), date(2023, 5, 15))
        with self.assertRaises(ValueError):
            parse_date("invalid-date-string")

    def test_account_history_slug(self):
        """Test account slug generation."""
        acct1 = AllyAccountHistory("Savings Account", "xxxxxx1234", "Savings Account")
        self.assertEqual(acct1.slug, "savings_account_1234")

        acct2 = AllyAccountHistory("No Penalty CD", "xxxxxx5678", "No Penalty 11-Month CD")
        self.assertEqual(acct2.slug, "no_penalty_cd_5678")

        acct3 = AllyAccountHistory("Checking Account", "", "Interest Checking")
        self.assertEqual(acct3.slug, "checking_account")

    def test_add_statement_and_deduplication(self):
        """Test statement addition and duplicate transaction suppression."""
        acct = AllyAccountHistory("Savings Account", "xxxxxx1234", "Savings Account")
        stmt1 = {
            "statement_date": "02/15/2023",
            "beg_date": "01/16/2023",
            "beg_bal": 100.00,
            "end_date": "02/15/2023",
            "end_bal": 150.00,
            "transactions": [
                {
                    "date": "01/20/2023",
                    "description": "Deposit",
                    "amount": 50.00,
                    "balance": 150.00,
                }
            ],
        }
        acct.add_statement(stmt1)
        self.assertEqual(len(acct.statements), 1)
        self.assertEqual(len(acct.transactions), 1)

        # Re-adding same statement or transaction should not duplicate
        acct.add_statement(stmt1)
        self.assertEqual(len(acct.statements), 2)
        self.assertEqual(len(acct.transactions), 1)

    def test_compute_daily_balances_continuous(self):
        """Test continuous daily balance calculation with no date gaps."""
        acct = AllyAccountHistory(
            account_name="Savings Account",
            account_number="xxxxxx9999",
            product="Savings Account",
            open_date="01/01/2023",
        )
        stmt = {
            "statement_date": "01/31/2023",
            "beg_date": "01/01/2023",
            "beg_bal": 1000.00,
            "end_date": "01/31/2023",
            "end_bal": 1200.00,
            "transactions": [
                {
                    "date": "01/15/2023",
                    "description": "Direct Deposit",
                    "amount": 200.00,
                    "balance": 1200.00,
                }
            ],
        }
        acct.add_statement(stmt)
        daily = acct.compute_daily_balances(end_date=date(2023, 1, 31))

        # Check total days: Jan 1 to Jan 31 = 31 days
        self.assertEqual(len(daily), 31)
        self.assertEqual(daily[0]["date"], "2023-01-01")
        self.assertEqual(daily[0]["balance"], 1000.00)

        # Day before transaction
        day_14 = [d for d in daily if d["date"] == "2023-01-14"][0]
        self.assertEqual(day_14["balance"], 1000.00)

        # Day of transaction
        day_15 = [d for d in daily if d["date"] == "2023-01-15"][0]
        self.assertEqual(day_15["balance"], 1200.00)

        # End of month
        self.assertEqual(daily[-1]["date"], "2023-01-31")
        self.assertEqual(daily[-1]["balance"], 1200.00)

    def test_aggregate_statements(self):
        """Test aggregation of multiple statement records across accounts."""
        raw_statements = [
            {
                "account_name": "Savings Account",
                "account_number": "xxxxxx1111",
                "product": "Savings Account",
                "open_date": "01/01/2020",
                "owner": "Test User",
                "statement_date": "01/15/2020",
                "beg_date": "12/16/2019",
                "beg_bal": 500.00,
                "end_date": "01/15/2020",
                "end_bal": 500.00,
                "transactions": [],
            },
            {
                "account_name": "No Penalty CD",
                "account_number": "xxxxxx2222",
                "product": "No Penalty CD",
                "open_date": "06/01/2021",
                "owner": "Test User",
                "statement_date": "06/15/2021",
                "beg_date": "06/01/2021",
                "beg_bal": 10000.00,
                "end_date": "06/15/2021",
                "end_bal": 10000.00,
                "transactions": [],
            },
        ]
        accounts = aggregate_statements(raw_statements)
        self.assertEqual(len(accounts), 2)
        self.assertIn("xxxxxx1111", accounts)
        self.assertIn("xxxxxx2222", accounts)
        self.assertEqual(accounts["xxxxxx1111"].account_name, "Savings Account")
        self.assertEqual(accounts["xxxxxx2222"].product, "No Penalty CD")


if __name__ == "__main__":
    unittest.main()
