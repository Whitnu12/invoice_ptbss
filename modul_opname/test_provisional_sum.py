import unittest
from decimal import Decimal
from unittest.mock import patch

from modul_opname import po_mapping, services
from modul_opname.test_po_mapping import FakeConnection
from modul_po.master_po import is_provisional_category, po_reference_fingerprint


class ProvisionalSumTests(unittest.TestCase):
    def setUp(self):
        self.conn = FakeConnection()
        self.item = {"item_key": "pi-1", "kategori": "PROVISIONAL SUM",
                     "deskripsi_pekerjaan": "Kabel", "uom": "Kg", "unit_price": Decimal("100"),
                     "nomor_po": "PO-1", "pi_po_item_id": None}
        self.rows = [
            {"pi_no": "PI-1", "nomor_po": "PO-1", "kategori": "PROVISIONAL SUM",
             "deskripsi_pekerjaan": desc, "unit": uom, "harga_satuan": Decimal(price),
             "po_item_id": None}
            for desc, uom, price in (("Kabel", "Kg", "100"), ("Logistik", "AU", "250"))
        ]
        self.payload = {"nomor_kontrak": "K-1", "nomor_pi": "PI-1", "nomor_po": "PO-1",
                        "item_key": "pi-1", "scope": "all"}

    def test_one_fingerprint_for_any_provisional_description_unit_and_alias(self):
        self.assertTrue(is_provisional_category("PROFESSIONAL SUM"))
        self.assertEqual(po_reference_fingerprint("PROVISIONAL SUM", "Kabel", "Kg"),
                         po_reference_fingerprint("PROFESSIONAL SUM", "Logistik", "AU"))
        self.assertNotEqual(po_reference_fingerprint("Jasa", "Kabel", "Kg"),
                            po_reference_fingerprint("Jasa", "Logistik", "AU"))

    def test_create_provisional_bucket_uses_confirmed_budget_not_pi_cost(self):
        with patch.object(po_mapping, "bootstrap_master_po"), \
             patch.object(po_mapping, "get_db_connection", return_value=self.conn), \
             patch.object(po_mapping, "_selection", return_value=("K-1", "PI-1", "PO-1", self.item)), \
             patch.object(po_mapping, "_group_rows", return_value=("ps", self.rows)), \
             patch.object(po_mapping, "_find_master_po", return_value=None), \
             patch.object(po_mapping, "refresh_po_total"), \
             patch.object(po_mapping, "sync_pi_realization"):
            result = po_mapping.reconcile_po_item({**self.payload, "action": "create", "unit_price": "10000"})
        insert = next(params for sql, params in self.conn.cur.statements
                      if "INSERT INTO database_master_po_item" in sql)
        self.assertEqual(insert[2:8], ("PROVISIONAL SUM", "Provisional Sum (At Cost + Fee 15%)",
                                       "AU", Decimal("1"), Decimal("10000"), Decimal("10000")))
        self.assertEqual(result["mapped_rows"], 2)

    def test_current_scope_maps_all_provisional_lines_of_same_pi(self):
        with patch.object(po_mapping, "bootstrap_master_po"), \
             patch.object(po_mapping, "get_db_connection", return_value=self.conn), \
             patch.object(po_mapping, "_selection", return_value=("K-1", "PI-1", "PO-1", self.item)), \
             patch.object(po_mapping, "_group_rows", return_value=("ps", self.rows)), \
             patch.object(po_mapping, "_find_master_po", return_value={"id": 10}), \
             patch.object(po_mapping, "_master_items", return_value=[{"id": 11, "kategori": "PROVISIONAL SUM", "total_plafon": Decimal("10000")}]), \
             patch.object(po_mapping, "sync_pi_realization"):
            result = po_mapping.reconcile_po_item({**self.payload, "action": "link", "scope": "current", "po_item_id": 11})
        self.assertEqual(result["mapped_rows"], 2)
        self.assertFalse(any("INSERT INTO database_po_mapping_rule" in sql for sql, _ in self.conn.cur.statements))

    def test_budget_revision_updates_value_not_qty(self):
        with patch.object(po_mapping, "bootstrap_master_po"), \
             patch.object(po_mapping, "get_db_connection", return_value=self.conn), \
             patch.object(po_mapping, "_selection", return_value=("K-1", "PI-1", "PO-1", self.item)), \
             patch.object(po_mapping, "_group_rows", return_value=("ps", self.rows)), \
             patch.object(po_mapping, "_find_master_po", return_value={"id": 10}), \
             patch.object(po_mapping, "_master_items", return_value=[{"id": 11, "kategori": "PROVISIONAL SUM"}]), \
             patch.object(po_mapping, "refresh_po_total"), \
             patch.object(po_mapping, "sync_pi_realization"):
            po_mapping.reconcile_po_item({**self.payload, "action": "adjust_budget",
                                          "po_item_id": 11, "unit_price": "12000"})
        updates = [params for sql, params in self.conn.cur.statements
                   if "UPDATE database_master_po_item SET qty_po=1" in sql]
        self.assertEqual(updates, [(Decimal("12000"), Decimal("12000"), 11, 10)])

    def test_cannot_map_against_unconfirmed_zero_provisional_budget(self):
        with patch.object(po_mapping, "bootstrap_master_po"), \
             patch.object(po_mapping, "get_db_connection", return_value=self.conn), \
             patch.object(po_mapping, "_selection", return_value=("K-1", "PI-1", "PO-1", self.item)), \
             patch.object(po_mapping, "_group_rows", return_value=("ps", self.rows)), \
             patch.object(po_mapping, "_find_master_po", return_value={"id": 10}), \
             patch.object(po_mapping, "_master_items", return_value=[{
                 "id": 11, "kategori": "PROVISIONAL SUM", "total_plafon": Decimal("0")}]), \
             patch.object(po_mapping, "sync_pi_realization"):
            with self.assertRaisesRegex(ValueError, "Isi plafon Provisional Sum"):
                po_mapping.reconcile_po_item({**self.payload, "action": "link", "po_item_id": 11})

    def test_opname_preserves_pi_cost_and_counts_po_budget_once(self):
        rows = [{"item_key": f"pi-{i}", "item_no": i, "pi_po_item_id": 11,
                 "kategori": "PROVISIONAL SUM", "deskripsi_pekerjaan": desc, "uom": unit,
                 "unit_price": Decimal(price), "nilai_pi": Decimal(value),
                 "mapping_status": "UNMAPPED", "nomor_po": "PO-1"}
                for i, desc, unit, price, value in ((1, "Kabel", "Kg", "100", "115"),
                                                    (2, "Logistik", "AU", "250", "287.5"))]
        master = {"id": 11, "item_no": 1, "kategori": "PROVISIONAL SUM",
                  "qty_po": Decimal("1"), "unit_price": Decimal("10000"),
                  "total_plafon": Decimal("10000")}
        with patch.object(services, "ensure_opname_schema"), \
             patch.object(services, "get_db_connection", return_value=FakeConnection()), \
             patch.object(services, "_find_master_po", return_value={"id": 10}), \
             patch.object(services, "_pi_items", return_value=rows), \
             patch.object(services, "_master_items", return_value=[master]), \
             patch.object(services, "_previous_for_item", return_value=Decimal("300")) as previous:
            result = services.get_opname_context("K-1", "PI-1", "PO-1")
        a, b = result["items"]
        self.assertEqual([a["unit_price"], b["unit_price"]], [Decimal("100"), Decimal("250")])
        self.assertEqual([a["nilai_previous"], b["nilai_previous"]], [Decimal("300"), Decimal("0")])
        self.assertEqual(a["po_plafon"], Decimal("10000"))
        self.assertTrue(b["shared_po_item"])
        self.assertEqual(previous.call_count, 1)

    def test_save_opname_uses_amount_including_fee_without_multiplying_budget(self):
        context = {"items": [{"item_key": "pi-1", "item_no": 1, "id": 11,
                              "kategori": "PROVISIONAL SUM", "deskripsi_pekerjaan": "Kabel",
                              "uom": "Kg", "is_provisional": True, "mapping_status": "MAPPED",
                              "qty_po": Decimal("1"), "unit_price": Decimal("100"),
                              "nilai_previous": Decimal("300"), "po_plafon": Decimal("10000")}],
                   "mapping_status": "MAPPED"}
        payload = {"nomor_kontrak": "K-1", "nomor_pi": "PI-1", "nomor_po": "PO-1",
                   "items": [{"item_key": "pi-1", "nilai_actual": "115"}]}
        with patch.object(services, "ensure_opname_schema"), \
             patch.object(services, "get_opname_context", return_value=context), \
             patch.object(services, "get_db_connection", return_value=self.conn):
            services.save_opname(payload)
        values = next(params for sql, params in self.conn.cur.statements if "INSERT INTO database_opname" in sql)
        self.assertEqual(values[12], Decimal("100"))
        self.assertEqual(values[17:21], (Decimal("300"), Decimal("115"),
                                         Decimal("415"), Decimal("9585")))

    def test_remaining_budget_subtracts_all_provisional_lines_in_one_pi(self):
        context = {"items": [
            {"item_key": "pi-1", "item_no": 1, "id": 11, "kategori": "PROVISIONAL SUM",
             "is_provisional": True, "mapping_status": "MAPPED", "qty_po": Decimal("1"),
             "unit_price": Decimal("100"), "nilai_previous": Decimal("300"),
             "po_plafon": Decimal("10000")},
            {"item_key": "pi-2", "item_no": 2, "id": 11, "kategori": "PROVISIONAL SUM",
             "is_provisional": True, "mapping_status": "MAPPED", "shared_po_item": True,
             "unit_price": Decimal("250"), "nilai_previous": Decimal("0"),
             "po_plafon": Decimal("10000")},
        ], "mapping_status": "MAPPED"}
        payload = {"nomor_kontrak": "K-1", "nomor_pi": "PI-1", "nomor_po": "PO-1",
                   "items": [{"item_key": "pi-1", "nilai_actual": "115"},
                             {"item_key": "pi-2", "nilai_actual": "287.5"}]}
        with patch.object(services, "ensure_opname_schema"), \
             patch.object(services, "get_opname_context", return_value=context), \
             patch.object(services, "get_db_connection", return_value=self.conn):
            services.save_opname(payload)
        values = [params for sql, params in self.conn.cur.statements
                  if "INSERT INTO database_opname" in sql]
        self.assertEqual(len(values), 2)
        self.assertEqual(values[0][20], Decimal("9297.5"))
        self.assertIsNone(values[1][20])


if __name__ == "__main__":
    unittest.main()
