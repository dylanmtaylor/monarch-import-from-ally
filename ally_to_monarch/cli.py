"""Command Line Interface for ally-to-monarch."""

import argparse
import sys
import os
import glob
from typing import List, Optional

from ally_to_monarch.cdp import capture_session, CDPError
from ally_to_monarch.api import AllyClient, AllyAPIError
from ally_to_monarch.statement_parser import StatementParser
from ally_to_monarch.parser import aggregate_statements
from ally_to_monarch.exporter import Exporter


def run_pipeline(
    port: int = 9222,
    output_dir: str = "output",
    statement_dir: str = "statements",
    workers: int = 8,
    years: Optional[List[int]] = None,
    skip_download_if_present: bool = True,
):
    """Run full automated pipeline from Chrome CDP to Monarch CSV export."""
    os.makedirs(statement_dir, exist_ok=True)
    os.makedirs(output_dir, exist_ok=True)

    # Check if statement PDFs are already present in statement_dir
    existing_pdfs = glob.glob(os.path.join(statement_dir, "*.pdf"))

    if not existing_pdfs or not skip_download_if_present:
        print(f"Connecting to Chrome on port {port} to capture Ally Bank session...")
        try:
            session = capture_session(port=port)
            print(f"Captured Ally session (Token: {session['token'][:8]}..., Customer ID: {session.get('customer_id')})")
        except CDPError as e:
            if existing_pdfs:
                print(f"CDP capture note: {e}")
                print(f"Found {len(existing_pdfs)} cached statement PDFs in '{statement_dir}', continuing with cached files.")
            else:
                print(f"Error: {e}", file=sys.stderr)
                sys.exit(1)
        else:
            client = AllyClient(
                token=session["token"],
                api_key=session["api_key"],
                customer_id=session.get("customer_id"),
            )

            print("Fetching available statements metadata from Ally Bank...")
            try:
                statements_meta = client.get_statements_list(years=years)
                print(f"Found {len(statements_meta)} monthly statements.")
            except AllyAPIError as e:
                print(f"Failed to fetch statement list: {e}", file=sys.stderr)
                if not existing_pdfs:
                    sys.exit(1)
                statements_meta = []

            if statements_meta:
                print(f"Downloading statements into '{statement_dir}' (concurrency={workers})...")
                downloaded = client.download_all_statements(
                    statements_meta=statements_meta,
                    output_dir=statement_dir,
                    max_workers=workers,
                )
                print(f"Downloaded / verified {len(downloaded)} statement PDFs.")

    # Refresh list of PDFs in statement_dir
    pdf_files = sorted(glob.glob(os.path.join(statement_dir, "*.pdf")))
    if not pdf_files:
        print(f"No statement PDFs found in '{statement_dir}'.", file=sys.stderr)
        sys.exit(1)

    print(f"\nParsing {len(pdf_files)} statement PDFs...")
    all_parsed_statements = []
    for pdf_path in pdf_files:
        try:
            parsed = StatementParser.parse_pdf(pdf_path)
            all_parsed_statements.extend(parsed)
        except Exception as e:
            print(f"Warning: Failed to parse {os.path.basename(pdf_path)}: {e}", file=sys.stderr)

    print(f"Aggregating statement histories across {len(all_parsed_statements)} statement records...")
    accounts = aggregate_statements(all_parsed_statements)

    print(f"Found {len(accounts)} unique Ally Bank account(s).")
    exporter = Exporter(output_dir=output_dir)
    exporter.export_all(accounts)


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="ally-to-monarch",
        description="Extract Ally Bank transactions and daily balance history into Monarch Money CSV format.",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # Command: all
    p_all = subparsers.add_parser("all", help="Full automated capture, parse, and export pipeline")
    p_all.add_argument("--port", type=int, default=9222, help="Chrome remote debugging port (default: 9222)")
    p_all.add_argument("--output-dir", type=str, default="output", help="Directory for Monarch CSVs (default: output)")
    p_all.add_argument("--statement-dir", type=str, default="statements", help="Directory to cache statement PDFs (default: statements)")
    p_all.add_argument("--workers", type=int, default=8, help="Worker threads for downloads (default: 8)")
    p_all.add_argument("--years", type=str, default=None, help="Comma-separated years to fetch (e.g. 2020,2021,2022)")

    # Command: parse-statements
    p_parse = subparsers.add_parser("parse-statements", help="Parse already downloaded statement PDFs and export CSVs")
    p_parse.add_argument("--statement-dir", type=str, default="statements", help="Directory containing statement PDFs")
    p_parse.add_argument("--output-dir", type=str, default="output", help="Directory for Monarch CSVs")

    args = parser.parse_args()

    if args.command in (None, "all"):
        years_list = None
        if hasattr(args, "years") and args.years:
            years_list = [int(y.strip()) for y in args.years.split(",") if y.strip()]

        run_pipeline(
            port=getattr(args, "port", 9222),
            output_dir=getattr(args, "output_dir", "output"),
            statement_dir=getattr(args, "statement_dir", "statements"),
            workers=getattr(args, "workers", 8),
            years=years_list,
        )
    elif args.command == "parse-statements":
        pdf_files = sorted(glob.glob(os.path.join(args.statement_dir, "*.pdf")))
        if not pdf_files:
            print(f"No statement PDFs found in '{args.statement_dir}'.", file=sys.stderr)
            sys.exit(1)

        print(f"Parsing {len(pdf_files)} statement PDFs...")
        all_parsed = []
        for p in pdf_files:
            all_parsed.extend(StatementParser.parse_pdf(p))

        accounts = aggregate_statements(all_parsed)
        exporter = Exporter(output_dir=args.output_dir)
        exporter.export_all(accounts)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
