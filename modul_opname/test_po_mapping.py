import unittest
from decimal import Decimal
from unittest.mock import patch

from modul_opname import po_mapping


class FakeCursor:
    def __init__(self):
        self.statements = []
        self.row = None
        self.rowcount = 0
        self.lastrowid = 0
        self.unread_release = False
        self.release_consumed = False

    def execute(self, sql, params=()):
        self.statements.append((sql, params))
        self.rowcount = 0
        if "GET_LOCK" in sql:
            self.row = {"acquired": 1}
        elif "RELEASE_LOCK" in sql:
            self.row = {"released": 1}
            self.unread_release = True
        elif "SELECT po_item_id FROM database_po_mapping_rule" in sql:
            self.row = None
        elif "MAX(version_no)" in sql:
            self.row = {"next_version": 1}
        elif "MAX(item_no)" in sql:
            self.row = {"next_item_no": 1}
        elif "SUM(qty_realisasi)" in sql:
            self.row = {"used": Decimal("40")}
        elif "INSERT INTO database_master_po_item" in sql:
            self.lastrowid = 30
        elif "INSERT INTO database_master_po" in sql:
            self.lastrowid = 20
        elif "UPDATE database_transaksi_rincian" in sql:
            self.rowcount = 1

    def fetchone(self):
        if self.unread_release:
            self.unread_release = False
            self.release_consumed = True
        return self.row

    def fetchall(self):
        return []

    def close(self):
        if self.unread_release:
            raise RuntimeError("Unread result found")


class FakeConnection:
    def __init__(self):
        self.cur = FakeCursor()
        self.commits = 0
        self.rollbacks = 0

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def cursor(self):
        return self.cur

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


