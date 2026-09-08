import json
import re
import smtplib

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select

from app.db import EmailOutbox, Record, Session, engine
from app.main import app
from app import mailer


@pytest.fixture
def client():
    with TestClient(app) as client:
        yield client


@pytest.fixture
def smtp(monkeypatch):
    settings = {'SMTP_HOST': 'smtp.company.example', 'SMTP_PORT': '465',
                'SMTP_USERNAME': 'sender@company.example', 'SMTP_PASSWORD': 'unit-test-secret',
                'SMTP_FROM': 'sender@company.example', 'SMTP_USE_TLS': 'false',
                'SMTP_USE_SSL': 'true', 'SMTP_TIMEOUT_SECONDS': '15',
                'PUBLIC_APP_URL': 'https://greta-test.example'}
    for key, value in settings.items():
        monkeypatch.setenv(key, value)
    class FakeSMTP:
        instances = []
        messages = []
        error = None
        def __init__(self, host, port, **kwargs):
            self.host, self.port, self.options = host, port, kwargs
            self.calls = []
            self.instances.append(self)
        def ehlo(self): self.calls.append('ehlo')
        def starttls(self, **kwargs):
            assert kwargs['context'].check_hostname
            self.calls.append('starttls')
        def login(self, username, password):
            assert (username, password) == ('sender@company.example', 'unit-test-secret')
            self.calls.append('login')
            if self.error == 'auth':
                raise smtplib.SMTPAuthenticationError(535, b'credentials rejected')
        def noop(self):
            self.calls.append('noop')
            return 250, b'OK'
        def send_message(self, message, **kwargs):
            if self.error == 'recipient':
                raise smtplib.SMTPRecipientsRefused({message['To']: (550, b'Rejected')})
            self.messages.append((message, kwargs))
            if self.error == 'ambiguous':
                raise smtplib.SMTPServerDisconnected('Disconnected after DATA')
            return {}
        def quit(self):
            self.calls.append('quit')
            if self.error == 'quit':
                raise smtplib.SMTPServerDisconnected('Disconnected after acceptance')
        def close(self): self.calls.append('close')
    monkeypatch.setattr(mailer.smtplib, 'SMTP_SSL', FakeSMTP)
    monkeypatch.setattr(mailer.smtplib, 'SMTP', FakeSMTP)
    yield FakeSMTP
    with Session() as db:
        db.execute(delete(EmailOutbox))
        db.commit()


def role(client, name='Buyer'):
    assert client.post('/api/v1/auth/demo', json={'role': name}).status_code == 200


def issued_rfi(client):
    role(client)
    supplier = client.post('/api/v1/suppliers', json={
        'name': 'Test Turbomachinery', 'country': 'Indonesia',
        'category_id': 'rotating', 'email': 'contact@vendor.test',
    })
    assert supplier.status_code == 200, supplier.text
    rfi = client.post('/api/v1/rfis', json={
        'title': 'Invitation integration test', 'category_id': 'rotating',
        'closing_date': '2099-12-20', 'requirement': 'Require industrial compressor specifications.',
        'supplier_ids': [supplier.json()['id']],
        'questions': [{'id': 'q1', 'text': 'Lead time in weeks', 'type': 'integer', 'required': True}],
    })
    assert rfi.status_code == 200, rfi.text
    id = rfi.json()['id']
    for status in ['Internal Review', 'Approved', 'Issued']:
        result = client.post(f'/api/v1/rfis/{id}/status', json={'status': status})
        assert result.status_code == 200, result.text
    return id


def queue(client, id):
    response = client.post(f'/api/v1/rfis/{id}/emails', json={})
    assert response.status_code == 200, response.text
    return response.json()[0]


def delivery(client, id):
    return client.get(f'/api/v1/rfis/{id}/emails').json()[0]


