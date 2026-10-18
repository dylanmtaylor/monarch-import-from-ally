"""Unit tests for AllyClient API interactions using mocks."""

import unittest
from unittest.mock import patch, MagicMock
import urllib.error
import io
import json

from ally_to_monarch.api import AllyClient, AllyAPIError


class TestAllyClient(unittest.TestCase):
    """Test suite for Ally ACS client."""

    def setUp(self):
        self.client = AllyClient(token="mock_token_123", api_key="mock_key_abc", customer_id="123456789")

    def test_headers_construction(self):
        """Test API headers construction."""
        headers = self.client._get_headers()
        self.assertEqual(headers["Authorization"], "Bearer mock_token_123")
        self.assertEqual(headers["api-key"], "mock_key_abc")
        self.assertEqual(headers["Accept"], "application/json")

    @patch("urllib.request.urlopen")
    def test_get_customer_profile_success(self, mock_urlopen):
        """Test fetching customer profile."""
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({"data": {"id": "987654321", "name": {"first": "Jane"}}}).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        client = AllyClient(token="test_tok")
        profile = client.get_customer_profile()
        self.assertEqual(profile["data"]["id"], "987654321")
        self.assertEqual(client.customer_id, "987654321")

    @patch("urllib.request.urlopen")
    def test_get_statements_list_ignores_out_of_range(self, mock_urlopen):
        """Test that get_statements_list gracefully ignores 400 HTTP errors for out of range years."""
        # Year 2026 succeeds, Year 2019 raises 400
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({"statements": [{"documentId": "doc123"}]}).encode("utf-8")

        def side_effect(req, timeout=15):
            url = req.full_url
            if "year=2026" in url:
                cm = MagicMock()
                cm.__enter__.return_value = mock_resp
                return cm
            else:
                err = urllib.error.HTTPError(url, 400, "Bad Request", {}, io.BytesIO(b'{"error":"out of range"}'))
                raise err

        mock_urlopen.side_effect = side_effect

        results = self.client.get_statements_list(years=[2026, 2019])
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["documentId"], "doc123")
        self.assertEqual(results[0]["year"], 2026)

    @patch("urllib.request.urlopen")
    def test_download_statement_pdf_error(self, mock_urlopen):
        """Test API error handling when statement download fails."""
        mock_urlopen.side_effect = urllib.error.HTTPError(
            "https://secure.ally.com/acs/v1/bank-statements/invalid",
            404,
            "Not Found",
            {},
            io.BytesIO(b"Document not found"),
        )
        with self.assertRaises(AllyAPIError) as ctx:
            self.client.download_statement_pdf("invalid")
        self.assertIn("HTTP 404", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
