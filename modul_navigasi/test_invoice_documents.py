import unittest
from decimal import Decimal
from unittest.mock import patch

from bs4 import BeautifulSoup

from app import app
from invoice_documents import invoice_context, receipt_context
from modul_navigasi.routes import invoice_official, invoice_receipt


INVOICE = {
    "id": 7, "nomor_invoice": "127/BSS-JOB/VI/2026", "nomor_kontrak": "7201250141",
    "pi_no": "004/BSS-JOB/WS/IV/2026", "nomor_po": "4500011236",
    "nomor_sa_wan": "1000025165", "customer": "JOB Pertamina - Medco E&P Tomori Sulawesi",
    "alamat_customer": "Jakarta", "npwp_customer": "001.234.567.8-999.000",
    "tanggal_invoice": "2026-06-17", "jatuh_tempo": "2026-07-17",
    "nilai_gross": Decimal("890007885"), "diskon_nominal": 0,
    "nilai_dpp": Decimal("890007885"), "ppn_nominal": Decimal("97900867"),
    "pph_nominal": Decimal("0"), "total_netto": Decimal("987908752"),
}
TRANSACTIONS = [{
    "nomor_wan_sa": "1000025165", "kategori": "PROVISIONAL SUM",
    "deskripsi_pekerjaan": "Add Cost + Fee 15%", "qty": 1, "unit": "LOT",
    "harga_satuan": Decimal("890007885"), "keterangan": "Sewa peralatan",
}]


