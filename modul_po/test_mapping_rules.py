import unittest
from unittest.mock import patch

from modul_po import master_po


class FakeCursor:
    def __init__(self, rule_rows, transaction_rows):
        self.rule_rows = rule_rows
        self.transaction_rows = transaction_rows
        self.result = []
        self.queries = []
        self.rowcount = 0

    def execute(self, sql, params=()):
        self.queries.append((sql, params))
        self.rowcount = 0
        if "FROM database_po_mapping_rule m" in sql:
            self.result = self.rule_rows
        elif "SELECT nomor_po, kategori" in sql:
            self.result = self.transaction_rows
        elif "UPDATE database_transaksi_rincian" in sql:
            self.rowcount = 1

    def fetchall(self):
        return self.result

    def close(self):
        pass


class FakeConnection:
    def __init__(self, cursor):
        self.cur = cursor
        self.commits = 0

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def cursor(self):
        return self.cur

    def commit(self):
        self.commits += 1

    def rollback(self):
        pass


class MappingRuleTests(unittest.TestCase):
    def test_reference_key_normalizes_legacy_uom_and_personnel_suffix(self):
        self.assertEqual(
            master_po.reference_key("PERSONEL ON CALL", "Rigger man-days", "Day"),
            master_po.reference_key("PERSONEL ON CALL", "Rigger", "man-days"),
        )

    def test_provisional_note_normalization_and_similarity(self):
        self.assertEqual(
            master_po.reference_note("Meeting package HSE & wellservices"),
            master_po.reference_note("Meeting package HSE and wellservices"),
        )
        self.assertGreaterEqual(
            master_po.reference_note_similarity("Pengadaan diesel fuel transportir", "Pengadaan diesel fuel & transportir"),
            0.72,
        )

    def test_future_pi_uses_confirmed_reference_rule(self):
        fingerprint = master_po.po_reference_fingerprint("Jasa", "Sewa Alat", "hari")
        cur = FakeCursor(
            [{"nomor_po": "PO-1", "fingerprint": fingerprint, "po_item_id": 11}],
            [{"nomor_po": "PO-1", "kategori": "Jasa", "deskripsi_pekerjaan": "Sewa Alat",
              "unit": "hari", "po_item_id": None}],
        )
        conn = FakeConnection(cur)
        with patch.object(master_po, "bootstrap_master_po"), \
             patch.object(master_po, "get_db_connection", return_value=conn):
            changed = master_po.apply_po_mapping_rules("K-1", "PI-3")
        self.assertEqual(changed, 1)
        self.assertEqual(conn.commits, 1)
        self.assertTrue(any("UPDATE database_transaksi_rincian" in sql for sql, _ in cur.queries))

    def test_does_not_override_manual_mapping(self):
        fingerprint = master_po.po_reference_fingerprint("Jasa", "Sewa Alat", "hari")
        cur = FakeCursor(
            [{"nomor_po": "PO-1", "fingerprint": fingerprint, "po_item_id": 11}],
            [{"nomor_po": "PO-1", "kategori": "Jasa", "deskripsi_pekerjaan": "Sewa Alat",
              "unit": "hari", "po_item_id": 99}],
        )
        conn = FakeConnection(cur)
        with patch.object(master_po, "bootstrap_master_po"), \
             patch.object(master_po, "get_db_connection", return_value=conn):
            changed = master_po.apply_po_mapping_rules("K-1", "PI-3")
        self.assertEqual(changed, 0)
        self.assertFalse(any("UPDATE database_transaksi_rincian" in sql for sql, _ in cur.queries))

    def test_future_provisional_pi_uses_bucket_despite_different_description_and_unit(self):
        fingerprint = master_po.po_reference_fingerprint("PROVISIONAL SUM", "Kabel", "Kg")
        cur = FakeCursor(
            [{"nomor_po": "PO-1", "fingerprint": fingerprint, "po_item_id": 11}],
            [{"nomor_po": "PO-1", "kategori": "PROFESSIONAL SUM",
              "deskripsi_pekerjaan": "Logistik", "unit": "AU", "po_item_id": None}],
        )
        with patch.object(master_po, "bootstrap_master_po"), \
             patch.object(master_po, "get_db_connection", return_value=FakeConnection(cur)):
            changed = master_po.apply_po_mapping_rules("K-1", "PI-4")
        self.assertEqual(changed, 1)


if __name__ == "__main__":
    unittest.main()