def test_ssl_authentication_test_never_sends_email(client, smtp):
    role(client)
    assert client.get('/api/v1/admin/email').status_code == 403
    assert client.post('/api/v1/admin/email/test', json={}).status_code == 403
    role(client, 'Admin')
    response = client.get('/api/v1/admin/email')
    assert response.json()['invitations_ready'] is True
    assert 'unit-test-secret' not in response.text and 'password' not in response.text
    result = client.post('/api/v1/admin/email/test', json={})
    assert result.status_code == 200, result.text
    assert result.json()['email_sent'] is False and result.json()['authenticated']
    instance = smtp.instances[0]
    assert (instance.host, instance.port, instance.options['timeout']) == ('smtp.company.example', 465, 15)
    assert instance.options['context'].check_hostname
    assert instance.calls == ['ehlo', 'login', 'noop', 'quit']
    assert smtp.messages == []


def test_starttls_and_invalid_transport(smtp, monkeypatch):
    monkeypatch.setenv('SMTP_USE_SSL', 'false')
    monkeypatch.setenv('SMTP_USE_TLS', 'true')
    monkeypatch.setenv('SMTP_PORT', '587')
    assert mailer.connection_test()['transport'] == 'STARTTLS'
    assert smtp.instances[0].calls == ['ehlo', 'starttls', 'ehlo', 'login', 'noop', 'quit']
    monkeypatch.setenv('SMTP_USE_SSL', 'true')
    with pytest.raises(HTTPException): mailer.SMTPSettings.load()
    assert len(smtp.instances) == 1


def test_queue_is_encrypted_idempotent_and_generates_working_response_link(client, smtp):
    id = issued_rfi(client)
    old = client.post(f'/api/v1/rfis/{id}/invitations', json={}).json()[0]['path'].split('=')[1]
    first = queue(client, id)
    assert first['status'] == 'PENDING' and first['attempts'] == 0
    assert queue(client, id)['id'] == first['id']
    assert not smtp.instances
    assert client.get('/api/v1/respond/' + old).status_code == 410
    with Session() as db:
        row = db.get(EmailOutbox, first['id'])
        assert 'invitation=' not in row.payload and 'https://' not in row.payload
        payload = json.loads(mailer.cipher().decrypt(row.payload.encode()))
        token = re.search(r'\?invitation=(\S+)', payload['body']).group(1)
        assert token not in db.get(Record, row.invitation_id).data.values()
        assert db.scalar(select(func.count()).select_from(EmailOutbox)) == 1
    assert mailer.process_pending_email() is True
    assert mailer.process_pending_email() is False
    assert delivery(client, id)['status'] == 'SENT'
    with Session() as db: assert db.get(EmailOutbox, first['id']).payload is None
    message, envelope = smtp.messages[0]
    assert envelope['to_addrs'] == ['contact@vendor.test']
    assert '2099-12-20' in message.get_content() and 'https://greta-test.example/?invitation=' in message.get_content()
    assert token not in client.get(f'/api/v1/rfis/{id}/emails').text
    assert client.get('/api/v1/respond/' + token).json()['supplier'] == 'Test Turbomachinery'
    assert client.post('/api/v1/respond/' + token, json={'answers': {'q1': '12'}, 'submit': True}).status_code == 200
    assert queue(client, id)['id'] == first['id']
    assert mailer.process_pending_email() is False and len(smtp.messages) == 1


def test_missing_public_url_and_scope_prevent_queue(client, smtp, monkeypatch):
    id = issued_rfi(client)
    role(client, 'Admin')
    assert client.post(f'/api/v1/rfis/{id}/emails', json={}).status_code == 403
    role(client, 'Fungsi Pengguna')
    assert client.get(f'/api/v1/rfis/{id}/emails').status_code == 403
    role(client)
    for url in ['', 'http://localhost:3000', 'https://127.0.0.1', 'https://app.local']:
        monkeypatch.setenv('PUBLIC_APP_URL', url)
        assert client.post(f'/api/v1/rfis/{id}/emails', json={}).status_code == 503
    monkeypatch.setenv('PUBLIC_APP_URL', 'https://greta-test.example')
    with Session() as db:
        rfi = db.get(Record, id)
        rfi.region = 'Region 2'
        db.commit()
    assert client.post(f'/api/v1/rfis/{id}/emails', json={}).status_code == 404
    assert not smtp.instances
    with Session() as db: assert db.scalar(select(func.count()).select_from(EmailOutbox)) == 0


