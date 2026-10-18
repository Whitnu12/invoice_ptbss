from unittest.mock import MagicMock, patch

import pytest
from flask import Flask
from mysql.connector.errors import DatabaseError

from modul_po import master_po


@pytest.fixture
def client():
    app = Flask(__name__)
    app.secret_key = 'test-only'
    app.register_blueprint(master_po.master_po_bp)
    with app.test_client() as client:
        with client.session_transaction() as session:
            session['logged_in'] = True
        with patch.object(master_po, 'bootstrap_master_po'):
            yield client


def test_detail_returns_header_and_items(client):
    connection = MagicMock()
    cursor = connection.__enter__.return_value.cursor.return_value
    cursor.fetchone.return_value = {'id': 7, 'nomor_po': 'PO-7', 'total_plafon': 1000}
    cursor.fetchall.return_value = [{'id': 1, 'qty_used': 2, 'nilai_used': 200}]
    with patch.object(master_po, 'get_db_connection', return_value=connection):
        response = client.get('/master-po/api/7')
    assert response.status_code == 200
    assert response.json['data']['header']['id'] == 7
    assert response.json['data']['items'][0]['nilai_used'] == 200


def test_missing_detail_is_json_404(client):
    connection = MagicMock()
    connection.__enter__.return_value.cursor.return_value.fetchone.return_value = None
    with patch.object(master_po, 'get_db_connection', return_value=connection):
        response = client.get('/master-po/api/999')
    assert response.status_code == 404
    assert response.json['success'] is False


def test_collation_failure_has_traceable_json_code(client):
    with patch.object(master_po, 'get_db_connection', side_effect=DatabaseError('Private SQL text', errno=1267)):
        response = client.get('/master-po/api/7')
    assert response.status_code == 500
    assert response.json['error_code'].startswith('PO-DB-1267-')
    assert 'Private SQL text' not in response.get_data(as_text=True)
