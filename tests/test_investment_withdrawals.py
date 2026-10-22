import sqlite3
import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient

from app import database
from app.main import app


class InvestmentWithdrawalTests(unittest.TestCase):
    def setUp(self):
        self.today = datetime.now(ZoneInfo("America/Sao_Paulo")).date().isoformat()
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

    def rows(self, table, investment_id):
        with database.get_connection() as connection:
            return [dict(row) for row in connection.execute(
                f"SELECT * FROM {table} WHERE investment_id = ? ORDER BY id", (investment_id,)
            )]

    def investment(self, investment_id):
        return next(item for item in self.client.get("/api/investments/").json()
                    if item["id"] == investment_id)

    def create_fixed(self):
        response = self.client.post("/api/investments/", json={
            "name": "CDB", "investment_type": "fixed_income",
            "amount_invested": 1000, "started_at": self.today, "rate_type": "CDI"
        })
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()["id"]

    def create_market(self):
        response = self.client.post("/api/investments/", json={
            "name": "Bitcoin", "investment_type": "market_investment",
            "amount_invested": 1000, "started_at": self.today,
            "asset_type": "crypto", "symbol": "BTC", "quantity": 10,
            "average_price": 100
        })
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()["id"]

    def withdraw(self, investment_id, **kwargs):
        return self.client.post(f"/api/investments/{investment_id}/withdrawals", json={
            "amount": 250, "withdrawal_date": self.today, **kwargs
        })

    def test_migration_of_existing_db_is_idempotent_and_preserves_data(self):
        with sqlite3.connect(self.db_path) as connection:
            connection.execute("DROP TABLE investment_movements")
            connection.execute("DROP TABLE investments")
            connection.execute("CREATE TABLE investments (id INTEGER PRIMARY KEY, name TEXT, investment_type TEXT, amount_invested REAL, started_at TEXT, created_at TEXT)")
            connection.execute("CREATE TABLE investment_movements (id INTEGER PRIMARY KEY, investment_id INTEGER, transaction_id INTEGER, movement_type TEXT, amount REAL, quantity REAL, movement_date TEXT, created_at TEXT)")
            connection.execute("INSERT INTO investments VALUES (1, 'Antigo', 'fixed_income', 100, '2026-01-01', '2026-01-01')")
            connection.execute("INSERT INTO investment_movements VALUES (1, 1, NULL, 'initial_contribution', 100, NULL, '2026-01-01', '2026-01-01')")
        database.init_db()
        database.init_db()
        with database.get_connection() as connection:
            investment = connection.execute("SELECT * FROM investments WHERE id = 1").fetchone()
            movement = connection.execute("SELECT * FROM investment_movements WHERE id = 1").fetchone()
            self.assertEqual(investment["status"], "active")
            self.assertIsNone(investment["closed_at"])
            self.assertIsNone(movement["principal_amount"])
            self.assertEqual(movement["amount"], 100)

    def test_fixed_partial_withdrawal_keeps_cash_and_principal_separate(self):
        investment_id = self.create_fixed()
        response = self.withdraw(investment_id, principal_amount=400)
        self.assertEqual(response.status_code, 200, response.text)
        position = self.investment(investment_id)
        self.assertEqual((position["amount_invested"], position["status"], position["closed_at"]),
                         (600, "active", None))
        movement = self.rows("investment_movements", investment_id)[-1]
        transaction = self.rows("transactions", investment_id)[-1]
        self.assertEqual((movement["movement_type"], movement["amount"], movement["principal_amount"],
                          movement["quantity"], movement["movement_date"]),
                         ("withdrawal", 250, 400, None, self.today))
        self.assertEqual((transaction["id"], transaction["type"], transaction["amount"],
                          transaction["description"], transaction["transaction_date"]),
                         (movement["transaction_id"], "investment_withdrawal", 250,
                          "Resgate de CDB", self.today))
        dashboard = self.client.get("/api/dashboard/").json()
        self.assertEqual((dashboard["income"], dashboard["invested"], dashboard["balance"]),
                         (0, 1000, -750))
        self.assertEqual(dashboard["monthly"][-1]["value"], -750)

    def test_fixed_total_withdrawal_closes_position(self):
        investment_id = self.create_fixed()
        response = self.withdraw(investment_id, amount=1100, principal_amount=1000)
        self.assertEqual(response.status_code, 200, response.text)
        position = self.investment(investment_id)
        self.assertEqual((position["amount_invested"], position["status"], position["closed_at"]),
                         (0, "closed", self.today))
        self.assertEqual(self.client.get("/api/dashboard/").json()["balance"], 100)

    def test_market_partial_withdrawal_keeps_average_price(self):
        investment_id = self.create_market()
        response = self.withdraw(investment_id, amount=350, quantity=3)
        self.assertEqual(response.status_code, 200, response.text)
        position = self.investment(investment_id)
        self.assertEqual((position["amount_invested"], position["details"]["quantity"],
                          position["details"]["average_price"], position["status"]),
                         (700, 7, 100, "active"))
        self.assertEqual(self.rows("investment_movements", investment_id)[-1]["principal_amount"], 300)

    def test_market_total_withdrawal_zeros_position_and_closes_it(self):
        investment_id = self.create_market()
        response = self.withdraw(investment_id, amount=900, quantity=10)
        self.assertEqual(response.status_code, 200, response.text)
        position = self.investment(investment_id)
        self.assertEqual((position["amount_invested"], position["details"]["quantity"],
                          position["details"]["average_price"], position["status"], position["closed_at"]),
                         (0, 0, 0, "closed", self.today))

    def test_market_inconsistent_cost_basis_rejects_withdrawal(self):
        for average_price in (50, 200):
            with self.subTest(average_price=average_price):
                investment_id = self.create_market()
                with database.get_connection() as connection:
                    connection.execute("""
                        UPDATE market_investment_details SET average_price = ?
                        WHERE investment_id = ?
                    """, (average_price, investment_id))
                response = self.withdraw(investment_id, amount=800, quantity=10)
                self.assertEqual(response.status_code, 409, response.text)
                self.assertEqual(self.investment(investment_id)["amount_invested"], 1000)
                self.assertEqual(len(self.rows("transactions", investment_id)), 1)

    def test_small_market_amount_never_becomes_negative(self):
        investment_id = self.create_market()
        with database.get_connection() as connection:
            connection.execute("UPDATE investments SET amount_invested = 1e-9 WHERE id = ?", (investment_id,))
            connection.execute("""
                UPDATE market_investment_details SET average_price = 1e-9
                WHERE investment_id = ?
            """, (investment_id,))
        response = self.withdraw(investment_id, amount=1e-10, quantity=2)
        self.assertEqual(response.status_code, 409, response.text)
        self.assertEqual(self.investment(investment_id)["amount_invested"], 1e-9)

    def test_fixed_principal_too_small_to_change_position_is_rejected(self):
        investment_id = self.create_fixed()
        response = self.withdraw(investment_id, amount=100, principal_amount=5e-324)
        self.assertEqual(response.status_code, 400, response.text)
        self.assertEqual(self.investment(investment_id)["amount_invested"], 1000)
        self.assertEqual(len(self.rows("investment_movements", investment_id)), 1)
        self.assertEqual(len(self.rows("transactions", investment_id)), 1)

    def test_market_quantity_too_small_to_change_position_is_rejected(self):
        investment_id = self.create_market()
        response = self.withdraw(investment_id, amount=500, quantity=1e-20)
        self.assertEqual(response.status_code, 400, response.text)
        self.assertEqual(self.investment(investment_id)["details"]["quantity"], 10)
        self.assertEqual(len(self.rows("investment_movements", investment_id)), 1)
        self.assertEqual(len(self.rows("transactions", investment_id)), 1)

    def test_contribution_cannot_be_backdated_before_withdrawal(self):
        investment_id = self.create_market()
        tomorrow = (date.fromisoformat(self.today) + timedelta(days=1)).isoformat()
        self.assertEqual(self.withdraw(investment_id, quantity=2, withdrawal_date=tomorrow).status_code, 200)
        response = self.client.post(f"/api/investments/{investment_id}/contributions", json={
            "amount": 50, "quantity": 1, "contribution_date": self.today
        })
        self.assertEqual(response.status_code, 400, response.text)
        self.assertEqual(self.investment(investment_id)["details"]["quantity"], 8)
        self.assertEqual(len(self.rows("transactions", investment_id)), 2)

    def test_new_contribution_after_partial_withdrawal_can_be_withdrawn(self):
        investment_id = self.create_market()
        self.assertEqual(self.withdraw(investment_id, quantity=2).status_code, 200)
        tomorrow = (date.fromisoformat(self.today) + timedelta(days=1)).isoformat()
        response = self.client.post(f"/api/investments/{investment_id}/contributions", json={
            "amount": 200, "quantity": 2, "contribution_date": tomorrow
        })
        self.assertEqual(response.status_code, 200, response.text)
        position = self.investment(investment_id)
        self.assertEqual((position["amount_invested"], position["details"]["quantity"],
                          position["details"]["average_price"]), (1000, 10, 100))
        response = self.withdraw(investment_id, quantity=10, withdrawal_date=tomorrow)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(self.rows("investment_movements", investment_id)[-1]["principal_amount"], 1000)
        self.assertEqual(self.investment(investment_id)["status"], "closed")

    def test_consistent_small_market_position_remains_positive_after_partial_withdrawal(self):
        investment_id = self.create_market()
        with database.get_connection() as connection:
            connection.execute("UPDATE investments SET amount_invested = 1e-9 WHERE id = ?", (investment_id,))
            connection.execute("""
                UPDATE market_investment_details SET average_price = 1e-10
                WHERE investment_id = ?
            """, (investment_id,))
        response = self.withdraw(investment_id, amount=1e-10, quantity=2)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertGreater(self.investment(investment_id)["amount_invested"], 0)

    def test_invalid_withdrawal_date_and_backdated_withdrawal_are_rejected(self):
        investment_id = self.create_fixed()
        yesterday = (date.fromisoformat(self.today) - timedelta(days=1)).isoformat()
        for invalid_date in ("not-a-date", "2026-02-30", yesterday):
            with self.subTest(invalid_date=invalid_date):
                response = self.withdraw(investment_id, principal_amount=100,
                                         withdrawal_date=invalid_date)
                self.assertEqual(response.status_code, 400, response.text)
                self.assertEqual(self.investment(investment_id)["amount_invested"], 1000)
                self.assertEqual(len(self.rows("transactions", investment_id)), 1)

    def test_closed_investment_cannot_receive_contribution_or_withdrawal(self):
        investment_id = self.create_fixed()
        self.withdraw(investment_id, principal_amount=1000)
        contribution = self.client.post(f"/api/investments/{investment_id}/contributions", json={
            "amount": 50, "contribution_date": "2026-10-23"
        })
        self.assertEqual(contribution.status_code, 409)
        self.assertEqual(self.withdraw(investment_id, principal_amount=1).status_code, 409)
        self.assertEqual(len(self.rows("investment_movements", investment_id)), 2)

    def test_linked_transactions_cannot_be_updated_or_deleted_generically(self):
        investment_id = self.create_fixed()
        self.withdraw(investment_id, principal_amount=100)
        original = self.rows("transactions", investment_id)
        for transaction in original:
            transaction_id = transaction["id"]
            updated = self.client.put(f"/api/transactions/{transaction_id}", json={
                "description": "Changed", "amount": 1, "type": "income",
                "transaction_date": self.today
            })
            deleted = self.client.delete(f"/api/transactions/{transaction_id}")
            self.assertEqual(updated.status_code, 409, updated.text)
            self.assertEqual(deleted.status_code, 409, deleted.text)
            self.assertIn("investment", updated.json()["detail"].lower())
        self.assertEqual(self.rows("transactions", investment_id), original)
        self.assertEqual(self.client.delete("/api/transactions/99999").status_code, 404)

    def test_unlinked_transactions_can_still_be_updated_and_deleted(self):
        transaction_id = self.client.post("/api/transactions/", json={
            "description": "Other", "amount": 10, "type": "income", "transaction_date": self.today
        }).json()["id"]
        response = self.client.put(f"/api/transactions/{transaction_id}", json={
            "description": "Updated", "amount": 20, "type": "income", "transaction_date": self.today
        })
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(self.client.delete(f"/api/transactions/{transaction_id}").status_code, 200)

    def test_generic_transaction_post_cannot_forge_withdrawal(self):
        response = self.client.post("/api/transactions/", json={
            "description": "Fake withdrawal", "amount": 1000000,
            "type": "investment_withdrawal", "transaction_date": self.today
        })
        self.assertEqual(response.status_code, 400, response.text)
        self.assertEqual(self.client.get("/api/transactions/").json(), [])
        self.assertEqual(self.client.get("/api/dashboard/").json()["balance"], 0)

    def test_generic_transaction_put_cannot_forge_withdrawal(self):
        transaction_id = self.client.post("/api/transactions/", json={
            "description": "Other", "amount": 10, "type": "income",
            "transaction_date": self.today
        }).json()["id"]
        response = self.client.put(f"/api/transactions/{transaction_id}", json={
            "description": "Fake withdrawal", "amount": 1000000,
            "type": "investment_withdrawal", "transaction_date": self.today
        })
        self.assertEqual(response.status_code, 400, response.text)
        self.assertEqual(self.client.get("/api/dashboard/").json()["balance"], 10)

    def test_invalid_withdrawals_do_not_write_history(self):
        fixed = self.create_fixed()
        market = self.create_market()
        cases = [
            (fixed, {"amount": 0, "principal_amount": 1}),
            (fixed, {"principal_amount": None}),
            (fixed, {"principal_amount": 1001}),
            (fixed, {"principal_amount": 10, "quantity": 1}),
            (market, {}),
            (market, {"quantity": 0}),
            (market, {"quantity": 11}),
            (market, {"quantity": 1, "principal_amount": 1}),
        ]
        for investment_id, payload in cases:
            with self.subTest(payload=payload):
                response = self.withdraw(investment_id, **payload)
                self.assertEqual(response.status_code, 400, response.text)
                self.assertEqual(len(self.rows("investment_movements", investment_id)), 1)
                self.assertEqual(len(self.rows("transactions", investment_id)), 1)
        self.assertEqual(self.withdraw(99999, principal_amount=1).status_code, 404)

    def test_failure_writing_movement_rolls_back_position_and_transaction(self):
        investment_id = self.create_fixed()
        with database.get_connection() as connection:
            connection.execute("""CREATE TRIGGER reject_withdrawal BEFORE INSERT ON investment_movements
                WHEN NEW.movement_type = 'withdrawal' BEGIN SELECT RAISE(ABORT, 'test failure'); END""")
        with self.assertRaises(sqlite3.IntegrityError):
            self.withdraw(investment_id, principal_amount=100)
        self.assertEqual(self.investment(investment_id)["amount_invested"], 1000)
        self.assertEqual(len(self.rows("transactions", investment_id)), 1)
        self.assertEqual(len(self.rows("investment_movements", investment_id)), 1)

    def test_historical_contributions_cannot_rewrite_withdrawn_position(self):
        investment_id = self.create_fixed()
        contribution = self.client.post(f"/api/investments/{investment_id}/contributions", json={
            "amount": 200, "contribution_date": "2026-10-02"
        }).json()
        self.withdraw(investment_id, principal_amount=100)
        movement_id = contribution["movement_id"]
        response = self.client.put(f"/api/investments/{investment_id}/contributions/{movement_id}", json={
            "amount": 300, "contribution_date": "2026-10-02"
        })
        self.assertEqual(response.status_code, 409)
        self.assertEqual(self.client.delete(
            f"/api/investments/{investment_id}/contributions/{movement_id}").status_code, 409)
        self.assertEqual(self.investment(investment_id)["amount_invested"], 1100)

    def test_investment_update_cannot_reset_withdrawn_position(self):
        investment_id = self.create_market()
        self.assertEqual(self.withdraw(investment_id, quantity=2).status_code, 200)
        response = self.client.put(f"/api/investments/{investment_id}", json={
            "name": "Bitcoin", "investment_type": "market_investment",
            "amount_invested": 1000, "started_at": self.today,
            "asset_type": "crypto", "symbol": "BTC", "quantity": 10,
            "average_price": 100
        })
        self.assertEqual(response.status_code, 409)
        self.assertEqual(self.investment(investment_id)["details"]["quantity"], 8)

    def test_investment_deletion_removes_withdrawal_transactions(self):
        investment_id = self.create_market()
        self.assertEqual(self.withdraw(investment_id, quantity=2).status_code, 200)
        self.assertEqual(len(self.rows("transactions", investment_id)), 2)
        self.assertEqual(self.client.delete(f"/api/investments/{investment_id}").status_code, 200)
        self.assertEqual(self.rows("transactions", investment_id), [])
        self.assertEqual(self.rows("investment_movements", investment_id), [])


if __name__ == "__main__":
    unittest.main()