def test_invalid_recipient_and_rfi_state_leave_no_partial_queue(client, smtp):
    id = issued_rfi(client)
    with Session() as db:
        rfi = db.get(Record, id)
        rfi.data = {**rfi.data, 'supplier_ids': [*rfi.data['supplier_ids'], 's1']}
        db.commit()
    assert client.post(f'/api/v1/rfis/{id}/emails', json={}).status_code == 422
    with Session() as db: assert db.scalar(select(func.count()).select_from(EmailOutbox)) == 0
    assert client.post(f'/api/v1/rfis/{id}/amend', json={}).status_code == 200
    assert client.post(f'/api/v1/rfis/{id}/emails', json={}).status_code == 409
    assert not smtp.instances


@pytest.mark.parametrize('error', ['auth', 'recipient'])
def test_confirmed_failure_requires_explicit_retry(client, smtp, error):
    id = issued_rfi(client)
    row = queue(client, id)
    smtp.error = error
    assert mailer.process_pending_email()
    assert delivery(client, id)['status'] == 'FAILED'
    assert mailer.process_pending_email() is False
    assert queue(client, id)['id'] == row['id']
    assert mailer.process_pending_email() is False
    smtp.error = None
    result = client.post(f"/api/v1/rfis/{id}/emails/{row['id']}/retry", json={})
    assert result.status_code == 200, result.text
    assert mailer.process_pending_email()
    assert delivery(client, id)['status'] == 'SENT' and delivery(client, id)['attempts'] == 2


def test_ambiguous_delivery_never_retries_automatically(client, smtp):
    id = issued_rfi(client)
    row = queue(client, id)
    smtp.error = 'ambiguous'
    assert mailer.process_pending_email()
    assert delivery(client, id)['status'] == 'UNKNOWN'
    assert mailer.process_pending_email() is False
    assert client.post(f"/api/v1/rfis/{id}/emails/{row['id']}/retry", json={}).status_code == 409
    queue(client, id)
    assert mailer.process_pending_email() is False and len(smtp.messages) == 1


def test_quit_failure_after_acceptance_is_still_sent(client, smtp):
    id = issued_rfi(client)
    queue(client, id)
    smtp.error = 'quit'
    assert mailer.process_pending_email()
    assert delivery(client, id)['status'] == 'SENT'
    assert mailer.process_pending_email() is False and len(smtp.messages) == 1


@pytest.mark.parametrize('action', ['amend', 'invitations'])
def test_revoked_invitation_is_cancelled_before_sending(client, smtp, action):
    id = issued_rfi(client)
    queue(client, id)
    assert client.post(f'/api/v1/rfis/{id}/{action}', json={}).status_code == 200
    assert mailer.process_pending_email()
    assert delivery(client, id)['status'] == 'CANCELLED'
    assert not smtp.instances


@pytest.mark.skipif(engine.dialect.name != 'postgresql', reason='PostgreSQL row-lock concurrency')
def test_concurrent_requests_and_workers_do_not_duplicate_email(client, smtp):
    from concurrent.futures import ThreadPoolExecutor
    id = issued_rfi(client)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: queue(client, id), range(2)))
    assert results[0]['id'] == results[1]['id']
    with ThreadPoolExecutor(max_workers=2) as pool:
        processed = list(pool.map(lambda _: mailer.process_pending_email(), range(2)))
    assert sum(processed) == 1 and len(smtp.messages) == 1
    assert delivery(client, id)['status'] == 'SENT'
