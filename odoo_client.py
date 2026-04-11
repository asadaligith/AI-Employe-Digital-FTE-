#!/usr/bin/env python3
"""
odoo_client.py — Gold Tier Odoo JSON-RPC Client

Interface with Odoo ERP via JSON-RPC for invoices, payments, and contacts.
Uses only stdlib (urllib.request, json).

Config section in config.json:
    "odoo": {
        "enabled": false,
        "url": "https://your-odoo-instance.com",
        "database": "your-db",
        "username": "admin",
        "password": "your-api-key",
        "timeout": 30
    }

Usage:
    from odoo_client import OdooClient
    client = OdooClient.from_config()
    invoices = client.get_invoices(state="posted")
"""

import os
import json
import urllib.request
import urllib.error
from typing import Optional

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
VAULT_DIR = SCRIPT_DIR
CONFIG_FILE = os.path.join(VAULT_DIR, "config.json")


class OdooError(Exception):
    """Raised when an Odoo JSON-RPC call fails."""
    pass


class OdooClient:
    """Odoo JSON-RPC client for ERP operations."""

    def __init__(self, url: str, database: str, username: str,
                 password: str, timeout: int = 30):
        self.url = url.rstrip("/")
        self.database = database
        self.username = username
        self.password = password
        self.timeout = timeout
        self.uid = None
        self._request_id = 0

    @classmethod
    def from_config(cls) -> "OdooClient":
        """Create an OdooClient from config.json."""
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as fh:
                config = json.load(fh)
        except (OSError, json.JSONDecodeError) as exc:
            raise OdooError(f"Cannot load config.json: {exc}")

        odoo_cfg = config.get("odoo", {})
        if not odoo_cfg.get("enabled"):
            raise OdooError("Odoo integration is disabled in config.json")

        return cls(
            url=odoo_cfg.get("url", ""),
            database=odoo_cfg.get("database", ""),
            username=odoo_cfg.get("username", ""),
            password=odoo_cfg.get("password", ""),
            timeout=odoo_cfg.get("timeout", 30),
        )

    def _next_id(self) -> int:
        self._request_id += 1
        return self._request_id

    def _jsonrpc(self, endpoint: str, service: str, method: str,
                 args: list) -> dict:
        """Make a JSON-RPC call to Odoo."""
        url = f"{self.url}{endpoint}"
        payload = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": "call",
            "params": {
                "service": service,
                "method": method,
                "args": args,
            },
        }

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
        )

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                result = json.loads(resp.read().decode("utf-8"))
        except urllib.error.URLError as exc:
            raise OdooError(f"Connection failed: {exc}")
        except json.JSONDecodeError as exc:
            raise OdooError(f"Invalid JSON response: {exc}")

        if "error" in result:
            err = result["error"]
            msg = err.get("data", {}).get("message", err.get("message", str(err)))
            raise OdooError(f"Odoo error: {msg}")

        return result.get("result")

    def authenticate(self) -> int:
        """Authenticate with Odoo and store UID.

        Returns:
            User ID (uid) on success.

        Raises:
            OdooError on authentication failure.
        """
        if not self.url:
            raise OdooError("Odoo URL not configured")
        if not self.database:
            raise OdooError("Odoo database not configured")

        result = self._jsonrpc(
            "/jsonrpc", "common", "login",
            [self.database, self.username, self.password],
        )

        if not result:
            raise OdooError("Authentication failed — check credentials")

        self.uid = result
        return self.uid

    def _ensure_auth(self) -> None:
        """Authenticate if not already done."""
        if self.uid is None:
            self.authenticate()

    def execute_kw(self, model: str, method: str, args: list,
                   kwargs: dict = None) -> any:
        """Generic Odoo ORM execute_kw call."""
        self._ensure_auth()

        return self._jsonrpc(
            "/jsonrpc", "object", "execute_kw",
            [self.database, self.uid, self.password,
             model, method, args, kwargs or {}],
        )

    def search_read(self, model: str, domain: list = None,
                    fields: list = None, limit: int = 100,
                    order: str = "") -> list:
        """Search and read records from an Odoo model."""
        self._ensure_auth()

        kwargs = {}
        if fields:
            kwargs["fields"] = fields
        if limit:
            kwargs["limit"] = limit
        if order:
            kwargs["order"] = order

        return self.execute_kw(
            model, "search_read",
            [domain or []],
            kwargs,
        )

    def create(self, model: str, values: dict) -> int:
        """Create a record. Returns the new record ID."""
        self._ensure_auth()
        return self.execute_kw(model, "create", [values])

    def write(self, model: str, ids: list, values: dict) -> bool:
        """Update records. Returns True on success."""
        self._ensure_auth()
        return self.execute_kw(model, "write", [ids, values])

    # ------------------------------------------------------------------
    # Convenience methods
    # ------------------------------------------------------------------

    def get_invoices(self, state: str = None, limit: int = 20) -> list:
        """List invoices (account.move with move_type in/out_invoice).

        Args:
            state: Filter by state (draft, posted, cancel). None for all.
            limit: Max records to return.

        Returns:
            List of invoice dicts.
        """
        domain = [("move_type", "in", ["out_invoice", "in_invoice"])]
        if state:
            domain.append(("state", "=", state))

        return self.search_read(
            "account.move",
            domain=domain,
            fields=["name", "partner_id", "move_type", "state",
                     "amount_total", "amount_residual", "invoice_date",
                     "invoice_date_due", "currency_id"],
            limit=limit,
            order="invoice_date desc",
        )

    def get_payments(self, limit: int = 20) -> list:
        """List payments (account.payment)."""
        return self.search_read(
            "account.payment",
            fields=["name", "partner_id", "payment_type", "state",
                     "amount", "date", "currency_id", "journal_id"],
            limit=limit,
            order="date desc",
        )

    def get_contacts(self, limit: int = 50) -> list:
        """List contacts (res.partner)."""
        return self.search_read(
            "res.partner",
            domain=[("is_company", "=", True)],
            fields=["name", "email", "phone", "city", "country_id",
                     "customer_rank", "supplier_rank"],
            limit=limit,
            order="name asc",
        )

    def create_invoice(self, partner_id: int, lines: list) -> dict:
        """Create a draft customer invoice.

        Args:
            partner_id: Odoo partner ID.
            lines: List of {"product_id": int, "quantity": float,
                    "price_unit": float, "name": str}.

        Returns:
            {"invoice_id": int, "name": str}
        """
        invoice_lines = []
        for line in lines:
            invoice_lines.append((0, 0, {
                "product_id": line.get("product_id"),
                "quantity": line.get("quantity", 1),
                "price_unit": line.get("price_unit", 0),
                "name": line.get("name", ""),
            }))

        invoice_id = self.create("account.move", {
            "move_type": "out_invoice",
            "partner_id": partner_id,
            "invoice_line_ids": invoice_lines,
        })

        # Read back the name
        invoices = self.search_read(
            "account.move",
            domain=[("id", "=", invoice_id)],
            fields=["name"],
            limit=1,
        )

        name = invoices[0]["name"] if invoices else f"INV/{invoice_id}"
        return {"invoice_id": invoice_id, "name": name}

    def get_financial_summary(self) -> dict:
        """Get aggregated financial summary.

        Returns:
            {
                "total_receivable": float,
                "total_payable": float,
                "overdue_amount": float,
                "invoice_count": int,
                "payment_count": int,
                "currency": str
            }
        """
        # Receivable invoices (customer)
        out_invoices = self.search_read(
            "account.move",
            domain=[
                ("move_type", "=", "out_invoice"),
                ("state", "=", "posted"),
            ],
            fields=["amount_total", "amount_residual", "invoice_date_due",
                     "currency_id"],
            limit=500,
        )

        # Payable invoices (vendor)
        in_invoices = self.search_read(
            "account.move",
            domain=[
                ("move_type", "=", "in_invoice"),
                ("state", "=", "posted"),
            ],
            fields=["amount_total", "amount_residual", "invoice_date_due"],
            limit=500,
        )

        # Payments
        payments = self.search_read(
            "account.payment",
            domain=[("state", "=", "posted")],
            fields=["amount"],
            limit=500,
        )

        total_receivable = sum(inv.get("amount_residual", 0) for inv in out_invoices)
        total_payable = sum(inv.get("amount_residual", 0) for inv in in_invoices)

        # Overdue: invoices past due date with remaining balance
        from datetime import date
        today = date.today().isoformat()
        overdue = sum(
            inv.get("amount_residual", 0)
            for inv in out_invoices
            if inv.get("invoice_date_due") and inv["invoice_date_due"] < today
               and inv.get("amount_residual", 0) > 0
        )

        currency = "USD"
        if out_invoices and out_invoices[0].get("currency_id"):
            cur = out_invoices[0]["currency_id"]
            if isinstance(cur, (list, tuple)) and len(cur) > 1:
                currency = cur[1]

        return {
            "total_receivable": round(total_receivable, 2),
            "total_payable": round(total_payable, 2),
            "overdue_amount": round(overdue, 2),
            "invoice_count": len(out_invoices) + len(in_invoices),
            "payment_count": len(payments),
            "currency": currency,
        }


# ---------------------------------------------------------------------------
# CLI self-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    if "--test" in sys.argv:
        print("odoo_client.py — dry-run self-test")
        print("Checking config...")
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as fh:
                config = json.load(fh)
            odoo_cfg = config.get("odoo", {})
            if not odoo_cfg.get("enabled"):
                print("Odoo is disabled in config.json — test passed (no connection)")
            else:
                client = OdooClient.from_config()
                print(f"Config loaded: url={client.url}, db={client.database}")
                print("Would authenticate and query — skipping in test mode")
        except (OSError, json.JSONDecodeError) as exc:
            print(f"Config not available: {exc}")
        print("OK")
    else:
        print("Usage: python odoo_client.py --test")
