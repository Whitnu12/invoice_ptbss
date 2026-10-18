import unittest
import shutil
import subprocess
from pathlib import Path
from unittest.mock import patch

from bs4 import BeautifulSoup

from app import app
from modul_navigasi.routes import _invoice_payload, invoice_tax


class InvoiceTaxAssetTests(unittest.TestCase):
    def test_page_links_directly_to_stylesheet(self):
        with app.test_request_context("/modul/invoice-tax"):
            with patch("modul_navigasi.routes.can_write", return_value=True):
                html = invoice_tax.__wrapped__()

        soup = BeautifulSoup(html, "html.parser")
        links = soup.select('link[rel="stylesheet"][href="/static/css/invoice_tax.css"]')
        self.assertEqual(len(links), 1)
        self.assertIsNotNone(links[0].find_parent("body"))
        self.assertFalse(soup.select("#invoiceTaxStyles"))
        self.assertEqual(len(soup.select(".invoice-tax-page")), 1)
        self.assertEqual(soup.select_one(".invoice-tax-page")["data-payment-flow-version"], "soft-delete-1")
        self.assertEqual(len(soup.select("#invoiceRows")), 1)
        self.assertIsNotNone(soup.select_one("#invoiceNotice[role='alert'][hidden]"))
        self.assertIsNotNone(soup.select_one("#sourcePreview.source-preview[hidden]"))
        self.assertEqual(len(soup.select("table")), 3)
        self.assertFalse(soup.select("table button"))
        self.assertEqual(len(soup.select(".invoice-form-grid")), 3)
        self.assertEqual(len(soup.select(".invoice-checkbox-label")), 4)
        for selector in (
            ".invoice-picker-card", ".invoice-selection-empty", ".invoice-tabs",
            ".payment-kpis", ".payment-event-form", "#panel-tax", "#panel-archive",
        ):
            self.assertIsNotNone(soup.select_one(f".invoice-tax-page {selector}"), selector)
        self.assertNotIn("Fondasi Invoice Resmi normalized", html)
        self.assertNotIn("Daftar Invoice Resmi", html)
        self.assertIsNone(soup.select_one("#sidebarToggle"))
        self.assertIsNone(soup.select_one("#sidebarBackdrop"))

    def test_stylesheet_is_served_as_css(self):
        css_path = Path(app.static_folder) / "css" / "invoice_tax.css"
        stylesheet = css_path.read_bytes()

        response = app.test_client().get("/static/css/invoice_tax.css")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "text/css")
        self.assertEqual(response.data, stylesheet)
        response.close()
        for selector in (
            ".invoice-tax-page .invoice-picker-card",
            ".invoice-tax-page .invoice-selection-empty",
            ".invoice-tax-page .invoice-tabs",
            ".invoice-tax-page .payment-kpis",
            ".invoice-tax-page .payment-event-extra-grid",
            ".invoice-tax-page .invoice-form-grid",
            ".invoice-tax-page .invoice-checkbox-label",
            ".invoice-tax-page .invoice-notice",
            ".invoice-tax-page .source-preview-table",
        ):
            self.assertIn(selector.encode(), stylesheet, selector)
        self.assertEqual(stylesheet.count(b"{"), stylesheet.count(b"}"))

    @unittest.skipUnless(shutil.which("node"), "Node.js tidak tersedia")
    def test_rendered_invoice_script_has_valid_javascript(self):
        for can_write in (True, False):
            with self.subTest(can_write=can_write):
                with app.test_request_context("/modul/invoice-tax"):
                    with patch("modul_navigasi.routes.can_write", return_value=can_write):
                        html = invoice_tax.__wrapped__()
                script = BeautifulSoup(html, "html.parser").select_one(".invoice-tax-page script")
                self.assertIsNotNone(script)
                result = subprocess.run(
                    ["node", "--check"], input=script.string or "",
                    text=True, capture_output=True, check=False,
                )
                self.assertEqual(result.returncode, 0, result.stderr)

    def test_source_preview_and_api_errors_are_not_silent(self):
        source = (Path(app.template_folder) / "invoice_tax.html").read_text(encoding="utf-8")
        self.assertIn("transactions.map((row, index)", source)
        self.assertNotIn("transactions.slice(0, 8)", source)
        for value in ("row.qty", "row.unit", "row.harga_satuan", "row.total_harga", "item.nilai_gross_sumber"):
            self.assertIn(value, source)
        self.assertIn("Server mengembalikan respons yang tidak dapat dibaca", source)
        self.assertIn("invoiceNotice.hidden = false", source)
        self.assertNotIn("response.json().then", source)

    def test_customer_details_reuse_saved_invoice_data(self):
        source = (Path(app.template_folder) / "invoice_tax.html").read_text(encoding="utf-8")
        with app.test_request_context("/modul/invoice-tax"):
            with patch("modul_navigasi.routes.can_write", return_value=True):
                soup = BeautifulSoup(invoice_tax.__wrapped__(), "html.parser")
        self.assertIsNotNone(soup.select_one("#sourceCustomer[readonly]"))
        self.assertIsNotNone(soup.select_one("#sourceAddress[readonly]"))
        self.assertIsNotNone(soup.select_one("[name='npwp_customer']"))
        self.assertIsNotNone(soup.select_one("#customerReuseHint"))
        self.assertIn("const reuseSavedCustomer", source)
        self.assertIn("knownNpwp.size === 1", source)
        self.assertIn("knownNpwp.size > 1", source)
        self.assertIn("customer_name: activeInvoiceData.customer", source)
        self.assertIn("customer_npwp: activeInvoiceData.npwp_customer", source)

    def test_customer_fields_are_kept_in_invoice_payload(self):
        payload = _invoice_payload({
            "kontrak_id": 1, "nomor_invoice": "TEST/001",
            "customer": "PT Contoh", "alamat_customer": "Jakarta",
            "npwp_customer": "01.234.567.8-999.000",
        })
        self.assertEqual(payload["customer"], "PT Contoh")
        self.assertEqual(payload["alamat_customer"], "Jakarta")
        self.assertEqual(payload["npwp_customer"], "01.234.567.8-999.000")

    def test_payment_has_one_input_form_and_registered_history_endpoint(self):
        with app.test_request_context("/modul/invoice-tax"):
            with patch("modul_navigasi.routes.can_write", return_value=True):
                soup = BeautifulSoup(invoice_tax.__wrapped__(), "html.parser")
        panel = soup.select_one("#panel-payment")
        self.assertEqual(len(panel.select("form")), 1)
        self.assertIsNotNone(panel.select_one("#paymentEventForm [name='tanggal_penyerahan']"))
        self.assertIsNone(panel.select_one("#paymentForm"))
        self.assertIsNone(panel.select_one("[name='tanggal_pelunasan']"))
        self.assertIsNone(panel.select_one("[name='tanggal_jatuh_tempo']"))
        self.assertIsNotNone(panel.select_one("#deletedPaymentHistory[hidden]"))
        methods = set().union(*(rule.methods for rule in app.url_map.iter_rules()
                                if rule.rule == "/api/modul-3/payment-events"))
        self.assertTrue({"GET", "POST"}.issubset(methods))
        delete_methods = set().union(*(rule.methods for rule in app.url_map.iter_rules()
                                       if rule.rule == "/api/modul-3/payment-events/<int:event_id>"))
        self.assertIn("DELETE", delete_methods)


if __name__ == "__main__":
    unittest.main()
