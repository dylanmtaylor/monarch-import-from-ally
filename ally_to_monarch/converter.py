"""Converts Ally Bank transactions and balances to Monarch Money CSV format."""

import csv
import io
import re
from typing import List, Dict, Any, Optional
from datetime import datetime


def clean_merchant_name(desc: str) -> str:
    """Extract a concise, human-friendly merchant/counterparty from statement text."""
    desc_upper = desc.upper()

    if "INTEREST PAID" in desc_upper:
        return "Ally Bank Interest"

    # Match bank names in parentheses or 'transfer to/from'
    if "TRUIST" in desc_upper:
        return "Truist Bank Transfer"
    if "BLUE RIDGE" in desc_upper:
        return "Blue Ridge Bank Transfer"
    if "PRIMIS" in desc_upper:
        return "Primis Bank Transfer"

    if "P2P" in desc_upper:
        return "Ally P2P Transfer"

    if "TRANSFER FROM" in desc_upper:
        m = re.search(r"TRANSFER FROM\s+([A-Za-z0-9 ]+?)(?:Ally Bank Transfer|$)", desc, re.IGNORECASE)
        if m:
            name = m.group(1).strip()
            return f"Transfer from {name}"
        return "Ally Bank Transfer"

    if "TRANSFER TO" in desc_upper:
        m = re.search(r"TRANSFER TO\s+([A-Za-z0-9 ]+?)(?:\(|$)", desc, re.IGNORECASE)
        if m:
            name = m.group(1).strip()
            return f"Transfer to {name}"
        return "Ally Bank Transfer"

    if "WITHDRAWAL" in desc_upper:
        return "Withdrawal"
    if "DEPOSIT" in desc_upper:
        return "Deposit"

    # Default fallback: first 40 chars
    return desc[:40].strip()


def infer_category(desc: str, amount: float) -> str:
    """Infer Monarch category from description and amount."""
    desc_upper = desc.upper()
    if "INTEREST" in desc_upper:
        return "Interest"
    if any(k in desc_upper for k in ["TRANSFER", "WITHDRAWAL", "DEPOSIT"]):
        return "Transfer"
    if "FEE" in desc_upper:
        return "Bank Fee"
    return "Transfer"


def convert_balances_to_csv(daily_balances: List[Dict[str, Any]]) -> str:
    """
    Format daily balances into Monarch Money CSV format.
    Header: Date,Balance
    """
    output = io.StringIO()
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(["Date", "Balance"])

    for row in daily_balances:
        writer.writerow([row["date"], f"{row['balance']:.2f}"])

    return output.getvalue()


def convert_transactions_to_csv(
    transactions: List[Dict[str, Any]], account_display_name: str
) -> str:
    """
    Format transactions into Monarch Money CSV format.
    Header: Date,Merchant,Category,Account,Original Statement,Notes,Amount
    """
    output = io.StringIO()
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(["Date", "Merchant", "Category", "Account", "Original Statement", "Notes", "Amount"])

    for txn in transactions:
        # Format date as YYYY-MM-DD
        raw_date = txn["date"].strip()
        if "/" in raw_date:
            d_obj = datetime.strptime(raw_date, "%m/%d/%Y")
            iso_date = d_obj.strftime("%Y-%m-%d")
        else:
            iso_date = raw_date

        desc = txn.get("description", "").strip()
        merchant = clean_merchant_name(desc)
        category = infer_category(desc, txn["amount"])
        notes = f"Ally Bank {txn.get('date', '')}"
        amount_str = f"{txn['amount']:.2f}"

        writer.writerow([
            iso_date,
            merchant,
            category,
            account_display_name,
            desc,
            notes,
            amount_str,
        ])

    return output.getvalue()
