import unittest
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

from flask import Flask

from modul_navigasi.routes import (
    _payment_derived_status,
    _payment_invoice_charge,
    _payment_json_row,
    api_payment_monitoring_upsert,
)


class PaymentTrackingTests(unittest.TestCase):
    def setUp(self):
        self.row = {
            "id": 1,
            "invoice_id": 2,
            "nominal_tagihan": Decimal("0"),
            "nominal_dibayar": Decimal("0"),
            "potongan_pph": Decimal("0"),
            "potongan_ppn_wapu": Decimal("0"),
            "status_pembayaran": "DIBAYAR",
            "tanggal_jatuh_tempo": date.today() - timedelta(days=1),
            "invoice_nilai_dpp": Decimal("1000"),
            "invoice_ppn_nominal": Decimal("110"),
            "invoice_total_netto": Decimal("1000"),
        }

    def test_zero_legacy_bill_uses_invoice_and_is_not_lunas(self):
        result = _payment_json_row(self.row)
        self.assertEqual(result["nominal_tagihan"], "1110.00")
        self.assertEqual(result["saldo_piutang"], "1110.00")
        self.assertEqual(result["aging_status"], "OVERDUE")
        self.assertTrue(result["tagihan_dari_invoice"])
        self.assertTrue(result["perlu_verifikasi"])

    def test_bank_receipt_and_withholding_close_balance(self):
        result = _payment_json_row({
            **self.row,
            "nominal_dibayar": Decimal("1000"),
            "potongan_pph": Decimal("110"),
        })
        self.assertEqual(result["saldo_piutang"], "0.00")
        self.assertEqual(result["aging_status"], "LUNAS")
        self.assertFalse(result["perlu_verifikasi"])

    def test_recorded_bill_difference_is_flagged(self):
        result = _payment_json_row({**self.row, "nominal_tagihan": Decimal("1000")})
        self.assertTrue(result["tagihan_berbeda_invoice"])
        self.assertEqual(result["tagihan_invoice_bruto"], "1110.00")

    def test_missing_invoice_amount_is_not_lunas(self):
        result = _payment_json_row({
            **self.row,
            "invoice_nilai_dpp": Decimal("0"),
            "invoice_ppn_nominal": Decimal("0"),
            "invoice_total_netto": Decimal("0"),
        })
        self.assertEqual(result["aging_status"], "TAGIHAN BELUM ADA")

    def test_status_derived_from_amount_and_handover(self):
        amount = Decimal("1110")
        zero = Decimal("0")
        self.assertEqual(_payment_derived_status(amount, zero, zero, zero, None), "BELUM DIBAYAR")
        self.assertEqual(_payment_derived_status(amount, zero, zero, zero, date.today()), "PROSES")
        self.assertEqual(_payment_derived_status(amount, Decimal("500"), zero, zero, None), "PROSES")
        self.assertEqual(_payment_derived_status(amount, Decimal("1000"), Decimal("110"), zero, None), "DIBAYAR")

    def test_invoice_charge_is_gross_before_withholding(self):
        self.assertEqual(_payment_invoice_charge(self.row), Decimal("1110.00"))

    def test_upsert_auto_uses_invoice_amount_and_derived_status(self):
        class ReadCursor:
            def __init__(self):
                self.rows = iter([
                    {"id": 2, "nilai_dpp": Decimal("1000"), "ppn_nominal": Decimal("110"),
                     "total_netto": Decimal("1000"), "jatuh_tempo": date(2026, 11, 12)},
                    None,
                    {"total": 0},
                ])

            def execute(self, sql, params):
                pass

            def fetchone(self):
                return next(self.rows)

            def close(self):
                pass

        class WriteCursor:
            lastrowid = 9

            def __init__(self):
                self.params = None

            def execute(self, sql, params):
                self.params = params

            def close(self):
                pass

        class Connection:
            def __init__(self):
                self.read = ReadCursor()
                self.write = WriteCursor()
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

        connection = Connection()
        app = Flask(__name__)
        payload = {
            "invoice_id": 2, "status_pembayaran": "AUTO",
            "tanggal_penyerahan": "2026-10-13", "nominal_dibayar": "0",
            "potongan_pph": "0", "potongan_ppn_wapu": "0",
        }
        with app.test_request_context(json=payload):
            with patch("modul_navigasi.routes.can_write", return_value=True), \
                 patch("modul_navigasi.routes.get_db_connection", return_value=connection), \
                 patch("modul_navigasi.routes._record_finance_audit"):
                response = api_payment_monitoring_upsert.__wrapped__()
        self.assertTrue(response.json["success"])
        self.assertTrue(connection.committed)
        self.assertEqual(connection.write.params[5], Decimal("1110.00"))
        self.assertEqual(connection.write.params[10], "PROSES")


if __name__ == "__main__":
    unittest.main()
