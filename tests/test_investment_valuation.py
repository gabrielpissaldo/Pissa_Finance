import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient

from app import database
from app.main import app


class InvestmentValuationTests(unittest.TestCase):
    def setUp(self):
        self.today = datetime.now(ZoneInfo("America/Sao_Paulo")).date()
        self.directory = tempfile.TemporaryDirectory()
        self.db_path = Path(self.directory.name) / "finance.db"
        self.path_patch = patch.object(database, "DATABASE_PATH", self.db_path)
        self.path_patch.start()
        self.client_context = TestClient(app)
        self.client = self.client_context.__enter__()

    def tearDown(self):
        self.client_context.__exit__(None, None, None)
        self.path_patch.stop()
        self.directory.cleanup()

    def create_fixed(self, *, amount=1000, started_at=None,
                     fixed_rate: float | None = 10, rate_type="prefixed",
                     rate_modifier=None, maturity_date=None):
        started_at = started_at or self.today.isoformat()
        response = self.client.post("/api/investments/", json={
            "name": "Prefixado teste",
            "investment_type": "fixed_income",
            "amount_invested": amount,
            "started_at": started_at,
            "rate_type": rate_type,
            "rate_modifier": rate_modifier,
            "fixed_rate": fixed_rate,
            "maturity_date": maturity_date
        })
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()["id"]

    def create_market(self, *, amount=1000):
        response = self.client.post("/api/investments/", json={
            "name": "Ativo teste",
            "investment_type": "market_investment",
            "amount_invested": amount,
            "started_at": self.today.isoformat(),
            "asset_type": "stock",
            "symbol": "TEST",
            "quantity": 10,
            "average_price": amount / 10
        })
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()["id"]

    def investment(self, investment_id):
        response = self.client.get("/api/investments/")
        self.assertEqual(response.status_code, 200, response.text)
        return next(row for row in response.json() if row["id"] == investment_id)

    def withdraw(self, investment_id, *, amount, principal_amount=None,
                 quantity=None, withdrawal_date=None):
        payload = {
            "amount": amount,
            "withdrawal_date": withdrawal_date or self.today.isoformat()
        }
        if principal_amount is not None:
            payload["principal_amount"] = principal_amount
        if quantity is not None:
            payload["quantity"] = quantity
        return self.client.post(
            f"/api/investments/{investment_id}/withdrawals", json=payload
        )

    def test_prefixed_position_without_withdrawals_is_valued(self):
        started_at = (self.today - timedelta(days=365)).isoformat()
        investment_id = self.create_fixed(started_at=started_at)

        position = self.investment(investment_id)

        self.assertEqual(position["amount_invested"], 1000)
        self.assertEqual(position["valuation_status"], "available")
        self.assertEqual(position["valuation_as_of"], self.today.isoformat())
        self.assertAlmostEqual(position["current_value"], 1100, places=7)
        self.assertAlmostEqual(position["unrealized_profit_loss"], 100, places=7)
        self.assertAlmostEqual(position["unrealized_return_percent"], 10, places=7)
        self.assertEqual(position["realized_profit_loss"], 0)
        self.assertAlmostEqual(position["total_profit_loss"], 100, places=7)
        self.assertAlmostEqual(position["total_return_percent"], 10, places=7)

    def test_prefixed_valuation_tracks_contribution_dates_and_partial_withdrawals(self):
        started_at = (self.today - timedelta(days=730)).isoformat()
        contribution_date = (self.today - timedelta(days=365)).isoformat()
        investment_id = self.create_fixed(started_at=started_at)
        contribution = self.client.post(
            f"/api/investments/{investment_id}/contributions",
            json={"amount": 500, "contribution_date": contribution_date}
        )
        self.assertEqual(contribution.status_code, 200, contribution.text)

        first = self.withdraw(
            investment_id, amount=550, principal_amount=500
        )
        self.assertEqual(first.status_code, 200, first.text)
        position = self.investment(investment_id)
        self.assertAlmostEqual(position["current_value"], 1210, places=7)
        self.assertEqual(position["amount_invested"], 1000)
        self.assertAlmostEqual(position["realized_profit_loss"], 50, places=7)
        self.assertAlmostEqual(position["unrealized_profit_loss"], 210, places=7)
        self.assertAlmostEqual(position["total_profit_loss"], 260, places=7)
        self.assertAlmostEqual(position["total_return_percent"], 260 / 1500 * 100, places=7)

        second = self.withdraw(
            investment_id, amount=110, principal_amount=100
        )
        self.assertEqual(second.status_code, 200, second.text)
        position = self.investment(investment_id)
        self.assertEqual(position["amount_invested"], 900)
        self.assertAlmostEqual(position["current_value"], 1100, places=7)
        self.assertAlmostEqual(position["realized_profit_loss"], 60, places=7)
        self.assertAlmostEqual(position["unrealized_profit_loss"], 200, places=7)
        self.assertAlmostEqual(position["total_profit_loss"], 260, places=7)

    def test_closed_prefixed_position_has_no_unrealized_value(self):
        started_at = (self.today - timedelta(days=365)).isoformat()
        investment_id = self.create_fixed(started_at=started_at)
        withdrawal = self.withdraw(
            investment_id, amount=1100, principal_amount=1000
        )
        self.assertEqual(withdrawal.status_code, 200, withdrawal.text)

        position = self.investment(investment_id)

        self.assertEqual(position["status"], "closed")
        self.assertEqual(position["amount_invested"], 0)
        self.assertEqual(position["valuation_status"], "closed")
        self.assertEqual(position["current_value"], 0)
        self.assertEqual(position["unrealized_profit_loss"], 0)
        self.assertIsNone(position["unrealized_return_percent"])
        self.assertAlmostEqual(position["realized_profit_loss"], 100, places=7)
        self.assertAlmostEqual(position["total_profit_loss"], 100, places=7)
        self.assertAlmostEqual(position["total_return_percent"], 10, places=7)

    def test_maturity_caps_prefixed_accrual(self):
        maturity_date = (self.today - timedelta(days=365)).isoformat()
        started_at = (self.today - timedelta(days=730)).isoformat()
        investment_id = self.create_fixed(
            started_at=started_at, maturity_date=maturity_date
        )

        position = self.investment(investment_id)

        self.assertEqual(position["valuation_status"], "available")
        self.assertAlmostEqual(position["current_value"], 1100, places=7)

    def test_market_withdrawal_reports_realized_gain_without_fabricated_quote(self):
        investment_id = self.create_market()
        withdrawal = self.withdraw(
            investment_id, amount=350, quantity=3
        )
        self.assertEqual(withdrawal.status_code, 200, withdrawal.text)

        position = self.investment(investment_id)

        self.assertEqual(position["valuation_status"], "pending_quote")
        self.assertIsNone(position["current_value"])
        self.assertIsNone(position["unrealized_profit_loss"])
        self.assertIsNone(position["unrealized_return_percent"])
        self.assertAlmostEqual(position["realized_profit_loss"], 50, places=7)
        self.assertIsNone(position["total_profit_loss"])
        self.assertIsNone(position["total_return_percent"])

    def test_indexed_fixed_income_waits_for_external_index(self):
        started_at = (self.today - timedelta(days=365)).isoformat()
        for rate_type, modifier in (("cdi", 110), ("selic", 100), ("ipca", 6)):
            with self.subTest(rate_type=rate_type):
                investment_id = self.create_fixed(
                    started_at=started_at,
                    rate_type=rate_type,
                    fixed_rate=None,
                    rate_modifier=modifier
                )
                position = self.investment(investment_id)
                self.assertEqual(position["valuation_status"], "pending_external_index")
                self.assertIsNone(position["current_value"])
                self.assertIsNone(position["unrealized_profit_loss"])
                self.assertIsNone(position["unrealized_return_percent"])
                self.assertEqual(position["realized_profit_loss"], 0)
                self.assertIsNone(position["total_profit_loss"])
                self.assertIsNone(position["total_return_percent"])

    def test_valuation_read_does_not_change_dashboard_or_cash_ledger(self):
        investment_id = self.create_fixed()
        dashboard_before = self.client.get("/api/dashboard/").json()
        transactions_before = self.client.get("/api/transactions/").json()

        position = self.investment(investment_id)
        dashboard_after = self.client.get("/api/dashboard/").json()
        transactions_after = self.client.get("/api/transactions/").json()

        self.assertIn("valuation_status", position)
        self.assertEqual(dashboard_after, dashboard_before)
        self.assertEqual(transactions_after, transactions_before)
