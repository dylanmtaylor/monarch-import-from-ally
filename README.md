# monarch-import-from-ally

Automated extraction and conversion tool for **Ally Bank** accounts (Savings, Checking, CDs, and Matured/Closed accounts) into **Monarch Money**-compatible CSV imports.

Connects to an authenticated Ally Bank session in Google Chrome via Chrome DevTools Protocol (CDP), captures active session tokens and statement archives, parses combined customer statement PDFs via PyMuPDF (`fitz`), and exports:
1. **Continuous Daily Balance History** (`Date,Balance`) across all calendar days back to account inception, integrating verified statement checkpoints.
2. **Standard Transactions** (`Date,Merchant,Category,Account,Original Statement,Notes,Amount`) with automatic merchant cleaning and categorization for **Transfers**, **Interest Paid**, and **Direct Deposits**.
3. **Full Account Coverage**: Seamlessly includes **ALL accounts**, including active accounts (e.g. Online Savings) and archived/matured accounts (e.g. No Penalty CDs) that no longer appear on online transaction searches.

---

## Features

- **Multi-Account & Closed Account Support**:
  - Automatically identifies all accounts appearing in Ally's Combined Customer Statements (Savings Accounts, Certificates of Deposit, Checking, etc.).
  - Extracts full historical activity even after accounts mature or close.
- **Overcomes Online Archival Limits**:
  - Ally archives online transaction search after ~90-120 days. This tool taps directly into Ally's 7-year document archive (`/acs/v1/bank-statements`) to extract exact statement transactions and ending balances.
- **Continuous Daily Balance Interpolation**:
  - Reconstructs uninterrupted daily balances forward-filled from account open date up to the present day, perfectly aligning with statement checkpoints.
- **Chrome CDP Session Extraction**:
  - Reuses your active, authenticated Chrome browser session via CDP (port `9222`) without requiring credential storage or password exposure.
- **Monarch Money Import Ready**:
  - Strict compliance with Monarch's CSV specifications for Balances (`Date,Balance`) and Transactions (`Date,Merchant,Category,Account,Original Statement,Notes,Amount`).
- **Zero PII Committed**:
  - All account numbers, financial amounts, raw JSON captures, PDF statements, and CSV exports are safely excluded via `.gitignore`.

---

## Installation

```bash
git clone https://github.com/dylanmtaylor/monarch-import-from-ally.git
cd monarch-import-from-ally
pip install -e .
```

### Dependencies
- Python 3.9+
- `pymupdf>=1.20.0`
- `websocket-client>=1.6.0`

---

## Quickstart

### 1. Launch Chrome with Remote Debugging
Ensure Chrome is running with `--remote-debugging-port=9222` and log into [Ally Bank](https://secure.ally.com):

```bash
google-chrome --remote-debugging-port=9222
# or on Flatpak:
flatpak run com.google.Chrome --remote-debugging-port=9222
```

### 2. Run Capture & Convert
Run the automated pipeline to capture statement PDFs, parse account transactions, and generate Monarch CSVs:

```bash
ally-to-monarch all
# or directly via python:
python3 -m ally_to_monarch.cli all
```

To re-parse already downloaded statement PDFs without hitting the network:

```bash
ally-to-monarch parse-statements --statement-dir statements --output-dir output
```

---

## Output Files

The tool generates separate CSVs for each account in the `output/` directory:

| File | Type | Description |
|---|---|---|
| `output/ally_balances_<account_slug>.csv` | Balances | Daily balance series (`Date,Balance`) forward-filled from inception to today. |
| `output/ally_transactions_<account_slug>.csv` | Transactions | Account-specific transactions formatted for Monarch Money. |
| `output/ally_transactions_all.csv` | Combined | All transactions across all Ally accounts sorted chronologically. |

---

## Importing into Monarch Money

1. **Daily Balances**:
   - Go to **Accounts** in Monarch Money.
   - Select your Ally account (or create a manual account if importing historical/closed accounts like a CD).
   - Click **Edit** -> **Upload balance history** and upload `output/ally_balances_<account_slug>.csv`.
2. **Transactions**:
   - In the account page, click **Edit** -> **Upload transactions** and select `output/ally_transactions_<account_slug>.csv` (or the combined `output/ally_transactions_all.csv`).

---

## Testing

Run the unit test suite (100% synthetic fixtures, zero network or PII dependencies):

```bash
python3 -m unittest discover tests -v
```

---

## License

MIT License. See [LICENSE](LICENSE) for details.
