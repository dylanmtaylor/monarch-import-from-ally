"""Parser for Ally Bank Combined Customer Statement PDFs."""

import re
from typing import List, Dict, Any, Optional
import fitz  # PyMuPDF


class StatementParser:
    """Parses Ally Bank monthly Combined Customer Statement PDFs."""

    @staticmethod
    def parse_pdf(file_path_or_bytes) -> List[Dict[str, Any]]:
        """
        Parse an Ally Bank PDF statement.
        
        Args:
            file_path_or_bytes: Either a file path string or raw bytes of a PDF.
            
        Returns:
            A list of account statement dictionaries found within the PDF.
        """
        if isinstance(file_path_or_bytes, bytes):
            doc = fitz.open(stream=file_path_or_bytes, filetype="pdf")
        else:
            doc = fitz.open(file_path_or_bytes)

        full_text = "\n".join(page.get_text() for page in doc)
        stmt_date_m = re.search(r"Statement Date\s*\n\s*(\d{2}/\d{2}/\d{4})", full_text)
        statement_date = stmt_date_m.group(1) if stmt_date_m else None

        accounts = []

        for page in doc:
            ptext = page.get_text()
            # Look for account summary header
            # Example:
            # Savings Account
            # Summary For:
            # Dylan M Taylor
            # Account Number:  xxxxxx1234
            # Open Date:  08/23/2014
            # Product:  Savings Account
            m = re.search(
                r"([A-Za-z0-9 ]+)\s*\n\s*Summary For:\s*\n\s*([^\n]+)\s*\n\s*Account Number:\s*([^\n]+)\s*\n\s*Open Date:\s*([^\n]+)\s*\n\s*Product:\s*([^\n]+)",
                ptext,
            )
            if not m:
                continue

            acct_name = m.group(1).strip()
            owner = m.group(2).strip()
            acct_num = m.group(3).strip()
            open_date = m.group(4).strip()
            product = m.group(5).strip()

            # Beginning Balance, as of MM/DD/YYYY
            beg_m = re.search(
                r"Beginning Balance(?:, as of (\d{2}/\d{2}/\d{4}))?\s*\n\s*(-?\$?[\d,]+\.\d{2})",
                ptext,
            )
            # Ending Balance, as of MM/DD/YYYY
            end_m = re.search(
                r"Ending Balance(?:, as of (\d{2}/\d{2}/\d{4}))?\s*\n\s*(-?\$?[\d,]+\.\d{2})",
                ptext,
            )

            beg_date = beg_m.group(1) if (beg_m and beg_m.group(1)) else None
            beg_bal = float(beg_m.group(2).replace("$", "").replace(",", "")) if beg_m else 0.0
            end_date = end_m.group(1) if (end_m and end_m.group(1)) else statement_date
            end_bal = float(end_m.group(2).replace("$", "").replace(",", "")) if end_m else 0.0

            transactions = []
            if "Activity" in ptext:
                act_text = ptext.split("Activity", 1)[1]
                lines = [l.strip() for l in act_text.split("\n") if l.strip()]

                # Skip header column names: Date, Description, Credits, Debits, Balance
                header_idx = 0
                while header_idx < len(lines) and lines[header_idx] in [
                    "Date", "Description", "Credits", "Debits", "Balance"
                ]:
                    header_idx += 1

                i = header_idx
                while i < len(lines):
                    line = lines[i]
                    # Check if line is a date (MM/DD/YYYY)
                    if re.match(r"^\d{2}/\d{2}/\d{4}$", line):
                        txn_date = line
                        i += 1
                        desc_parts = []
                        # Accumulate description lines until an amount or next date is encountered
                        while (
                            i < len(lines)
                            and not re.match(r"^-?\$[\d,]+\.\d{2}$", lines[i])
                            and not re.match(r"^\d{2}/\d{2}/\d{4}$", lines[i])
                        ):
                            desc_parts.append(lines[i])
                            i += 1

                        desc = " ".join(desc_parts).strip()

                        # Skip Beginning/Ending Balance lines in the activity table
                        if desc in ["Beginning Balance", "Ending Balance"]:
                            if i < len(lines) and re.match(r"^-?\$[\d,]+\.\d{2}$", lines[i]):
                                i += 1
                            continue

                        # Extract credit, debit, balance amounts
                        amounts = []
                        while i < len(lines) and re.match(r"^-?\$[\d,]+\.\d{2}$", lines[i]):
                            amt = float(lines[i].replace("$", "").replace(",", ""))
                            amounts.append(amt)
                            i += 1

                        credits = 0.0
                        debits = 0.0
                        running_bal = None
                        if len(amounts) >= 3:
                            credits = amounts[0]
                            debits = amounts[1]
                            running_bal = amounts[2]
                        elif len(amounts) == 2:
                            val = amounts[0]
                            running_bal = amounts[1]
                            if val > 0:
                                credits = val
                            else:
                                debits = val
                        elif len(amounts) == 1:
                            running_bal = amounts[0]

                        net_amount = round(credits + debits, 2)
                        transactions.append({
                            "date": txn_date,
                            "description": desc,
                            "credits": credits,
                            "debits": debits,
                            "amount": net_amount,
                            "balance": running_bal,
                        })
                    else:
                        i += 1

            accounts.append({
                "account_name": acct_name,
                "account_number": acct_num,
                "owner": owner,
                "open_date": open_date,
                "product": product,
                "statement_date": statement_date,
                "beg_date": beg_date,
                "beg_bal": beg_bal,
                "end_date": end_date,
                "end_bal": end_bal,
                "transactions": transactions,
            })

        return accounts
