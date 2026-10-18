import unittest

from modul_dokumen.bamp import generate_bamp_html
from modul_dokumen.basp import generate_basp_html
from modul_dokumen.bastb import generate_bastb_html
from modul_dokumen.proforma_invoice import generate_proforma_invoice_html
from modul_dokumen.rincian_pekerjaan import generate_rincian_pekerjaan_html
from modul_dokumen.master_package_config import persistent_defaults


class DocumentSignerSourceTests(unittest.TestCase):
    def setUp(self):
        self.master = {
            "nomor_kontrak": "K-1", "pi_no": "PI-1",
            "diwakili_oleh": "Wakil PI Pertama", "selaku": "Jabatan PI Pertama",
            "diwakili_oleh_p2": "Wakil PI Kedua", "selaku_p2": "Jabatan PI Kedua",
            "prepared_by_name": "Pembuat PI Aktual", "prepared_by_title": "Jabatan Pembuat",
            "approved_by_1": "Pemeriksa PI Aktual", "approved_by_title_1": "Jabatan Pemeriksa",
        }
        self.jasa = {
            "nomor_kontrak": "K-1", "pi_no": "PI-1", "kategori": "MONTHLY BASIS",
            "deskripsi_pekerjaan": "Pekerjaan jasa", "qty": 1,
            "unit": "Ls", "harga_satuan": 1000,
            "diwakili_oleh": "Wakil lama transaksi",
        }
        self.barang = {**self.jasa, "kategori": "MATERIAL", "deskripsi_pekerjaan": "Barang"}

    def test_berita_acara_representatives_follow_selected_pi(self):
        for generator, rows in (
            (generate_bamp_html, [self.jasa]),
            (generate_basp_html, [self.jasa]),
            (generate_bastb_html, [self.barang]),
        ):
            with self.subTest(generator=generator.__name__):
                html = generator(rows, "K-1", "PI-1", {"master_pi": self.master})
                self.assertIn("Wakil PI Pertama", html)
                self.assertIn("Wakil PI Kedua", html)
                self.assertNotIn("Wakil lama transaksi", html)

    def test_berita_acara_does_not_insert_sample_people_when_pi_fields_empty(self):
        empty_master = {"nomor_kontrak": "K-1", "pi_no": "PI-1"}
        for generator, rows in (
            (generate_bamp_html, [self.jasa]),
            (generate_basp_html, [self.jasa]),
            (generate_bastb_html, [self.barang]),
        ):
            with self.subTest(generator=generator.__name__):
                html = generator(rows, "K-1", "PI-1", {"master_pi": empty_master})
                self.assertNotIn("Ronny Dwi Purnomo", html)
                self.assertNotIn("Ir. Ferry Tatimu", html)
                self.assertNotIn("Wakil lama transaksi", html)

    def test_proforma_uses_pi_preparer_when_no_document_signer_is_stored(self):
        html = generate_proforma_invoice_html(
            [self.jasa], "K-1", "PI-1", {"master_pi": self.master}
        )
        self.assertIn("Pembuat PI Aktual", html)
        self.assertIn("Jabatan Pembuat", html)
        self.assertNotIn("Onesimus Suriadi", html)

    def test_proforma_keeps_explicit_signer_for_selected_pi(self):
        row = {**self.jasa, "penandatangan_nama": "Pejabat PI Khusus",
               "penandatangan_jabatan": "Jabatan Khusus"}
        html = generate_proforma_invoice_html(
            [row], "K-1", "PI-1", {"master_pi": self.master}
        )
        self.assertIn("Pejabat PI Khusus", html)
        self.assertIn("Jabatan Khusus", html)
        self.assertNotIn("Pembuat PI Aktual", html)

    def test_rincian_signers_follow_selected_pi(self):
        html = generate_rincian_pekerjaan_html(
            [self.jasa], "K-1", "PI-1", {"master_pi": self.master}
        )
        self.assertIn("Pembuat PI Aktual", html)
        self.assertIn("Jabatan Pembuat", html)
        self.assertIn("Pemeriksa PI Aktual", html)
        self.assertIn("Jabatan Pemeriksa", html)
        self.assertNotIn("Yanuar Wiranata", html)
        self.assertNotIn("Onesimus Suriadi", html)

    def test_rincian_omits_names_when_pi_signers_are_empty(self):
        html = generate_rincian_pekerjaan_html(
            [self.jasa], "K-1", "PI-1", {"master_pi": {"nomor_kontrak": "K-1", "pi_no": "PI-1"}}
        )
        self.assertIn("DIBUAT OLEH", html)
        self.assertIn("DIPERIKSA", html)
        self.assertNotIn("Yanuar Wiranata", html)
        self.assertNotIn("Onesimus Suriadi", html)

    def test_package_does_not_reuse_legacy_director_signature_by_default(self):
        self.assertEqual(persistent_defaults()["ttd_3"], "")


if __name__ == "__main__":
    unittest.main()