class PoMappingTests(unittest.TestCase):
    def setUp(self):
        self.conn = FakeConnection()
        self.item = {
            "item_key": "pi-a", "kategori": "Jasa", "deskripsi_pekerjaan": "Sewa Alat",
            "uom": "hari", "qty_pi": Decimal("20"), "unit_price": Decimal("15"),
            "pi_po_item_id": None, "nomor_po": "PO-1",
        }
        self.rows = [
            {"pi_no": pi, "nomor_po": "PO-1", "kategori": "Jasa",
             "deskripsi_pekerjaan": "Sewa Alat", "unit": "hari",
             "harga_satuan": Decimal("15"), "po_item_id": None}
            for pi in ("PI-1", "PI-2")
        ]
        self.payload = {"nomor_kontrak": "K-1", "nomor_pi": "PI-1",
                        "nomor_po": "PO-1", "item_key": "pi-a", "scope": "all"}
        self.sync = patch.object(po_mapping, "sync_pi_realization").start()
        self.addCleanup(patch.stopall)
        patch.object(po_mapping, "bootstrap_master_po").start()
        patch.object(po_mapping, "get_db_connection", return_value=self.conn).start()
        patch.object(po_mapping, "_selection", return_value=("K-1", "PI-1", "PO-1", self.item)).start()
        patch.object(po_mapping, "_group_rows", return_value=("fingerprint", self.rows)).start()
        self.refresh = patch.object(po_mapping, "refresh_po_total").start()

    def test_link_existing_item_to_two_pi(self):
        with patch.object(po_mapping, "_find_master_po", return_value={"id": 10}), \
             patch.object(po_mapping, "_master_items", return_value=[{"id": 11, "unit_price": Decimal("15")} ]):
            result = po_mapping.reconcile_po_item({**self.payload, "action": "link", "po_item_id": 11})
        self.assertEqual(result["mapped_rows"], 2)
        self.assertEqual(result["affected_pi_count"], 2)
        self.assertEqual(self.conn.commits, 1)
        self.assertTrue(self.conn.cur.release_consumed)
        self.assertEqual(self.sync.call_count, 2)
        self.assertTrue(any("INSERT INTO database_po_mapping_rule" in sql for sql, _ in self.conn.cur.statements))
        self.assertFalse(any("INSERT INTO database_master_po_item" in sql for sql, _ in self.conn.cur.statements))

    def test_create_draft_from_pi_with_confirmed_po_qty_and_price(self):
        with patch.object(po_mapping, "_find_master_po", return_value=None):
            result = po_mapping.reconcile_po_item({**self.payload, "action": "create", "qty_po": "100", "unit_price": "15"})
        self.assertEqual(result["po_id"], 20)
        self.assertEqual(result["item_id"], 30)
        insert = next(params for sql, params in self.conn.cur.statements if "INSERT INTO database_master_po_item" in sql)
        self.assertEqual(insert[5:8], (Decimal("100"), Decimal("15"), Decimal("1500")))
        self.refresh.assert_called_once()

    def test_adjust_qty_without_creating_new_item(self):
        with patch.object(po_mapping, "_find_master_po", return_value={"id": 10}), \
             patch.object(po_mapping, "_master_items", return_value=[{"id": 11, "unit_price": Decimal("15")} ]):
            po_mapping.reconcile_po_item({**self.payload, "action": "adjust_qty", "po_item_id": 11, "qty_po": "100"})
        updates = [params for sql, params in self.conn.cur.statements if "UPDATE database_master_po_item" in sql]
        self.assertEqual(updates, [(Decimal("100"), Decimal("1500"), 11, 10)])
        self.assertFalse(any("INSERT INTO database_master_po_item" in sql for sql, _ in self.conn.cur.statements))

    def test_rejects_qty_below_recorded_realization(self):
        with patch.object(po_mapping, "_find_master_po", return_value={"id": 10}), \
             patch.object(po_mapping, "_master_items", return_value=[{"id": 11, "unit_price": Decimal("15")} ]):
            with self.assertRaisesRegex(ValueError, "kurang dari realisasi"):
                po_mapping.reconcile_po_item({**self.payload, "action": "adjust_qty", "po_item_id": 11, "qty_po": "30"})
        self.assertEqual(self.conn.commits, 0)
        self.assertEqual(self.conn.rollbacks, 1)

    def test_rejects_unconfirmed_qty(self):
        with self.assertRaisesRegex(ValueError, "Qty PO wajib diisi"):
            po_mapping.reconcile_po_item({**self.payload, "action": "create", "unit_price": "15"})

    def test_current_pi_scope_does_not_create_future_rule(self):
        with patch.object(po_mapping, "_find_master_po", return_value={"id": 10}), \
             patch.object(po_mapping, "_master_items", return_value=[{"id": 11, "unit_price": Decimal("15")} ]):
            result = po_mapping.reconcile_po_item({**self.payload, "action": "link", "po_item_id": 11, "scope": "current"})
        self.assertEqual(result["mapped_rows"], 1)
        self.assertFalse(any("INSERT INTO database_po_mapping_rule" in sql for sql, _ in self.conn.cur.statements))

    def test_current_pi_scope_keeps_other_price_variant_unmapped(self):
        rows = self.rows + [{**self.rows[0], "harga_satuan": Decimal("19")}]
        with patch.object(po_mapping, "_group_rows", return_value=("fingerprint", rows)), \
             patch.object(po_mapping, "_find_master_po", return_value={"id": 10}), \
             patch.object(po_mapping, "_master_items", return_value=[{"id": 11, "unit_price": Decimal("15")}]):
            po_mapping.reconcile_po_item({**self.payload, "action": "link", "po_item_id": 11, "scope": "current"})
        updates = [(sql, params) for sql, params in self.conn.cur.statements
                   if "UPDATE database_transaksi_rincian" in sql]
        self.assertEqual(len(updates), 1)
        self.assertIn("harga_satuan <=> %s", updates[0][0])
        self.assertEqual(updates[0][1][-1], Decimal("15"))

    def test_options_suggest_existing_reference_item(self):
        from modul_po.master_po import po_reference_fingerprint

        fingerprint = po_reference_fingerprint("Jasa", "Sewa Alat", "hari")
        with patch.object(po_mapping, "_group_rows", return_value=(fingerprint, self.rows)), \
             patch.object(po_mapping, "_find_master_po", return_value={"id": 10}), \
             patch.object(po_mapping, "_master_items", return_value=[
                 {"id": 11, "kategori": "Jasa", "deskripsi_pekerjaan": "Sewa Alat", "uom": "hari"},
                 {"id": 12, "kategori": "Jasa", "deskripsi_pekerjaan": "Lain", "uom": "hari"},
             ]):
            result = po_mapping.po_mapping_options(self.payload)
        self.assertEqual(result["suggested_item_ids"], [11])
        self.assertEqual(result["affected_pi_count"], 2)

    def test_opname_counts_shared_po_qty_and_previous_once(self):
        from modul_opname import services

        pi_rows = [
            {"item_key": key, "item_no": index, "pi_po_item_id": 11,
             "kategori": "Jasa", "deskripsi_pekerjaan": "Sewa Alat", "uom": "hari",
             "unit_price": Decimal("15"), "mapping_status": "UNMAPPED", "nomor_po": "PO-1"}
            for index, key in enumerate(("pi-a", "pi-b"), 1)
        ]
        master_item = {"id": 11, "item_no": 1, "qty_po": Decimal("100"),
                       "unit_price": Decimal("15"), "deskripsi_pekerjaan": "Sewa Alat", "uom": "hari"}
        with patch.object(services, "ensure_opname_schema"), \
             patch.object(services, "get_db_connection", return_value=FakeConnection()), \
             patch.object(services, "_find_master_po", return_value={"id": 10}), \
             patch.object(services, "_pi_items", return_value=pi_rows), \
             patch.object(services, "_master_items", return_value=[master_item]), \
             patch.object(services, "_previous_for_item", return_value=Decimal("40")) as previous:
            context = services.get_opname_context("K-1", "PI-1", "PO-1")
        self.assertEqual(previous.call_count, 1)
        self.assertEqual(context["items"][0]["qty_po"], Decimal("100"))
        self.assertIsNone(context["items"][1]["qty_po"])
        self.assertEqual([x["qty_previous"] for x in context["items"]], [Decimal("40"), Decimal("0")])

    def test_save_opname_uses_master_qty_and_price_for_mapped_item(self):
        from modul_opname import services

        context = {"items": [{"item_key": "pi-a", "item_no": 1, "id": 11,
                              "mapping_status": "MAPPED", "qty_po": Decimal("100"),
                              "unit_price": Decimal("15"), "qty_previous": Decimal("40"),
                              "kategori": "Jasa", "deskripsi_pekerjaan": "Sewa Alat", "uom": "hari"}],
                   "mapping_status": "MAPPED"}
        payload = {"nomor_kontrak": "K-1", "nomor_pi": "PI-1", "nomor_po": "PO-1",
                   "items": [{"item_key": "pi-a", "qty_po": 999, "unit_price": 999,
                              "volume_actual": 2}]}
        with patch.object(services, "ensure_opname_schema"), \
             patch.object(services, "get_opname_context", return_value=context), \
             patch.object(services, "get_db_connection", return_value=self.conn):
            services.save_opname(payload)
        insert = next(params for sql, params in self.conn.cur.statements if "INSERT INTO database_opname" in sql)
        self.assertEqual(insert[11], Decimal("100"))
        self.assertEqual(insert[12], Decimal("15"))


if __name__ == "__main__":
    unittest.main()