class InvoiceDocumentTests(unittest.TestCase):
    def test_legacy_layout_and_saved_values_are_rendered(self):
        with app.test_request_context("/modul/invoice-tax/invoice/7"):
            from flask import render_template
            invoice_html = render_template("invoice_official.html", **invoice_context(INVOICE, TRANSACTIONS))
            receipt_html = render_template("invoice_receipt.html", **receipt_context(INVOICE))
        invoice_soup = BeautifulSoup(invoice_html, "html.parser")
        receipt_soup = BeautifulSoup(receipt_html, "html.parser")
        self.assertIn("FM-AK-11 Rev: 00", invoice_html)
        self.assertIn("PAYMENT INSTRUCTION", invoice_html)
        self.assertIn("Add Cost + Fee 15%", invoice_html)
        self.assertIn("Rp 987,908,752", invoice_html)
        self.assertEqual(len(invoice_soup.select(".invoice-container")), 1)
        self.assertEqual(len(receipt_soup.select(".receipt-box")), 1)
        self.assertIn("Rp 987.908.752,00", receipt_html)
        self.assertIn("KT-127-BSS-JOB-VI-2026", receipt_html)
        self.assertIn("1000025165", receipt_html)

    def test_document_routes_preview_download_and_not_found(self):
        with patch("modul_navigasi.routes._invoice_document_record", return_value=INVOICE), patch(
            "modul_navigasi.routes.muat_transaksi_terfilter", return_value=TRANSACTIONS
        ), patch(
            "modul_navigasi.routes.muat_pi_master", return_value=[]
        ):
            with app.test_request_context("/modul/invoice-tax/invoice/7?download=1"):
                response = invoice_official.__wrapped__(7)
            self.assertEqual(response.status_code, 200)
            self.assertIn("attachment", response.headers["Content-Disposition"])
            self.assertIn("Invoice_127-BSS-JOB-VI-2026.html", response.headers["Content-Disposition"])
            self.assertIn("Add Cost + Fee 15%", response.get_data(as_text=True))
            with app.test_request_context("/modul/invoice-tax/receipt/7"):
                response = invoice_receipt.__wrapped__(7)
            self.assertEqual(response.status_code, 200)
            self.assertNotIn("Content-Disposition", response.headers)
            self.assertIn("KUITANSI PEMBAYARAN", response.get_data(as_text=True))
            with app.test_request_context("/modul/invoice-tax/receipt/7?download=1"):
                response = invoice_receipt.__wrapped__(7)
            self.assertIn("Kuitansi_127-BSS-JOB-VI-2026.html", response.headers["Content-Disposition"])
        with patch("modul_navigasi.routes._invoice_document_record", return_value=None):
            with app.test_request_context("/modul/invoice-tax/invoice/99"):
                self.assertEqual(invoice_official.__wrapped__(99)[1], 404)

    def test_compact_invoice_uses_pi_scope_and_total_with_empty_unit_columns(self):
        scope = "Sewa alat & operasional\nPeriode <Juli> 2026"
        transactions = [
            {**TRANSACTIONS[0], "qty": 1, "harga_satuan": 100},
            {**TRANSACTIONS[0], "qty": 2, "harga_satuan": 200},
            {**TRANSACTIONS[0], "nomor_wan_sa": "WAN-LAIN", "qty": 1, "harga_satuan": 900},
        ]
        with patch("modul_navigasi.routes._invoice_document_record", return_value=dict(INVOICE)), patch(
            "modul_navigasi.routes.muat_transaksi_terfilter", return_value=transactions
        ), patch(
            "modul_navigasi.routes.muat_pi_master", return_value=[{"lingkup_pekerjaan": scope}]
        ) as master_loader:
            with app.test_request_context("/modul/invoice-tax/invoice/7?format=ringkas&download=1"):
                response = invoice_official.__wrapped__(7)
        self.assertEqual(response.status_code, 200)
        self.assertIn("attachment", response.headers["Content-Disposition"])
        master_loader.assert_called_once_with(INVOICE["nomor_kontrak"], INVOICE["pi_no"])
        soup = BeautifulSoup(response.get_data(as_text=True), "html.parser")
        table = soup.select_one(".invoice-items-table")
        self.assertEqual([th.get_text(strip=True) for th in table.select("thead th")],
                         ["No.", "DESCRIPTION", "UNIT", "UNIT PRICE (Rp.)", "AMOUNT (Rp.)"])
        rows = table.find("tbody", recursive=False).find_all("tr", recursive=False)
        self.assertEqual(len(rows), 2)
        cells = rows[0].find_all("td", recursive=False)
        self.assertEqual(len(cells), 5)
        self.assertIn("Sewa alat & operasional", cells[1].get_text())
        self.assertIn("Periode <Juli> 2026", cells[1].get_text())
        self.assertIsNone(cells[1].find("juli"))
        self.assertEqual(cells[2].get_text(strip=True), "")
        self.assertEqual(cells[3].get_text(strip=True), "")
        self.assertEqual(cells[4].get_text(strip=True), "Rp 500")
        self.assertEqual(rows[1].find("td", recursive=False)["colspan"], "3")
        self.assertIn("Rp 987,908,752", rows[1].get_text())

    def test_documents_escape_customer_supplied_html(self):
        modified = {**INVOICE, "customer": "<script>alert(1)</script>"}
        with app.test_request_context("/modul/invoice-tax/receipt/7"):
            from flask import render_template
            rendered = render_template("invoice_receipt.html", **receipt_context(modified))
        self.assertNotIn("<script>", rendered)
        self.assertIn("&lt;script&gt;", rendered)

    def test_page_links_are_scoped_to_selected_invoice(self):
        with app.test_request_context("/modul/invoice-tax"):
            from modul_navigasi.routes import invoice_tax
            with patch("modul_navigasi.routes.can_write", return_value=False):
                rendered = invoice_tax.__wrapped__()
        soup = BeautifulSoup(rendered, "html.parser")
        actions = soup.select_one("#invoiceDocumentActions[hidden]")
        self.assertIsNotNone(actions)
        self.assertEqual(len(actions.select("a")), 6)
        self.assertEqual(len(actions.select("a[download]")), 3)
        self.assertEqual(len(actions.select('a[data-format="lengkap"]')), 2)
        self.assertEqual(len(actions.select('a[data-format="ringkas"]')), 2)
        self.assertIn("navigation.invoice_official", app.view_functions)
        self.assertIn("navigation.invoice_receipt", app.view_functions)


if __name__ == "__main__":
    unittest.main()
