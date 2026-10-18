"""Unit tests for Ally Bank PDF statement parsing using synthetic fixtures."""

import unittest
import fitz
from ally_to_monarch.statement_parser import StatementParser


def create_synthetic_statement_pdf(multi_account: bool = False) -> bytes:
    """Generate an in-memory synthetic Ally PDF statement using PyMuPDF."""
    doc = fitz.open()

    # Page 1: Savings Account
    p1 = doc.new_page()
    text_p1 = """COMBINED CUSTOMER STATEMENT
Statement Date
03/15/2023
Page 1

Savings Account
Summary For:
Jane Doe
Account Number:  xxxxxx8888
Open Date:  01/10/2021
Product:  Savings Account

Summary
Beginning Balance, as of 02/16/2023
$1,000.00
Deposits and Other Credits
$500.00
Interest Paid This Period
$2.50
Withdrawals and Other Debits
-$200.00
Ending Balance, as of 03/15/2023
$1,302.50

Activity
Date
Description
Credits
Debits
Balance
02/16/2023
Beginning Balance
$1,000.00
02/20/2023
Direct Deposit
Employer Payroll Transfer
$500.00
-$0.00
$1,500.00
03/01/2023
ACH Withdrawal
Requested transfer to Bank Checking
$0.00
-$200.00
$1,300.00
03/15/2023
Interest Paid
$2.50
-$0.00
$1,302.50
03/15/2023
Ending Balance
$1,302.50
"""
    p1.insert_text((50, 50), text_p1)

    if multi_account:
        # Page 2: No Penalty CD
        p2 = doc.new_page()
        text_p2 = """COMBINED CUSTOMER STATEMENT
Statement Date
03/15/2023
Page 2

No Penalty CD
Summary For:
Jane Doe
Account Number:  xxxxxx5555
Open Date:  03/01/2023
Product:  No Penalty 11-Month CD

Summary
Beginning Balance, as of 03/01/2023
$0.00
Deposits and Other Credits
$10,000.00
Interest Paid This Period
$0.00
Withdrawals and Other Debits
$0.00
Ending Balance, as of 03/15/2023
$10,000.00

Activity
Date
Description
Credits
Debits
Balance
03/01/2023
Beginning Balance
$0.00
03/02/2023
ACH Deposit
Opening deposit funding
$10,000.00
-$0.00
$10,000.00
03/15/2023
Ending Balance
$10,000.00
"""
        p2.insert_text((50, 50), text_p2)

    return doc.tobytes()


class TestStatementParser(unittest.TestCase):
    """Test suite for PDF statement extraction."""

    def test_parse_single_account_statement(self):
        """Test parsing a single account statement from PDF bytes."""
        pdf_bytes = create_synthetic_statement_pdf(multi_account=False)
        accounts = StatementParser.parse_pdf(pdf_bytes)

        self.assertEqual(len(accounts), 1)
        acct = accounts[0]
        self.assertEqual(acct["account_name"], "Savings Account")
        self.assertEqual(acct["account_number"], "xxxxxx8888")
        self.assertEqual(acct["owner"], "Jane Doe")
        self.assertEqual(acct["open_date"], "01/10/2021")
        self.assertEqual(acct["product"], "Savings Account")
        self.assertEqual(acct["statement_date"], "03/15/2023")
        self.assertEqual(acct["beg_date"], "02/16/2023")
        self.assertEqual(acct["beg_bal"], 1000.00)
        self.assertEqual(acct["end_date"], "03/15/2023")
        self.assertEqual(acct["end_bal"], 1302.50)

        # Transactions
        txns = acct["transactions"]
        self.assertEqual(len(txns), 3)

        # Txn 1: Direct Deposit
        self.assertEqual(txns[0]["date"], "02/20/2023")
        self.assertIn("Direct Deposit", txns[0]["description"])
        self.assertEqual(txns[0]["credits"], 500.00)
        self.assertEqual(txns[0]["debits"], 0.00)
        self.assertEqual(txns[0]["amount"], 500.00)
        self.assertEqual(txns[0]["balance"], 1500.00)

        # Txn 2: ACH Withdrawal
        self.assertEqual(txns[1]["date"], "03/01/2023")
        self.assertIn("ACH Withdrawal", txns[1]["description"])
        self.assertEqual(txns[1]["credits"], 0.00)
        self.assertEqual(txns[1]["debits"], -200.00)
        self.assertEqual(txns[1]["amount"], -200.00)
        self.assertEqual(txns[1]["balance"], 1300.00)

        # Txn 3: Interest Paid
        self.assertEqual(txns[2]["date"], "03/15/2023")
        self.assertIn("Interest Paid", txns[2]["description"])
        self.assertEqual(txns[2]["credits"], 2.50)
        self.assertEqual(txns[2]["amount"], 2.50)
        self.assertEqual(txns[2]["balance"], 1302.50)

    def test_parse_multi_account_statement(self):
        """Test parsing combined statement with multiple accounts."""
        pdf_bytes = create_synthetic_statement_pdf(multi_account=True)
        accounts = StatementParser.parse_pdf(pdf_bytes)

        self.assertEqual(len(accounts), 2)
        savings = [a for a in accounts if a["account_number"] == "xxxxxx8888"][0]
        cd = [a for a in accounts if a["account_number"] == "xxxxxx5555"][0]

        self.assertEqual(savings["account_name"], "Savings Account")
        self.assertEqual(cd["account_name"], "No Penalty CD")
        self.assertEqual(cd["product"], "No Penalty 11-Month CD")
        self.assertEqual(cd["end_bal"], 10000.00)
        self.assertEqual(len(cd["transactions"]), 1)
        self.assertEqual(cd["transactions"][0]["amount"], 10000.00)


if __name__ == "__main__":
    unittest.main()
