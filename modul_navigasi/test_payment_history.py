import unittest
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

from flask import Flask

from app import app as production_app
from modul_navigasi.routes import (
    api_payment_event_create,
    api_payment_event_delete,
    api_payment_events_list,
    api_payment_monitoring_upsert,
)


class FakeReadCursor:
    def __init__(self, rows):
        self.rows = iter(rows)
        self.calls = []

    def execute(self, sql, params):
        self.calls.append((sql, params))

    def fetchone(self):
        return next(self.rows)

    def fetchall(self):
        return next(self.rows)

    def close(self):
        pass


class FakeWriteCursor:
    lastrowid = 17
    rowcount = 1

    def __init__(self):
        self.calls = []

    def execute(self, sql, params):
        self.calls.append((sql, params))

    def close(self):
        pass


class FakeConnection:
    def __init__(self, rows):
        self.read = FakeReadCursor(rows)
        self.write = FakeWriteCursor()
        self.committed = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def cursor(self, dictionary=False):
        return self.read if dictionary else self.write

    def commit(self):
        self.committed = True

    def rollback(self):
        pass


class PaymentHistoryTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.secret_key = "test"
        self.invoice = {
            "id": 2, "nilai_dpp": Decimal("1000"),
            "ppn_nominal": Decimal("110"), "total_netto": Decimal("1000"),
            "jatuh_tempo": date(2026, 11, 12),
        }

    def test_create_partial_payment_appends_event_and_updates_cumulative_summary(self):
        snapshot = {
            "id": 9, "nominal_tagihan": Decimal("1110"),
            "nominal_dibayar": Decimal("200"),
            "potongan_pph": Decimal("0"), "potongan_ppn_wapu": Decimal("0"),
            "tanggal_penyerahan": None, "tanggal_jatuh_tempo": date(2026, 11, 12),
        }
        connection = FakeConnection([self.invoice, snapshot, {"latest_date": None}])
        payload = {
            "invoice_id": 2, "tanggal_pembayaran": date.today().isoformat(),
            "nominal_diterima": "300", "potongan_pph": "10",
            "potongan_ppn_wapu": "0", "catatan": "Transfer tahap 2",
        }
        with self.app.test_request_context(json=payload):
            with patch("modul_navigasi.routes.can_write", return_value=True), \
                 patch("modul_navigasi.routes.get_db_connection", return_value=connection), \
                 patch("modul_navigasi.routes._record_finance_audit"):
                response, status_code = api_payment_event_create.__wrapped__()
        self.assertEqual(status_code, 201)
        self.assertTrue(response.json["success"])
        self.assertTrue(connection.committed)
        self.assertEqual(len(connection.write.calls), 2)
        self.assertEqual(connection.write.calls[0][1][2], Decimal("300.00"))
        self.assertEqual(connection.write.calls[1][1][1], Decimal("500"))
        self.assertEqual(connection.write.calls[1][1][2], Decimal("10"))
        self.assertEqual(connection.write.calls[1][1][5], "PROSES")

    def test_date_only_saves_handover_without_creating_payment_event(self):
        connection = FakeConnection([self.invoice, None, {"latest_date": None}])
        payload = {"invoice_id": 2, "tanggal_penyerahan": date.today().isoformat()}
        with self.app.test_request_context(json=payload):
            with patch("modul_navigasi.routes.can_write", return_value=True), \
                 patch("modul_navigasi.routes.get_db_connection", return_value=connection), \
                 patch("modul_navigasi.routes._record_finance_audit"):
                response, status_code = api_payment_event_create.__wrapped__()
        self.assertEqual(status_code, 200)
        self.assertTrue(response.json["success"])
        self.assertEqual(len(connection.write.calls), 1)
        self.assertIn("database_invoice_payment\n", connection.write.calls[0][0])
        self.assertNotIn("database_invoice_payment_event", connection.write.calls[0][0])
        self.assertEqual(connection.write.calls[0][1][1], date.today())
        self.assertEqual(connection.write.calls[0][1][-1], "PROSES")

    def test_payment_can_save_handover_in_same_submission(self):
        snapshot = {
            "id": 9, "nominal_tagihan": Decimal("1110"),
            "nominal_dibayar": Decimal("0"), "potongan_pph": Decimal("0"),
            "potongan_ppn_wapu": Decimal("0"), "tanggal_penyerahan": None,
            "tanggal_jatuh_tempo": date(2026, 11, 12),
        }
        connection = FakeConnection([self.invoice, snapshot, {"latest_date": None}])
        payload = {
            "invoice_id": 2, "tanggal_pembayaran": date.today().isoformat(),
            "tanggal_penyerahan": date.today().isoformat(),
            "nominal_diterima": "100",
        }
        with self.app.test_request_context(json=payload):
            with patch("modul_navigasi.routes.can_write", return_value=True), \
                 patch("modul_navigasi.routes.get_db_connection", return_value=connection), \
                 patch("modul_navigasi.routes._record_finance_audit"):
                response, status_code = api_payment_event_create.__wrapped__()
        self.assertEqual(status_code, 201)
        self.assertEqual(len(connection.write.calls), 2)
        self.assertEqual(connection.write.calls[1][1][-2], date.today())

    def test_overpayment_is_rejected_without_writing(self):
        snapshot = {
            "id": 9, "nominal_tagihan": Decimal("1110"),
            "nominal_dibayar": Decimal("1000"),
            "potongan_pph": Decimal("0"), "potongan_ppn_wapu": Decimal("0"),
        }
        connection = FakeConnection([self.invoice, snapshot, {"latest_date": None}])
        payload = {
            "invoice_id": 2, "tanggal_pembayaran": date.today().isoformat(),
            "nominal_diterima": "200",
        }
        with self.app.test_request_context(json=payload):
            with patch("modul_navigasi.routes.can_write", return_value=True), \
                 patch("modul_navigasi.routes.get_db_connection", return_value=connection):
                response, status_code = api_payment_event_create.__wrapped__()
        self.assertEqual(status_code, 400)
        self.assertIn("melebihi tagihan", response.json["message"])
        self.assertFalse(connection.write.calls)

    def test_final_backdated_entry_uses_latest_payment_date_for_settlement(self):
        snapshot = {
            "id": 9, "nominal_tagihan": Decimal("1110"),
            "nominal_dibayar": Decimal("1000"),
            "potongan_pph": Decimal("0"), "potongan_ppn_wapu": Decimal("0"),
            "tanggal_penyerahan": None, "tanggal_jatuh_tempo": None,
        }
        connection = FakeConnection([self.invoice, snapshot, {"latest_date": date.today()}])
        payload = {
            "invoice_id": 2, "tanggal_pembayaran": (date.today() - timedelta(days=1)).isoformat(),
            "nominal_diterima": "110",
        }
        with self.app.test_request_context(json=payload):
            with patch("modul_navigasi.routes.can_write", return_value=True), \
                 patch("modul_navigasi.routes.get_db_connection", return_value=connection), \
                 patch("modul_navigasi.routes._record_finance_audit"):
                response, status_code = api_payment_event_create.__wrapped__()
        self.assertEqual(status_code, 201)
        self.assertEqual(connection.write.calls[1][1][5], "DIBAYAR")
        self.assertEqual(connection.write.calls[1][1][6], date.today())

    def test_history_exposes_legacy_opening_without_inventing_payment_date(self):
        connection = FakeConnection([
            {"id": 2},
            {"nominal_dibayar": Decimal("500"), "potongan_pph": Decimal("10"),
             "potongan_ppn_wapu": Decimal("0"), "tanggal_pelunasan": None},
            [{"id": 17, "invoice_id": 2, "tanggal_pembayaran": date(2026, 10, 13),
              "nominal_diterima": Decimal("300"), "potongan_pph": Decimal("10"),
              "potongan_ppn_wapu": Decimal("0"), "catatan": None,
              "created_by": None, "created_at": None}],
        ])
        with self.app.test_request_context("/?invoice_id=2"):
            with patch("modul_navigasi.routes.get_db_connection", return_value=connection):
                response = api_payment_events_list.__wrapped__()
        self.assertTrue(response.json["success"])
        self.assertEqual(response.json["opening"]["nominal_diterima"], "200.00")
        self.assertEqual(response.json["data"][0]["tanggal_pembayaran"], "2026-10-13")
        self.assertIsNone(response.json["legacy_paid_date"])

    def test_history_get_is_reachable_through_registered_flask_route(self):
        connection = FakeConnection([{"id": 2}, None, []])
        with production_app.test_client() as client:
            with client.session_transaction() as session:
                session["logged_in"] = True
            with patch("modul_navigasi.routes.get_db_connection", return_value=connection):
                response = client.get("/api/modul-3/payment-events?invoice_id=2")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json["success"])
        self.assertEqual(response.json["data"], [])

    def test_deleted_event_is_excluded_from_opening_and_hidden_from_read_only_role(self):
        active = {"id": 17, "nominal_diterima": Decimal("300"), "potongan_pph": Decimal("0"),
                  "potongan_ppn_wapu": Decimal("0"), "deleted_at": None}
        deleted = {"id": 18, "nominal_diterima": Decimal("100"), "potongan_pph": Decimal("0"),
                   "potongan_ppn_wapu": Decimal("0"), "deleted_at": date.today(),
                   "deleted_by": "finance.user", "deleted_role": "Finance & Tax"}
        rows = [{"id": 2}, {"nominal_dibayar": Decimal("500"), "potongan_pph": 0,
                              "potongan_ppn_wapu": 0, "tanggal_pelunasan": None}, [active, deleted]]
        for role, expected_ids in (("Management", [17]), ("Finance & Tax", [17, 18])):
            with self.subTest(role=role), self.app.test_request_context("/?invoice_id=2"):
                from flask import session
                session["current_role"] = role
                with patch("modul_navigasi.routes.get_db_connection", return_value=FakeConnection(rows)):
                    response = api_payment_events_list.__wrapped__()
                self.assertEqual([item["id"] for item in response.json["data"]], expected_ids)
                self.assertEqual(response.json["opening"]["nominal_diterima"], "200.00")

    def test_soft_delete_recalculates_balance_and_records_actor(self):
        from flask import session
        snapshot = {"id": 9, "nominal_tagihan": Decimal("1110"),
                    "nominal_dibayar": Decimal("400"), "potongan_pph": Decimal("10"),
                    "potongan_ppn_wapu": Decimal("0"), "tanggal_penyerahan": None}
        event = {"id": 17, "nominal_diterima": Decimal("300"),
                 "potongan_pph": Decimal("10"), "potongan_ppn_wapu": Decimal("0"),
                 "deleted_at": None}
        connection = FakeConnection([{"invoice_id": 2}, self.invoice, snapshot, event,
                                     {"latest_date": None}])
        with self.app.test_request_context():
            session["current_role"] = "Finance & Tax"
            session["current_user"] = "finance.user"
            with patch("modul_navigasi.routes.get_db_connection", return_value=connection), \
                 patch("modul_navigasi.routes._record_finance_audit") as audit:
                response = api_payment_event_delete.__wrapped__(17)
        self.assertTrue(response.json["success"])
        self.assertTrue(connection.committed)
        self.assertEqual(len(connection.write.calls), 2)
        self.assertIn("deleted_at = CURRENT_TIMESTAMP", connection.write.calls[0][0])
        self.assertEqual(connection.write.calls[0][1], ("finance.user", "Finance & Tax", 17))
        self.assertEqual(connection.write.calls[1][1][1], Decimal("100.00"))
        self.assertEqual(connection.write.calls[1][1][2], Decimal("0"))
        self.assertEqual(connection.write.calls[1][1][5], "PROSES")
        audit.assert_called_once()

    def test_soft_delete_rejects_management_and_repeat_delete(self):
        from flask import session
        with self.app.test_request_context():
            session["current_role"] = "Management"
            session["current_user"] = "manager"
            with patch("modul_navigasi.routes.get_db_connection") as db:
                response, code = api_payment_event_delete.__wrapped__(17)
            self.assertEqual(code, 403)
            db.assert_not_called()

        connection = FakeConnection([{"invoice_id": 2}, self.invoice,
                                     {"id": 9}, {"id": 17, "deleted_at": date.today()}])
        with self.app.test_request_context():
            session["current_role"] = "Finance & Tax"
            session["current_user"] = "finance.user"
            with patch("modul_navigasi.routes.get_db_connection", return_value=connection):
                response, code = api_payment_event_delete.__wrapped__(17)
        self.assertEqual(code, 409)
        self.assertFalse(connection.write.calls)

    def test_deleting_final_payment_reopens_receivable(self):
        from flask import session
        snapshot = {"id": 9, "nominal_tagihan": Decimal("1110"),
                    "nominal_dibayar": Decimal("1110"), "potongan_pph": Decimal("0"),
                    "potongan_ppn_wapu": Decimal("0"), "tanggal_penyerahan": None,
                    "tanggal_pelunasan": date.today()}
        event = {"id": 17, "nominal_diterima": Decimal("300"),
                 "potongan_pph": Decimal("0"), "potongan_ppn_wapu": Decimal("0"),
                 "deleted_at": None}
        connection = FakeConnection([{"invoice_id": 2}, self.invoice, snapshot, event,
                                     {"latest_date": (date.today() - timedelta(days=1))}])
        with self.app.test_request_context():
            session["current_role"] = "Super Admin"
            session["current_user"] = "admin.user"
            with patch("modul_navigasi.routes.get_db_connection", return_value=connection), \
                 patch("modul_navigasi.routes._record_finance_audit"):
                response = api_payment_event_delete.__wrapped__(17)
        self.assertTrue(response.json["success"])
        updated = connection.write.calls[1][1]
        self.assertEqual(updated[1], Decimal("810.00"))
        self.assertEqual(updated[5], "PROSES")
        self.assertIsNone(updated[6])
        self.assertIn("deleted_at IS NULL", connection.read.calls[-1][0])

    def test_soft_delete_is_reachable_through_registered_flask_route(self):
        snapshot = {"id": 9, "nominal_tagihan": Decimal("1110"),
                    "nominal_dibayar": Decimal("300"), "potongan_pph": Decimal("0"),
                    "potongan_ppn_wapu": Decimal("0"), "tanggal_penyerahan": None}
        event = {"id": 17, "nominal_diterima": Decimal("300"),
                 "potongan_pph": Decimal("0"), "potongan_ppn_wapu": Decimal("0"),
                 "deleted_at": None}
        connection = FakeConnection([{"invoice_id": 2}, self.invoice, snapshot, event,
                                     {"latest_date": None}])
        with production_app.test_client() as client:
            with client.session_transaction() as session:
                session.update({"logged_in": True, "current_role": "Finance & Tax",
                                "current_user": "finance.user"})
            with patch("modul_navigasi.routes.get_db_connection", return_value=connection), \
                 patch("modul_navigasi.routes._record_finance_audit"):
                response = client.delete("/api/modul-3/payment-events/17")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json["success"])

    def test_summary_cannot_overwrite_amounts_after_events_exist(self):
        connection = FakeConnection([
            self.invoice,
            {"id": 9, "nomor_faktur_pajak": None,
             "nominal_dibayar": Decimal("300"),
             "potongan_pph": Decimal("0"), "potongan_ppn_wapu": Decimal("0")},
            {"total": 1},
        ])
        payload = {
            "invoice_id": 2, "tanggal_penyerahan": "2026-10-13",
            "nominal_dibayar": "400", "potongan_pph": "0",
            "potongan_ppn_wapu": "0",
        }
        with self.app.test_request_context(json=payload):
            with patch("modul_navigasi.routes.can_write", return_value=True), \
                 patch("modul_navigasi.routes.get_db_connection", return_value=connection):
                response, status_code = api_payment_monitoring_upsert.__wrapped__()
        self.assertEqual(status_code, 400)
        self.assertIn("Catat Pembayaran", response.json["message"])
        self.assertFalse(connection.write.calls)


if __name__ == "__main__":
    unittest.main()
