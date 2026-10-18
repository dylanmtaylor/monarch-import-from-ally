"""Ally Bank ACS API Client."""

import json
import os
import urllib.request
import urllib.error
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any, Optional

DEFAULT_API_KEY = "XhnbsDYmBensf2vqVXAfv0uD7SJBA27u"
BASE_URL = "https://secure.ally.com"


class AllyAPIError(Exception):
    """Raised when an API call fails."""
    pass


class AllyClient:
    """Client for Ally Bank ACS REST endpoints."""

    def __init__(self, token: str, api_key: str = DEFAULT_API_KEY, customer_id: Optional[str] = None):
        self.token = token
        self.api_key = api_key
        self.customer_id = customer_id

    def _get_headers(self, accept: str = "application/json") -> Dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": accept,
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/155.0.0.0 Safari/537.36",
        }
        if self.api_key:
            headers["api-key"] = self.api_key
        return headers

    def get_customer_profile(self) -> Dict[str, Any]:
        """Fetch customer profile from /acs/v3/customers/self."""
        url = f"{BASE_URL}/acs/v3/customers/self?addFields=etin"
        req = urllib.request.Request(url, headers=self._get_headers())
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                if not self.customer_id and "data" in data and "id" in data["data"]:
                    self.customer_id = data["data"]["id"]
                return data
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="ignore")
            raise AllyAPIError(f"Failed to fetch customer profile: HTTP {e.code} - {err_body}")

    def get_transfer_accounts(self) -> List[Dict[str, Any]]:
        """Fetch accounts list from /acs/v1/customer-transfers/transfer-accounts."""
        if not self.customer_id:
            self.get_customer_profile()

        url = f"{BASE_URL}/acs/v1/customer-transfers/transfer-accounts?customerId={self.customer_id}"
        req = urllib.request.Request(url, headers=self._get_headers())
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data.get("accounts", [])
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="ignore")
            raise AllyAPIError(f"Failed to fetch transfer accounts: HTTP {e.code} - {err_body}")

    def get_bank_account_detail(self, account_index: str) -> Dict[str, Any]:
        """Fetch detailed info for an account from /acs/v1/bank-accounts/{index}."""
        url = f"{BASE_URL}/acs/v1/bank-accounts/{account_index}?include=accountAddress"
        req = urllib.request.Request(url, headers=self._get_headers())
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="ignore")
            raise AllyAPIError(f"Failed to fetch account detail: HTTP {e.code} - {err_body}")

    def get_statements_list(self, years: Optional[List[int]] = None) -> List[Dict[str, Any]]:
        """Fetch statement metadata for available years (typically up to 7 years back)."""
        if years is None:
            current_year = datetime.now().year
            # Check up to 8 years back
            years = list(range(current_year, current_year - 8, -1))

        all_statements = []
        for year in years:
            url = f"{BASE_URL}/acs/v1/bank-statements?docType=STATEMENTS&year={year}"
            req = urllib.request.Request(url, headers=self._get_headers())
            try:
                with urllib.request.urlopen(req, timeout=15) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    stmts = data.get("statements", [])
                    for s in stmts:
                        s["year"] = year
                        all_statements.append(s)
            except urllib.error.HTTPError as e:
                # 400 with USB_COM_503 means year is out of valid range (older than 7 years)
                if e.code == 400:
                    continue
                err_body = e.read().decode("utf-8", errors="ignore")
                raise AllyAPIError(f"Failed to fetch statements for {year}: HTTP {e.code} - {err_body}")

        return all_statements

    def download_statement_pdf(self, document_id: str, output_path: Optional[str] = None) -> bytes:
        """Download a statement PDF by documentId."""
        url = f"{BASE_URL}/acs/v1/bank-statements/{document_id}"
        req = urllib.request.Request(url, headers=self._get_headers(accept="application/pdf"))
        try:
            with urllib.request.urlopen(req, timeout=25) as resp:
                content = resp.read()
                if output_path:
                    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
                    with open(output_path, "wb") as f:
                        f.write(content)
                return content
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="ignore")
            raise AllyAPIError(f"Failed to download statement {document_id}: HTTP {e.code} - {err_body}")

    def download_all_statements(
        self,
        statements_meta: List[Dict[str, Any]],
        output_dir: str,
        max_workers: int = 8
    ) -> List[str]:
        """Download all statement PDFs concurrently into output_dir."""
        os.makedirs(output_dir, exist_ok=True)
        downloaded_paths = []

        def _download_single(meta: Dict[str, Any]) -> str:
            doc_id = meta["documentId"]
            path = os.path.join(output_dir, f"{doc_id}.pdf")
            if os.path.exists(path) and os.path.getsize(path) > 0:
                return path
            self.download_statement_pdf(doc_id, output_path=path)
            return path

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_meta = {executor.submit(_download_single, s): s for s in statements_meta}
            for future in as_completed(future_to_meta):
                path = future.result()
                downloaded_paths.append(path)

        return sorted(downloaded_paths)
