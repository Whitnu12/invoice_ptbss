import unittest

from modul_dokumen.document_package_renderer import render_saved_opname_html
from modul_dokumen.wcc import generate_wcc_html


class WccSignatureTests(unittest.TestCase):
    def master_pi(self, second_approver):
        return {
            "prepared_by_name": "Pembuat PI",
            "prepared_by_title": "Supervisor",
            "diwakili_oleh": "Perwakilan kontrak",
            "selaku": "Manajer kontrak",
            "approved_by_1": "Penyetuju Satu",
            "approved_by_title_1": "Jabatan Satu",
            "approved_by_2": second_approver,
            "approved_by_title_2": "Jabatan Dua",
        }

    def render_wcc(self, second_approver):
        rows = [{"nomor_kontrak": "K-1", "pi_no": "PI-1", "total_harga": 1000}]
        return generate_wcc_html(rows, "K-1", "PI-1", {"master_pi": self.master_pi(second_approver)})

    def test_only_prepared_and_approved_when_second_approver_is_empty(self):
        for value in ("", "  ", "tidak ada / kosong", "--- (Tidak Ada / Kosong) ---", "NULL"):
            with self.subTest(second_approver=value):
                html = self.render_wcc(value)
                self.assertIn("Prepared by,", html)
                self.assertIn("Approved by,", html)
                self.assertNotIn("Reviewed by,", html)
                self.assertIn("Penyetuju Satu", html)
                self.assertNotIn("Jabatan Dua", html)
                self.assertNotIn("Perwakilan kontrak", html)
                self.assertNotIn("Imron Maulana", html)
                self.assertNotIn("Onesimus Suryadi", html)

    def test_first_approver_reviews_when_second_approver_exists(self):
        html = self.render_wcc("Penyetuju Dua")
        self.assertIn("Prepared by,", html)
        self.assertIn("Reviewed by,", html)
        self.assertIn("Approved by,", html)
        self.assertLess(html.index("Reviewed by,"), html.index("Penyetuju Satu"))
        self.assertLess(html.index("Approved by,"), html.index("Penyetuju Dua"))
        self.assertIn("Jabatan Satu", html)
        self.assertIn("Jabatan Dua", html)
        self.assertNotIn("Perwakilan kontrak", html)

    def test_saved_opname_in_package_uses_the_same_roles(self):
        saved = {"tanggal_opname": "2026-10-16", "items": {
            "1": {"kategori": "Jasa", "description": "Pekerjaan", "uom": "Ls",
                  "po_vol": 1, "unit_price": 1000, "current_vol": 1},
        }}
        for second_approver, reviewed in (("tidak ada / kosong", False), ("Penyetuju Dua", True)):
            with self.subTest(second_approver=second_approver):
                html = render_saved_opname_html(
                    saved,
                    transaksi_list=[{
                        "approved_by_2": "Nama lama dari rincian transaksi",
                        "approved_by_1": "Nama lama lainnya",
                        "prepared_by_name": "Pembuat lama",
                    }],
                    nomor_kontrak="K-1", pi_no="PI-1",
                    master_pi=self.master_pi(second_approver),
                )
                self.assertEqual("Reviewed by," in html, reviewed)
                self.assertIn("Penyetuju Satu", html)
                self.assertEqual("Penyetuju Dua" in html, reviewed)
                self.assertNotIn("Perwakilan kontrak", html)
                self.assertNotIn("Nama lama dari rincian transaksi", html)
                self.assertNotIn("Nama lama lainnya", html)
                self.assertNotIn("Pembuat lama", html)


if __name__ == "__main__":
    unittest.main()
