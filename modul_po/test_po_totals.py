import unittest
from decimal import Decimal
from unittest.mock import patch

from flask import Flask

from modul_po import master_po
from modul_po.master_po import refresh_po_total


class FakeCursor:
    def __init__(self):
        self.calls = []
        self.row = {"total_plafon": Decimal("1500.00")}

    def execute(self, sql, params):
        self.calls.append((sql, params))

    def fetchone(self):
        return self.row


class PoTotalsTests(unittest.TestCase):
    def test_refresh_recalculates_items_before_header(self):
        cur = FakeCursor()
        total = refresh_po_total(cur, 20)
        self.assertEqual(total, Decimal("1500.00"))
        self.assertIn("ROUND(qty_po * unit_price, 2)", cur.calls[0][0])
        self.assertEqual(cur.calls[0][1], (20,))
        self.assertIn("SUM(total_plafon)", cur.calls[1][0])
        self.assertEqual(cur.calls[2][1], (Decimal("1500.00"), 20))

    def test_save_existing_po_uses_header_and_item_ids(self):
        class SaveCursor:
            rowcount = 1
            lastrowid = 0

            def __init__(self):
                self.calls = []
                self.result = None

            def execute(self, sql, params=()):
                self.calls.append((sql, params))
                if "SELECT id, status_po, nomor_kontrak, nomor_po FROM database_master_po" in sql:
                    self.result = {"id": 10, "status_po": "ACTIVE", "nomor_kontrak": "K-1", "nomor_po": "PO-1"}
                elif "SELECT id FROM database_master_po_item" in sql:
                    self.result = None

            def fetchone(self):
                return self.result

            def fetchall(self):
                return []

            def close(self):
                pass

        class SaveConnection:
            def __init__(self):
                self.cur = SaveCursor()
                self.committed = False

            def __enter__(self):
                return self

            def __exit__(self, *_):
                return False

            def cursor(self):
                return self.cur

            def commit(self):
                self.committed = True

            def rollback(self):
                pass

        conn = SaveConnection()
        app = Flask(__name__)
        payload = {"id": 10, "nomor_kontrak": "K-1", "nomor_po": "PO-1",
                   "items": [{"id": 20, "item_no": 1, "deskripsi_pekerjaan": "Sewa Alat",
                              "qty_po": 100, "unit_price": 15}]}
        with app.test_request_context("/master-po/api", method="POST", json=payload), \
             patch.object(master_po, "bootstrap_master_po"), \
             patch.object(master_po, "get_db_connection", return_value=conn), \
             patch.object(master_po, "refresh_po_total"), \
             patch.object(master_po, "remap_transaction_pi_items"), \
             patch.object(master_po, "remap_unmapped_realizations"):
            response = master_po.api_save.__wrapped__()
        self.assertTrue(conn.committed)
        self.assertEqual(response.get_json()["po_id"], 10)
        updates = [params for sql, params in conn.cur.calls if "UPDATE database_master_po_item" in sql]
        self.assertEqual(updates[0][4:7], (Decimal("100"), Decimal("15"), Decimal("1500")))
        self.assertEqual(updates[0][7:10], ('', 20, 10))

    def test_draft_from_history_keeps_separate_provisional_rows_and_notes(self):
        class DraftCursor:
            lastrowid = 50

            def __init__(self):
                self.calls = []
                self.result = None
                self.rows = []

            def execute(self, sql, params=()):
                self.calls.append((sql, params))
                self.result = None
                self.rows = []
                if "MAX(version_no)" in sql:
                    self.result = {"max_version": 0}
                elif "FROM database_transaksi_rincian" in sql:
                    self.rows = [
                        {"kategori": "PROVISIONAL SUM", "deskripsi_pekerjaan": "Kabel",
                         "uom": "Kg", "qty_po_awal": 3, "unit_price": 100,
                         "keterangan": "Kabel area A",
                         "tanggal_po": "2026-01-01"},
                        {"kategori": "PROFESSIONAL SUM", "deskripsi_pekerjaan": "Logistik",
                         "uom": "AU", "qty_po_awal": 2, "unit_price": 250,
                         "keterangan": "Logistik area B"},
                    ]

            def fetchone(self):
                return self.result

            def fetchall(self):
                return self.rows

            def close(self):
                pass

        class DraftConnection:
            def __init__(self):
                self.cur = DraftCursor()

            def __enter__(self):
                return self

            def __exit__(self, *_):
                return False

            def cursor(self):
                return self.cur

            def commit(self):
                pass

            def rollback(self):
                pass

        conn = DraftConnection()
        app = Flask(__name__)
        with app.test_request_context("/master-po/api/register-from-history", method="POST",
                                      json={"nomor_kontrak": "K-1", "nomor_po": "PO-1"}), \
             patch.object(master_po, "bootstrap_master_po"), \
             patch.object(master_po, "get_db_connection", return_value=conn), \
             patch.object(master_po, "refresh_po_total"), \
             patch.object(master_po, "remap_unmapped_realizations", return_value=0):
            response = master_po.api_register_from_history.__wrapped__()
        inserted = [params for sql, params in conn.cur.calls
                    if "INSERT INTO database_master_po_item" in sql]
        self.assertEqual(len(inserted), 2)
        self.assertEqual(inserted[0][2:9], ("PROVISIONAL SUM", "Kabel", "Kg",
                                            Decimal("3"), Decimal("100"), Decimal("300"),
                                            "Kabel area A"))
        self.assertIn("Periksa Qty dan Harga Satuan Provisional Sum", response.get_json()["warning"])


if __name__ == "__main__":
    unittest.main()
