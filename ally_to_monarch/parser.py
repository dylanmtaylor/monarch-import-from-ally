"""Balance history computation and statement aggregation."""

from datetime import datetime, timedelta, date
from typing import List, Dict, Any, Optional
from collections import defaultdict


def parse_date(date_str: str) -> date:
    """Parse a date string in MM/DD/YYYY or YYYY-MM-DD format."""
    date_str = date_str.strip()
    if "-" in date_str:
        # Check if ISO format with time
        if "T" in date_str:
            date_str = date_str.split("T")[0]
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    elif "/" in date_str:
        return datetime.strptime(date_str, "%m/%d/%Y").date()
    raise ValueError(f"Unrecognized date format: {date_str}")


class AllyAccountHistory:
    """Represents the complete historical record of an Ally account."""

    def __init__(
        self,
        account_name: str,
        account_number: str,
        product: str,
        open_date: Optional[str] = None,
        owner: Optional[str] = None,
    ):
        self.account_name = account_name
        self.account_number = account_number
        self.product = product
        self.open_date = open_date
        self.owner = owner
        self.statements: List[Dict[str, Any]] = []
        self.transactions: List[Dict[str, Any]] = []

    @property
    def slug(self) -> str:
        """Safe filename slug for this account."""
        clean_name = self.account_name.lower().replace(" ", "_").replace("-", "_")
        clean_num = self.account_number.replace("x", "").replace("*", "").strip()
        if clean_num:
            return f"{clean_name}_{clean_num}"
        return clean_name

    def add_statement(self, stmt_data: Dict[str, Any]):
        """Add a parsed statement for this account."""
        self.statements.append(stmt_data)
        if stmt_data.get("transactions"):
            for t in stmt_data["transactions"]:
                # Avoid duplicate transactions if already added
                if not any(
                    x["date"] == t["date"]
                    and x["amount"] == t["amount"]
                    and x["description"] == t["description"]
                    for x in self.transactions
                ):
                    self.transactions.append(t)

    def compute_daily_balances(
        self, end_date: Optional[date] = None, from_first_statement: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Compute continuous daily balance history forward-filled from inception to end_date.
        
        Args:
            end_date: Last date to compute balances for (defaults to today).
            from_first_statement: If True, start daily history at the earliest verified statement date
                                 rather than forward-filling from open_date when older statements are missing.
            
        Returns:
            List of {"date": "YYYY-MM-DD", "balance": float} for every single day.
        """
        if end_date is None:
            end_date = date.today()

        # Determine start date
        start_d: Optional[date] = None
        if self.open_date and not from_first_statement:
            try:
                start_d = parse_date(self.open_date)
            except Exception:
                pass

        # Sort statements chronologically
        sorted_stmts = sorted(
            self.statements,
            key=lambda s: parse_date(s.get("beg_date") or s.get("statement_date") or "01/01/2000"),
        )

        earliest_stmt_date: Optional[date] = None
        initial_balance = 0.0

        if sorted_stmts:
            first_stmt = sorted_stmts[0]
            if first_stmt.get("beg_date"):
                earliest_stmt_date = parse_date(first_stmt["beg_date"])
                initial_balance = first_stmt.get("beg_bal", 0.0)
            elif first_stmt.get("statement_date"):
                earliest_stmt_date = parse_date(first_stmt["statement_date"])
                initial_balance = first_stmt.get("end_bal", 0.0)

        if from_first_statement and earliest_stmt_date:
            start_d = earliest_stmt_date
        elif not start_d:
            start_d = earliest_stmt_date or date(2020, 1, 1)

        # Make sure start_d is not in future
        if start_d > end_date:
            start_d = end_date

        # Map daily net activity and statement checkpoint balances
        daily_activity = defaultdict(float)
        checkpoint_balances: Dict[date, float] = {}

        # Sort transactions
        sorted_txns = sorted(self.transactions, key=lambda t: parse_date(t["date"]))
        for t in sorted_txns:
            t_date = parse_date(t["date"])
            daily_activity[t_date] += t["amount"]
            if t.get("balance") is not None:
                # Last transaction balance on that day serves as checkpoint
                checkpoint_balances[t_date] = t["balance"]

        for s in sorted_stmts:
            if s.get("end_date"):
                end_d = parse_date(s["end_date"])
                checkpoint_balances[end_d] = s.get("end_bal", 0.0)
            if s.get("beg_date"):
                beg_d = parse_date(s["beg_date"])
                # Only set beginning checkpoint if before transactions
                if beg_d not in checkpoint_balances:
                    checkpoint_balances[beg_d] = s.get("beg_bal", 0.0)

        # Construct daily series
        daily_balances = []
        curr_balance = initial_balance
        curr_d = start_d

        while curr_d <= end_date:
            # If current day has transactions, apply them
            if curr_d in daily_activity:
                curr_balance += daily_activity[curr_d]

            # If checkpoint exists for this day, align with official statement balance
            if curr_d in checkpoint_balances:
                curr_balance = checkpoint_balances[curr_d]

            curr_balance = round(curr_balance, 2)
            daily_balances.append({
                "date": curr_d.strftime("%Y-%m-%d"),
                "balance": curr_balance
            })

            curr_d += timedelta(days=1)

        return daily_balances


def aggregate_statements(statements_list: List[Dict[str, Any]]) -> Dict[str, AllyAccountHistory]:
    """
    Aggregate statements across all accounts.
    
    Args:
        statements_list: List of parsed account statement objects.
        
    Returns:
        Mapping of account_number -> AllyAccountHistory.
    """
    accounts: Dict[str, AllyAccountHistory] = {}

    for stmt in statements_list:
        acct_num = stmt["account_number"]
        if acct_num not in accounts:
            accounts[acct_num] = AllyAccountHistory(
                account_name=stmt["account_name"],
                account_number=acct_num,
                product=stmt["product"],
                open_date=stmt.get("open_date"),
                owner=stmt.get("owner"),
            )
        accounts[acct_num].add_statement(stmt)

    return accounts
